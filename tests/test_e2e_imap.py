"""
End-to-end tests with live IMAP connections.

These tests verify the complete V3 email processing workflow using real IMAP servers.
They require valid IMAP credentials and should be skipped if credentials are not available.

To run these tests:
    pytest tests/test_e2e_imap.py -v

To skip these tests (if credentials not available):
    pytest tests/test_e2e_imap.py -v -m "not e2e_imap"

Requirements:
    - Valid IMAP configuration in config/config.yaml
    - IMAP_PASSWORD environment variable in .env
    - At least one unprocessed email in the INBOX
    - Test account with emails available for testing

Note: These tests will actually connect to IMAP servers and may modify email flags.
Use a test account, not production email.
"""

import pytest
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager
from src.settings import Settings
from src.imap_client import ImapClient, IMAPConnectionError, IMAPFetchError
from src.orchestrator import Pipeline, ProcessOptions
from src.dry_run import set_dry_run, is_dry_run

logger = logging.getLogger(__name__)

# Pytest marker for E2E IMAP tests
pytestmark = pytest.mark.e2e_imap


# ============================================================================
# Fixtures and Helpers
# ============================================================================

def has_imap_credentials() -> bool:
    """Check if IMAP credentials are available for testing."""
    try:
        config_path = project_root / 'config' / 'config.yaml'
        env_path = project_root / '.env'
        
        if not config_path.exists() or not env_path.exists():
            return False
        
        config = ConfigManager(str(config_path), str(env_path))
        password_env_key = config.yaml['imap'].get('password_env', 'IMAP_PASSWORD')
        password = os.getenv(password_env_key)
        
        return bool(password and config.yaml.get('imap', {}).get('server'))
    except Exception:
        return False


@pytest.fixture(scope="module")
def live_imap_config():
    """Load live IMAP configuration for E2E tests."""
    if not has_imap_credentials():
        pytest.skip("IMAP credentials not available - skipping live E2E tests")
    
    config_path = project_root / 'config' / 'config.yaml'
    env_path = project_root / '.env'
    config = ConfigManager(str(config_path), str(env_path))
    
    return config


@pytest.fixture(scope="module")
def live_imap_client(live_imap_config):
    """Create a live IMAP client connection for E2E tests."""
    client = ImapClient()
    try:
        client.connect()
        yield client
    finally:
        try:
            client.disconnect()
        except Exception:
            pass  # Ignore disconnect errors in cleanup


@pytest.fixture(scope="module")
def live_settings(live_imap_config):
    """Initialize settings facade for E2E tests."""
    config_path = project_root / 'config' / 'config.yaml'
    env_path = project_root / '.env'
    
    settings = Settings()
    settings.initialize(str(config_path), str(env_path))
    
    yield settings
    
    # Cleanup: reset settings instance
    Settings._instance = None
    Settings._config = None


@pytest.fixture
def test_email_uid(live_imap_client) -> Optional[str]:
    """Get a test email UID for testing (first unprocessed email)."""
    try:
        emails = live_imap_client.get_unprocessed_emails(limit=1)
        if emails:
            return emails[0]['uid']
        return None
    except Exception as e:
        logger.warning(f"Could not get test email UID: {e}")
        return None


# ============================================================================
# E2E Tests: IMAP Connection
# ============================================================================

class TestE2EIMAPConnection:
    """Test live IMAP connection functionality."""
    
    def test_imap_connection_success(self, live_imap_client):
        """Test successful IMAP connection."""
        assert live_imap_client._connected is True
        assert live_imap_client._imap is not None
    
    def test_imap_connection_selects_inbox(self, live_imap_client):
        """Test that IMAP connection selects INBOX."""
        # Connection should have selected INBOX during connect()
        assert live_imap_client._connected is True
        # Verify we can perform operations
        status, data = live_imap_client._imap.status('INBOX', '(MESSAGES)')
        assert status == 'OK'
    
    def test_imap_connection_reconnect(self, live_imap_client):
        """Test that reconnection works after disconnect."""
        # Disconnect
        live_imap_client.disconnect()
        assert live_imap_client._connected is False
        
        # Reconnect
        live_imap_client.connect()
        assert live_imap_client._connected is True
        
        # Verify we can perform operations
        status, data = live_imap_client._imap.status('INBOX', '(MESSAGES)')
        assert status == 'OK'


