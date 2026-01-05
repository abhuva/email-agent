"""
Email body truncation module.
Handles truncation of email bodies (plain text and HTML) to configurable maximum length.
"""

import logging
from typing import Dict, Tuple, Optional
from src.config import ConfigManager

logger = logging.getLogger(__name__)

# Default truncation length if not specified in config
DEFAULT_MAX_BODY_CHARS = 10000

# Truncation indicator text
TRUNCATION_INDICATOR = "[Content truncated]"


def get_max_truncation_length(config: Optional[ConfigManager] = None, default: int = DEFAULT_MAX_BODY_CHARS) -> int:
    """
    Get maximum truncation length from configuration.
    
    Args:
        config: ConfigManager instance (optional, for testing)
        default: Default value if config is None or value is missing/invalid
    
    Returns:
        Maximum character count for truncation (always positive)
    
    Raises:
        ValueError: If config value is negative
    """
    if config is None:
        logger.debug(f"Using default max_body_chars: {default}")
        return default
    
    try:
        max_chars = config.max_body_chars
        if max_chars <= 0:
            logger.warning(f"Invalid max_body_chars value: {max_chars}. Using default: {default}")
            return default
        logger.debug(f"Using max_body_chars from config: {max_chars}")
        return max_chars
    except (AttributeError, KeyError, ValueError, TypeError) as e:
        logger.warning(f"Could not read max_body_chars from config: {e}. Using default: {default}")
        return default


def truncate_plain_text(body: str, max_length: int) -> Dict[str, any]:
    """
    Truncate plain text email body, preferring word boundaries.
    
    Args:
        body: Plain text email body
        max_length: Maximum character count (must be positive)
    
    Returns:
        Dict with keys:
            - truncatedBody: str - Truncated body text
            - isTruncated: bool - Whether truncation occurred
    """
    if not body:
        return {'truncatedBody': '', 'isTruncated': False}
    
    if max_length <= 0:
        logger.warning(f"Invalid max_length: {max_length}. Returning empty string.")
        return {'truncatedBody': '', 'isTruncated': False}
    
    if len(body) <= max_length:
        return {'truncatedBody': body, 'isTruncated': False}
    
    # Reserve space for truncation indicator
    indicator_len = len(TRUNCATION_INDICATOR)
    available_length = max_length - indicator_len
    
    if available_length <= 0:
        # Max length is too small to fit indicator
        return {'truncatedBody': TRUNCATION_INDICATOR[:max_length], 'isTruncated': True}
    
    # Try to truncate at newline first (preferred)
    truncated = body[:available_length]
    newline_idx = truncated.rfind('\n')
    
    if newline_idx > available_length * 0.3:  # Only use if we keep at least 30% of content
        truncated = body[:newline_idx]
    else:
        # Fall back to word boundary (last space)
        space_idx = truncated.rfind(' ')
        if space_idx > available_length * 0.3:  # Only use if we keep at least 30% of content
            truncated = body[:space_idx]
        # If no good boundary found, truncate at exact position
    
    truncated = truncated.rstrip() + ' ' + TRUNCATION_INDICATOR
    
    # Ensure we don't exceed max_length (safety check)
    if len(truncated) > max_length:
        truncated = truncated[:max_length - len(TRUNCATION_INDICATOR)] + TRUNCATION_INDICATOR
        # If still too long, just cut it
        if len(truncated) > max_length:
            truncated = truncated[:max_length]
    
    return {'truncatedBody': truncated, 'isTruncated': True}


def truncate_html(body: str, max_length: int) -> Dict[str, any]:
    """
    Truncate HTML email body while preserving valid HTML structure.
    
    Args:
        body: HTML email body
        max_length: Maximum character count (must be positive)
    
    Returns:
        Dict with keys:
            - truncatedBody: str - Truncated HTML body
            - isTruncated: bool - Whether truncation occurred
    """
    # Placeholder - will implement with HTML parser
    # For now, fall back to plain text truncation
    logger.warning("HTML truncation not yet implemented, using plain text fallback")
    result = truncate_plain_text(body, max_length)
    # Replace plain text indicator with HTML indicator
    if result['isTruncated']:
        result['truncatedBody'] = result['truncatedBody'].replace(
            TRUNCATION_INDICATOR,
            '<p><em>[Content truncated]</em></p>'
        )
    return result


def truncate_email_body(
    body: str,
    contentType: str,
    max_length: int,
    config: Optional[ConfigManager] = None
) -> Dict[str, any]:
    """
    Main truncation function that detects format and delegates to appropriate handler.
    
    Args:
        body: Email body content
        contentType: Content-Type header (e.g., 'text/plain', 'text/html')
        max_length: Maximum character count (if None, reads from config)
        config: ConfigManager instance (optional, used if max_length is None)
    
    Returns:
        Dict with keys:
            - truncatedBody: str - Truncated body
            - isTruncated: bool - Whether truncation occurred
    """
    # Get max_length from config if not provided
    if max_length is None:
        max_length = get_max_truncation_length(config)
    
    if not body:
        return {'truncatedBody': '', 'isTruncated': False}
    
    # Detect format from content type
    content_type_lower = contentType.lower() if contentType else ''
    
    if 'text/html' in content_type_lower or 'html' in content_type_lower:
        logger.debug("Detected HTML format, using HTML truncation")
        return truncate_html(body, max_length)
    else:
        # Default to plain text
        logger.debug("Detected plain text format (or unknown), using plain text truncation")
        return truncate_plain_text(body, max_length)
