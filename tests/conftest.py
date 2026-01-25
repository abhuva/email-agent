"""
Test fixtures and helpers for V4 email agent tests.

This module provides comprehensive test infrastructure including:
- V4 configuration fixtures
- Mock IMAP server fixtures
- Mock LLM API fixtures
- Test email data fixtures
- Dry-run test helpers
"""
import pytest
import imaplib
import json
import os
import yaml
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# ============================================================================
# V4 Configuration Fixtures
# ============================================================================

@pytest.fixture
def v3_config_dict():
    """Return a complete V3 config dictionary matching PDD Section 3.1."""
    return {
        'imap': {
            'server': 'test.imap.com',
            'port': 993,
            'username': 'test@example.com',
            'password_env': 'IMAP_PASSWORD',
            'query': 'UNSEEN',
            'processed_tag': 'AIProcessed',
            'application_flags': ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']
        },
        'paths': {
            'template_file': 'config/note_template.md.j2',
            'obsidian_vault': '/tmp/test_vault',
            'log_file': 'logs/agent.log',
            'analytics_file': 'logs/analytics.jsonl',
            'changelog_path': 'logs/email_changelog.md',
            'prompt_file': 'config/prompt.md'
        },
        'openrouter': {
            'api_key_env': 'OPENROUTER_API_KEY',
            'api_url': 'https://openrouter.ai/api/v1'
        },
        'classification': {
            'model': 'test-model',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 1
        },
        'summarization': {
            'model': 'test-model',
            'temperature': 0.3,
            'retry_attempts': 3,
            'retry_delay_seconds': 1
        },
        'processing': {
            'importance_threshold': 8,
            'spam_threshold': 5,
            'max_body_chars': 4000,
            'max_emails_per_run': 15
        }
    }


@pytest.fixture
def v4_config_file(tmp_path, v4_config_dict):
    """Create a temporary V4 config.yaml file with all required files."""
    # Create directory structure
    test_dir = tmp_path / "test_config"
    test_dir.mkdir()
    (test_dir / "config").mkdir()
    (test_dir / "logs").mkdir()
    (test_dir / "vault").mkdir()  # Obsidian vault
    
    # Create required files
    prompt_file = test_dir / "config" / "prompt.md"
    prompt_file.write_text("# Test Prompt\n\nAnalyze this email.")
    
    template_file = test_dir / "config" / "note_template.md.j2"
    template_file.write_text("---\nuid: {{ uid }}\n---\n\n# {{ subject }}\n\n{{ body }}")
    
    # Create config file
    config_file = test_dir / "config.yaml"
    # Update paths to be relative to test_dir
    v4_config_dict['paths']['obsidian_vault'] = str(test_dir / "vault")
    v4_config_dict['paths']['template_file'] = str(template_file)
    v4_config_dict['paths']['prompt_file'] = str(prompt_file)
    v4_config_dict['paths']['log_file'] = str(test_dir / "logs" / "agent.log")
    v4_config_dict['paths']['analytics_file'] = str(test_dir / "logs" / "analytics.jsonl")
    v4_config_dict['paths']['changelog_path'] = str(test_dir / "logs" / "email_changelog.md")
    
    with open(config_file, 'w') as f:
        yaml.dump(v4_config_dict, f)
    
    return str(config_file)


