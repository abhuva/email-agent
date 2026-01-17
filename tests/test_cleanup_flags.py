"""
Tests for cleanup flags module.

These tests verify the CleanupFlags class functionality including flag scanning,
flag removal, dry-run mode, confirmation prompts, and error handling.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any

from src.cleanup_flags import (
    CleanupFlags,
    FlagScanResult,
    CleanupSummary,
    CleanupFlagsError
)
from src.imap_client import IMAPConnectionError, IMAPFetchError


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Mock account configuration for testing."""
    return {
        'imap': {
            'query': 'ALL',
            'application_flags': [
                'AIProcessed',
                'ObsidianNoteCreated',
                'NoteCreationFailed'
            ]
        }
    }


@pytest.fixture
def mock_imap_client():
    """Mock IMAP client."""
    client = Mock()
    client.connect = Mock()
    client.disconnect = Mock()
    client.get_email_by_uid = Mock()
    client.clear_flag = Mock(return_value=True)
    client._imap = Mock()
    client._imap.uid = Mock()
    client._connected = False
    return client


@pytest.fixture
def cleanup_flags_instance(mock_config, mock_imap_client):
    """Create a CleanupFlags instance with mocked dependencies."""
    return CleanupFlags(config=mock_config, imap_client=mock_imap_client)


class TestCleanupFlags:
    """Test CleanupFlags class."""
    
    def test_cleanup_flags_initialization(self, mock_config, mock_imap_client):
        """Test CleanupFlags initialization."""
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        assert cleanup.imap_client is not None
        assert len(cleanup.application_flags) > 0
    
    def test_cleanup_flags_loads_application_flags(self, mock_config, mock_imap_client):
        """Test that application flags are loaded from config."""
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        assert 'AIProcessed' in cleanup.application_flags
        assert 'ObsidianNoteCreated' in cleanup.application_flags
    
    def test_cleanup_flags_fallback_to_default_flags(self, mock_imap_client):
        """Test fallback to default flags if config is missing."""
        # Config without application_flags
        config_no_flags = {'imap': {'query': 'ALL'}}
        
        cleanup = CleanupFlags(config=config_no_flags, imap_client=mock_imap_client)
        # Should use default flags
        assert len(cleanup.application_flags) > 0
        assert 'AIProcessed' in cleanup.application_flags
    
    def test_connect(self, mock_config, mock_imap_client):
        """Test connecting to IMAP server."""
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        cleanup.connect()
        mock_imap_client.connect.assert_called_once()
    
    def test_connect_raises_on_error(self, mock_config, mock_imap_client):
        """Test that connect raises CleanupFlagsError on IMAP connection failure."""
        mock_imap_client.connect.side_effect = IMAPConnectionError("Connection failed")
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        with pytest.raises(CleanupFlagsError, match="IMAP connection failed"):
            cleanup.connect()
    
    def test_disconnect(self, mock_config, mock_imap_client):
        """Test disconnecting from IMAP server."""
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        cleanup.disconnect()
        mock_imap_client.disconnect.assert_called_once()
    
    def test_scan_flags_no_emails(self, mock_config, mock_imap_client):
        """Test scanning flags when no emails are found."""
        # Mock empty search result
        mock_imap_client._imap.uid.return_value = ('OK', [b''])
        mock_imap_client._connected = True
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        results = cleanup.scan_flags()
        
        assert len(results) == 0
    
    def test_scan_flags_with_application_flags(self, mock_config, mock_imap_client):
        """Test scanning flags when emails have application flags."""
        mock_imap_client._connected = True
        
        # Mock search result with one UID
        def uid_side_effect(command, *args):
            if command == 'SEARCH':
                return ('OK', [b'12345'])
            elif command == 'FETCH':
                # Return FETCH response with flags
                return ('OK', [(b'12345 (FLAGS (\\Seen \\Flagged AIProcessed) BODY[HEADER.FIELDS (SUBJECT)] {10}\r\nSubject: Test Email\r\n)')])
            return ('OK', [])
        
        mock_imap_client._imap.uid.side_effect = uid_side_effect
        
        # Mock get_email_by_uid for subject extraction (fallback)
        mock_imap_client.get_email_by_uid.return_value = {
            'uid': '12345',
            'subject': 'Test Email'
        }
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        results = cleanup.scan_flags()
        
        # Should find one email with application flags
        assert len(results) == 1
        assert results[0].uid == '12345'
        assert 'AIProcessed' in results[0].application_flags
    
    def test_scan_flags_without_application_flags(self, mock_config, mock_imap_client):
        """Test scanning flags when emails don't have application flags."""
        mock_imap_client._connected = True
        
        # Mock search and FETCH responses
        def uid_side_effect(command, *args):
            if command == 'SEARCH':
                return ('OK', [b'12345'])
            elif command == 'FETCH':
                # Return FETCH response without application flags
                return ('OK', [(b'12345 (FLAGS (\\Seen \\Flagged) BODY[HEADER.FIELDS (SUBJECT)] {10}\r\nSubject: Test\r\n)')])
            return ('OK', [])
        
        mock_imap_client._imap.uid.side_effect = uid_side_effect
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        results = cleanup.scan_flags()
        
        # Should not include emails without application flags
        assert len(results) == 0
    
    def test_scan_flags_imap_search_error(self, mock_config, mock_imap_client):
        """Test scanning flags when IMAP search fails."""
        mock_imap_client._imap.uid.return_value = ('NO', [b'Search failed'])
        mock_imap_client._connected = True
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        with pytest.raises(CleanupFlagsError, match="IMAP search failed"):
            cleanup.scan_flags()
    
    def test_remove_flags_empty_list(self, mock_config, mock_imap_client):
        """Test removing flags with empty scan results."""
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        summary = cleanup.remove_flags([], dry_run=False)
        
        assert summary.total_emails_scanned == 0
        assert summary.emails_with_flags == 0
        assert summary.total_flags_removed == 0
        assert summary.emails_modified == 0
        assert summary.errors == 0
    
    def test_remove_flags_dry_run(self, mock_config, mock_imap_client):
        """Test removing flags in dry-run mode."""
        scan_result = FlagScanResult(
            uid='12345',
            subject='Test Email',
            application_flags=['AIProcessed'],
            all_flags=['\\Seen', '\\Flagged', 'AIProcessed']
        )
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        summary = cleanup.remove_flags([scan_result], dry_run=True)
        
        # In dry-run, flags should not actually be removed
        mock_imap_client.clear_flag.assert_not_called()
        assert summary.total_emails_scanned == 1
        assert summary.total_flags_removed == 1  # Counted but not removed
    
    def test_remove_flags_actual_removal(self, mock_config, mock_imap_client):
        """Test actually removing flags (not dry-run)."""
        scan_result = FlagScanResult(
            uid='12345',
            subject='Test Email',
            application_flags=['AIProcessed', 'ObsidianNoteCreated'],
            all_flags=['\\Seen', '\\Flagged', 'AIProcessed', 'ObsidianNoteCreated']
        )
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        summary = cleanup.remove_flags([scan_result], dry_run=False)
        
        # Should call clear_flag for each application flag
        assert mock_imap_client.clear_flag.call_count == 2
        mock_imap_client.clear_flag.assert_any_call('12345', 'AIProcessed')
        mock_imap_client.clear_flag.assert_any_call('12345', 'ObsidianNoteCreated')
        
        assert summary.total_emails_scanned == 1
        assert summary.total_flags_removed == 2
        assert summary.emails_modified == 1
        assert summary.errors == 0
    
    def test_remove_flags_partial_failure(self, mock_config, mock_imap_client):
        """Test removing flags when some operations fail."""
        scan_result = FlagScanResult(
            uid='12345',
            subject='Test Email',
            application_flags=['AIProcessed', 'ObsidianNoteCreated'],
            all_flags=['\\Seen', 'AIProcessed', 'ObsidianNoteCreated']
        )
        
        # First flag removal succeeds, second fails
        def clear_flag_side_effect(uid, flag):
            if flag == 'AIProcessed':
                return True
            return False
        
        mock_imap_client.clear_flag.side_effect = clear_flag_side_effect
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        summary = cleanup.remove_flags([scan_result], dry_run=False)
        
        assert summary.total_emails_scanned == 1
        assert summary.total_flags_removed == 1  # Only one succeeded
        assert summary.errors == 1  # One error
    
    def test_remove_flags_exception_handling(self, mock_config, mock_imap_client):
        """Test removing flags when an exception occurs."""
        scan_result = FlagScanResult(
            uid='12345',
            subject='Test Email',
            application_flags=['AIProcessed'],
            all_flags=['\\Seen', 'AIProcessed']
        )
        
        # Simulate exception during flag removal
        mock_imap_client.clear_flag.side_effect = Exception("Unexpected error")
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        summary = cleanup.remove_flags([scan_result], dry_run=False)
        
        assert summary.errors == 1
    
    def test_format_scan_results_empty(self, mock_config, mock_imap_client):
        """Test formatting empty scan results."""
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        formatted = cleanup.format_scan_results([])
        
        assert "No emails" in formatted
    
    def test_format_scan_results_with_data(self, mock_config, mock_imap_client):
        """Test formatting scan results with data."""
        scan_results = [
            FlagScanResult(
                uid='12345',
                subject='Test Email 1',
                application_flags=['AIProcessed'],
                all_flags=['\\Seen', 'AIProcessed']
            ),
            FlagScanResult(
                uid='67890',
                subject='Test Email 2',
                application_flags=['ObsidianNoteCreated'],
                all_flags=['\\Seen', 'ObsidianNoteCreated']
            )
        ]
        
        cleanup = CleanupFlags(config=mock_config, imap_client=mock_imap_client)
        formatted = cleanup.format_scan_results(scan_results)
        
        assert "2 email(s)" in formatted
        assert "12345" in formatted
        assert "67890" in formatted
        assert "Test Email 1" in formatted
        assert "Test Email 2" in formatted


