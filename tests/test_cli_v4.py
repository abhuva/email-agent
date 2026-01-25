"""
Tests for V4 CLI implementation using click.

These tests verify the V4 CLI structure, argument parsing, and validation.
All tests use V4 components (MasterOrchestrator, ConfigLoader) exclusively.
"""
import pytest
import sys
from click.testing import CliRunner
from pathlib import Path
import tempfile
import yaml
import os
from unittest.mock import patch, MagicMock

from src.cli_v4 import cli


@pytest.fixture
def temp_v4_config_dir(tmp_path):
    """Create a temporary V4 config directory structure for testing."""
    test_dir = tmp_path / "test_config"
    test_dir.mkdir()
    (test_dir / "accounts").mkdir()
    (test_dir / "logs").mkdir()
    
    # Create global config
    global_config = test_dir / "config.yaml"
    global_config_data = {
        'imap': {
            'server': 'global.imap.com',
            'port': 143,
            'username': 'global@example.com',
            'password_env': 'TEST_IMAP_PASSWORD',
            'query': 'UNSEEN',
            'processed_tag': 'AIProcessed'
        },
        'paths': {
            'obsidian_vault': str(test_dir),
            'log_file': str(test_dir / "logs" / "test.log")
        },
        'openrouter': {
            'api_key_env': 'TEST_OPENROUTER_API_KEY',
            'api_url': 'https://openrouter.ai/api/v1',
            'model': 'test-model',
            'temperature': 0.2
        }
    }
    with open(global_config, 'w') as f:
        yaml.dump(global_config_data, f)
    
    # Create account configs
    work_account = test_dir / "accounts" / "work.yaml"
    work_account_data = {
        'imap': {
            'server': 'work.imap.com',
            'username': 'work@example.com'
        }
    }
    with open(work_account, 'w') as f:
        yaml.dump(work_account_data, f)
    
    personal_account = test_dir / "accounts" / "personal.yaml"
    personal_account_data = {
        'imap': {
            'server': 'personal.imap.com',
            'username': 'personal@example.com'
        }
    }
    with open(personal_account, 'w') as f:
        yaml.dump(personal_account_data, f)
    
    yield str(test_dir)


@pytest.fixture
def test_env_vars(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv('TEST_IMAP_PASSWORD', 'test_password')
    monkeypatch.setenv('TEST_OPENROUTER_API_KEY', 'test_api_key')


@pytest.fixture
def runner():
    """Create a CliRunner for testing."""
    return CliRunner()


def test_cli_help(runner):
    """Test that CLI help is displayed correctly."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Email-Agent V4' in result.output or 'email-agent' in result.output.lower()
    assert 'process' in result.output
    assert 'cleanup-flags' in result.output
    assert 'show-config' in result.output


def test_cli_version(runner):
    """Test that CLI version is displayed correctly."""
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert 'email-agent' in result.output
    assert '4.0.0' in result.output


def test_process_command_help(runner):
    """Test that process command help is displayed correctly."""
    result = runner.invoke(cli, ['process', '--help'])
    assert result.exit_code == 0
    assert '--account' in result.output
    assert '--all' in result.output
    assert '--dry-run' in result.output
    assert '--uid' in result.output
    assert '--force-reprocess' in result.output


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_account(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with --account flag."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.5
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'PROCESSING SUMMARY' in result.output or 'Processing Summary' in result.output or 'total accounts' in result.output.lower()
    mock_get_orchestrator.assert_called_once()
    mock_orchestrator.run.assert_called_once()
    # Verify argv contains --account and account name
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--account' in call_args
    assert 'work' in call_args


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_all(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with --all flag."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 2
    mock_result.successful_accounts = 2
    mock_result.failed_accounts = 0
    mock_result.total_time = 2.0
    mock_result.account_results = {'work': (True, None), 'personal': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--all'
    ])
    
    assert result.exit_code == 0
    assert 'PROCESSING SUMMARY' in result.output or 'Processing Summary' in result.output or 'total accounts' in result.output.lower()
    mock_orchestrator.run.assert_called_once()
    # Verify argv contains --all-accounts
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--all-accounts' in call_args


def test_process_command_account_and_all_mutually_exclusive(runner, temp_v4_config_dir):
    """Test that --account and --all are mutually exclusive."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--all'
    ])
    
    assert result.exit_code == 1
    assert 'mutually exclusive' in result.output.lower()


