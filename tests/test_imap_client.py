"""
Tests for V4 IMAP client module.

These tests verify IMAP connection, email retrieval, and flag management.
Uses mocking to avoid requiring actual IMAP server access.
"""
import pytest
import imaplib
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

from src.imap_client import (
    ImapClient,
    IMAPConnectionError,
    IMAPFetchError,
    IMAPClientError
)
from src.account_processor import ConfigurableImapClient


@pytest.fixture
def mock_imap_config():
    """Mock IMAP configuration dictionary for testing."""
    return {
        'imap': {
            'server': 'test.imap.com',
            'port': 993,
            'username': 'test@example.com',
            'password': 'test_password',
            'query': 'UNSEEN',
            'processed_tag': 'AIProcessed'
        },
        'processing': {
            'max_emails_per_run': 15
        }
    }


@pytest.fixture
def mock_imap_connection():
    """Create a mock IMAP connection."""
    mock_imap = MagicMock(spec=imaplib.IMAP4_SSL)
    mock_imap.select.return_value = ('OK', [b'1'])
    return mock_imap


def test_imap_client_initialization():
    """Test that ImapClient initializes correctly."""
    client = ImapClient()
    assert client._imap is None
    assert client._connected is False


@patch('src.account_processor.imaplib.IMAP4_SSL')
def test_imap_client_connect_success(mock_imap_class, mock_imap_config, mock_imap_connection):
    """Test successful IMAP connection."""
    mock_imap_class.return_value = mock_imap_connection
    
    client = ConfigurableImapClient(mock_imap_config)
    client.connect()
    
    assert client._connected is True
    assert client._imap is not None
    mock_imap_class.assert_called_once_with('test.imap.com', 993)
    mock_imap_connection.login.assert_called_once_with('test@example.com', 'test_password')
    mock_imap_connection.select.assert_called_once_with('INBOX')


@patch('src.account_processor.imaplib.IMAP4_SSL')
def test_imap_client_connect_authentication_failure(mock_imap_class, mock_imap_config):
    """Test IMAP connection with authentication failure."""
    mock_imap = MagicMock()
    mock_imap.login.side_effect = imaplib.IMAP4.error('Authentication failed')
    mock_imap_class.return_value = mock_imap
    
    client = ConfigurableImapClient(mock_imap_config)
    with pytest.raises(IMAPConnectionError, match="IMAP authentication failed"):
        client.connect()
    
    assert client._connected is False


@patch('src.account_processor.imaplib.IMAP4')
def test_imap_client_connect_starttls(mock_imap_class, mock_imap_config):
    """Test IMAP connection with STARTTLS (port 143)."""
    mock_imap_config['imap']['port'] = 143
    
    mock_imap = MagicMock()
    mock_imap.select.return_value = ('OK', [b'1'])
    mock_imap_class.return_value = mock_imap
    
    client = ConfigurableImapClient(mock_imap_config)
    client.connect()
    
    assert client._connected is True
    mock_imap_class.assert_called_once_with('test.imap.com', 143)
    mock_imap.starttls.assert_called_once()


def test_imap_client_disconnect(mock_imap_connection):
    """Test IMAP disconnection."""
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    client.disconnect()
    
    assert client._connected is False
    assert client._imap is None
    mock_imap_connection.logout.assert_called_once()


def test_imap_client_context_manager(mock_imap_connection, mock_imap_config):
    """Test IMAP client as context manager."""
    with patch('src.account_processor.imaplib.IMAP4_SSL') as mock_imap_class:
        mock_imap_class.return_value = mock_imap_connection
        
        with ConfigurableImapClient(mock_imap_config) as client:
            assert client._connected is True
        
        # Should be disconnected after context exit
        assert client._connected is False


def test_imap_client_get_email_by_uid(mock_imap_connection):
    """Test retrieving email by UID."""
    # Mock email data
    email_body = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Mon, 1 Jan 2024 12:00:00 +0000

