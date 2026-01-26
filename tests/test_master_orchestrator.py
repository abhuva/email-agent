"""
Unit tests for V4 MasterOrchestrator class.

This test suite verifies:
- Initialization and configuration
- CLI argument parsing
- Account discovery and selection
- AccountProcessor creation and lifecycle
- Multi-account orchestration
- Error handling and isolation
- Result aggregation

All tests use mocks to ensure complete isolation and fast execution.
"""
import pytest
import argparse
import logging
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
from typing import List, Dict, Any


def create_test_args(**kwargs):
    """Helper to create test argparse.Namespace with all required fields."""
    defaults = {
        'account_list': None,
        'accounts': None,
        'all_accounts': False,
        'config_dir': None,
        'log_level': None,
        'dry_run': False,
        'force_reprocess': False,
        'uid': None,
        'max_emails': None,
        'debug_prompt': False
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)

from src.orchestrator import (
    MasterOrchestrator,
    OrchestrationResult,
    ConfigurationError
)
from src.account_processor import (
    AccountProcessor,
    AccountProcessorError,
    AccountProcessorSetupError,
    AccountProcessorRunError
)
from src.config_loader import ConfigLoader


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory structure."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    accounts_dir = config_dir / "accounts"
    accounts_dir.mkdir()
    
    # Create sample account config files
    (accounts_dir / "work.yaml").write_text("imap:\n  username: work@example.com\n")
    (accounts_dir / "personal.yaml").write_text("imap:\n  username: personal@example.com\n")
    
    return config_dir


@pytest.fixture
def mock_config_loader(temp_config_dir):
    """Mock ConfigLoader."""
    loader = Mock(spec=ConfigLoader)
    loader.base_dir = temp_config_dir
    loader.load_merged_config = Mock(return_value={
        'imap': {'server': 'test.com', 'username': 'test@example.com'},
        'processing': {'max_emails_per_run': 10}
    })
    loader._discover_available_accounts = Mock(return_value=['work', 'personal'])
    return loader


@pytest.fixture
def mock_account_processor():
    """Mock AccountProcessor."""
    processor = Mock(spec=AccountProcessor)
    processor.setup = Mock()
    processor.run = Mock()
    processor.teardown = Mock()
    processor.account_id = "test_account"
    return processor


@pytest.fixture
def master_orchestrator(temp_config_dir, mock_config_loader):
    """Create MasterOrchestrator instance for testing."""
    with patch('src.orchestrator.ConfigLoader', return_value=mock_config_loader):
        orchestrator = MasterOrchestrator(
            config_base_dir=str(temp_config_dir),
            logger=logging.getLogger('test')
        )
        orchestrator.config_loader = mock_config_loader
        return orchestrator


# ============================================================================
# Initialization Tests
# ============================================================================

class TestMasterOrchestratorInitialization:
    """Test MasterOrchestrator initialization."""
    
    def test_initialization_with_defaults(self, temp_config_dir):
        """Test initialization with default parameters."""
        orchestrator = MasterOrchestrator()
        assert orchestrator.config_base_dir == Path("config").resolve()
        assert orchestrator.config_loader is not None
        # Note: V4 no longer has shared services - components are created per-account
    
    def test_initialization_with_custom_config_dir(self, temp_config_dir):
        """Test initialization with custom config directory."""
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        assert orchestrator.config_base_dir == Path(temp_config_dir).resolve()
    
    def test_initialization_with_custom_logger(self, temp_config_dir):
        """Test initialization with custom logger."""
        custom_logger = logging.getLogger('custom')
        orchestrator = MasterOrchestrator(
            config_base_dir=str(temp_config_dir),
            logger=custom_logger
        )
        assert orchestrator.logger == custom_logger
    
    def test_initialization_creates_config_loader(self, temp_config_dir):
        """Test that ConfigLoader is created during initialization."""
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        assert orchestrator.config_loader is not None
        assert isinstance(orchestrator.config_loader, ConfigLoader)


# ============================================================================
# CLI Argument Parsing Tests
# ============================================================================

