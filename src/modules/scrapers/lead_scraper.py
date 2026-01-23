"""Lead Scraper Module"""
from typing import Optional
from .availability_tester import test_availability

async def scrape_lead_details(page, lead_url: str, logger) -> dict:
    """Scrape detailed information from a Lead record."""
    logger.info(f'Scraping Lead details from: {lead_url}')
    
    await page.goto(lead_url, wait_until='domcontentloaded')
    await page.wait_for_timeout(5000)
    
    lead_data = {
        'record_type': 'Lead',
        'record_url': lead_url,
        'basic_info': {},
        'profile': {},
        'address': {},
        'system_info': {},
        'ca_availability': None
    }
    
    try:
        async def get_field_value(field_label: str) -> Optional[str]:
            """Extract field value by finding the label span."""
            try:
                # Find all label spans
                label_spans = await page.query_selector_all('span.test-id__field-label')
                
                for label_span in label_spans:
                    label_text = await label_span.inner_text()
                    if field_label in label_text:
                        # Found the label! Now get the parent form element
                        form_element = await label_span.evaluate_handle('el => el.closest(".slds-form-element")')
                        
                        # Look for the value in various formatted elements
                        value_element = await form_element.query_selector(
                            'lightning-formatted-text, lightning-formatted-name, lightning-formatted-email, '
                            'lightning-formatted-url, lightning-formatted-phone, records-formula-output'
                        )
                        
                        if value_element:
                            value = await value_element.inner_text()
                            return value.strip() if value else None
                
                return None
            except Exception as e:
                logger.warning(f'Error extracting "{field_label}": {e}')
                return None
        
        logger.info('Extracting all fields...')
        
        # Basic Info
        lead_data['basic_info']['name'] = await get_field_value('Name')
        lead_data['basic_info']['title'] = await get_field_value('Title')
        lead_data['basic_info']['company'] = await get_field_value('Company')
        lead_data['basic_info']['available_candidate'] = await get_field_value('Available Candidate')
        lead_data['basic_info']['product_interest'] = await get_field_value('Product Interest')
        lead_data['basic_info']['lead_status'] = await get_field_value('Lead Status')
        lead_data['basic_info']['website'] = await get_field_value('Website')
        lead_data['basic_info']['linkedin'] = await get_field_value('LinkedIn')
        
        # Profile
        lead_data['profile']['role'] = await get_field_value('Role in the Organization')
        lead_data['profile']['opt_in_consent'] = await get_field_value('Opt In Consent')
        lead_data['profile']['industry'] = await get_field_value('Industry')
        lead_data['profile']['email'] = await get_field_value('Email')
        lead_data['profile']['industry_detail'] = await get_field_value('Industry Detail')
        lead_data['profile']['annual_revenue'] = await get_field_value('Annual Revenue')
        lead_data['profile']['type_of_org'] = await get_field_value('Type of Org')
        lead_data['profile']['number_of_employees'] = await get_field_value('Number of Employees')
        lead_data['profile']['business_description'] = await get_field_value('Business Description')
        lead_data['profile']['city'] = await get_field_value('City')
        lead_data['profile']['lead_record_type'] = await get_field_value('Lead Record Type')
        
        # Address
        lead_data['address']['full_address'] = await get_field_value('Address')
        
        # System Info
        lead_data['system_info']['data_last_checked'] = await get_field_value('Data Last Checked')
        lead_data['system_info']['data_match_type'] = await get_field_value('Data Match Type')
        lead_data['system_info']['created_by'] = await get_field_value('Created By')
        lead_data['system_info']['last_modified_by'] = await get_field_value('Last Modified By')
        
        logger.info('Lead extraction complete!')
        
        # NOW test availability (after all fields are scraped)
        available_value = lead_data['basic_info'].get('available_candidate')
        if available_value:
            logger.info('Testing availability...')
            try:
                ca_availability = await test_availability(page, available_value, logger)
                lead_data['ca_availability'] = ca_availability
                logger.info(f'Availability test complete: {ca_availability}')
            except Exception as e:
                logger.error(f'Error during availability test: {e}')
                lead_data['ca_availability'] = 'Unknown'
        else:
            logger.warning('No Available Candidate value found, skipping availability test')
            lead_data['ca_availability'] = 'Unknown'
        
        return lead_data
        
    except Exception as e:
        logger.error(f'Error scraping Lead: {e}')
        lead_data['error'] = str(e)
        return lead_data