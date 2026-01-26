"""
Rules engine for email processing pipeline.

This module provides blacklist and whitelist rule processing functionality.
Blacklist rules are applied BEFORE AI processing (pre-processing) to either
DROP emails (skip processing entirely) or RECORD them (generate raw markdown
without AI classification).

Whitelist rules are applied AFTER AI processing (post-processing) to boost
importance scores and add tags to emails that match.

Integration Pattern:
    Rules are loaded from YAML configuration files and applied to EmailContext
    objects as they move through the processing pipeline:
    
    1. Load rules: rules = load_blacklist_rules(config_path)
    2. Check blacklist: action = check_blacklist(email_context, rules)
    3. Apply action: Based on action (DROP, RECORD, PASS), proceed accordingly
    4. After LLM classification: rules = load_whitelist_rules(config_path)
    5. Apply whitelist: new_score, tags = apply_whitelist(email_context, rules, current_score)
    
    Example:
        >>> from src.models import EmailContext
        >>> from src.rules import load_blacklist_rules, check_blacklist
        >>> 
        >>> email = EmailContext(uid="123", sender="spam@example.com", subject="Test")
        >>> rules = load_blacklist_rules("config/blacklist.yaml")
        >>> action = check_blacklist(email, rules)
        >>> if action == ActionEnum.DROP:
        ...     # Skip processing
        ...     pass
"""

import logging
import os
import re
import yaml
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Union, Any
from email.utils import parseaddr

from src.models import EmailContext

logger = logging.getLogger(__name__)


class InvalidRuleError(Exception):
    """Exception raised when a rule (blacklist or whitelist) is invalid or malformed."""
    pass


class ActionEnum(Enum):
    """
    Actions that can be taken when a blacklist rule matches.
    
    Values:
        DROP: Skip email processing entirely (do not generate any files)
        RECORD: Generate raw markdown file without AI classification
        PASS: Continue with normal processing pipeline
    """
    DROP = "drop"
    RECORD = "record"
    PASS = "pass"


@dataclass
class BlacklistRule:
    """
    Represents a single blacklist rule for email filtering.
    
    Blacklist rules are applied before AI processing to filter out unwanted
    emails. Each rule specifies a trigger type (sender, subject, or domain),
    a value to match against, and an action to take when matched.
    
    Fields:
        trigger_type: Type of field to match ("sender", "subject", or "domain")
        value: The value to match against (exact match for sender/subject,
              domain match for domain trigger)
        action: Action to take when rule matches (ActionEnum: DROP, RECORD, or PASS)
        pattern: Optional compiled regex pattern if value contains regex
        raw_value: Original value string for reference
    
    Example:
        >>> rule = BlacklistRule(
        ...     trigger_type="sender",
        ...     value="no-reply@spam.com",
        ...     action=ActionEnum.DROP
        ... )
        >>> rule.trigger_type
        'sender'
    """
    trigger_type: str  # "sender", "subject", or "domain"
    value: str  # The pattern/value to match
    action: ActionEnum  # Action to take when matched
    
    # Optional fields for regex support
    pattern: Optional[Pattern[str]] = None  # Compiled regex if value is regex
    raw_value: Optional[str] = None  # Original value for reference
    
    def __post_init__(self):
        """Validate rule after initialization."""
        if self.trigger_type not in ("sender", "subject", "domain"):
            raise ValueError(
                f"Invalid trigger_type: {self.trigger_type}. "
                f"Must be one of: sender, subject, domain"
            )
        
        if not self.value:
            raise ValueError("Rule value cannot be empty")
        
        if not isinstance(self.action, ActionEnum):
            raise ValueError(f"Action must be ActionEnum, got {type(self.action)}")


# Type alias for convenience
TriggerType = str  # "sender" | "subject" | "domain"


