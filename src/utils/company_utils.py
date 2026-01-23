"""Company name cleaning utilities.

Extracted from Actor 1 (ca-api-search) main.py lines 68-107
"""
import re


def clean_search_company(company: str) -> str:
    """
    Clean a company name for search by removing corporate suffixes and common words.
    
    Examples:
        "Acme Corporation, Inc." → "Acme"
        "Widget LLC" → "Widget"
        "ARBON STEEL AND SERVICE COMPANY, INC." → "ARBON STEEL"
    """
    if not company:
        return company
    
    # Remove everything after comma first
    company = company.split(',')[0].strip()
    
    # Remove corporate suffixes and common phrases (case insensitive)
    # Order matters - remove longer phrases first
    suffixes = [
        r'\s+and\s+Service\s+Company\b',  # "and Service Company"
        r'\s+&\s+Service\s+Company\b',    # "& Service Company"
        r'\s+Service\s+Company\b',         # "Service Company"
        r'\s+and\s+Company\b',             # "and Company"
        r'\s+&\s+Company\b',               # "& Company"
        r'\b(Inc\.?|Incorporated)\b',
        r'\b(LLC|L\.L\.C\.)\b',
        r'\b(Corp\.?|Corporation)\b',
        r'\b(Ltd\.?|Limited)\b',
        r'\b(Co\.?|Company)\b',
        r'\b(LP|L\.P\.)\b',
        r'\b(LLP|L\.L\.P\.)\b',
        r'\b(PLC|P\.L\.C\.)\b',
        r'\b(N\.A\.)\b',  # National Association
        r'\s+and\s+Trust\b',  # "and Trust"
        r'\s+&\s+Trust\b',    # "& Trust"
    ]
    
    for suffix in suffixes:
        company = re.sub(suffix, '', company, flags=re.IGNORECASE)
    
    return company.strip()