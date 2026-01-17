"""
Tests for V3 CLI implementation using click.

These tests verify the CLI structure, argument parsing, and validation.
"""
import pytest
import sys
from click.testing import CliRunner
from pathlib import Path
import tempfile
import yaml
import os
from unittest.mock import patch, MagicMock

from src.cli_v3 import cli, ProcessOptions, CleanupFlagsOptions


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary V3 config file for testing."""
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
            'obsidian_vault': str(test_dir),
            'log_file': str(test_dir / "logs" / "test.log"),
            'analytics_file': str(test_dir / "logs" / "test_analytics.jsonl"),
            'changelog_path': str(test_dir / "logs" / "test_changelog.md"),
            'prompt_file': str(prompt_file)
        },
        'openrouter': {
            'api_key_env': 'TEST_OPENROUTER_API_KEY',
            'api_url': 'https://openrouter.ai/api/v1',
            'model': 'test-model',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
        'processing': {
            'importance_threshold': 8,
            'spam_threshold': 5,
            'max_body_chars': 4000,
            'max_emails_per_run': 15
        },
        'classification': {
            'model': 'test-model',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
        'summarization': {
            'model': 'test-model',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
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


@pytest.fixture
def runner():
    """Create a CliRunner for testing."""
    return CliRunner()


def test_cli_help(runner):
    """Test that CLI help is displayed correctly."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Email-Agent' in result.output
    assert 'process' in result.output
    assert 'cleanup-flags' in result.output
    assert 'show-config' in result.output


def test_cli_version(runner):
    """Test that CLI version is displayed correctly."""
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert 'email-agent' in result.output
    assert '3.0.0' in result.output


def test_process_command_help(runner):
    """Test that process command help is displayed correctly."""
    result = runner.invoke(cli, ['process', '--help'])
    assert result.exit_code == 0
    assert '--uid' in result.output
    assert '--force-reprocess' in result.output
    assert '--dry-run' in result.output


@patch('src.orchestrator.Pipeline')
@patch('src.settings.settings')
def test_process_command_defaults(mock_settings, mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with default options."""
    # Mock settings singleton to prevent initialization errors
    from pathlib import Path
    mock_settings._ensure_initialized = MagicMock()
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.initialize = MagicMock()
    
    # Create mock pipeline instance
    mock_pipeline = MagicMock()
    mock_summary = MagicMock()
    mock_summary.total_emails = 0
    mock_summary.successful = 0
    mock_summary.failed = 0
    mock_summary.total_time = 0.1
    mock_summary.average_time = 0.0
    mock_pipeline.process_emails.return_value = mock_summary
    
    # Set return_value so Pipeline() returns mock_pipeline without calling __init__
    mock_pipeline_class.return_value = mock_pipeline
    
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process'
    ])
    assert result.exit_code == 0, f"CLI failed with output: {result.output}\nException: {result.exception}"
    assert 'Processing complete' in result.output or 'successful' in result.output.lower()


@patch('src.orchestrator.Pipeline')
@patch('src.settings.settings')
def test_process_command_with_uid(mock_settings, mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with --uid option."""
    # Mock settings singleton to prevent initialization errors
    from pathlib import Path
    mock_settings._ensure_initialized = MagicMock()
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.initialize = MagicMock()
    
    # Mock the pipeline and its return value
    mock_pipeline = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline
    mock_summary = MagicMock()
    mock_summary.total_emails = 1
    mock_summary.successful = 1
    mock_summary.failed = 0
    mock_summary.total_time = 0.1
    mock_summary.average_time = 0.1
    mock_pipeline.process_emails.return_value = mock_summary
    
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--uid', '12345'
    ])
    assert result.exit_code == 0
    # Verify pipeline was called with correct UID
    call_args = mock_pipeline.process_emails.call_args[0][0]
    assert call_args.uid == '12345'


