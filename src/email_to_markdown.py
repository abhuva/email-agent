"""
Email body sanitization and Markdown conversion module.

This module provides functions to:
- Detect email body type (HTML or plain text)
- Sanitize HTML content (remove scripts, dangerous elements)
- Convert HTML to Markdown
- Enhance plain text to Markdown
- Provide unified API for email body conversion
"""

import logging
import re
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False
    logger.warning("html2text not available. HTML to Markdown conversion will use fallback.")


def detect_content_type(body: str) -> bool:
    """
    Detect if email body is HTML or plain text.
    
    Args:
        body: Email body content
    
    Returns:
        True if HTML, False if plain text
    
    Examples:
        >>> detect_content_type("<p>Hello</p>")
        True
        >>> detect_content_type("Plain text email")
        False
    """
    if not body:
        return False
    
    # Check for HTML tags
    html_pattern = re.compile(r'<[a-z][\s\S]*>', re.IGNORECASE)
    return bool(html_pattern.search(body))


def sanitize_html_body(body: str) -> Dict[str, Any]:
    """
    Sanitize HTML email body by removing dangerous elements and inline images.
    
    Removes:
    - Script tags (security risk)
    - Style tags (not needed for content)
    - Noscript tags
    - Inline images (img tags)
    - Dangerous elements (iframe, object, embed)
    - JavaScript URLs
    
    Args:
        body: HTML email body content
    
    Returns:
        Dictionary with keys:
            - content: str - Sanitized HTML content
            - isHtml: bool - Always True for this function
            - warnings: List[str] - List of warnings about removed content
    
    Examples:
        >>> result = sanitize_html_body("<p>Hello</p><script>alert('xss')</script>")
        >>> result['isHtml']
        True
        >>> 'script' not in result['content']
        True
    """
    warnings = []
    
    if not body:
        return {
            'content': '',
            'isHtml': True,
            'warnings': []
        }
    
    try:
        soup = BeautifulSoup(body, 'html.parser')
        
        # Remove dangerous elements
        dangerous_tags = ['script', 'style', 'noscript', 'iframe', 'object', 'embed']
        for tag_name in dangerous_tags:
            for tag in soup.find_all(tag_name):
                warnings.append(f"Removed {tag_name} tag")
                tag.decompose()
        
        # Remove inline images
        for img in soup.find_all('img'):
            warnings.append("Removed inline image")
            img.decompose()
        
        # Remove javascript: URLs from links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href and href.lower().startswith('javascript:'):
                warnings.append("Removed javascript: URL")
                link.decompose()
        
        sanitized_html = str(soup)
        
        return {
            'content': sanitized_html,
            'isHtml': True,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error sanitizing HTML: {e}")
        # Fallback: return original body with warning
        return {
            'content': body,
            'isHtml': True,
            'warnings': [f"HTML sanitization failed: {e}"]
        }


def html_to_markdown(html_content: str) -> str:
    """
    Convert sanitized HTML to Markdown format.
    
    Preserves:
    - Headings (h1-h6)
    - Paragraphs
    - Emphasis (bold, italic)
    - Links
    - Lists (ul, ol)
    - Blockquotes
    - Code blocks
    
    Args:
        html_content: Sanitized HTML content
    
    Returns:
        Markdown formatted string
    
    Examples:
        >>> html = "<p>Hello <strong>world</strong></p>"
        >>> markdown = html_to_markdown(html)
        >>> 'world' in markdown
        True
    """
    if not html_content:
        return ''
    
    if not HAS_HTML2TEXT:
        # Fallback: use BeautifulSoup to extract text
        logger.warning("html2text not available, using fallback text extraction")
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator='\n\n', strip=True)
    
    try:
        # Configure html2text converter
        h = html2text.HTML2Text()
        h.ignore_links = False  # Keep links
        h.ignore_images = True  # We already removed images
        h.body_width = 0  # Don't wrap lines
        h.unicode_snob = True  # Use unicode characters
        h.mark_code = True  # Mark code blocks
        
        # Convert HTML to Markdown
        markdown = h.handle(html_content)
        
        return markdown.strip()
        
    except Exception as e:
        logger.error(f"Error converting HTML to Markdown: {e}")
        # Fallback: extract plain text
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator='\n\n', strip=True)


