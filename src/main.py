"""CA Search and Scrape - Airtable Integration v1

Workflow:
1. Search for candidate (CA Search V2 logic)
2. If confidence ≥70% → Auto-scrape (CA Scrape V3 logic)
3. If confidence <70% → Return search results only
4. Write results back to Airtable record
"""
from apify import Actor
from playwright.async_api import async_playwright
from datetime import datetime, timezone

# Import search modules (from CA Search V2)
from .modules.auth import login_to_vistage
from .modules.search.search import prepare_search_query, execute_search, extract_name_from_linkedin_slug
from .modules.search.scoring import calculate_match_score, calculate_name_only_score, apply_chicago_tiebreaker

# Import scraping modules (from CA Scrape V3)
from .modules.scrapers.lead_scraper import scrape_lead_details
from .modules.scrapers.contact_scraper import scrape_contact_details
from .modules.scrapers.opportunity_scraper import scrape_opportunity_details
from .modules.output_formatter import format_final_output

# Import Airtable integration
from .modules.airtable_writer import AirtableWriter


async def main() -> None:
    """Main entry point combining search and scrape logic."""
    
    # Record overall start time
    overall_start = datetime.now(timezone.utc)
    search_start = overall_start
    
    async with Actor:
        Actor.log.info('=' * 70)
        Actor.log.info('CA SEARCH AND SCRAPE - AIRTABLE INTEGRATION V1')
        Actor.log.info('=' * 70)
        Actor.log.info(f'Started at: {overall_start.isoformat()}')

        # Get input
        actor_input = await Actor.get_input() or {}

        # Extract Airtable configuration
        airtable_token = actor_input.get('airtable_token', '')
        airtable_base_id = actor_input.get('airtable_base_id', '')
        airtable_table_name = actor_input.get('airtable_table_name', 'HubSpot Sync')
        record_id = actor_input.get('record_id', '')

        # Extract search inputs
        linkedin_slug = actor_input.get('linkedin_slug', '').strip()
        domain = actor_input.get('domain', '').strip()
        search_name = actor_input.get('search_name', '').strip()
        expected_company = actor_input.get('expected_company', '').strip()
        vistage_username = actor_input.get('vistage_username', '')
        vistage_password = actor_input.get('vistage_password', '')

        # Validate Airtable configuration
        if not all([airtable_token, airtable_base_id, record_id]):
            Actor.log.error('Missing required Airtable configuration!')
            await Actor.exit()

        # Initialize Airtable writer
        airtable = AirtableWriter(
            token=airtable_token,
            base_id=airtable_base_id,
            table_name=airtable_table_name,
            record_id=record_id,
            logger=Actor.log
        )

        # Validate credentials
        if not all([vistage_username, vistage_password]):
            Actor.log.error('Missing required credentials!')
            await airtable.write_error('Missing Vistage credentials')
            await Actor.exit()

        # Validate search parameters
        if not linkedin_slug and not domain and not (search_name and expected_company):
            Actor.log.error('Must provide at least one search method!')
            await airtable.write_error('Missing search parameters')
            await Actor.exit()

        # Write initial status to Airtable
        await airtable.write_search_start()
        
        # Prepare search query
        search_query, search_type, search_name_cleaned, expected_company_cleaned, linkedin_url = prepare_search_query(
            linkedin_slug=linkedin_slug,
            domain=domain,
            search_name=search_name,
            expected_company=expected_company,
            logger=Actor.log
        )
        
        Actor.log.info('Launching browser...')

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=Actor.configuration.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context()
            page = await context.new_page()
            
            Actor.log.info('Browser launched successfully')
            
            # ============================================
            # PHASE 1: SEARCH (CA Search V2 Logic)
            # ============================================
            Actor.log.info('')
            Actor.log.info('=' * 70)
            Actor.log.info('PHASE 1: SEARCH')
            Actor.log.info('=' * 70)
            
            # Login ONCE (reuse session for both phases)
            login_success = await login_to_vistage(page, vistage_username, vistage_password, Actor.log)
            if not login_success:
                Actor.log.error('Login failed!')
                await airtable.write_error('Vistage login failed - check credentials')
                await Actor.exit()
            
            # Execute cascading search
            best_match, final_search_type, search_metadata = await execute_search_phase(
                page=page,
                linkedin_slug=linkedin_slug,
                domain=domain,
                search_name_cleaned=search_name_cleaned,
                expected_company_cleaned=expected_company_cleaned,
                linkedin_url=linkedin_url,
                search_query=search_query,
                search_type=search_type
            )
            
            search_end = datetime.now(timezone.utc)
            search_duration = (search_end - search_start).total_seconds()
            
            # Check if match was found
            if not best_match:
                Actor.log.warning('No matches found above 50% threshold')

                output = {
                    'search_successful': False,
                    'match_found': False,
                    'confidence': None,
                    'auto_scraped': False,
                    'message': 'No matches found above 50% confidence threshold',
                    'search_metadata': search_metadata,
                    'timing': {
                        'search_start': search_start.isoformat(),
                        'search_end': search_end.isoformat(),
                        'search_duration_seconds': search_duration
                    }
                }

                await Actor.push_data(output)
                await airtable.write_search_results(output)
                Actor.log.info(f'Search completed in {search_duration:.2f}s - No match found')
                return
            
            # Determine confidence
            match_score = best_match.get('score', 0)
            confidence = 'high' if match_score >= 70.0 else 'needs_review'
            
            Actor.log.info('')
            Actor.log.info(f'Match Score: {match_score}%')
            Actor.log.info(f'Confidence: {confidence}')
            Actor.log.info(f'Search Duration: {search_duration:.2f}s')
            
            # ============================================
            # DECISION POINT: Check Confidence Level
            # ============================================
            
            if confidence != 'high':
                # Medium/Low confidence - STOP after search
                Actor.log.info('')
                Actor.log.info('=' * 70)
                Actor.log.info('⚠️  CONFIDENCE <70% - STOPPING AFTER SEARCH')
                Actor.log.info('=' * 70)

                # Build search metadata with match details
                search_metadata_with_details = {
                    **search_metadata,
                    'name': best_match.get('name'),
                    'company': best_match.get('company'),
                    'title': best_match.get('title'),
                    'msa': best_match.get('msa'),
                    'salesforce_url': best_match.get('salesforce_url'),
                    'section': best_match.get('section'),
                    'record_type': best_match.get('record_type_raw')
                }

                output = {
                    'search_successful': True,
                    'match_found': True,
                    'confidence': confidence,
                    'match_score': match_score,
                    'auto_scraped': False,
                    'name': best_match.get('name'),
                    'company': best_match.get('company'),
                    'title': best_match.get('title'),
                    'msa': best_match.get('msa'),
                    'salesforce_url': best_match.get('salesforce_url'),
                    'section': best_match.get('section'),
                    'record_type': best_match.get('record_type_raw'),
                    'search_metadata': search_metadata_with_details,
                    'message': 'Manual review recommended - scraping skipped',
                    'timing': {
                        'search_start': search_start.isoformat(),
                        'search_end': search_end.isoformat(),
                        'search_duration_seconds': search_duration
                    }
                }

                await Actor.push_data(output)
                await airtable.write_search_results(output)

                Actor.log.info('')
                Actor.log.info('COMPLETE - Search Only')
                Actor.log.info(f'Total Duration: {search_duration:.2f}s')
                return
            
            # ============================================
            # PHASE 2: SCRAPE (CA Scrape V3 Logic)
            # ============================================
            Actor.log.info('')
            Actor.log.info('=' * 70)
            Actor.log.info('✅ CONFIDENCE ≥70% - PROCEEDING TO SCRAPE')
            Actor.log.info('=' * 70)
            
            scrape_start = datetime.now(timezone.utc)
            salesforce_url = best_match.get('salesforce_url')
            
            try:
                scrape_result = await execute_scrape_phase(page, salesforce_url, Actor.log)
                
                scrape_end = datetime.now(timezone.utc)
                scrape_duration = (scrape_end - scrape_start).total_seconds()
                total_duration = (scrape_end - overall_start).total_seconds()
                
                Actor.log.info(f'Scrape Duration: {scrape_duration:.2f}s')
                Actor.log.info(f'Total Duration: {total_duration:.2f}s')
                
                # Build combined output
                output = {
                    'search_successful': True,
                    'match_found': True,
                    'confidence': confidence,
                    'match_score': match_score,
                    'auto_scraped': True,
                    'search_metadata': {
                        'search_type': search_metadata['search_type'],
                        'search_attempts': search_metadata['search_attempts'],
                        'total_results_found': search_metadata['total_results_found'],
                        'name': best_match.get('name'),
                        'company': best_match.get('company'),
                        'title': best_match.get('title'),
                        'msa': best_match.get('msa'),
                        'salesforce_url': salesforce_url,
                        'section': best_match.get('section'),
                        'record_type': best_match.get('record_type_raw')
                    },
                    'scrape_data': scrape_result,
                    'timing': {
                        'search_start': search_start.isoformat(),
                        'search_end': search_end.isoformat(),
                        'search_duration_seconds': search_duration,
                        'scrape_start': scrape_start.isoformat(),
                        'scrape_end': scrape_end.isoformat(),
                        'scrape_duration_seconds': scrape_duration,
                        'total_duration_seconds': total_duration
                    }
                }
                
                await Actor.push_data(output)
                await airtable.write_search_results(output)

                Actor.log.info('')
                Actor.log.info('=' * 70)
                Actor.log.info('✅ COMPLETE - SEARCH + SCRAPE')
                Actor.log.info('=' * 70)
                Actor.log.info(f'Search: {search_duration:.2f}s | Scrape: {scrape_duration:.2f}s | Total: {total_duration:.2f}s')

            except Exception as e:
                Actor.log.error(f'Scrape phase failed: {e}')
                
                scrape_end = datetime.now(timezone.utc)
                scrape_duration = (scrape_end - scrape_start).total_seconds()
                total_duration = (scrape_end - overall_start).total_seconds()
                
                # Build search metadata with match details
                search_metadata_with_details = {
                    **search_metadata,
                    'name': best_match.get('name'),
                    'company': best_match.get('company'),
                    'title': best_match.get('title'),
                    'msa': best_match.get('msa'),
                    'salesforce_url': salesforce_url,
                    'section': best_match.get('section'),
                    'record_type': best_match.get('record_type_raw')
                }

                # Return search results with error message
                output = {
                    'search_successful': True,
                    'match_found': True,
                    'confidence': confidence,
                    'match_score': match_score,
                    'auto_scraped': False,
                    'scrape_error': str(e),
                    'name': best_match.get('name'),
                    'company': best_match.get('company'),
                    'title': best_match.get('title'),
                    'msa': best_match.get('msa'),
                    'salesforce_url': salesforce_url,
                    'section': best_match.get('section'),
                    'record_type': best_match.get('record_type_raw'),
                    'search_metadata': search_metadata_with_details,
                    'message': 'Search succeeded but scrape failed - use salesforce_url manually',
                    'timing': {
                        'search_start': search_start.isoformat(),
                        'search_end': search_end.isoformat(),
                        'search_duration_seconds': search_duration,
                        'scrape_start': scrape_start.isoformat(),
                        'scrape_end': scrape_end.isoformat(),
                        'scrape_duration_seconds': scrape_duration,
                        'total_duration_seconds': total_duration
                    }
                }

                await Actor.push_data(output)
                await airtable.write_search_results(output)


