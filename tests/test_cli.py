"""Tests for CLI interface"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import argparse
import os

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import main, parse_args


class TestCLIBasicStructure:
    """Test basic CLI structure and argument parsing"""
    
    def test_cli_has_help_option(self, capsys):
        """Test that --help option works"""
        with pytest.raises(SystemExit) as exc_info:
            with patch('sys.argv', ['cli.py', '--help']):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'Email-Agent' in captured.out or 'email-agent' in captured.out.lower()
    
    def test_cli_has_version_option(self, capsys):
        """Test that --version option works"""
        with pytest.raises(SystemExit) as exc_info:
            with patch('sys.argv', ['cli.py', '--version']):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '0.1.0' in captured.out or 'version' in captured.out.lower()
    
    def test_cli_accepts_config_path(self):
        """Test that --config option accepts a path"""
        with patch('sys.argv', ['cli.py', '--config', 'test_config.yaml']):
            args = parse_args()
            assert args.config == 'test_config.yaml'
    
    def test_cli_has_default_config_path(self):
        """Test that config defaults to config/config.yaml"""
        with patch('sys.argv', ['cli.py']):
            args = parse_args()
            assert args.config == 'config/config.yaml'


class TestCLIConfigOptions:
    """Test config file path options"""
    
    def test_config_path_validation_exists(self, tmp_path):
        """Test that config path validation works for existing files"""
        config_file = tmp_path / 'test_config.yaml'
        config_file.write_text('test: value')
        
        with patch('sys.argv', ['cli.py', '--config', str(config_file)]):
            args = parse_args()
            # Should not raise if file exists
            assert args.config == str(config_file)
    
    def test_config_path_validation_missing(self, capsys):
        """Test that missing config file shows helpful error"""
        with patch('sys.argv', ['cli.py', '--config', 'nonexistent.yaml']):
            # Should handle gracefully - actual validation happens in main()
            args = parse_args()
            assert args.config == 'nonexistent.yaml'


class TestCLIDebugAndOptions:
    """Test debug mode and other options"""
    
    def test_debug_flag_enables_debug(self):
        """Test that --debug flag sets debug mode"""
        with patch('sys.argv', ['cli.py', '--debug']):
            args = parse_args()
            assert args.debug is True
    
    def test_log_level_option(self):
        """Test that --log-level option works"""
        with patch('sys.argv', ['cli.py', '--log-level', 'DEBUG']):
            args = parse_args()
            assert args.log_level == 'DEBUG'
    
    def test_log_level_defaults_to_info(self):
        """Test that log level defaults to INFO"""
        with patch('sys.argv', ['cli.py']):
            args = parse_args()
            assert args.log_level == 'INFO'
    
    def test_limit_option_accepts_number(self):
        """Test that --limit option accepts a number"""
        with patch('sys.argv', ['cli.py', '--limit', '5']):
            args = parse_args()
            assert args.limit == 5
    
    def test_limit_option_is_optional(self):
        """Test that --limit option is optional"""
        with patch('sys.argv', ['cli.py']):
            args = parse_args()
            assert args.limit is None
    
    def test_continuous_mode_flag(self):
        """Test that --continuous flag enables continuous mode"""
        with patch('sys.argv', ['cli.py', '--continuous']):
            args = parse_args()
            assert args.continuous is True
    
    def test_single_run_is_default(self):
        """Test that single-run mode is default"""
        with patch('sys.argv', ['cli.py']):
            args = parse_args()
            assert args.continuous is False


class TestCLIErrorHandling:
    """Test error handling and validation"""
    
    def test_invalid_log_level_shows_error(self, capsys):
        """Test that invalid log level shows helpful error"""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['cli.py', '--log-level', 'INVALID']):
                parse_args()
    
    def test_invalid_limit_shows_error(self, capsys):
        """Test that invalid limit (non-number) shows error"""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['cli.py', '--limit', 'not-a-number']):
                parse_args()
    
    def test_negative_limit_shows_error(self, capsys):
        """Test that negative limit shows error"""
        with pytest.raises((SystemExit, argparse.ArgumentError)):
            with patch('sys.argv', ['cli.py', '--limit', '-1']):
                parse_args()


class TestCLIExecutionFlow:
    """Test main execution flow and exit codes"""
    
    def test_main_loads_config_successfully(self, tmp_path):
        """Test that main() loads config and exits with 0 on success"""
        # Create minimal valid config
        config_file = tmp_path / 'config.yaml'
        env_file = tmp_path / '.env'
        config_file.write_text("""
