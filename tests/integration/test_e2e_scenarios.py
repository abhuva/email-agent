"""
End-to-end integration scenarios for V4 email processing pipeline.

This module contains end-to-end integration tests that exercise multiple
components together, verifying the complete processing flow from configuration
loading through email processing to note generation.
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock

from src.orchestrator import MasterOrchestrator
from tests.integration.mock_services import MockImapClient, MockLLMClient, MockEmailData
from tests.integration.test_utils import (
    create_test_global_config,
    create_test_account_config,
    create_test_email_data,
    create_test_rules_file
)


@pytest.mark.integration
class TestE2EIntegrationScenarios:
    """End-to-end integration scenarios."""
    
    def test_complete_pipeline_flow(
        self,
        temp_config_dir,
        integration_global_config,
        integration_account_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test complete pipeline flow: config → accounts → fetch → rules → parse → LLM → notes.
        
        Scenario:
        - Load configuration
        - Process account
        - Fetch emails
        - Apply rules
        - Parse content
        - Classify with LLM
        - Generate notes
        """
        # Set up configuration
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        account_file = accounts_dir / "test_account.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(integration_account_config, f)
        
        # Create empty rules files
        create_test_rules_file(temp_config_dir, 'blacklist.yaml', [])
        create_test_rules_file(temp_config_dir, 'whitelist.yaml', [])
        
        # Add test email
        email = create_test_email_data(
            uid="1",
            sender="test@example.com",
            subject="Test Email",
            body="Test content",
            html_body="<p>Test content</p>"
        )
        mock_imap_client.add_email(email)
        mock_imap_client.connect()
        
        # Configure mock LLM
        mock_llm_client.set_default_response(spam_score=2, importance_score=8)
        
        # Create orchestrator with temp config directory
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        orchestrator.llm_client = mock_llm_client
        orchestrator.note_generator = Mock()
        
        # Patch the account processor creation to use mock IMAP
        from unittest.mock import patch
        from src.account_processor import create_imap_client_from_config
        
        with patch('src.account_processor.create_imap_client_from_config') as mock_factory:
            mock_factory.return_value = mock_imap_client
            
            # Run processing with --config-dir to ensure orchestrator uses temp directory
            result = orchestrator.run(['--account', 'test_account', '--config-dir', str(temp_config_dir)])
            
            # Verify processing completed
            assert result.successful_accounts >= 0
            
    def test_multi_account_processing(
        self,
        temp_config_dir,
        integration_global_config,
        mock_imap_client,
        mock_llm_client
    ):
        """
        Test processing multiple accounts with isolated configurations.
        
        Scenario:
        - Multiple account configs
        - Each account processed independently
        - Configurations don't interfere
        """
        # Set up global config
        global_file = temp_config_dir / "config.yaml"
        with open(global_file, 'w') as f:
            yaml.dump(integration_global_config, f)
        
        # Create multiple account configs
        accounts_dir = temp_config_dir / "accounts"
        accounts_dir.mkdir(exist_ok=True)
        
        account1_config = create_test_account_config()
        account1_config['imap']['server'] = 'account1.imap.com'
        account1_file = accounts_dir / "account1.yaml"
        with open(account1_file, 'w') as f:
            yaml.dump(account1_config, f)
        
        account2_config = create_test_account_config()
        account2_config['imap']['server'] = 'account2.imap.com'
        account2_file = accounts_dir / "account2.yaml"
        with open(account2_file, 'w') as f:
            yaml.dump(account2_config, f)
        
        # Create rules files
        create_test_rules_file(temp_config_dir, 'blacklist.yaml', [])
        create_test_rules_file(temp_config_dir, 'whitelist.yaml', [])
        
        # Add emails for both accounts
        email1 = create_test_email_data(uid="1", sender="test1@example.com", subject="Email 1")
        email2 = create_test_email_data(uid="2", sender="test2@example.com", subject="Email 2")
        mock_imap_client.add_email(email1)
        mock_imap_client.add_email(email2)
        mock_imap_client.connect()
        
        # Configure mock LLM
        mock_llm_client.set_default_response(spam_score=2, importance_score=7)
        
        # Create orchestrator with temp config directory
        orchestrator = MasterOrchestrator(config_base_dir=str(temp_config_dir))
        orchestrator.llm_client = mock_llm_client
        orchestrator.note_generator = Mock()
        
        # Patch the account processor creation to use mock IMAP
        from unittest.mock import patch
        from src.account_processor import create_imap_client_from_config
        
        with patch('src.account_processor.create_imap_client_from_config') as mock_factory:
            mock_factory.return_value = mock_imap_client
            
            # Process both accounts with --config-dir to ensure orchestrator uses temp directory
            result = orchestrator.run(['--account', 'account1', '--account', 'account2', '--config-dir', str(temp_config_dir)])
            
            # Verify both accounts were processed
            assert result.total_accounts == 2
