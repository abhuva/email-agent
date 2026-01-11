"""
Test fixtures and utilities for V4 core components unit tests.

This module provides test infrastructure specifically for V4 components:
- ConfigLoader fixtures
- Rules engine fixtures
- ContentParser fixtures
- AccountProcessor fixtures
- MasterOrchestrator fixtures
- Test data builders and factories
- Mock helpers for isolated unit testing

Test Isolation:
    All fixtures are designed to ensure complete isolation between tests.
    Each test should be able to run independently without side effects.
"""
import pytest
import yaml
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List, Optional

# ============================================================================
# V4 Configuration Fixtures
# ============================================================================

@pytest.fixture
def v4_global_config_dict():
    """Sample V4 global configuration dictionary."""
    return {
        'imap': {
            'server': 'global.imap.com',
            'port': 993,
            'username': 'global@example.com',
            'password': 'global_password',
            'query': 'ALL',
            'processed_tag': 'AIProcessed'
        },
        'paths': {
            'obsidian_vault': '/global/vault',
            'log_file': 'logs/global.log'
        },
        'processing': {
            'importance_threshold': 7,
            'spam_threshold': 5,
            'max_emails_per_run': 10
        },
        'classification': {
            'model': 'test-model',
            'temperature': 0.2
        }
    }


@pytest.fixture
def v4_account_config_dict():
    """Sample V4 account-specific configuration dictionary."""
    return {
        'imap': {
            'server': 'account.imap.com',
            'username': 'account@example.com',
            'port': 143  # Override port
        },
        'paths': {
            'obsidian_vault': '/account/vault'  # Override vault
        },
        'processing': {
            'importance_threshold': 8  # Override threshold
        }
    }