def validate_blacklist_rule(raw_rule: Dict[str, Any]) -> BlacklistRule:
    """
    Validate and convert a raw rule dictionary into a BlacklistRule object.
    
    This function checks that all required fields are present, validates
    trigger types and actions, and handles regex pattern compilation if needed.
    
    Args:
        raw_rule: Dictionary with rule data from YAML file.
                 Expected keys: trigger, value, action
    
    Returns:
        Validated BlacklistRule object
    
    Raises:
        InvalidRuleError: If the rule is malformed or invalid
    
    Example:
        >>> raw_rule = {
        ...     "trigger": "sender",
        ...     "value": "spam@example.com",
        ...     "action": "drop"
        ... }
        >>> rule = validate_blacklist_rule(raw_rule)
        >>> rule.trigger_type
        'sender'
    """
    if not isinstance(raw_rule, dict):
        raise InvalidRuleError(
            f"Rule must be a dictionary, got {type(raw_rule).__name__}"
        )
    
    # Extract and validate trigger type
    trigger = raw_rule.get("trigger")
    if not trigger:
        raise InvalidRuleError("Rule missing required field: 'trigger'")
    
    trigger_str = str(trigger).lower().strip()
    if trigger_str not in ("sender", "subject", "domain"):
        raise InvalidRuleError(
            f"Invalid trigger type: '{trigger}'. "
            f"Must be one of: sender, subject, domain"
        )
    
    # Extract and validate value
    value = raw_rule.get("value")
    if value is None:
        raise InvalidRuleError("Rule missing required field: 'value'")
    
    value_str = str(value).strip()
    if not value_str:
        raise InvalidRuleError("Rule 'value' cannot be empty")
    
    # Extract and validate action
    action_str = raw_rule.get("action")
    if not action_str:
        raise InvalidRuleError("Rule missing required field: 'action'")
    
    action_str_lower = str(action_str).lower().strip()
    try:
        action = ActionEnum(action_str_lower)
    except ValueError:
        valid_actions = [e.value for e in ActionEnum]
        raise InvalidRuleError(
            f"Invalid action: '{action_str}'. "
            f"Must be one of: {', '.join(valid_actions)}"
        )
    
    # Try to compile as regex if value looks like a regex pattern
    # (contains special regex characters)
    pattern = None
    raw_value = value_str
    
    # Check if value contains regex-like patterns (simple heuristic)
    regex_indicators = ['*', '?', '^', '$', '[', ']', '(', ')', '|', '+', '{', '}']
    if any(char in value_str for char in regex_indicators):
        try:
            pattern = re.compile(value_str, re.IGNORECASE)
            logger.debug(f"Compiled regex pattern for rule: {value_str}")
        except re.error as e:
            # If regex compilation fails, treat as literal string
            logger.warning(
                f"Rule value '{value_str}' contains regex characters but failed to "
                f"compile as regex: {e}. Treating as literal string."
            )
            pattern = None
    
    return BlacklistRule(
        trigger_type=trigger_str,
        value=value_str,
        action=action,
        pattern=pattern,
        raw_value=raw_value
    )


