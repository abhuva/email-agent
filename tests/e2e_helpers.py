"""
Helper utilities for V4 end-to-end tests.

This module provides utilities for:
- Loading test account configurations
- Checking test account credentials
- Managing test account state
- Test data preparation and cleanup
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
import pytest

# Project root directory
project_root = Path(__file__).parent.parent


def load_test_accounts_config() -> Dict[str, Any]:
    """
    Load test accounts configuration from config/test-accounts.yaml.
    
    Returns:
        Dictionary containing test accounts configuration.
        Returns empty dict if file doesn't exist.
    """
    config_path = project_root / 'config' / 'test-accounts.yaml'
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config or {}
    except Exception as e:
        pytest.skip(f"Failed to load test accounts config: {e}")


def get_test_accounts() -> List[Dict[str, Any]]:
    """
    Get list of configured test accounts.
    
    Returns:
        List of test account dictionaries.
    """
    config = load_test_accounts_config()
    return config.get('test_accounts', [])


def has_test_account_credentials(account_id: str) -> bool:
    """
    Check if credentials are available for a test account.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        True if credentials are available, False otherwise.
    """
    accounts = get_test_accounts()
    
    # Find account by account_id
    account = next((acc for acc in accounts if acc.get('account_id') == account_id), None)
    if not account:
        return False
    
    # Check if password environment variable is set
    password_env = account.get('password_env')
    if not password_env:
        return False
    
    password = os.getenv(password_env)
    return bool(password)


def get_test_account_config(account_id: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific test account.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        Test account configuration dictionary, or None if not found.
    """
    accounts = get_test_accounts()
    return next((acc for acc in accounts if acc.get('account_id') == account_id), None)


def has_any_test_account_credentials() -> bool:
    """
    Check if at least one test account has credentials available.
    
    Returns:
        True if at least one test account has credentials, False otherwise.
    """
    accounts = get_test_accounts()
    if not accounts:
        return False
    
    for account in accounts:
        password_env = account.get('password_env')
        if password_env and os.getenv(password_env):
            return True
    
    return False


def get_test_accounts_with_credentials() -> List[str]:
    """
    Get list of test account IDs that have credentials available.
    
    Returns:
        List of account IDs with available credentials.
    """
    accounts = get_test_accounts()
    result = []
    
    for account in accounts:
        account_id = account.get('account_id')
        password_env = account.get('password_env')
        
        if account_id and password_env and os.getenv(password_env):
            result.append(account_id)
    
    return result


def require_test_account_credentials(account_id: str):
    """
    Require that test account credentials are available.
    Skips test if credentials are not available.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    """
    if not has_test_account_credentials(account_id):
        account_config = get_test_account_config(account_id)
        password_env = account_config.get('password_env', 'UNKNOWN') if account_config else 'UNKNOWN'
        pytest.skip(f"Test account credentials not available: {account_id} (env: {password_env})")


def require_any_test_account_credentials():
    """
    Require that at least one test account has credentials available.
    Skips test if no credentials are available.
    """
    if not has_any_test_account_credentials():
        pytest.skip("No test account credentials available - skipping E2E tests")


def get_account_config_path(account_id: str) -> Path:
    """
    Get path to account configuration file.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        Path to account config file (config/accounts/<account-id>.yaml)
    """
    return project_root / 'config' / 'accounts' / f'{account_id}.yaml'


def account_config_exists(account_id: str) -> bool:
    """
    Check if account configuration file exists.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        True if config file exists, False otherwise.
    """
    return get_account_config_path(account_id).exists()


def require_account_config(account_id: str):
    """
    Require that account configuration file exists.
    Skips test if config file doesn't exist.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    """
    if not account_config_exists(account_id):
        config_path = get_account_config_path(account_id)
        pytest.skip(f"Account config file not found: {config_path}")


def load_account_config(account_id: str) -> Dict[str, Any]:
    """
    Load account configuration from config/accounts/<account-id>.yaml.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        Account configuration dictionary.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is invalid YAML.
    """
    config_path = get_account_config_path(account_id)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Account config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def get_test_vault_path(account_id: str) -> Path:
    """
    Get test vault path for an account.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        Path to test vault directory.
    """
    # Use temporary directory for test vaults
    import tempfile
    return Path(tempfile.gettempdir()) / 'email-agent-e2e-tests' / account_id


def ensure_test_vault_exists(account_id: str) -> Path:
    """
    Ensure test vault directory exists and is writable.
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    
    Returns:
        Path to test vault directory.
    
    Raises:
        OSError: If vault directory cannot be created or is not writable.
    """
    vault_path = get_test_vault_path(account_id)
    vault_path.mkdir(parents=True, exist_ok=True)
    
    # Verify writable
    test_file = vault_path / '.test-write'
    try:
        test_file.write_text('test')
        test_file.unlink()
    except Exception as e:
        raise OSError(f"Test vault directory is not writable: {vault_path}") from e
    
    return vault_path


def cleanup_test_vault(account_id: str):
    """
    Clean up test vault directory (remove all files).
    
    Args:
        account_id: Test account identifier (e.g., 'test-gmail-1')
    """
    vault_path = get_test_vault_path(account_id)
    
    if vault_path.exists():
        import shutil
        shutil.rmtree(vault_path, ignore_errors=True)


def get_test_email_templates() -> Dict[str, Dict[str, str]]:
    """
    Get test email templates for E2E testing.
    
    Returns:
        Dictionary of test email templates with keys: subject, body, etc.
    """
    return {
        'plain_text': {
            'subject': 'E2E Test - Plain Text Email',
            'body': 'This is a plain text test email for E2E testing.\n\nIt contains multiple paragraphs and should be processed correctly.',
            'sender': 'test-sender@example.com'
        },
        'html': {
            'subject': 'E2E Test - HTML Email',
            'body': '<html><body><h1>HTML Test Email</h1><p>This is an <strong>HTML</strong> test email.</p></body></html>',
            'sender': 'test-sender@example.com'
        },
        'blacklist_match': {
            'subject': 'E2E Test - Blacklist Match',
            'body': 'This email should match a blacklist rule and be dropped or recorded.',
            'sender': 'spam@example.com'  # Should match blacklist rule
        },
        'whitelist_match': {
            'subject': 'E2E Test - Whitelist Match',
            'body': 'This email should match a whitelist rule and get boosted.',
            'sender': 'important-client@example.com'  # Should match whitelist rule
        },
        'complex_html': {
            'subject': 'E2E Test - Complex HTML',
            'body': '''
            <html>
            <body>
                <h1>Complex HTML Email</h1>
                <table>
                    <tr><th>Column 1</th><th>Column 2</th></tr>
                    <tr><td>Data 1</td><td>Data 2</td></tr>
                </table>
                <img src="https://example.com/image.png" alt="Test Image">
                <a href="https://example.com">Link</a>
            </body>
            </html>
            ''',
            'sender': 'test-sender@example.com'
        }
    }
