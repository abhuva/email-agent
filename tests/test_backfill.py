"""
Tests for V3 backfill module.

These tests verify the BackfillProcessor class, ProgressTracker, Throttler,
and all backfill functionality including date range filtering, folder selection,
and error handling.
"""
import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime, timedelta
from typing import Dict, Any, List

from src.backfill import (
    BackfillProcessor,
    BackfillOptions,
    BackfillSummary,
    ProgressTracker,
    Throttler
)
from src.imap_client import IMAPClientError, IMAPConnectionError, IMAPFetchError
from src.orchestrator import Pipeline, ProcessOptions, ProcessingResult
from src.config import ConfigError
from src.settings import Settings


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings facade for testing."""
    settings_mock = Mock(spec=Settings)
    settings_mock.get_imap_server.return_value = 'test.imap.com'
    settings_mock.get_imap_port.return_value = 993
    settings_mock.get_imap_username.return_value = 'test@example.com'
    settings_mock.get_imap_password.return_value = 'test_password'
    settings_mock.get_imap_query.return_value = 'ALL'
    settings_mock.get_imap_processed_tag.return_value = 'AIProcessed'
    settings_mock.get_openrouter_retry_attempts.return_value = 3
    settings_mock.get_openrouter_retry_delay_seconds.return_value = 5
    settings_mock._initialized = True
    settings_mock._ensure_initialized = Mock()
    
    with patch('src.backfill.settings', settings_mock):
        yield settings_mock


@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return {
        'uid': '12345',
        'subject': 'Test Email',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'date': '2024-01-01T12:00:00Z',
        'body': 'This is a test email body.',
        'content_type': 'text/plain'
    }


@pytest.fixture
def mock_imap_client():
    """Mock IMAP client."""
    client = Mock()
    client.connect = Mock()
    client.disconnect = Mock()
    client.get_email_by_uid = Mock()
    client._imap = Mock()
    client._imap.select.return_value = ('OK', [b'1'])
    client._imap.uid = Mock()
    client._connected = True
    client._ensure_connected = Mock()
    return client


@pytest.fixture
def mock_pipeline():
    """Mock pipeline for testing."""
    pipeline = Mock(spec=Pipeline)
    pipeline.imap_client = Mock()
    pipeline.imap_client._connected = False
    pipeline._process_single_email = Mock()
    return pipeline


class TestProgressTracker:
    """Test ProgressTracker class."""
    
    def test_progress_tracker_initialization_determinate(self):
        """Test ProgressTracker initialization with total count."""
        tracker = ProgressTracker(total=100)
        assert tracker.total == 100
        assert tracker.processed == 0
        assert tracker.failed == 0
        assert tracker.skipped == 0
    
    def test_progress_tracker_initialization_indeterminate(self):
        """Test ProgressTracker initialization without total count."""
        tracker = ProgressTracker(total=None)
        assert tracker.total is None
        assert tracker.processed == 0
        assert tracker.failed == 0
        assert tracker.skipped == 0
    
    def test_progress_tracker_update(self):
        """Test updating progress counters."""
        tracker = ProgressTracker(total=100)
        tracker.update(processed=5, failed=2, skipped=1)
        assert tracker.processed == 5
        assert tracker.failed == 2
        assert tracker.skipped == 1
    
    def test_progress_tracker_get_stats(self):
        """Test getting progress statistics."""
        tracker = ProgressTracker(total=100)
        tracker.update(processed=10, failed=2, skipped=1)
        stats = tracker.get_stats()
        assert stats['current'] == 13
        assert stats['total'] == 100
        assert stats['processed'] == 10
        assert stats['failed'] == 2
        assert stats['skipped'] == 1
        assert stats['percentage'] == 13.0


class TestThrottler:
    """Test Throttler class."""
    
    def test_throttler_initialization(self):
        """Test Throttler initialization."""
        throttler = Throttler(calls_per_minute=60)
        assert throttler.calls_per_minute == 60
        assert throttler.min_interval > 0
    
    def test_throttler_no_throttling(self):
        """Test Throttler with no throttling (None)."""
        throttler = Throttler(calls_per_minute=None)
        start_time = time.time()
        throttler.wait_if_needed()
        elapsed = time.time() - start_time
        # Should return immediately without waiting
        assert elapsed < 0.1
    
    def test_throttler_wait_with_backoff(self):
        """Test exponential backoff for retry attempts."""
        throttler = Throttler(calls_per_minute=60)
        start_time = time.time()
        throttler.wait_with_backoff(attempt=1, base_delay=0.1)
        elapsed = time.time() - start_time
        # Should wait approximately base_delay * (2^0) = 0.1 seconds
        assert 0.09 <= elapsed <= 0.15


class TestBackfillProcessor:
    """Test BackfillProcessor class."""
    
    def test_backfill_processor_initialization(self, mock_settings):
        """Test BackfillProcessor initialization."""
        with patch('src.backfill.ImapClient') as mock_imap, \
             patch('src.backfill.Pipeline') as mock_pipeline_class:
            
            mock_imap.return_value = Mock()
            mock_pipeline_class.return_value = Mock()
            
            processor = BackfillProcessor()
            assert processor.imap_client is not None
            assert processor.pipeline is not None
            assert processor.throttler is not None
    
    def test_backfill_processor_raises_on_config_error(self, mock_settings):
        """Test that BackfillProcessor raises ConfigError if settings not initialized."""
        mock_settings._ensure_initialized.side_effect = ConfigError("Not initialized")
        
        with patch('src.backfill.settings', mock_settings):
            with pytest.raises(ConfigError):
                BackfillProcessor()
    
    def test_backfill_emails_no_emails_found(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill when no emails are found."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline):
            
            # Mock empty email list
            mock_imap_client._imap.uid.return_value = ('OK', [b''])
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails()
            
            assert summary.total_emails == 0
            assert summary.processed == 0
            assert summary.failed == 0
            assert summary.skipped == 0
    
    def test_backfill_emails_with_date_range(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill with date range filtering."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")):
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Mock email retrieval
            sample_email = {
                'uid': '12345',
                'subject': 'Test Email',
                'from': 'sender@example.com',
                'to': ['recipient@example.com'],
                'date': '2024-06-15T12:00:00Z',
                'body': 'Test body',
                'content_type': 'text/plain'
            }
            
            # Mock IMAP search to return one UID
            mock_imap_client._imap.uid.return_value = ('OK', [b'12345'])
            mock_imap_client.get_email_by_uid.return_value = sample_email
            
            # Mock pipeline processing
            success_result = ProcessingResult(
                uid='12345',
                success=True,
                classification_result=None,
                note_content='# Test\n\nContent',
                file_path='/tmp/test_vault/test_note.md',
                processing_time=0.1
            )
            mock_pipeline._process_single_email.return_value = success_result
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            start_date = date(2024, 1, 1)
            end_date = date(2024, 12, 31)
            
            summary = processor.backfill_emails(start_date=start_date, end_date=end_date)
            
            assert summary.total_emails == 1
            assert summary.processed == 1
            # Verify IMAP search was called with date filters
            assert mock_imap_client._imap.uid.called
    
    def test_backfill_emails_invalid_date_range(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill with invalid date range (start > end)."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline):
            
            processor = BackfillProcessor()
            
            start_date = date(2024, 12, 31)
            end_date = date(2024, 1, 1)  # Invalid: start > end
            
            with pytest.raises(ValueError, match="Invalid date range"):
                processor.backfill_emails(start_date=start_date, end_date=end_date)
    
    def test_backfill_emails_with_folder(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill with specific folder selection."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")):
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Mock empty result
            mock_imap_client._imap.uid.return_value = ('OK', [b''])
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails(folder='INBOX')
            
            # Verify folder was selected
            mock_imap_client._imap.select.assert_called_with('INBOX')
    
    def test_backfill_emails_with_max_emails(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill with max_emails limit."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")):
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Mock multiple UIDs
            mock_imap_client._imap.uid.return_value = ('OK', [b'1 2 3 4 5'])
            
            sample_email = {
                'uid': '1',
                'subject': 'Test',
                'from': 'test@example.com',
                'to': ['recipient@example.com'],
                'date': '2024-01-01T12:00:00Z',
                'body': 'Test body',
                'content_type': 'text/plain'
            }
            mock_imap_client.get_email_by_uid.return_value = sample_email
            
            success_result = ProcessingResult(
                uid='1',
                success=True,
                classification_result=None,
                note_content='# Test\n\nContent',
                file_path='/tmp/test_vault/test_note.md',
                processing_time=0.1
            )
            mock_pipeline._process_single_email.return_value = success_result
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails(max_emails=2)
            
            # Should only process 2 emails even though 5 were found
            assert summary.total_emails == 2
            assert summary.processed == 2
    
    def test_backfill_emails_with_force_reprocess(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill with force_reprocess option."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")):
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Mock email retrieval
            mock_imap_client._imap.uid.return_value = ('OK', [b'12345'])
            sample_email = {
                'uid': '12345',
                'subject': 'Test',
                'from': 'test@example.com',
                'to': ['recipient@example.com'],
                'date': '2024-01-01T12:00:00Z',
                'body': 'Test body',
                'content_type': 'text/plain'
            }
            mock_imap_client.get_email_by_uid.return_value = sample_email
            
            success_result = ProcessingResult(
                uid='12345',
                success=True,
                classification_result=None,
                note_content='# Test\n\nContent',
                file_path='/tmp/test_vault/test_note.md',
                processing_time=0.1
            )
            mock_pipeline._process_single_email.return_value = success_result
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails(force_reprocess=True)
            
            # Verify force_reprocess was passed to pipeline
            call_args = mock_pipeline._process_single_email.call_args
            assert call_args is not None
            process_options = call_args[0][1]  # Second argument is ProcessOptions
            assert process_options.force_reprocess is True
    
    def test_backfill_emails_with_dry_run(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill with dry_run option."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")):
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Mock email retrieval
            mock_imap_client._imap.uid.return_value = ('OK', [b'12345'])
            sample_email = {
                'uid': '12345',
                'subject': 'Test',
                'from': 'test@example.com',
                'to': ['recipient@example.com'],
                'date': '2024-01-01T12:00:00Z',
                'body': 'Test body',
                'content_type': 'text/plain'
            }
            mock_imap_client.get_email_by_uid.return_value = sample_email
            
            success_result = ProcessingResult(
                uid='12345',
                success=True,
                classification_result=None,
                note_content='# Test\n\nContent',
                file_path='/tmp/test_vault/test_note.md',
                processing_time=0.1
            )
            mock_pipeline._process_single_email.return_value = success_result
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails(dry_run=True)
            
            # Verify dry_run was passed to pipeline
            call_args = mock_pipeline._process_single_email.call_args
            assert call_args is not None
            process_options = call_args[0][1]  # Second argument is ProcessOptions
            assert process_options.dry_run is True
    
    def test_backfill_emails_processing_failure(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill when email processing fails."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")):
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Mock email retrieval
            mock_imap_client._imap.uid.return_value = ('OK', [b'12345'])
            sample_email = {
                'uid': '12345',
                'subject': 'Test',
                'from': 'test@example.com',
                'to': ['recipient@example.com'],
                'date': '2024-01-01T12:00:00Z',
                'body': 'Test body',
                'content_type': 'text/plain'
            }
            mock_imap_client.get_email_by_uid.return_value = sample_email
            
            # Mock processing failure
            failure_result = ProcessingResult(
                uid='12345',
                success=False,
                error='Processing failed',
                classification_result=None,
                note_content=None,
                file_path=None,
                processing_time=0.1
            )
            mock_pipeline._process_single_email.return_value = failure_result
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails()
            
            assert summary.total_emails == 1
            assert summary.processed == 0
            assert summary.failed == 1
    
    def test_backfill_emails_imap_connection_error(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill when IMAP connection fails."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline):
            
            mock_imap_client.connect.side_effect = IMAPConnectionError("Connection failed")
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            with pytest.raises(IMAPConnectionError):
                processor.backfill_emails()
    
    def test_backfill_emails_imap_fetch_error(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test backfill when IMAP fetch fails."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline):
            
            # Mock IMAP search failure
            mock_imap_client._imap.uid.return_value = ('NO', [b'Search failed'])
            
            processor = BackfillProcessor()
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            with pytest.raises(IMAPFetchError):
                processor.backfill_emails()
    
    def test_backfill_emails_throttling(self, mock_settings, mock_imap_client, mock_pipeline):
        """Test that throttling is applied during backfill."""
        with patch('src.backfill.ImapClient', return_value=mock_imap_client), \
             patch('src.backfill.Pipeline', return_value=mock_pipeline), \
             patch('src.backfill.settings') as mock_settings_patch, \
             patch('src.obsidian_note_creation.write_obsidian_note') as mock_write_note, \
             patch('src.prompt_renderer.render_email_prompt', side_effect=ImportError("Not available")), \
             patch('src.backfill.Throttler') as mock_throttler_class:
            
            mock_settings_patch.get_imap_processed_tag.return_value = 'AIProcessed'
            mock_write_note.return_value = '/tmp/test_vault/test_note.md'
            
            # Create a mock throttler
            mock_throttler = Mock()
            mock_throttler.wait_if_needed = Mock()
            mock_throttler_class.return_value = mock_throttler
            
            # Mock email retrieval
            mock_imap_client._imap.uid.return_value = ('OK', [b'12345'])
            sample_email = {
                'uid': '12345',
                'subject': 'Test',
                'from': 'test@example.com',
                'to': ['recipient@example.com'],
                'date': '2024-01-01T12:00:00Z',
                'body': 'Test body',
                'content_type': 'text/plain'
            }
            mock_imap_client.get_email_by_uid.return_value = sample_email
            
            success_result = ProcessingResult(
                uid='12345',
                success=True,
                classification_result=None,
                note_content='# Test\n\nContent',
                file_path='/tmp/test_vault/test_note.md',
                processing_time=0.1
            )
            mock_pipeline._process_single_email.return_value = success_result
            
            processor = BackfillProcessor(calls_per_minute=60)
            processor.imap_client = mock_imap_client
            processor.pipeline = mock_pipeline
            
            summary = processor.backfill_emails()
            
            # Verify throttler was called
            assert mock_throttler.wait_if_needed.called


class TestBackfillOptions:
    """Test BackfillOptions dataclass."""
    
    def test_backfill_options_defaults(self):
        """Test BackfillOptions with default values."""
        options = BackfillOptions()
        assert options.start_date is None
        assert options.end_date is None
        assert options.folder is None
        assert options.force_reprocess is True  # Default True for backfill
        assert options.dry_run is False
        assert options.max_emails is None
    
    def test_backfill_options_custom_values(self):
        """Test BackfillOptions with custom values."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)
        options = BackfillOptions(
            start_date=start_date,
            end_date=end_date,
            folder='INBOX',
            force_reprocess=False,
            dry_run=True,
            max_emails=100
        )
        assert options.start_date == start_date
        assert options.end_date == end_date
        assert options.folder == 'INBOX'
        assert options.force_reprocess is False
        assert options.dry_run is True
        assert options.max_emails == 100


class TestBackfillSummary:
    """Test BackfillSummary dataclass."""
    
    def test_backfill_summary_creation(self):
        """Test creating a BackfillSummary."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=10)
        
        summary = BackfillSummary(
            total_emails=100,
            processed=95,
            failed=3,
            skipped=2,
            total_time=10.0,
            average_time=0.1,
            start_time=start_time,
            end_time=end_time
        )
        
        assert summary.total_emails == 100
        assert summary.processed == 95
        assert summary.failed == 3
        assert summary.skipped == 2
        assert summary.total_time == 10.0
        assert summary.average_time == 0.1
        assert summary.start_time == start_time
        assert summary.end_time == end_time
