"""
Conditional summarization logic module.

This module provides functions to:
- Check if an email should be summarized based on its tags
- Load summarization prompts from configuration
- Determine summarization readiness for email processing
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


def get_summarization_tags() -> List[str]:
    """
    Safely access and validate the summarization_tags configuration from V3 settings.
    
    Returns:
        List of tag strings that trigger summarization, or empty list if invalid/missing
    
    Examples:
        >>> tags = get_summarization_tags()
        >>> 'important' in tags
        True
    """
    try:
        from src.settings import settings
        
        # Get summarization tags from V3 config
        try:
            processing_config = settings._config.processing
            tags = getattr(processing_config, 'summarization_tags', None)
        except Exception:
            tags = None
        
        # Check if tags exist and is a list
        if tags is None:
            logger.debug("summarization_tags not configured, returning empty list")
            return []
        
        if not isinstance(tags, list):
            logger.warning(f"summarization_tags is not a list (got {type(tags)}), returning empty list")
            return []
        
        # Validate all items are strings
        valid_tags = []
        for tag in tags:
            if isinstance(tag, str) and tag.strip():
                valid_tags.append(tag.strip())
            else:
                logger.warning(f"Invalid tag in summarization_tags: {tag} (skipping)")
        
        if not valid_tags:
            logger.debug("summarization_tags is empty or contains no valid strings, returning empty list")
            return []
        
        return valid_tags
        
    except Exception as e:
        logger.warning(f"Error accessing summarization_tags config: {e}, returning empty list")
        return []


def should_summarize_email(email_tags: List[str], summarization_tags: List[str]) -> bool:
    """
    Check if an email's tags intersect with summarization_tags.
    
    Args:
        email_tags: List of tags associated with the email
        summarization_tags: List of tags that trigger summarization
    
    Returns:
        True if email should be summarized, False otherwise
    
    Examples:
        >>> should_summarize_email(['Urgent', 'Important'], ['Urgent'])
        True
        >>> should_summarize_email(['Neutral'], ['Urgent'])
        False
        >>> should_summarize_email([], ['Urgent'])
        False
    """
    if not email_tags:
        return False
    
    if not summarization_tags:
        return False
    
    # Use set intersection to check for matches
    email_tag_set = set(str(tag).strip() for tag in email_tags if tag)
    summarization_tag_set = set(str(tag).strip() for tag in summarization_tags if tag)
    
    has_match = bool(email_tag_set & summarization_tag_set)
    
    if has_match:
        matching_tags = email_tag_set & summarization_tag_set
        logger.debug(f"Email tags {email_tags} match summarization tags {summarization_tags} (matches: {matching_tags})")
    
    return has_match


def load_summarization_prompt(prompt_path: Optional[str]) -> Optional[str]:
    """
    Load the summarization prompt from the configured file path.
    
    Args:
        prompt_path: Path to the summarization prompt file
    
    Returns:
        Prompt content as string, or None if loading fails
    
    Examples:
        >>> prompt = load_summarization_prompt('config/summarization_prompt.md')
        >>> prompt is not None
        True
    """
    if not prompt_path:
        logger.debug("summarization_prompt_path not configured")
        return None
    
    try:
        prompt_file = Path(prompt_path)
        
        # Check if file exists
        if not prompt_file.exists():
            logger.warning(f"Summarization prompt file not found: {prompt_path}")
            return None
        
        # Check if it's a file (not a directory)
        if not prompt_file.is_file():
            logger.warning(f"Summarization prompt path is not a file: {prompt_path}")
            return None
        
        # Read the file
        prompt_content = prompt_file.read_text(encoding='utf-8')
        
        # Validate content is non-empty
        if not prompt_content or not prompt_content.strip():
            logger.warning(f"Summarization prompt file is empty: {prompt_path}")
            return None
        
        logger.debug(f"Successfully loaded summarization prompt from {prompt_path} ({len(prompt_content)} chars)")
        return prompt_content.strip()
        
    except FileNotFoundError:
        logger.warning(f"Summarization prompt file not found: {prompt_path}")
        return None
    except PermissionError:
        logger.error(f"Permission denied reading summarization prompt file: {prompt_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading summarization prompt from {prompt_path}: {e}", exc_info=True)
        return None


def check_summarization_required(
    email: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determine if an email should be summarized and load the prompt if needed.
    
    This is the main function that orchestrates tag checking and prompt loading.
    Uses V3 settings facade directly.
    
    Args:
        email: Email dict with 'tags' key (list of tag strings)
    
    Returns:
        Dict with keys:
            - summarize: bool - Whether summarization should proceed
            - prompt: Optional[str] - Loaded prompt if summarize is True, None otherwise
            - reason: Optional[str] - Reason if summarize is False (for logging)
    
    Examples:
        >>> email = {'tags': ['important']}
        >>> result = check_summarization_required(email)
        >>> result['summarize']
        True
    """
    try:
        from src.settings import settings
        
        # Get summarization tags from V3 settings
        summarization_tags = get_summarization_tags()
        
        if not summarization_tags:
            logger.debug("No summarization tags configured, skipping summarization")
            return {
                'summarize': False,
                'prompt': None,
                'reason': 'no_summarization_tags_configured'
            }
        
        # Get email tags
        email_tags = email.get('tags', [])
        if not isinstance(email_tags, list):
            email_tags = []
        
        # Check if email should be summarized
        if not should_summarize_email(email_tags, summarization_tags):
            logger.debug(f"Email tags {email_tags} do not match summarization tags {summarization_tags}")
            return {
                'summarize': False,
                'prompt': None,
                'reason': 'tags_do_not_match'
            }
        
        # Email should be summarized - load the prompt from V3 settings
        try:
            paths_config = settings._config.paths
            prompt_path = getattr(paths_config, 'summarization_prompt_path', None)
        except Exception:
            prompt_path = None
        
        prompt = load_summarization_prompt(prompt_path)
        
        if not prompt:
            logger.warning(f"Summarization required but prompt failed to load (path: {prompt_path})")
            return {
                'summarize': False,
                'prompt': None,
                'reason': 'prompt_load_failed'
            }
        
        # Success - summarization should proceed
        logger.info(f"Summarization required for email (tags: {email_tags}, matching: {set(email_tags) & set(summarization_tags)})")
        return {
            'summarize': True,
            'prompt': prompt,
            'reason': None
        }
        
    except Exception as e:
        # Graceful degradation - never raise exceptions
        logger.error(f"Unexpected error in check_summarization_required: {e}", exc_info=True)
        return {
            'summarize': False,
            'prompt': None,
            'reason': f'unexpected_error: {str(e)}'
        }
