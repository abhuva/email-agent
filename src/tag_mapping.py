# Tag mapping and extraction logic for email-agent.

from typing import Dict, List
import re

# Allowed LLM keywords (case-insensitive)
ALLOWED_KEYWORDS = {"urgent", "neutral", "spam"}


def extract_keyword(ai_response: str) -> str:
    """
    Extract the single allowed keyword ('urgent', 'neutral', 'spam') from AI response.
    - Accepts only exact matches (case-insensitive, whitespace trimmed, stripping non-alpha chars from first token)
    - If not recognized, returns 'neutral' (safe fallback)
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
    Map the extracted keyword to IMAP tag(s) using the config-provided mapping (case-insensitive)
    - Always returns a list (for eventual [AI-Processed] append)
    - Defaults to neutral tag if not found
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
