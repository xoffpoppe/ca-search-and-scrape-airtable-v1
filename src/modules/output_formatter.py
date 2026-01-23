"""Output Formatter - Converts scraped data to final API format"""
from .rules_engine import evaluate_rules

def format_final_output(lead_or_contact_data: dict, opportunity_data: dict = None, logger=None) -> dict:
    """
    Format scraped data using EXACT field mappings from Actor 2's formatter.
    """
    
    record_type = lead_or_contact_data.get('record_type', 'Unknown')
    basic_info = lead_or_contact_data.get('basic_info', {})
    profile = lead_or_contact_data.get('profile', {})
    
    # Initialize output
    if record_type == 'Contact':
        output = {
            'ca name': basic_info.get('contact_full_name'),
            'ca company': profile.get('company_name'),
            'ca phone': basic_info.get('work_phone'),
            'ca mobile': basic_info.get('mobile_phone'),
            'ca email': basic_info.get('email'),
            'ca url': lead_or_contact_data.get('record_url'),
            'lead source': profile.get('lead_source'),
            'ca role': basic_info.get('title'),
            'ca vistage role': profile.get('vistage_role'),
            'ca contact status': profile.get('contact_status'),
            'opt in': profile.get('opt_in_consent'),
            'ca details': f"msa: {profile.get('msa', 'null')}\nsection: Contacts\nrecord_type: Contact",
        }
    else:  # Lead
        output = {
            'ca name': basic_info.get('name'),
            'ca company': basic_info.get('company'),
            'ca phone': None,
            'ca mobile': None,
            'ca email': profile.get('email'),
            'ca url': lead_or_contact_data.get('record_url'),
            'lead source': profile.get('lead_source'),
            'ca role': profile.get('role'),
            'ca contact status': basic_info.get('lead_status'),
            'opt in': profile.get('opt_in_consent'),
            'available': basic_info.get('available_candidate'),
            'ca availability': lead_or_contact_data.get('ca_availability'),
            'ca details': f"msa: {profile.get('msa', 'null')}\nsection: Leads\nrecord_type: Lead",
        }
        output['ca stage'] = None
        output['opportunity close date'] = None
        output['days untouched'] = None
        output['chair rep'] = None
        output['reason'] = None
    
    # If we have opportunity data (for Contacts), merge it
    if opportunity_data and record_type == 'Contact':
        output['available'] = opportunity_data.get('available')
        output['ca availability'] = opportunity_data.get('ca_availability')
        output['ca stage'] = opportunity_data.get('stage')
        output['opportunity close date'] = opportunity_data.get('close_date')
        output['days untouched'] = opportunity_data.get('days_untouched')
        output['chair rep'] = opportunity_data.get('chair_rep')
        
        # Reason from candidate_funnel
        candidate_funnel = opportunity_data.get('candidate_funnel', {})
        output['reason'] = candidate_funnel.get('reason_for_joining')
    
    # If Contact but no opportunity
    if record_type == 'Contact' and not opportunity_data:
        output['available'] = None
        output['ca availability'] = None
        output['ca stage'] = None
        output['opportunity close date'] = None
        output['days untouched'] = None
        output['chair rep'] = None
        output['reason'] = None
    
    # NEW: Evaluate rules to determine proposed_ca_status
    output['proposed ca status'] = evaluate_rules(output, logger)
    
    return output