class TestFlagScanResult:
    """Test FlagScanResult dataclass."""
    
    def test_flag_scan_result_creation(self):
        """Test creating a FlagScanResult."""
        result = FlagScanResult(
            uid='12345',
            subject='Test Email',
            application_flags=['AIProcessed'],
            all_flags=['\\Seen', '\\Flagged', 'AIProcessed']
        )
        
        assert result.uid == '12345'
        assert result.subject == 'Test Email'
        assert result.application_flags == ['AIProcessed']
        assert len(result.all_flags) == 3


class TestCleanupSummary:
    """Test CleanupSummary dataclass."""
    
    def test_cleanup_summary_creation(self):
        """Test creating a CleanupSummary."""
        summary = CleanupSummary(
            total_emails_scanned=100,
            emails_with_flags=50,
            total_flags_removed=75,
            emails_modified=50,
            errors=2
        )
        
        assert summary.total_emails_scanned == 100
        assert summary.emails_with_flags == 50
        assert summary.total_flags_removed == 75
        assert summary.emails_modified == 50
        assert summary.errors == 2


class TestCleanupFlagsError:
    """Test CleanupFlagsError exception."""
    
    def test_cleanup_flags_error_creation(self):
        """Test creating a CleanupFlagsError."""
        error = CleanupFlagsError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
