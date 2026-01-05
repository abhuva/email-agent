# Tag mapping and extraction logic for email-agent.

from typing import Dict, List
import re

# Allowed LLM keywords (case-insensitive)
ALLOWED_KEYWORDS = {"urgent", "neutral", "spam"}


def extract_keyword(ai_response: str) -> str:
    """
    Extract the single allowed keyword from AI response.
    
    Extracts one of the allowed keywords ('urgent', 'neutral', 'spam') from the AI's
    response string. Performs case-insensitive matching and strips non-alphabetic
    characters from the first token. Always returns a valid keyword, defaulting to
    'neutral' if no match is found (safe fallback).
    
    Args:
        ai_response: Raw response string from AI (may contain extra text)
        
    Returns:
        One of: 'urgent', 'neutral', or 'spam' (always 'neutral' if no match)
        
    Example:
        >>> extract_keyword("urgent")
        'urgent'
        >>> extract_keyword("Urgent!!!")
        'urgent'
        >>> extract_keyword("This is spam")
        'spam'
        >>> extract_keyword("unknown response")
        'neutral'
    """
    if not ai_response:
        return "neutral"
    cleaned = ai_response.lower().strip()
    # Remove punctuation from the first word/token
    tokens = cleaned.split()
    if not tokens:
        return "neutral"
    first = re.sub(r'[^a-z]', '', tokens[0])  # keep only letters
    if first in ALLOWED_KEYWORDS:
        return first
    return "neutral"


def map_keyword_to_tags(keyword: str, tag_mapping: Dict[str, str]) -> List[str]:
    """
    Map extracted keyword to IMAP tag names using configuration mapping.
    
    Maps a keyword ('urgent', 'neutral', 'spam') to the corresponding IMAP tag name
    from the configuration. Performs case-insensitive lookup. If the keyword is not
    found in the mapping, falls back to the 'neutral' tag. Always returns a list
    (even if empty) for consistency with tagging operations.
    
    Args:
        keyword: Extracted keyword ('urgent', 'neutral', or 'spam')
        tag_mapping: Dictionary mapping keywords to IMAP tag names
                    (e.g., {'urgent': 'Urgent', 'neutral': 'Neutral', 'spam': 'Spam'})
        
    Returns:
        List containing the IMAP tag name, or empty list if mapping fails
        
    Example:
        >>> mapping = {'urgent': 'Urgent', 'neutral': 'Neutral', 'spam': 'Spam'}
        >>> map_keyword_to_tags('urgent', mapping)
        ['Urgent']
        >>> map_keyword_to_tags('unknown', mapping)
        ['Neutral']  # Falls back to neutral
    """
    key = keyword.lower()
    mapped = tag_mapping.get(key)
    if mapped:
        return [mapped]
    # Fallback to 'neutral' mapping, if defined
    mapped_neutral = tag_mapping.get("neutral")
    return [mapped_neutral] if mapped_neutral else []

# Example LLM prompt for enforcing only allowed keywords:
PROMPT_INSTRUCTION = (
    "You must respond with only one of the following tags, case-insensitive: 'Urgent', 'Neutral', or 'Spam'.\n"
    "Use 'Spam' only if you are highly confident the message is not legitimate. Default to 'Neutral' if you are unsure or it does not clearly match another category."
)
