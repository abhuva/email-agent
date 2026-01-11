"""
Content parser module for converting HTML email bodies to Markdown.

This module provides functionality to:
- Convert HTML email content to Markdown format using html2text
- Fall back to plain text on conversion failure
- Enforce character limits on parsed content
- Track fallback status for pipeline processing

Integration Pattern:
    The content parser is used in the V4 processing pipeline:
    
    1. EmailContext is created with raw_html and raw_text
    2. parse_html_content() is called with both HTML and plain text
    3. Returns parsed_content and is_fallback flag
    4. EmailContext.parsed_body and EmailContext.is_html_fallback are updated
    
    Example:
        context = EmailContext(uid="123", sender="test@example.com", subject="Test",
                               raw_html="<p>Hello</p>", raw_text="Hello")
        parsed_content, is_fallback = parse_html_content(context.raw_html, context.raw_text)
        context.parsed_body = parsed_content
        context.is_html_fallback = is_fallback
"""

import logging
from typing import Tuple

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False

logger = logging.getLogger(__name__)


def _html_to_markdown(html_body: str) -> str:
    """
    Convert HTML content to Markdown format using html2text.
    
    This is a private helper function that handles the actual HTML to Markdown
    conversion. It configures html2text with appropriate settings for email
    content and returns the converted Markdown string.
    
    Args:
        html_body: HTML content to convert
    
    Returns:
        Markdown formatted string
    
    Raises:
        Exception: If html2text is not available or conversion fails
    """
    if not HAS_HTML2TEXT:
        raise ImportError("html2text library is not available")
    
    # Configure html2text converter
    h = html2text.HTML2Text()
    h.ignore_links = False  # Keep links in Markdown
    h.ignore_images = True  # Ignore images to save tokens
    h.body_width = 0  # Don't wrap lines (preserve original formatting)
    h.unicode_snob = True  # Use unicode characters
    h.mark_code = True  # Mark code blocks
    
    # Convert HTML to Markdown
    markdown = h.handle(html_body)
    
    # Basic normalization: strip leading/trailing whitespace
    return markdown.strip()


def parse_html_content(html_body: str, plain_text_body: str) -> Tuple[str, bool]:
    """
    Parse HTML email content to Markdown, with fallback to plain text.
    
    This function attempts to convert HTML email bodies to Markdown format.
    If HTML conversion fails (missing HTML, empty HTML, or conversion error),
    it falls back to using the plain text body. The function also enforces
    a 20,000 character limit on the returned content.
    
    Args:
        html_body: HTML content of the email (may be None, empty, or whitespace)
        plain_text_body: Plain text content of the email (fallback option)
    
    Returns:
        Tuple of (parsed_content: str, is_fallback: bool):
        - parsed_content: The converted Markdown content (or plain text if fallback)
        - is_fallback: True if plain text was used (HTML conversion failed/skipped),
                      False if HTML was successfully converted
    
    Examples:
        >>> html = "<p>Hello <strong>world</strong></p>"
        >>> text = "Hello world"
        >>> content, is_fallback = parse_html_content(html, text)
        >>> is_fallback
        False
        >>> 'world' in content
        True
        
        >>> content, is_fallback = parse_html_content("", "Plain text only")
        >>> is_fallback
        True
        >>> content
        'Plain text only'
    """
    # Handle missing, empty, or whitespace-only HTML
    if not html_body or not html_body.strip():
        logger.debug("HTML body is missing or empty, using plain text fallback")
        parsed_content = plain_text_body
        is_fallback = True
    else:
        # Attempt HTML to Markdown conversion
        try:
            logger.debug("Attempting HTML to Markdown conversion")
            parsed_content = _html_to_markdown(html_body)
            
            # Check if conversion produced empty or whitespace-only result
            if not parsed_content or not parsed_content.strip():
                logger.warning("HTML conversion produced empty result, falling back to plain text")
                parsed_content = plain_text_body
                is_fallback = True
            else:
                # Success: HTML was converted to Markdown
                logger.debug("HTML to Markdown conversion successful")
                is_fallback = False
                
        except Exception as e:
            # HTML conversion failed - log error and fall back to plain text
            logger.warning(f"HTML to Markdown conversion failed: {e}, falling back to plain text")
            parsed_content = plain_text_body
            is_fallback = True
    
    # Enforce 20,000 character limit
    # Note: Truncation does not change the is_fallback flag - if content came from
    # HTML and was truncated, is_fallback remains False; if it came from plain_text,
    # is_fallback remains True
    if len(parsed_content) > 20_000:
        original_length = len(parsed_content)
        parsed_content = parsed_content[:20_000]
        logger.warning(
            f"Content truncated from {original_length} to 20,000 characters "
            f"(is_fallback={is_fallback})"
        )
    
    return parsed_content, is_fallback