def load_blacklist_rules(config_path: Union[str, Path]) -> List[BlacklistRule]:
    """
    Load blacklist rules from a YAML configuration file.
    
    This function reads a YAML file containing blacklist rules, validates each
    rule, and returns a list of BlacklistRule objects. Malformed rules are
    skipped with a warning log message, allowing the system to continue
    processing with valid rules.
    
    Args:
        config_path: Path to the blacklist YAML configuration file
    
    Returns:
        List of validated BlacklistRule objects. Empty list if file doesn't
        exist or contains no valid rules.
    
    Raises:
        InvalidRuleError: If the YAML file cannot be read or parsed
    
    Example:
        >>> rules = load_blacklist_rules("config/blacklist.yaml")
        >>> len(rules)
        3
        >>> rules[0].trigger_type
        'sender'
    """
    config_path = Path(config_path)
    
    # Handle missing file gracefully (return empty list)
    if not config_path.exists():
        logger.warning(f"Blacklist config file not found: {config_path}. Using empty rules list.")
        return []
    
    # Load YAML file
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise InvalidRuleError(
            f"YAML parse error in {config_path}: {e}"
        ) from e
    except IOError as e:
        raise InvalidRuleError(
            f"Error reading blacklist config file {config_path}: {e}"
        ) from e
    
    # Handle empty or None YAML
    if raw_data is None:
        logger.warning(f"Blacklist config file {config_path} is empty. Using empty rules list.")
        return []
    
    # Extract rules list
    # YAML structure can be either:
    # 1. A list of rules directly: [{trigger: ..., value: ..., action: ...}, ...]
    # 2. A dict with 'blocked_items' key: {blocked_items: [{trigger: ..., ...}, ...]}
    rules_list = []
    
    if isinstance(raw_data, list):
        # Direct list format
        rules_list = raw_data
    elif isinstance(raw_data, dict):
        # Dict format - look for 'blocked_items' key
        if 'blocked_items' in raw_data:
            blocked_items = raw_data['blocked_items']
            if isinstance(blocked_items, list):
                rules_list = blocked_items
            else:
                logger.warning(
                    f"Expected 'blocked_items' to be a list in {config_path}, "
                    f"got {type(blocked_items).__name__}. Using empty rules list."
                )
        else:
            # Try to find any list value in the dict
            for key, value in raw_data.items():
                if isinstance(value, list):
                    rules_list = value
                    logger.info(f"Using '{key}' list from {config_path} as rules")
                    break
    else:
        logger.warning(
            f"Unexpected YAML structure in {config_path}: expected list or dict, "
            f"got {type(raw_data).__name__}. Using empty rules list."
        )
        return []
    
    # Validate and convert each rule
    validated_rules = []
    skipped_count = 0
    
    for idx, raw_rule in enumerate(rules_list, start=1):
        try:
            rule = validate_blacklist_rule(raw_rule)
            validated_rules.append(rule)
        except InvalidRuleError as e:
            skipped_count += 1
            logger.warning(
                f"Skipping malformed rule #{idx} in {config_path}: {e}. "
                f"Rule data: {raw_rule}"
            )
        except Exception as e:
            skipped_count += 1
            logger.error(
                f"Unexpected error validating rule #{idx} in {config_path}: {e}. "
                f"Rule data: {raw_rule}",
                exc_info=True
            )
    
    if skipped_count > 0:
        logger.warning(
            f"Skipped {skipped_count} invalid rule(s) from {config_path}. "
            f"Loaded {len(validated_rules)} valid rule(s)."
        )
    else:
        logger.info(f"Loaded {len(validated_rules)} blacklist rule(s) from {config_path}")
    
    return validated_rules


def _extract_domain_from_email(email_address: str) -> Optional[str]:
    """
    Extract domain from an email address.
    
    Handles various email formats:
    - "user@domain.com"
    - "Name <user@domain.com>"
    - "Lastname, Firstname <user@domain.com>"
    - "user@domain.com" (already clean)
    
    Args:
        email_address: Email address string (may include name)
    
    Returns:
        Domain string (e.g., "example.com") or None if extraction fails
    
    Example:
        >>> _extract_domain_from_email("user@example.com")
        'example.com'
        >>> _extract_domain_from_email("Name <user@example.com>")
        'example.com'
        >>> _extract_domain_from_email("Lastname, Firstname <user@example.com>")
        'example.com'
    """
    if not email_address:
        return None
    
    email_str = str(email_address).strip()
    
    # First try to extract email from angle brackets if present
    # This handles "Name <email>" and "Lastname, Firstname <email>" formats
    if '<' in email_str and '>' in email_str:
        start = email_str.rfind('<')
        end = email_str.rfind('>')
        if start < end:
            email_addr = email_str[start+1:end].strip()
            # Extract domain part (everything after @)
            if '@' in email_addr:
                domain = email_addr.split('@', 1)[1].strip()
                # Remove any trailing angle brackets or other characters
                domain = domain.rstrip('>').strip()
                return domain if domain else None
    
    # Fallback to parseaddr for other formats
    name, email_addr = parseaddr(email_str)
    
    # If parseaddr didn't extract email, try the whole string
    if not email_addr:
        email_addr = email_str
        # Try to extract email from angle brackets if present (fallback)
        if '<' in email_addr and '>' in email_addr:
            start = email_addr.rfind('<')
            end = email_addr.rfind('>')
            if start < end:
                email_addr = email_addr[start+1:end].strip()
    
    # Extract domain part (everything after @)
    if '@' in email_addr:
        domain = email_addr.split('@', 1)[1].strip()
        # Remove any trailing angle brackets or other characters
        domain = domain.rstrip('>').strip()
        return domain if domain else None
    
    return None


