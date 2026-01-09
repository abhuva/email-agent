import os
import pytest
from src.config import (
    load_yaml_config, validate_yaml_config,
    load_env_vars, validate_env_vars, ConfigError, ConfigManager
)


def test_load_yaml_config_valid(valid_config_path):
    config = load_yaml_config(valid_config_path)
    assert isinstance(config, dict)
    assert 'imap' in config

def test_load_yaml_config_invalid(invalid_config_path):
    config = load_yaml_config(invalid_config_path)
    assert 'imap' not in config

def test_validate_yaml_config_valid(valid_config_path):
    config = load_yaml_config(valid_config_path)
    assert validate_yaml_config(config)

def test_validate_yaml_config_invalid(invalid_config_path):
    config = load_yaml_config(invalid_config_path)
    with pytest.raises(ConfigError):
        validate_yaml_config(config)

def test_load_env_valid(valid_env_file, valid_config_path):
    os.environ.pop('IMAP_PASSWORD', None)
    os.environ.pop('OPENROUTER_API_KEY', None)
    load_env_vars(valid_env_file)
    config = load_yaml_config(valid_config_path)
    assert 'IMAP_PASSWORD' in os.environ
    assert 'OPENROUTER_API_KEY' in os.environ
    assert validate_env_vars(config)

def test_load_env_invalid(invalid_env_file, valid_config_path):
    os.environ.pop('IMAP_PASSWORD', None)
    os.environ.pop('OPENROUTER_API_KEY', None)
    load_env_vars(invalid_env_file)
    config = load_yaml_config(valid_config_path)
    with pytest.raises(ConfigError):
        validate_env_vars(config)

def test_config_manager_valid(valid_config_path, valid_env_file):
    os.environ.pop('IMAP_PASSWORD', None)
    os.environ.pop('OPENROUTER_API_KEY', None)
    # The manager constructor loads and validates on instantiation
    load_env_vars(valid_env_file)
    cm = ConfigManager(valid_config_path, valid_env_file)
    assert cm.imap['server'] == 'mail.example.com'
    assert cm.imap_password == 'test_password'  # Matches valid_env_file fixture
    assert cm.openrouter_api_key == 'test_api_key'  # Matches valid_env_file fixture
    assert isinstance(cm.tag_mapping, dict)
    assert cm.max_body_chars == 4000
    assert isinstance(cm.imap_connection_params(), dict)
    assert isinstance(cm.openrouter_params(), dict)

def test_config_manager_missing_env(valid_config_path):
    os.environ.pop('IMAP_PASSWORD', None)
    os.environ.pop('OPENROUTER_API_KEY', None)
    with pytest.raises(ConfigError):
        ConfigManager(valid_config_path, 'tests/missing.env')
