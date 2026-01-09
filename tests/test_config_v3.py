"""
Tests for V3 configuration system.

These tests verify the V3 configuration schema, loader, and settings facade.
"""
import os
import pytest
import tempfile
import yaml
from pathlib import Path

from src.config_v3_schema import V3ConfigSchema, ImapConfig, PathsConfig, OpenRouterConfig, ProcessingConfig
from src.config_v3_loader import ConfigLoader
from src.config import ConfigError
from src.settings import Settings


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary V3 config file for testing with required files."""
    # Create test directory structure
    test_dir = tmp_path / "test_config"
    test_dir.mkdir()
    (test_dir / "config").mkdir()
    (test_dir / "logs").mkdir()
    
    # Create required files
    prompt_file = test_dir / "config" / "prompt.md"
    prompt_file.write_text("# Test Prompt")
    
    template_file = test_dir / "config" / "note_template.md.j2"
    template_file.write_text("# Test Template")
    
    # Create config file
    config_file = test_dir / "config.yaml"
    config_data = {
        'imap': {
            'server': 'test.imap.com',
            'port': 143,
            'username': 'test@example.com',
            'password_env': 'TEST_IMAP_PASSWORD',
            'query': 'UNSEEN',
            'processed_tag': 'AIProcessed'
        },
        'paths': {
            'template_file': str(template_file),
            'obsidian_vault': str(test_dir),  # Use test dir as vault
            'log_file': str(test_dir / "logs" / "test.log"),
            'analytics_file': str(test_dir / "logs" / "test_analytics.jsonl"),
            'changelog_path': str(test_dir / "logs" / "test_changelog.md"),
            'prompt_file': str(prompt_file)
        },
        'openrouter': {
            'api_key_env': 'TEST_OPENROUTER_API_KEY',
            'api_url': 'https://openrouter.ai/api/v1'
        },
        'classification': {
            'model': 'test-model',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
        'summarization': {
            'model': 'test-model',
            'temperature': 0.3,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
        'processing': {
            'importance_threshold': 8,
            'spam_threshold': 5,
            'max_body_chars': 4000,
            'max_emails_per_run': 15
        }
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    yield str(config_file)


@pytest.fixture
def test_env_vars(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv('TEST_IMAP_PASSWORD', 'test_password')
    monkeypatch.setenv('TEST_OPENROUTER_API_KEY', 'test_api_key')


def test_v3_config_schema_validation(temp_config_file, test_env_vars):
    """Test that V3 config schema validates correctly."""
    loader = ConfigLoader(temp_config_file)
    config = loader.load()
    
    assert isinstance(config, V3ConfigSchema)
    assert config.imap.server == 'test.imap.com'
    assert config.imap.port == 143
    assert config.classification.model == 'test-model'
    assert config.processing.importance_threshold == 8
    assert os.path.exists(config.paths.prompt_file)
    assert os.path.exists(config.paths.template_file)


def test_v3_config_loader_missing_file():
    """Test that loader raises error for missing file."""
    with pytest.raises(ConfigError, match="Configuration file not found"):
        loader = ConfigLoader('nonexistent.yaml')
        loader.load()


def test_v3_config_loader_invalid_yaml(tmp_path):
    """Test that loader handles invalid YAML."""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("invalid: yaml: content: [")
    
    loader = ConfigLoader(str(config_file))
    with pytest.raises(ConfigError, match="YAML parse error"):
        loader.load()


def test_v3_settings_facade(temp_config_file, test_env_vars):
    """Test that settings facade provides access to all config values."""
    settings = Settings()
    settings.initialize(temp_config_file, '.env')
    
    # Test IMAP getters
    assert settings.get_imap_server() == 'test.imap.com'
    assert settings.get_imap_port() == 143
    assert settings.get_imap_username() == 'test@example.com'
    assert settings.get_imap_password() == 'test_password'
    assert settings.get_imap_query() == 'UNSEEN'
    assert settings.get_imap_processed_tag() == 'AIProcessed'
    
    # Test Paths getters (using actual paths from fixture)
    template_file = settings.get_template_file()
    prompt_file = settings.get_prompt_file()
    log_file = settings.get_log_file()
    analytics_file = settings.get_analytics_file()
    
    assert os.path.exists(template_file)
    assert os.path.exists(prompt_file)
    assert 'note_template.md.j2' in template_file
    assert 'prompt.md' in prompt_file
    assert 'test.log' in log_file
    assert 'test_analytics.jsonl' in analytics_file
    
    # Test OpenRouter getters
    assert settings.get_openrouter_api_key() == 'test_api_key'
    assert settings.get_openrouter_api_url() == 'https://openrouter.ai/api/v1'
    assert settings.get_openrouter_model() == 'test-model'
    assert settings.get_openrouter_temperature() == 0.2
    assert settings.get_openrouter_retry_attempts() == 3
    assert settings.get_openrouter_retry_delay_seconds() == 5
    
    # Test Processing getters
    assert settings.get_importance_threshold() == 8
    assert settings.get_spam_threshold() == 5
    assert settings.get_max_body_chars() == 4000
    assert settings.get_max_emails_per_run() == 15


def test_v3_settings_facade_missing_env_var(temp_config_file):
    """Test that settings facade raises error when env var is missing."""
    settings = Settings()
    settings.initialize(temp_config_file, '.env')
    
    # Should raise error when password env var is not set
    with pytest.raises(ConfigError, match="IMAP password environment variable"):
        settings.get_imap_password()
    
    with pytest.raises(ConfigError, match="OpenRouter API key environment variable"):
        settings.get_openrouter_api_key()


def test_v3_settings_facade_singleton():
    """Test that Settings implements singleton pattern."""
    settings1 = Settings()
    settings2 = Settings()
    
    assert settings1 is settings2


def test_v3_config_env_overrides(temp_config_file, test_env_vars, monkeypatch):
    """Test that environment variable overrides work."""
    # Set override environment variables
    monkeypatch.setenv('EMAIL_AGENT_IMAP_SERVER', 'override.imap.com')
    monkeypatch.setenv('EMAIL_AGENT_CLASSIFICATION_MODEL', 'override-model')
    monkeypatch.setenv('EMAIL_AGENT_PROCESSING_IMPORTANCE_THRESHOLD', '7')
    
    loader = ConfigLoader(temp_config_file)
    config = loader.load()
    
    # Verify overrides were applied
    assert config.imap.server == 'override.imap.com'
    assert config.classification.model == 'override-model'
    assert config.processing.importance_threshold == 7


def test_v3_config_schema_validation_errors():
    """Test that schema validation catches invalid values."""
    # Test invalid port
    with pytest.raises(Exception):  # Pydantic ValidationError
        ImapConfig(server='test.com', port=70000, username='test', password_env='TEST')
    
    # Test invalid temperature
    with pytest.raises(Exception):  # Pydantic ValidationError
        OpenRouterConfig(api_key_env='TEST', api_url='http://test.com', model='test', temperature=3.0)
    
    # Test invalid threshold
    with pytest.raises(Exception):  # Pydantic ValidationError
        ProcessingConfig(importance_threshold=15, spam_threshold=5, max_body_chars=4000, max_emails_per_run=15)