@patch('src.orchestrator.Pipeline')
@patch('src.settings.settings')
def test_process_command_force_reprocess(mock_settings, mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with --force-reprocess flag."""
    # Mock settings singleton to prevent initialization errors
    from pathlib import Path
    mock_settings._ensure_initialized = MagicMock()
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.initialize = MagicMock()
    
    # Mock the pipeline and its return value
    mock_pipeline = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline
    mock_summary = MagicMock()
    mock_summary.total_emails = 0
    mock_summary.successful = 0
    mock_summary.failed = 0
    mock_summary.total_time = 0.1
    mock_summary.average_time = 0.0
    mock_pipeline.process_emails.return_value = mock_summary
    
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--force-reprocess'
    ])
    assert result.exit_code == 0
    # Verify pipeline was called with force_reprocess=True
    call_args = mock_pipeline.process_emails.call_args[0][0]
    assert call_args.force_reprocess is True


@patch('src.orchestrator.Pipeline')
@patch('src.settings.settings')
def test_process_command_dry_run(mock_settings, mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with --dry-run flag."""
    # Mock settings singleton to prevent initialization errors
    from pathlib import Path
    mock_settings._ensure_initialized = MagicMock()
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.initialize = MagicMock()
    
    # Mock the pipeline and its return value
    mock_pipeline = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline
    mock_summary = MagicMock()
    mock_summary.total_emails = 0
    mock_summary.successful = 0
    mock_summary.failed = 0
    mock_summary.total_time = 0.1
    mock_summary.average_time = 0.0
    mock_pipeline.process_emails.return_value = mock_summary
    
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--dry-run'
    ])
    assert result.exit_code == 0
    assert '[DRY RUN MODE]' in result.output or 'DRY RUN MODE' in result.output
    # Verify pipeline was called with dry_run=True
    call_args = mock_pipeline.process_emails.call_args[0][0]
    assert call_args.dry_run is True


