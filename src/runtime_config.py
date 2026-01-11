"""
V4 Runtime Configuration Module

This module provides unified configuration and environment handling for the multi-account
architecture. It merges CLI arguments, environment variables, and defaults into a
structured RuntimeConfig object.

Configuration Precedence (highest to lowest):
1. CLI arguments
2. Environment variables
3. Default values

Usage:
    >>> from src.runtime_config import build_runtime_config, RuntimeConfig
    >>> from argparse import Namespace
    >>> 
    >>> # Parse CLI args (example)
    >>> parsed_args = Namespace(
    ...     account='work',
    ...     all_accounts=False,
    ...     dry_run=False,
    ...     config_dir='config',
    ...     env_file='.env'
    ... )
    >>> 
    >>> # Build runtime config
    >>> config = build_runtime_config(parsed_args)
    >>> print(config.account_names)
    ['work']
    >>> print(config.dry_run)
    False
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from argparse import Namespace

logger = logging.getLogger(__name__)


@dataclass
class RuntimeConfig:
    """
    Multi-account runtime configuration.
    
    This configuration object represents the complete runtime state needed
    to execute the V4 email agent, including account selection, paths,
    and processing options.
    
    Attributes:
        account_names: List of account names to process (empty = all accounts)
        process_all: Whether to process all accounts
        config_base_dir: Base directory for configuration files
        accounts_dir: Directory containing account-specific configs
        env_file: Path to .env file for secrets
        dry_run: Whether to run in preview mode (no side effects)
        log_level: Logging level (DEBUG, INFO, WARN, ERROR)
        account_configs: Per-account merged configurations (loaded on demand)
    """
    # Account selection
    account_names: List[str] = field(default_factory=list)
    process_all: bool = False
    
    # Paths
    config_base_dir: Path = field(default_factory=lambda: Path('config'))
    accounts_dir: Path = field(init=False)
    env_file: Path = field(default_factory=lambda: Path('.env'))
    
    # Options
    dry_run: bool = False
    log_level: str = 'INFO'
    
    # Per-account configs (loaded on demand via ConfigLoader)
    account_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict, repr=False)
    
    def __post_init__(self):
        """Set derived paths after initialization."""
        # accounts_dir is always config_base_dir / 'accounts'
        if isinstance(self.config_base_dir, str):
            self.config_base_dir = Path(self.config_base_dir)
        self.accounts_dir = self.config_base_dir / 'accounts'
    
    def validate(self) -> None:
        """
        Validate the runtime configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate account selection
        if self.process_all and self.account_names:
            raise ValueError("Cannot specify both --all and --account. Use one or the other.")
        
        # Validate paths
        if not self.config_base_dir.exists():
            raise ValueError(f"Config base directory does not exist: {self.config_base_dir}")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")
        
        # Normalize log level (WARN -> WARNING)
        if self.log_level.upper() == 'WARN':
            self.log_level = 'WARNING'
        else:
            self.log_level = self.log_level.upper()


def read_env_account_ids() -> List[str]:
    """
    Read account IDs from ACCOUNT_IDS environment variable.
    
    Returns:
        List of account names (empty if not set or invalid)
    """
    account_ids_str = os.getenv('ACCOUNT_IDS', '').strip()
    if not account_ids_str:
        return []
    
    # Split by comma and clean up
    account_ids = [name.strip() for name in account_ids_str.split(',')]
    # Filter out empty strings
    account_ids = [name for name in account_ids if name]
    
    return account_ids


def read_env_bool(key: str, default: bool = False) -> bool:
    """
    Read a boolean environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Boolean value (true if env var is 'true', '1', 'yes', 'on')
    """
    value = os.getenv(key, '').strip().lower()
    if not value:
        return default
    
    return value in ('true', '1', 'yes', 'on')


def read_env_path(key: str, default: Optional[Path] = None) -> Optional[Path]:
    """
    Read a path from an environment variable.
    
    Args:
        key: Environment variable name
        default: Default path if not set
        
    Returns:
        Path object or None
    """
    value = os.getenv(key, '').strip()
    if not value:
        return default
    
    return Path(value)


def normalize_account_names(account_names: List[str]) -> List[str]:
    """
    Normalize account names (remove duplicates, empty strings, and whitespace-only strings).
    
    Args:
        account_names: List of account names
        
    Returns:
        Normalized list (unique, non-empty)
    """
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for name in account_names:
        # Strip whitespace and check if non-empty
        name = name.strip() if name else ''
        if name and name not in seen:
            seen.add(name)
            unique.append(name)
    
    return unique


