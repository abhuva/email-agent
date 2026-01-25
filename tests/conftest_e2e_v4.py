"""
Pytest fixtures for V4 end-to-end tests.

This module provides fixtures for:
- Test account configuration loading
- Test environment setup and teardown
- Test vault management
- Test data seeding
- E2E test isolation
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Generator
import yaml

from tests.e2e_helpers import (
    get_test_accounts,
    has_test_account_credentials,
    has_any_test_account_credentials,
    get_test_account_config,
    get_account_config_path,
    load_account_config,
    get_test_vault_path,
    ensure_test_vault_exists,
    cleanup_test_vault,
    require_test_account_credentials,
    require_any_test_account_credentials,
    require_account_config
)

# Project root directory
project_root = Path(__file__).parent.parent


# ============================================================================
# Test Account Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_accounts_config():
    """
    Load test accounts configuration from config/test-accounts.yaml.
    
    Returns:
        Dictionary containing test accounts configuration.
    """
    from tests.e2e_helpers import load_test_accounts_config
    return load_test_accounts_config()


@pytest.fixture(scope="session")
def available_test_accounts():
    """
    Get list of test accounts that have credentials available.
    
    Returns:
        List of account IDs with available credentials.
    """
    from tests.e2e_helpers import get_test_accounts_with_credentials
    accounts = get_test_accounts_with_credentials()
    
    if not accounts:
        pytest.skip("No test accounts with credentials available")
    
    return accounts


@pytest.fixture
def test_account_id(available_test_accounts):
    """
    Get a single test account ID for testing.
    
    Uses the first available test account.
    """
    if not available_test_accounts:
        pytest.skip("No test accounts available")
    
    return available_test_accounts[0]


@pytest.fixture
def test_account_config(test_account_id):
    """
    Get configuration for a test account.
    
    Returns:
        Test account configuration dictionary.
    """
    require_test_account_credentials(test_account_id)
    require_account_config(test_account_id)
    
    account_info = get_test_account_config(test_account_id)
    account_yaml = load_account_config(test_account_id)
    
    return {
        'account_id': test_account_id,
        'info': account_info,
        'config': account_yaml
    }


# ============================================================================
# Test Environment Fixtures
# ============================================================================

@pytest.fixture
def e2e_test_config_dir(tmp_path):
    """
    Create a temporary test configuration directory for E2E tests.
    
    This fixture creates a temporary config directory structure:
    - config/config.yaml (global config)
    - config/accounts/ (account configs)
    - config/blacklist.yaml
    - config/whitelist.yaml
    
    Returns:
        Path to temporary config directory.
    """
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    (config_dir / 'accounts').mkdir()
    
    # Create minimal global config
    global_config = {
        'imap': {
            'server': 'imap.example.com',
            'port': 993,
            'username': 'test@example.com',
            'password_env': 'IMAP_PASSWORD',
            'query': 'UNSEEN',
            'processed_tag': 'AIProcessed'
        },
        'paths': {
            'template_file': 'config/note_template.md.j2',
            'obsidian_vault': str(tmp_path / 'vault'),
            'log_file': str(tmp_path / 'logs' / 'agent.log'),
            'analytics_file': str(tmp_path / 'logs' / 'analytics.jsonl'),
            'changelog_path': str(tmp_path / 'logs' / 'changelog.md'),
            'prompt_file': 'config/prompt.md'
        },
        'openrouter': {
            'api_key_env': 'OPENROUTER_API_KEY',
            'api_url': 'https://openrouter.ai/api/v1'
        },
        'classification': {
            'model': 'google/gemini-2.5-flash-lite-preview-09-2025',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 1,
            'cost_per_1k_tokens': 0.0001
        },
        'summarization': {
            'model': 'google/gemini-2.5-flash-lite-preview-09-2025',
            'temperature': 0.3,
            'retry_attempts': 3,
            'retry_delay_seconds': 1
        },
        'processing': {
            'importance_threshold': 8,
            'spam_threshold': 5,
            'max_body_chars': 4000,
            'max_emails_per_run': 15
        },
        'safety_interlock': {
            'enabled': True,
            'cost_threshold': 0.10,
            'skip_confirmation_below_threshold': False,
            'average_tokens_per_email': 2000,
            'currency': '$'
        }
    }
    
    with open(config_dir / 'config.yaml', 'w') as f:
        yaml.dump(global_config, f)
    
    # Create empty rules files
    with open(config_dir / 'blacklist.yaml', 'w') as f:
        yaml.dump([], f)
    
    with open(config_dir / 'whitelist.yaml', 'w') as f:
        yaml.dump([], f)
    
    # Create logs directory
    (tmp_path / 'logs').mkdir()
    
    return config_dir


@pytest.fixture
def e2e_test_vault(tmp_path):
    """
    Create a temporary test vault directory for E2E tests.
    
    Returns:
        Path to test vault directory.
    """
    vault_dir = tmp_path / 'test_vault'
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def e2e_test_account_config(e2e_test_config_dir, test_account_id, e2e_test_vault, tmp_path):
    """
    Create a test account configuration file for E2E testing.
    
    This fixture creates a temporary account config that:
    - Uses the test account's actual credentials (from env vars)
    - Points to the test vault directory
    - Uses test-safe settings (low limits, etc.)
    
    Returns:
        Dictionary with account_id and config_path.
    """
    require_test_account_credentials(test_account_id)
    
    account_info = get_test_account_config(test_account_id)
    if not account_info:
        pytest.skip(f"Test account info not found: {test_account_id}")
    
    # Create account config
    account_config = {
        'imap': {
            'server': account_info.get('provider', {}).get('imap_server', 'imap.example.com'),
            'port': 993,
            'username': account_info.get('email_address', 'test@example.com'),
            'password_env': account_info.get('password_env', 'IMAP_PASSWORD'),
            'query': 'UNSEEN',
            'processed_tag': 'AIProcessed'
        },
        'paths': {
            'obsidian_vault': str(e2e_test_vault),
            'log_file': str(tmp_path / 'logs' / f'{test_account_id}.log'),
            'analytics_file': str(tmp_path / 'logs' / f'{test_account_id}-analytics.jsonl')
        },
        'processing': {
            'max_emails_per_run': 5,  # Low limit for testing
            'importance_threshold': 7,
            'spam_threshold': 5
        }
    }
    
    # Write account config file
    account_config_path = e2e_test_config_dir / 'accounts' / f'{test_account_id}.yaml'
    with open(account_config_path, 'w') as f:
        yaml.dump(account_config, f)
    
    return {
        'account_id': test_account_id,
        'config_path': account_config_path,
        'config': account_config
    }


# ============================================================================
# Test Data Seeding Fixtures
# ============================================================================

@pytest.fixture
def test_email_templates():
    """
    Get test email templates for E2E testing.
    
    Returns:
        Dictionary of test email templates.
    """
    from tests.e2e_helpers import get_test_email_templates
    return get_test_email_templates()


# ============================================================================
# Master Orchestrator Fixtures
# ============================================================================

@pytest.fixture
def e2e_master_orchestrator(e2e_test_config_dir):
    """
    Create a MasterOrchestrator instance for E2E testing.
    
    This fixture creates an orchestrator configured for testing:
    - Uses test config directory
    - Configured for test environment
    - Ready to process test accounts
    
    Returns:
        MasterOrchestrator instance.
    """
    from src.orchestrator import MasterOrchestrator
    import logging
    
    # Create logger for tests
    logger = logging.getLogger('e2e_test')
    logger.setLevel(logging.DEBUG)
    
    orchestrator = MasterOrchestrator(
        config_base_dir=str(e2e_test_config_dir),
        logger=logger
    )
    
    return orchestrator


# ============================================================================
# Test Isolation Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def e2e_test_isolation(e2e_test_vault):
    """
    Ensure test isolation for E2E tests.
    
    This fixture:
    - Cleans up test vault before each test
    - Ensures clean state for each test
    
    Note: This runs automatically for all tests in this module.
    """
    # Cleanup before test
    if e2e_test_vault.exists():
        shutil.rmtree(e2e_test_vault, ignore_errors=True)
    e2e_test_vault.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Cleanup after test (optional - can keep for debugging)
    # if e2e_test_vault.exists():
    #     shutil.rmtree(e2e_test_vault, ignore_errors=True)


# ============================================================================
# Marker-based Fixtures (for conditional test execution)
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Skip E2E tests if requirements are not met.
    
    This hook runs during test collection and skips only tests marked with e2e_v4
    if test account credentials/config are not available. Other tests are unaffected.
    """
    # Check if any E2E tests are being collected
    e2e_tests = [item for item in items if item.get_closest_marker("e2e_v4")]
    
    if not e2e_tests:
        # No E2E tests in this collection, nothing to check
        return
    
    # Check for test account credentials
    if not has_any_test_account_credentials():
        skip_marker = pytest.mark.skip(reason="E2E test requirements not met: No test account credentials available")
        for item in e2e_tests:
            item.add_marker(skip_marker)
        return
    
    # Check for account configs
    accounts = get_test_accounts()
    if not accounts:
        skip_marker = pytest.mark.skip(reason="E2E test requirements not met: No test accounts configured")
        for item in e2e_tests:
            item.add_marker(skip_marker)
        return
    
    # Check that at least one account has both credentials and config
    has_valid_account = False
    for account in accounts:
        account_id = account.get('account_id')
        if account_id:
            if has_test_account_credentials(account_id) and get_account_config_path(account_id).exists():
                has_valid_account = True
                break
    
    if not has_valid_account:
        skip_marker = pytest.mark.skip(reason="E2E test requirements not met: No valid test accounts (credentials + config)")
        for item in e2e_tests:
            item.add_marker(skip_marker)


