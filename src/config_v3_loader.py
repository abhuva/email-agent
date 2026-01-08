"""
V3 Configuration Loader

This module provides functionality to load, parse, and validate V3 configuration
files using the Pydantic schema defined in config_v3_schema.py.

The loader follows the PDD specification and ensures all configuration
conforms to the exact structure required.

Environment Variable Overrides:
    Configuration values can be overridden using environment variables.
    Naming convention: EMAIL_AGENT_<SECTION>_<KEY> (uppercase, underscores)
    
    Examples:
        EMAIL_AGENT_IMAP_SERVER=imap.custom.com
        EMAIL_AGENT_OPENROUTER_MODEL=openai/gpt-4
        EMAIL_AGENT_PROCESSING_IMPORTANCE_THRESHOLD=7
        EMAIL_AGENT_PATHS_OBSIDIAN_VAULT=/custom/path
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from src.config_v3_schema import V3ConfigSchema
from src.config import ConfigError

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Configuration loader for V3 configuration files.
    
    This class handles loading YAML configuration files, parsing them,
    and validating them against the V3 Pydantic schema.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Raises:
        ConfigError: If the config file is missing, invalid YAML, or validation fails
        
    Example:
        >>> loader = ConfigLoader('config/config.yaml')
        >>> config = loader.load()
        >>> print(config.imap.server)
        'imap.example.com'
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")
    
    @staticmethod
    def _apply_env_overrides(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration dictionary.
        
        Environment variable naming: EMAIL_AGENT_<SECTION>_<KEY>
        Examples:
            EMAIL_AGENT_IMAP_SERVER -> config['imap']['server']
            EMAIL_AGENT_OPENROUTER_MODEL -> config['openrouter']['model']
            EMAIL_AGENT_PROCESSING_IMPORTANCE_THRESHOLD -> config['processing']['importance_threshold']
        
        Args:
            config_dict: Configuration dictionary from YAML
            
        Returns:
            Configuration dictionary with environment variable overrides applied
        """
        env_prefix = "EMAIL_AGENT_"
        overrides_applied = []
        
        # Map of section names for environment variable parsing
        section_map = {
            'IMAP': 'imap',
            'PATHS': 'paths',
            'OPENROUTER': 'openrouter',
            'CLASSIFICATION': 'classification',
            'SUMMARIZATION': 'summarization',
            'PROCESSING': 'processing'
        }
        
        # Scan all environment variables with the prefix
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(env_prefix):
                continue
            
            # Remove prefix and split into section and key
            key_without_prefix = env_key[len(env_prefix):]
            parts = key_without_prefix.split('_', 1)
            
            if len(parts) != 2:
                logger.warning(f"Invalid environment variable format: {env_key} (expected EMAIL_AGENT_<SECTION>_<KEY>)")
                continue
            
            section_env, key_env = parts
            section = section_map.get(section_env)
            
            if not section:
                logger.warning(f"Unknown configuration section in environment variable: {env_key}")
                continue
            
            # Ensure section exists in config
            if section not in config_dict:
                config_dict[section] = {}
            
            # Convert value based on expected type (simple heuristic)
            converted_value = ConfigLoader._convert_env_value(key_env, env_value, section)
            
            # Apply override
            config_dict[section][key_env.lower()] = converted_value
            overrides_applied.append(f"{section}.{key_env.lower()}={converted_value}")
        
        if overrides_applied:
            logger.info(f"Applied {len(overrides_applied)} environment variable overrides: {', '.join(overrides_applied)}")
        
        return config_dict
    
    @staticmethod
    def _convert_env_value(key: str, value: str, section: str) -> Any:
        """
        Convert environment variable string value to appropriate type.
        
        Args:
            key: Configuration key name
            value: Environment variable value (string)
            section: Configuration section name
            
        Returns:
            Converted value with appropriate type
        """
        # Integer fields
        int_fields = {
            'imap': ['port'],
            'openrouter': ['retry_attempts', 'retry_delay_seconds'],
            'processing': ['importance_threshold', 'spam_threshold', 'max_body_chars', 'max_emails_per_run']
        }
        
        # Float fields
        float_fields = {
            'openrouter': ['temperature']
        }
        
        # Boolean fields (if any)
        bool_fields = {}
        
        key_lower = key.lower()
        
        if section in int_fields and key_lower in int_fields[section]:
            try:
                return int(value)
            except ValueError:
                raise ConfigError(f"Environment variable value for {key} must be an integer, got: {value}")
        
        if section in float_fields and key_lower in float_fields[section]:
            try:
                return float(value)
            except ValueError:
                raise ConfigError(f"Environment variable value for {key} must be a number, got: {value}")
        
        if section in bool_fields and key_lower in bool_fields[section]:
            return value.lower() in ('true', '1', 'yes', 'on')
        
        # Default: return as string
        return value
    
    def load(self) -> V3ConfigSchema:
        """
        Load and validate the configuration file.
        
        Environment variable overrides are applied before validation.
        
        Returns:
            Validated V3ConfigSchema instance
            
        Raises:
            ConfigError: If YAML parsing fails
            ValidationError: If schema validation fails (from Pydantic)
        """
        logger.info(f"Loading configuration from {self.config_path}")
        
        # Load YAML file
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {self.config_path}: {e}")
        except IOError as e:
            raise ConfigError(f"Error reading configuration file {self.config_path}: {e}")
        
        if raw_config is None:
            raise ConfigError(f"Configuration file {self.config_path} is empty")
        
        # Apply environment variable overrides
        raw_config = self._apply_env_overrides(raw_config)
        
        # Validate against Pydantic schema
        try:
            validated_config = V3ConfigSchema(**raw_config)
            logger.info("Configuration loaded and validated successfully")
            return validated_config
        except Exception as e:
            # Pydantic validation errors provide detailed information
            error_msg = f"Configuration validation failed: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
    
    @staticmethod
    def load_from_dict(config_dict: Dict[str, Any]) -> V3ConfigSchema:
        """
        Load and validate configuration from a dictionary.
        
        This is useful for testing or programmatic configuration.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            Validated V3ConfigSchema instance
            
        Raises:
            ValidationError: If schema validation fails
        """
        try:
            validated_config = V3ConfigSchema(**config_dict)
            return validated_config
        except Exception as e:
            error_msg = f"Configuration validation failed: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
