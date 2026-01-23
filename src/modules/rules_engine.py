"""Rules Engine - Evaluates YAML rules to determine proposed_ca_status"""
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

def load_rules(rules_file: str = 'rules/proposed_status_rules.yaml') -> dict:
    """Load rules from YAML file."""
    rules_path = Path(__file__).parent.parent.parent / rules_file
    with open(rules_path, 'r') as f:
        return yaml.safe_load(f)

def evaluate_condition(field_value: Any, operator: str, expected_value: Any) -> bool:
    """Evaluate a single condition."""
    
    # Handle null checks first
    if operator == 'is_null':
        return field_value is None or field_value == '' or field_value == 'null'
    
    if operator == 'is_not_null':
        return field_value is not None and field_value != '' and field_value != 'null'
    
    # If field is null and operator is not a null check, condition fails
    if field_value is None or field_value == '' or field_value == 'null':
        return False
    
    # String operations
    if operator == 'equals':
        return str(field_value) == str(expected_value)
    
    if operator == 'contains':
        return str(expected_value).lower() in str(field_value).lower()
    
    # Date operations
    if operator in ['days_ago_less_than', 'days_ago_more_than']:
        try:
            # Parse date in format MM/DD/YYYY
            date_obj = datetime.strptime(str(field_value), '%m/%d/%Y')
            days_ago = (datetime.now() - date_obj).days
            
            if operator == 'days_ago_less_than':
                return days_ago < int(expected_value)
            else:  # days_ago_more_than
                return days_ago > int(expected_value)
        except (ValueError, TypeError):
            return False
    
    return False

def evaluate_rules(data: Dict[str, Any], logger=None) -> str:
    """
    Evaluate rules against data and return the proposed CA status.
    
    Args:
        data: Dictionary containing all output fields
        logger: Optional logger for debugging
    
    Returns:
        String with the proposed CA status
    """
    try:
        rules_config = load_rules()
        rules = rules_config.get('rules', [])
        
        if logger:
            logger.info(f'Evaluating {len(rules)} rules for proposed_ca_status')
        
        # Evaluate each rule in order
        for rule in rules:
            rule_name = rule.get('name', 'Unnamed')
            conditions = rule.get('conditions', [])
            result = rule.get('result', 'Unknown')
            
            # Empty conditions means this is the default/fallback rule
            if not conditions:
                if logger:
                    logger.info(f'Rule "{rule_name}" matched (default fallback)')
                return result
            
            # Check if ALL conditions match
            all_conditions_match = True
            for condition in conditions:
                field = condition.get('field')
                operator = condition.get('operator')
                value = condition.get('value')
                
                field_value = data.get(field)
                
                if not evaluate_condition(field_value, operator, value):
                    all_conditions_match = False
                    break
            
            # If all conditions matched, return this result
            if all_conditions_match:
                if logger:
                    logger.info(f'Rule "{rule_name}" matched → {result}')
                return result
        
        # No rules matched and no default fallback
        if logger:
            logger.warning('No rules matched and no default fallback found')
        return 'Unknown'
        
    except Exception as e:
        if logger:
            logger.error(f'Error evaluating rules: {e}')
        return 'Error'