@patch('src.orchestrator.Pipeline')
@patch('src.settings.settings')
def test_process_command_all_flags(mock_settings, mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with all flags."""
    # Mock settings singleton to prevent initialization errors
    from pathlib import Path
    mock_settings._ensure_initialized = MagicMock()
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.initialize = MagicMock()
    
    # Mock the pipeline and its return value
    mock_pipeline = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline
    mock_summary = MagicMock()
    mock_summary.total_emails = 1
    mock_summary.successful = 1
    mock_summary.failed = 0
    mock_summary.total_time = 0.1
    mock_summary.average_time = 0.1
    mock_pipeline.process_emails.return_value = mock_summary
    
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--uid', '67890',
        '--force-reprocess',
        '--dry-run'
    ])
    assert result.exit_code == 0
    assert '[DRY RUN MODE]' in result.output or 'DRY RUN MODE' in result.output
    # Verify pipeline was called with all flags
    call_args = mock_pipeline.process_emails.call_args[0][0]
    assert call_args.uid == '67890'
    assert call_args.force_reprocess is True
    assert call_args.dry_run is True


def test_cleanup_flags_command_help(runner):
    """Test that cleanup-flags command help is displayed correctly."""
    result = runner.invoke(cli, ['cleanup-flags', '--help'])
    assert result.exit_code == 0
    # Check for key phrases in help text (exact wording may vary)
    assert 'cleanup-flags' in result.output.lower() or 'clean up' in result.output.lower() or 'flags' in result.output.lower()
    assert 'WARNING' in result.output or 'confirmation' in result.output.lower() or 'maintenance' in result.output.lower()


@patch('src.cleanup_flags.CleanupFlags')
@patch('src.settings.settings')
def test_cleanup_flags_confirmation_cancel(mock_settings, mock_cleanup_class, runner, temp_config_file, test_env_vars):
    """Test cleanup-flags command with cancelled confirmation."""
    from pathlib import Path
    # Mock settings to prevent initialization errors
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.get_imap_application_flags.return_value = ['AIProcessed']
    mock_settings.initialize = MagicMock()
    
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'cleanup-flags'
    ], input='no\n')
    assert result.exit_code == 0
    assert 'WARNING' in result.output
    assert 'Operation cancelled' in result.output or 'cancelled' in result.output.lower()


@patch('src.cleanup_flags.CleanupFlags')
@patch('src.settings.settings')
def test_cleanup_flags_confirmation_yes(mock_settings, mock_cleanup_class, runner, temp_config_file, test_env_vars):
    """Test cleanup-flags command with confirmed execution."""
    from pathlib import Path
    # Mock settings to prevent initialization errors
    config_path = Path(temp_config_file)
    mock_settings.get_log_file.return_value = str(config_path.parent / "logs" / "test.log")
    mock_settings.get_imap_application_flags.return_value = ['AIProcessed']
    mock_settings.initialize = MagicMock()
    
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
        '--config', temp_config_file,
        'cleanup-flags'
    ], input='yes\n')
    assert result.exit_code == 0
    assert 'WARNING' in result.output


def test_cli_missing_config_file(runner):
    """Test CLI with missing config file."""
    result = runner.invoke(cli, [
        '--config', 'nonexistent.yaml',
        'process'
    ])
    assert result.exit_code != 0
    assert 'not found' in result.output.lower() or 'error' in result.output.lower()


def test_cli_invalid_command(runner):
    """Test CLI with invalid command."""
    result = runner.invoke(cli, ['invalid-command'])
    assert result.exit_code != 0
    assert 'No such command' in result.output or 'Usage:' in result.output


def test_process_options_dataclass():
    """Test ProcessOptions dataclass."""
    options = ProcessOptions(
        uid='12345',
        force_reprocess=True,
        dry_run=True,
        config_path='config.yaml',
        env_path='.env'
    )
    assert options.uid == '12345'
    assert options.force_reprocess is True
    assert options.dry_run is True
    assert options.config_path == 'config.yaml'
    assert options.env_path == '.env'


def test_cleanup_flags_options_dataclass():
    """Test CleanupFlagsOptions dataclass."""
    options = CleanupFlagsOptions(
        config_path='config.yaml',
        env_path='.env'
    )
    assert options.config_path == 'config.yaml'
    assert options.env_path == '.env'


# ============================================================================
# V4 Multi-Account CLI Tests (Task 11)
# ============================================================================

@pytest.fixture
def temp_v4_config(tmp_path):
    """Create a temporary V4 config structure for testing."""
    test_dir = tmp_path / "test_config"
    test_dir.mkdir()
    (test_dir / "config").mkdir()
    (test_dir / "config" / "accounts").mkdir()
    (test_dir / "logs").mkdir()
    
    # Create global config
    global_config = test_dir / "config" / "config.yaml"
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
        }
    }
    with open(global_config, 'w') as f:
        yaml.dump(global_config_data, f)
    
    # Create account config
    account_config = test_dir / "config" / "accounts" / "work.yaml"
    account_config_data = {
        'imap': {
            'server': 'work.imap.com',
            'username': 'work@example.com'
        }
    }
    with open(account_config, 'w') as f:
        yaml.dump(account_config_data, f)
    
    yield str(test_dir / "config" / "config.yaml")


@patch('src.orchestrator.MasterOrchestrator')
def test_process_command_with_account_flag(mock_orchestrator_class, runner, temp_v4_config, test_env_vars):
    """Test process command with --account flag (V4 mode)."""
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.5
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_orchestrator_class.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'Processing Summary' in result.output or 'PROCESSING SUMMARY' in result.output
    assert 'Total accounts' in result.output or 'total_accounts' in result.output.lower()
    assert 'Successful' in result.output or 'successful' in result.output.lower()
    mock_orchestrator_class.assert_called_once()
    mock_orchestrator.run.assert_called_once()
    # Check that --account was passed
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--account' in call_args
    assert 'work' in call_args


@patch('src.orchestrator.MasterOrchestrator')
def test_process_command_with_all_flag(mock_orchestrator_class, runner, temp_v4_config, test_env_vars):
    """Test process command with --all flag (V4 mode)."""
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 2
    mock_result.successful_accounts = 2
    mock_result.failed_accounts = 0
    mock_result.total_time = 2.0
    mock_result.account_results = {'work': (True, None), 'personal': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_orchestrator_class.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--all'
    ])
    
    assert result.exit_code == 0
    assert 'Processing Summary' in result.output or 'PROCESSING SUMMARY' in result.output
    mock_orchestrator_class.assert_called_once()
    mock_orchestrator.run.assert_called_once()
    # Check that --all-accounts was passed
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--all-accounts' in call_args


def test_process_command_account_and_all_mutually_exclusive(runner, temp_v4_config):
    """Test that --account and --all are mutually exclusive."""
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--account', 'work', '--all'
    ])
    
    assert result.exit_code == 1
    assert 'mutually exclusive' in result.output.lower()


def test_process_command_invalid_account_name(runner, temp_v4_config):
    """Test process command with invalid account name."""
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--account', ''
    ])
    
    assert result.exit_code == 1
    assert 'cannot be empty' in result.output.lower()


def test_process_command_account_name_too_long(runner, temp_v4_config):
    """Test process command with account name that's too long."""
    long_name = 'a' * 101
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--account', long_name
    ])
    
    assert result.exit_code == 1
    assert 'too long' in result.output.lower()


def test_process_command_account_name_invalid_characters(runner, temp_v4_config):
    """Test process command with account name containing invalid characters."""
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--account', 'work@account'
    ])
    
    assert result.exit_code == 1
    assert 'invalid characters' in result.output.lower()


@patch('src.orchestrator.MasterOrchestrator')
def test_process_command_account_with_dry_run(mock_orchestrator_class, runner, temp_v4_config, test_env_vars):
    """Test process command with --account and --dry-run flags."""
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.total_accounts = 1
    mock_result.successful_accounts = 1
    mock_result.failed_accounts = 0
    mock_result.total_time = 1.0
    mock_result.account_results = {'work': (True, None)}
    mock_orchestrator.run.return_value = mock_result
    mock_orchestrator_class.return_value = mock_orchestrator
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'process', '--account', 'work', '--dry-run'
    ])
    
    assert result.exit_code == 0
    mock_orchestrator.run.assert_called_once()
    # Check that --dry-run was passed
    call_args = mock_orchestrator.run.call_args[0][0]
    assert '--dry-run' in call_args


