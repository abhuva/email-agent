"""
V3 Configuration Facade

This module provides a central facade for accessing all configuration values.
It is the sole module responsible for loading and providing access to parameters
from config.yaml, decoupling all other modules from the YAML file's structure.

All application modules MUST access configuration through this facade, not
directly from YAML or the config loader.

Architecture:
    - This facade implements the Facade Pattern as specified in pdd.md Section 2
    - All configuration access is centralized here
    - Changes to config.yaml structure only require updates to this module
    - Other modules remain decoupled from configuration implementation details

Usage:
    >>> from src.settings import settings
    >>> server = settings.get_imap_server()
    >>> api_url = settings.get_openrouter_api_url()
    >>> api_key = settings.get_openrouter_api_key()
"""
import os
import logging
from typing import Optional
from pathlib import Path

from src.config_v3_loader import ConfigLoader
from src.config_v3_schema import V3ConfigSchema
from src.config import ConfigError

logger = logging.getLogger(__name__)


class Settings:
    """
    Configuration facade providing getter methods for all configuration values.
    
    This class implements the Facade Pattern as specified in the PDD.
    It loads configuration once and provides type-safe access to all values.
    
    All modules should import and use this singleton instance:
        from src.settings import settings
    """
    
    _instance: Optional['Settings'] = None
    _config: Optional[V3ConfigSchema] = None
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, config_path: str = "config/config.yaml", env_path: str = ".env") -> None:
        """
        Initialize the settings facade by loading configuration.
        
        This should be called once at application startup.
        If not called explicitly, configuration will be loaded lazily on first access.
        
        Args:
            config_path: Path to the YAML configuration file
            env_path: Path to the .env file (for loading environment variables)
            
        Raises:
            ConfigError: If configuration loading or validation fails
        """
        if self._config is not None:
            logger.warning("Settings already initialized, ignoring re-initialization")
            return
        
        # Load environment variables from .env file if it exists
        if os.path.exists(env_path):
            from dotenv import load_dotenv
            load_dotenv(env_path)
            logger.info(f"Loaded environment variables from {env_path}")
        
        # Load and validate configuration
        loader = ConfigLoader(config_path)
        self._config = loader.load()
        logger.info("Settings facade initialized successfully")
    
    def _ensure_initialized(self) -> None:
        """Ensure configuration is loaded (lazy initialization)."""
        if self._config is None:
            logger.info("Settings not initialized, loading configuration lazily")
            self.initialize()
    
    # IMAP Configuration Getters
    
    def get_imap_server(self) -> str:
        """Get IMAP server hostname."""
        self._ensure_initialized()
        return self._config.imap.server
    
    def get_imap_port(self) -> int:
        """Get IMAP server port."""
        self._ensure_initialized()
        return self._config.imap.port
    
    def get_imap_username(self) -> str:
        """Get IMAP username."""
        self._ensure_initialized()
        return self._config.imap.username
    
    def get_imap_password(self) -> str:
        """
        Get IMAP password from environment variable.
        
        Returns:
            IMAP password from environment variable
            
        Raises:
            ConfigError: If password environment variable is not set
        """
        self._ensure_initialized()
        password_env = self._config.imap.password_env
        password = os.environ.get(password_env)
        if not password:
            raise ConfigError(f"IMAP password environment variable '{password_env}' is not set (security requirement)")
        return password
    
    def get_imap_query(self) -> str:
        """Get IMAP search query."""
        self._ensure_initialized()
        return self._config.imap.query
    
    def get_imap_processed_tag(self) -> str:
        """Get IMAP flag name for processed emails."""
        self._ensure_initialized()
        return self._config.imap.processed_tag
    
    def get_imap_application_flags(self) -> list[str]:
        """Get list of application-specific IMAP flags for cleanup command."""
        self._ensure_initialized()
        return self._config.imap.application_flags
    
    # Paths Configuration Getters
    
    def get_template_file(self) -> str:
        """Get path to Jinja2 template file."""
        self._ensure_initialized()
        return self._config.paths.template_file
    
    def get_obsidian_vault(self) -> str:
        """Get path to Obsidian vault directory."""
        self._ensure_initialized()
        return self._config.paths.obsidian_vault
    
    def get_log_file(self) -> str:
        """Get path to operational log file."""
        self._ensure_initialized()
        return self._config.paths.log_file
    
    def get_analytics_file(self) -> str:
        """Get path to structured analytics file (JSONL)."""
        self._ensure_initialized()
        return self._config.paths.analytics_file
    
    def get_changelog_path(self) -> str:
        """Get path to changelog/audit log file."""
        self._ensure_initialized()
        return self._config.paths.changelog_path
    
    def get_prompt_file(self) -> str:
        """Get path to LLM prompt file."""
        self._ensure_initialized()
        return self._config.paths.prompt_file
    
    # OpenRouter Configuration Getters (shared settings)
    
    def get_openrouter_api_key(self) -> str:
        """
        Get OpenRouter API key from environment variable.
        
        Returns:
            OpenRouter API key from environment variable
            
        Raises:
            ConfigError: If API key environment variable is not set
        """
        self._ensure_initialized()
        api_key_env = self._config.openrouter.api_key_env
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ConfigError(f"OpenRouter API key environment variable '{api_key_env}' is not set (security requirement)")
        return api_key
    
    def get_openrouter_api_url(self) -> str:
        """Get OpenRouter API endpoint URL."""
        self._ensure_initialized()
        return self._config.openrouter.api_url
    
    # Classification Configuration Getters
    
    def get_classification_model(self) -> str:
        """Get LLM model name for classification."""
        self._ensure_initialized()
        return self._config.classification.model
    
    def get_classification_temperature(self) -> float:
        """Get LLM temperature setting for classification."""
        self._ensure_initialized()
        return self._config.classification.temperature
    
    def get_classification_retry_attempts(self) -> int:
        """Get number of retry attempts for classification API calls."""
        self._ensure_initialized()
        return self._config.classification.retry_attempts
    
    def get_classification_retry_delay_seconds(self) -> int:
        """Get initial retry delay in seconds for classification."""
        self._ensure_initialized()
        return self._config.classification.retry_delay_seconds
    
    # Summarization Configuration Getters
    
    def get_summarization_model(self) -> str:
        """Get LLM model name for summarization."""
        self._ensure_initialized()
        return self._config.summarization.model
    
    def get_summarization_temperature(self) -> float:
        """Get LLM temperature setting for summarization."""
        self._ensure_initialized()
        return self._config.summarization.temperature
    
    def get_summarization_retry_attempts(self) -> int:
        """Get number of retry attempts for summarization API calls."""
        self._ensure_initialized()
        return self._config.summarization.retry_attempts
    
    def get_summarization_retry_delay_seconds(self) -> int:
        """Get initial retry delay in seconds for summarization."""
        self._ensure_initialized()
        return self._config.summarization.retry_delay_seconds
    
    # Backward compatibility: Keep old method names that map to classification
    def get_openrouter_model(self) -> str:
        """Get LLM model name (backward compatibility - returns classification model)."""
        return self.get_classification_model()
    
    def get_openrouter_temperature(self) -> float:
        """Get LLM temperature setting (backward compatibility - returns classification temperature)."""
        return self.get_classification_temperature()
    
    def get_openrouter_retry_attempts(self) -> int:
        """Get number of retry attempts (backward compatibility - returns classification retry attempts)."""
        return self.get_classification_retry_attempts()
    
    def get_openrouter_retry_delay_seconds(self) -> int:
        """Get initial retry delay (backward compatibility - returns classification retry delay)."""
        return self.get_classification_retry_delay_seconds()
    
    # Processing Configuration Getters
    
    def get_importance_threshold(self) -> int:
        """Get minimum importance score threshold (0-10)."""
        self._ensure_initialized()
        return self._config.processing.importance_threshold
    
    def get_spam_threshold(self) -> int:
        """Get maximum spam score threshold (0-10)."""
        self._ensure_initialized()
        return self._config.processing.spam_threshold
    
    def get_max_body_chars(self) -> int:
        """Get maximum characters to send to LLM."""
        self._ensure_initialized()
        return self._config.processing.max_body_chars
    
    def get_max_emails_per_run(self) -> int:
        """Get maximum number of emails to process per execution."""
        self._ensure_initialized()
        return self._config.processing.max_emails_per_run


# Singleton instance - import this in other modules
settings = Settings()
