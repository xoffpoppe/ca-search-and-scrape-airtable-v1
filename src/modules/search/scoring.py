"""Scoring and selection logic for search results.

Extracted from Actor 1 (ca-api-search) main.py lines 355-432
"""
import re
from typing import List, Dict
from rapidfuzz import fuzz
from ...utils.name_utils import normalize_name_with_nicknames



def calculate_match_score(result: dict, search_name: str = '', expected_company: str = '') -> float:
    """
    Calculate match score for a search result.
    
    Scoring formula:
    - Base Score: (Name Match × 50%) + (Company Match × 50%)
    - Bonus: +5 points for Contact record type
    - CRITICAL: If company match < 70%, overall score is capped at 69% (forces manual review)
    
    Uses nickname normalization to handle variations like:
    - "Bob" vs "Robert"
    - "Dick" vs "Richard"
    - "Jon" vs "Jonathan"
    
    Args:
        result: Dictionary containing name, company, and other fields
        search_name: The name being searched for
        expected_company: The expected company name
        
    Returns:
        Float score between 0-100 (105 max with bonus, but capped at 69 if company match is weak)
    """
    score = 0.0
    company_score = 0.0
    
    # Name matching (50% weight) with nickname awareness
    if search_name and result.get('name'):
        result_name = result['name']
        # Clean up the name (remove suffixes like "- CE Candidate")
        result_name_clean = re.sub(r'\s*-\s*CE Candidate.*$', '', result_name).strip()
        
        # Generate nickname variations for both search and result names
        search_variations = normalize_name_with_nicknames(search_name)
        result_variations = normalize_name_with_nicknames(result_name_clean)
        
        # Try all combinations and take the highest score
        best_name_score = 0
        for search_var in search_variations:
            for result_var in result_variations:
                # Use token_sort_ratio for better handling of name variations
                current_score = fuzz.token_sort_ratio(search_var.lower(), result_var.lower())
                best_name_score = max(best_name_score, current_score)
        
        score += (best_name_score * 0.5)
    
    # Company matching (50% weight)
    if expected_company and result.get('company'):
        result_company = result['company']
        
        # Use partial_ratio for company matching (handles variations like "Inc.", "LLC", etc.)
        company_score = fuzz.partial_ratio(expected_company.lower(), result_company.lower())
        score += (company_score * 0.5)
    
    # Bonus for Contact record type (+5 points)
    if result.get('section') == 'Contacts':
        score += 5.0
    
    # CRITICAL THRESHOLD: If company match is below 70%, cap the overall score at 69%
    # This forces manual review for weak company matches, even if name is perfect
    MINIMUM_COMPANY_MATCH = 70.0
    if expected_company and company_score < MINIMUM_COMPANY_MATCH:
        # Cap score at 69% to force manual review
        score = min(score, 69.0)
    
    return round(score, 2)


def calculate_name_only_score(result: dict, search_name: str = '') -> float:
    """
    Calculate match score based ONLY on name matching (for LinkedIn searches).
    
    Scoring formula:
    - Name Match: 100%
    - Bonus: +5 points for Contact record type
    - Minimum threshold: 70% to be considered valid
    
    Uses nickname normalization to handle variations.
    
    Args:
        result: Dictionary containing name and other fields
        search_name: The name being searched for
        
    Returns:
        Float score between 0-105
    """
    score = 0.0
    
    # Name matching (100% weight) with nickname awareness
    if search_name and result.get('name'):
        result_name = result['name']
        # Clean up the name (remove suffixes like "- CE Candidate")
        result_name_clean = re.sub(r'\s*-\s*CE Candidate.*$', '', result_name).strip()
        
        # Generate nickname variations for both search and result names
        search_variations = normalize_name_with_nicknames(search_name)
        result_variations = normalize_name_with_nicknames(result_name_clean)
        
        # Try all combinations and take the highest score
        best_name_score = 0
        for search_var in search_variations:
            for result_var in result_variations:
                # Use token_sort_ratio for better handling of name variations
                current_score = fuzz.token_sort_ratio(search_var.lower(), result_var.lower())
                best_name_score = max(best_name_score, current_score)
        
        score += best_name_score
    
    # Bonus for Contact record type (+5 points)
    if result.get('section') == 'Contacts':
        score += 5.0
    
    return round(score, 2)


def apply_chicago_tiebreaker(results: List[dict]) -> List[dict]:
    """
    Apply Chicago-Naperville-Arlington Heights MSA tiebreaker for results with same score.
    
    Args:
        results: List of results with scores
        
    Returns:
        Sorted list with Chicago MSA preferred in case of ties
    """
    chicago_msa = "Chicago-Naperville-Arlington Heights"
    
    # Sort by score (descending), then by Chicago MSA preference
    def sort_key(result):
        score = result.get('score', 0)
        is_chicago = 1 if chicago_msa in result.get('msa', '') else 0
        return (-score, -is_chicago)  # Negative for descending order
    
    return sorted(results, key=sort_key)