@patch('src.config_loader.ConfigLoader')
def test_show_config_command_yaml(mock_loader_class, runner, temp_v4_config):
    """Test show-config command with YAML output format."""
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
    mock_loader_class.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'show-config', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'CONFIGURATION FOR ACCOUNT: WORK' in result.output or 'Configuration for account: work' in result.output.lower()
    assert 'work.imap.com' in result.output
    mock_loader.load_global_config.assert_called_once()
    mock_loader.load_account_config.assert_called_once_with('work')


@patch('src.config_loader.ConfigLoader')
def test_show_config_command_json(mock_loader_class, runner, temp_v4_config):
    """Test show-config command with JSON output format."""
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
    mock_loader_class.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'show-config', '--account', 'work', '--format', 'json'
    ])
    
    assert result.exit_code == 0
    assert 'CONFIGURATION FOR ACCOUNT: WORK' in result.output or 'Configuration for account: work' in result.output.lower()
    assert 'work.imap.com' in result.output
    assert '"server"' in result.output  # JSON format indicator


def test_show_config_command_missing_account(runner, temp_v4_config):
    """Test show-config command without --account flag."""
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'show-config'
    ])
    
    assert result.exit_code != 0
    assert 'required' in result.output.lower() or 'missing' in result.output.lower()


@patch('src.config_loader.ConfigLoader')
def test_show_config_command_invalid_account(mock_loader_class, runner, temp_v4_config):
    """Test show-config command with invalid account name."""
    mock_loader = MagicMock()
    from src.config_loader import ConfigurationError
    mock_loader.load_global_config.return_value = {}
    mock_loader.load_account_config.side_effect = ConfigurationError("Account not found")
    mock_loader_class.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'show-config', '--account', 'nonexistent'
    ])
    
    assert result.exit_code == 1
    assert 'error' in result.output.lower() or 'not found' in result.output.lower()


def test_show_config_command_help(runner):
    """Test that show-config command help is displayed correctly."""
    result = runner.invoke(cli, ['show-config', '--help'])
    assert result.exit_code == 0
    assert '--account' in result.output
    assert '--format' in result.output
    assert 'yaml' in result.output.lower() or 'json' in result.output.lower()


@patch('src.config_loader.ConfigLoader')
def test_show_config_command_override_highlighting(mock_loader_class, runner, temp_v4_config):
    """Test that show-config highlights overridden values."""
    mock_loader = MagicMock()
    global_config = {
        'imap': {
            'server': 'global.imap.com',
            'port': 993,
            'ssl': True
        }
    }
    account_config = {
        'imap': {
            'server': 'work.imap.com'  # Override server
        }
    }
    mock_loader.load_global_config.return_value = global_config
    mock_loader.load_account_config.return_value = account_config
    mock_loader_class.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'show-config', '--account', 'work'
    ])
    
    assert result.exit_code == 0
    assert 'CONFIGURATION FOR ACCOUNT: WORK' in result.output or 'Configuration for account: work' in result.output.lower()
    assert 'work.imap.com' in result.output
    # Should have override comment for overridden values
    assert 'overridden from global' in result.output
    # Should have legend explaining overrides
    assert 'overridden from global' in result.output.lower() or 'account-specific' in result.output.lower()


@patch('src.config_loader.ConfigLoader')
def test_show_config_command_no_highlight(mock_loader_class, runner, temp_v4_config):
    """Test show-config with --no-highlight flag."""
    mock_loader = MagicMock()
    global_config = {'imap': {'server': 'global.com'}}
    account_config = {'imap': {'server': 'work.com'}}
    mock_loader.load_global_config.return_value = global_config
    mock_loader.load_account_config.return_value = account_config
    mock_loader_class.return_value = mock_loader
    
    result = runner.invoke(cli, [
        '--config', temp_v4_config,
        'show-config', '--account', 'work', '--no-highlight'
    ])
    
    assert result.exit_code == 0
    # Should not have override comments when --no-highlight is used
    assert 'overridden from global' not in result.output


def test_process_command_help_includes_account_options(runner):
    """Test that process command help includes new account options."""
    result = runner.invoke(cli, ['process', '--help'])
    assert result.exit_code == 0
    assert '--account' in result.output
    assert '--all' in result.output
    assert 'multi-account' in result.output.lower() or 'V4' in result.output
