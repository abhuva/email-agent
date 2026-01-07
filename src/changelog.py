"""
Changelog/audit log functionality for email processing.

This module provides functions to:
- Initialize changelog files with Markdown table headers
- Format email data as table rows
- Generate visual run separators
- Update changelog files with processed email information
- Track execution runs and maintain audit trail
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def initialize_changelog(path: str) -> str:
    """
    Initialize changelog file with Markdown table header if it doesn't exist,
    or read existing file content safely.
    
    Args:
        path: Path to the changelog file
        
    Returns:
        File content as string (existing content or newly created header)
        
    Raises:
        OSError: If file operations fail
        
    Example:
        >>> content = initialize_changelog('logs/email_changelog.md')
        >>> '# Email Processing Changelog' in content
        True
        >>> '| Timestamp |' in content
        True
    """
    changelog_path = Path(path)
    
    # Ensure parent directory exists
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not changelog_path.exists():
        # Create new changelog file with header
        logger.info(f"Creating new changelog file: {changelog_path}")
        header = """# Email Processing Changelog

| Timestamp | Email Account | Subject | From | Filename |
|---| ---|---| ---|---|
"""
        try:
            with open(changelog_path, 'w', encoding='utf-8') as f:
                f.write(header)
            logger.debug(f"Created changelog file with header: {changelog_path}")
            return header
        except OSError as e:
            logger.error(f"Failed to create changelog file {changelog_path}: {e}")
            raise
    else:
        # Read existing file content
        logger.debug(f"Reading existing changelog file: {changelog_path}")
        try:
            with open(changelog_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"Read {len(content)} characters from changelog file")
            return content
        except OSError as e:
            logger.error(f"Failed to read changelog file {changelog_path}: {e}")
            raise


def format_email_row(email_data: Dict[str, Any]) -> str:
    """
    Format processed email data as a Markdown table row with current timestamp.
    
    Args:
        email_data: Dictionary with keys:
            - email_account: Email account/address (str)
            - subject: Email subject (str)
            - from_addr: Sender address (str)
            - filename: Generated note filename (str)
    
    Returns:
        Pipe-formatted table row string
        
    Example:
        >>> data = {
        ...     'email_account': 'user@example.com',
        ...     'subject': 'Test Email',
        ...     'from_addr': 'sender@example.com',
        ...     'filename': '2026-01-06-120000 - Test Email.md'
        ... }
        >>> row = format_email_row(data)
        >>> '|' in row
        True
        >>> 'user@example.com' in row
        True
    """
    # Get current UTC timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Extract fields with safe defaults
    email_account = email_data.get('email_account', '')
    subject = email_data.get('subject', '')
    from_addr = email_data.get('from_addr', '')
    filename = email_data.get('filename', '')
    
    # Escape Markdown special characters in table cells
    # Escape pipe (|) and backslash (\) characters
    def escape_markdown(text: str) -> str:
        if not text:
            return ''
        # Replace pipe with HTML entity or escaped version
        text = text.replace('\\', '\\\\')  # Escape backslashes first
        text = text.replace('|', '\\|')     # Escape pipes
        return text
    
    email_account_escaped = escape_markdown(str(email_account))
    subject_escaped = escape_markdown(str(subject))
    from_addr_escaped = escape_markdown(str(from_addr))
    filename_escaped = escape_markdown(str(filename))
    
    # Format as table row
    row = f"| {timestamp} | {email_account_escaped} | {subject_escaped} | {from_addr_escaped} | {filename_escaped} |"
    
    return row


def generate_run_separator(run_count: int, run_timestamp: Optional[datetime] = None) -> str:
    """
    Generate visual separator between execution runs using Markdown horizontal rule.
    
    Args:
        run_count: Sequential run number (1, 2, 3, ...)
        run_timestamp: Optional timestamp for the run (defaults to current UTC time)
    
    Returns:
        Markdown string with separator and run metadata
        
    Example:
        >>> separator = generate_run_separator(1)
        >>> '---' in separator
        True
        >>> 'Run #1' in separator
        True
    """
    if run_timestamp is None:
        run_timestamp = datetime.now(timezone.utc)
    
    # Format timestamp as YYYY-MM-DD HH:MM UTC
    timestamp_str = run_timestamp.strftime('%Y-%m-%d %H:%M UTC')
    
    separator = f"""

---

**Run #{run_count} - {timestamp_str}**

"""
    return separator


def get_run_count(changelog_content: str) -> int:
    """
    Count the number of runs in existing changelog by counting '**Run #' occurrences.
    
    Args:
        changelog_content: Current changelog file content
    
    Returns:
        Next run number (current_count + 1)
        
    Example:
        >>> content = '**Run #1 - 2026-01-06 12:00 UTC**'
        >>> get_run_count(content)
        2
    """
    # Count occurrences of '**Run #' pattern
    run_count = changelog_content.count('**Run #')
    # Return next run number
    return run_count + 1


def update_changelog(
    path: str,
    email_list: List[Dict[str, Any]],
    run_count: Optional[int] = None
) -> bool:
    """
    Update changelog file with new email rows and run separator.
    
    This function:
    1. Initializes or reads existing changelog
    2. Generates run separator
    3. Formats each email as table row
    4. Appends new content to file
    5. Uses atomic write (temp file + rename) for reliability
    
    Args:
        path: Path to changelog file
        email_list: List of email data dictionaries (each with email_account, subject, from_addr, filename)
        run_count: Optional run number (auto-calculated if not provided)
    
    Returns:
        True if update succeeded, False otherwise
        
    Example:
        >>> emails = [{
        ...     'email_account': 'user@example.com',
        ...     'subject': 'Test',
        ...     'from_addr': 'sender@example.com',
        ...     'filename': 'test.md'
        ... }]
        >>> update_changelog('logs/changelog.md', emails, run_count=1)
        True
    """
    if not email_list:
        logger.debug("No emails to add to changelog, skipping update")
        return True
    
    try:
        # Initialize or read existing changelog
        changelog_content = initialize_changelog(path)
        
        # Get run count if not provided
        if run_count is None:
            run_count = get_run_count(changelog_content)
        
        # Generate run separator
        run_timestamp = datetime.now(timezone.utc)
        separator = generate_run_separator(run_count, run_timestamp)
        
        # Format each email as table row
        rows = []
        for email_data in email_list:
            row = format_email_row(email_data)
            rows.append(row)
        
        # Combine separator and rows
        new_content = separator + '\n'.join(rows) + '\n'
        
        # Append to existing content
        updated_content = changelog_content + new_content
        
        # Atomic write: write to temp file, then rename
        changelog_path = Path(path)
        temp_file = changelog_path.with_suffix('.tmp')
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            # Atomic rename (works on Unix and Windows)
            temp_file.replace(changelog_path)
            
            logger.info(f"Updated changelog with {len(email_list)} email(s) for run #{run_count}")
            return True
            
        except OSError as e:
            logger.error(f"Failed to write changelog file {path}: {e}")
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False
            
    except Exception as e:
        logger.error(f"Error updating changelog {path}: {e}", exc_info=True)
        return False
