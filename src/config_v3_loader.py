"""
V3 Configuration Loader

This module provides functionality to load, parse, and validate V3 configuration
files using the Pydantic schema defined in config_v3_schema.py.

The loader follows the PDD specification and ensures all configuration
conforms to the exact structure required.
"""
import os
import yaml
import logging
from typing import Dict, Any
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
    
    def load(self) -> V3ConfigSchema:
        """
        Load and validate the configuration file.
        
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
