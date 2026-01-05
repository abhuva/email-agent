"""
Email tagging workflow: integrates AI response parsing, tag mapping, and IMAP tagging.
Always ensures AIProcessed tag is applied for idempotency.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from src.tag_mapping import extract_keyword, map_keyword_to_tags
from src.imap_connection import add_tags_to_email
import re


def tag_email_safely(
    imap,
    email_uid,
    ai_response: str,
    tag_mapping: Dict[str, str],
    processed_tag: str = 'AIProcessed'
) -> bool:
    """
    Safely tag an email based on AI response, always appending AIProcessed tag.
    
    Args:
        imap: Active IMAP connection
        email_uid: Email UID (bytes, int, or str)
        ai_response: Raw AI response string (should contain 'urgent', 'neutral', or 'spam')
        tag_mapping: Dict mapping keywords to IMAP tag names (e.g., {'urgent': 'Urgent', 'neutral': 'Neutral'})
        processed_tag: Tag to always append (default: 'AIProcessed')
    
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
        
        # Always append AIProcessed tag
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


def _fetch_email_flags(imap, email_uid) -> List[str]:
    """
    Fetch current flags for an email UID.
    Returns list of flag strings, or empty list on error.
    """
    try:
        if isinstance(email_uid, bytes):
            uid_str = email_uid.decode()
        elif isinstance(email_uid, int):
            uid_str = str(email_uid)
        else:
            uid_str = str(email_uid)
        
        status, data = imap.uid('FETCH', uid_str, '(FLAGS)')
        if status != 'OK' or not data or not data[0]:
            return []
        
        # Parse FLAGS from response: b'1 (FLAGS (\\Seen \\Flagged))'
        flags_str = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
        # Extract flags between parentheses
        flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
        if flags_match:
            flags = flags_match.group(1).split()
            # Remove backslashes and clean up
            flags = [f.strip('\\') for f in flags if f.strip()]
            return flags
        return []
    except Exception as e:
        logging.warning(f"Failed to fetch flags for UID {email_uid}: {e}")
        return []


def process_email_with_ai_tags(
    imap_connection,
    email_uid: Any,
    ai_response: str,
    config: Dict[str, Any],
    email_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Complete email tagging workflow with validation, verification, and audit logging.
    
    Args:
        imap_connection: Active IMAP connection (mailbox should already be selected)
        email_uid: Email UID (bytes, int, or str)
        ai_response: Raw AI response string from LLM
        config: Configuration dict with 'tag_mapping' and 'processed_tag' keys
        email_metadata: Optional dict with email info (subject, sender, etc.) for logging
    
    Returns:
        Dict with keys: success, applied_tags, before_tags, after_tags, keyword, timestamp
    """
    timestamp = datetime.now().isoformat()
    result = {
        'success': False,
        'applied_tags': [],
        'before_tags': [],
        'after_tags': [],
        'keyword': None,
        'timestamp': timestamp
    }
    
    # Input validation
    if not email_uid:
        logging.error(f"Invalid email UID: {email_uid}")
        return result
    
    if not ai_response or not isinstance(ai_response, str):
        logging.error(f"Invalid AI response: {ai_response}")
        return result
    
    if 'tag_mapping' not in config:
        logging.error("Config missing 'tag_mapping' key")
        return result
    
    tag_mapping = config.get('tag_mapping', {})
    processed_tag = config.get('processed_tag', 'AIProcessed')
    
    # Log start of processing
    metadata_str = ""
    if email_metadata:
        subject = email_metadata.get('subject', 'N/A')
        sender = email_metadata.get('sender', 'N/A')
        metadata_str = f" (Subject: {subject[:50]}, From: {sender[:50]})"
    logging.info(f"Processing email UID {email_uid}{metadata_str} at {timestamp}")
    
    try:
        # Fetch flags before tagging
        before_flags = _fetch_email_flags(imap_connection, email_uid)
        result['before_tags'] = before_flags
        logging.debug(f"Email UID {email_uid} flags before: {before_flags}")
        
        # Extract keyword and determine tags to apply
        keyword = extract_keyword(ai_response)
        result['keyword'] = keyword
        tags_to_apply = map_keyword_to_tags(keyword, tag_mapping)
        if not tags_to_apply:
            tags_to_apply = [tag_mapping.get('neutral', 'Neutral')]
        tags_to_apply.append(processed_tag)
        result['applied_tags'] = tags_to_apply
        
        # Apply tags
        success = add_tags_to_email(imap_connection, email_uid, tags_to_apply)
        result['success'] = success
        
        if success:
            # Verify by fetching flags after
            after_flags = _fetch_email_flags(imap_connection, email_uid)
            result['after_tags'] = after_flags
            logging.debug(f"Email UID {email_uid} flags after: {after_flags}")
            
            # Verify AIProcessed tag was applied
            if processed_tag not in after_flags:
                logging.warning(f"AIProcessed tag not found in flags after tagging for UID {email_uid}")
            
            logging.info(
                f"Email UID {email_uid} tagged successfully. "
                f"Keyword: {keyword}, Applied: {tags_to_apply}, "
                f"Before: {before_flags}, After: {after_flags}"
            )
        else:
            logging.error(f"Failed to tag email UID {email_uid}")
            result['after_tags'] = before_flags  # No change on failure
        
    except Exception as e:
        logging.error(f"Error processing email UID {email_uid}: {e}", exc_info=True)
        result['success'] = False
    
    return result