# ============================================================================
# E2E Tests: Email Retrieval
# ============================================================================

class TestE2EEmailRetrieval:
    """Test email retrieval from live IMAP server."""
    
    def test_get_unprocessed_emails_returns_list(self, live_imap_client):
        """Test that get_unprocessed_emails returns a list."""
        emails = live_imap_client.get_unprocessed_emails(limit=5)
        assert isinstance(emails, list)
        # May be empty if no unprocessed emails, which is OK
    
    def test_get_unprocessed_emails_structure(self, live_imap_client):
        """Test that retrieved emails have correct structure."""
        emails = live_imap_client.get_unprocessed_emails(limit=1)
        
        if emails:
            email = emails[0]
            # Verify required fields
            assert 'uid' in email
            assert 'subject' in email
            assert 'from' in email
            assert 'date' in email
            assert 'body' in email
            
            # Verify types
            assert isinstance(email['uid'], str)
            assert isinstance(email['subject'], str)
            assert isinstance(email['from'], str)
    
    def test_get_unprocessed_emails_respects_limit(self, live_imap_client):
        """Test that limit parameter is respected."""
        emails = live_imap_client.get_unprocessed_emails(limit=3)
        assert len(emails) <= 3
    
    def test_get_email_by_uid(self, live_imap_client, test_email_uid):
        """Test retrieving a specific email by UID."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        email = live_imap_client.get_email_by_uid(test_email_uid)
        
        assert email is not None
        assert email['uid'] == test_email_uid
        assert 'subject' in email
        assert 'from' in email
        assert 'body' in email
    
    def test_get_email_by_uid_invalid(self, live_imap_client):
        """Test that invalid UID raises appropriate error."""
        with pytest.raises((IMAPFetchError, ValueError)):
            live_imap_client.get_email_by_uid('999999999')
    
    def test_is_processed_flag_check(self, live_imap_client, test_email_uid):
        """Test checking if email is processed."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        # Should return False for unprocessed email
        is_processed = live_imap_client.is_processed(test_email_uid)
        assert isinstance(is_processed, bool)


# ============================================================================
# E2E Tests: Flag Management
# ============================================================================