async def execute_search_phase(
    page,
    linkedin_slug: str,
    domain: str,
    search_name_cleaned: str,
    expected_company_cleaned: str,
    linkedin_url: str,
    search_query: str,
    search_type: str
) -> tuple:
    """
    Execute CA Search V2 cascading search logic.
    
    Returns:
        (best_match dict, final_search_type str, search_metadata dict)
    """
    best_match = None
    final_search_type = None
    total_results_found = 0
    search_attempts = []
    
    # Try LinkedIn search first
    if linkedin_slug and not best_match:
        Actor.log.info('ATTEMPTING: LinkedIn slug search...')
        search_attempts.append('linkedin')
        
        results = await execute_search(page, search_query, 'linkedin', Actor.log)
        total_results_found += len(results)
        
        if results:
            linkedin_name = extract_name_from_linkedin_slug(linkedin_url)
            
            for result in results:
                score = calculate_name_only_score(result, linkedin_name)
                result['score'] = score
                result['name_match'] = linkedin_name
            
            MIN_SCORE_THRESHOLD = 70.0
            scored_results = [r for r in results if r.get('score', 0) >= MIN_SCORE_THRESHOLD]
            
            if scored_results:
                scored_results = apply_chicago_tiebreaker(scored_results)
                best_match = scored_results[0]
                final_search_type = 'linkedin'
                Actor.log.info(f'✅ LinkedIn match found: {best_match.get("name")} ({best_match.get("score")}%)')
    
    # Try Domain search
    if domain and not best_match:
        Actor.log.info('ATTEMPTING: Domain search...')
        search_attempts.append('domain')
        
        domain_query = domain.lower().replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        results = await execute_search(page, domain_query, 'domain', Actor.log)
        total_results_found += len(results)
        
        if results and search_name_cleaned:
            for result in results:
                score = calculate_name_only_score(result, search_name_cleaned)
                result['score'] = score
                result['name_match'] = search_name_cleaned
            
            MIN_SCORE_THRESHOLD = 70.0
            scored_results = [r for r in results if r.get('score', 0) >= MIN_SCORE_THRESHOLD]
            
            if scored_results:
                scored_results = apply_chicago_tiebreaker(scored_results)
                best_match = scored_results[0]
                final_search_type = 'domain'
                Actor.log.info(f'✅ Domain match found: {best_match.get("name")} ({best_match.get("score")}%)')
    
    # Try Name + Company search
    if search_name_cleaned and expected_company_cleaned and not best_match:
        Actor.log.info('ATTEMPTING: Name + Company search...')
        search_attempts.append('name')
        
        results = await execute_search(page, search_name_cleaned, 'name', Actor.log)
        total_results_found += len(results)
        
        if results:
            for result in results:
                score = calculate_match_score(result, search_name_cleaned, expected_company_cleaned)
                result['score'] = score
                result['name_match'] = search_name_cleaned
                result['company_match'] = expected_company_cleaned
            
            HIGH_CONFIDENCE_THRESHOLD = 70.0
            MANUAL_REVIEW_THRESHOLD = 50.0
            
            high_confidence_results = [r for r in results if r.get('score', 0) >= HIGH_CONFIDENCE_THRESHOLD]
            
            if high_confidence_results:
                high_confidence_results = apply_chicago_tiebreaker(high_confidence_results)
                best_match = high_confidence_results[0]
                final_search_type = 'name'
                Actor.log.info(f'✅ High confidence match: {best_match.get("name")} ({best_match.get("score")}%)')
            else:
                manual_review_results = [r for r in results if r.get('score', 0) >= MANUAL_REVIEW_THRESHOLD]
                
                if manual_review_results:
                    manual_review_results = sorted(manual_review_results, key=lambda x: x.get('score', 0), reverse=True)
                    best_match = manual_review_results[0]
                    final_search_type = 'name'
                    Actor.log.info(f'⚠️  Manual review match: {best_match.get("name")} ({best_match.get("score")}%)')
    
    # Build search metadata
    search_metadata = {
        'search_type': final_search_type,
        'search_attempts': search_attempts,
        'total_results_found': total_results_found
    }
    
    if best_match:
        if best_match.get('name_match'):
            search_metadata['name_searched'] = best_match.get('name_match')
        if best_match.get('company_match'):
            search_metadata['company_searched'] = best_match.get('company_match')
    
    return best_match, final_search_type, search_metadata


