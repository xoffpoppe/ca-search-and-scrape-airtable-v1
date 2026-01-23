"""Contact Scraper Module - Scrapes contact and extracts opportunity URL (does not scrape opportunity)"""
from typing import Optional
from datetime import datetime

async def scrape_contact_details(page, contact_url: str, logger) -> dict:
    """Scrape detailed information from a Contact record."""
    logger.info(f'Scraping Contact details from: {contact_url}')
    
    await page.goto(contact_url, wait_until='domcontentloaded')
    await page.wait_for_timeout(5000)
    
    contact_data = {
        'record_type': 'Contact',
        'record_url': contact_url,
        'basic_info': {},
        'profile': {},
        'address': {},
        'system_info': {},
        'opportunities': [],
        'selected_opportunity': None
    }
    
    try:
        async def get_field_value(field_label: str) -> Optional[str]:
            try:
                label_spans = await page.query_selector_all('span.test-id__field-label')
                for label_span in label_spans:
                    label_text = await label_span.inner_text()
                    if field_label in label_text:
                        form_element = await label_span.evaluate_handle('el => el.closest(".slds-form-element")')
                        value_element = await form_element.query_selector(
                            'lightning-formatted-text, lightning-formatted-name, lightning-formatted-email, '
                            'lightning-formatted-url, lightning-formatted-phone, records-formula-output, '
                            'lightning-formatted-rich-text'
                        )
                        if value_element:
                            value = await value_element.inner_text()
                            return value.strip() if value else None
                return None
            except Exception as e:
                logger.warning(f'Error extracting "{field_label}": {e}')
                return None
        
        logger.info('Extracting Contact fields...')
        
        # Basic Contact Info
        contact_data['basic_info']['contact_full_name'] = await get_field_value('Contact Full Name')
        contact_data['basic_info']['work_phone'] = await get_field_value('Work Phone')
        contact_data['basic_info']['mobile_phone'] = await get_field_value('Mobile Phone')
        contact_data['basic_info']['email'] = await get_field_value('Email')
        contact_data['basic_info']['title'] = await get_field_value('Title')
        contact_data['basic_info']['alternate_email'] = await get_field_value('Alternate Email')
        contact_data['basic_info']['company_relationship'] = await get_field_value('Company Relationship')
        contact_data['basic_info']['website'] = await get_field_value('Website')
        contact_data['basic_info']['linkedin'] = await get_field_value('LinkedIn')
        
        # Profile
        contact_data['profile']['name'] = await get_field_value('Name')
        contact_data['profile']['company_name'] = await get_field_value('Company Name')
        contact_data['profile']['role'] = await get_field_value('Role in the Organization')
        contact_data['profile']['opt_in_consent'] = await get_field_value('Opt In Consent')
        contact_data['profile']['annual_revenue'] = await get_field_value('Annual Revenue')
        contact_data['profile']['industry'] = await get_field_value('Industry')
        contact_data['profile']['number_of_employees'] = await get_field_value('Number of Employees')
        contact_data['profile']['msa'] = await get_field_value('MSA')
        contact_data['profile']['business_description'] = await get_field_value('Business Description')
        contact_data['profile']['vistage_role'] = await get_field_value('Vistage Role Summary')
        
        # System Info
        contact_data['system_info']['created_by'] = await get_field_value('Created By')
        contact_data['system_info']['last_modified_by'] = await get_field_value('Last Modified By')
        contact_data['system_info']['data_match_type'] = await get_field_value('Data Match Type')
        
        logger.info('Extracting opportunities...')
        
        # Navigate to View All
        contact_id = contact_url.split('/contact/')[-1].split('/')[0]
        opportunities_url = f'https://app.vistage.com/chairapp/s/contact/related/{contact_id}/Opportunities1__r'
        
        logger.info(f'Navigating to: {opportunities_url}')
        await page.goto(opportunities_url, wait_until='domcontentloaded')
        await page.wait_for_timeout(3000)
        
        # Scrape opportunities - Opportunity is in <th>, other fields in <td>
        try:
            rows = await page.query_selector_all('tbody tr')
            logger.info(f'Found {len(rows)} opportunity rows')
            
            for row in rows:
                try:
                    # Get the TH element (Opportunity Name)
                    th_element = await row.query_selector('th')
                    opp_link = None
                    opp_name = None
                    opp_url = None
                    
                    if th_element:
                        opp_link = await th_element.query_selector('a[href*="/opportunity/"]')
                        if opp_link:
                            opp_name = await opp_link.inner_text()
                            opp_url = await opp_link.get_attribute('href')
                    
                    # Get TD elements (Account, Stage, Close Date, etc.)
                    tds = await row.query_selector_all('td')
                    
                    # Based on the HTML: td[1] = Account, td[2] = Stage, td[3] = Close Date
                    account_name = await tds[1].inner_text() if len(tds) > 1 else None
                    stage = await tds[2].inner_text() if len(tds) > 2 else None
                    close_date_text = await tds[3].inner_text() if len(tds) > 3 else None
                    
                    opportunity = {
                        'opportunity_name': opp_name.strip() if opp_name else None,
                        'opportunity_url': f'https://app.vistage.com{opp_url}' if opp_url and opp_url.startswith('/') else opp_url,
                        'account_name': account_name.strip() if account_name else None,
                        'stage': stage.strip() if stage else None,
                        'close_date': close_date_text.strip() if close_date_text else None
                    }
                    
                    contact_data['opportunities'].append(opportunity)
                    logger.info(f"  {opp_name} - {stage} - {close_date_text}")
                    
                except Exception as e:
                    logger.warning(f'Error extracting row: {e}')
                    continue
            
            # Select opportunity with latest close date
            if contact_data['opportunities']:
                latest_opp = None
                latest_date = None
                
                for opp in contact_data['opportunities']:
                    try:
                        if opp['close_date']:
                            date_obj = datetime.strptime(opp['close_date'], '%m/%d/%Y')
                            if latest_date is None or date_obj > latest_date:
                                latest_date = date_obj
                                latest_opp = opp
                    except:
                        continue
                
                if latest_opp:
                    contact_data['selected_opportunity'] = latest_opp
                    logger.info(f"Selected: {latest_opp['opportunity_name']} ({latest_opp['close_date']})")
                    logger.info(f"Opportunity URL extracted: {latest_opp['opportunity_url']}")
                    # NOTE: NOT scraping opportunity - Actor 3 will do this
            else:
                logger.info('No opportunities found')
                    
        except Exception as e:
            logger.warning(f'Error extracting opportunities: {e}')
        
        logger.info('Contact extraction complete!')
        return contact_data
        
    except Exception as e:
        logger.error(f'Error: {e}')
        contact_data['error'] = str(e)
        return contact_data