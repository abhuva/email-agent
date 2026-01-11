"""
V4 Logging Context Module

This module provides context management for enhanced logging in the V4 multi-account
email processing system. It stores and propagates contextual information (account_id,
correlation_id, job_id, etc.) that is automatically included in all log messages.

Key Features:
    - Thread-local and contextvars support (for async)
    - Context propagation across function calls
    - Context clearing between account runs
    - Helper functions for setting context

Usage:
    >>> from src.logging_context import set_account_context, with_account_context
    >>> 
    >>> # Set context manually
    >>> set_account_context(account_id='work', correlation_id='abc-123')
    >>> logger.info("This log will include account_id and correlation_id")
    >>> 
    >>> # Use context manager
    >>> with with_account_context(account_id='work', correlation_id='abc-123'):
    >>>     logger.info("This log will include context")
    >>> # Context is automatically cleared after the block

See Also:
    - docs/v4-logging-design.md - Complete design documentation
    - src/logging_config.py - Logging configuration
    - Task 12 - Enhanced Logging System
"""
import contextvars
import threading
from typing import Dict, Any, Optional
from contextlib import contextmanager

# Context variables for async support
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('correlation_id', default=None)
_account_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('account_id', default=None)
_job_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('job_id', default=None)
_environment: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('environment', default='production')
_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)

# Thread-local storage for sync code (fallback)
_thread_local = threading.local()


def _get_thread_local_context() -> Dict[str, Any]:
    """Get thread-local context dictionary, creating it if needed."""
    if not hasattr(_thread_local, 'context'):
        _thread_local.context = {}
    return _thread_local.context


def get_logging_context() -> Dict[str, Any]:
    """
    Get the current logging context.
    
    This function retrieves context from both contextvars (for async) and
    thread-local storage (for sync code), with contextvars taking precedence.
    
    Returns:
        Dictionary containing current context fields:
        - correlation_id: Unique ID for processing run
        - account_id: Account identifier
        - job_id: Job/batch identifier
        - environment: Environment name
        - request_id: Request identifier
    """
    context = {}
    
    # Try contextvars first (for async support)
    try:
        correlation_id = _correlation_id.get()
        account_id = _account_id.get()
        job_id = _job_id.get()
        environment = _environment.get()
        request_id = _request_id.get()
        
        if correlation_id is not None:
            context['correlation_id'] = correlation_id
        if account_id is not None:
            context['account_id'] = account_id
        if job_id is not None:
            context['job_id'] = job_id
        if environment is not None:
            context['environment'] = environment
        if request_id is not None:
            context['request_id'] = request_id
    except LookupError:
        # Contextvars not set, fall back to thread-local
        pass
    
    # Fall back to thread-local storage (for sync code)
    thread_context = _get_thread_local_context()
    context.update(thread_context)
    
    return context


def set_correlation_id(correlation_id: Optional[str]) -> None:
    """
    Set the correlation ID for the current context.
    
    Args:
        correlation_id: Unique identifier for a processing run/job
    """
    _correlation_id.set(correlation_id)
    _get_thread_local_context()['correlation_id'] = correlation_id


def set_account_id(account_id: Optional[str]) -> None:
    """
    Set the account ID for the current context.
    
    Args:
        account_id: Account identifier being processed
    """
    _account_id.set(account_id)
    _get_thread_local_context()['account_id'] = account_id


def set_job_id(job_id: Optional[str]) -> None:
    """
    Set the job ID for the current context.
    
    Args:
        job_id: Job/batch identifier
    """
    _job_id.set(job_id)
    _get_thread_local_context()['job_id'] = job_id


def set_environment(environment: Optional[str]) -> None:
    """
    Set the environment name for the current context.
    
    Args:
        environment: Environment name (e.g., 'production', 'development')
    """
    _environment.set(environment)
    _get_thread_local_context()['environment'] = environment


def set_request_id(request_id: Optional[str]) -> None:
    """
    Set the request ID for the current context.
    
    Args:
        request_id: Request identifier for API calls
    """
    _request_id.set(request_id)
    _get_thread_local_context()['request_id'] = request_id


def set_account_context(
    account_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    job_id: Optional[str] = None,
    environment: Optional[str] = None,
    request_id: Optional[str] = None
) -> None:
    """
    Set multiple context fields at once.
    
    Args:
        account_id: Account identifier
        correlation_id: Correlation ID for processing run
        job_id: Job/batch identifier
        environment: Environment name
        request_id: Request identifier
    """
    if account_id is not None:
        set_account_id(account_id)
    if correlation_id is not None:
        set_correlation_id(correlation_id)
    if job_id is not None:
        set_job_id(job_id)
    if environment is not None:
        set_environment(environment)
    if request_id is not None:
        set_request_id(request_id)


def clear_context() -> None:
    """
    Clear all context fields.
    
    This should be called between account processing runs to ensure
    context from one account doesn't leak into another.
    """
    # Clear contextvars
    try:
        _correlation_id.set(None)
        _account_id.set(None)
        _job_id.set(None)
        _environment.set('production')
        _request_id.set(None)
    except LookupError:
        pass
    
    # Clear thread-local storage
    if hasattr(_thread_local, 'context'):
        _thread_local.context.clear()


@contextmanager
def with_account_context(
    account_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    job_id: Optional[str] = None,
    environment: Optional[str] = None,
    request_id: Optional[str] = None
):
    """
    Context manager for setting account context.
    
    Context is automatically cleared when exiting the context manager.
    
    Args:
        account_id: Account identifier
        correlation_id: Correlation ID for processing run
        job_id: Job/batch identifier
        environment: Environment name
        request_id: Request identifier
        
    Example:
        >>> with with_account_context(account_id='work', correlation_id='abc-123'):
        >>>     logger.info("Processing account")
        >>> # Context is automatically cleared here
    """
    # Store old context
    old_context = get_logging_context()
    
    # Set new context
    set_account_context(
        account_id=account_id,
        correlation_id=correlation_id,
        job_id=job_id,
        environment=environment,
        request_id=request_id
    )
    
    try:
        yield
    finally:
        # Restore old context (or clear if it was empty)
        clear_context()  # Clear first
        if old_context:
            set_account_context(**old_context)


@contextmanager
def with_correlation_id(correlation_id: str):
    """
    Context manager for setting correlation ID only.
    
    Args:
        correlation_id: Correlation ID for processing run
        
    Example:
        >>> with with_correlation_id('abc-123'):
        >>>     logger.info("This log will include correlation_id")
    """
    old_correlation_id = _correlation_id.get(None)
    set_correlation_id(correlation_id)
    try:
        yield
    finally:
        if old_correlation_id is not None:
            set_correlation_id(old_correlation_id)
        else:
            _correlation_id.set(None)
            _get_thread_local_context().pop('correlation_id', None)