def test_process_command_requires_account_or_all(runner, temp_v4_config_dir):
    """Test that process command requires either --account or --all."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process'
    ])
    
    assert result.exit_code == 1
    assert 'must specify' in result.output.lower() or 'required' in result.output.lower()


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_dry_run(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with --dry-run flag."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--dry-run'
    ])
    
    assert result.exit_code == 0
    mock_orchestrator.run.assert_called_once()
    # Verify argv contains --dry-run
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--dry-run' in call_args


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_uid(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with --uid option."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--uid', '12345'
    ])
    
    assert result.exit_code == 0
    mock_orchestrator.run.assert_called_once()
    # Verify argv contains --uid and UID value
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--uid' in call_args
    assert '12345' in call_args


def test_process_command_uid_with_all_fails(runner, temp_v4_config_dir):
    """Test that --uid cannot be used with --all."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--all', '--uid', '12345'
    ])
    
    assert result.exit_code == 1
    assert 'cannot be used with --all' in result.output.lower() or '--uid' in result.output.lower()


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_force_reprocess(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with --force-reprocess flag."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--force-reprocess'
    ])
    
    assert result.exit_code == 0
    mock_orchestrator.run.assert_called_once()
    # Verify argv contains --force-reprocess
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--force-reprocess' in call_args


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_max_emails(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with --max-emails option."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--max-emails', '10'
    ])
    
    assert result.exit_code == 0
    mock_orchestrator.run.assert_called_once()
    # Verify argv contains --max-emails and value
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--max-emails' in call_args
    assert '10' in call_args


@patch('src.cli_v4._get_orchestrator')
def test_process_command_with_all_options(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test process command with all options combined."""
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--uid', '12345',
        '--force-reprocess', '--dry-run', '--max-emails', '5'
    ])
    
    assert result.exit_code == 0
    mock_orchestrator.run.assert_called_once()
    # Verify all options are in argv
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--account' in call_args
    assert 'work' in call_args
    assert '--uid' in call_args
    assert '12345' in call_args
    assert '--force-reprocess' in call_args
    assert '--dry-run' in call_args
    assert '--max-emails' in call_args
    assert '5' in call_args


@patch('src.cli_v4._get_orchestrator')
def test_process_command_failed_accounts_exit_code(mock_get_orchestrator, runner, temp_v4_config_dir, test_env_vars):
    """Test that process command exits with error code when accounts fail."""
    # Create mock orchestrator with failed account
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 0
    mock_result.failed_accounts = 1
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (False, 'Test error')}
    mock_orchestrator.run.return_value = mock_result
    mock_get_orchestrator.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'failed' in result.output.lower() or 'error' in result.output.lower()


@patch('src.cli_v4._get_config_loader')
def test_show_config_command_yaml(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test show-config command with YAML output format."""
    # Create mock config loader
    mock_loader = MagicMock()
    global_config = {
        'imap': {
            'server': 'global.imap.com',
            'port': 993
        }
    }
    account_config = {
        'imap': {
            'server': 'work.imap.com',
            'username': 'work@example.com'
        }
    }
    mock_loader.load_global_config.return_value = global_config
    mock_loader.load_account_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'show-config', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'configuration for account: work' in result.output.lower()
    assert 'work.imap.com' in result.output
    mock_loader.load_global_config.assert_called_once()
    mock_loader.load_account_config.assert_called_once_with('work')


@patch('src.cli_v4._get_config_loader')
def test_show_config_command_json(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test show-config command with JSON output format."""
    # Create mock config loader
    mock_loader = MagicMock()
    global_config = {'imap': {'server': 'global.com'}}
    account_config = {'imap': {'server': 'work.com'}}
    mock_loader.load_global_config.return_value = global_config
    mock_loader.load_account_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'show-config', '--account', 'work', '--format', 'json'
    ])
    
    assert result.exit_code == 0
    assert 'configuration for account: work' in result.output.lower()
    assert 'work.com' in result.output


def test_show_config_command_missing_account(runner, temp_v4_config_dir):
    """Test show-config command without --account flag."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'show-config'
    ])
    
    assert result.exit_code != 0
    assert 'required' in result.output.lower() or 'missing' in result.output.lower()


