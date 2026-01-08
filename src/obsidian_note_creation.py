"""
Obsidian note creation and email tagging workflow.

This module provides functions to:
- Generate complete Obsidian note content from email data
- Write notes to disk
- Tag emails with success/failure tags
- Orchestrate the complete note creation workflow
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone

from src.obsidian_note_assembly import assemble_obsidian_note
from src.yaml_frontmatter import extract_email_metadata
from src.email_to_markdown import convert_email_to_markdown
from src.obsidian_utils import (
    generate_unique_filename,
    safe_write_file,
    FileSystemError,
    InvalidPathError,
    WritePermissionError,
    FileWriteError
)

logger = logging.getLogger(__name__)

# IMAP tag names for note creation status
# Note: No hyphens or special characters - IMAP servers may reject them
OBSIDIAN_NOTE_CREATED_TAG = 'ObsidianNoteCreated'
NOTE_CREATION_FAILED_TAG = 'NoteCreationFailed'


def generate_note_content(
    email: Dict[str, Any],
    summary_result: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate complete Obsidian note content from email data.
    
    This function:
    1. Extracts email metadata for YAML frontmatter
    2. Converts email body to Markdown
    3. Gets summary text if available
    4. Assembles the complete note
    
    Args:
        email: Email dict with subject, sender, body, date, etc.
        summary_result: Optional summary result dict from Task 7
    
    Returns:
        Complete Markdown note content ready for writing
    
    Examples:
        >>> email = {'subject': 'Test', 'sender': 'test@example.com', 'body': 'Content'}
        >>> note = generate_note_content(email)
        >>> '---' in note
        True
        >>> 'Content' in note
        True
    """
    # Log email details for debugging
    email_uid = email.get('id')
    uid_str = email_uid.decode() if isinstance(email_uid, bytes) else str(email_uid)
    email_subject = email.get('subject', 'N/A')
    email_sender = email.get('sender', 'N/A')
    logger.debug(f"generate_note_content: UID {uid_str}, Subject: {email_subject[:50]}, From: {email_sender[:50]}")
    
    try:
        # Extract metadata for YAML frontmatter
        metadata = extract_email_metadata(email)
        
        # Convert email body to Markdown
        email_body = email.get('body', '')
        content_type = email.get('content_type', 'text/plain')
        markdown_body = convert_email_to_markdown(email_body, content_type=content_type)
        
        # Get summary text if available
        summary_text = None
        if summary_result and summary_result.get('success'):
            summary_text = summary_result.get('summary', '')
            if not summary_text or not summary_text.strip():
                summary_text = None
        
        # Assemble the complete note
        note_content = assemble_obsidian_note(
            yaml_data=metadata,
            summary_text=summary_text,
            email_content=markdown_body
        )
        
        logger.debug(f"Generated note content: {len(note_content)} chars")
        return note_content
        
    except Exception as e:
        logger.error(f"Error generating note content: {e}", exc_info=True)
        # Return minimal valid note on error
        return "---\n---\n\n# Original Content\n\n"


def write_obsidian_note(
    note_content: str,
    email_subject: str,
    vault_path: str,
    timestamp: Optional[datetime] = None,
    overwrite: bool = False
) -> str:
    """
    Write Obsidian note to disk with proper filename and path resolution.
    
    Args:
        note_content: Complete Markdown note content
        email_subject: Email subject for filename generation
        vault_path: Base path to Obsidian vault directory
        timestamp: Optional timestamp for filename (uses current time if None)
        overwrite: If True, overwrite existing file. If False, find unique path.
    
    Returns:
        Full path to the created note file
    
    Raises:
        InvalidPathError: If vault path is invalid
        WritePermissionError: If write permission is denied
        FileWriteError: If file writing fails
    
    Examples:
        >>> note = "---\n---\n\n# Original Content\n\n"
        >>> path = write_obsidian_note(note, "Test Email", "/path/to/vault")
        >>> path.endswith('.md')
        True
    """
    # CRITICAL: Log email subject to verify content consistency
    logger.debug(f"write_obsidian_note: Subject: {email_subject[:50]}")
    
    try:
        # Validate vault path exists
        vault_dir = Path(vault_path)
        if not vault_dir.exists():
            raise InvalidPathError(f"Obsidian vault path does not exist: {vault_path}")
        
        if not vault_dir.is_dir():
            raise InvalidPathError(f"Obsidian vault path is not a directory: {vault_path}")
        
        # Generate unique filename
        filename = generate_unique_filename(
            subject=email_subject,
            base_path=str(vault_dir),
            timestamp=timestamp
        )
        
        # Write file using safe_write_file
        actual_path = safe_write_file(
            content=note_content,
            file_path=filename,
            overwrite=overwrite  # Overwrite if force-reprocess, otherwise find unique path
        )
        
        logger.info(f"Successfully wrote Obsidian note: {actual_path}")
        return actual_path
        
    except (InvalidPathError, WritePermissionError, FileWriteError):
        # Re-raise these specific errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error writing Obsidian note: {e}", exc_info=True)
        raise FileWriteError(f"Failed to write Obsidian note: {e}") from e