class TestCLIArgumentParsing:
    """Test CLI argument parsing."""
    
    def test_parse_args_single_account(self):
        """Test parsing --account flag."""
        args = MasterOrchestrator.parse_args(['--account', 'work'])
        assert args.account_list == ['work']
        assert args.accounts is None
        assert args.all_accounts is False
    
    def test_parse_args_multiple_account_flags(self):
        """Test parsing multiple --account flags."""
        args = MasterOrchestrator.parse_args([
            '--account', 'work',
            '--account', 'personal'
        ])
        assert args.account_list == ['work', 'personal']
    
    def test_parse_args_comma_separated_accounts(self):
        """Test parsing --accounts with comma-separated list."""
        args = MasterOrchestrator.parse_args(['--accounts', 'work,personal'])
        assert args.accounts == 'work,personal'
        assert args.account_list is None
    
    def test_parse_args_all_accounts(self):
        """Test parsing --all-accounts flag."""
        args = MasterOrchestrator.parse_args(['--all-accounts'])
        assert args.all_accounts is True
        assert args.account_list is None
        assert args.accounts is None
    
    def test_parse_args_config_dir(self):
        """Test parsing --config-dir flag."""
        args = MasterOrchestrator.parse_args(['--config-dir', '/custom/config'])
        assert args.config_dir == '/custom/config'
    
    def test_parse_args_dry_run(self):
        """Test parsing --dry-run flag."""
        args = MasterOrchestrator.parse_args(['--dry-run'])
        assert args.dry_run is True
    
    def test_parse_args_log_level(self):
        """Test parsing --log-level flag."""
        args = MasterOrchestrator.parse_args(['--log-level', 'DEBUG'])
        assert args.log_level == 'DEBUG'
    
    def test_parse_args_defaults(self):
        """Test default argument values."""
        args = MasterOrchestrator.parse_args([])
        assert args.config_dir == 'config'
        assert args.log_level == 'INFO'
        assert args.dry_run is False


# ============================================================================
# Account Discovery Tests
# ============================================================================

class TestAccountDiscovery:
    """Test account discovery functionality."""
    
    def test_discover_available_accounts(self, master_orchestrator, temp_config_dir):
        """Test discovering available accounts."""
        accounts = master_orchestrator._discover_available_accounts()
        assert isinstance(accounts, list)
        # Should find work and personal accounts
        assert 'work' in accounts or 'personal' in accounts
    
    def test_discover_accounts_empty_directory(self, temp_config_dir):
        """Test discovery when accounts directory is empty."""
        # Remove account files
        accounts_dir = temp_config_dir / "accounts"
        for file in accounts_dir.glob("*.yaml"):
            file.unlink()
        
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        accounts = orchestrator._discover_available_accounts()
        assert accounts == []
    
    def test_discover_accounts_missing_directory(self, temp_config_dir):
        """Test discovery when accounts directory doesn't exist."""
        # Remove accounts directory and its contents
        accounts_dir = temp_config_dir / "accounts"
        import shutil
        shutil.rmtree(accounts_dir)
        
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        accounts = orchestrator._discover_available_accounts()
        assert accounts == []
    
    def test_discover_accounts_filters_examples(self, temp_config_dir):
        """Test that example files are filtered out."""
        accounts_dir = temp_config_dir / "accounts"
        (accounts_dir / "example.yaml").write_text("test: data\n")
        
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        accounts = orchestrator._discover_available_accounts()
        assert 'example' not in accounts


# ============================================================================
# Account Selection Tests
# ============================================================================