@pytest.fixture
def v4_config_file_minimal(tmp_path):
    """Create a minimal V4 config file for testing validation errors."""
    test_dir = tmp_path / "test_config"
    test_dir.mkdir()
    (test_dir / "config").mkdir()
    (test_dir / "vault").mkdir()
    
    prompt_file = test_dir / "config" / "prompt.md"
    prompt_file.write_text("# Test")
    
    template_file = test_dir / "config" / "note_template.md.j2"
    template_file.write_text("Test")
    
    config_file = test_dir / "config.yaml"
    config_data = {
        'imap': {
            'server': 'test.imap.com',
            'username': 'test@example.com',
            'password_env': 'IMAP_PASSWORD'
        },
        'paths': {
            'obsidian_vault': str(test_dir / "vault"),
            'template_file': str(template_file),
            'prompt_file': str(prompt_file)
        },
        'openrouter': {
            'model': 'test-model',
            'api_key_env': 'OPENROUTER_API_KEY'
        },
        'processing': {}
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    return str(config_file)


@pytest.fixture
def valid_env_file(tmp_path):
    """Create a valid .env file with required environment variables."""
    content = "IMAP_PASSWORD=test_password\nOPENROUTER_API_KEY=test_api_key\n"
    p = tmp_path / ".env"
    p.write_text(content)
    return str(p)


@pytest.fixture
def mock_config_loader(monkeypatch, v4_config_dict):
    """Mock ConfigLoader for testing."""
    from src.config_loader import ConfigLoader
    
    config_loader_mock = Mock(spec=ConfigLoader)
    config_loader_mock.load.return_value = v4_config_dict
    config_loader_mock.get.return_value = None  # Default get behavior
    
    # Mock get method to access nested config values
    def mock_get(key, default=None):
        keys = key.split('.')
        value = v4_config_dict
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    config_loader_mock.get.side_effect = mock_get
    
    return config_loader_mock


# ============================================================================
# Legacy Config Fixtures (for backward compatibility)
# ============================================================================

@pytest.fixture
def valid_config_path(tmp_path):
    """Legacy V2 config format for backward compatibility."""
    content = '''
imap:
  server: 'mail.example.com'
  port: 993
  username: 'testuser'
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
  api_url: 'https://openrouter.ai/api/v1/ai-task'
'''
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def invalid_config_path(tmp_path):
    """Invalid config file for testing validation."""
    content = "openrouter: {}"
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def invalid_env_file(tmp_path):
    """Invalid .env file for testing."""
    content = """IMAP_PASSWORD=\n"""
    p = tmp_path / ".env"
    p.write_text(content)
    return str(p)


# ============================================================================
# Mock IMAP Server Fixtures
# ============================================================================

@pytest.fixture
def mock_imap_connection():
    """Create a mock IMAP connection with standard methods."""
    mock_imap = MagicMock(spec=imaplib.IMAP4_SSL)
    mock_imap.select.return_value = ('OK', [b'1'])
    mock_imap.search.return_value = ('OK', [b'1 2 3'])
    mock_imap.fetch.return_value = ('OK', [(b'1 (UID 12345 FLAGS (\\Seen))', b'email data')])
    mock_imap.store.return_value = ('OK', [b'FLAGS updated'])
    mock_imap.logout.return_value = ('OK', [b'Logged out'])
    return mock_imap


@pytest.fixture
def mock_imap_connection_starttls():
    """Create a mock IMAP connection with STARTTLS (port 143)."""
    mock_imap = MagicMock(spec=imaplib.IMAP4)
    mock_imap.starttls.return_value = ('OK', [b'STARTTLS successful'])
    mock_imap.select.return_value = ('OK', [b'1'])
    mock_imap.search.return_value = ('OK', [b'1 2 3'])
    mock_imap.fetch.return_value = ('OK', [(b'1 (UID 12345 FLAGS (\\Seen))', b'email data')])
    mock_imap.store.return_value = ('OK', [b'FLAGS updated'])
    mock_imap.logout.return_value = ('OK', [b'Logged out'])
    return mock_imap


@pytest.fixture
def mock_imap_client():
    """Create a fully configured mock IMAP client."""
    client = Mock()
    client.connect = Mock()
    client.disconnect = Mock()
    client.get_email_by_uid = Mock()
    client.get_unprocessed_emails = Mock(return_value=[])
    client.is_processed = Mock(return_value=False)
    client.set_flag = Mock(return_value=True)
    client.remove_flag = Mock(return_value=True)
    client._connected = True
    client._imap = Mock()
    return client


@pytest.fixture
def mock_imap_connection_error():
    """Mock IMAP connection that raises errors."""
    mock_imap = MagicMock()
    mock_imap.login.side_effect = imaplib.IMAP4.error('Authentication failed')
    return mock_imap


# ============================================================================
# Mock LLM API Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_response_success():
    """Mock successful LLM API response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 2, "importance_score": 9}'
            }
        }]
    }
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200
    return mock_response


@pytest.fixture
def mock_llm_response_error():
    """Mock LLM API response with error."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception('API Error')
    mock_response.status_code = 500
    return mock_response


@pytest.fixture
def mock_llm_client():
    """Create a fully configured mock LLM client."""
    from src.llm_client import LLMResponse
    
    client = Mock()
    response = LLMResponse(
        spam_score=2,
        importance_score=9,
        raw_response='{"spam_score": 2, "importance_score": 9}'
    )
    client.classify_email = Mock(return_value=response)
    client._api_key = 'test_api_key'
    client._api_url = 'https://openrouter.ai/api/v1'
    return client


@pytest.fixture
def mock_llm_client_error():
    """Mock LLM client that raises errors."""
    from src.llm_client import LLMAPIError
    
    client = Mock()
    client.classify_email.side_effect = LLMAPIError("API request failed")
    return client


# ============================================================================
# Test Email Data Fixtures
# ============================================================================

@pytest.fixture
def sample_email_data():
    """Basic sample email data."""
    return {
        'uid': '12345',
        'subject': 'Test Email',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'date': '2024-01-01T12:00:00Z',
        'body': 'This is a test email body.',
        'content_type': 'text/plain'
    }


@pytest.fixture
def sample_email_data_important():
    """Sample email that should be classified as important."""
    return {
        'uid': '12346',
        'subject': 'URGENT: Action Required',
        'from': 'boss@example.com',
        'to': ['employee@example.com'],
        'date': '2024-01-01T13:00:00Z',
        'body': 'This is an urgent email requiring immediate attention.',
        'content_type': 'text/plain'
    }


@pytest.fixture
def sample_email_data_spam():
    """Sample email that should be classified as spam."""
    return {
        'uid': '12347',
        'subject': 'You have won $1,000,000!',
        'from': 'spammer@example.com',
        'to': ['victim@example.com'],
        'date': '2024-01-01T14:00:00Z',
        'body': 'Click here to claim your prize!',
        'content_type': 'text/plain'
    }


@pytest.fixture
def sample_email_data_html():
    """Sample email with HTML content."""
    return {
        'uid': '12348',
        'subject': 'HTML Email',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'date': '2024-01-01T15:00:00Z',
        'body': '<html><body><h1>HTML Content</h1><p>This is HTML.</p></body></html>',
        'content_type': 'text/html'
    }


@pytest.fixture
def sample_email_data_large():
    """Sample email with large body content."""
    # Reduced size to avoid pytest serialization issues (4294967295 error)
    # Using 2KB instead of 10KB to prevent binary serialization overflow
    large_body = 'A' * 2000  # 2KB of content
    return {
        'uid': '12349',
        'subject': 'Large Email',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'date': '2024-01-01T16:00:00Z',
        'body': large_body,
        'content_type': 'text/plain'
    }


@pytest.fixture
def sample_email_data_multipart():
    """Sample email with multipart content."""
    return {
        'uid': '12350',
        'subject': 'Multipart Email',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'date': '2024-01-01T17:00:00Z',
        'body': 'This is a multipart email with attachments.',
        'content_type': 'multipart/mixed',
        'attachments': [
            {'filename': 'document.pdf', 'size': 1024}
        ]
    }


@pytest.fixture
def sample_email_data_thread():
    """Sample email that is part of a thread."""
    return {
        'uid': '12351',
        'subject': 'Re: Discussion Thread',
        'from': 'participant@example.com',
        'to': ['group@example.com'],
        'date': '2024-01-01T18:00:00Z',
        'body': 'This is a reply in a discussion thread.',
        'content_type': 'text/plain',
        'in_reply_to': '<message-id-123@example.com>',
        'references': ['<message-id-123@example.com>']
    }


@pytest.fixture
def sample_email_list(sample_email_data, sample_email_data_important, sample_email_data_spam):
    """List of multiple sample emails."""
    return [
        sample_email_data,
        sample_email_data_important,
        sample_email_data_spam
    ]


# ============================================================================
# Classification Result Fixtures
# ============================================================================

@pytest.fixture
def mock_classification_result():
    """Mock classification result for important email."""
    from src.decision_logic import ClassificationResult, ClassificationStatus
    
    return ClassificationResult(
        is_important=True,
        is_spam=False,
        importance_score=9,
        spam_score=2,
        confidence=0.9,
        status=ClassificationStatus.SUCCESS,
        raw_scores={'spam_score': 2, 'importance_score': 9},
        metadata={}
    )


@pytest.fixture
def mock_classification_result_spam():
    """Mock classification result for spam email."""
    from src.decision_logic import ClassificationResult, ClassificationStatus
    
    return ClassificationResult(
        is_important=False,
        is_spam=True,
        importance_score=2,
        spam_score=8,
        confidence=0.8,
        status=ClassificationStatus.SUCCESS,
        raw_scores={'spam_score': 8, 'importance_score': 2},
        metadata={}
    )


@pytest.fixture
def mock_classification_result_neutral():
    """Mock classification result for neutral email."""
    from src.decision_logic import ClassificationResult, ClassificationStatus
    
    return ClassificationResult(
        is_important=False,
        is_spam=False,
        importance_score=5,
        spam_score=3,
        confidence=0.7,
        status=ClassificationStatus.SUCCESS,
        raw_scores={'spam_score': 3, 'importance_score': 5},
        metadata={}
    )


# ============================================================================
# Dry-Run Test Helpers
# ============================================================================

@pytest.fixture
def dry_run_context():
    """Context manager fixture for dry-run mode testing."""
    from src.dry_run import DryRunContext
    return DryRunContext


@pytest.fixture
def enable_dry_run(monkeypatch):
    """Fixture to enable dry-run mode for a test."""
    from src.dry_run import set_dry_run, is_dry_run
    
    def _enable():
        set_dry_run(True)
        assert is_dry_run() is True
    
    def _disable():
        set_dry_run(False)
        assert is_dry_run() is False
    
    # Enable at start
    _enable()
    
    yield _enable, _disable
    
    # Disable at end
    _disable()


@pytest.fixture
def dry_run_helper():
    """Helper functions for dry-run testing."""
    from src.dry_run import set_dry_run, is_dry_run, DryRunContext
    
    class DryRunHelper:
        """Helper class for dry-run operations."""
        
        @staticmethod
        def enable():
            """Enable dry-run mode."""
            set_dry_run(True)
        
        @staticmethod
        def disable():
            """Disable dry-run mode."""
            set_dry_run(False)
        
        @staticmethod
        def is_enabled():
            """Check if dry-run is enabled."""
            return is_dry_run()
        
        @staticmethod
        def context(enabled: bool = True):
            """Get a dry-run context manager."""
            return DryRunContext(enabled)
        
        @staticmethod
        def assert_dry_run():
            """Assert that dry-run mode is enabled."""
            assert is_dry_run(), "Expected dry-run mode to be enabled"
        
        @staticmethod
        def assert_not_dry_run():
            """Assert that dry-run mode is disabled."""
            assert not is_dry_run(), "Expected dry-run mode to be disabled"
    
    return DryRunHelper


# ============================================================================
# Additional Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_decision_logic():
    """Mock decision logic module."""
    from src.decision_logic import ClassificationResult, ClassificationStatus
    
    logic = Mock()
    result = ClassificationResult(
        is_important=True,
        is_spam=False,
        importance_score=9,
        spam_score=2,
        confidence=0.9,
        status=ClassificationStatus.SUCCESS,
        raw_scores={'spam_score': 2, 'importance_score': 9},
        metadata={}
    )
    logic.classify = Mock(return_value=result)
    return logic


@pytest.fixture
def mock_note_generator():
    """Mock note generator."""
    generator = Mock()
    generator.generate_note = Mock(return_value='# Test Email\n\nTest content')
    return generator


@pytest.fixture
def mock_email_logger():
    """Mock email logger."""
    logger = Mock()
    logger.log_email_processed = Mock()
    logger.log_classification_result = Mock()
    return logger


@pytest.fixture
def temp_analytics_file(tmp_path):
    """Create a temporary analytics JSONL file."""
    analytics_file = tmp_path / "analytics.jsonl"
    return str(analytics_file)


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file."""
    log_file = tmp_path / "agent.log"
    return str(log_file)


@pytest.fixture
def temp_obsidian_vault(tmp_path):
    """Create a temporary Obsidian vault directory."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return str(vault_dir)
