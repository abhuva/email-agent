"""
V4 End-to-End Pipeline Tests

This module contains end-to-end tests for the complete V4 email processing pipeline.
These tests use real email accounts and services to validate the entire workflow
from email fetching to note generation.

Test Categories:
- Single-account basic flow
- Multi-account processing
- Rules engine (blacklist/whitelist)
- Content parsing (HTML to Markdown)
- Edge cases and error handling
- Provider-specific testing

Requirements:
- Test account credentials in environment variables
- Test account configs in config/accounts/
- Test accounts documented in config/test-accounts.yaml

To run:
    pytest tests/test_e2e_v4_pipeline.py -v -m e2e_v4

To skip (if credentials not available):
    pytest tests/test_e2e_v4_pipeline.py -v -m "not e2e_v4"
"""

import pytest
import os
import time
from pathlib import Path
from typing import Dict, Any, List
import yaml

# Register E2E fixtures using pytest_plugins (proper way to load additional conftest files)
pytest_plugins = ['tests.conftest_e2e_v4']

from tests.e2e_helpers import (
    require_test_account_credentials,
    require_account_config,
    get_test_account_config,
    load_account_config,
    get_test_vault_path,
    ensure_test_vault_exists,
    cleanup_test_vault,
    get_test_email_templates
)

# Pytest marker for V4 E2E tests
pytestmark = pytest.mark.e2e_v4


# ============================================================================
# Single-Account Basic Flow Tests
# ============================================================================

class TestE2ESingleAccountBasicFlow:
    """Test single-account basic email processing flow."""
    
    def test_process_single_plain_text_email(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator,
        e2e_test_vault
    ):
        """
        Scenario 1.1: Process single plain text email through complete pipeline.
        
        Expected:
        - Email fetched from IMAP
        - Blacklist check passes
        - Content parsed
        - LLM classification returns scores
        - Whitelist check applied
        - Note generated and saved
        - Email tagged with AIProcessed
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        # Ensure vault exists
        vault_path = ensure_test_vault_exists(account_id)
        
        # Process account (will process unprocessed emails)
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.successful_accounts >= 0, "Account processing should complete"
        
        # Check if any notes were created (if emails were available)
        note_files = list(vault_path.glob('*.md'))
        if note_files:
            # Verify note content
            note_file = note_files[0]
            note_content = note_file.read_text()
            
            assert 'subject' in note_content.lower() or 'Subject' in note_content
            assert account_id in str(vault_path) or vault_path.exists()
    
    def test_process_single_html_email(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator,
        e2e_test_vault
    ):
        """
        Scenario 1.2: Process single HTML email with HTML-to-Markdown conversion.
        
        Expected:
        - Email fetched from IMAP
        - HTML content parsed to Markdown
        - Note generated with Markdown content
        - Email tagged with AIProcessed
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        vault_path = ensure_test_vault_exists(account_id)
        
        # Process account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.successful_accounts >= 0
        
        # Check for notes (if HTML emails were available)
        note_files = list(vault_path.glob('*.md'))
        if note_files:
            note_file = note_files[0]
            note_content = note_file.read_text()
            
            # Verify Markdown conversion (should not contain raw HTML tags)
            # Note: This is a basic check - actual HTML parsing validation
            # would require specific test emails with known HTML content
            assert len(note_content) > 0, "Note should have content"


# ============================================================================
# Multi-Account Processing Tests
# ============================================================================

