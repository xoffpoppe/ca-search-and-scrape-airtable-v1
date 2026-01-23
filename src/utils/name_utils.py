"""Name cleaning, variations, and nickname handling utilities.

Extracted from Actor 1 (ca-api-search) main.py lines 20-352
"""
import re
from typing import List
from unidecode import unidecode


def clean_search_name(name: str) -> str:
    """
    Clean a name for search by removing titles, suffixes, and degrees.
    
    Examples:
        "Dr. John Smith" → "John Smith"
        "Jane Doe, Esq." → "Jane Doe"
        "Bob Johnson, PhD" → "Bob Johnson"
        "Cheryl Rucker-Whitaker MD, MPH" → "Cheryl Rucker-Whitaker"
    """
    if not name:
        return name
    
    # Remove everything after comma (degrees, credentials)
    name = name.split(',')[0].strip()
    
    # Remove common titles at the beginning
    titles = ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Miss', 'Rev.', 'Prof.', 'Esq.']
    for title in titles:
        # Case insensitive removal at the beginning
        if name.lower().startswith(title.lower()):
            name = name[len(title):].strip()
    
    # Remove credentials/degrees at the end (case insensitive)
    credentials = [
        r'\s+M\.?D\.?$',  # MD, M.D.
        r'\s+Ph\.?D\.?$',  # PhD, Ph.D.
        r'\s+MBA$',
        r'\s+J\.?D\.?$',  # JD, J.D.
        r'\s+CPA$',
        r'\s+DDS$',
        r'\s+Esq\.?$',
        r'\s+RN$',
        r'\s+M\.?S\.?$',  # MS, M.S.
        r'\s+M\.?A\.?$',  # MA, M.A.
        r'\s+MPH$',
        r'\s+FACHE$',
        r'\s+PE$',
        r'\s+CFA$',
        r'\s+CFP$',
    ]
    
    for credential in credentials:
        name = re.sub(credential, '', name, flags=re.IGNORECASE)
    
    return name.strip()


