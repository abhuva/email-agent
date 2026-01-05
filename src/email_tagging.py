"""
Email tagging workflow: integrates AI response parsing, tag mapping, and IMAP tagging.
Always ensures [AI-Processed] tag is applied for idempotency.
"""

import logging
from typing import Dict, List, Any
from src.tag_mapping import extract_keyword, map_keyword_to_tags
from src.imap_connection import add_tags_to_email


def tag_email_safely(
    imap,
    email_uid,
    ai_response: str,
    tag_mapping: Dict[str, str],
    processed_tag: str = '[AI-Processed]'
) -> bool:
    """
    Safely tag an email based on AI response, always appending [AI-Processed] tag.
    
    Args:
        imap: Active IMAP connection
        email_uid: Email UID (bytes, int, or str)
        ai_response: Raw AI response string (should contain 'urgent', 'neutral', or 'spam')
        tag_mapping: Dict mapping keywords to IMAP tag names (e.g., {'urgent': 'Urgent', 'neutral': 'Neutral'})
        processed_tag: Tag to always append (default: '[AI-Processed]')
    
    Returns:
        True if tagging succeeded, False otherwise
    """
    try:
        # Extract keyword from AI response (guaranteed to return 'urgent', 'neutral', or 'spam')
        keyword = extract_keyword(ai_response)
        logging.debug(f"Extracted keyword from AI response: {keyword}")
        
        # Map keyword to IMAP tags
        tags = map_keyword_to_tags(keyword, tag_mapping)
        if not tags:
            # Fallback: if mapping failed, use neutral
            tags = [tag_mapping.get('neutral', 'Neutral')]
            logging.warning(f"Tag mapping failed for keyword '{keyword}', using neutral fallback")
        
        # Always append [AI-Processed] tag
        tags.append(processed_tag)
        
        logging.info(f"Tagging email UID {email_uid} with tags: {tags}")
        
        # Apply tags via IMAP
        success = add_tags_to_email(imap, email_uid, tags)
        
        if success:
            logging.info(f"Successfully tagged email UID {email_uid} with {tags}")
        else:
            logging.error(f"Failed to tag email UID {email_uid}")
        
        return success
        
    except Exception as e:
        logging.error(f"Error in tag_email_safely for UID {email_uid}: {e}")
        return False
