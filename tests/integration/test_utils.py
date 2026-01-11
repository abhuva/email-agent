"""
Test utilities for integration tests.

This module provides helper functions and factories for creating test data,
configuration files, and test scenarios for integration testing.
"""

import yaml
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from tests.integration.mock_services import MockEmailData


def create_test_config_dir(
    base_dir: Path,
    global_config: Optional[Dict[str, Any]] = None,
    account_configs: Optional[Dict[str, Dict[str, Any]]] = None
) -> Path:
    """
    Create a temporary test configuration directory structure.
    
    Args:
        base_dir: Base directory for test files
        global_config: Global configuration dictionary
        account_configs: Dictionary mapping account names to their configs
        
    Returns:
        Path to the created config directory
    """
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    accounts_dir = config_dir / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)
    
    # Create global config
    if global_config:
        global_file = config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(global_config, f)
    
    # Create account configs
    if account_configs:
        for account_name, account_config in account_configs.items():
            account_file = accounts_dir / f"{account_name}.yaml"
            with open(account_file, 'w') as f:
                yaml.dump(account_config, f)
    
    return config_dir


def create_test_global_config(
    imap_server: str = "test.imap.com",
    imap_port: int = 993,
    imap_username: str = "test@example.com",
    imap_password: str = "test_password",
    **overrides
) -> Dict[str, Any]:
    """
    Create a test global configuration dictionary.
    
    Args:
        imap_server: IMAP server hostname
        imap_port: IMAP server port
        imap_username: IMAP username
        imap_password: IMAP password
        **overrides: Additional configuration overrides
        
    Returns:
        Configuration dictionary
    """
    config = {
        'imap': {
            'server': imap_server,
            'port': imap_port,
            'username': imap_username,
            'password': imap_password,
            'query': 'ALL',
            'processed_tag': 'AIProcessed'
        },
        'paths': {
            'obsidian_vault': '/test/vault',
            'log_file': 'logs/test.log'
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
    config.update(overrides)
    return config


def create_test_account_config(**overrides) -> Dict[str, Any]:
    """
    Create a test account-specific configuration dictionary.
    
    Args:
        **overrides: Configuration overrides
        
    Returns:
        Account configuration dictionary
    """
    config = {
        'imap': {
            'server': 'account.imap.com',
            'username': 'account@example.com'
        }
    }
    config.update(overrides)
    return config


def create_test_blacklist_rules() -> List[Dict[str, Any]]:
    """Create sample blacklist rules for testing."""
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


def create_test_whitelist_rules() -> List[Dict[str, Any]]:
    """Create sample whitelist rules for testing."""
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


def create_test_email_data(
    uid: str = "12345",
    sender: str = "test@example.com",
    subject: str = "Test Email",
    body: str = "Test body content",
    html_body: Optional[str] = None,
    **overrides
) -> MockEmailData:
    """
    Create test email data.
    
    Args:
        uid: Email UID
        sender: Sender email address
        subject: Email subject
        body: Plain text body
        html_body: HTML body (defaults to simple HTML version of body)
        **overrides: Additional email data overrides
        
    Returns:
        MockEmailData instance
    """
    if html_body is None:
        html_body = f"<p>{body}</p>"
        
    email_data = MockEmailData(
        uid=uid,
        sender=sender,
        subject=subject,
        body=body,
        html_body=html_body,
        **overrides
    )
    return email_data


def create_test_rules_file(
    rules_dir: Path,
    filename: str,
    rules: List[Dict[str, Any]]
) -> Path:
    """
    Create a test rules YAML file.
    
    Args:
        rules_dir: Directory to create rules file in
        filename: Name of rules file (e.g., 'blacklist.yaml')
        rules: List of rule dictionaries
        
    Returns:
        Path to created rules file
    """
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_file = rules_dir / filename
    with open(rules_file, 'w') as f:
        yaml.dump(rules, f)
    return rules_file


def reset_mock_services(mock_imap, mock_llm):
    """
    Reset mock services to default state.
    
    Args:
        mock_imap: MockImapClient instance
        mock_llm: MockLLMClient instance
    """
    mock_imap.clear_emails()
    mock_imap.set_connection_error(False)
    mock_imap.set_fetch_error(False)
    mock_imap.set_empty_inbox(False)
    mock_imap.set_malformed_message(False)
    
    mock_llm.set_default_response()
    mock_llm.set_timeout(False)
    mock_llm.set_invalid_json(False)
    mock_llm.set_truncated_response(False)
    mock_llm.set_response_delay(0.0)
    mock_llm._scenario_responses.clear()
