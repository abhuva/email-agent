"""
Error handling utilities for consistent error management and logging.

This module provides:
- Standardized error logging with operation context
- Error categorization and error codes
- Enhanced error messages with context
- Error recovery utilities
"""

import logging
import traceback
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorCode:
    """Standard error codes for different error categories."""
    # Configuration errors (1xxx)
    CONFIG_MISSING = "E1001"
    CONFIG_INVALID = "E1002"
    CONFIG_PATH_INVALID = "E1003"
    
    # IMAP errors (2xxx)
    IMAP_CONNECTION_FAILED = "E2001"
    IMAP_AUTH_FAILED = "E2002"
    IMAP_FETCH_FAILED = "E2003"
    IMAP_TAG_FAILED = "E2004"
    
    # API errors (3xxx)
    API_REQUEST_FAILED = "E3001"
    API_RATE_LIMIT = "E3002"
    API_TIMEOUT = "E3003"
    API_INVALID_RESPONSE = "E3004"
    
    # File system errors (4xxx)
    FILE_READ_FAILED = "E4001"
    FILE_WRITE_FAILED = "E4002"
    FILE_PERMISSION_DENIED = "E4003"
    FILE_PATH_INVALID = "E4004"
    
    # Processing errors (5xxx)
    EMAIL_PROCESSING_FAILED = "E5001"
    NOTE_CREATION_FAILED = "E5002"
    SUMMARY_GENERATION_FAILED = "E5003"
    CHANGELOG_UPDATE_FAILED = "E5004"
    
    # Unknown errors (9xxx)
    UNKNOWN_ERROR = "E9001"


def log_error_with_context(
    error: Exception,
    error_code: str,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR,
    include_traceback: bool = True
) -> None:
    """
    Log an error with standardized context information.
    
    Args:
        error: The exception that occurred
        error_code: Standard error code from ErrorCode class
        operation: Description of the operation that failed
        context: Additional context dictionary (email UID, file path, etc.)
        level: Logging level (default: ERROR)
        include_traceback: Whether to include full traceback (default: True)
    
    Example:
        >>> try:
        ...     process_email(email)
        ... except Exception as e:
        ...     log_error_with_context(
        ...         e, ErrorCode.EMAIL_PROCESSING_FAILED,
        ...         "Processing email with AI",
        ...         context={'email_uid': '123', 'subject': 'Test'}
        ...     )
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    # Build context string
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items() if v is not None]
        if context_items:
            context_str = f" | Context: {', '.join(context_items)}"
    
    # Build log message
    log_message = (
        f"[{error_code}] {operation} failed: {error_type}: {error_message}{context_str}"
    )
    
    # Log with appropriate level
    if include_traceback:
        logger.log(level, log_message, exc_info=True)
    else:
        logger.log(level, log_message)


def safe_operation(
    operation: str,
    error_code: str,
    context: Optional[Dict[str, Any]] = None,
    default_return: Any = None,
    on_error: Optional[Callable] = None
):
    """
    Decorator for safe operation execution with error handling.
    
    Args:
        operation: Description of the operation
        error_code: Standard error code
        context: Base context dictionary (can be extended by function)
        default_return: Value to return on error (default: None)
        on_error: Optional callback function to call on error
    
    Example:
        >>> @safe_operation("Creating Obsidian note", ErrorCode.NOTE_CREATION_FAILED)
        ... def create_note(email):
        ...     # note creation code
        ...     return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Build context from function arguments if available
                op_context = context.copy() if context else {}
                
                # Try to extract email_uid or other common context from args/kwargs
                if args and isinstance(args[0], dict):
                    email_data = args[0]
                    if 'id' in email_data:
                        uid = email_data['id']
                        uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
                        op_context['email_uid'] = uid_str
                    if 'subject' in email_data:
                        op_context['email_subject'] = email_data['subject'][:50]
                
                log_error_with_context(
                    e, error_code, operation,
                    context=op_context,
                    include_traceback=True
                )
                
                # Call error callback if provided
                if on_error:
                    try:
                        on_error(e, op_context)
                    except Exception as callback_error:
                        logger.error(f"Error in on_error callback: {callback_error}", exc_info=True)
                
                return default_return
        return wrapper
    return decorator


def categorize_error(error: Exception) -> tuple[str, str]:
    """
    Categorize an error and return appropriate error code and category.
    
    Args:
        error: The exception to categorize
    
    Returns:
        Tuple of (error_code, category)
    
    Example:
        >>> code, category = categorize_error(FileNotFoundError("file not found"))
        >>> print(code)
        'E4001'
    """
    error_type = type(error).__name__
    
    # Import custom exceptions
    from src.config import ConfigError, ConfigFormatError, ConfigPathError
    from src.imap_connection import IMAPConnectionError, IMAPFetchError
    from src.openrouter_client import OpenRouterAPIError
    from src.obsidian_utils import FileSystemError, InvalidPathError, WritePermissionError, FileWriteError
    
    # Categorize based on exception type
    if isinstance(error, ConfigFormatError):
        return ErrorCode.CONFIG_INVALID, "Configuration"
    elif isinstance(error, ConfigPathError):
        return ErrorCode.CONFIG_PATH_INVALID, "Configuration"
    elif isinstance(error, ConfigError):
        return ErrorCode.CONFIG_MISSING, "Configuration"
    elif isinstance(error, IMAPConnectionError):
        return ErrorCode.IMAP_CONNECTION_FAILED, "IMAP"
    elif isinstance(error, IMAPFetchError):
        return ErrorCode.IMAP_FETCH_FAILED, "IMAP"
    elif isinstance(error, OpenRouterAPIError):
        error_msg = str(error).lower()
        if 'rate limit' in error_msg or '429' in error_msg:
            return ErrorCode.API_RATE_LIMIT, "API"
        elif 'timeout' in error_msg:
            return ErrorCode.API_TIMEOUT, "API"
        else:
            return ErrorCode.API_REQUEST_FAILED, "API"
    elif isinstance(error, (InvalidPathError, FileSystemError)):
        return ErrorCode.FILE_PATH_INVALID, "File System"
    elif isinstance(error, WritePermissionError):
        return ErrorCode.FILE_PERMISSION_DENIED, "File System"
    elif isinstance(error, FileWriteError):
        return ErrorCode.FILE_WRITE_FAILED, "File System"
    elif isinstance(error, (OSError, IOError)):
        return ErrorCode.FILE_WRITE_FAILED, "File System"
    elif isinstance(error, (ConnectionError, TimeoutError)):
        return ErrorCode.API_TIMEOUT, "Network"
    elif isinstance(error, (ValueError, TypeError)):
        return ErrorCode.EMAIL_PROCESSING_FAILED, "Processing"
    else:
        return ErrorCode.UNKNOWN_ERROR, "Unknown"


def format_error_summary(errors: list[Dict[str, Any]]) -> str:
    """
    Format a summary of errors for display.
    
    Args:
        errors: List of error dictionaries with 'code', 'message', 'context' keys
    
    Returns:
        Formatted error summary string
    """
    if not errors:
        return "No errors occurred."
    
    summary_lines = [f"Total errors: {len(errors)}"]
    
    # Group errors by code
    error_counts = {}
    for error in errors:
        code = error.get('code', ErrorCode.UNKNOWN_ERROR)
        error_counts[code] = error_counts.get(code, 0) + 1
    
    summary_lines.append("\nError breakdown:")
    for code, count in sorted(error_counts.items()):
        summary_lines.append(f"  {code}: {count}")
    
    return "\n".join(summary_lines)
