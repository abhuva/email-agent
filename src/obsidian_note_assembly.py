"""
Obsidian note assembly and formatting module.

This module provides functions to assemble complete Obsidian notes by combining:
- YAML frontmatter
- Summary section (as Obsidian callout)
- Original email content
"""

import logging
from typing import Dict, Any, Optional
from src.yaml_frontmatter import generate_email_yaml_frontmatter

logger = logging.getLogger(__name__)


def format_yaml_frontmatter(yaml_data: Dict[str, Any]) -> str:
    """
    Format YAML data as valid Obsidian YAML frontmatter with proper delimiters.
    
    This is a wrapper around the existing yaml_frontmatter module that ensures
    the output is properly formatted with delimiters.
    
    Args:
        yaml_data: Dictionary containing YAML frontmatter data
    
    Returns:
        YAML frontmatter string with --- delimiters, or empty frontmatter block if data is empty
    
    Examples:
        >>> data = {'subject': 'Test', 'from': 'test@example.com'}
        >>> frontmatter = format_yaml_frontmatter(data)
        >>> '---' in frontmatter
        True
        >>> 'subject' in frontmatter
        True
    """
    if not yaml_data:
        # Return empty frontmatter block
        return "---\n---\n"
    
    if not isinstance(yaml_data, dict):
        logger.warning(f"yaml_data is not a dict (got {type(yaml_data)}), returning empty frontmatter")
        return "---\n---\n"
    
    try:
        # Use existing function from yaml_frontmatter module
        frontmatter = generate_email_yaml_frontmatter(yaml_data)
        
        # Ensure it has proper delimiters (generate_email_yaml_frontmatter should already include them)
        if not frontmatter.startswith("---"):
            frontmatter = "---\n" + frontmatter
        if not frontmatter.endswith("\n---\n"):
            if frontmatter.endswith("\n---"):
                frontmatter = frontmatter + "\n"
            else:
                frontmatter = frontmatter.rstrip() + "\n---\n"
        
        return frontmatter
        
    except Exception as e:
        logger.error(f"Error formatting YAML frontmatter: {e}", exc_info=True)
        # Return empty frontmatter block on error
        return "---\n---\n"


def format_summary_callout(summary_text: Optional[str]) -> str:
    """
    Format summary text as Obsidian callout with proper syntax and spacing.
    
    Args:
        summary_text: Summary text to format, or None/empty string if no summary
    
    Returns:
        Obsidian callout formatted string, or empty string if no summary
    
    Examples:
        >>> callout = format_summary_callout("This is a summary")
        >>> '[!summary]' in callout
        True
        >>> callout = format_summary_callout(None)
        >>> callout == ''
        True
    """
    if not summary_text or not summary_text.strip():
        return ''
    
    # Clean up summary text
    summary_clean = summary_text.strip()
    
    # Format as Obsidian callout
    # Obsidian callout syntax: > [!summary] Title\n> Content
    callout = f"> [!summary] Summary\n> {summary_clean}\n\n"
    
    return callout


def format_original_content(email_content: str) -> str:
    """
    Format email content under 'Original Content' heading with proper Markdown formatting.
    
    Args:
        email_content: Email body content (already converted to Markdown)
    
    Returns:
        Formatted content section with heading
    
    Examples:
        >>> content = format_original_content("Email body here")
        >>> '# Original Content' in content
        True
        >>> 'Email body here' in content
        True
    """
    if not email_content:
        return "# Original Content\n\n"
    
    # Ensure content ends with newline
    content_clean = email_content.rstrip()
    
    # Format with heading and proper spacing
    formatted = f"# Original Content\n\n{content_clean}\n"
    
    return formatted


def assemble_obsidian_note(
    yaml_data: Dict[str, Any],
    summary_text: Optional[str] = None,
    email_content: str = ""
) -> str:
    """
    Assemble complete Obsidian note by combining YAML frontmatter, summary, and email content.
    
    This is the main function that orchestrates all components with proper spacing.
    
    Args:
        yaml_data: Dictionary with email metadata for YAML frontmatter
        summary_text: Optional summary text to include as Obsidian callout
        email_content: Email body content (already converted to Markdown)
    
    Returns:
        Complete Markdown string ready for writing to disk
    
    Examples:
        >>> yaml = {'subject': 'Test', 'from': 'test@example.com'}
        >>> note = assemble_obsidian_note(yaml, "Summary here", "Email body")
        >>> '---' in note
        True
        >>> 'Summary here' in note
        True
        >>> 'Email body' in note
        True
    """
    try:
        # Validate inputs
        if not isinstance(yaml_data, dict):
            logger.warning(f"yaml_data is not a dict (got {type(yaml_data)}), using empty dict")
            yaml_data = {}
        
        if email_content is None:
            email_content = ""
        
        # 1. Format YAML frontmatter
        frontmatter = format_yaml_frontmatter(yaml_data)
        
        # 2. Format summary callout (if available)
        summary_section = format_summary_callout(summary_text)
        
        # 3. Format original content section
        content_section = format_original_content(email_content)
        
        # 4. Assemble all sections with exactly one blank line between sections
        sections = [frontmatter]
        
        # Add summary if present
        if summary_section:
            sections.append(summary_section)
        
        # Always add content section
        sections.append(content_section)
        
        # Join sections with single newline (sections already include trailing newlines)
        # Remove extra newlines to ensure exactly one blank line between sections
        note_content = "".join(sections)
        
        # Normalize newlines: ensure exactly one blank line between major sections
        # Frontmatter ends with \n---\n, so we want one more \n before next section
        note_content = note_content.replace("\n\n\n", "\n\n")  # Remove triple newlines
        note_content = note_content.replace("\n---\n\n\n", "\n---\n\n")  # Fix after frontmatter
        
        # Ensure final newline
        if not note_content.endswith("\n"):
            note_content = note_content + "\n"
        
        logger.debug(f"Assembled Obsidian note: {len(note_content)} chars, "
                    f"frontmatter: {len(frontmatter)} chars, "
                    f"summary: {len(summary_section)} chars, "
                    f"content: {len(content_section)} chars")
        
        return note_content
        
    except Exception as e:
        logger.error(f"Error assembling Obsidian note: {e}", exc_info=True)
        # Return minimal valid note on error
        return "---\n---\n\n# Original Content\n\n"
