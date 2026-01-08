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


def test_process_command_defaults(runner, temp_config_file, test_env_vars):
    """Test process command with default options."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process'
    ])
    assert result.exit_code == 0
    assert 'Process command called' in result.output
    assert '(all unprocessed)' in result.output
    assert 'Force reprocess: False' in result.output
    assert 'Dry run: False' in result.output


def test_process_command_with_uid(runner, temp_config_file, test_env_vars):
    """Test process command with --uid option."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--uid', '12345'
    ])
    assert result.exit_code == 0
    assert 'UID: 12345' in result.output


def test_process_command_force_reprocess(runner, temp_config_file, test_env_vars):
    """Test process command with --force-reprocess flag."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--force-reprocess'
    ])
    assert result.exit_code == 0
    assert 'Force reprocess: True' in result.output


def test_process_command_dry_run(runner, temp_config_file, test_env_vars):
    """Test process command with --dry-run flag."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--dry-run'
    ])
    assert result.exit_code == 0
    assert '[DRY RUN MODE]' in result.output
    assert 'Dry run: True' in result.output


def test_process_command_all_flags(runner, temp_config_file, test_env_vars):
    """Test process command with all flags."""
    result = runner.invoke(cli, [
        '--config', temp_config_file,
        'process',
        '--uid', '67890',
        '--force-reprocess',
        '--dry-run'
    ])
    assert result.exit_code == 0
    assert 'UID: 67890' in result.output
    assert 'Force reprocess: True' in result.output
    assert 'Dry run: True' in result.output


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