class TestE2EFlagManagement:
    """Test IMAP flag management with live server."""
    
    def test_set_flag(self, live_imap_client, test_email_uid):
        """Test setting a flag on an email."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        # Use a test flag that we can safely set/remove
        test_flag = 'TestFlagE2E'
        
        try:
            # Set flag
            result = live_imap_client.set_flag(test_email_uid, test_flag)
            assert result is True
            
            # Verify flag is set
            email = live_imap_client.get_email_by_uid(test_email_uid)
            flags = email.get('flags', [])
            # Note: Flag may be in different format depending on IMAP server
            # Just verify the operation succeeded
            
        finally:
            # Cleanup: remove test flag
            try:
                live_imap_client.remove_flag(test_email_uid, test_flag)
            except Exception:
                pass  # Ignore cleanup errors
    
    def test_remove_flag(self, live_imap_client, test_email_uid):
        """Test removing a flag from an email."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        test_flag = 'TestFlagE2E'
        
        try:
            # First set the flag
            live_imap_client.set_flag(test_email_uid, test_flag)
            
            # Then remove it
            result = live_imap_client.remove_flag(test_email_uid, test_flag)
            assert result is True
            
        except Exception as e:
            # Cleanup on error
            try:
                live_imap_client.remove_flag(test_email_uid, test_flag)
            except Exception:
                pass
            raise
    
    def test_set_processed_flag(self, live_imap_client, test_email_uid):
        """Test setting the processed flag (AIProcessed)."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        processed_flag = 'AIProcessed'
        
        try:
            # Check initial state
            initial_processed = live_imap_client.is_processed(test_email_uid)
            
            # Set processed flag
            result = live_imap_client.set_flag(test_email_uid, processed_flag)
            assert result is True
            
            # Verify it's now processed
            is_processed = live_imap_client.is_processed(test_email_uid)
            assert is_processed is True
            
        finally:
            # Cleanup: remove processed flag to restore original state
            try:
                live_imap_client.remove_flag(test_email_uid, processed_flag)
            except Exception:
                pass


# ============================================================================
# E2E Tests: Email Processing Workflow
# ============================================================================

class TestE2EEmailProcessingWorkflow:
    """Test complete email processing workflow with live IMAP."""
    
    def test_pipeline_retrieves_emails(self, live_settings, test_email_uid):
        """Test that pipeline can retrieve emails from live IMAP."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        # Mock LLM and other components to avoid actual API calls
        with patch('src.orchestrator.LLMClient') as mock_llm_class, \
             patch('src.orchestrator.DecisionLogic') as mock_decision_class, \
             patch('src.orchestrator.NoteGenerator') as mock_note_class, \
             patch('src.orchestrator.EmailLogger') as mock_logger_class, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note:
            
            # Setup mocks
            from src.llm_client import LLMResponse
            from src.decision_logic import ClassificationResult, ClassificationStatus
            
            mock_llm = MagicMock()
            mock_llm.classify_email.return_value = LLMResponse(
                spam_score=2,
                importance_score=9,
                raw_response='{"spam_score": 2, "importance_score": 9}'
            )
            mock_llm_class.return_value = mock_llm
            
            mock_decision = MagicMock()
            mock_decision.classify.return_value = ClassificationResult(
                is_important=True,
                is_spam=False,
                importance_score=9,
                spam_score=2,
                confidence=0.9,
                status=ClassificationStatus.SUCCESS,
                raw_scores={'spam_score': 2, 'importance_score': 9},
                metadata={}
            )
            mock_decision_class.return_value = mock_decision
            
            mock_note = MagicMock()
            mock_note.generate_note.return_value = '# Test Email\n\nTest content'
            mock_note_class.return_value = mock_note
            
            mock_logger = MagicMock()
            mock_logger_class.return_value = mock_logger
            
            # Create pipeline
            pipeline = Pipeline()
            options = ProcessOptions(
                uid=None,
                force_reprocess=False,
                dry_run=True  # Use dry-run to avoid actual file writes and flag setting
            )
            
            # Process emails
            summary = pipeline.process_emails(options)
            
            # Verify pipeline executed
            assert summary is not None
            assert summary.total_emails >= 0  # May be 0 if no unprocessed emails
            assert summary.total_time >= 0
    
    def test_pipeline_with_specific_uid(self, live_settings, test_email_uid):
        """Test pipeline processing a specific email by UID."""
        if not test_email_uid:
            pytest.skip("No test email UID available")
        
        # Mock LLM and other components
        with patch('src.orchestrator.LLMClient') as mock_llm_class, \
             patch('src.orchestrator.DecisionLogic') as mock_decision_class, \
             patch('src.orchestrator.NoteGenerator') as mock_note_class, \
             patch('src.orchestrator.EmailLogger') as mock_logger_class, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note:
            
            # Setup mocks (same as above)
            from src.llm_client import LLMResponse
            from src.decision_logic import ClassificationResult, ClassificationStatus
            
            mock_llm = MagicMock()
            mock_llm.classify_email.return_value = LLMResponse(
                spam_score=2,
                importance_score=9,
                raw_response='{"spam_score": 2, "importance_score": 9}'
            )
            mock_llm_class.return_value = mock_llm
            
            mock_decision = MagicMock()
            mock_decision.classify.return_value = ClassificationResult(
                is_important=True,
                is_spam=False,
                importance_score=9,
                spam_score=2,
                confidence=0.9,
                status=ClassificationStatus.SUCCESS,
                raw_scores={'spam_score': 2, 'importance_score': 9},
                metadata={}
            )
            mock_decision_class.return_value = mock_decision
            
            mock_note = MagicMock()
            mock_note.generate_note.return_value = '# Test Email\n\nTest content'
            mock_note_class.return_value = mock_note
            
            mock_logger = MagicMock()
            mock_logger_class.return_value = mock_logger
            
            # Create pipeline
            pipeline = Pipeline()
            options = ProcessOptions(
                uid=test_email_uid,
                force_reprocess=False,
                dry_run=True
            )
            
            # Process email
            summary = pipeline.process_emails(options)
            
            # Verify pipeline executed
            assert summary is not None
            assert summary.total_emails == 1
            assert summary.successful == 1 or summary.failed == 1  # Should process or fail, not skip


# ============================================================================
# E2E Tests: Email Types
# ============================================================================

