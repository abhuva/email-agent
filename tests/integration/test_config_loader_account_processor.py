"""
Integration tests for ConfigLoader ↔ AccountProcessor interaction.

This module tests the integration between ConfigLoader and AccountProcessor,
verifying that:
- ConfigLoader correctly provides configuration to AccountProcessor
- AccountProcessor correctly uses configuration from ConfigLoader
- Configuration defaults and overrides are honored
- Invalid configurations are handled gracefully
- Multiple accounts are processed correctly with isolated configs
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.config_loader import ConfigLoader, ConfigurationError
from src.account_processor import AccountProcessor, AccountProcessorSetupError
from src.orchestrator import MasterOrchestrator
from tests.integration.mock_services import MockImapClient, MockLLMClient
from tests.integration.test_utils import (
    create_test_global_config,
    create_test_account_config
)


class TestConfigLoaderAccountProcessorIntegration:
    """Integration tests for ConfigLoader and AccountProcessor."""
    
    def test_valid_config_creates_account_processor(
        self,
        temp_config_dir,
        integration_global_config,
        integration_account_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that valid configuration from ConfigLoader creates AccountProcessor correctly.
        
        Scenario:
        - ConfigLoader loads valid global + account config
        - AccountProcessor is created with merged config
        - AccountProcessor uses config values correctly
        """
        # Set up configuration files
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "test_account.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(integration_account_config, f)
        
        # Create ConfigLoader
        loader = ConfigLoader(base_dir=temp_config_dir)
        
        # Load merged config
        merged_config = loader.load_merged_config('test_account')
        
        # Verify config was merged correctly
        assert merged_config['imap']['server'] == integration_account_config['imap']['server']
        assert merged_config['imap']['port'] == integration_global_config['imap']['port']
        
        # Create AccountProcessor with mock dependencies
        def mock_imap_factory(config):
            assert config['imap']['server'] == integration_account_config['imap']['server']
            return mock_imap_client
        
        processor = AccountProcessor(
            account_id='test_account',
            account_config=merged_config,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        # Verify processor was created with correct config
        assert processor.account_id == 'test_account'
        assert processor.config['imap']['server'] == integration_account_config['imap']['server']
        
    def test_config_defaults_are_honored(
        self,
        temp_config_dir,
        integration_global_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that configuration defaults from global config are honored.
        
        Scenario:
        - Global config has default values
        - Account config doesn't override all fields
        - AccountProcessor uses defaults for non-overridden fields
        """
        # Create global config with defaults
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        # Create account config with minimal overrides
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "minimal_account.yaml"
        minimal_account_config = {
            'imap': {
                'username': 'minimal@example.com'
            }
        }
        with open(account_file, 'w') as f:
            yaml.dump(minimal_account_config, f)
        
        # Load merged config
        loader = ConfigLoader(base_dir=temp_config_dir)
        merged_config = loader.load_merged_config('minimal_account')
        
        # Verify defaults are preserved
        assert merged_config['imap']['server'] == integration_global_config['imap']['server']
        assert merged_config['imap']['port'] == integration_global_config['imap']['port']
        assert merged_config['imap']['username'] == 'minimal@example.com'
        
        # Create AccountProcessor
        def mock_imap_factory(config):
            return mock_imap_client
        
        processor = AccountProcessor(
            account_id='minimal_account',
            account_config=merged_config,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        # Verify processor uses default values
        assert processor.config['imap']['server'] == integration_global_config['imap']['server']
        assert processor.config['imap']['port'] == integration_global_config['imap']['port']
        
    def test_config_overrides_are_applied(
        self,
        temp_config_dir,
        integration_global_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that account-specific configuration overrides are applied.
        
        Scenario:
        - Global config has default values
        - Account config overrides specific fields
        - AccountProcessor uses overridden values
        """
        # Create global config
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        # Create account config with overrides
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "override_account.yaml"
        override_account_config = {
            'imap': {
                'server': 'override.imap.com',
                'port': 143,
                'username': 'override@example.com'
            },
            'processing': {
                'importance_threshold': 9
            }
        }
        with open(account_file, 'w') as f:
            yaml.dump(override_account_config, f)
        
        # Load merged config
        loader = ConfigLoader(base_dir=temp_config_dir)
        merged_config = loader.load_merged_config('override_account')
        
        # Verify overrides are applied
        assert merged_config['imap']['server'] == 'override.imap.com'
        assert merged_config['imap']['port'] == 143
        assert merged_config['processing']['importance_threshold'] == 9
        
        # Create AccountProcessor
        def mock_imap_factory(config):
            assert config['imap']['server'] == 'override.imap.com'
            assert config['imap']['port'] == 143
            return mock_imap_client
        
        processor = AccountProcessor(
            account_id='override_account',
            account_config=merged_config,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        # Verify processor uses overridden values
        assert processor.config['imap']['server'] == 'override.imap.com'
        assert processor.config['imap']['port'] == 143
        
    def test_invalid_config_handled_gracefully(
        self,
        temp_config_dir,
        integration_global_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that invalid configuration entries are handled gracefully.
        
        Scenario:
        - Account config has invalid/missing required fields
        - ConfigLoader validation catches errors
        - AccountProcessor creation fails gracefully
        """
        # Create global config
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        # Create account config with missing required fields
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "invalid_account.yaml"
        invalid_account_config = {
            'imap': {
                # Missing server, port, username
            }
        }
        with open(account_file, 'w') as f:
            yaml.dump(invalid_account_config, f)
        
        # Load merged config with validation disabled to test AccountProcessor error handling
        loader = ConfigLoader(base_dir=temp_config_dir, enable_validation=False)
        merged_config = loader.load_merged_config('invalid_account')
        
        # Try to create AccountProcessor - should fail due to missing IMAP fields
        # The actual factory (create_imap_client_from_config) will raise AccountProcessorSetupError
        # when required IMAP fields are missing
        from src.account_processor import create_imap_client_from_config
        
        with pytest.raises(AccountProcessorSetupError):
            processor = AccountProcessor(
                account_id='invalid_account',
                account_config=merged_config,
                imap_client_factory=create_imap_client_from_config,
                llm_client=mock_llm_client,
                blacklist_service=lambda x: [],
                whitelist_service=lambda x: [],
                note_generator=Mock(),
                parser=lambda html, text: (text, False)
            )
            processor.setup()  # Setup should fail when creating IMAP client
            
    def test_multiple_accounts_isolated_configs(
        self,
        temp_config_dir,
        integration_global_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that multiple accounts have isolated configurations.
        
        Scenario:
        - Multiple account configs exist
        - Each AccountProcessor gets its own isolated config
        - Configs don't interfere with each other
        """
        # Create global config
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        # Create multiple account configs
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        
        account1_config = {
            'imap': {
                'server': 'account1.imap.com',
                'username': 'account1@example.com'
            }
        }
        account1_file = accounts_dir / "account1.yaml"
        with open(account1_file, 'w') as f:
            yaml.dump(account1_config, f)
        
        account2_config = {
            'imap': {
                'server': 'account2.imap.com',
                'username': 'account2@example.com'
            }
        }
        account2_file = accounts_dir / "account2.yaml"
        with open(account2_file, 'w') as f:
            yaml.dump(account2_config, f)
        
        # Load configs for both accounts
        loader = ConfigLoader(base_dir=temp_config_dir)
        config1 = loader.load_merged_config('account1')
        config2 = loader.load_merged_config('account2')
        
        # Verify configs are different
        assert config1['imap']['server'] == 'account1.imap.com'
        assert config2['imap']['server'] == 'account2.imap.com'
        
        # Create AccountProcessors
        def mock_imap_factory(config):
            return mock_imap_client
        
        processor1 = AccountProcessor(
            account_id='account1',
            account_config=config1,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        processor2 = AccountProcessor(
            account_id='account2',
            account_config=config2,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        # Verify processors have isolated configs
        assert processor1.config['imap']['server'] == 'account1.imap.com'
        assert processor2.config['imap']['server'] == 'account2.imap.com'
        assert processor1.account_id == 'account1'
        assert processor2.account_id == 'account2'
        
    def test_master_orchestrator_integration(
        self,
        temp_config_dir,
        integration_global_config,
        integration_account_config,
        mock_llm_client
    ):
        """
        Test integration through MasterOrchestrator.create_account_processor.
        
        Scenario:
        - MasterOrchestrator uses ConfigLoader to load config
        - Creates AccountProcessor with loaded config
        - Integration point works correctly
        """
        # Set up configuration files
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "test_account.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(integration_account_config, f)
        
        # Create MasterOrchestrator (it creates ConfigLoader internally)
        orchestrator = MasterOrchestrator(
            config_base_dir=str(temp_config_dir)
        )
        
        # Mock the LLM client and note generator on orchestrator
        orchestrator.llm_client = mock_llm_client
        orchestrator.note_generator = Mock()
        
        # Create AccountProcessor through orchestrator
        processor = orchestrator.create_account_processor('test_account')
        
        # Verify processor was created correctly
        assert processor.account_id == 'test_account'
        assert processor.config['imap']['server'] == integration_account_config['imap']['server']
        
    def test_empty_configuration_handled(
        self,
        temp_config_dir,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that empty configuration is handled gracefully.
        
        Scenario:
        - Global config is empty or minimal
        - Account config doesn't exist
        - System handles gracefully
        """
        # Create minimal global config
        global_file = temp_config_dir / "config.yaml"
        minimal_config = {'imap': {}}
        with open(global_file, 'w') as f:
            yaml.dump(minimal_config, f)
        
        # Try to load non-existent account config
        loader = ConfigLoader(base_dir=temp_config_dir)
        
        with pytest.raises((FileNotFoundError, ConfigurationError)):
            loader.load_merged_config('nonexistent_account')
            
    def test_duplicate_accounts_handled(
        self,
        temp_config_dir,
        integration_global_config,
        integration_account_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test that duplicate account configurations are handled.
        
        Scenario:
        - Same account config loaded multiple times
        - Each AccountProcessor gets fresh config (not shared reference)
        - Configs are isolated
        """
        # Set up configuration files
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "duplicate_account.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(integration_account_config, f)
        
        # Load config multiple times
        loader = ConfigLoader(base_dir=temp_config_dir)
        config1 = loader.load_merged_config('duplicate_account')
        config2 = loader.load_merged_config('duplicate_account')
        
        # Verify configs are separate objects (not shared)
        assert config1 is not config2
        assert config1 == config2  # But values are equal
        
        # Create AccountProcessors
        def mock_imap_factory(config):
            return mock_imap_client
        
        processor1 = AccountProcessor(
            account_id='duplicate_account',
            account_config=config1,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        processor2 = AccountProcessor(
            account_id='duplicate_account',
            account_config=config2,
            imap_client_factory=mock_imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=lambda x: [],
            whitelist_service=lambda x: [],
            note_generator=Mock(),
            parser=lambda html, text: (text, False)
        )
        
        # Verify processors are separate instances
        assert processor1 is not processor2
        assert processor1.config is not processor2.config
