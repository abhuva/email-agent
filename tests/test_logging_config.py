"""
Tests for V4 Enhanced Logging Configuration

Tests the centralized logging configuration system including:
- Startup-time logging override
- Configuration loading from files
- Environment variable overrides
- Runtime overrides
- Context filter integration
"""
import pytest
import logging
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.logging_config import (
    init_logging,
    get_logger,
    DEFAULT_CONFIG,
    JSONFormatter,
    ContextFilter
)
from src.logging_context import (
    set_account_context,
    clear_context,
    with_account_context
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def reset_logging():
    """Reset logging configuration after each test."""
    yield
    # Clear all handlers from root logger (close them first on Windows)
    root_logger = logging.getLogger('email_agent')
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)
    # Clear context
    clear_context()


def test_init_logging_defaults(reset_logging, temp_log_dir):
    """Test that init_logging works with default configuration."""
    init_logging()
    
    root_logger = logging.getLogger('email_agent')
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) > 0
    
    # Test that logging works
    logger = get_logger('test_module')
    logger.info("Test message")
    
    # Verify handler exists
    assert any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)


def test_init_logging_with_overrides(reset_logging, temp_log_dir):
    """Test that init_logging accepts runtime overrides."""
    init_logging(overrides={'level': 'DEBUG'})
    
    root_logger = logging.getLogger('email_agent')
    assert root_logger.level == logging.DEBUG


def test_init_logging_with_file(reset_logging, temp_log_dir):
    """Test that init_logging loads configuration from YAML file."""
    # Create a test config file
    config_file = temp_log_dir / 'logging.yaml'
    config_file.write_text("""
logging:
  level: DEBUG
  format: json
  handlers:
    console:
      enabled: true
      level: DEBUG
    file:
      enabled: true
      path: {log_dir}/test.log
      level: DEBUG
""".format(log_dir=temp_log_dir))
    
    init_logging(config_path=str(config_file))
    
    root_logger = logging.getLogger('email_agent')
    assert root_logger.level == logging.DEBUG


def test_init_logging_env_overrides(reset_logging, temp_log_dir):
    """Test that environment variables override configuration."""
    with patch.dict(os.environ, {'LOG_LEVEL': 'ERROR'}):
        init_logging()
        
        root_logger = logging.getLogger('email_agent')
        assert root_logger.level == logging.ERROR


def test_get_logger(reset_logging):
    """Test that get_logger creates loggers with correct naming."""
    init_logging()
    
    logger1 = get_logger('test_module')
    assert logger1.name == 'email_agent.test_module'
    
    logger2 = get_logger('__main__')
    assert logger2.name == 'email_agent'
    
    logger3 = get_logger('src.orchestrator')
    assert logger3.name == 'email_agent.orchestrator'


def test_context_filter_includes_context(reset_logging, capsys):
    """Test that ContextFilter adds context fields to log records."""
    init_logging()
    
    # Set context
    set_account_context(account_id='work', correlation_id='abc-123')
    
    # Create a logger and log a message
    logger = get_logger('test_module')
    logger.info("Test message with context")
    
    # Capture output
    captured = capsys.readouterr()
    assert 'work' in captured.out or 'abc-123' in captured.out


def test_json_formatter(reset_logging, temp_log_dir):
    """Test that JSONFormatter produces valid JSON output."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname='test.py',
        lineno=1,
        msg='Test message',
        args=(),
        exc_info=None
    )
    record.component = 'test_module'
    record.correlation_id = 'abc-123'
    record.account_id = 'work'
    
    output = formatter.format(record)
    
    # Parse as JSON to verify it's valid
    log_data = json.loads(output)
    assert log_data['level'] == 'INFO'
    assert log_data['message'] == 'Test message'
    assert log_data['component'] == 'test_module'
    assert log_data['correlation_id'] == 'abc-123'
    assert log_data['account_id'] == 'work'


def test_logging_with_account_context(reset_logging, capsys):
    """Test that logging works correctly with account context manager."""
    init_logging()
    
    logger = get_logger('test_module')
    
    with with_account_context(account_id='work', correlation_id='test-123'):
        logger.info("Processing account")
    
    captured = capsys.readouterr()
    assert 'work' in captured.out or 'test-123' in captured.out


def test_logging_override_clears_old_handlers(reset_logging):
    """Test that init_logging clears existing handlers."""
    # Set up some initial logging
    root_logger = logging.getLogger('email_agent')
    root_logger.addHandler(logging.StreamHandler())
    initial_handler_count = len(root_logger.handlers)
    
    # Initialize logging (should clear and reconfigure)
    init_logging()
    
    # Should have new handlers, not accumulate old ones
    assert len(root_logger.handlers) >= 1
    # The exact count depends on configuration, but should be reasonable
    assert len(root_logger.handlers) <= 3  # console, file, maybe json_file


def test_file_handler_creation(reset_logging, temp_log_dir):
    """Test that file handler is created when enabled."""
    log_file = temp_log_dir / 'test.log'
    
    init_logging(overrides={
        'handlers': {
            'file': {
                'enabled': True,
                'path': str(log_file),
                'level': 'INFO'
            }
        }
    })
    
    logger = get_logger('test_module')
    logger.info("Test message to file")
    
    # Verify file was created and contains the message
    assert log_file.exists()
    content = log_file.read_text()
    assert 'Test message to file' in content
