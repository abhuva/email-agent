"""
V4 Configuration Loader with Deep Merge Logic

This module provides functionality to load and merge global and account-specific
configuration files. It implements deep merge logic where:
- Dictionaries: Deep merged (keys in override overwrite keys in base)
- Lists: Completely replaced (lists in override replace lists in base)
- Primitives: Overwritten (values in override replace values in base)

This is the V4 configuration loader that supports multi-tenant configurations
as specified in pdd_V4.md Section 3.1.

The loader automatically validates merged configurations against a schema
to ensure they meet required structure and constraints.

Usage:
    >>> from src.config_loader import ConfigLoader
    >>> loader = ConfigLoader('config')
    >>> config = loader.load_merged_config('work')
    >>> print(config['imap']['server'])
    >>> # Get validation results
    >>> validation_result = loader.get_last_validation_result()
    >>> if not validation_result.is_valid:
    >>>     print(f"Validation errors: {validation_result.errors}")
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

from src.config_validator import ConfigSchemaValidator, ValidationResult

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
        accounts_dirname: str = "accounts",
        enable_validation: bool = True
    ) -> None:
        """
        Initialize the ConfigLoader with paths to configuration files.
        
        Args:
            base_dir: Base directory containing config files
            global_filename: Name of the global config file
            accounts_dirname: Name of the accounts subdirectory
            enable_validation: Whether to enable schema validation (default: True)
        """
        # Resolve paths to absolute Path objects
        self.base_dir = Path(base_dir).resolve()
        self.global_filename = global_filename
        self.accounts_dirname = accounts_dirname
        self.enable_validation = enable_validation
        
        # Store resolved paths
        self._global_config_path: Optional[Path] = None
        self._accounts_dir: Optional[Path] = None
        
        # Initialize validator if validation is enabled
        self._validator: Optional[ConfigSchemaValidator] = None
        if self.enable_validation:
            self._validator = ConfigSchemaValidator()
        
        # Store last validation result
        self._last_validation_result: Optional[ValidationResult] = None
        
        logger.debug(f"ConfigLoader initialized with base_dir={self.base_dir}, validation={enable_validation}")
    
    @staticmethod
    def _validate_account_name(account_name: str) -> str:
        """
        Validate and sanitize an account name.
        
        This method:
        - Strips whitespace
        - Disallows path traversal patterns (../, ..\\)
        - Raises ValueError for invalid names
        
        Args:
            account_name: Account name to validate
            
        Returns:
            Sanitized account name
            
        Raises:
            ValueError: If the account name is invalid or contains path traversal patterns
        """
        if not isinstance(account_name, str):
            raise ValueError(f"Account name must be a string, got {type(account_name).__name__}")
        
        # Strip whitespace
        sanitized = account_name.strip()
        
        # Check for empty after stripping
        if not sanitized:
            raise ValueError("Account name cannot be empty or whitespace-only")
        
        # Disallow path traversal patterns
        if '..' in sanitized or '/' in sanitized or '\\' in sanitized:
            raise ValueError(
                f"Account name contains invalid characters (path traversal detected): {account_name}"
            )
        
        return sanitized
    
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
            ValueError: If the account name is invalid
            FileNotFoundError: If the account config file does not exist
        """
        # Validate account name
        account_name = self._validate_account_name(account_name)
        
        if self._accounts_dir is None:
            self._accounts_dir = self.base_dir / self.accounts_dirname
        
        account_path = self._accounts_dir / f"{account_name}.yaml"
        
        if not account_path.exists():
            raise FileNotFoundError(
                f"Account configuration file not found: {account_path}"
            )
        
        return account_path
    
    def _load_yaml_file(self, path: Path) -> Dict:
        """
        Load a YAML file and return its contents as a dictionary.
        
        This method uses yaml.safe_load to avoid executing arbitrary code.
        It validates that the root element is a dictionary (mapping).
        
        Args:
            path: Path to the YAML file to load
            
        Returns:
            Dictionary containing the parsed YAML content
            
        Raises:
            ConfigurationError: If the file cannot be read, is invalid YAML,
                              or the root element is not a dictionary
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"YAML parse error in {path}: {e}"
            ) from e
        except IOError as e:
            raise ConfigurationError(
                f"Error reading configuration file {path}: {e}"
            ) from e
        
        # Normalize None to empty dict
        if raw_data is None:
            return {}
        
        # Validate that root is a dictionary (mapping)
        if not isinstance(raw_data, dict):
            raise ConfigurationError(
                f"Configuration file {path} root must be a mapping (dict), "
                f"got {type(raw_data).__name__}"
            )
        
        return raw_data
    
    def load_global_config(self) -> Dict:
        """
        Load the global configuration file.
        
        Returns:
            Dictionary containing the global configuration
            
        Raises:
            FileNotFoundError: If the global config file does not exist
            ConfigurationError: If the YAML file is malformed or invalid
        """
        global_path = self._get_global_config_path()
        logger.debug(f"Loading global configuration from {global_path}")
        return self._load_yaml_file(global_path)
    
    def load_account_config(self, account_name: str) -> Dict:
        """
        Load an account-specific configuration file.
        
        If the account config file does not exist, this method returns an empty
        dictionary, allowing global-only configurations to work.
        
        Args:
            account_name: Name of the account to load configuration for
            
        Returns:
            Dictionary containing the account-specific configuration, or empty dict
            if the account config file does not exist
            
        Raises:
            ValueError: If the account name is invalid
            ConfigurationError: If the YAML file is malformed or invalid
            
        Note:
            Missing account config files are allowed and return an empty dict.
            This enables global-only configurations.
        """
        # Validate account name (will raise ValueError if invalid)
        account_name = self._validate_account_name(account_name)
        try:
            account_path = self._get_account_config_path(account_name)
            logger.debug(f"Loading account configuration from {account_path}")
            return self._load_yaml_file(account_path)
        except FileNotFoundError:
            logger.debug(
                f"Account configuration file for '{account_name}' not found, "
                "using global-only configuration"
            )
            return {}
    
    @staticmethod
    def deep_merge(base: Dict, override: Dict) -> Dict:
        """
        Deep merge two configuration dictionaries according to V4 merge rules.
        
        Merge rules:
        - Dictionaries: Recursively deep merged (keys in override overwrite keys in base)
        - Lists: Completely replaced (lists in override replace lists in base, no concatenation)
        - Primitives: Overwritten (values in override replace values in base)
        - Mismatched types: Override value replaces base value
        
        This function does not mutate the input arguments.
        
        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary
            
        Returns:
            New dictionary containing the merged configuration
            
        Examples:
            >>> base = {'a': 1, 'b': {'x': 10, 'y': 20}, 'c': [1, 2, 3]}
            >>> override = {'b': {'y': 30, 'z': 40}, 'c': [4, 5]}
            >>> merged = ConfigLoader.deep_merge(base, override)
            >>> merged
            {'a': 1, 'b': {'x': 10, 'y': 30, 'z': 40}, 'c': [4, 5]}
            
            >>> # Lists are replaced, not concatenated
            >>> base = {'items': [1, 2, 3]}
            >>> override = {'items': [4, 5]}
            >>> ConfigLoader.deep_merge(base, override)
            {'items': [4, 5]}
        """
        # Start with a copy of the base dictionary
        result = base.copy()
        
        for key, override_value in override.items():
            base_value = result.get(key)
            
            # Case 1: Both values are dictionaries - recursively merge
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = ConfigLoader.deep_merge(base_value, override_value)
            
            # Case 2: Both values are lists - replace (not concatenate)
            elif isinstance(base_value, list) and isinstance(override_value, list):
                result[key] = override_value.copy()  # Copy to avoid mutation
            
            # Case 3: All other cases - override replaces base
            # This includes:
            # - Primitives (int, str, float, bool, None)
            # - Mismatched types (e.g., base is dict but override is list)
            # - Override is dict/list but base is not
            else:
                # For mutable types (dict, list), make a copy to avoid mutation
                if isinstance(override_value, dict):
                    result[key] = override_value.copy()
                elif isinstance(override_value, list):
                    result[key] = override_value.copy()
                else:
                    # Primitives can be assigned directly
                    result[key] = override_value
        
        return result
    
    def load_merged_config(self, account_name: str, validate: Optional[bool] = None) -> Dict:
        """
        Load and merge global and account-specific configurations.
        
        This method:
        1. Loads the global config.yaml
        2. Loads the account-specific {account_name}.yaml (if it exists)
        3. Deep merges them according to V4 merge rules:
           - Dictionaries: Deep merged (keys in override overwrite keys in base)
           - Lists: Completely replaced (lists in override replace lists in base)
           - Primitives: Overwritten (values in override replace values in base)
        4. Validates the merged configuration against the schema (if enabled)
        5. Returns the merged configuration dictionary
        
        Args:
            account_name: Name of the account to load configuration for
            validate: Override validation setting for this call (None = use instance default)
            
        Returns:
            Merged configuration dictionary (may be normalized with defaults applied)
            
        Raises:
            ValueError: If the account name is invalid
            FileNotFoundError: If global config is missing
            ConfigurationError: If configuration loading, merging, or validation fails
            
        Note:
            Missing account config files are allowed and will result in global-only
            configuration being returned. Global config is required and will raise
            FileNotFoundError if missing.
            
            Validation is performed after merging. If validation fails with fatal errors,
            a ConfigurationError is raised. Validation results can be retrieved using
            get_last_validation_result().
        """
        # Validate account name (will raise ValueError if invalid)
        account_name = self._validate_account_name(account_name)
        # Load global configuration (required)
        global_config = self.load_global_config()
        
        # Load account-specific configuration (optional - returns {} if missing)
        account_config = self.load_account_config(account_name)
        
        # Deep merge: global as base, account as override
        merged_config = self.deep_merge(global_config, account_config)
        
        # Validate merged configuration if validation is enabled
        should_validate = validate if validate is not None else self.enable_validation
        if should_validate and self._validator is not None:
            validation_result = self._validator.validate(merged_config)
            self._last_validation_result = validation_result
            
            # Log validation issues
            if validation_result.has_errors():
                error_messages = [str(issue) for issue in validation_result.errors]
                logger.error(
                    f"Configuration validation failed for account '{account_name}':\n"
                    + "\n".join(f"  - {msg}" for msg in error_messages)
                )
                # Raise ConfigurationError for fatal validation errors
                raise ConfigurationError(
                    f"Configuration validation failed for account '{account_name}': "
                    f"{len(validation_result.errors)} error(s) found. "
                    f"Use get_last_validation_result() for details."
                )
            elif validation_result.has_warnings():
                warning_messages = [str(issue) for issue in validation_result.warnings]
                logger.warning(
                    f"Configuration validation warnings for account '{account_name}':\n"
                    + "\n".join(f"  - {msg}" for msg in warning_messages)
                )
            
            # Use normalized config if available (has defaults applied)
            if validation_result.normalized_config is not None:
                merged_config = validation_result.normalized_config
        
        logger.info(
            f"Loaded merged configuration for account '{account_name}' "
            f"({len(account_config)} account-specific overrides)"
        )
        
        return merged_config
    
    def get_last_validation_result(self) -> Optional[ValidationResult]:
        """
        Get the validation result from the last load_merged_config call.
        
        Returns:
            ValidationResult from the last validation, or None if validation
            hasn't been performed or is disabled
        """
        return self._last_validation_result
    
    def validate_config(self, config: Dict) -> ValidationResult:
        """
        Validate a configuration dictionary against the schema.
        
        This method can be used to validate a configuration dictionary without
        loading it from files. Useful for testing or validating user-provided configs.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            ValidationResult containing validation status, errors, and warnings
            
        Raises:
            RuntimeError: If validation is disabled for this ConfigLoader instance
        """
        if not self.enable_validation or self._validator is None:
            raise RuntimeError("Validation is disabled for this ConfigLoader instance")
        
        result = self._validator.validate(config)
        self._last_validation_result = result
        return result


# Module-level convenience function
DEFAULT_BASE_DIR = Path("config")


def load_merged_config(
    account_name: str,
    base_dir: Path | str = DEFAULT_BASE_DIR,
    enable_validation: bool = True
) -> Dict:
    """
    Convenience function to load merged configuration for an account.
    
    This is a module-level convenience function that creates a ConfigLoader
    instance and calls load_merged_config on it.
    
    Args:
        account_name: Name of the account to load configuration for
        base_dir: Base directory containing config files (default: 'config')
        enable_validation: Whether to enable schema validation (default: True)
        
    Returns:
        Merged configuration dictionary
        
    Raises:
        ValueError: If the account name is invalid
        FileNotFoundError: If global config is missing
        ConfigurationError: If configuration loading, merging, or validation fails
        
    Example:
        >>> from src.config_loader import load_merged_config
        >>> config = load_merged_config('work')
        >>> print(config['imap']['server'])
    """
    loader = ConfigLoader(base_dir=base_dir, enable_validation=enable_validation)
    return loader.load_merged_config(account_name)