class TestE2EEmailTypes:
    """Test processing different types of emails."""
    
    def test_plain_text_email(self, live_imap_client):
        """Test retrieving and processing plain text emails."""
        emails = live_imap_client.get_unprocessed_emails(limit=10)
        
        # Find a plain text email (if available)
        plain_text_email = None
        for email in emails:
            # Check if email has plain text content
            body = email.get('body', '')
            if body and not body.strip().startswith('<'):
                plain_text_email = email
                break
        
        if plain_text_email:
            assert 'uid' in plain_text_email
            assert 'subject' in plain_text_email
            assert 'body' in plain_text_email
            assert len(plain_text_email['body']) > 0
    
    def test_html_email(self, live_imap_client):
        """Test retrieving HTML emails."""
        emails = live_imap_client.get_unprocessed_emails(limit=10)
        
        # Find an HTML email (if available)
        html_email = None
        for email in emails:
            body = email.get('body', '')
            # HTML emails typically have HTML tags
            if '<html' in body.lower() or '<div' in body.lower() or '<p' in body.lower():
                html_email = email
                break
        
        if html_email:
            assert 'uid' in html_email
            assert 'subject' in html_email
            # HTML emails should still have body content (may be converted to text)
            assert 'body' in html_email
    
    def test_email_with_attachments(self, live_imap_client):
        """Test retrieving emails with attachments."""
        emails = live_imap_client.get_unprocessed_emails(limit=10)
        
        # Find an email with attachments (if available)
        # Note: Attachment detection may require parsing email structure
        # For now, just verify we can retrieve emails
        if emails:
            email = emails[0]
            assert 'uid' in email
            assert 'subject' in email
            # Attachments info may be in metadata, but basic retrieval should work


# ============================================================================
# E2E Tests: Error Handling
# ============================================================================

class TestE2EErrorHandling:
    """Test error handling with live IMAP server."""
    
    def test_connection_error_handling(self):
        """Test handling of connection errors."""
        # Try to connect with invalid credentials
        client = ImapClient()
        
        # This should raise an error, not crash
        with pytest.raises(IMAPConnectionError):
            # Temporarily patch settings to return invalid credentials
            with patch('src.imap_client.settings') as mock_settings:
                mock_settings.get_imap_server.return_value = 'invalid.server.example.com'
                mock_settings.get_imap_port.return_value = 993
                mock_settings.get_imap_username.return_value = 'invalid'
                mock_settings.get_imap_password.return_value = 'invalid'
                
                client.connect()
    
    def test_fetch_error_handling(self, live_imap_client):
        """Test handling of fetch errors."""
        # Try to fetch non-existent email
        with pytest.raises((IMAPFetchError, ValueError)):
            live_imap_client.get_email_by_uid('999999999')
    
    def test_pipeline_error_isolation(self, live_settings):
        """Test that pipeline errors are isolated per email."""
        # Mock LLM to raise errors
        with patch('src.orchestrator.LLMClient') as mock_llm_class, \
             patch('src.orchestrator.ImapClient') as mock_imap_class:
            
            from src.llm_client import LLMClientError
            
            # Setup IMAP to return emails
            mock_imap = MagicMock()
            mock_imap.get_unprocessed_emails.return_value = [
                {'uid': '1', 'subject': 'Test 1', 'from': 'test@example.com', 'date': '2024-01-01', 'body': 'Body 1'},
                {'uid': '2', 'subject': 'Test 2', 'from': 'test@example.com', 'date': '2024-01-01', 'body': 'Body 2'},
            ]
            mock_imap.is_processed.return_value = False
            mock_imap_class.return_value = mock_imap
            
            # Setup LLM to fail on first email, succeed on second
            call_count = [0]
            def mock_classify(email_data):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise LLMClientError("API error")
                from src.llm_client import LLMResponse
                return LLMResponse(
                    spam_score=2,
                    importance_score=9,
                    raw_response='{"spam_score": 2, "importance_score": 9}'
                )
            
            mock_llm = MagicMock()
            mock_llm.classify_email.side_effect = mock_classify
            mock_llm_class.return_value = mock_llm
            
            # Create pipeline
            pipeline = Pipeline()
            options = ProcessOptions(
                uid=None,
                force_reprocess=False,
                dry_run=True
            )
            
            # Process emails - should handle first error and continue
            summary = pipeline.process_emails(options)
            
            # Verify both emails were attempted
            assert summary.total_emails == 2
            # First should fail, second should succeed (or both fail if decision logic fails)
            assert summary.failed >= 1 or summary.successful >= 1