class TestAccountSelection:
    """Test account selection logic."""
    
    def test_select_accounts_single_account(self, master_orchestrator):
        """Test selecting a single account."""
        args = argparse.Namespace(
            account_list=['work'],
            accounts=None,
            all_accounts=False
        )
        master_orchestrator.config_loader._discover_available_accounts = Mock(return_value=['work', 'personal'])
        
        accounts = master_orchestrator.select_accounts(args)
        assert accounts == ['work']
    
    def test_select_accounts_multiple_flags(self, master_orchestrator):
        """Test selecting multiple accounts via --account flags."""
        args = argparse.Namespace(
            account_list=['work', 'personal'],
            accounts=None,
            all_accounts=False
        )
        master_orchestrator.config_loader._discover_available_accounts = Mock(return_value=['work', 'personal'])
        
        accounts = master_orchestrator.select_accounts(args)
        assert set(accounts) == {'work', 'personal'}
    
    def test_select_accounts_comma_separated(self, master_orchestrator):
        """Test selecting accounts via --accounts comma-separated."""
        args = argparse.Namespace(
            account_list=None,
            accounts='work,personal',
            all_accounts=False
        )
        master_orchestrator.config_loader._discover_available_accounts = Mock(return_value=['work', 'personal'])
        
        accounts = master_orchestrator.select_accounts(args)
        assert set(accounts) == {'work', 'personal'}
    
    def test_select_accounts_all(self, master_orchestrator):
        """Test selecting all accounts."""
        args = argparse.Namespace(
            account_list=None,
            accounts=None,
            all_accounts=True
        )
        master_orchestrator._discover_available_accounts = Mock(return_value=['work', 'personal'])
        
        accounts = master_orchestrator.select_accounts(args)
        assert set(accounts) == {'work', 'personal'}
    
    def test_select_accounts_default_all(self, master_orchestrator):
        """Test default behavior (all accounts when no flag specified)."""
        args = argparse.Namespace(
            account_list=None,
            accounts=None,
            all_accounts=False
        )
        master_orchestrator._discover_available_accounts = Mock(return_value=['work', 'personal'])
        
        accounts = master_orchestrator.select_accounts(args)
        assert set(accounts) == {'work', 'personal'}
    
    def test_select_accounts_invalid_account(self, master_orchestrator):
        """Test that invalid account raises ValueError."""
        args = argparse.Namespace(
            account_list=['invalid'],
            accounts=None,
            all_accounts=False
        )
        master_orchestrator._discover_available_accounts = Mock(return_value=['work', 'personal'])
        
        with pytest.raises(ValueError, match="Unknown account"):
            master_orchestrator.select_accounts(args)
    
    def test_select_accounts_no_accounts_available(self, master_orchestrator):
        """Test error when no accounts are available."""
        args = argparse.Namespace(
            account_list=None,
            accounts=None,
            all_accounts=True
        )
        master_orchestrator._discover_available_accounts = Mock(return_value=[])
        
        with pytest.raises(ConfigurationError, match="No accounts found"):
            master_orchestrator.select_accounts(args)


# ============================================================================
# AccountProcessor Creation Tests
# ============================================================================

