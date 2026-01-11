"""
V4 Enhanced Logging Configuration Module

This module provides centralized logging configuration for the V4 multi-account email processing system.
It initializes and overrides the application's logging configuration on startup, ensuring all components
use the same enhanced logging settings with contextual information.

Key Features:
    - Startup-time logging override
    - Centralized configuration loader
    - Support for plain text and JSON formats
    - Context-aware logging (account_id, correlation_id, etc.)
    - Runtime configuration overrides

Usage:
    >>> from src.logging_config import init_logging
    >>> 
    >>> # Initialize with defaults
    >>> init_logging()
    >>> 
    >>> # Initialize with config file
    >>> init_logging(config_path='config/logging.yaml')
    >>> 
    >>> # Initialize with runtime overrides
    >>> init_logging(overrides={'level': 'DEBUG', 'format': 'json'})
    >>> 
    >>> # Use standard logging after initialization
    >>> import logging
    >>> logger = logging.getLogger(__name__)
    >>> logger.info("This will include context automatically")

See Also:
    - docs/v4-logging-design.md - Complete design documentation
    - Task 12 - Enhanced Logging System
"""
import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Union
import json
from datetime import datetime, timezone

# Default configuration
DEFAULT_CONFIG = {
    'level': 'INFO',
    'format': 'plain',  # 'plain' or 'json'
    'handlers': {
        'console': {
            'enabled': True,
            'level': 'INFO'
        },
        'file': {
            'enabled': True,
            'path': 'logs/email_agent.log',
            'level': 'INFO',
            'max_bytes': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5
        },
        'json_file': {
            'enabled': False,
            'path': 'logs/email_agent.jsonl',
            'level': 'INFO'
        }
    },
    'context': {
        'include_component': True,
        'include_environment': True,
        'default_environment': 'production'
    }
}

# Environment variable overrides
ENV_VAR_MAPPING = {
    'LOG_LEVEL': 'level',
    'LOG_FORMAT': 'format',
    'LOG_FILE': ('handlers', 'file', 'path'),
    'LOG_CONSOLE': ('handlers', 'console', 'enabled'),
    'LOG_JSON_FILE': ('handlers', 'json_file', 'enabled'),
    'LOG_JSON_PATH': ('handlers', 'json_file', 'path'),
}


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Formats log records as JSON with context fields included.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'component': getattr(record, 'component', 'unknown'),
        }
        
        # Add context fields if present
        context_fields = ['correlation_id', 'account_id', 'job_id', 'environment', 'request_id']
        for field in context_fields:
            value = getattr(record, field, None)
            if value is not None:
                log_data[field] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """
    Filter that adds context fields to log records.
    
    Context is retrieved from contextvars or thread-local storage.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to log record."""
        # Import here to avoid circular dependencies
        try:
            from src.logging_context import get_logging_context
            context = get_logging_context()
        except ImportError:
            # Fallback if logging_context is not available
            context = {}
        
        # Add context fields to record
        record.correlation_id = context.get('correlation_id', 'N/A')
        record.account_id = context.get('account_id', 'N/A')
        record.job_id = context.get('job_id', 'N/A')
        record.environment = context.get('environment', 'production')
        record.request_id = context.get('request_id', 'N/A')
        
        # Add component name (module name)
        if not hasattr(record, 'component'):
            # Extract component from logger name
            logger_name = record.name
            if '.' in logger_name:
                # Use last part of module path (e.g., 'orchestrator' from 'email_agent.orchestrator')
                record.component = logger_name.split('.')[-1]
            else:
                record.component = logger_name
        
        return True


