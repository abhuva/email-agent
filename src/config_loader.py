"""
V4 Configuration Loader with Deep Merge Logic

This module provides functionality to load and merge global and account-specific
configuration files. It implements deep merge logic where:
- Dictionaries: Deep merged (keys in override overwrite keys in base)
- Lists: Completely replaced (lists in override replace lists in base)
- Primitives: Overwritten (values in override replace values in base)

This is the V4 configuration loader that supports multi-tenant configurations
as specified in pdd_V4.md Section 3.1.

Usage:
    >>> from src.config_loader import ConfigLoader
    >>> loader = ConfigLoader('config')
    >>> config = loader.load_merged_config('work')
    >>> print(config['imap']['server'])
"""
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""
    pass


class ConfigLoader:
    """
    Configuration loader that handles loading and merging global and account-specific configurations.
    
    This class implements the V4 configuration strategy where:
    - Global configuration is loaded from config/config.yaml
    - Account-specific overrides are loaded from config/accounts/{account_name}.yaml
    - Configurations are deep merged according to V4 merge rules
    
    Args:
        base_dir: Base directory containing config files (default: 'config')
        global_filename: Name of the global config file (default: 'config.yaml')
        accounts_dirname: Name of the accounts subdirectory (default: 'accounts')
        
    Example:
        >>> loader = ConfigLoader('config')
        >>> config = loader.load_merged_config('work')
        >>> # config contains merged global + account-specific settings
    """
    
    def __init__(
        self,
        base_dir: Path | str = "config",
        global_filename: str = "config.yaml",
        accounts_dirname: str = "accounts"
    ) -> None:
        """
        Initialize the ConfigLoader with paths to configuration files.
        
        Args:
            base_dir: Base directory containing config files
            global_filename: Name of the global config file
            accounts_dirname: Name of the accounts subdirectory
        """
        # Resolve paths to absolute Path objects
        self.base_dir = Path(base_dir).resolve()
        self.global_filename = global_filename
        self.accounts_dirname = accounts_dirname
        
        # Store resolved paths
        self._global_config_path: Optional[Path] = None
        self._accounts_dir: Optional[Path] = None
        
        logger.debug(f"ConfigLoader initialized with base_dir={self.base_dir}")
    
    def _get_global_config_path(self) -> Path:
        """
        Get the path to the global configuration file.
        
        Returns:
            Path to the global config.yaml file
            
        Raises:
            FileNotFoundError: If the global config file does not exist
        """
        if self._global_config_path is None:
            self._global_config_path = self.base_dir / self.global_filename
        
        if not self._global_config_path.exists():
            raise FileNotFoundError(
                f"Global configuration file not found: {self._global_config_path}"
            )
        
        return self._global_config_path
    
    def _get_account_config_path(self, account_name: str) -> Path:
        """
        Get the path to an account-specific configuration file.
        
        Args:
            account_name: Name of the account (used to construct filename)
            
        Returns:
            Path to the account-specific YAML file (e.g., config/accounts/{account_name}.yaml)
            
        Raises:
            FileNotFoundError: If the account config file does not exist
        """
        if self._accounts_dir is None:
            self._accounts_dir = self.base_dir / self.accounts_dirname
        
        account_path = self._accounts_dir / f"{account_name}.yaml"
        
        if not account_path.exists():
            raise FileNotFoundError(
                f"Account configuration file not found: {account_path}"
            )
        
        return account_path
    
    def load_merged_config(self, account_name: str) -> Dict:
        """
        Load and merge global and account-specific configurations.
        
        This method:
        1. Loads the global config.yaml
        2. Loads the account-specific {account_name}.yaml (if it exists)
        3. Deep merges them according to V4 merge rules
        4. Returns the merged configuration dictionary
        
        Args:
            account_name: Name of the account to load configuration for
            
        Returns:
            Merged configuration dictionary
            
        Raises:
            FileNotFoundError: If global config or account config is missing
            ConfigurationError: If configuration loading or merging fails
            
        Note:
            Implementation will be completed in subsequent subtasks.
            This method signature is defined here for interface clarity.
        """
        # Placeholder - implementation will be added in subtask 2.4
        raise NotImplementedError(
            "load_merged_config will be implemented after YAML loading and deep merge utilities are complete"
        )