def generate_name_variations(name: str) -> List[str]:
    """
    Generate search variations for multi-word names, hyphenated names, and names with particles.
    
    Handles:
    - Hyphenated names: "Cheryl Rucker-Whitaker" → ["Cheryl Rucker-Whitaker", "Cheryl Rucker", "Cheryl Whitaker", "Rucker Whitaker"]
    - Multi-word names: "Jane Martin Dutchman" → ["Jane Martin Dutchman", "Jane Dutchman", "Jane Martin", "Martin Dutchman"]
    - French particles: "Jennifer des Groseilliers" → ["Jennifer des Groseilliers", "Jennifer Groseilliers", "des Groseilliers"]
    - Special characters: Uses unidecode to create normalized versions
    
    Args:
        name: Full name string
        
    Returns:
        List of name variations to try, in priority order
    """
    name = name.strip()
    variations = []
    
    # Always include the original name first
    variations.append(name)
    
    # Also include normalized version (without special characters)
    normalized = unidecode(name)
    if normalized != name:
        variations.append(normalized)
    
    # Check for hyphenated last name (e.g., "Cheryl Rucker-Whitaker")
    if '-' in name:
        words = name.split()
        if len(words) >= 2 and '-' in words[-1]:
            # Split the hyphenated last name
            first_names = words[:-1]
            last_name_parts = words[-1].split('-')
            
            # "Cheryl Rucker-Whitaker" → "Cheryl Rucker"
            variations.append(f"{' '.join(first_names)} {last_name_parts[0]}")
            
            # "Cheryl Rucker-Whitaker" → "Cheryl Whitaker"
            variations.append(f"{' '.join(first_names)} {last_name_parts[1]}")
            
            # "Cheryl Rucker-Whitaker" → "Rucker Whitaker"
            variations.append(f"{last_name_parts[0]} {last_name_parts[1]}")
    
    # Handle regular multi-word names (3+ words without hyphens)
    words = name.split()
    if len(words) >= 3 and '-' not in name:
        # Check if name contains French/Dutch particles (de, des, van, von, etc.)
        particles = ['de', 'des', 'van', 'von', 'du', 'da', 'della', 'del', 'le', 'la']
        has_particle = any(word.lower() in particles for word in words[1:])
        
        if has_particle:
            # Handle names with particles like "Jennifer des Groseilliers"
            # Try without the particle: "Jennifer Groseilliers"
            filtered_words = [w for w in words if w.lower() not in particles]
            if len(filtered_words) >= 2:
                variations.append(' '.join(filtered_words))
            
            # Try just the last part with particle: "des Groseilliers"
            if len(words) >= 2:
                variations.append(' '.join(words[-2:]))
        else:
            # Regular 3+ word name like "Jane Martin Dutchman"
            # First + Last (skip middle)
            variations.append(f"{words[0]} {words[-1]}")
            
            # First + Middle (in case last is wrong)
            variations.append(f"{words[0]} {words[1]}")
            
            # Middle + Last (in case first is wrong)
            variations.append(f"{words[1]} {words[-1]}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        v_lower = v.lower()
        if v_lower not in seen:
            seen.add(v_lower)
            unique_variations.append(v)
    
    return unique_variations


# Comprehensive nickname to formal name mapping
NICKNAME_MAP = {
    # Common male nicknames
    'alex': 'alexander',
    'andy': 'andrew',
    'art': 'arthur',
    'ben': 'benjamin',
    'bill': 'william',
    'billy': 'william',
    'bob': 'robert',
    'bobby': 'robert',
    'brad': 'bradley',
    'charlie': 'charles',
    'chris': 'christopher',
    'chuck': 'charles',
    'dan': 'daniel',
    'danny': 'daniel',
    'dave': 'david',
    'dick': 'richard',
    'don': 'donald',
    'doug': 'douglas',
    'ed': 'edward',
    'eddie': 'edward',
    'fred': 'frederick',
    'gene': 'eugene',
    'greg': 'gregory',
    'hank': 'henry',
    'jack': 'john',
    'jake': 'jacob',
    'jim': 'james',
    'jimmy': 'james',
    'joe': 'joseph',
    'joey': 'joseph',
    'jon': 'jonathan',
    'josh': 'joshua',
    'ken': 'kenneth',
    'larry': 'lawrence',
    'len': 'leonard',
    'leo': 'leonard',
    'matt': 'matthew',
    'max': 'maxwell',
    'mike': 'michael',
    'mick': 'michael',
    'nat': 'nathan',
    'nate': 'nathan',
    'ned': 'edward',
    'nick': 'nicholas',
    'pat': 'patrick',
    'pete': 'peter',
    'phil': 'philip',
    'randy': 'randall',
    'ray': 'raymond',
    'rich': 'richard',
    'rick': 'richard',
    'rob': 'robert',
    'rod': 'rodney',
    'ron': 'ronald',
    'sam': 'samuel',
    'steve': 'steven',
    'ted': 'theodore',
    'tim': 'timothy',
    'tom': 'thomas',
    'tommy': 'thomas',
    'tony': 'anthony',
    'vic': 'victor',
    'will': 'william',
    'zach': 'zachary',
    
    # Common female nicknames
    'abby': 'abigail',
    'alex': 'alexandra',
    'allie': 'allison',
    'amanda': 'amanda',
    'amy': 'amelia',
    'annie': 'ann',
    'barb': 'barbara',
    'becky': 'rebecca',
    'beth': 'elizabeth',
    'betsy': 'elizabeth',
    'betty': 'elizabeth',
    'cathy': 'catherine',
    'chris': 'christine',
    'cindy': 'cynthia',
    'deb': 'deborah',
    'debbie': 'deborah',
    'diana': 'diane',
    'dotty': 'dorothy',
    'liz': 'elizabeth',
    'lizzy': 'elizabeth',
    'maggie': 'margaret',
    'mandy': 'amanda',
    'meg': 'margaret',
    'missy': 'melissa',
    'molly': 'mary',
    'nancy': 'ann',
    'pat': 'patricia',
    'patty': 'patricia',
    'peg': 'margaret',
    'penny': 'penelope',
    'sally': 'sarah',
    'sam': 'samantha',
    'sandy': 'sandra',
    'sue': 'susan',
    'susie': 'susan',
    'tina': 'christina',
    'trish': 'patricia',
    'vicky': 'victoria',
    'wendy': 'gwendolyn',
}


def normalize_name_with_nicknames(name: str) -> List[str]:
    """
    Normalize a name by expanding nicknames to formal names.
    Returns a list of possible name variations.
    
    Args:
        name: Name string (e.g., "Bob Smith")
        
    Returns:
        List of name variations including nickname and formal versions
        Example: "Bob Smith" → ["Bob Smith", "Robert Smith"]
    """
    if not name:
        return [name]
    
    variations = [name]  # Always include original
    
    # Split name into parts
    parts = name.lower().split()
    
    if not parts:
        return variations
    
    # Check if first name is a nickname
    first_name = parts[0]
    if first_name in NICKNAME_MAP:
        formal_name = NICKNAME_MAP[first_name]
        # Create variation with formal first name
        formal_parts = [formal_name] + parts[1:]
        formal_full_name = ' '.join(formal_parts)
        variations.append(formal_full_name.title())
    
    # Also create reverse mapping - check if it's a formal name with known nicknames
    reverse_nicknames = {}
    for nick, formal in NICKNAME_MAP.items():
        if formal not in reverse_nicknames:
            reverse_nicknames[formal] = []
        reverse_nicknames[formal].append(nick)
    
    if first_name in reverse_nicknames:
        for nickname in reverse_nicknames[first_name]:
            nickname_parts = [nickname] + parts[1:]
            nickname_full_name = ' '.join(nickname_parts)
            variations.append(nickname_full_name.title())
    
    return variations