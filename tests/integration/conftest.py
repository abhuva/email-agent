"""
Pytest fixtures for V4 integration tests.

This module provides fixtures for integration testing, including:
- Mock IMAP and LLM clients
- Test configuration setup
- Test data builders
- Common test utilities
"""

import pytest
import yaml
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, patch

from tests.integration.mock_services import MockImapClient, MockLLMClient
from tests.integration.test_utils import (
    create_test_config_dir,
    create_test_global_config,
    create_test_account_config,
    create_test_email_data,
    create_test_blacklist_rules,
    create_test_whitelist_rules,
    create_test_rules_file,
    reset_mock_services
)


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_imap_client():
    """Create a mock IMAP client for integration testing."""
    client = MockImapClient()
    yield client
    # Cleanup
    client.disconnect()
    client.clear_emails()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for integration testing."""
    client = MockLLMClient()
    yield client
    # Cleanup
    client.set_default_response()
    client._scenario_responses.clear()


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary configuration directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    accounts_dir = config_dir / "accounts"
    accounts_dir.mkdir()
    return config_dir


@pytest.fixture
def integration_global_config():
    """Global configuration for integration tests."""
    return create_test_global_config()


@pytest.fixture
def integration_account_config():
    """Account-specific configuration for integration tests."""
    return create_test_account_config()


@pytest.fixture
def integration_config_setup(temp_config_dir, integration_global_config, integration_account_config):
    """Set up complete configuration structure for integration tests."""
    # Create global config
    global_file = temp_config_dir / "config.yaml"
    with open(global_file, 'w') as f:
        yaml.dump(integration_global_config, f)
    
    # Create account config
    accounts_dir = temp_config_dir / "accounts"
    account_file = accounts_dir / "test_account.yaml"
    with open(account_file, 'w') as f:
        yaml.dump(integration_account_config, f)
    
    return {
        'config_dir': temp_config_dir,
        'global_config': integration_global_config,
        'account_config': integration_account_config,
        'account_name': 'test_account'
    }


# ============================================================================
# Rules Fixtures
# ============================================================================

@pytest.fixture
def integration_blacklist_rules():
    """Blacklist rules for integration tests."""
    return create_test_blacklist_rules()


@pytest.fixture
def integration_whitelist_rules():
    """Whitelist rules for integration tests."""
    return create_test_whitelist_rules()


@pytest.fixture
def integration_rules_files(temp_config_dir, integration_blacklist_rules, integration_whitelist_rules):
    """Create rules files for integration tests."""
    blacklist_file = create_test_rules_file(temp_config_dir, 'blacklist.yaml', integration_blacklist_rules)
    whitelist_file = create_test_rules_file(temp_config_dir, 'whitelist.yaml', integration_whitelist_rules)
    
    return {
        'blacklist_file': blacklist_file,
        'whitelist_file': whitelist_file,
        'blacklist_rules': integration_blacklist_rules,
        'whitelist_rules': integration_whitelist_rules
    }


# ============================================================================
# Email Data Fixtures
# ============================================================================

@pytest.fixture
def sample_email_data():
    """Sample email data for integration tests."""
    return create_test_email_data()


@pytest.fixture
def multiple_email_data():
    """Multiple email data items for integration tests."""
    return [
        create_test_email_data(uid="1", sender="test1@example.com", subject="Email 1"),
        create_test_email_data(uid="2", sender="test2@example.com", subject="Email 2"),
        create_test_email_data(uid="3", sender="test3@example.com", subject="Email 3"),
    ]


# ============================================================================
# Test Helper Fixtures
# ============================================================================

@pytest.fixture
def reset_mocks(mock_imap_client, mock_llm_client):
    """Fixture that resets mocks before each test."""
    reset_mock_services(mock_imap_client, mock_llm_client)
    yield
    reset_mock_services(mock_imap_client, mock_llm_client)


# ============================================================================
# Factory Fixtures
# ============================================================================

@pytest.fixture
def create_imap_client_factory(mock_imap_client):
    """Factory function that returns the mock IMAP client."""
    def _factory(config: Dict[str, Any]):
        return mock_imap_client
    return _factory


@pytest.fixture
def create_llm_client_factory(mock_llm_client):
    """Factory function that returns the mock LLM client."""
    def _factory():
        return mock_llm_client
    return _factory