def _match_pattern(value: str, pattern: Optional[Pattern[str]], match_value: str) -> bool:
    """
    Match a string value against a pattern (regex or literal).
    
    Args:
        value: The pattern value from the rule
        pattern: Compiled regex pattern (if value is regex) or None
        match_value: The string to match against
    
    Returns:
        True if match_value matches the pattern, False otherwise
    """
    if not match_value:
        return False
    
    # If we have a compiled regex pattern, use it
    if pattern:
        try:
            return bool(pattern.search(match_value))
        except Exception as e:
            logger.warning(f"Error matching regex pattern '{value}': {e}")
            return False
    
    # Otherwise, do case-insensitive exact or contains match
    # For now, we'll do case-insensitive contains match
    # (can be enhanced to support exact match if needed)
    return value.lower() in match_value.lower()


def match_sender_rule(email_obj: EmailContext, rule: BlacklistRule) -> bool:
    """
    Check if an email matches a sender-based blacklist rule.
    
    This function extracts the sender email address from the EmailContext
    and matches it against the rule's value pattern. Matching is case-insensitive
    and supports both exact and substring matching.
    
    Args:
        email_obj: EmailContext object with sender information
        rule: BlacklistRule with trigger_type="sender"
    
    Returns:
        True if the email sender matches the rule, False otherwise
    
    Example:
        >>> email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        >>> rule = BlacklistRule(trigger_type="sender", value="spam@example.com", action=ActionEnum.DROP)
        >>> match_sender_rule(email, rule)
        True
    """
    if rule.trigger_type != "sender":
        return False
    
    if not email_obj.sender:
        return False
    
    return _match_pattern(rule.value, rule.pattern, email_obj.sender)


def match_subject_rule(email_obj: EmailContext, rule: BlacklistRule) -> bool:
    """
    Check if an email matches a subject-based blacklist rule.
    
    This function extracts the subject line from the EmailContext
    and matches it against the rule's value pattern. Matching is case-insensitive
    and supports both exact and substring matching.
    
    Args:
        email_obj: EmailContext object with subject information
        rule: BlacklistRule with trigger_type="subject"
    
    Returns:
        True if the email subject matches the rule, False otherwise
    
    Example:
        >>> email = EmailContext(uid="1", sender="test@example.com", subject="Unsubscribe Now")
        >>> rule = BlacklistRule(trigger_type="subject", value="Unsubscribe", action=ActionEnum.RECORD)
        >>> match_subject_rule(email, rule)
        True
    """
    if rule.trigger_type != "subject":
        return False
    
    if not email_obj.subject:
        return False
    
    return _match_pattern(rule.value, rule.pattern, email_obj.subject)


def match_domain_rule(email_obj: EmailContext, rule: BlacklistRule) -> bool:
    """
    Check if an email matches a domain-based blacklist rule.
    
    This function extracts the domain from the sender email address and
    matches it against the rule's value. Domain matching is case-insensitive
    and supports exact domain matching.
    
    Args:
        email_obj: EmailContext object with sender information
        rule: BlacklistRule with trigger_type="domain"
    
    Returns:
        True if the email domain matches the rule, False otherwise
    
    Example:
        >>> email = EmailContext(uid="1", sender="user@spam.com", subject="Test")
        >>> rule = BlacklistRule(trigger_type="domain", value="spam.com", action=ActionEnum.DROP)
        >>> match_domain_rule(email, rule)
        True
    """
    if rule.trigger_type != "domain":
        return False
    
    if not email_obj.sender:
        return False
    
    # Extract domain from sender
    domain = _extract_domain_from_email(email_obj.sender)
    if not domain:
        return False
    
    # For domain matching, we typically want exact match (case-insensitive)
    # but also support regex if pattern is provided
    if rule.pattern:
        return _match_pattern(rule.value, rule.pattern, domain)
    else:
        # Exact domain match (case-insensitive)
        return rule.value.lower() == domain.lower()


def rule_matches_email(email_obj: EmailContext, rule: BlacklistRule) -> bool:
    """
    Check if an email matches a blacklist rule (dispatches to appropriate matcher).
    
    This is a convenience function that dispatches to the appropriate
    matching function based on the rule's trigger type.
    
    Args:
        email_obj: EmailContext object to check
        rule: BlacklistRule to match against
    
    Returns:
        True if the email matches the rule, False otherwise
    
    Example:
        >>> email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        >>> rule = BlacklistRule(trigger_type="sender", value="spam@example.com", action=ActionEnum.DROP)
        >>> rule_matches_email(email, rule)
        True
    """
    if rule.trigger_type == "sender":
        return match_sender_rule(email_obj, rule)
    elif rule.trigger_type == "subject":
        return match_subject_rule(email_obj, rule)
    elif rule.trigger_type == "domain":
        return match_domain_rule(email_obj, rule)
    else:
        logger.warning(f"Unknown trigger type: {rule.trigger_type}")
        return False