imap:
  server: 'test.example.com'
  port: 993
  username: 'test@example.com'
  password_env: 'IMAP_PASSWORD'
prompt_file: 'prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'
processed_tag: 'AIProcessed'
max_body_chars: 4000
max_emails_per_run: 15
log_file: 'logs/test.log'
log_level: 'INFO'
analytics_file: 'logs/analytics.jsonl'
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: 'openai/gpt-3.5-turbo'
""")
        env_file.write_text("IMAP_PASSWORD=test\nOPENROUTER_API_KEY=test")
        
        # Create log directory
        log_dir = tmp_path / 'logs'
        log_dir.mkdir()
        
        with patch('sys.argv', ['cli.py', '--config', str(config_file), '--env', str(env_file)]):
                with patch('src.cli.run_email_processing_loop') as mock_run:
                    mock_run.return_value = {
                        'successfully_processed': 0,
                        'summary': {
                            'total': 0,
                            'successfully_processed': 0,
                            'failed': 0,
                            'success_rate': 0,
                            'tags': {}
                        }
                    }
                    result = main()
                    assert result == 0  # Success exit code
                    mock_run.assert_called_once()
    
    def test_main_handles_config_error(self, capsys):
        """Test that main() exits with 1 on config error"""
        with patch('sys.argv', ['cli.py', '--config', 'nonexistent.yaml']):
            with patch('src.cli.ConfigManager') as mock_config:
                mock_config.side_effect = Exception("Config file not found")
                result = main()
                assert result == 1  # Error exit code
                captured = capsys.readouterr()
                assert 'error' in captured.err.lower() or 'Error' in captured.err
    
    def test_main_integrates_with_main_loop(self, tmp_path):
        """Test that main() calls run_email_processing_loop with correct args"""
        config_file = tmp_path / 'config.yaml'
        env_file = tmp_path / '.env'
        config_file.write_text("""
imap:
  server: 'test.example.com'
  port: 993
  username: 'test@example.com'
  password_env: 'IMAP_PASSWORD'
prompt_file: 'prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'
processed_tag: 'AIProcessed'
max_body_chars: 4000
max_emails_per_run: 15
log_file: 'logs/test.log'
log_level: 'INFO'
analytics_file: 'logs/analytics.jsonl'
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: 'openai/gpt-3.5-turbo'
""")
        env_file.write_text("IMAP_PASSWORD=test\nOPENROUTER_API_KEY=test")
        
        # Create log directory
        log_dir = tmp_path / 'logs'
        log_dir.mkdir()
        
        with patch('sys.argv', ['cli.py', '--config', str(config_file), '--env', str(env_file), '--limit', '10', '--continuous']):
                with patch('src.cli.run_email_processing_loop') as mock_run:
                    mock_run.return_value = {
                        'successfully_processed': 0,
                        'summary': {
                            'total': 0,
                            'successfully_processed': 0,
                            'failed': 0,
                            'success_rate': 0,
                            'tags': {}
                        }
                    }
                    mock_config = MagicMock()
                    mock_config.max_emails_per_run = 15
                    mock_config.log_file = str(log_dir / 'test.log')
                    mock_config.yaml = {'log_level': 'INFO'}
                    with patch('src.cli.ConfigManager', return_value=mock_config):
                        main()
                        # Verify run_email_processing_loop was called with correct args
                        mock_run.assert_called_once()
                        call_kwargs = mock_run.call_args[1]
                        assert call_kwargs['max_emails'] == 10  # Override from --limit
                        assert call_kwargs['single_run'] is False  # --continuous flag