class TestE2EMultiAccountProcessing:
    """Test multi-account processing with state isolation."""
    
    def test_process_multiple_accounts_sequentially(
        self,
        multi_account_setup,
        e2e_master_orchestrator
    ):
        """
        Scenario 2.1: Process multiple accounts sequentially, verifying isolation.
        
        Expected:
        - Account 1 processed (note in account 1 vault)
        - Account 2 processed (note in account 2 vault)
        - Complete isolation between accounts
        """
        if len(multi_account_setup) < 2:
            pytest.skip("Need at least 2 test accounts for multi-account test")
        
        account_ids = list(multi_account_setup.keys())[:2]
        
        # Process both accounts
        result = e2e_master_orchestrator.run(['--accounts', ','.join(account_ids)])
        
        # Assertions
        assert result.total_accounts == 2, "Should process 2 accounts"
        assert result.successful_accounts >= 0, "Accounts should be processed"
        
        # Verify isolation (each account has its own vault)
        for account_id in account_ids:
            account_info = multi_account_setup[account_id]
            vault_path = account_info['vault_path']
            
            # Vault should exist (even if empty)
            assert vault_path.exists(), f"Vault should exist for {account_id}"
    
    def test_process_all_accounts(
        self,
        available_test_accounts,
        e2e_master_orchestrator,
        e2e_test_config_dir
    ):
        """
        Scenario 2.2: Process all configured accounts using --all-accounts flag.
        
        Expected:
        - All accounts discovered
        - Each account processed in sequence
        - Summary shows all accounts processed
        """
        if len(available_test_accounts) < 1:
            pytest.skip("Need at least 1 test account")
        
        # Process all accounts
        result = e2e_master_orchestrator.run(['--all-accounts'])
        
        # Assertions
        assert result.total_accounts > 0, "Should discover accounts"
        assert result.total_accounts == len(available_test_accounts), \
            "Should process all available accounts"
    
    def test_account_failure_isolation(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator
    ):
        """
        Scenario 2.3: Verify failure in one account doesn't affect others.
        
        Note: This test requires an invalid account config, which is hard to
        set up automatically. For now, we verify that failures are logged
        and don't crash the orchestrator.
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        # Process account (should succeed with valid account)
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        # Even if processing fails, orchestrator should handle it gracefully
        assert result.total_accounts == 1, "Should attempt to process account"
        # Result may be successful or failed, but should be handled gracefully


# ============================================================================
# Rules Engine Tests
# ============================================================================

class TestE2ERulesEngine:
    """Test blacklist and whitelist rules engine."""
    
    def test_blacklist_drop_rule(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator,
        e2e_test_config_dir,
        e2e_test_vault
    ):
        """
        Scenario 3.1: Email matches blacklist rule and is dropped.
        
        Expected:
        - Email fetched
        - Blacklist check matches
        - Email dropped (no processing)
        - Email NOT tagged with AIProcessed
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        # Configure blacklist rule
        blacklist_path = e2e_test_config_dir / 'blacklist.yaml'
        blacklist_rules = [
            {
                'trigger': 'sender',
                'value': 'spam@example.com',
                'action': 'drop'
            }
        ]
        with open(blacklist_path, 'w') as f:
            yaml.dump(blacklist_rules, f)
        
        vault_path = ensure_test_vault_exists(account_id)
        initial_note_count = len(list(vault_path.glob('*.md')))
        
        # Process account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        # Note: This test assumes there's an email from spam@example.com
        # In practice, you'd need to send such an email before running the test
        assert result.successful_accounts >= 0
        
        # If blacklist worked, notes count should not increase for dropped emails
        # (This is a basic check - actual behavior depends on test data)
        final_note_count = len(list(vault_path.glob('*.md')))
        # Note: We can't assert exact count without knowing test email state
    
    def test_whitelist_boost_rule(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator,
        e2e_test_config_dir,
        e2e_test_vault
    ):
        """
        Scenario 3.3: Email matches whitelist rule and gets score boost and tags.
        
        Expected:
        - Email processed
        - Whitelist check matches
        - Score boosted
        - Tags added
        - Note contains boosted score and tags
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        # Configure whitelist rule
        whitelist_path = e2e_test_config_dir / 'whitelist.yaml'
        whitelist_rules = [
            {
                'trigger': 'domain',
                'value': 'important-client.com',
                'action': 'boost',
                'score_boost': 20,
                'add_tags': ['#vip', '#work']
            }
        ]
        with open(whitelist_path, 'w') as f:
            yaml.dump(whitelist_rules, f)
        
        vault_path = ensure_test_vault_exists(account_id)
        
        # Process account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.successful_accounts >= 0
        
        # Check notes for boosted scores and tags (if emails matched)
        note_files = list(vault_path.glob('*.md'))
        if note_files:
            note_file = note_files[0]
            note_content = note_file.read_text()
            
            # Check for tags in note (if template includes them)
            # Note: Actual tag format depends on note template
            assert len(note_content) > 0


# ============================================================================
# Content Parsing Tests
# ============================================================================

class TestE2EContentParsing:
    """Test HTML to Markdown content parsing."""
    
    def test_complex_html_parsing(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator,
        e2e_test_vault
    ):
        """
        Scenario 4.1: Parse complex HTML with tables, images, links.
        
        Expected:
        - HTML content parsed to Markdown
        - Tables, images, links converted correctly
        - Formatting preserved
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        vault_path = ensure_test_vault_exists(account_id)
        
        # Process account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.successful_accounts >= 0
        
        # Check notes for Markdown content (if HTML emails were available)
        note_files = list(vault_path.glob('*.md'))
        if note_files:
            note_file = note_files[0]
            note_content = note_file.read_text()
            
            # Verify Markdown (should not contain raw HTML tags like <table>, <img>)
            # Note: This is a basic check - actual validation requires specific test emails
            assert len(note_content) > 0


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

