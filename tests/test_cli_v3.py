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
    assert 'Email-Agent V3' in result.output
    assert 'process' in result.output
    assert 'cleanup-flags' in result.output


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
def test_process_command_defaults(mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with default options."""
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
        'process'
    ])
    assert result.exit_code == 0
    assert 'Processing complete' in result.output or 'successful' in result.output.lower()


@patch('src.orchestrator.Pipeline')
def test_process_command_with_uid(mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with --uid option."""
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
def test_process_command_force_reprocess(mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with --force-reprocess flag."""
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
def test_process_command_dry_run(mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with --dry-run flag."""
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
    assert '[DRY RUN MODE]' in result.output
    # Verify pipeline was called with dry_run=True
    call_args = mock_pipeline.process_emails.call_args[0][0]
    assert call_args.dry_run is True


@patch('src.orchestrator.Pipeline')
def test_process_command_all_flags(mock_pipeline_class, runner, temp_config_file, test_env_vars):
    """Test process command with all flags."""
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
    assert '[DRY RUN MODE]' in result.output
    # Verify pipeline was called with all flags
    call_args = mock_pipeline.process_emails.call_args[0][0]
    assert call_args.uid == '67890'
    assert call_args.force_reprocess is True
    assert call_args.dry_run is True


def test_cleanup_flags_command_help(runner):
    """Test that cleanup-flags command help is displayed correctly."""
    result = runner.invoke(cli, ['cleanup-flags', '--help'])
    assert result.exit_code == 0
    assert 'clean up IMAP processed flags' in result.output
    assert 'WARNING' in result.output or 'confirmation' in result.output.lower()


def test_cleanup_flags_confirmation_cancel(runner, temp_config_file, test_env_vars):
    """Test cleanup-flags command with cancelled confirmation."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'cleanup-flags'
    ], input='no\n')
    assert result.exit_code == 0
    assert 'WARNING' in result.output
    assert 'Operation cancelled' in result.output or 'cancelled' in result.output.lower()


def test_cleanup_flags_confirmation_yes(runner, temp_config_file, test_env_vars):
    """Test cleanup-flags command with confirmed execution."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'cleanup-flags'
    ], input='yes\n')
    assert result.exit_code == 0
    assert 'WARNING' in result.output
    assert 'Confirmation received' in result.output or 'ready to proceed' in result.output.lower()


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
