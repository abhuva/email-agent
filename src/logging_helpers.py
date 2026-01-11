"""
V4 Logging Helpers Module

This module provides helper functions for structured logging in the V4 multi-account
email processing system, specifically for account lifecycle and configuration overrides.

Key Features:
    - Account processing lifecycle logging (start/end)
    - Configuration override logging
    - Structured error logging with context

Usage:
    >>> from src.logging_helpers import log_account_start, log_account_end, log_config_overrides
    >>> from src.logging_context import set_account_context
    >>> 
    >>> set_account_context(account_id='work', correlation_id='abc-123')
    >>> log_account_start('work')
    >>> # ... process account ...
    >>> log_account_end('work', success=True, processing_time=10.5)

See Also:
    - docs/v4-logging-design.md - Complete design documentation
    - src/logging_config.py - Logging configuration
    - src/logging_context.py - Context management
    - Task 12 - Enhanced Logging System
"""
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


def log_account_start(account_id: str, correlation_id: Optional[str] = None) -> None:
    """
    Log the start of account processing.
    
    This should be called at the beginning of account processing with the account
    context already set (via logging_context.set_account_context).
    
    Args:
        account_id: Account identifier being processed
        correlation_id: Optional correlation ID (if not set in context)
    """
    context_msg = f"Processing account: {account_id}"
    if correlation_id:
        context_msg += f" [correlation_id={correlation_id}]"
    
    logger.info(context_msg)


def log_account_end(
    account_id: str,
    success: bool,
    processing_time: float,
    correlation_id: Optional[str] = None,
    error: Optional[str] = None
) -> None:
    """
    Log the end of account processing.
    
    This should be called at the end of account processing (success or failure)
    with the account context still set.
    
    Args:
        account_id: Account identifier that was processed
        success: Whether processing completed successfully
        processing_time: Time taken to process (in seconds)
        correlation_id: Optional correlation ID (if not set in context)
        error: Optional error message (if processing failed)
    """
    status = "successfully" if success else "failed"
    context_msg = f"Account '{account_id}' processing complete ({status}, time: {processing_time:.2f}s)"
    
    if correlation_id:
        context_msg += f" [correlation_id={correlation_id}]"
    
    if error:
        context_msg += f" - Error: {error}"
    
    if success:
        logger.info(context_msg)
    else:
        logger.error(context_msg)


def log_config_overrides(
    overrides: Dict[str, Any],
    account_id: Optional[str] = None,
    source: str = "account_config",
    scope: str = "account"
) -> None:
    """
    Log configuration overrides in a structured way.
    
    This function logs which configuration values were overridden, their effective
    values, scope (global vs per-account), and source (CLI, env vars, account config, etc.).
    
    Args:
        overrides: Dictionary of configuration overrides (key: value pairs)
        account_id: Optional account identifier (if scope is 'account')
        source: Source of the override (e.g., 'cli', 'env_var', 'account_config', 'runtime')
        scope: Scope of the override ('global' or 'account')
    
    Example:
        >>> log_config_overrides(
        ...     overrides={'imap.username': 'work@example.com', 'imap.server': 'imap.work.com'},
        ...     account_id='work',
        ...     source='account_config',
        ...     scope='account'
        ... )
    """
    if not overrides:
        return
    
    # Format override information
    override_items = []
    for key, value in overrides.items():
        # Mask sensitive values
        masked_value = _mask_sensitive_value(key, value)
        override_items.append(f"{key}={masked_value}")
    
    override_str = ", ".join(override_items)
    
    # Build log message
    if scope == 'account' and account_id:
        msg = f"Configuration override for account '{account_id}' ({source}): {override_str}"
    elif scope == 'global':
        msg = f"Global configuration override ({source}): {override_str}"
    else:
        msg = f"Configuration override ({source}): {override_str}"
    
    logger.info(msg)


def log_config_merge(
    account_id: str,
    global_config_keys: List[str],
    account_config_keys: List[str],
    merged_keys: List[str]
) -> None:
    """
    Log configuration merge operation.
    
    This logs when global and account-specific configurations are merged,
    showing which keys came from which source.
    
    Args:
        account_id: Account identifier
        global_config_keys: List of configuration keys from global config
        account_config_keys: List of configuration keys from account config
        merged_keys: List of all keys in the merged configuration
    """
    if not account_config_keys:
        logger.debug(f"Account '{account_id}': Using global-only configuration ({len(global_config_keys)} keys)")
        return
    
    logger.info(
        f"Account '{account_id}': Merged configuration "
        f"(global: {len(global_config_keys)} keys, "
        f"account: {len(account_config_keys)} keys, "
        f"total: {len(merged_keys)} keys)"
    )


def _mask_sensitive_value(key: str, value: Any) -> str:
    """
    Mask sensitive configuration values in log messages.
    
    Args:
        key: Configuration key name
        value: Configuration value
        
    Returns:
        Masked value string (original value if not sensitive)
    """
    # List of keys that contain sensitive information
    sensitive_keys = [
        'password', 'secret', 'token', 'key', 'api_key', 'auth',
        'credential', 'passwd', 'pwd'
    ]
    
    key_lower = key.lower()
    
    # Check if key contains sensitive keywords
    if any(sensitive in key_lower for sensitive in sensitive_keys):
        if isinstance(value, str) and len(value) > 0:
            # Mask all but first and last character
            if len(value) <= 2:
                return "***"
            return value[0] + "*" * (len(value) - 2) + value[-1]
        else:
            return "***"
    
    return str(value)


def log_error_with_context(
    error: Exception,
    account_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    operation: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error with full context information.
    
    This is a convenience function that logs errors with all available context
    fields and additional diagnostic information.
    
    Args:
        error: Exception that occurred
        account_id: Optional account identifier
        correlation_id: Optional correlation ID
        operation: Optional operation name (e.g., 'setup', 'processing', 'teardown')
        additional_context: Optional dictionary of additional context fields
    """
    error_msg = f"Error: {type(error).__name__}: {str(error)}"
    
    if account_id:
        error_msg = f"Account '{account_id}': {error_msg}"
    
    if operation:
        error_msg = f"{operation}: {error_msg}"
    
    if correlation_id:
        error_msg += f" [correlation_id={correlation_id}]"
    
    if additional_context:
        context_str = ", ".join(f"{k}={v}" for k, v in additional_context.items())
        error_msg += f" [context: {context_str}]"
    
    logger.error(error_msg, exc_info=True)
