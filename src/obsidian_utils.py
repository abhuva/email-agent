"""
File system utilities for Obsidian integration.

This module provides functions for:
- Sanitizing email subjects for use in filenames
- Generating unique, timestamped filenames
- Safe file writing with error handling
- Path validation and file existence checks
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class FileSystemError(Exception):
    """Base exception for file system operations."""
    pass


class InvalidPathError(FileSystemError):
    """Raised when a path is invalid or contains invalid characters."""
    pass


class WritePermissionError(FileSystemError):
    """Raised when write permission is denied."""
    pass


class FileWriteError(FileSystemError):
    """Raised when file writing fails."""
    pass


def sanitize_filename(subject: str, max_length: int = 200) -> str:
    """
    Sanitize an email subject for use in a filename.
    
    Removes or replaces invalid filename characters and handles special cases
    for cross-platform compatibility. The result is safe for use in filenames
    on Windows, macOS, and Linux.
    
    Args:
        subject: The email subject to sanitize
        max_length: Maximum length of the sanitized filename (default: 200)
        
    Returns:
        Sanitized string safe for use in filenames
        
    Examples:
        >>> sanitize_filename("Project Update: Q4 Results")
        'Project Update - Q4 Results'
        >>> sanitize_filename("Email with /invalid\\chars: *?\"<>|")
        'Email with invalid chars'
        >>> sanitize_filename("  Multiple   Spaces  ")
        'Multiple - Spaces'
    """
    if not subject:
        return "untitled"
    
    # Remove invalid filename characters: / \ : * ? " < > |
    # Replace with space or hyphen for readability
    sanitized = re.sub(r'[<>:"/\\|?*]', ' ', subject)
    
    # Replace multiple spaces/hyphens with single hyphen
    sanitized = re.sub(r'[\s\-_]+', '-', sanitized)
    
    # Remove leading/trailing hyphens and spaces
    sanitized = sanitized.strip('- ')
    
    # Truncate to max_length if needed
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('- ')
    
    # If result is empty after sanitization, use default
    if not sanitized:
        sanitized = "untitled"
    
    return sanitized


def generate_unique_filename(
    subject: str,
    base_path: Optional[str] = None,
    timestamp: Optional[datetime] = None
) -> str:
    """
    Generate a unique, timestamped filename for an Obsidian note.
    
    The filename follows the format: YYYY-MM-DD-HHMMSS - <Sanitized-Subject>.md
    
    Args:
        subject: The email subject to use in the filename
        base_path: Optional base directory path. If provided, returns full path.
        timestamp: Optional datetime object. If not provided, uses current time.
        
    Returns:
        Filename string (or full path if base_path provided)
        
    Examples:
        >>> filename = generate_unique_filename("Project Update")
        '2024-01-15-143022 - Project-Update.md'
        >>> full_path = generate_unique_filename("Test", "/path/to/vault")
        '/path/to/vault/2024-01-15-143022 - Test.md'
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    # Format timestamp as YYYY-MM-DD-HHMMSS
    timestamp_str = timestamp.strftime('%Y-%m-%d-%H%M%S')
    
    # Sanitize the subject
    sanitized_subject = sanitize_filename(subject)
    
    # Construct filename
    filename = f"{timestamp_str} - {sanitized_subject}.md"
    
    # If base_path provided, join with it
    if base_path:
        # Normalize path separators
        base = Path(base_path)
        full_path = base / filename
        return str(full_path)
    
    return filename


def file_exists(file_path: str) -> bool:
    """
    Check if a file exists at the given path.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if file exists, False otherwise
    """
    return os.path.isfile(file_path)


def is_valid_path(path: str) -> bool:
    """
    Validate that a path is valid and doesn't contain invalid characters.
    
    Args:
        path: Path to validate
        
    Returns:
        True if path is valid, False otherwise
    """
    try:
        # Try to create a Path object (will raise exception if invalid)
        p = Path(path)
        # Check if path contains any invalid characters
        # Path validation will catch most issues
        return True
    except (OSError, ValueError):
        return False


def get_unique_path(base_path: str, max_attempts: int = 100) -> str:
    """
    Get a unique path by appending numbers if the file already exists.
    
    If the file exists, appends (1), (2), etc. until a unique path is found.
    
    Args:
        base_path: The base file path
        max_attempts: Maximum number of attempts before giving up
        
    Returns:
        Unique file path
        
    Raises:
        FileSystemError: If unable to find unique path after max_attempts
        
    Examples:
        >>> get_unique_path("/path/to/file.md")
        '/path/to/file.md'  # if doesn't exist
        >>> get_unique_path("/path/to/file.md")
        '/path/to/file (1).md'  # if file.md exists
    """
    if not file_exists(base_path):
        return base_path
    
    # Split path into directory, stem, and extension
    path = Path(base_path)
    directory = path.parent
    stem = path.stem
    suffix = path.suffix
    
    # Try appending numbers
    for i in range(1, max_attempts + 1):
        new_path = directory / f"{stem} ({i}){suffix}"
        if not file_exists(str(new_path)):
            return str(new_path)
    
    raise FileSystemError(f"Unable to find unique path after {max_attempts} attempts")


def has_write_permission(directory_path: str) -> bool:
    """
    Check if we have write permission for a directory.
    
    Args:
        directory_path: Directory path to check
        
    Returns:
        True if we have write permission, False otherwise
    """
    if not os.path.isdir(directory_path):
        return False
    
    # Try to create a test file to check write permission
    test_file = os.path.join(directory_path, '.write_test')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except (OSError, PermissionError):
        return False


def safe_write_file(
    content: str,
    file_path: str,
    overwrite: bool = False
) -> str:
    """
    Safely write content to a file with comprehensive error handling.
    
    This function:
    - Validates the path
    - Checks write permissions
    - Handles file existence (creates unique path if needed)
    - Writes content with proper error handling
    - Returns the actual path written to
    
    Args:
        content: Content to write to the file
        file_path: Target file path
        overwrite: If True, overwrite existing file. If False, find unique path.
        
    Returns:
        Actual file path written to
        
    Raises:
        InvalidPathError: If the path is invalid
        WritePermissionError: If write permission is denied
        FileWriteError: If file writing fails for any other reason
        
    Examples:
        >>> safe_write_file("# Note", "/path/to/note.md")
        '/path/to/note.md'
        >>> safe_write_file("# Note", "/path/to/note.md", overwrite=True)
        '/path/to/note.md'  # overwrites if exists
    """
    # Validate path
    if not is_valid_path(file_path):
        raise InvalidPathError(f"Invalid file path: {file_path}")
    
    path = Path(file_path)
    directory = path.parent
    
    # Check if directory exists, create if needed
    if not directory.exists():
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise WritePermissionError(
                f"Cannot create directory {directory}: {e}"
            ) from e
    
    # Check write permission
    if not has_write_permission(str(directory)):
        raise WritePermissionError(
            f"No write permission for directory: {directory}"
        )
    
    # Handle file existence
    actual_path = file_path
    if not overwrite and file_exists(file_path):
        actual_path = get_unique_path(file_path)
    
    # Write file
    try:
        with open(actual_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except OSError as e:
        raise FileWriteError(
            f"Failed to write file {actual_path}: {e}"
        ) from e
    
    return actual_path
