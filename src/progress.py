"""
Progress bar utilities for email processing operations.

This module provides a standardized interface for creating and managing progress bars
across the email processing pipeline. It wraps tqdm to provide consistent progress
tracking for:
- Email fetching
- Content parsing
- LLM processing
- Note generation

The utilities are designed to work in both CLI and notebook environments, and
respect configuration settings for disabling progress bars when needed.

Usage:
    >>> from src.progress import create_progress_bar, tqdm_write
    >>> 
    >>> # For iterable-based progress
    >>> for email in create_progress_bar(emails, desc="Processing emails", unit="emails"):
    ...     process_email(email)
    >>> 
    >>> # For manual update progress
    >>> with create_progress_bar(total=100, desc="Processing", unit="items") as pbar:
    ...     for i in range(100):
    ...         do_work()
    ...         pbar.update(1)
    >>> 
    >>> # For logging inside progress bars
    >>> tqdm_write("Log message that won't interfere with progress bar")
"""
import os
import logging
from typing import Optional, Iterable, Any, Union
from contextlib import contextmanager

try:
    from tqdm.auto import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Create a dummy tqdm class for when tqdm is not available
    class tqdm:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def __iter__(self):
            return iter([])
        def update(self, n=1):
            pass
        def write(self, s, file=None, end="\n"):
            print(s, end=end, file=file)

logger = logging.getLogger(__name__)


def is_progress_enabled() -> bool:
    """
    Check if progress bars should be enabled.
    
    Progress bars can be disabled by setting the DISABLE_PROGRESS environment variable
    to 'true', '1', or 'yes'. This is useful for:
    - CI/CD environments
    - Non-interactive shells
    - When logging to files
    
    Returns:
        True if progress bars should be shown, False otherwise
    """
    disable = os.getenv('DISABLE_PROGRESS', '').lower()
    return disable not in ('true', '1', 'yes')


def create_progress_bar(
    iterable: Optional[Iterable[Any]] = None,
    total: Optional[int] = None,
    desc: str = "Processing",
    unit: str = "items",
    disable: Optional[bool] = None,
    mininterval: float = 0.1,
    ncols: Optional[int] = None,
    **kwargs
) -> Union[tqdm, Iterable[Any]]:
    """
    Create a progress bar for tracking processing operations.
    
    This function provides a standardized way to create progress bars across the
    application. It handles:
    - Automatic disabling based on environment variables
    - Consistent formatting and units
    - Both iterable-based and manual-update modes
    
    Args:
        iterable: Optional iterable to wrap (for iterable-based progress)
        total: Total number of items (for manual-update mode)
        desc: Description text for the progress bar
        unit: Unit label (e.g., "emails", "items", "notes")
        disable: Override automatic disable detection (None = auto-detect)
        mininterval: Minimum update interval in seconds (default: 0.1)
        ncols: Number of columns for progress bar (None = auto)
        **kwargs: Additional arguments passed to tqdm
    
    Returns:
        tqdm progress bar instance (or iterable if iterable was provided)
    
    Examples:
        # Iterable-based (wraps an existing iterable)
        for email in create_progress_bar(emails, desc="Fetching emails", unit="emails"):
            process(email)
        
        # Manual-update mode (context manager)
        with create_progress_bar(total=100, desc="Processing", unit="items") as pbar:
            for i in range(100):
                do_work()
                pbar.update(1)
    """
    if not TQDM_AVAILABLE:
        logger.warning("tqdm not available, progress bars disabled")
        if iterable is not None:
            return iterable
        return _DummyProgressBar()
    
    # Determine if progress should be disabled
    if disable is None:
        disable = not is_progress_enabled()
    
    # Set default tqdm parameters
    tqdm_kwargs = {
        'desc': desc,
        'unit': unit,
        'disable': disable,
        'mininterval': mininterval,
        **kwargs
    }
    
    if ncols is not None:
        tqdm_kwargs['ncols'] = ncols
    
    if iterable is not None:
        # Iterable-based mode
        if total is None and hasattr(iterable, '__len__'):
            # Try to get length from iterable
            try:
                total = len(iterable)
            except (TypeError, AttributeError):
                pass
        
        if total is not None:
            tqdm_kwargs['total'] = total
        
        return tqdm(iterable, **tqdm_kwargs)
    else:
        # Manual-update mode
        if total is None:
            raise ValueError("Either 'iterable' or 'total' must be provided")
        
        tqdm_kwargs['total'] = total
        return tqdm(**tqdm_kwargs)


class _DummyProgressBar:
    """Dummy progress bar that does nothing when tqdm is not available."""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def __iter__(self):
        return iter([])
    
    def update(self, n=1):
        pass


def tqdm_write(message: str, file=None, end: str = "\n"):
    """
    Write a message without interfering with progress bar display.
    
    When logging inside a loop that uses tqdm, use this function instead of
    print() or logger.info() to avoid mangling the progress bar display.
    
    Args:
        message: Message to write
        file: File object to write to (default: sys.stdout)
        end: Line ending (default: "\n")
    
    Examples:
        >>> with create_progress_bar(total=100, desc="Processing") as pbar:
        ...     for i in range(100):
        ...         if i % 10 == 0:
        ...             tqdm_write(f"Processed {i} items")
        ...         pbar.update(1)
    """
    if TQDM_AVAILABLE:
        tqdm.write(message, file=file, end=end)
    else:
        print(message, end=end, file=file)