def build_runtime_config(parsed_args: Namespace) -> RuntimeConfig:
    """
    Build runtime configuration from CLI arguments, environment variables, and defaults.
    
    Configuration precedence (highest to lowest):
    1. CLI arguments
    2. Environment variables
    3. Default values
    
    Args:
        parsed_args: Parsed CLI arguments (argparse.Namespace or similar)
                    Expected attributes:
                    - account: Optional[str] - Single account name
                    - all_accounts: bool - Process all accounts flag
                    - dry_run: bool - Dry run flag
                    - config_dir: Optional[str] - Config directory path
                    - env_file: Optional[str] - .env file path
                    - log_level: Optional[str] - Logging level
    
    Returns:
        RuntimeConfig object with merged configuration
        
    Raises:
        ValueError: If configuration is invalid
        
    Example:
        >>> from argparse import Namespace
        >>> args = Namespace(
        ...     account='work',
        ...     all_accounts=False,
        ...     dry_run=False,
        ...     config_dir=None,
        ...     env_file=None,
        ...     log_level=None
        ... )
        >>> config = build_runtime_config(args)
        >>> config.account_names
        ['work']
    """
    # 1. Read environment variables (lower priority than CLI)
    env_account_ids = read_env_account_ids()
    env_dry_run = read_env_bool('DRY_RUN', False)
    env_config_dir = read_env_path('CONFIG_DIR')
    env_env_file = read_env_path('ENV_FILE', Path('.env'))
    env_log_level = os.getenv('LOG_LEVEL', 'INFO').strip()
    default_account = os.getenv('DEFAULT_ACCOUNT', '').strip()
    
    # 2. Merge CLI arguments (highest priority)
    # Account selection
    account_names: List[str] = []
    process_all = False
    
    if hasattr(parsed_args, 'all_accounts') and parsed_args.all_accounts:
        process_all = True
        # If --all is specified, ignore any account names
        account_names = []
    elif hasattr(parsed_args, 'account') and parsed_args.account:
        # Single account from CLI
        account_names = [parsed_args.account]
    elif env_account_ids:
        # Accounts from environment
        account_names = env_account_ids
    elif default_account:
        # Default account from environment
        account_names = [default_account]
    else:
        # No account specified - process all
        process_all = True
        account_names = []
    
    # Normalize account names
    account_names = normalize_account_names(account_names)
    
    # Dry run: CLI > Env > Default
    # Check if CLI explicitly sets dry_run (True or False)
    if hasattr(parsed_args, 'dry_run'):
        dry_run = bool(parsed_args.dry_run)  # CLI takes precedence
    elif env_dry_run:
        dry_run = True
    else:
        dry_run = False
    
    # Config directory: CLI > Env > Default
    config_base_dir: Path
    if hasattr(parsed_args, 'config_dir') and parsed_args.config_dir:
        config_base_dir = Path(parsed_args.config_dir)
    elif env_config_dir:
        config_base_dir = env_config_dir
    else:
        config_base_dir = Path('config')
    
    # Resolve to absolute path
    config_base_dir = config_base_dir.resolve()
    
    # Env file: CLI > Env > Default
    env_file: Path
    if hasattr(parsed_args, 'env_file') and parsed_args.env_file:
        env_file = Path(parsed_args.env_file)
    elif env_env_file:
        env_file = env_env_file
    else:
        env_file = Path('.env')
    
    # Resolve to absolute path if it exists
    if env_file.exists():
        env_file = env_file.resolve()
    
    # Log level: CLI > Env > Default
    log_level: str
    if hasattr(parsed_args, 'log_level') and parsed_args.log_level:
        log_level = parsed_args.log_level
    elif env_log_level:
        log_level = env_log_level
    else:
        log_level = 'INFO'
    
    # 3. Build configuration object
    config = RuntimeConfig(
        account_names=account_names,
        process_all=process_all,
        config_base_dir=config_base_dir,
        env_file=env_file,
        dry_run=dry_run,
        log_level=log_level
    )
    
    # 4. Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    # 5. Log configuration (at debug level to avoid noise)
    logger.debug(f"Runtime configuration built:")
    logger.debug(f"  Account names: {config.account_names if config.account_names else '(all accounts)'}")
    logger.debug(f"  Process all: {config.process_all}")
    logger.debug(f"  Config base dir: {config.config_base_dir}")
    logger.debug(f"  Accounts dir: {config.accounts_dir}")
    logger.debug(f"  Env file: {config.env_file}")
    logger.debug(f"  Dry run: {config.dry_run}")
    logger.debug(f"  Log level: {config.log_level}")
    
    return config


__all__ = ['RuntimeConfig', 'build_runtime_config', 'read_env_account_ids', 'normalize_account_names']