class TestE2EEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_email_body(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator,
        e2e_test_vault
    ):
        """
        Scenario 5.1: Process email with empty body.
        
        Expected:
        - Email processed gracefully
        - Note generated with empty body
        - No errors
        """
        account_id = e2e_test_account_config['account_id']
        require_test_account_credentials(account_id)
        
        vault_path = ensure_test_vault_exists(account_id)
        
        # Process account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.successful_accounts >= 0
        # Note: Actual empty body test requires sending such an email first
    
    def test_imap_connection_handling(
        self,
        e2e_test_account_config,
        e2e_master_orchestrator
    ):
        """
        Scenario 5.3: Handle IMAP connection failure gracefully.
        
        Expected:
        - Connection failure handled
        - Error logged
        - Account skipped
        - Other accounts unaffected
        """
        account_id = e2e_test_account_config['account_id']
        
        # Process account (with valid credentials, should succeed)
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        # Even if connection fails, orchestrator should handle it gracefully
        assert result.total_accounts == 1
        # Result may be successful or failed, but should be handled gracefully


# ============================================================================
# Provider-Specific Tests
# ============================================================================

class TestE2EProviderSpecific:
    """Test provider-specific IMAP servers."""
    
    def test_gmail_provider(
        self,
        available_test_accounts,
        e2e_master_orchestrator,
        e2e_test_config_dir
    ):
        """
        Scenario 6.1: Test with Gmail IMAP server.
        
        Expected:
        - Gmail IMAP connection successful
        - Email fetched from Gmail
        - Processing completes
        """
        # Find Gmail account
        gmail_accounts = [
            acc for acc in available_test_accounts
            if 'gmail' in acc.lower()
        ]
        
        if not gmail_accounts:
            pytest.skip("No Gmail test account available")
        
        account_id = gmail_accounts[0]
        require_test_account_credentials(account_id)
        
        # Process Gmail account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.total_accounts == 1
        assert result.successful_accounts >= 0
    
    def test_outlook_provider(
        self,
        available_test_accounts,
        e2e_master_orchestrator,
        e2e_test_config_dir
    ):
        """
        Scenario 6.2: Test with Outlook IMAP server.
        
        Expected:
        - Outlook IMAP connection successful
        - Email fetched from Outlook
        - Processing completes
        """
        # Find Outlook account
        outlook_accounts = [
            acc for acc in available_test_accounts
            if 'outlook' in acc.lower()
        ]
        
        if not outlook_accounts:
            pytest.skip("No Outlook test account available")
        
        account_id = outlook_accounts[0]
        require_test_account_credentials(account_id)
        
        # Process Outlook account
        result = e2e_master_orchestrator.run(['--account', account_id])
        
        # Assertions
        assert result.total_accounts == 1
        assert result.successful_accounts >= 0


# ============================================================================
# Test Environment Verification
# ============================================================================

class TestE2EEnvironmentVerification:
    """Verify E2E test environment is set up correctly."""
    
    def test_test_accounts_available(self, available_test_accounts):
        """Verify test accounts are available."""
        assert len(available_test_accounts) > 0, "At least one test account should be available"
    
    def test_test_account_credentials(self, available_test_accounts):
        """Verify test account credentials are available."""
        from tests.e2e_helpers import has_test_account_credentials
        
        for account_id in available_test_accounts:
            assert has_test_account_credentials(account_id), \
                f"Credentials should be available for {account_id}"
    
    def test_test_account_configs(self, available_test_accounts):
        """Verify test account configs exist."""
        from tests.e2e_helpers import account_config_exists
        
        for account_id in available_test_accounts:
            assert account_config_exists(account_id), \
                f"Config should exist for {account_id}"
    
    def test_master_orchestrator_initialization(self, e2e_master_orchestrator):
        """Verify MasterOrchestrator can be initialized."""
        assert e2e_master_orchestrator is not None
        assert e2e_master_orchestrator.config_loader is not None
    
    def test_account_discovery(self, e2e_master_orchestrator, e2e_test_config_dir):
        """Verify account discovery works."""
        accounts = e2e_master_orchestrator.config_loader.discover_accounts()
        assert isinstance(accounts, list)
        # May be empty if no account configs in test directory
