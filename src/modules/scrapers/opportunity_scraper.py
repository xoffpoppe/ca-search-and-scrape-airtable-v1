"""Opportunity Scraper - Production version with confirmed selectors"""
from typing import Optional
from datetime import datetime, timezone
from .availability_tester import test_availability

async def scrape_opportunity_details(page, opportunity_url: str, logger) -> dict:
    """Scrape Opportunity details using confirmed span.test-id__field-label selectors."""
    
    # Record start time
    start_time = datetime.now(timezone.utc)
    start_timestamp = start_time.isoformat()
    
    logger.info(f'Scraping Opportunity from: {opportunity_url}')
    logger.info(f'Opportunity scrape started at: {start_timestamp}')
    
    await page.goto(opportunity_url, wait_until='domcontentloaded', timeout=60000)
    await page.wait_for_timeout(5000)
    
    opportunity_data = {
        'record_type': 'Opportunity',
        'record_url': opportunity_url,
        'stage': None,
        'close_date': None,
        'available': None,
        'days_untouched': None,
        'reason_category': None,
        'reason_code': None,
        'reason_detail': None,
        'chair_rep': None,
        'candidate_funnel': {},
        'timing': {
            'start_timestamp': start_timestamp
        }
    }
    
    async def get_field_value(field_label: str) -> Optional[str]:
        """Extract field value by finding the label span."""
        try:
            # Find the specific label
            label_element = await page.locator(f'span.test-id__field-label:has-text("{field_label}")').first.element_handle()
            
            if not label_element:
                return None
            
            # Get the parent form element
            parent = await label_element.query_selector('xpath=ancestor::div[contains(@class, "slds-form-element")]')
            
            if not parent:
                logger.warning(f'No parent found for {field_label}')
                return None
            
            # Find the value within the parent
            value_element = await parent.query_selector('lightning-formatted-text, lightning-formatted-url, lightning-formatted-date-time, .slds-form-element__static')
            
            if value_element:
                value_text = await value_element.inner_text()
                return value_text.strip() if value_text else None
            
            logger.warning(f'No value element found for {field_label}')
            return None
            
        except Exception as e:
            logger.warning(f'Error extracting {field_label}: {str(e)}')
            return None
    
    # Extract fields
    logger.info('Extracting Opportunity fields...')
    
    opportunity_data['available'] = await get_field_value('Available Candidate')
    logger.info(f'Available Candidate extracted: {opportunity_data["available"]}')
    
    opportunity_data['close_date'] = await get_field_value('Close Date')
    logger.info(f'Close Date extracted: {opportunity_data["close_date"]}')
    
    opportunity_data['days_untouched'] = await get_field_value('Opportunity Days Untouched')
    logger.info(f'Days Untouched extracted: {opportunity_data["days_untouched"]}')
    
    opportunity_data['reason_category'] = await get_field_value('Reason Category')
    logger.info(f'Reason Category extracted: {opportunity_data["reason_category"]}')
    
    opportunity_data['reason_code'] = await get_field_value('Reason Code')
    logger.info(f'Reason Code extracted: {opportunity_data["reason_code"]}')
    
    opportunity_data['reason_detail'] = await get_field_value('Reason Code Detail')
    logger.info(f'Reason Detail extracted: {opportunity_data["reason_detail"]}')
    
    opportunity_data['chair_rep'] = await get_field_value('Chair - Rep')
    logger.info(f'Chair - Rep extracted: {opportunity_data["chair_rep"]}')
    
    # Format reason
    if opportunity_data['reason_category'] or opportunity_data['reason_code'] or opportunity_data['reason_detail']:
        parts = [
            opportunity_data['reason_category'] or '',
            opportunity_data['reason_code'] or '',
            opportunity_data['reason_detail'] or ''
        ]
        opportunity_data['candidate_funnel']['reason_for_joining'] = ' - '.join(filter(None, parts))
    
    # Extract Stage
    try:
        stage_element = await page.locator('span:has-text("Stage:")').first.inner_text(timeout=3000)
        if stage_element:
            stage_text = stage_element.replace('Stage:', '').strip()
            opportunity_data['stage'] = stage_text
            logger.info(f'Stage extracted: {stage_text}')
    except:
        logger.warning('Could not extract Stage field')
    
    # Opt In Consent
    opt_in = await get_field_value('Opt In Consent')
    if opt_in:
        logger.info(f'Opt In Consent extracted: {opt_in}')
    
    # Test availability - always test regardless of Available Candidate field value
    logger.info('Testing availability...')
    available_value = opportunity_data['available']
    if available_value:
        ca_availability = await test_availability(page, available_value, logger)
        opportunity_data['ca_availability'] = ca_availability
        logger.info(f'Availability test complete: {ca_availability}')
    else:
        logger.warning('No Available Candidate value found, skipping availability test')
        opportunity_data['ca_availability'] = 'Unknown'
    
    # Record end time
    end_time = datetime.now(timezone.utc)
    end_timestamp = end_time.isoformat()
    duration_seconds = (end_time - start_time).total_seconds()
    
    opportunity_data['timing']['end_timestamp'] = end_timestamp
    opportunity_data['timing']['duration_seconds'] = duration_seconds
    
    logger.info('Opportunity extraction complete')
    logger.info(f'Final - Available: {opportunity_data["available"]}')
    logger.info(f'Final - Stage: {opportunity_data["stage"]}')
    logger.info(f'Final - Close Date: {opportunity_data["close_date"]}')
    logger.info(f'Final - Days Untouched: {opportunity_data["days_untouched"]}')
    logger.info(f'Final - Reason: {opportunity_data.get("candidate_funnel", {}).get("reason_for_joining")}')
    logger.info(f'Opportunity scrape duration: {duration_seconds:.2f} seconds')
    
    return opportunity_data