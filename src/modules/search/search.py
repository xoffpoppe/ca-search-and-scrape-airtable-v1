"""Search execution module for Salesforce/Vistage.

Extracted from Actor 1 (ca-api-search) main.py search logic
"""
import urllib.parse
import re
from typing import List, Dict, Optional, Tuple
from ...utils.name_utils import clean_search_name, generate_name_variations
from ...utils.company_utils import clean_search_company



async def execute_search(
    page,
    search_query: str,
    search_type: str,
    logger
) -> List[Dict]:
    """
    Execute search on Vistage/Salesforce and extract results.
    
    Args:
        page: Playwright page object
        search_query: The search query string
        search_type: Type of search ('linkedin', 'domain', or 'name')
        logger: Actor logger
        
    Returns:
        List of search result dictionaries
    """
    # Navigate directly to search results using URL
    encoded_search = urllib.parse.quote(search_query)
    search_url = f'https://app.vistage.com/chairapp/s/search?searchTerm={encoded_search}'
    
    logger.info(f'Navigating to search URL: {search_url}')
    await page.goto(search_url, wait_until='domcontentloaded')
    await page.wait_for_timeout(5000)
    
    # Verify we're on the search page
    current_url_after_search = page.url
    logger.info(f'After navigation, current URL: {current_url_after_search}')
    
    if 'Login' in current_url_after_search:
        logger.error('Redirected back to login page - session issue!')
        await page.screenshot(path='session_failed.png')
        return []
    
    logger.info('Search results loaded')
    
    # Take a screenshot to see what we're working with
    await page.screenshot(path='search_results.png', full_page=True)
    logger.info('Screenshot saved as search_results.png')
    
    # Extract results
    results = await extract_search_results(page, logger)
    
    return results


async def extract_search_results(page, logger) -> List[Dict]:
    """
    Extract search results from the Salesforce Lightning page.
    
    Uses Lightning Web Component selectors to extract structured data.
    Falls back to text parsing if HTML extraction fails.
    
    Args:
        page: Playwright page object
        logger: Actor logger
        
    Returns:
        List of result dictionaries with keys: name, company, title, msa, section, salesforce_url
    """
    results = []
    
    # Try to extract results from HTML structure first using Lightning Web Component selectors
    try:
        logger.info('Extracting results using Lightning Web Component selectors...')
        
        # Define selectors for each record type
        # These selectors target the name link within each Lightning Web Component
        selectors = {
            'Leads': 'c-capp-global-search-results-lead .link',
            'Contacts': 'c-capp-global-search-results-contact .link',
            'Opportunities': 'c-capp-global-search-results-opportunity .link',
            'Accounts': 'c-capp-global-search-results-account .link'
        }
        
        for section, selector in selectors.items():
            section_links = await page.query_selector_all(selector)
            logger.info(f'Found {len(section_links)} {section} links')
            
            for link in section_links:
                # Get the href attribute EXACTLY as-is from Salesforce
                href = await link.get_attribute('href')
                
                if not href:
                    continue
                
                # If relative path, prepend domain
                if href.startswith('http'):
                    salesforce_url = href
                else:
                    salesforce_url = f'https://app.vistage.com{href}' if href.startswith('/') else f'https://app.vistage.com/{href}'
                
                # Get the name from the link text
                name = await link.inner_text()
                name = name.strip()
                
                if len(name) < 2:
                    continue
                
                # Get the parent component to extract other fields
                parent_component = await link.evaluate_handle('''el => {
                    let component = el.closest('c-capp-global-search-results-lead, c-capp-global-search-results-contact, c-capp-global-search-results-opportunity, c-capp-global-search-results-account');
                    return component;
                }''')
                
                result = {
                    'name': name,
                    'salesforce_url': salesforce_url,
                    'section': section
                }
                
                if parent_component:
                    parent_text = await parent_component.inner_text()
                    lines = [l.strip() for l in parent_text.split('\n') if l.strip()]
                    
                    logger.info(f'Processing result for: {name}')
                    
                    # Extract additional fields from parent text
                    # IMPORTANT: Only take the FIRST occurrence of each field to avoid contamination from other results
                    company_found = False
                    title_found = False
                    msa_found = False
                    record_type_found = False
                    
                    for line in lines:
                        if line.startswith('Title:') and not title_found:
                            result['title'] = line.replace('Title:', '').strip()
                            title_found = True
                        elif (line.startswith('Company:') or line.startswith('Account Name:')) and not company_found:
                            company_value = line.replace('Company:', '').replace('Account Name:', '').strip()
                            result['company'] = company_value
                            company_found = True
                            logger.info(f'EXTRACTED COMPANY for {name}: {company_value}')
                        elif line.startswith('MSA:') and not msa_found:
                            result['msa'] = line.replace('MSA:', '').strip()
                            msa_found = True
                        elif line.startswith('Record Type:') and not record_type_found:
                            result['record_type_raw'] = line.replace('Record Type:', '').strip()
                            record_type_found = True
                        
                        # Stop processing once we have all fields
                        if company_found and title_found and msa_found and record_type_found:
                            break
                
                results.append(result)
        
        logger.info(f'Extracted {len(results)} results from Lightning Web Components')
        
    except Exception as e:
        logger.warning(f'Error extracting from Lightning Web Components: {e}')
        logger.info('Falling back to text parsing...')
    
    # Fallback: If HTML extraction failed or got no results, use text parsing
    if len(results) == 0:
        results = await extract_results_text_fallback(page, logger)
    
    logger.info(f'Parsed {len(results)} total results')
    logger.info(f'Leads: {len([r for r in results if r.get("section") == "Leads"])}')
    logger.info(f'Contacts: {len([r for r in results if r.get("section") == "Contacts"])}')
    logger.info(f'Opportunities: {len([r for r in results if r.get("section") == "Opportunities"])}')
    logger.info(f'Accounts: {len([r for r in results if r.get("section") == "Accounts"])}')
    
    # Filter to only Leads and Contacts - we don't score Opportunities or Accounts
    # Opportunities will be scraped when we scrape their related Contact
    # Accounts are companies, not people, so we don't need them
    results_before_filter = len(results)
    results = [r for r in results if r.get('section') in ['Leads', 'Contacts']]
    
    if results_before_filter > len(results):
        logger.info(f'Filtered out {results_before_filter - len(results)} Opportunities/Accounts - only scoring Leads and Contacts')
    
    return results