def check_blacklist(email_obj: EmailContext, rules: List[BlacklistRule]) -> ActionEnum:
    """
    Check if an email matches any blacklist rules and return the appropriate action.
    
    This function iterates through the provided blacklist rules and checks if
    the email matches any of them. When multiple rules match, the action with
    the highest priority is returned:
    - DROP (highest priority) - Skip email processing entirely
    - RECORD (medium priority) - Generate raw markdown without AI
    - PASS (lowest priority) - Continue with normal processing
    
    If no rules match, returns PASS (default action).
    
    Args:
        email_obj: EmailContext object to check against blacklist rules
        rules: List of BlacklistRule objects to check
    
    Returns:
        ActionEnum indicating what action to take:
        - ActionEnum.DROP: Skip processing entirely
        - ActionEnum.RECORD: Generate raw markdown without AI
        - ActionEnum.PASS: Continue with normal processing (default)
    
    Example:
        >>> from src.models import EmailContext
        >>> from src.rules import load_blacklist_rules, check_blacklist
        >>> 
        >>> email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        >>> rules = load_blacklist_rules("config/blacklist.yaml")
        >>> action = check_blacklist(email, rules)
        >>> if action == ActionEnum.DROP:
        ...     print("Email will be dropped")
    """
    if not rules:
        return ActionEnum.PASS
    
    # Track the highest priority action found
    # Priority order: DROP > RECORD > PASS
    highest_action = ActionEnum.PASS
    
    for rule in rules:
        try:
            # Check if this rule matches the email
            if rule_matches_email(email_obj, rule):
                # Update highest priority action
                # DROP has highest priority, then RECORD, then PASS
                if rule.action == ActionEnum.DROP:
                    highest_action = ActionEnum.DROP
                    # DROP is highest priority, so we can return immediately
                    logger.debug(
                        f"Email {email_obj.uid} matched DROP rule: "
                        f"{rule.trigger_type}={rule.value}"
                    )
                    return ActionEnum.DROP
                elif rule.action == ActionEnum.RECORD:
                    # RECORD is higher than PASS, but lower than DROP
                    if highest_action == ActionEnum.PASS:
                        highest_action = ActionEnum.RECORD
                        logger.debug(
                            f"Email {email_obj.uid} matched RECORD rule: "
                            f"{rule.trigger_type}={rule.value}"
                        )
                # PASS actions don't need to update highest_action (it's already PASS)
        
        except Exception as e:
            # Defensive handling: if a rule causes an unexpected error,
            # log it and continue with other rules
            logger.warning(
                f"Error checking rule {rule.trigger_type}={rule.value} "
                f"against email {email_obj.uid}: {e}. Skipping this rule.",
                exc_info=True
            )
            continue
    
    return highest_action


@dataclass
class WhitelistRule:
    """
    Represents a single whitelist rule for email score boosting and tagging.
    
    Whitelist rules are applied after AI processing to boost importance scores
    and add tags to emails that match. Each rule specifies a trigger type
    (sender, subject, or domain), a value to match against, a score boost to
    apply, and optional tags to add.
    
    Fields:
        trigger_type: Type of field to match ("sender", "subject", or "domain")
        value: The value to match against (exact match for sender/subject,
              domain match for domain trigger)
        score_boost: Numeric value to add to importance_score (must be >= 0)
        tags: List of tags to add to the email (list of strings)
        pattern: Optional compiled regex pattern if value contains regex
        raw_value: Original value string for reference
    
    Example:
        >>> rule = WhitelistRule(
        ...     trigger_type="domain",
        ...     value="important-client.com",
        ...     score_boost=20,
        ...     tags=["#vip", "#work"]
        ... )
        >>> rule.trigger_type
        'domain'
    """
    trigger_type: str  # "sender", "subject", or "domain"
    value: str  # The pattern/value to match
    score_boost: float  # Score boost to apply (must be >= 0)
    tags: List[str]  # Tags to add when rule matches
    
    # Optional fields for regex support
    pattern: Optional[Pattern[str]] = None  # Compiled regex if value is regex
    raw_value: Optional[str] = None  # Original value for reference
    
    def __post_init__(self):
        """Validate rule after initialization."""
        if self.trigger_type not in ("sender", "subject", "domain"):
            raise ValueError(
                f"Invalid trigger_type: {self.trigger_type}. "
                f"Must be one of: sender, subject, domain"
            )
        
        if not self.value:
            raise ValueError("Rule value cannot be empty")
        
        if self.score_boost < 0:
            raise ValueError(f"score_boost must be >= 0, got {self.score_boost}")
        
        if not isinstance(self.tags, list):
            raise ValueError(f"tags must be a list, got {type(self.tags)}")
        
        # Validate tags are non-empty strings
        for tag in self.tags:
            if not isinstance(tag, str):
                raise ValueError(f"All tags must be strings, got {type(tag)}")
            if not tag.strip():
                raise ValueError("Tags cannot be empty strings")


