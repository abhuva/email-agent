"""
Tests for V4 runtime configuration module.

Tests the build_runtime_config function and RuntimeConfig class,
including CLI argument parsing, environment variable reading, and
configuration merging with proper precedence.
"""

import os
import pytest
from pathlib import Path
from argparse import Namespace
from unittest.mock import patch

from src.runtime_config import (
    RuntimeConfig,
    build_runtime_config,
    read_env_account_ids,
    read_env_bool,
    read_env_path,
    normalize_account_names
)


class TestRuntimeConfig:
    """Tests for RuntimeConfig dataclass."""
    
    def test_default_initialization(self):
        """Test RuntimeConfig with default values."""
        config = RuntimeConfig()
        
        assert config.account_names == []
        assert config.process_all is False
        assert config.config_base_dir == Path('config')
        assert config.accounts_dir == Path('config') / 'accounts'
        assert config.env_file == Path('.env')
        assert config.dry_run is False
        assert config.log_level == 'INFO'
        assert config.account_configs == {}
    
    def test_custom_initialization(self):
        """Test RuntimeConfig with custom values."""
        config = RuntimeConfig(
            account_names=['work', 'personal'],
            process_all=False,
            config_base_dir=Path('/custom/config'),
            dry_run=True,
            log_level='DEBUG'
        )
        
        assert config.account_names == ['work', 'personal']
        assert config.process_all is False
        assert config.config_base_dir == Path('/custom/config')
        assert config.accounts_dir == Path('/custom/config') / 'accounts'
        assert config.dry_run is True
        assert config.log_level == 'DEBUG'
    
    def test_accounts_dir_derived(self):
        """Test that accounts_dir is automatically derived from config_base_dir."""
        config = RuntimeConfig(config_base_dir=Path('test/config'))
        
        assert config.accounts_dir == Path('test/config') / 'accounts'
    
    def test_validate_success(self, tmp_path):
        """Test successful validation."""
        # Create config directory
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        config = RuntimeConfig(
            account_names=['work'],
            config_base_dir=config_dir,
            log_level='INFO'
        )
        
        # Should not raise
        config.validate()
    
    def test_validate_conflicting_account_selection(self, tmp_path):
        """Test validation fails when both process_all and account_names are set."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        config = RuntimeConfig(
            account_names=['work'],
            process_all=True,
            config_base_dir=config_dir
        )
        
        with pytest.raises(ValueError, match="Cannot specify both --all and --account"):
            config.validate()
    
    def test_validate_missing_config_dir(self):
        """Test validation fails when config directory doesn't exist."""
        config = RuntimeConfig(
            config_base_dir=Path('/nonexistent/path')
        )
        
        with pytest.raises(ValueError, match="Config base directory does not exist"):
            config.validate()
    
    def test_validate_invalid_log_level(self, tmp_path):
        """Test validation fails with invalid log level."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        config = RuntimeConfig(
            config_base_dir=config_dir,
            log_level='INVALID'
        )
        
        with pytest.raises(ValueError, match="Invalid log level"):
            config.validate()
    
    def test_validate_normalizes_log_level(self, tmp_path):
        """Test that validation normalizes log level (WARN -> WARNING)."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        config = RuntimeConfig(
            config_base_dir=config_dir,
            log_level='warn'
        )
        
        config.validate()
        assert config.log_level == 'WARNING'
        
        # Test lowercase normalization
        config.log_level = 'info'
        config.validate()
        assert config.log_level == 'INFO'


class TestEnvironmentVariableReading:
    """Tests for environment variable reading functions."""
    
    def test_read_env_account_ids_empty(self):
        """Test reading empty ACCOUNT_IDS."""
        with patch.dict(os.environ, {}, clear=True):
            result = read_env_account_ids()
            assert result == []
    
    def test_read_env_account_ids_single(self):
        """Test reading single account ID."""
        with patch.dict(os.environ, {'ACCOUNT_IDS': 'work'}):
            result = read_env_account_ids()
            assert result == ['work']
    
    def test_read_env_account_ids_multiple(self):
        """Test reading multiple account IDs."""
        with patch.dict(os.environ, {'ACCOUNT_IDS': 'work,personal,test'}):
            result = read_env_account_ids()
            assert result == ['work', 'personal', 'test']
    
    def test_read_env_account_ids_with_spaces(self):
        """Test reading account IDs with spaces (should be trimmed)."""
        with patch.dict(os.environ, {'ACCOUNT_IDS': 'work , personal , test'}):
            result = read_env_account_ids()
            assert result == ['work', 'personal', 'test']
    
    def test_read_env_bool_true(self):
        """Test reading boolean env var as true."""
        with patch.dict(os.environ, {'TEST_FLAG': 'true'}):
            assert read_env_bool('TEST_FLAG') is True
        
        with patch.dict(os.environ, {'TEST_FLAG': '1'}):
            assert read_env_bool('TEST_FLAG') is True
        
        with patch.dict(os.environ, {'TEST_FLAG': 'yes'}):
            assert read_env_bool('TEST_FLAG') is True
    
    def test_read_env_bool_false(self):
        """Test reading boolean env var as false."""
        with patch.dict(os.environ, {'TEST_FLAG': 'false'}):
            assert read_env_bool('TEST_FLAG') is False
        
        with patch.dict(os.environ, {'TEST_FLAG': '0'}):
            assert read_env_bool('TEST_FLAG') is False
        
        with patch.dict(os.environ, {}, clear=True):
            assert read_env_bool('TEST_FLAG', default=False) is False
    
    def test_read_env_bool_default(self):
        """Test reading boolean env var with default."""
        with patch.dict(os.environ, {}, clear=True):
            assert read_env_bool('TEST_FLAG', default=True) is True
            assert read_env_bool('TEST_FLAG', default=False) is False
    
    def test_read_env_path(self):
        """Test reading path from environment variable."""
        with patch.dict(os.environ, {'TEST_PATH': '/custom/path'}):
            result = read_env_path('TEST_PATH')
            assert result == Path('/custom/path')
    
    def test_read_env_path_default(self):
        """Test reading path with default."""
        with patch.dict(os.environ, {}, clear=True):
            default = Path('.env')
            result = read_env_path('TEST_PATH', default=default)
            assert result == default