async def extract_results_text_fallback(page, logger) -> List[Dict]:
    """
    Fallback text-based extraction when HTML selectors fail.
    
    Args:
        page: Playwright page object
        logger: Actor logger
        
    Returns:
        List of result dictionaries
    """
    results = []
    
    logger.info('Using text parsing fallback...')
    page_text = await page.inner_text('body')
    logger.info(f'Page contains {len(page_text)} characters of text')
    
    # Find where the results start
    if 'For content and community results' in page_text:
        all_results_text = page_text.split('For content and community results')[1]
    else:
        all_results_text = page_text
    
    lines = all_results_text.split('\n')
    
    current_result = {}
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        if line.startswith('Title:'):
            if current_result.get('name'):
                results.append(current_result.copy())
            
            name = ''
            j = i - 1
            while j >= 0:
                potential_name = lines[j].strip()
                if potential_name and not potential_name.startswith(('Title:', 'Company:', 'MSA:', 'Record Type:', 'Account Name:')):
                    name = potential_name
                    break
                j -= 1
            
            current_result = {'name': name}
            current_result['title'] = line.replace('Title:', '').strip()
        
        elif line.startswith('Company:'):
            current_result['company'] = line.replace('Company:', '').strip()
        elif line.startswith('Account Name:'):
            current_result['company'] = line.replace('Account Name:', '').strip()
        elif line.startswith('MSA:'):
            current_result['msa'] = line.replace('MSA:', '').strip()
        elif line.startswith('Record Type:'):
            record_type = line.replace('Record Type:', '').strip()
            current_result['record_type_raw'] = record_type
            if 'Lead' in record_type:
                current_result['section'] = 'Leads'
            elif 'Contact' in record_type:
                current_result['section'] = 'Contacts'
            elif 'Opportunity' in record_type:
                current_result['section'] = 'Opportunities'
            elif 'Account' in record_type:
                current_result['section'] = 'Accounts'
            else:
                current_result['section'] = 'Unknown'
        
        i += 1
    
    if current_result.get('name'):
        results.append(current_result)
    
    # Fix: Results without Record Type might be Contacts or Accounts
    for result in results:
        if not result.get('record_type_raw'):
            # Default to Contacts if no record type
            if not result.get('section'):
                result['section'] = 'Contacts'
            result['record_type_raw'] = f"{result.get('section', 'Contact')} (no record type field)"
        elif result.get('section') == 'Unknown':
            result['section'] = 'Contacts'
    
    # Filter out malformed results
    results = [r for r in results if r.get('name') and len(r.get('name', '')) > 2]
    
    return results