@patch('src.cli_v4._get_config_loader')
def test_show_config_command_invalid_account(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test show-config command with invalid account name."""
    from src.config_loader import ConfigurationError
    mock_loader = MagicMock()
    mock_loader.load_global_config.return_value = {}
    mock_loader.load_account_config.side_effect = ConfigurationError("Account not found")
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'show-config', '--account', 'nonexistent'
    ])
    
    assert result.exit_code == 1
    assert 'error' in result.output.lower() or 'not found' in result.output.lower()


def test_cleanup_flags_command_help(runner):
    """Test that cleanup-flags command help is displayed correctly."""
    result = runner.invoke(cli, ['cleanup-flags', '--help'])
    assert result.exit_code == 0
    assert '--account' in result.output
    assert '--dry-run' in result.output
    assert 'WARNING' in result.output or 'maintenance' in result.output.lower()


@patch('src.account_processor.create_imap_client_from_config')
@patch('src.cli_v4._get_config_loader')
def test_cleanup_flags_confirmation_cancel(mock_get_config_loader, mock_create_client, runner, temp_v4_config_dir, test_env_vars):
    """Test cleanup-flags command with cancelled confirmation."""
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'imap': {
            'server': 'test.imap.com',
            'username': 'test@example.com',
            'password_env': 'TEST_IMAP_PASSWORD',
            'application_flags': ['AIProcessed']
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock IMAP client creation
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'cleanup-flags', '--account', 'work'
    ], input='no\n')
    
    assert result.exit_code == 0
    assert 'WARNING' in result.output
    assert 'cancelled' in result.output.lower() or 'Operation cancelled' in result.output


@patch('src.cleanup_flags.CleanupFlags')
@patch('src.account_processor.create_imap_client_from_config')
@patch('src.cli_v4._get_config_loader')
def test_cleanup_flags_confirmation_yes(mock_get_config_loader, mock_create_client, mock_cleanup_class, runner, temp_v4_config_dir, test_env_vars):
    """Test cleanup-flags command with confirmed execution."""
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'imap': {
            'server': 'test.imap.com',
            'username': 'test@example.com',
            'password_env': 'TEST_IMAP_PASSWORD',
            'application_flags': ['AIProcessed']
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock IMAP client creation
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    
    # Mock cleanup flags
    mock_cleanup = MagicMock()
    mock_cleanup_class.return_value = mock_cleanup
    mock_cleanup.connect.return_value = None
    mock_cleanup.disconnect.return_value = None
    mock_cleanup.scan_flags.return_value = []  # Empty list causes early return
    mock_cleanup.format_scan_results.return_value = "No flags found"
    mock_cleanup.remove_flags.return_value = MagicMock(
        total_emails_scanned=0,
        emails_with_flags=0,
        total_flags_removed=0,
        emails_modified=0,
        errors=0
    )
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'cleanup-flags', '--account', 'work'
    ], input='yes\n')
    
    assert result.exit_code == 0
    assert 'WARNING' in result.output


@patch('src.cleanup_flags.CleanupFlags')
@patch('src.account_processor.create_imap_client_from_config')
@patch('src.cli_v4._get_config_loader')
def test_cleanup_flags_dry_run(mock_get_config_loader, mock_create_client, mock_cleanup_class, runner, temp_v4_config_dir, test_env_vars):
    """Test cleanup-flags command with --dry-run flag."""
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'imap': {
            'server': 'test.imap.com',
            'username': 'test@example.com',
            'password_env': 'TEST_IMAP_PASSWORD',
            'application_flags': ['AIProcessed']
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock IMAP client creation
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    
    # Mock cleanup flags
    mock_cleanup = MagicMock()
    mock_cleanup_class.return_value = mock_cleanup
    mock_cleanup.connect.return_value = None
    mock_cleanup.disconnect.return_value = None
    mock_cleanup.scan_flags.return_value = []
    mock_cleanup.format_scan_results.return_value = "No flags found"
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'cleanup-flags', '--account', 'work', '--dry-run'
    ])
    
    assert result.exit_code == 0
    assert 'DRY RUN' in result.output or 'dry-run' in result.output.lower()
    # Dry run should not require confirmation
    assert 'yes' not in result.output.lower() or 'Type' not in result.output


def test_backfill_command_not_implemented(runner, temp_v4_config_dir):
    """Test that backfill command shows not implemented message."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'backfill', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'not yet fully migrated' in result.output.lower() or 'not implemented' in result.output.lower()


def test_cli_invalid_command(runner):
    """Test CLI with invalid command."""
    result = runner.invoke(cli, ['invalid-command'])
    assert result.exit_code != 0
    assert 'No such command' in result.output or 'Usage:' in result.output


def test_cli_config_dir_option(runner, temp_v4_config_dir):
    """Test that --config-dir option works."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        '--help'
    ])
    assert result.exit_code == 0


def test_cli_log_level_option(runner, temp_v4_config_dir):
    """Test that --log-level option works."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        '--log-level', 'DEBUG',
        '--help'
    ])
    assert result.exit_code == 0


