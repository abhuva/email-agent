"""
Email body truncation module.
Handles truncation of email bodies (plain text and HTML) to configurable maximum length.
"""

import logging
from typing import Dict, Tuple, Optional
from src.config import ConfigManager

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger = logging.getLogger(__name__)
    logger.warning("BeautifulSoup4 not available. HTML truncation will use plain text fallback.")

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
    
    Uses BeautifulSoup to parse HTML, traverse text nodes, and truncate at logical
    break points (end of paragraphs/divs) while maintaining valid HTML structure.
    
    Args:
        body: HTML email body
        max_length: Maximum character count (must be positive)
    
    Returns:
        Dict with keys:
            - truncatedBody: str - Truncated HTML body
            - isTruncated: bool - Whether truncation occurred
    """
    if not body:
        return {'truncatedBody': '', 'isTruncated': False}
    
    if max_length <= 0:
        logger.warning(f"Invalid max_length: {max_length}. Returning empty string.")
        return {'truncatedBody': '', 'isTruncated': False}
    
    if not HAS_BS4:
        # Fallback to plain text truncation if BeautifulSoup not available
        logger.warning("BeautifulSoup4 not available, using plain text fallback for HTML")
        result = truncate_plain_text(body, max_length)
        if result['isTruncated']:
            result['truncatedBody'] = result['truncatedBody'].replace(
                TRUNCATION_INDICATOR,
                '<p><em>[Content truncated]</em></p>'
            )
        return result
    
    # Reserve space for HTML truncation indicator
    indicator_html = '<p><em>[Content truncated]</em></p>'
    indicator_len = len(indicator_html)
    available_length = max_length - indicator_len
    
    if available_length <= 0:
        # Max length too small
        return {'truncatedBody': indicator_html[:max_length], 'isTruncated': True}
    
    try:
        # Always parse HTML to remove scripts/styles, even if no truncation needed
        soup = BeautifulSoup(body, 'html.parser')
        
        # Remove script and style tags (don't count toward text length for AI processing)
        # These should always be removed for security and to focus on content
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Check if truncation is needed (after cleaning)
        if len(body) <= max_length:
            # Return cleaned HTML even if no truncation needed
            return {'truncatedBody': str(soup), 'isTruncated': False}
        
        # Get plain text content for length calculation
        text_content = soup.get_text(separator=' ', strip=True)
        
        # If plain text representation is short enough, no truncation needed
        # But still return cleaned HTML (without scripts/styles)
        if len(text_content) <= available_length:
            return {'truncatedBody': str(soup), 'isTruncated': False}
        
        # Strategy: Traverse elements and remove from end until we're under limit
        # Start with a copy for manipulation
        truncated_soup = BeautifulSoup(str(soup), 'html.parser')
        
        # Remove script/style from copy too
        for tag in truncated_soup(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Find all block-level elements (p, div, li, etc.) that we can remove
        block_elements = truncated_soup.find_all(['p', 'div', 'li', 'section', 'article', 'aside'])
        
        # Remove from end until we're under the limit
        current_text = truncated_soup.get_text(separator=' ', strip=True)
        while len(current_text) > available_length and block_elements:
            # Remove last block element
            block_elements[-1].decompose()
            block_elements.pop()
            current_text = truncated_soup.get_text(separator=' ', strip=True)
        
        # If still too long, use more aggressive approach: keep only first N characters of text
        if len(current_text) > available_length:
            # Extract and truncate text, then rebuild minimal HTML
            plain_result = truncate_plain_text(text_content, available_length)
            truncated_text = plain_result['truncatedBody'].replace(TRUNCATION_INDICATOR, '').strip()
            # Wrap in a simple paragraph
            result_html = f"<p>{truncated_text}</p>{indicator_html}"
        else:
            # Add truncation indicator to the truncated HTML
            if truncated_soup.body:
                truncated_soup.body.append(BeautifulSoup(indicator_html, 'html.parser'))
            elif truncated_soup.html:
                if truncated_soup.html.body:
                    truncated_soup.html.body.append(BeautifulSoup(indicator_html, 'html.parser'))
                else:
                    truncated_soup.html.append(BeautifulSoup(indicator_html, 'html.parser'))
            else:
                # No body/html tags, append to root
                truncated_soup.append(BeautifulSoup(indicator_html, 'html.parser'))
            
            result_html = str(truncated_soup)
        
        # Final safety check
        if len(result_html) > max_length:
            # Last resort: very basic HTML
            plain_result = truncate_plain_text(text_content, available_length)
            truncated_text = plain_result['truncatedBody'].replace(TRUNCATION_INDICATOR, '').strip()
            result_html = f"<p>{truncated_text}</p>{indicator_html}"
            if len(result_html) > max_length:
                result_html = result_html[:max_length]
        
        return {'truncatedBody': result_html, 'isTruncated': True}
        
    except Exception as e:
        logger.error(f"Error truncating HTML: {e}. Falling back to plain text truncation.")
        # Fallback to plain text
        result = truncate_plain_text(body, max_length)
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