def _load_config_from_file(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load logging configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for YAML config support. Install with: pip install pyyaml")
    
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Logging config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Extract logging section
    if 'logging' in config:
        return config['logging']
    else:
        return config


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Updated configuration dictionary
    """
    config = config.copy()
    
    for env_var, config_path in ENV_VAR_MAPPING.items():
        env_value = os.environ.get(env_var)
        if env_value is None:
            continue
        
        # Handle nested paths (tuples)
        if isinstance(config_path, tuple):
            # Navigate to nested dict
            current = config
            for key in config_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            # Set final value
            key = config_path[-1]
            # Convert string booleans
            if isinstance(current.get(key), bool) or env_var in ['LOG_CONSOLE', 'LOG_JSON_FILE']:
                current[key] = env_value.lower() in ('true', '1', 'yes', 'on')
            else:
                current[key] = env_value
        else:
            # Simple key-value mapping
            if config_path == 'level':
                config[config_path] = env_value.upper()
            elif config_path == 'format':
                config[config_path] = env_value.lower()
            else:
                config[config_path] = env_value
    
    return config


def _merge_config(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge configuration dictionaries.
    
    Args:
        base: Base configuration
        overrides: Override configuration
        
    Returns:
        Merged configuration
    """
    result = base.copy()
    
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    
    return result


def _setup_handlers(logger: logging.Logger, config: Dict[str, Any]) -> None:
    """
    Set up logging handlers based on configuration.
    
    Args:
        logger: Root logger to configure
        config: Logging configuration
    """
    handlers_config = config.get('handlers', {})
    log_format = config.get('format', 'plain')
    context_filter = ContextFilter()
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    if handlers_config.get('console', {}).get('enabled', True):
        console_level = handlers_config.get('console', {}).get('level', config.get('level', 'INFO'))
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
        
        if log_format == 'json':
            console_handler.setFormatter(JSONFormatter())
        else:
            # Plain text format with context
            formatter = logging.Formatter(
                fmt='%(asctime)s %(levelname)-8s [%(correlation_id)s] [%(account_id)s] [%(component)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
        
        console_handler.addFilter(context_filter)
        logger.addHandler(console_handler)
    
    # File handler (rotating)
    if handlers_config.get('file', {}).get('enabled', True):
        file_config = handlers_config.get('file', {})
        file_path = Path(file_config.get('path', 'logs/email_agent.log'))
        file_level = file_config.get('level', config.get('level', 'INFO'))
        max_bytes = file_config.get('max_bytes', 10 * 1024 * 1024)
        backup_count = file_config.get('backup_count', 5)
        
        # Create log directory if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            str(file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, file_level.upper(), logging.INFO))
        
        if log_format == 'json':
            file_handler.setFormatter(JSONFormatter())
        else:
            formatter = logging.Formatter(
                fmt='%(asctime)s %(levelname)-8s [%(correlation_id)s] [%(account_id)s] [%(component)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
        
        file_handler.addFilter(context_filter)
        logger.addHandler(file_handler)
    
    # JSON file handler (JSONL format)
    if handlers_config.get('json_file', {}).get('enabled', False):
        json_config = handlers_config.get('json_file', {})
        json_path = Path(json_config.get('path', 'logs/email_agent.jsonl'))
        json_level = json_config.get('level', config.get('level', 'INFO'))
        
        # Create log directory if needed
        json_path.parent.mkdir(parents=True, exist_ok=True)
        
        json_handler = logging.FileHandler(str(json_path), encoding='utf-8')
        json_handler.setLevel(getattr(logging, json_level.upper(), logging.INFO))
        json_handler.setFormatter(JSONFormatter())
        json_handler.addFilter(context_filter)
        logger.addHandler(json_handler)


def init_logging(
    config_path: Optional[Union[str, Path]] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> None:
    """
    Initialize and override the application's logging configuration.
    
    This function should be called as the first step of application startup to ensure
    all components use the same enhanced logging settings.
    
    Args:
        config_path: Optional path to YAML configuration file (default: None, uses defaults)
        overrides: Optional dictionary of runtime overrides (e.g., {'level': 'DEBUG'})
        
    Raises:
        FileNotFoundError: If config_path is specified but file doesn't exist
        ValueError: If configuration is invalid
        ImportError: If PyYAML is required but not installed
        
    Example:
        >>> # Use defaults
        >>> init_logging()
        >>> 
        >>> # Load from file
        >>> init_logging(config_path='config/logging.yaml')
        >>> 
        >>> # Override at runtime
        >>> init_logging(overrides={'level': 'DEBUG', 'format': 'json'})
    """
    # Start with default configuration
    config = DEFAULT_CONFIG.copy()
    
    # Load from file if provided
    if config_path:
        file_config = _load_config_from_file(config_path)
        config = _merge_config(config, file_config)
    
    # Apply environment variable overrides
    config = _apply_env_overrides(config)
    
    # Apply runtime overrides
    if overrides:
        config = _merge_config(config, overrides)
    
    # Get root logger
    root_logger = logging.getLogger('email_agent')
    root_logger.setLevel(getattr(logging, config.get('level', 'INFO').upper(), logging.INFO))
    
    # Set up handlers
    _setup_handlers(root_logger, config)
    
    # Log initialization (use basic logging before context is set up)
    root_logger.info("Logging system initialized")
    if config_path:
        root_logger.info(f"Logging configuration loaded from: {config_path}")
    if overrides:
        root_logger.info(f"Logging configuration overrides applied: {overrides}")
    
    # Log effective configuration (at DEBUG level to avoid noise)
    if root_logger.isEnabledFor(logging.DEBUG):
        root_logger.debug(f"Effective logging configuration: level={config.get('level')}, format={config.get('format')}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    This is a convenience function that ensures loggers are created with the
    correct naming convention and inherit from the root logger.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        
    Returns:
        Logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("This message will include context")
    """
    # Ensure logger name starts with 'email_agent'
    if not name.startswith('email_agent'):
        if name == '__main__':
            name = 'email_agent'
        else:
            # Convert module path to email_agent.module format
            if name.startswith('src.'):
                name = 'email_agent.' + name[4:]
            else:
                name = 'email_agent.' + name
    
    return logging.getLogger(name)
