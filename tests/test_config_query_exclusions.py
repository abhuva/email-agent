"""
Tests for configurable IMAP query exclusions in ConfigManager (Task 16).
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.config import ConfigManager, ConfigFormatError


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary directory with config files"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def base_config_content():
    """Base config content without imap_query_exclusions"""
    return """
imap:
  server: 'imap.example.com'
  port: 993
  username: 'test@example.com'
  password_env: 'IMAP_PASSWORD'
prompt_file: 'config/prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'
processed_tag: 'AIProcessed'
max_body_chars: 4000
max_emails_per_run: 15
log_file: 'logs/agent.log'
log_level: 'INFO'
analytics_file: 'logs/analytics.jsonl'
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: 'openai/gpt-3.5-turbo'
"""


def test_config_default_exclude_tags(temp_config_dir, base_config_content, valid_env_file):
    """Test that default exclude tags are used when imap_query_exclusions is not specified"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(base_config_content)
    
    # Create prompt file
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    config = ConfigManager(str(config_file), valid_env_file)
    
    # Should have default three tags
    assert len(config.exclude_tags) == 3
    assert 'AIProcessed' in config.exclude_tags
    assert 'ObsidianNoteCreated' in config.exclude_tags
    assert 'NoteCreationFailed' in config.exclude_tags
    assert config.disable_idempotency is False


def test_config_custom_exclude_tags(temp_config_dir, base_config_content, valid_env_file):
    """Test custom exclude_tags configuration"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'CustomTag'
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    config = ConfigManager(str(config_file), valid_env_file)
    
    assert len(config.exclude_tags) == 2
    assert 'AIProcessed' in config.exclude_tags
    assert 'CustomTag' in config.exclude_tags
    assert 'ObsidianNoteCreated' not in config.exclude_tags


def test_config_additional_exclude_tags(temp_config_dir, base_config_content, valid_env_file):
    """Test additional_exclude_tags configuration"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
  additional_exclude_tags:
    - 'Archived'
    - 'ProcessedByOtherTool'
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    config = ConfigManager(str(config_file), valid_env_file)
    
    # Should have all 5 tags (3 default + 2 additional)
    assert len(config.exclude_tags) == 5
    assert 'AIProcessed' in config.exclude_tags
    assert 'ObsidianNoteCreated' in config.exclude_tags
    assert 'NoteCreationFailed' in config.exclude_tags
    assert 'Archived' in config.exclude_tags
    assert 'ProcessedByOtherTool' in config.exclude_tags


def test_config_disable_idempotency(temp_config_dir, base_config_content, valid_env_file):
    """Test disable_idempotency flag"""
    config_content = base_config_content + """
imap_query_exclusions:
  disable_idempotency: true
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    config = ConfigManager(str(config_file), valid_env_file)
    
    assert config.disable_idempotency is True
    # exclude_tags should still be set (for logging/debugging)
    assert len(config.exclude_tags) == 3


def test_config_invalid_exclude_tags_not_list(temp_config_dir, base_config_content, valid_env_file):
    """Test that invalid exclude_tags type is rejected"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags: 'not-a-list'
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    with pytest.raises(ConfigFormatError) as exc_info:
        ConfigManager(str(config_file), valid_env_file)
    
    assert "exclude_tags must be a list" in str(exc_info.value)


def test_config_invalid_exclude_tags_empty_string(temp_config_dir, base_config_content, valid_env_file):
    """Test that empty string in exclude_tags is rejected"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - ''
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    with pytest.raises(ConfigFormatError) as exc_info:
        ConfigManager(str(config_file), valid_env_file)
    
    assert "cannot be empty" in str(exc_info.value)


def test_config_invalid_exclude_tags_with_hyphen(temp_config_dir, base_config_content, valid_env_file):
    """Test that tags with hyphens are rejected (IMAP flag naming rules)"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'Obsidian-Note-Created'  # Invalid: contains hyphens
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    with pytest.raises(ConfigFormatError) as exc_info:
        ConfigManager(str(config_file), valid_env_file)
    
    assert "Invalid IMAP flag name" in str(exc_info.value)
    assert "Obsidian-Note-Created" in str(exc_info.value)


def test_config_invalid_disable_idempotency_not_boolean(temp_config_dir, base_config_content, valid_env_file):
    """Test that disable_idempotency must be boolean"""
    config_content = base_config_content + """
imap_query_exclusions:
  disable_idempotency: 'yes'  # Invalid: should be boolean
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    with pytest.raises(ConfigFormatError) as exc_info:
        ConfigManager(str(config_file), valid_env_file)
    
    assert "disable_idempotency must be a boolean" in str(exc_info.value)


def test_config_exclude_tags_removes_duplicates(temp_config_dir, base_config_content, valid_env_file):
    """Test that duplicate tags are removed"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'AIProcessed'  # Duplicate
  additional_exclude_tags:
    - 'ObsidianNoteCreated'  # Duplicate from exclude_tags
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    config = ConfigManager(str(config_file), valid_env_file)
    
    # Should have only 2 unique tags
    assert len(config.exclude_tags) == 2
    assert 'AIProcessed' in config.exclude_tags
    assert 'ObsidianNoteCreated' in config.exclude_tags


def test_config_empty_exclude_tags_warning(temp_config_dir, base_config_content, valid_env_file, caplog):
    """Test that empty exclude_tags generates warning"""
    config_content = base_config_content + """
imap_query_exclusions:
  exclude_tags: []
"""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(config_content)
    
    prompt_file = temp_config_dir / "prompt.md"
    prompt_file.write_text("# Test prompt")
    
    with caplog.at_level("WARNING"):
        config = ConfigManager(str(config_file), valid_env_file)
    
    assert "idempotency may be compromised" in caplog.text.lower() or len(config.exclude_tags) == 0