# ============================================================================
# Helper Fixtures for Specific Test Scenarios
# ============================================================================

@pytest.fixture
def multi_account_setup(e2e_test_config_dir, available_test_accounts, e2e_test_vault, tmp_path):
    """
    Set up multiple test accounts for multi-account testing scenarios.
    
    Returns:
        Dictionary mapping account_id to config info.
    """
    accounts = {}
    
    for account_id in available_test_accounts[:2]:  # Use first 2 accounts
        require_test_account_credentials(account_id)
        
        account_info = get_test_account_config(account_id)
        if not account_info:
            continue
        
        # Create account config
        account_config = {
            'imap': {
                'server': 'imap.example.com',  # Will be overridden by actual account
                'port': 993,
                'username': account_info.get('email_address', 'test@example.com'),
                'password_env': account_info.get('password_env', 'IMAP_PASSWORD'),
                'query': 'UNSEEN',
                'processed_tag': 'AIProcessed'
            },
            'paths': {
                'obsidian_vault': str(e2e_test_vault / account_id),
                'log_file': str(tmp_path / 'logs' / f'{account_id}.log')
            },
            'processing': {
                'max_emails_per_run': 3
            }
        }
        
        # Create account-specific vault
        (e2e_test_vault / account_id).mkdir(parents=True, exist_ok=True)
        
        # Write account config
        account_config_path = e2e_test_config_dir / 'accounts' / f'{account_id}.yaml'
        with open(account_config_path, 'w') as f:
            yaml.dump(account_config, f)
        
        accounts[account_id] = {
            'account_id': account_id,
            'config_path': account_config_path,
            'config': account_config,
            'vault_path': e2e_test_vault / account_id
        }
    
    return accounts
