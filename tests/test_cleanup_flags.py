"""
Tests for V3 cleanup flags module.

These tests verify the CleanupFlags class functionality including flag scanning,
flag removal, dry-run mode, confirmation prompts, and error handling.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List

from src.cleanup_flags import (
    CleanupFlags,
    FlagScanResult,
    CleanupSummary,
    CleanupFlagsError
)
from src.imap_client import IMAPConnectionError, IMAPFetchError
from src.settings import Settings


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings facade for testing."""
    settings_mock = Mock(spec=Settings)
    settings_mock.get_imap_query.return_value = 'ALL'
    settings_mock.get_imap_application_flags.return_value = [
        'AIProcessed',
        'ObsidianNoteCreated',
        'NoteCreationFailed'
    ]
    settings_mock._initialized = True
    settings_mock._ensure_initialized = Mock()
    
    with patch('src.cleanup_flags.settings', settings_mock):
        yield settings_mock


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


class TestCleanupFlags:
    """Test CleanupFlags class."""
    
    def test_cleanup_flags_initialization(self, mock_settings):
        """Test CleanupFlags initialization."""
        with patch('src.cleanup_flags.ImapClient') as mock_imap:
            mock_imap.return_value = Mock()
            
            cleanup = CleanupFlags()
            assert cleanup.imap_client is not None
            assert len(cleanup.application_flags) > 0
    
    def test_cleanup_flags_loads_application_flags(self, mock_settings):
        """Test that application flags are loaded from settings."""
        with patch('src.cleanup_flags.ImapClient') as mock_imap:
            mock_imap.return_value = Mock()
            
            cleanup = CleanupFlags()
            assert 'AIProcessed' in cleanup.application_flags
            assert 'ObsidianNoteCreated' in cleanup.application_flags
    
    def test_cleanup_flags_fallback_to_default_flags(self, mock_settings):
        """Test fallback to default flags if settings fail."""
        mock_settings.get_imap_application_flags.side_effect = Exception("Settings error")
        
        with patch('src.cleanup_flags.ImapClient') as mock_imap:
            mock_imap.return_value = Mock()
            
            cleanup = CleanupFlags()
            # Should use default flags
            assert len(cleanup.application_flags) > 0
            assert 'AIProcessed' in cleanup.application_flags
    
    def test_connect(self, mock_settings, mock_imap_client):
        """Test connecting to IMAP server."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            cleanup = CleanupFlags()
            cleanup.connect()
            mock_imap_client.connect.assert_called_once()
    
    def test_connect_raises_on_error(self, mock_settings, mock_imap_client):
        """Test that connect raises CleanupFlagsError on IMAP connection failure."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            mock_imap_client.connect.side_effect = IMAPConnectionError("Connection failed")
            
            cleanup = CleanupFlags()
            with pytest.raises(CleanupFlagsError, match="IMAP connection failed"):
                cleanup.connect()
    
    def test_disconnect(self, mock_settings, mock_imap_client):
        """Test disconnecting from IMAP server."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            cleanup = CleanupFlags()
            cleanup.disconnect()
            mock_imap_client.disconnect.assert_called_once()
    
    def test_scan_flags_no_emails(self, mock_settings, mock_imap_client):
        """Test scanning flags when no emails are found."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            # Mock empty search result
            mock_imap_client._imap.uid.return_value = ('OK', [b''])
            mock_imap_client._connected = True
            
            cleanup = CleanupFlags()
            results = cleanup.scan_flags()
            
            assert len(results) == 0
    
    def test_scan_flags_with_application_flags(self, mock_settings, mock_imap_client):
        """Test scanning flags when emails have application flags."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
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
            
            cleanup = CleanupFlags()
            results = cleanup.scan_flags()
            
            # Should find one email with application flags
            assert len(results) == 1
            assert results[0].uid == '12345'
            assert 'AIProcessed' in results[0].application_flags
    
    def test_scan_flags_without_application_flags(self, mock_settings, mock_imap_client):
        """Test scanning flags when emails don't have application flags."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
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
            
            cleanup = CleanupFlags()
            results = cleanup.scan_flags()
            
            # Should not include emails without application flags
            assert len(results) == 0
    
    def test_scan_flags_imap_search_error(self, mock_settings, mock_imap_client):
        """Test scanning flags when IMAP search fails."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            mock_imap_client._imap.uid.return_value = ('NO', [b'Search failed'])
            mock_imap_client._connected = True
            
            cleanup = CleanupFlags()
            with pytest.raises(CleanupFlagsError, match="IMAP search failed"):
                cleanup.scan_flags()
    
    def test_remove_flags_empty_list(self, mock_settings, mock_imap_client):
        """Test removing flags with empty scan results."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            cleanup = CleanupFlags()
            summary = cleanup.remove_flags([], dry_run=False)
            
            assert summary.total_emails_scanned == 0
            assert summary.emails_with_flags == 0
            assert summary.total_flags_removed == 0
            assert summary.emails_modified == 0
            assert summary.errors == 0
    
    def test_remove_flags_dry_run(self, mock_settings, mock_imap_client):
        """Test removing flags in dry-run mode."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            scan_result = FlagScanResult(
                uid='12345',
                subject='Test Email',
                application_flags=['AIProcessed'],
                all_flags=['\\Seen', '\\Flagged', 'AIProcessed']
            )
            
            cleanup = CleanupFlags()
            summary = cleanup.remove_flags([scan_result], dry_run=True)
            
            # In dry-run, flags should not actually be removed
            mock_imap_client.clear_flag.assert_not_called()
            assert summary.total_emails_scanned == 1
            assert summary.total_flags_removed == 1  # Counted but not removed
    
    def test_remove_flags_actual_removal(self, mock_settings, mock_imap_client):
        """Test actually removing flags (not dry-run)."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            scan_result = FlagScanResult(
                uid='12345',
                subject='Test Email',
                application_flags=['AIProcessed', 'ObsidianNoteCreated'],
                all_flags=['\\Seen', '\\Flagged', 'AIProcessed', 'ObsidianNoteCreated']
            )
            
            cleanup = CleanupFlags()
            summary = cleanup.remove_flags([scan_result], dry_run=False)
            
            # Should call clear_flag for each application flag
            assert mock_imap_client.clear_flag.call_count == 2
            mock_imap_client.clear_flag.assert_any_call('12345', 'AIProcessed')
            mock_imap_client.clear_flag.assert_any_call('12345', 'ObsidianNoteCreated')
            
            assert summary.total_emails_scanned == 1
            assert summary.total_flags_removed == 2
            assert summary.emails_modified == 1
            assert summary.errors == 0
    
    def test_remove_flags_partial_failure(self, mock_settings, mock_imap_client):
        """Test removing flags when some operations fail."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
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
            
            cleanup = CleanupFlags()
            summary = cleanup.remove_flags([scan_result], dry_run=False)
            
            assert summary.total_emails_scanned == 1
            assert summary.total_flags_removed == 1  # Only one succeeded
            assert summary.errors == 1  # One error
    
    def test_remove_flags_exception_handling(self, mock_settings, mock_imap_client):
        """Test removing flags when an exception occurs."""
        with patch('src.cleanup_flags.ImapClient', return_value=mock_imap_client):
            scan_result = FlagScanResult(
                uid='12345',
                subject='Test Email',
                application_flags=['AIProcessed'],
                all_flags=['\\Seen', 'AIProcessed']
            )
            
            # Simulate exception during flag removal
            mock_imap_client.clear_flag.side_effect = Exception("Unexpected error")
            
            cleanup = CleanupFlags()
            summary = cleanup.remove_flags([scan_result], dry_run=False)
            
            assert summary.errors == 1
    
    def test_format_scan_results_empty(self, mock_settings):
        """Test formatting empty scan results."""
        with patch('src.cleanup_flags.ImapClient'):
            cleanup = CleanupFlags()
            formatted = cleanup.format_scan_results([])
            
            assert "No emails" in formatted
    
    def test_format_scan_results_with_data(self, mock_settings):
        """Test formatting scan results with data."""
        with patch('src.cleanup_flags.ImapClient'):
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
            
            cleanup = CleanupFlags()
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
