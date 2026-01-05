"""
TDD tests for safe IMAP operation context manager with retry logic and error handling.
"""

import pytest
import time
import imaplib
from unittest.mock import Mock, patch
from src.imap_connection import (
    safe_imap_operation,
    IMAPConnectionError,
    IMAPFetchError,
    add_tags_to_email
)

class MockIMAPConnection:
    def __init__(self, simulate_failures=0, simulate_capability=True, simulate_select_fail=False):
        self.simulate_failures = simulate_failures
        self.simulate_capability = simulate_capability
        self.simulate_select_fail = simulate_select_fail
        self.attempts = 0
        self.selected_mailbox = None
        self.calls = []
        self.sock = Mock()
        self.sock.settimeout = Mock()
    
    def capability(self):
        # No longer needed - we don't check KEYWORDS capability
        # But keep for backward compatibility if other code uses it
        self.calls.append('CAPABILITY')
        return ('OK', [b'IMAP4rev1 AUTH=PLAIN'])
    
    def select(self, mailbox):
        self.calls.append(('SELECT', mailbox))
        if self.simulate_select_fail:
            return ('NO', [b'Select failed'])
        self.selected_mailbox = mailbox
        return ('OK', [b'1'])
    
    def uid(self, *args):
        self.calls.append(('UID', args))
        self.attempts += 1
        if self.attempts <= self.simulate_failures:
            raise Exception("TRYAGAIN")
        return ('OK', [b'success'])
    
    def login(self, user, password):
        self.calls.append(('LOGIN', user))
        return ('OK', [b'Login successful'])
    
    def logout(self):
        self.calls.append('LOGOUT')
        return ('OK', [b'Bye'])

@patch('src.imap_connection.imaplib.IMAP4_SSL')
def test_safe_imap_operation_ensures_mailbox_context(mock_imap_ssl):
    """Test that safe_imap_operation ensures SELECT is called before UID operations"""
    mock_imap = MockIMAPConnection()
    mock_imap_ssl.return_value = mock_imap
    
    with safe_imap_operation('host', 'user', 'pass', mailbox='INBOX'):
        # Mailbox should be selected
        assert mock_imap.selected_mailbox == 'INBOX'
        assert ('SELECT', 'INBOX') in mock_imap.calls

@patch('src.imap_connection.imaplib.IMAP4_SSL')
def test_safe_imap_operation_retries_on_transient_errors(mock_imap_ssl):
    """Test that safe_imap_operation retries connection on transient errors with exponential backoff"""
    attempts = []
    def make_mock(*args, **kwargs):
        mock = MockIMAPConnection()
        attempts.append(mock)
        # Simulate transient error during select (connection setup) for first attempt
        if len(attempts) == 1:
            original_select = mock.select
            def failing_select(mailbox):
                raise imaplib.IMAP4.error("TRYAGAIN")
            mock.select = failing_select
        return mock
    
    mock_imap_ssl.side_effect = make_mock
    
    # Mock time.sleep to avoid actual delays in tests
    with patch('src.imap_connection.time.sleep'):
        # Should succeed after retries
        with safe_imap_operation('host', 'user', 'pass', max_retries=3) as imap:
            # Connection should be established after retries
            assert imap is not None
    
    # Should have attempted multiple connections due to retries
    assert len(attempts) >= 2

@patch('src.imap_connection.imaplib.IMAP4_SSL')
def test_safe_imap_operation_handles_connection_failures(mock_imap_ssl):
    """Test that safe_imap_operation handles connection failures gracefully"""
    mock_imap_ssl.side_effect = Exception("Connection failed")
    
    with patch('src.imap_connection.time.sleep'):
        with pytest.raises(IMAPFetchError):
            with safe_imap_operation('host', 'user', 'pass', max_retries=2):
                pass

@patch('src.imap_connection.imaplib.IMAP4_SSL')
def test_safe_imap_operation_successful_operation(mock_imap_ssl):
    """Test successful safe_imap_operation with all validations passing"""
    mock_imap = MockIMAPConnection()
    mock_imap_ssl.return_value = mock_imap
    
    with safe_imap_operation('host', 'user', 'pass') as imap:
        assert imap == mock_imap
        assert mock_imap.selected_mailbox == 'INBOX'
        # Can perform operations
        result = add_tags_to_email(imap, '42', ['Test', 'AIProcessed'])
        assert result is True