async def execute_scrape_phase(page, salesforce_url: str, logger) -> dict:
    """
    Execute CA Scrape V3 scraping logic.
    
    Returns:
        Dictionary with 18-field API output
    """
    # Detect record type
    if '/lead/' in salesforce_url.lower():
        record_type = 'Lead'
    elif '/contact/' in salesforce_url.lower():
        record_type = 'Contact'
    else:
        raise ValueError('URL must be a Lead or Contact URL')
    
    logger.info(f'Record Type: {record_type}')
    logger.info(f'URL: {salesforce_url}')
    
    # Scrape based on type
    opportunity_url = None
    
    if record_type == 'Lead':
        logger.info('Scraping Lead...')
        lead_or_contact_data = await scrape_lead_details(page, salesforce_url, logger)
        logger.info(f'Lead scrape complete: {lead_or_contact_data.get("basic_info", {}).get("name")}')
        
    elif record_type == 'Contact':
        logger.info('Scraping Contact...')
        lead_or_contact_data = await scrape_contact_details(page, salesforce_url, logger)
        logger.info(f'Contact scrape complete: {lead_or_contact_data.get("basic_info", {}).get("contact_full_name")}')
        
        # Extract opportunity URL
        selected_opp = lead_or_contact_data.get('selected_opportunity')
        if selected_opp:
            opportunity_url = selected_opp.get('opportunity_url')
            logger.info(f'Found Opportunity URL: {opportunity_url}')
    
    # Scrape opportunity if exists
    opportunity_data = None
    
    if opportunity_url:
        logger.info('Scraping Opportunity...')
        opportunity_data = await scrape_opportunity_details(page, opportunity_url, logger)
        logger.info(f'Opportunity scrape complete')
    
    # Format output
    api_output = format_final_output(lead_or_contact_data, opportunity_data, logger)
    
    return api_output