def test_process_command_uid_validation_empty(runner, temp_v4_config_dir):
    """Test that empty UID is rejected."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--uid', ''
    ])
    
    assert result.exit_code == 1
    assert 'cannot be empty' in result.output.lower()


def test_process_command_uid_validation_too_long(runner, temp_v4_config_dir):
    """Test that UID that's too long is rejected."""
    long_uid = 'a' * 101
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'process', '--account', 'work', '--uid', long_uid
    ])
    
    assert result.exit_code == 1
    assert 'too long' in result.output.lower()


# ============================================================================
# Auth Command Tests
# ============================================================================

def test_auth_command_help(runner):
    """Test that auth command help is displayed correctly."""
    result = runner.invoke(cli, ['auth', '--help'])
    assert result.exit_code == 0
    assert '--account' in result.output
    assert 'oauth' in result.output.lower() or 'authentication' in result.output.lower()


def test_auth_command_missing_account(runner, temp_v4_config_dir):
    """Test that auth command requires --account flag."""
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth'
    ])
    
    assert result.exit_code != 0
    assert 'required' in result.output.lower() or 'missing' in result.output.lower()


@patch('src.cli_v4._get_config_loader')
def test_auth_command_account_not_found(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test auth command with non-existent account."""
    from src.config_loader import ConfigurationError
    mock_loader = MagicMock()
    mock_loader.load_merged_config.side_effect = FileNotFoundError("Account config not found")
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'nonexistent'
    ])
    
    assert result.exit_code == 1
    assert 'error' in result.output.lower() or 'not found' in result.output.lower()
    assert 'nonexistent' in result.output.lower()


@patch('src.cli_v4._get_config_loader')
def test_auth_command_not_oauth_method(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test auth command with account that doesn't use OAuth."""
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'password',
            'password_env': 'TEST_PASSWORD'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'not configured for oauth' in result.output.lower() or 'oauth' in result.output.lower()
    assert 'password' in result.output.lower()


@patch('src.cli_v4._get_config_loader')
def test_auth_command_missing_provider(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test auth command with OAuth method but missing provider."""
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth'
            # provider is missing
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'provider' in result.output.lower()
    assert 'not specified' in result.output.lower() or 'missing' in result.output.lower()


@patch('src.cli_v4._get_config_loader')
def test_auth_command_invalid_provider(mock_get_config_loader, runner, temp_v4_config_dir):
    """Test auth command with invalid provider."""
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'invalid_provider'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'invalid' in result.output.lower() or 'error' in result.output.lower()
    assert 'invalid_provider' in result.output.lower() or 'provider' in result.output.lower()


@patch('src.auth.oauth_flow.OAuthFlow')
@patch('src.auth.providers.google.GoogleOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_google_success(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_google_provider_class,
    mock_oauth_flow_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with Google provider - successful flow."""
    # Set environment variables
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = False
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Google provider
    mock_google_provider = MagicMock()
    mock_google_provider_class.return_value = mock_google_provider
    
    # Mock OAuth flow
    mock_flow = MagicMock()
    mock_token_info = {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_at': None
    }
    mock_flow.run.return_value = mock_token_info
    mock_oauth_flow_class.return_value = mock_flow
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'successful' in result.output.lower() or '✅' in result.output
    assert 'work' in result.output.lower()
    mock_oauth_flow_class.assert_called_once()
    mock_flow.run.assert_called_once()


@patch('src.auth.oauth_flow.OAuthFlow')
@patch('src.auth.providers.microsoft.MicrosoftOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_microsoft_success(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_microsoft_provider_class,
    mock_oauth_flow_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with Microsoft provider - successful flow."""
    # Set environment variables
    monkeypatch.setenv('MS_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('MS_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'microsoft'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = False
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Microsoft provider
    mock_microsoft_provider = MagicMock()
    mock_microsoft_provider_class.return_value = mock_microsoft_provider
    
    # Mock OAuth flow
    mock_flow = MagicMock()
    mock_token_info = {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_at': None
    }
    mock_flow.run.return_value = mock_token_info
    mock_oauth_flow_class.return_value = mock_flow
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'successful' in result.output.lower() or '✅' in result.output
    assert 'work' in result.output.lower()
    assert 'microsoft' in result.output.lower()
    mock_oauth_flow_class.assert_called_once()
    mock_flow.run.assert_called_once()


@patch('src.auth.providers.google.GoogleOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_google_provider_init_error(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_google_provider_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with Google provider initialization error."""
    from src.auth.providers.google import GoogleOAuthError
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = False
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Google provider initialization error
    mock_google_provider_class.side_effect = GoogleOAuthError("Missing GOOGLE_CLIENT_ID")
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'error' in result.output.lower()
    assert 'google' in result.output.lower() or 'GOOGLE_CLIENT_ID' in result.output


@patch('src.auth.oauth_flow.OAuthFlow')
@patch('src.auth.providers.google.GoogleOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_oauth_port_error(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_google_provider_class,
    mock_oauth_flow_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with OAuth port error."""
    from src.auth.oauth_flow import OAuthPortError
    
    # Set environment variables
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = False
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Google provider
    mock_google_provider = MagicMock()
    mock_google_provider_class.return_value = mock_google_provider
    
    # Mock OAuth flow with port error
    mock_flow = MagicMock()
    mock_flow.run.side_effect = OAuthPortError("No available ports")
    mock_oauth_flow_class.return_value = mock_flow
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'error' in result.output.lower() or 'port' in result.output.lower()
    mock_flow.stop_local_server.assert_called_once()


@patch('src.auth.oauth_flow.OAuthFlow')
@patch('src.auth.providers.google.GoogleOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_oauth_timeout_error(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_google_provider_class,
    mock_oauth_flow_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with OAuth timeout error."""
    from src.auth.oauth_flow import OAuthTimeoutError
    
    # Set environment variables
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = False
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Google provider
    mock_google_provider = MagicMock()
    mock_google_provider_class.return_value = mock_google_provider
    
    # Mock OAuth flow with timeout error
    mock_flow = MagicMock()
    mock_flow.run.side_effect = OAuthTimeoutError("Authentication timed out")
    mock_oauth_flow_class.return_value = mock_flow
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 1
    assert 'error' in result.output.lower() or 'timeout' in result.output.lower()
    mock_flow.stop_local_server.assert_called_once()


@patch('src.auth.oauth_flow.OAuthFlow')
@patch('src.auth.providers.google.GoogleOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_existing_tokens_overwrite_yes(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_google_provider_class,
    mock_oauth_flow_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with existing tokens - user confirms overwrite."""
    # Set environment variables
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager with existing tokens
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = True
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Google provider
    mock_google_provider = MagicMock()
    mock_google_provider_class.return_value = mock_google_provider
    
    # Mock OAuth flow
    mock_flow = MagicMock()
    mock_token_info = {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_at': None
    }
    mock_flow.run.return_value = mock_token_info
    mock_oauth_flow_class.return_value = mock_flow
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ], input='yes\n')
    
    assert result.exit_code == 0
    assert 'successful' in result.output.lower() or '✅' in result.output
    mock_flow.run.assert_called_once()


@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_existing_tokens_overwrite_no(
    mock_get_config_loader,
    mock_token_manager_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with existing tokens - user cancels overwrite."""
    # Set environment variables
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager with existing tokens
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = True
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ], input='no\n')
    
    assert result.exit_code == 0
    assert 'cancelled' in result.output.lower() or 'Operation cancelled' in result.output
    assert 'existing tokens' in result.output.lower() or 'will be used' in result.output.lower()


@patch('src.auth.oauth_flow.OAuthFlow')
@patch('src.auth.providers.google.GoogleOAuthProvider')
@patch('src.auth.token_manager.TokenManager')
@patch('src.cli_v4._get_config_loader')
def test_auth_command_keyboard_interrupt(
    mock_get_config_loader,
    mock_token_manager_class,
    mock_google_provider_class,
    mock_oauth_flow_class,
    runner,
    temp_v4_config_dir,
    monkeypatch
):
    """Test auth command with KeyboardInterrupt (Ctrl+C)."""
    # Set environment variables
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
    
    # Mock config loader
    mock_loader = MagicMock()
    account_config = {
        'auth': {
            'method': 'oauth',
            'provider': 'google'
        }
    }
    mock_loader.load_merged_config.return_value = account_config
    mock_get_config_loader.return_value = mock_loader
    
    # Mock token manager
    mock_token_manager = MagicMock()
    mock_credentials_path = MagicMock(spec=Path)
    mock_credentials_path.exists.return_value = False
    mock_credentials_path.__str__ = lambda x: '/tmp/credentials/work.json'
    mock_token_manager._get_token_path.return_value = mock_credentials_path
    mock_token_manager_class.return_value = mock_token_manager
    
    # Mock Google provider
    mock_google_provider = MagicMock()
    mock_google_provider_class.return_value = mock_google_provider
    
    # Mock OAuth flow with KeyboardInterrupt
    mock_flow = MagicMock()
    mock_flow.run.side_effect = KeyboardInterrupt()
    mock_oauth_flow_class.return_value = mock_flow
    
    result = runner.invoke(cli, [
        '--config-dir', temp_v4_config_dir,
        'auth', '--account', 'work'
    ])
    
    assert result.exit_code == 130  # Standard exit code for Ctrl+C
    assert 'cancelled' in result.output.lower() or 'KeyboardInterrupt' in result.output
    mock_flow.stop_local_server.assert_called_once()