def tag_email_note_created(
    imap,
    email_uid: Any,
    note_path: Optional[str] = None
) -> bool:
    """
    Tag email with Obsidian-Note-Created tag to mark successful note creation.
    
    Args:
        imap: Active IMAP connection
        email_uid: Email UID (bytes, int, or str)
        note_path: Optional note file path for logging
    
    Returns:
        True if tagging succeeded, False otherwise
    
    Examples:
        >>> tag_email_note_created(imap, b'123', '/path/to/note.md')
        True
    """
    try:
        from src.imap_connection import add_tags_to_email
        from src.email_tagging import _fetch_email_flags
        import time
        
        # Fetch flags before tagging for verification
        before_flags = _fetch_email_flags(imap, email_uid)
        logger.debug(f"Email UID {email_uid} flags before ObsidianNoteCreated tagging: {before_flags}")
        
        tags = [OBSIDIAN_NOTE_CREATED_TAG]
        success = add_tags_to_email(imap, email_uid, tags)
        
        if success:
            # Verify by re-fetching flags after a brief delay
            time.sleep(0.5)  # Brief delay to ensure IMAP server has processed the STORE command
            
            after_flags = _fetch_email_flags(imap, email_uid)
            logger.info(f"Email UID {email_uid} flags after ObsidianNoteCreated tagging: {after_flags}")
            
            # Verify the tag was actually applied
            if OBSIDIAN_NOTE_CREATED_TAG not in after_flags:
                logger.error(
                    f"VERIFICATION FAILED: ObsidianNoteCreated tag not found after tagging for UID {email_uid}. "
                    f"Expected: {OBSIDIAN_NOTE_CREATED_TAG}, Got: {after_flags}, "
                    f"Before: {before_flags}"
                )
                return False  # Mark as failed if verification fails
            else:
                logger.info(
                    f"VERIFICATION SUCCESS: ObsidianNoteCreated tag confirmed for UID {email_uid}. "
                    f"Before: {before_flags}, After: {after_flags}"
                )
            
            logger.info(f"Tagged email UID {email_uid} with {OBSIDIAN_NOTE_CREATED_TAG}" + 
                       (f" (note: {note_path})" if note_path else ""))
        else:
            logger.warning(f"Failed to tag email UID {email_uid} with {OBSIDIAN_NOTE_CREATED_TAG}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error tagging email UID {email_uid} with {OBSIDIAN_NOTE_CREATED_TAG}: {e}", exc_info=True)
        return False


