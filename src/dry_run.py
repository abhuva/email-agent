"""
Dry-run utility for V3 email processing.

This module provides a global dry-run context that can be checked throughout
the codebase to determine if operations should be executed or just previewed.

Usage:
    >>> from src.dry_run import set_dry_run, is_dry_run, DryRunContext
    >>> 
    >>> # Set dry-run mode globally
    >>> set_dry_run(True)
    >>> 
    >>> # Check if in dry-run mode
    >>> if is_dry_run():
    ...     print("Would write file here")
    ... else:
    ...     write_file()
    >>> 
    >>> # Use context manager for temporary dry-run mode
    >>> with DryRunContext(True):
    ...     # Operations here are in dry-run mode
    ...     pass
"""
import threading
from typing import Optional
from contextlib import contextmanager

# Thread-local storage for dry-run state
_thread_local = threading.local()


def set_dry_run(enabled: bool) -> None:
    """
    Set the global dry-run mode.
    
    Args:
        enabled: True to enable dry-run mode, False to disable
    """
    _thread_local.dry_run = enabled


def is_dry_run() -> bool:
    """
    Check if dry-run mode is currently enabled.
    
    Returns:
        True if dry-run mode is enabled, False otherwise
    """
    return getattr(_thread_local, 'dry_run', False)


def get_dry_run() -> bool:
    """
    Get the current dry-run mode state.
    
    Alias for is_dry_run() for consistency.
    
    Returns:
        True if dry-run mode is enabled, False otherwise
    """
    return is_dry_run()


@contextmanager
def DryRunContext(enabled: bool):
    """
    Context manager for temporary dry-run mode.
    
    Args:
        enabled: True to enable dry-run mode within context, False to disable
        
    Example:
        >>> with DryRunContext(True):
        ...     # Operations here are in dry-run mode
        ...     if is_dry_run():
        ...         print("Would write file")
    """
    previous_state = is_dry_run()
    try:
        set_dry_run(enabled)
        yield
    finally:
        set_dry_run(previous_state)