This is a test email body.
"""
    mock_imap_connection.uid.return_value = ('OK', [(None, email_body)])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    email = client.get_email_by_uid('12345')
    
    assert email['uid'] == '12345'
    assert 'Test Email' in email['subject']
    assert 'sender@example.com' in email['from']
    mock_imap_connection.uid.assert_called_with('FETCH', '12345', '(RFC822)')


def test_imap_client_get_email_by_uid_not_found(mock_imap_connection):
    """Test retrieving non-existent email by UID."""
    mock_imap_connection.uid.return_value = ('NO', [b'Email not found'])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    with pytest.raises(IMAPFetchError, match="Failed to fetch email UID"):
        client.get_email_by_uid('99999')


def test_imap_client_get_unprocessed_emails(mock_imap_connection):
    """Test retrieving unprocessed emails."""
    # Mock search results
    mock_imap_connection.uid.side_effect = [
        ('OK', [b'12345 67890']),  # Search result
        ('OK', [(None, b'From: test@example.com\nSubject: Test\n\nBody')]),  # Fetch UID 12345
        ('OK', [(None, b'From: test2@example.com\nSubject: Test2\n\nBody2')])  # Fetch UID 67890
    ]
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    emails = client.get_unprocessed_emails()
    
    assert len(emails) == 2
    assert emails[0]['uid'] == '12345'
    assert emails[1]['uid'] == '67890'
    
    # Verify search query excludes processed tag
    search_call = mock_imap_connection.uid.call_args_list[0]
    assert search_call[0][0] == 'SEARCH'
    assert 'NOT KEYWORD "AIProcessed"' in search_call[0][2]


@patch('src.dry_run.is_dry_run', return_value=False)
def test_imap_client_set_flag(mock_dry_run, mock_imap_connection):
    """Test setting IMAP flag."""
    mock_imap_connection.uid.return_value = ('OK', [b'1'])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    result = client.set_flag('12345', 'AIProcessed')
    
    assert result is True
    mock_imap_connection.uid.assert_called_with('STORE', '12345', '+FLAGS', '(AIProcessed)')


@patch('src.dry_run.is_dry_run', return_value=False)
def test_imap_client_clear_flag(mock_dry_run, mock_imap_connection):
    """Test clearing IMAP flag."""
    mock_imap_connection.uid.return_value = ('OK', [b'1'])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    result = client.clear_flag('12345', 'AIProcessed')
    
    assert result is True
    mock_imap_connection.uid.assert_called_with('STORE', '12345', '-FLAGS', '(AIProcessed)')


def test_imap_client_has_flag(mock_imap_connection):
    """Test checking if email has flag."""
    mock_imap_connection.uid.return_value = ('OK', [(b'12345 (FLAGS (\\Seen AIProcessed))',)])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    assert client.has_flag('12345', 'AIProcessed') is True
    assert client.has_flag('12345', 'NonExistentFlag') is False


def test_imap_client_is_processed(mock_imap_connection):
    """Test checking if email is processed."""
    mock_imap_connection.uid.return_value = ('OK', [(b'12345 (FLAGS (AIProcessed))',)])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    assert client.is_processed('12345') is True


@patch('src.dry_run.is_dry_run', return_value=False)
def test_imap_client_mark_as_processed(mock_dry_run, mock_imap_connection):
    """Test marking email as processed."""
    mock_imap_connection.uid.return_value = ('OK', [b'1'])
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    result = client.mark_as_processed('12345')
    
    assert result is True
    # Should set the processed tag from settings
    mock_imap_connection.uid.assert_called_with('STORE', '12345', '+FLAGS', '(AIProcessed)')


def test_imap_client_get_next_unprocessed_email(mock_imap_connection):
    """Test getting next unprocessed email."""
    mock_imap_connection.uid.side_effect = [
        ('OK', [b'12345']),  # Search result
        ('OK', [(None, b'From: test@example.com\nSubject: Test\n\nBody')])  # Fetch
    ]
    
    client = ImapClient()
    client._imap = mock_imap_connection
    client._connected = True
    
    email = client.get_next_unprocessed_email()
    
    assert email is not None
    assert email['uid'] == '12345'


@patch('src.dry_run.is_dry_run', return_value=False)
def test_imap_client_ensure_connected_raises_error(mock_dry_run):
    """Test that operations fail when not connected."""
    client = ImapClient()
    
    with pytest.raises(IMAPConnectionError, match="Not connected"):
        client.get_email_by_uid('12345')
    
    with pytest.raises(IMAPConnectionError, match="Not connected"):
        client.get_unprocessed_emails()
    
    with pytest.raises(IMAPConnectionError, match="Not connected"):
        client.set_flag('12345', 'AIProcessed')