def tag_email_note_failed(
    imap,
    email_uid: Any,
    error_message: Optional[str] = None
) -> bool:
    """
    Tag email with NoteCreationFailed tag to mark failed note creation.
    
    Args:
        imap: Active IMAP connection
        email_uid: Email UID (bytes, int, or str)
        error_message: Optional error message for logging
    
    Returns:
        True if tagging succeeded, False otherwise
    
    Examples:
        >>> tag_email_note_failed(imap, b'123', 'File write error')
        True
    """
    try:
        from src.imap_connection import add_tags_to_email
        from src.email_tagging import _fetch_email_flags
        import time
        
        # Fetch flags before tagging for verification
        before_flags = _fetch_email_flags(imap, email_uid)
        logger.debug(f"Email UID {email_uid} flags before NoteCreationFailed tagging: {before_flags}")
        
        tags = [NOTE_CREATION_FAILED_TAG]
        success = add_tags_to_email(imap, email_uid, tags)
        
        if success:
            # Verify by re-fetching flags after a brief delay
            time.sleep(0.5)  # Brief delay to ensure IMAP server has processed the STORE command
            
            after_flags = _fetch_email_flags(imap, email_uid)
            logger.info(f"Email UID {email_uid} flags after NoteCreationFailed tagging: {after_flags}")
            
            # Verify the tag was actually applied
            if NOTE_CREATION_FAILED_TAG not in after_flags:
                logger.error(
                    f"VERIFICATION FAILED: NoteCreationFailed tag not found after tagging for UID {email_uid}. "
                    f"Expected: {NOTE_CREATION_FAILED_TAG}, Got: {after_flags}, "
                    f"Before: {before_flags}"
                )
                return False  # Mark as failed if verification fails
            else:
                logger.info(
                    f"VERIFICATION SUCCESS: NoteCreationFailed tag confirmed for UID {email_uid}. "
                    f"Before: {before_flags}, After: {after_flags}"
                )
            
            logger.warning(f"Tagged email UID {email_uid} with {NOTE_CREATION_FAILED_TAG}" +
                          (f" (error: {error_message})" if error_message else ""))
        else:
            logger.error(f"Failed to tag email UID {email_uid} with {NOTE_CREATION_FAILED_TAG}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error tagging email UID {email_uid} with {NOTE_CREATION_FAILED_TAG}: {e}", exc_info=True)
        return False


def create_obsidian_note_for_email(
    email: Dict[str, Any],
    config,
    summary_result: Optional[Dict[str, Any]] = None,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Complete workflow to create an Obsidian note for an email.
    
    Args:
        email: Email dictionary with 'id', 'subject', 'sender', 'body', 'date', etc.
        config: ConfigManager instance
        summary_result: Optional summary result dict from generate_email_summary
    
    Returns:
        Dict with 'success', 'note_path', 'error' keys
    """
    # Log email details for debugging
    email_uid = email.get('id')
    uid_str = email_uid.decode() if isinstance(email_uid, bytes) else str(email_uid)
    email_subject = email.get('subject', 'N/A')
    email_sender = email.get('sender', 'N/A')
    logger.info(f"create_obsidian_note_for_email: UID {uid_str}, Subject: {email_subject[:60]}, From: {email_sender[:50]}")
    
    try:
        # Get vault path from config
        vault_path = getattr(config, 'obsidian_vault_path', None)
        if not vault_path:
            error_msg = "obsidian_vault_path not configured"
            logger.error(f"Cannot create note for email UID {uid_str}: {error_msg}")
            return {
                'success': False,
                'note_path': None,
                'error': error_msg
            }
        
        # Generate note content
        logger.debug(f"Generating note content for email UID {uid_str}")
        note_content = generate_note_content(email, summary_result)
        
        # Write note to disk
        logger.info(f"Writing Obsidian note for email UID {uid_str} to {vault_path}")
        note_path = write_obsidian_note(
            note_content=note_content,
            email_subject=email_subject,
            vault_path=vault_path,
            overwrite=overwrite
        )
        
        logger.info(f"Successfully created Obsidian note for email UID {uid_str}: {note_path}")
        return {
            'success': True,
            'note_path': note_path,
            'error': None
        }
        
    except InvalidPathError as e:
        error_msg = f"Invalid vault path: {e}"
        logger.error(f"Note creation failed for email UID {uid_str}: {error_msg}")
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
    except WritePermissionError as e:
        error_msg = f"Write permission denied: {e}"
        logger.error(f"Note creation failed for email UID {uid_str}: {error_msg}")
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
    except FileWriteError as e:
        error_msg = f"File write error: {e}"
        logger.error(f"Note creation failed for email UID {uid_str}: {error_msg}")
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"Note creation failed for email UID {uid_str}: {error_msg}", exc_info=True)
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