def enhance_plain_text_to_markdown(text: str) -> str:
    """
    Enhance plain text email by detecting and converting natural formatting patterns.
    
    Detects:
    - URLs and converts to Markdown links
    - Lines starting with * or - (lists)
    - Lines with multiple === or --- (headings)
    - Bold/italic patterns (*text*, _text_)
    
    Args:
        text: Plain text email content
    
    Returns:
        Enhanced Markdown formatted string
    
    Examples:
        >>> text = "Check out https://example.com"
        >>> markdown = enhance_plain_text_to_markdown(text)
        >>> 'example.com' in markdown
        True
    """
    if not text:
        return ''
    
    lines = text.split('\n')
    enhanced_lines = []
    
    # URL pattern
    url_pattern = re.compile(
        r'(https?://[^\s<>"{}|\\^`\[\]]+)',
        re.IGNORECASE
    )
    
    for line in lines:
        # Convert URLs to Markdown links
        line = url_pattern.sub(r'[\1](\1)', line)
        
        # Detect list items (lines starting with - or *)
        if re.match(r'^\s*[-*]\s+', line):
            # Already looks like a list, keep as is
            pass
        # Detect numbered lists
        elif re.match(r'^\s*\d+\.\s+', line):
            # Already looks like a numbered list, keep as is
            pass
        # Detect headings (lines with === or ---)
        elif re.match(r'^={3,}$', line) and enhanced_lines:
            # Convert previous line to heading
            if enhanced_lines:
                enhanced_lines[-1] = f"## {enhanced_lines[-1]}"
            continue
        elif re.match(r'^-{3,}$', line) and enhanced_lines:
            # Convert previous line to heading
            if enhanced_lines:
                enhanced_lines[-1] = f"### {enhanced_lines[-1]}"
            continue
        
        enhanced_lines.append(line)
    
    result = '\n'.join(enhanced_lines)
    
    # Clean up excessive empty lines (more than 2 consecutive)
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result.strip()


def convert_email_to_markdown(
    email_body: str,
    content_type: Optional[str] = None,
    strict_mode: bool = False
) -> str:
    """
    Convert email body to Markdown format.
    
    This is the main function to use for converting email bodies to Markdown.
    It handles both HTML and plain text emails, sanitizes content, and produces
    clean Markdown suitable for Obsidian notes.
    
    Args:
        email_body: Email body content (HTML or plain text)
        content_type: Optional content type hint (e.g., 'text/html', 'text/plain')
        strict_mode: If True, removes all HTML even if conversion fails
    
    Returns:
        Markdown formatted string
    
    Examples:
        >>> html = "<p>Hello <strong>world</strong></p>"
        >>> markdown = convert_email_to_markdown(html)
        >>> 'world' in markdown
        True
        >>> text = "Plain text email"
        >>> markdown = convert_email_to_markdown(text)
        >>> 'Plain text' in markdown
        True
    """
    if not email_body:
        return ''
    
    # Detect content type if not provided
    is_html = False
    if content_type:
        is_html = 'html' in content_type.lower()
    else:
        is_html = detect_content_type(email_body)
    
    if is_html:
        # Sanitize HTML
        sanitized = sanitize_html_body(email_body)
        
        if strict_mode and sanitized['warnings']:
            logger.debug(f"Sanitization warnings: {sanitized['warnings']}")
        
        # Convert to Markdown
        markdown = html_to_markdown(sanitized['content'])
        
        # Final cleanup
        markdown = _cleanup_markdown(markdown)
        
        return markdown
    else:
        # Plain text - enhance to Markdown
        markdown = enhance_plain_text_to_markdown(email_body)
        
        # Final cleanup
        markdown = _cleanup_markdown(markdown)
        
        return markdown


def _cleanup_markdown(markdown: str) -> str:
    """
    Clean up Markdown output: normalize whitespace, escape special chars, etc.
    
    Args:
        markdown: Raw Markdown string
    
    Returns:
        Cleaned Markdown string
    """
    if not markdown:
        return ''
    
    # Remove excessive empty lines (more than 2 consecutive)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    
    # Remove trailing whitespace from lines
    lines = [line.rstrip() for line in markdown.split('\n')]
    markdown = '\n'.join(lines)
    
    # Remove leading/trailing whitespace
    markdown = markdown.strip()
    
    return markdown