@pytest.fixture
def temp_v4_config_dir(tmp_path):
    """Create a temporary V4 config directory structure."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    accounts_dir = config_dir / "accounts"
    accounts_dir.mkdir()
    
    return config_dir


@pytest.fixture
def v4_global_config_file(temp_v4_config_dir, v4_global_config_dict):
    """Create a temporary V4 global config.yaml file."""
    config_file = temp_v4_config_dir / "config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(v4_global_config_dict, f)
    return config_file


@pytest.fixture
def v4_account_config_file(temp_v4_config_dir, v4_account_config_dict):
    """Create a temporary V4 account config file."""
    account_file = temp_v4_config_dir / "accounts" / "test_account.yaml"
    with open(account_file, 'w') as f:
        yaml.dump(v4_account_config_dict, f)
    return account_file


# ============================================================================
# Rules Engine Fixtures
# ============================================================================

@pytest.fixture
def sample_blacklist_rules():
    """Sample blacklist rules for testing."""
    return [
        {
            'trigger': 'sender',
            'value': 'spam@example.com',
            'action': 'drop'
        },
        {
            'trigger': 'domain',
            'value': 'spam.com',
            'action': 'record'
        },
        {
            'trigger': 'subject',
            'value': 'URGENT.*',
            'action': 'drop'
        }
    ]


@pytest.fixture
def sample_whitelist_rules():
    """Sample whitelist rules for testing."""
    return [
        {
            'trigger': 'sender',
            'value': 'important@example.com',
            'action': 'boost',
            'score_boost': 20,
            'add_tags': ['#important', '#work']
        },
        {
            'trigger': 'domain',
            'value': 'client.com',
            'action': 'boost',
            'score_boost': 15,
            'add_tags': ['#client']
        }
    ]


@pytest.fixture
def blacklist_rules_file(tmp_path, sample_blacklist_rules):
    """Create a temporary blacklist rules YAML file."""
    rules_file = tmp_path / "blacklist.yaml"
    with open(rules_file, 'w') as f:
        yaml.dump(sample_blacklist_rules, f)
    return rules_file


@pytest.fixture
def whitelist_rules_file(tmp_path, sample_whitelist_rules):
    """Create a temporary whitelist rules YAML file."""
    rules_file = tmp_path / "whitelist.yaml"
    with open(rules_file, 'w') as f:
        yaml.dump(sample_whitelist_rules, f)
    return rules_file


# ============================================================================
# EmailContext Test Data Builders
# ============================================================================

@pytest.fixture
def email_context_builder():
    """Builder fixture for creating EmailContext test objects."""
    from src.models import EmailContext
    
    class EmailContextBuilder:
        """Builder for creating EmailContext test objects."""
        
        def __init__(self):
            self.uid = "12345"
            self.sender = "test@example.com"
            self.subject = "Test Email"
            self.raw_html = "<p>Test HTML</p>"
            self.raw_text = "Test HTML"
            self.parsed_body = ""
            self.is_html_fallback = False
        
        def with_uid(self, uid: str):
            self.uid = uid
            return self
        
        def with_sender(self, sender: str):
            self.sender = sender
            return self
        
        def with_subject(self, subject: str):
            self.subject = subject
            return self
        
        def with_html(self, html: str):
            self.raw_html = html
            return self
        
        def with_text(self, text: str):
            self.raw_text = text
            return self
        
        def with_parsed_body(self, body: str):
            self.parsed_body = body
            return self
        
        def with_fallback(self, is_fallback: bool):
            self.is_html_fallback = is_fallback
            return self
        
        def build(self) -> EmailContext:
            """Build EmailContext instance."""
            return EmailContext(
                uid=self.uid,
                sender=self.sender,
                subject=self.subject,
                raw_html=self.raw_html,
                raw_text=self.raw_text,
                parsed_body=self.parsed_body,
                is_html_fallback=self.is_html_fallback
            )
    
    return EmailContextBuilder


@pytest.fixture
def sample_email_context(email_context_builder):
    """Sample EmailContext for testing."""
    return email_context_builder.build()


# ============================================================================
# Mock Service Fixtures for V4 Components
# ============================================================================

@pytest.fixture
def mock_config_loader():
    """Mock ConfigLoader for testing."""
    loader = Mock()
    loader.load_global_config = Mock(return_value={})
    loader.load_account_config = Mock(return_value={})
    loader.load_merged_config = Mock(return_value={})
    loader.get_last_validation_result = Mock(return_value=None)
    loader.validate_config = Mock(return_value=Mock(is_valid=True, errors=[], warnings=[]))
    return loader


@pytest.fixture
def mock_imap_client_v4():
    """Mock IMAP client for V4 testing."""
    client = Mock()
    client.connect = Mock()
    client.disconnect = Mock()
    client.fetch_emails = Mock(return_value=[])
    client.fetch_email_by_uid = Mock(return_value=None)
    client.set_flag = Mock(return_value=True)
    client.remove_flag = Mock(return_value=True)
    client._connected = True
    return client


@pytest.fixture
def mock_llm_client_v4():
    """Mock LLM client for V4 testing."""
    from src.llm_client import LLMResponse
    
    client = Mock()
    response = LLMResponse(
        spam_score=2,
        importance_score=9,
        raw_response='{"spam_score": 2, "importance_score": 9}'
    )
    client.classify_email = Mock(return_value=response)
    return client


@pytest.fixture
def mock_note_generator_v4():
    """Mock note generator for V4 testing."""
    generator = Mock()
    generator.generate_note = Mock(return_value='# Test Note\n\nTest content')
    return generator


@pytest.fixture
def mock_decision_logic_v4():
    """Mock decision logic for V4 testing."""
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
def mock_account_processor():
    """Mock AccountProcessor for testing MasterOrchestrator."""
    processor = Mock()
    processor.setup = Mock()
    processor.run = Mock()
    processor.teardown = Mock()
    processor.account_id = "test_account"
    return processor


# ============================================================================
# MasterOrchestrator Test Fixtures
# ============================================================================

@pytest.fixture
def mock_master_orchestrator_dependencies():
    """Mock all dependencies for MasterOrchestrator testing."""
    return {
        'config_loader': Mock(),
        'llm_client': Mock(),
        'note_generator': Mock(),
        'decision_logic': Mock()
    }


@pytest.fixture
def sample_orchestration_result():
    """Sample OrchestrationResult for testing."""
    from src.orchestrator import OrchestrationResult
    
    return OrchestrationResult(
        total_accounts=2,
        successful_accounts=2,
        failed_accounts=0,
        total_time=1.5,
        account_results={
            'work': (True, None),
            'personal': (True, None)
        }
    )


# ============================================================================
# Test Data Generators
# ============================================================================

@pytest.fixture
def config_dict_generator():
    """Generator for creating test configuration dictionaries."""
    def _generate(
        imap_server: str = "test.imap.com",
        imap_port: int = 993,
        imap_username: str = "test@example.com",
        **overrides
    ) -> Dict[str, Any]:
        """Generate a test configuration dictionary."""
        config = {
            'imap': {
                'server': imap_server,
                'port': imap_port,
                'username': imap_username,
                'password': 'test_password',
                'query': 'ALL',
                'processed_tag': 'AIProcessed'
            },
            'processing': {
                'max_emails_per_run': 10
            }
        }
        config.update(overrides)
        return config
    
    return _generate


@pytest.fixture
def email_data_generator():
    """Generator for creating test email data dictionaries."""
    def _generate(
        uid: str = "12345",
        sender: str = "test@example.com",
        subject: str = "Test Email",
        body: str = "Test body",
        **overrides
    ) -> Dict[str, Any]:
        """Generate test email data dictionary."""
        email = {
            'uid': uid,
            'from': sender,
            'subject': subject,
            'body': body,
            'date': '2024-01-01T12:00:00Z',
            'to': ['recipient@example.com']
        }
        email.update(overrides)
        return email
    
    return _generate