class TestAccountProcessorCreation:
    """Test AccountProcessor creation."""
    
    def test_create_account_processor(self, master_orchestrator, mock_config_loader):
        """Test creating an AccountProcessor instance."""
        # Mock the config to include classification model
        mock_config = {
            'classification': {
                'model': 'test-model'
            },
            'imap': {
                'server': 'test.imap.com',
                'port': 993,
                'username': 'test@example.com'
            },
            'paths': {
                'obsidian_vault': '/tmp/vault',
                'template_file': '/tmp/template.md.j2'
            }
        }
        mock_config_loader.load_merged_config.return_value = mock_config
        
        with patch('src.orchestrator.AccountProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            
            processor = master_orchestrator.create_account_processor('work')
            
            assert processor is not None
            mock_config_loader.load_merged_config.assert_called_once_with('work')
            mock_processor_class.assert_called_once()
    
    def test_create_account_processor_config_error(self, master_orchestrator, mock_config_loader):
        """Test error handling when config loading fails."""
        mock_config_loader.load_merged_config.side_effect = FileNotFoundError("Config not found")
        
        with pytest.raises(ConfigurationError, match="Failed to load configuration"):
            master_orchestrator.create_account_processor('work')
    
    def test_create_account_processor_initializes_services(self, master_orchestrator, mock_config_loader):
        """Test that account processor is created with proper config."""
        # Mock the config to include classification model
        mock_config = {
            'classification': {
                'model': 'test-model'
            },
            'imap': {
                'server': 'test.imap.com',
                'port': 993,
                'username': 'test@example.com'
            },
            'paths': {
                'obsidian_vault': '/tmp/vault',
                'template_file': '/tmp/template.md.j2'
            }
        }
        mock_config_loader.load_merged_config.return_value = mock_config
        
        with patch('src.orchestrator.AccountProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            
            processor = master_orchestrator.create_account_processor('work')
            
            assert processor is not None
            mock_config_loader.load_merged_config.assert_called_once_with('work')


# ============================================================================
# Shared Services Initialization Tests
# ============================================================================

# V3 shared services tests removed - V4 creates components per-account, not as shared services


# ============================================================================
# Orchestration Run Tests
# ============================================================================

class TestOrchestrationRun:
    """Test main orchestration run method."""
    
    def test_run_single_account_success(self, master_orchestrator, mock_account_processor):
        """Test successful processing of a single account."""
        # Setup mocks
        args = create_test_args(account_list=['work'])
        master_orchestrator.parse_args = Mock(return_value=args)
        
        def select_accounts_side_effect(args):
            master_orchestrator.accounts_to_process = ['work']
            return ['work']
        master_orchestrator.select_accounts = Mock(side_effect=select_accounts_side_effect)
        master_orchestrator.create_account_processor = Mock(return_value=mock_account_processor)
        
        # Mock context manager and logging functions
        with patch('src.orchestrator.with_account_context') as mock_context, \
             patch('src.orchestrator.log_account_start'), \
             patch('src.orchestrator.log_account_end'), \
             patch('src.orchestrator.log_error_with_context'), \
             patch('src.orchestrator.set_correlation_id'):
            mock_context.return_value.__enter__ = Mock()
            mock_context.return_value.__exit__ = Mock(return_value=False)
            
            result = master_orchestrator.run(['--account', 'work'])
            
            assert result.total_accounts == 1
            assert result.successful_accounts == 1
            assert result.failed_accounts == 0
            mock_account_processor.setup.assert_called_once()
            mock_account_processor.run.assert_called_once()
            # Teardown may be called multiple times (try block + finally block)
            assert mock_account_processor.teardown.call_count >= 1
    
    def test_run_multiple_accounts_success(self, master_orchestrator, mock_account_processor):
        """Test successful processing of multiple accounts."""
        work_processor = Mock()
        work_processor.setup = Mock()
        work_processor.run = Mock()
        work_processor.teardown = Mock()
        
        personal_processor = Mock()
        personal_processor.setup = Mock()
        personal_processor.run = Mock()
        personal_processor.teardown = Mock()
        
        args = create_test_args(all_accounts=True)
        master_orchestrator.parse_args = Mock(return_value=args)
        
        def select_accounts_side_effect(args):
            master_orchestrator.accounts_to_process = ['work', 'personal']
            return ['work', 'personal']
        master_orchestrator.select_accounts = Mock(side_effect=select_accounts_side_effect)
        master_orchestrator.create_account_processor = Mock(side_effect=[
            work_processor,
            personal_processor
        ])
        
        # Mock context manager and logging functions
        with patch('src.orchestrator.with_account_context') as mock_context, \
             patch('src.orchestrator.log_account_start'), \
             patch('src.orchestrator.log_account_end'), \
             patch('src.orchestrator.log_error_with_context'), \
             patch('src.orchestrator.set_correlation_id'):
            mock_context.return_value.__enter__ = Mock()
            mock_context.return_value.__exit__ = Mock(return_value=False)
            
            result = master_orchestrator.run(['--all-accounts'])
            
            assert result.total_accounts == 2
            assert result.successful_accounts == 2
            assert result.failed_accounts == 0
            assert work_processor.setup.called
            assert personal_processor.setup.called
    
    def test_run_account_setup_failure(self, master_orchestrator, mock_account_processor):
        """Test handling of account setup failure."""
        mock_account_processor.setup.side_effect = AccountProcessorSetupError("Setup failed")
        
        args = argparse.Namespace(
            account_list=['work'],
            accounts=None,
            all_accounts=False,
            config_dir=None,
            log_level=None,
            dry_run=False
        )
        master_orchestrator.parse_args = Mock(return_value=args)
        
        def select_accounts_side_effect(args):
            master_orchestrator.accounts_to_process = ['work']
            return ['work']
        master_orchestrator.select_accounts = Mock(side_effect=select_accounts_side_effect)
        master_orchestrator.create_account_processor = Mock(return_value=mock_account_processor)
        
        # Mock context manager and logging functions
        with patch('src.orchestrator.with_account_context') as mock_context, \
             patch('src.orchestrator.log_account_start'), \
             patch('src.orchestrator.log_account_end'), \
             patch('src.orchestrator.log_error_with_context'), \
             patch('src.orchestrator.set_correlation_id'):
            mock_context.return_value.__enter__ = Mock()
            mock_context.return_value.__exit__ = Mock(return_value=False)
            
            result = master_orchestrator.run(['--account', 'work'])
            
            assert result.total_accounts == 1
            assert result.successful_accounts == 0
            assert result.failed_accounts == 1
            assert 'work' in result.account_results
            assert result.account_results['work'][0] is False
            # Teardown should still be called
            mock_account_processor.teardown.assert_called_once()
    
    def test_run_account_processing_failure(self, master_orchestrator, mock_account_processor):
        """Test handling of account processing failure."""
        mock_account_processor.setup = Mock()
        mock_account_processor.run.side_effect = AccountProcessorRunError("Processing failed")
        
        args = create_test_args(account_list=['work'])
        master_orchestrator.parse_args = Mock(return_value=args)
        
        def select_accounts_side_effect(args):
            master_orchestrator.accounts_to_process = ['work']
            return ['work']
        master_orchestrator.select_accounts = Mock(side_effect=select_accounts_side_effect)
        master_orchestrator.create_account_processor = Mock(return_value=mock_account_processor)
        
        # Mock context manager and logging functions
        with patch('src.orchestrator.with_account_context') as mock_context, \
             patch('src.orchestrator.log_account_start'), \
             patch('src.orchestrator.log_account_end'), \
             patch('src.orchestrator.log_error_with_context'), \
             patch('src.orchestrator.set_correlation_id'):
            mock_context.return_value.__enter__ = Mock()
            mock_context.return_value.__exit__ = Mock(return_value=False)
            
            result = master_orchestrator.run(['--account', 'work'])
            
            assert result.failed_accounts == 1
            assert result.account_results['work'][0] is False
    
    def test_run_partial_failure_continues(self, master_orchestrator):
        """Test that partial failures don't stop processing of other accounts."""
        work_processor = Mock()
        work_processor.setup = Mock()
        work_processor.run = Mock()
        work_processor.teardown = Mock()
        
        personal_processor = Mock()
        personal_processor.setup = Mock()
        personal_processor.run.side_effect = AccountProcessorRunError("Failed")
        personal_processor.teardown = Mock()
        
        args = create_test_args(all_accounts=True)
        master_orchestrator.parse_args = Mock(return_value=args)
        
        def select_accounts_side_effect(args):
            master_orchestrator.accounts_to_process = ['work', 'personal']
            return ['work', 'personal']
        master_orchestrator.select_accounts = Mock(side_effect=select_accounts_side_effect)
        master_orchestrator.create_account_processor = Mock(side_effect=[
            work_processor,
            personal_processor
        ])
        
        # Mock context manager and logging functions
        with patch('src.orchestrator.with_account_context') as mock_context, \
             patch('src.orchestrator.log_account_start'), \
             patch('src.orchestrator.log_account_end'), \
             patch('src.orchestrator.log_error_with_context'), \
             patch('src.orchestrator.set_correlation_id'):
            mock_context.return_value.__enter__ = Mock()
            mock_context.return_value.__exit__ = Mock(return_value=False)
            
            result = master_orchestrator.run(['--all-accounts'])
            
            assert result.total_accounts == 2
            assert result.successful_accounts == 1
            assert result.failed_accounts == 1
            # Both should have been attempted
            assert work_processor.setup.called
            assert personal_processor.setup.called
    
    def test_run_no_accounts_selected(self, master_orchestrator):
        """Test run when no accounts are selected."""
        master_orchestrator.parse_args = Mock(return_value=argparse.Namespace(
            account_list=None,
            accounts=None,
            all_accounts=False,
            config_dir=None,
            log_level=None,
            dry_run=False
        ))
        master_orchestrator.select_accounts = Mock(return_value=[])
        
        result = master_orchestrator.run([])
        
        assert result.total_accounts == 0
        assert result.successful_accounts == 0
        assert result.failed_accounts == 0
    
    def test_run_teardown_on_failure(self, master_orchestrator, mock_account_processor):
        """Test that teardown is called even when processing fails."""
        mock_account_processor.setup = Mock()
        mock_account_processor.run.side_effect = AccountProcessorRunError("Error")
        mock_account_processor.teardown = Mock()
        
        args = argparse.Namespace(
            account_list=['work'],
            accounts=None,
            all_accounts=False,
            config_dir=None,
            log_level=None,
            dry_run=False
        )
        master_orchestrator.parse_args = Mock(return_value=args)
        
        def select_accounts_side_effect(args):
            master_orchestrator.accounts_to_process = ['work']
            return ['work']
        master_orchestrator.select_accounts = Mock(side_effect=select_accounts_side_effect)
        master_orchestrator.create_account_processor = Mock(return_value=mock_account_processor)
        
        # Mock context manager and logging functions
        with patch('src.orchestrator.with_account_context') as mock_context, \
             patch('src.orchestrator.log_account_start'), \
             patch('src.orchestrator.log_account_end'), \
             patch('src.orchestrator.log_error_with_context'), \
             patch('src.orchestrator.set_correlation_id'):
            mock_context.return_value.__enter__ = Mock()
            mock_context.return_value.__exit__ = Mock(return_value=False)
            
            master_orchestrator.run(['--account', 'work'])
            
            # Teardown should be called even after failure
            mock_account_processor.teardown.assert_called_once()
    
    def test_run_tracks_timing(self, master_orchestrator, mock_account_processor):
        """Test that orchestration tracks timing information."""
        master_orchestrator.parse_args = Mock(return_value=argparse.Namespace(
            account_list=['work'],
            accounts=None,
            all_accounts=False,
            config_dir=None,
            log_level=None,
            dry_run=False
        ))
        
        # Mock select_accounts to return accounts AND set accounts_to_process
        def mock_select_accounts(args):
            master_orchestrator.accounts_to_process = ['work']
            return ['work']
        master_orchestrator.select_accounts = Mock(side_effect=mock_select_accounts)
        master_orchestrator.create_account_processor = Mock(return_value=mock_account_processor)
        
        result = master_orchestrator.run(['--account', 'work'])
        
        assert result.total_time > 0
        assert hasattr(result, 'total_time')


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and isolation."""
    
    def test_config_dir_override(self, master_orchestrator, tmp_path):
        """Test that --config-dir overrides default."""
        new_config_dir = tmp_path / "new_config"
        new_config_dir.mkdir()
        
        master_orchestrator.parse_args = Mock(return_value=argparse.Namespace(
            account_list=None,
            accounts=None,
            all_accounts=False,
            config_dir=str(new_config_dir),
            log_level=None,
            dry_run=False
        ))
        master_orchestrator.select_accounts = Mock(return_value=[])
        
        master_orchestrator.run(['--config-dir', str(new_config_dir)])
        
        assert master_orchestrator.config_base_dir == new_config_dir.resolve()
    
    def test_log_level_override(self, master_orchestrator):
        """Test that --log-level sets logging level."""
        master_orchestrator.parse_args = Mock(return_value=argparse.Namespace(
            account_list=None,
            accounts=None,
            all_accounts=False,
            config_dir=None,
            log_level='DEBUG',
            dry_run=False
        ))
        master_orchestrator.select_accounts = Mock(return_value=[])
        
        master_orchestrator.run(['--log-level', 'DEBUG'])
        
        # Verify logging level was set (check logger level)
        assert logging.getLogger().level <= logging.DEBUG