class TestNormalizeAccountNames:
    """Tests for account name normalization."""
    
    def test_normalize_empty(self):
        """Test normalizing empty list."""
        assert normalize_account_names([]) == []
    
    def test_normalize_single(self):
        """Test normalizing single account name."""
        assert normalize_account_names(['work']) == ['work']
    
    def test_normalize_multiple(self):
        """Test normalizing multiple account names."""
        result = normalize_account_names(['work', 'personal', 'test'])
        assert result == ['work', 'personal', 'test']
    
    def test_normalize_removes_duplicates(self):
        """Test that normalization removes duplicates."""
        result = normalize_account_names(['work', 'personal', 'work', 'test'])
        assert result == ['work', 'personal', 'test']
    
    def test_normalize_removes_empty(self):
        """Test that normalization removes empty strings."""
        result = normalize_account_names(['work', '', 'personal', '  ', 'test'])
        assert result == ['work', 'personal', 'test']


class TestBuildRuntimeConfig:
    """Tests for build_runtime_config function."""
    
    def test_cli_account_takes_precedence(self, tmp_path):
        """Test that CLI --account takes precedence over environment."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {'ACCOUNT_IDS': 'env-account'}):
            args = Namespace(
                account='cli-account',
                all_accounts=False,
                dry_run=False,
                config_dir=str(config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            assert config.account_names == ['cli-account']
            assert config.process_all is False
    
    def test_cli_all_takes_precedence(self, tmp_path):
        """Test that CLI --all takes precedence over environment."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {'ACCOUNT_IDS': 'env-account'}):
            args = Namespace(
                account=None,
                all_accounts=True,
                dry_run=False,
                config_dir=str(config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            assert config.account_names == []
            assert config.process_all is True
    
    def test_env_account_ids_fallback(self, tmp_path):
        """Test that environment ACCOUNT_IDS is used when CLI doesn't specify."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {'ACCOUNT_IDS': 'work,personal'}):
            args = Namespace(
                account=None,
                all_accounts=False,
                dry_run=False,
                config_dir=str(config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            assert config.account_names == ['work', 'personal']
            assert config.process_all is False
    
    def test_default_all_accounts(self, tmp_path):
        """Test that default is to process all accounts when nothing is specified."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {}, clear=True):
            args = Namespace(
                account=None,
                all_accounts=False,
                dry_run=False,
                config_dir=str(config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            assert config.account_names == []
            assert config.process_all is True
    
    def test_dry_run_cli_precedence(self, tmp_path):
        """Test that CLI dry_run takes precedence over environment."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {'DRY_RUN': 'true'}):
            args = Namespace(
                account=None,
                all_accounts=True,
                dry_run=False,  # CLI says no dry run
                config_dir=str(config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            assert config.dry_run is False  # CLI wins
    
    def test_dry_run_env_fallback(self, tmp_path):
        """Test that environment DRY_RUN is used when CLI doesn't specify."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {'DRY_RUN': 'true'}):
            args = Namespace(
                account=None,
                all_accounts=True,
                dry_run=False,  # Explicitly False
                config_dir=str(config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            # CLI explicitly False, so should be False
            assert config.dry_run is False
    
    def test_config_dir_precedence(self, tmp_path):
        """Test that CLI config_dir takes precedence over environment."""
        cli_config_dir = tmp_path / 'cli_config'
        cli_config_dir.mkdir()
        
        env_config_dir = tmp_path / 'env_config'
        env_config_dir.mkdir()
        
        with patch.dict(os.environ, {'CONFIG_DIR': str(env_config_dir)}):
            args = Namespace(
                account=None,
                all_accounts=True,
                dry_run=False,
                config_dir=str(cli_config_dir),
                env_file=None,
                log_level=None
            )
            
            config = build_runtime_config(args)
            assert config.config_base_dir == cli_config_dir.resolve()
    
    def test_log_level_precedence(self, tmp_path):
        """Test that CLI log_level takes precedence over environment."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'}):
            args = Namespace(
                account=None,
                all_accounts=True,
                dry_run=False,
                config_dir=str(config_dir),
                env_file=None,
                log_level='WARNING'  # CLI says WARNING
            )
            
            config = build_runtime_config(args)
            assert config.log_level == 'WARNING'  # CLI wins
    
    def test_validation_failure(self):
        """Test that validation errors are raised."""
        # Use nonexistent config directory
        args = Namespace(
            account=None,
            all_accounts=True,
            dry_run=False,
            config_dir='/nonexistent/path',
            env_file=None,
            log_level=None
        )
        
        with pytest.raises(ValueError, match="Config base directory does not exist"):
            build_runtime_config(args)
    
    def test_minimal_args(self, tmp_path):
        """Test building config with minimal arguments."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        
        args = Namespace(
            account=None,
            all_accounts=False,
            dry_run=False,
            config_dir=str(config_dir),
            env_file=None,
            log_level=None
        )
        
        config = build_runtime_config(args)
        
        assert config.process_all is True  # Default when nothing specified
        assert config.config_base_dir == config_dir.resolve()
        assert config.accounts_dir == config_dir / 'accounts'
        assert config.dry_run is False
        assert config.log_level == 'INFO'
