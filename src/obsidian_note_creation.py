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
OBSIDIAN_NOTE_CREATED_TAG = 'Obsidian-Note-Created'
NOTE_CREATION_FAILED_TAG = 'Note-Creation-Failed'


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
    timestamp: Optional[datetime] = None
) -> str:
    """
    Write Obsidian note to disk with proper filename and path resolution.
    
    Args:
        note_content: Complete Markdown note content
        email_subject: Email subject for filename generation
        vault_path: Base path to Obsidian vault directory
        timestamp: Optional timestamp for filename (uses current time if None)
    
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
            overwrite=False  # Don't overwrite, find unique path if exists
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
        
        tags = [OBSIDIAN_NOTE_CREATED_TAG]
        success = add_tags_to_email(imap, email_uid, tags)
        
        if success:
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
    Tag email with Note-Creation-Failed tag to mark failed note creation.
    
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
        
        tags = [NOTE_CREATION_FAILED_TAG]
        success = add_tags_to_email(imap, email_uid, tags)
        
        if success:
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
    summary_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Complete workflow to create Obsidian note for an email.
    
    This function orchestrates:
    1. Note content generation
    2. File writing
    3. Error handling
    
    Args:
        email: Email dict with all required fields
        config: ConfigManager instance
        summary_result: Optional summary result from Task 7
    
    Returns:
        Dict with keys:
            - success: bool - Whether note creation succeeded
            - note_path: Optional[str] - Path to created note file
            - error: Optional[str] - Error message if failed
    
    Examples:
        >>> email = {'subject': 'Test', 'sender': 'test@example.com', 'body': 'Content'}
        >>> result = create_obsidian_note_for_email(email, config)
        >>> 'success' in result
        True
    """
    email_uid = email.get('id', 'unknown')
    email_subject = email.get('subject', 'Untitled')
    
    try:
        # Get vault path from config
        vault_path = getattr(config, 'obsidian_vault_path', None)
        if not vault_path:
            error_msg = "obsidian_vault_path not configured"
            logger.error(f"Cannot create note for email UID {email_uid}: {error_msg}")
            return {
                'success': False,
                'note_path': None,
                'error': error_msg
            }
        
        # Generate note content
        logger.debug(f"Generating note content for email UID {email_uid}")
        note_content = generate_note_content(email, summary_result)
        
        # Write note to disk
        logger.info(f"Writing Obsidian note for email UID {email_uid} to {vault_path}")
        note_path = write_obsidian_note(
            note_content=note_content,
            email_subject=email_subject,
            vault_path=vault_path
        )
        
        logger.info(f"Successfully created Obsidian note for email UID {email_uid}: {note_path}")
        return {
            'success': True,
            'note_path': note_path,
            'error': None
        }
        
    except InvalidPathError as e:
        error_msg = f"Invalid vault path: {e}"
        logger.error(f"Note creation failed for email UID {email_uid}: {error_msg}")
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
    except WritePermissionError as e:
        error_msg = f"Write permission denied: {e}"
        logger.error(f"Note creation failed for email UID {email_uid}: {error_msg}")
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
    except FileWriteError as e:
        error_msg = f"File write error: {e}"
        logger.error(f"Note creation failed for email UID {email_uid}: {error_msg}")
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"Note creation failed for email UID {email_uid}: {error_msg}", exc_info=True)
        return {
            'success': False,
            'note_path': None,
            'error': error_msg
        }