def validate_whitelist_rule(raw_rule: Dict[str, Any]) -> WhitelistRule:
    """
    Validate and convert a raw rule dictionary into a WhitelistRule object.
    
    This function checks that all required fields are present, validates
    trigger types, score_boost values, and tags, and handles regex pattern
    compilation if needed.
    
    Args:
        raw_rule: Dictionary with rule data from YAML file.
                 Expected keys: trigger, value, action, score_boost, add_tags
    
    Returns:
        Validated WhitelistRule object
    
    Raises:
        InvalidRuleError: If the rule is malformed or invalid
    
    Example:
        >>> raw_rule = {
        ...     "trigger": "domain",
        ...     "value": "important-client.com",
        ...     "action": "boost",
        ...     "score_boost": 20,
        ...     "add_tags": ["#vip", "#work"]
        ... }
        >>> rule = validate_whitelist_rule(raw_rule)
        >>> rule.trigger_type
        'domain'
    """
    if not isinstance(raw_rule, dict):
        raise InvalidRuleError(
            f"Rule must be a dictionary, got {type(raw_rule).__name__}"
        )
    
    # Extract and validate trigger type
    trigger = raw_rule.get("trigger")
    if not trigger:
        raise InvalidRuleError("Rule missing required field: 'trigger'")
    
    trigger_str = str(trigger).lower().strip()
    if trigger_str not in ("sender", "subject", "domain"):
        raise InvalidRuleError(
            f"Invalid trigger type: '{trigger}'. "
            f"Must be one of: sender, subject, domain"
        )
    
    # Extract and validate value
    value = raw_rule.get("value")
    if value is None:
        raise InvalidRuleError("Rule missing required field: 'value'")
    
    value_str = str(value).strip()
    if not value_str:
        raise InvalidRuleError("Rule 'value' cannot be empty")
    
    # Extract and validate action (must be "boost" for whitelist)
    action_str = raw_rule.get("action")
    if not action_str:
        raise InvalidRuleError("Rule missing required field: 'action'")
    
    action_str_lower = str(action_str).lower().strip()
    if action_str_lower != "boost":
        raise InvalidRuleError(
            f"Invalid action for whitelist rule: '{action_str}'. "
            f"Must be 'boost'"
        )
    
    # Extract and validate score_boost
    score_boost = raw_rule.get("score_boost")
    if score_boost is None:
        raise InvalidRuleError("Rule missing required field: 'score_boost'")
    
    # Convert to float and validate
    try:
        score_boost_float = float(score_boost)
    except (ValueError, TypeError):
        raise InvalidRuleError(
            f"score_boost must be a number, got {type(score_boost).__name__}: {score_boost}"
        )
    
    if score_boost_float < 0:
        raise InvalidRuleError(
            f"score_boost must be >= 0, got {score_boost_float}"
        )
    
    # Extract and validate tags
    tags = raw_rule.get("add_tags", [])
    if not isinstance(tags, list):
        raise InvalidRuleError(
            f"add_tags must be a list, got {type(tags).__name__}"
        )
    
    # Validate and normalize tags
    validated_tags = []
    for idx, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise InvalidRuleError(
                f"Tag at index {idx} must be a string, got {type(tag).__name__}"
            )
        tag_str = str(tag).strip()
        if not tag_str:
            raise InvalidRuleError(f"Tag at index {idx} cannot be empty")
        validated_tags.append(tag_str)
    
    # Try to compile as regex if value looks like a regex pattern
    pattern = None
    raw_value = value_str
    
    # Check if value contains regex-like patterns (simple heuristic)
    regex_indicators = ['*', '?', '^', '$', '[', ']', '(', ')', '|', '+', '{', '}']
    if any(char in value_str for char in regex_indicators):
        try:
            pattern = re.compile(value_str, re.IGNORECASE)
            logger.debug(f"Compiled regex pattern for whitelist rule: {value_str}")
        except re.error as e:
            # If regex compilation fails, treat as literal string
            logger.warning(
                f"Whitelist rule value '{value_str}' contains regex characters but failed to "
                f"compile as regex: {e}. Treating as literal string."
            )
            pattern = None
    
    return WhitelistRule(
        trigger_type=trigger_str,
        value=value_str,
        score_boost=score_boost_float,
        tags=validated_tags,
        pattern=pattern,
        raw_value=raw_value
    )