def extract_name_from_linkedin_slug(linkedin_url: str) -> str:
    """
    Extract person's name from LinkedIn slug.
    
    Examples:
        "https://www.linkedin.com/in/john-cossum-4a01027" → "John Cossum"
        "john-smith-12345" → "John Smith"
        "jane-doe" → "Jane Doe"
    
    Args:
        linkedin_url: Full LinkedIn URL or just the slug
        
    Returns:
        Extracted name with proper capitalization
    """
    # Extract slug from URL if needed
    if linkedin_url.startswith('http'):
        slug = linkedin_url.split('/in/')[-1].rstrip('/').split('?')[0]
    else:
        slug = linkedin_url.strip('/')
    
    # Split by hyphens
    parts = slug.split('-')
    
    # Remove numeric ID if present (last part that's all digits)
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    
    # Join and capitalize
    name = ' '.join(parts)
    name = name.title()
    
    return name


def prepare_search_query(
    linkedin_slug: str = '',
    domain: str = '',
    search_name: str = '',
    expected_company: str = '',
    logger = None
) -> Tuple[str, str, Optional[str], Optional[str], Optional[str]]:
    """
    Prepare search query based on available inputs.
    
    Determines search method and prepares query string.
    
    Args:
        linkedin_slug: LinkedIn profile slug or URL
        domain: Company domain
        search_name: Person's name
        expected_company: Company name
        logger: Actor logger
        
    Returns:
        Tuple of (search_query, search_type, search_name_cleaned, expected_company_cleaned, linkedin_url)
    """
    search_name_cleaned = None
    expected_company_cleaned = None
    linkedin_url = None
    
    # Determine search method and prepare query
    if linkedin_slug:
        # LinkedIn slug search (highest priority)
        if logger:
            logger.info(f'Using LinkedIn search with: {linkedin_slug}')
        
        # Extract slug from URL or use slug directly
        if linkedin_slug.startswith('http'):
            # Extract slug from full URL
            linkedin_url = linkedin_slug
            # Extract everything after '/in/' and clean it
            slug_clean = linkedin_url.split('/in/')[-1].rstrip('/').split('?')[0]
        else:
            # Already a slug, just clean it
            slug_clean = linkedin_slug.lstrip('/').split('?')[0]
            linkedin_url = f'https://www.linkedin.com/in/{slug_clean}'
        
        if logger:
            logger.info(f'LinkedIn URL: {linkedin_url}')
            logger.info(f'LinkedIn slug for search: {slug_clean}')
        
        # Search with just the slug (not the full URL)
        search_query = slug_clean
        search_type = 'linkedin'
        
        # Also clean the provided search_name if available (for scoring fallback)
        if search_name:
            search_name_cleaned = clean_search_name(search_name)
        if expected_company:
            expected_company_cleaned = clean_search_company(expected_company)
        
    elif domain:
        # Domain search (second priority)
        if logger:
            logger.info(f'Using domain search with: {domain}')
        
        # Clean the domain - remove protocol, www, paths, query params
        domain_clean = domain.lower()
        domain_clean = re.sub(r'^https?://', '', domain_clean)
        domain_clean = re.sub(r'^www\.', '', domain_clean)
        domain_clean = domain_clean.split('/')[0].split('?')[0].split('#')[0]
        
        if logger:
            logger.info(f'Cleaned domain: {domain_clean}')
        search_query = domain_clean
        search_type = 'domain'
        
        # Also clean name and company for potential fallback scoring
        if search_name:
            search_name_cleaned = clean_search_name(search_name)
        if expected_company:
            expected_company_cleaned = clean_search_company(expected_company)
        
    else:
        # Name-based search (fallback)
        if logger:
            logger.info(f'Original name search input: {search_name}')
            logger.info(f'Original company input: {expected_company}')
        
        # Clean the name and company for searching
        search_name_cleaned = clean_search_name(search_name)
        expected_company_cleaned = clean_search_company(expected_company)
        
        if logger:
            logger.info(f'Cleaned name for search: {search_name_cleaned}')
            logger.info(f'Cleaned company for search: {expected_company_cleaned}')
        
        # Generate name variations for multi-word names
        name_variations = generate_name_variations(search_name_cleaned)
        if logger:
            logger.info(f'Name variations to try: {name_variations}')
        
        # Combine name and company in search query for better Salesforce results
        search_query = f"{name_variations[0]} {expected_company_cleaned}"
        if logger:
            logger.info(f'Combined search query: {search_query}')
        search_type = 'name'
    
    return (search_query, search_type, search_name_cleaned, expected_company_cleaned, linkedin_url)

# commenting for github connect