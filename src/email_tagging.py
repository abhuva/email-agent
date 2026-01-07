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

# Module logger
logger = logging.getLogger(__name__)


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
        logger.debug(f"Extracted keyword from AI response: {keyword}")
        
        # Map keyword to IMAP tags
        tags = map_keyword_to_tags(keyword, tag_mapping)
        if not tags:
            # Fallback: if mapping failed, use neutral
            tags = [tag_mapping.get('neutral', 'Neutral')]
            logger.warning(f"Tag mapping failed for keyword '{keyword}', using neutral fallback")
        
        # Always append AIProcessed tag
        tags.append(processed_tag)
        
        logger.info(f"Tagging email UID {email_uid} with tags: {tags}")
        
        # Apply tags via IMAP
        logger.debug(f"Calling add_tags_to_email for UID {email_uid} with tags {tags}")
        success = add_tags_to_email(imap, email_uid, tags)
        logger.debug(f"add_tags_to_email returned: {success}")
        
        if success:
            logger.info(f"Successfully tagged email UID {email_uid} with {tags}")
        else:
            logger.error(f"Failed to tag email UID {email_uid} - add_tags_to_email returned False")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in tag_email_safely for UID {email_uid}: {e}", exc_info=True)
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
        
        logger.debug(f"Fetching flags for UID {uid_str}")
        status, data = imap.uid('FETCH', uid_str, '(FLAGS)')
        logger.debug(f"FETCH FLAGS response: status={status}, data={data}")
        
        if status != 'OK' or not data or not data[0]:
            logger.warning(f"Failed to fetch flags for UID {uid_str}: status={status}, data={data}")
            return []
        
        # Parse FLAGS from response: b'1 (FLAGS (\\Seen \\Flagged))'
        flags_str = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
        logger.debug(f"Raw FLAGS response string: {flags_str}")
        
        # Extract flags between parentheses
        flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
        if flags_match:
            flags = flags_match.group(1).split()
            # Remove backslashes and clean up
            flags = [f.strip('\\') for f in flags if f.strip()]
            logger.debug(f"Parsed flags for UID {uid_str}: {flags}")
            return flags
        else:
            logger.warning(f"Could not parse FLAGS from response: {flags_str}")
        return []
    except Exception as e:
        logger.warning(f"Failed to fetch flags for UID {email_uid}: {e}", exc_info=True)
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
        logger.error(f"Invalid email UID: {email_uid}")
        return result
    
    if not ai_response or not isinstance(ai_response, str):
        logger.error(f"Invalid AI response: {ai_response}")
        return result
    
    if 'tag_mapping' not in config:
        logger.error("Config missing 'tag_mapping' key")
        return result
    
    tag_mapping = config.get('tag_mapping', {})
    processed_tag = config.get('processed_tag', 'AIProcessed')
    
    # Log start of processing
    metadata_str = ""
    if email_metadata:
        subject = email_metadata.get('subject', 'N/A')
        sender = email_metadata.get('sender', 'N/A')
        metadata_str = f" (Subject: {subject[:50]}, From: {sender[:50]})"
    logger.info(f"Processing email UID {email_uid}{metadata_str} at {timestamp}")
    
    try:
        # Fetch flags before tagging
        before_flags = _fetch_email_flags(imap_connection, email_uid)
        result['before_tags'] = before_flags
        logger.debug(f"Email UID {email_uid} flags before: {before_flags}")
        
        # Extract keyword and determine tags to apply
        keyword = extract_keyword(ai_response)
        result['keyword'] = keyword
        tags_to_apply = map_keyword_to_tags(keyword, tag_mapping)
        if not tags_to_apply:
            tags_to_apply = [tag_mapping.get('neutral', 'Neutral')]
        tags_to_apply.append(processed_tag)
        result['applied_tags'] = tags_to_apply
        
        # Apply tags
        logger.info(f"Calling add_tags_to_email for UID {email_uid} with tags: {tags_to_apply}")
        success = add_tags_to_email(imap_connection, email_uid, tags_to_apply)
        result['success'] = success
        logger.info(f"add_tags_to_email returned success={success} for UID {email_uid}")
        
        if success:
            # Verify by fetching flags after - wait a moment for IMAP server to process
            import time
            time.sleep(0.5)  # Brief delay to ensure IMAP server has processed the STORE command
            
            logger.debug(f"Fetching flags after tagging for UID {email_uid}")
            after_flags = _fetch_email_flags(imap_connection, email_uid)
            result['after_tags'] = after_flags
            logger.info(f"Email UID {email_uid} flags after tagging: {after_flags}")
            
            # Verify all expected tags were applied
            missing_tags = []
            for expected_tag in tags_to_apply:
                if expected_tag not in after_flags:
                    missing_tags.append(expected_tag)
            
            if missing_tags:
                logger.error(
                    f"VERIFICATION FAILED: Tags not found after tagging for UID {email_uid}. "
                    f"Expected: {tags_to_apply}, Missing: {missing_tags}, "
                    f"Actual flags: {after_flags}"
                )
                result['success'] = False  # Mark as failed if verification fails
            else:
                logger.info(
                    f"VERIFICATION SUCCESS: All tags confirmed for UID {email_uid}. "
                    f"Expected: {tags_to_apply}, Found: {[tag for tag in tags_to_apply if tag in after_flags]}"
                )
            
            # Specifically verify AIProcessed tag
            if processed_tag not in after_flags:
                logger.error(
                    f"WARNING: AIProcessed tag not found in flags after tagging for UID {email_uid}. "
                    f"Expected: {processed_tag}, Got: {after_flags}"
                )
            else:
                logger.info(f"Verified: {processed_tag} tag is present in flags for UID {email_uid}")
            
            logger.info(
                f"Email UID {email_uid} tagging result. "
                f"Keyword: {keyword}, Applied: {tags_to_apply}, "
                f"Before: {before_flags}, After: {after_flags}, "
                f"Verification: {'PASSED' if not missing_tags else 'FAILED'}"
            )
        else:
            logger.error(f"Failed to tag email UID {email_uid}")
            result['after_tags'] = before_flags  # No change on failure
        
    except Exception as e:
        logger.error(f"Error processing email UID {email_uid}: {e}", exc_info=True)
        result['success'] = False
    
    return result