def load_whitelist_rules(config_path: Union[str, Path]) -> List[WhitelistRule]:
    """
    Load whitelist rules from a YAML configuration file.
    
    This function reads a YAML file containing whitelist rules, validates each
    rule, and returns a list of WhitelistRule objects. Malformed rules are
    skipped with a warning log message, allowing the system to continue
    processing with valid rules.
    
    Args:
        config_path: Path to the whitelist YAML configuration file
    
    Returns:
        List of validated WhitelistRule objects. Empty list if file doesn't
        exist or contains no valid rules.
    
    Raises:
        InvalidRuleError: If the YAML file cannot be read or parsed
    
    Example:
        >>> rules = load_whitelist_rules("config/whitelist.yaml")
        >>> len(rules)
        2
        >>> rules[0].trigger_type
        'domain'
    """
    config_path = Path(config_path)
    
    # Handle missing file gracefully (return empty list)
    if not config_path.exists():
        logger.warning(f"Whitelist config file not found: {config_path}. Using empty rules list.")
        return []
    
    # Load YAML file
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise InvalidRuleError(
            f"YAML parse error in {config_path}: {e}"
        ) from e
    except IOError as e:
        raise InvalidRuleError(
            f"Error reading whitelist config file {config_path}: {e}"
        ) from e
    
    # Handle empty or None YAML
    if raw_data is None:
        logger.warning(f"Whitelist config file {config_path} is empty. Using empty rules list.")
        return []
    
    # Extract rules list
    # YAML structure can be either:
    # 1. A list of rules directly: [{trigger: ..., value: ..., action: ..., score_boost: ..., add_tags: ...}, ...]
    # 2. A dict with 'allowed_items' key: {allowed_items: [{trigger: ..., ...}, ...]}
    rules_list = []
    
    if isinstance(raw_data, list):
        # Direct list format
        rules_list = raw_data
    elif isinstance(raw_data, dict):
        # Dict format - look for 'allowed_items' key
        if 'allowed_items' in raw_data:
            allowed_items = raw_data['allowed_items']
            if isinstance(allowed_items, list):
                rules_list = allowed_items
            else:
                logger.warning(
                    f"Expected 'allowed_items' to be a list in {config_path}, "
                    f"got {type(allowed_items).__name__}. Using empty rules list."
                )
        else:
            # Try to find any list value in the dict
            for key, value in raw_data.items():
                if isinstance(value, list):
                    rules_list = value
                    logger.info(f"Using '{key}' list from {config_path} as rules")
                    break
    else:
        logger.warning(
            f"Unexpected YAML structure in {config_path}: expected list or dict, "
            f"got {type(raw_data).__name__}. Using empty rules list."
        )
        return []
    
    # Validate and convert each rule
    validated_rules = []
    skipped_count = 0
    
    for idx, raw_rule in enumerate(rules_list, start=1):
        try:
            rule = validate_whitelist_rule(raw_rule)
            validated_rules.append(rule)
        except InvalidRuleError as e:
            skipped_count += 1
            logger.warning(
                f"Skipping malformed whitelist rule #{idx} in {config_path}: {e}. "
                f"Rule data: {raw_rule}"
            )
        except Exception as e:
            skipped_count += 1
            logger.error(
                f"Unexpected error validating whitelist rule #{idx} in {config_path}: {e}. "
                f"Rule data: {raw_rule}",
                exc_info=True
            )
    
    if skipped_count > 0:
        logger.warning(
            f"Skipped {skipped_count} invalid whitelist rule(s) from {config_path}. "
            f"Loaded {len(validated_rules)} valid rule(s)."
        )
    else:
        logger.info(f"Loaded {len(validated_rules)} whitelist rule(s) from {config_path}")
    
    return validated_rules


def whitelist_rule_matches_email(email_obj: EmailContext, rule: WhitelistRule) -> bool:
    """
    Check if an email matches a whitelist rule (dispatches to appropriate matcher).
    
    This function reuses the same trigger matching logic as blacklist rules
    but works with WhitelistRule objects. It dispatches to the appropriate
    matching function based on the rule's trigger type.
    
    Args:
        email_obj: EmailContext object to check
        rule: WhitelistRule to match against
    
    Returns:
        True if the email matches the rule, False otherwise
    
    Example:
        >>> email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        >>> rule = WhitelistRule(
        ...     trigger_type="sender",
        ...     value="boss@company.com",
        ...     score_boost=15,
        ...     tags=["#priority"]
        ... )
        >>> whitelist_rule_matches_email(email, rule)
        True
    """
    # Reuse the existing trigger matching logic by creating a temporary
    # BlacklistRule-like structure for matching (we only need trigger_type, value, pattern)
    # We can't directly use match_sender_rule etc. because they expect BlacklistRule,
    # so we'll implement the matching logic inline here
    
    if rule.trigger_type == "sender":
        if not email_obj.sender:
            return False
        return _match_pattern(rule.value, rule.pattern, email_obj.sender)
    elif rule.trigger_type == "subject":
        if not email_obj.subject:
            return False
        return _match_pattern(rule.value, rule.pattern, email_obj.subject)
    elif rule.trigger_type == "domain":
        if not email_obj.sender:
            return False
        domain = _extract_domain_from_email(email_obj.sender)
        if not domain:
            return False
        if rule.pattern:
            return _match_pattern(rule.value, rule.pattern, domain)
        else:
            return rule.value.lower() == domain.lower()
    else:
        logger.warning(f"Unknown trigger type: {rule.trigger_type}")
        return False


def apply_whitelist(
    email_obj: EmailContext,
    rules: List[WhitelistRule],
    current_score: float
) -> tuple[float, List[str]]:
    """
    Apply whitelist rules to an email, adjusting score and accumulating tags.
    
    This function iterates through the provided whitelist rules and checks if
    the email matches any of them. When a rule matches, its score_boost is
    added to the current score and its tags are added to the tags list.
    Multiple matching rules are cumulative - all matching rules' boosts and
    tags are applied.
    
    Args:
        email_obj: EmailContext object to check against whitelist rules
        rules: List of WhitelistRule objects to check
        current_score: Current importance score (before whitelist adjustments)
    
    Returns:
        Tuple of (new_score, tags_list) where:
        - new_score: Current score plus all matching rules' score_boost values
        - tags_list: List of all tags from matching rules (duplicates removed)
    
    Example:
        >>> from src.models import EmailContext
        >>> from src.rules import load_whitelist_rules, apply_whitelist
        >>> 
        >>> email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        >>> rules = load_whitelist_rules("config/whitelist.yaml")
        >>> new_score, tags = apply_whitelist(email, rules, 5.0)
        >>> new_score
        20.0
        >>> tags
        ['#priority']
    """
    if not rules:
        return (current_score, [])
    
    new_score = current_score
    tags_list = []
    
    for rule in rules:
        try:
            # Check if this rule matches the email
            if whitelist_rule_matches_email(email_obj, rule):
                # Apply score boost
                new_score += rule.score_boost
                
                # Add tags (avoid duplicates)
                for tag in rule.tags:
                    if tag not in tags_list:
                        tags_list.append(tag)
                
                logger.debug(
                    f"Email {email_obj.uid} matched whitelist rule: "
                    f"{rule.trigger_type}={rule.value}, "
                    f"boost={rule.score_boost}, tags={rule.tags}"
                )
        
        except Exception as e:
            # Defensive handling: if a rule causes an unexpected error,
            # log it and continue with other rules
            logger.warning(
                f"Error checking whitelist rule {rule.trigger_type}={rule.value} "
                f"against email {email_obj.uid}: {e}. Skipping this rule.",
                exc_info=True
            )
            continue
    
    return (new_score, tags_list)
