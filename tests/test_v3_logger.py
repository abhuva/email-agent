"""
Tests for V3 logging module.

These tests verify dual logging functionality:
1. Unstructured operational logs
2. Structured analytics (JSONL)
"""
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from src.v3_logger import (
    EmailLogger,
    AnalyticsWriter,
    LogQuery,
    EmailLogEntry
)
from src.config import ConfigError


@pytest.fixture
def temp_analytics_file(tmp_path):
    """Create a temporary analytics JSONL file for testing."""
    analytics_file = tmp_path / "analytics.jsonl"
    return str(analytics_file)


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file for testing."""
    log_file = tmp_path / "test.log"
    return str(log_file)


@pytest.fixture
def mock_settings():
    """Mock settings facade for testing."""
    with patch('src.v3_logger.settings') as mock:
        mock.get_analytics_file.return_value = 'logs/analytics.jsonl'
        mock.get_log_file.return_value = 'logs/agent.log'
        yield mock


class TestEmailLogEntry:
    """Tests for EmailLogEntry dataclass."""
    
    def test_create_entry(self):
        """Test creating an EmailLogEntry."""
        entry = EmailLogEntry(
            uid='12345',
            timestamp='2024-01-01T12:00:00Z',
            status='success',
            importance_score=9,
            spam_score=2
        )
        
        assert entry.uid == '12345'
        assert entry.timestamp == '2024-01-01T12:00:00Z'
        assert entry.status == 'success'
        assert entry.importance_score == 9
        assert entry.spam_score == 2
    
    def test_to_dict(self):
        """Test converting entry to dictionary."""
        entry = EmailLogEntry(
            uid='12345',
            timestamp='2024-01-01T12:00:00Z',
            status='success',
            importance_score=9,
            spam_score=2
        )
        
        data = entry.to_dict()
        assert data['uid'] == '12345'
        assert data['status'] == 'success'
        assert data['importance_score'] == 9
        assert data['spam_score'] == 2
    
    def test_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            'uid': '12345',
            'timestamp': '2024-01-01T12:00:00Z',
            'status': 'success',
            'importance_score': 9,
            'spam_score': 2
        }
        
        entry = EmailLogEntry.from_dict(data)
        assert entry.uid == '12345'
        assert entry.status == 'success'
        assert entry.importance_score == 9
        assert entry.spam_score == 2


class TestAnalyticsWriter:
    """Tests for AnalyticsWriter class."""
    
    def test_write_entry(self, temp_analytics_file):
        """Test writing an analytics entry."""
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        
        entry = EmailLogEntry(
            uid='12345',
            timestamp='2024-01-01T12:00:00Z',
            status='success',
            importance_score=9,
            spam_score=2
        )
        
        result = writer.write_entry(entry)
        assert result is True
        
        # Verify file was written
        assert Path(temp_analytics_file).exists()
        
        # Verify content
        with open(temp_analytics_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data['uid'] == '12345'
            assert data['status'] == 'success'
            assert data['importance_score'] == 9
            assert data['spam_score'] == 2
    
    def test_write_email_processing(self, temp_analytics_file):
        """Test writing email processing event."""
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        
        result = writer.write_email_processing(
            uid='12345',
            status='success',
            importance_score=9,
            spam_score=2
        )
        
        assert result is True
        
        # Verify entry was written
        with open(temp_analytics_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data['uid'] == '12345'
            assert data['status'] == 'success'
            assert 'timestamp' in data
    
    def test_write_error_status(self, temp_analytics_file):
        """Test writing error status entry."""
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        
        result = writer.write_email_processing(
            uid='12345',
            status='error',
            importance_score=-1,
            spam_score=-1
        )
        
        assert result is True
        
        # Verify entry
        with open(temp_analytics_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data['status'] == 'error'
            assert data['importance_score'] == -1
            assert data['spam_score'] == -1
    
    def test_multiple_entries(self, temp_analytics_file):
        """Test writing multiple entries (JSONL format)."""
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        
        # Write multiple entries
        writer.write_email_processing('12345', 'success', 9, 2)
        writer.write_email_processing('12346', 'success', 7, 1)
        writer.write_email_processing('12347', 'error', -1, -1)
        
        # Verify all entries
        with open(temp_analytics_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            # Check first entry
            data1 = json.loads(lines[0].strip())
            assert data1['uid'] == '12345'
            
            # Check second entry
            data2 = json.loads(lines[1].strip())
            assert data2['uid'] == '12346'
            
            # Check third entry
            data3 = json.loads(lines[2].strip())
            assert data3['uid'] == '12347'
            assert data3['status'] == 'error'


class TestEmailLogger:
    """Tests for EmailLogger class."""
    
    def test_log_email_processed_success(self, temp_analytics_file, caplog):
        """Test logging successful email processing."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Create analytics writer directly to avoid config loading
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        analytics_writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        email_logger = EmailLogger(analytics_writer=analytics_writer)
        
        email_logger.log_email_processed(
            uid='12345',
            status='success',
            importance_score=9,
            spam_score=2,
            subject='Test Email'
        )
        
        # Verify analytics entry
        assert Path(temp_analytics_file).exists()
        with open(temp_analytics_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data['uid'] == '12345'
            assert data['status'] == 'success'
        
        # Verify operational log
        assert 'Email processed: UID 12345' in caplog.text
        assert 'Importance: 9/10' in caplog.text
    
    def test_log_email_processed_error(self, temp_analytics_file, caplog):
        """Test logging failed email processing."""
        # Create analytics writer directly to avoid config loading
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        analytics_writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        email_logger = EmailLogger(analytics_writer=analytics_writer)
        
        email_logger.log_email_processed(
            uid='12345',
            status='error',
            importance_score=-1,
            spam_score=-1,
            subject='Test Email',
            error_message='Processing failed'
        )
        
        # Verify analytics entry
        with open(temp_analytics_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data['status'] == 'error'
            assert data['importance_score'] == -1
        
        # Verify operational log
        assert 'Email processing failed: UID 12345' in caplog.text
        assert 'Processing failed' in caplog.text
    
    def test_log_email_start(self, caplog):
        """Test logging email processing start."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        # Create logger without analytics to avoid config loading
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file='dummy.jsonl', log_file='dummy.log')
        analytics_writer = AnalyticsWriter('dummy.jsonl', file_manager=file_manager)
        email_logger = EmailLogger(analytics_writer=analytics_writer)
        email_logger.log_email_start('12345', 'Test Email')
        
        assert 'Starting email processing: UID 12345' in caplog.text
    
    def test_log_classification_result(self, caplog):
        """Test logging classification result."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Create logger without analytics to avoid config loading
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file='dummy.jsonl', log_file='dummy.log')
        analytics_writer = AnalyticsWriter('dummy.jsonl', file_manager=file_manager)
        email_logger = EmailLogger(analytics_writer=analytics_writer)
        email_logger.log_classification_result(
            uid='12345',
            importance_score=9,
            spam_score=2,
            is_important=True,
            is_spam=False
        )
        
        assert 'Classification for UID 12345' in caplog.text
        assert 'Importance=9/10' in caplog.text
        assert '[important]' in caplog.text


class TestLogQuery:
    """Tests for LogQuery class."""
    
    def test_query_by_uid(self, temp_analytics_file):
        """Test querying by email UID."""
        # Write test entries
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        writer.write_email_processing('12345', 'success', 9, 2)
        writer.write_email_processing('12346', 'success', 7, 1)
        writer.write_email_processing('12345', 'error', -1, -1)  # Same UID, different status
        
        # Query
        query = LogQuery(temp_analytics_file)
        results = query.query_by_uid('12345')
        
        assert len(results) == 2
        assert all(entry.uid == '12345' for entry in results)
        assert results[0].status == 'success'
        assert results[1].status == 'error'
    
    def test_query_by_status(self, temp_analytics_file):
        """Test querying by status."""
        # Write test entries
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        writer.write_email_processing('12345', 'success', 9, 2)
        writer.write_email_processing('12346', 'success', 7, 1)
        writer.write_email_processing('12347', 'error', -1, -1)
        
        # Query success
        query = LogQuery(temp_analytics_file)
        success_results = query.query_by_status('success')
        assert len(success_results) == 2
        
        # Query error
        error_results = query.query_by_status('error')
        assert len(error_results) == 1
        assert error_results[0].uid == '12347'
    
    def test_query_by_date_range(self, temp_analytics_file):
        """Test querying by date range."""
        # Write test entries
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        writer.write_email_processing('12345', 'success', 9, 2)
        writer.write_email_processing('12346', 'success', 7, 1)
        
        # Query with date range
        query = LogQuery(temp_analytics_file)
        start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999)
        
        results = query.query_by_date_range(start_date, end_date)
        assert len(results) >= 2
    
    def test_query_all(self, temp_analytics_file):
        """Test querying all entries."""
        # Write test entries
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        for i in range(10):
            writer.write_email_processing(f'1234{i}', 'success', 8, 2)
        
        # Query all
        query = LogQuery(temp_analytics_file)
        results = query.query_all()
        assert len(results) == 10
    
    def test_query_all_with_pagination(self, temp_analytics_file):
        """Test querying with pagination."""
        # Write test entries
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        for i in range(10):
            writer.write_email_processing(f'1234{i}', 'success', 8, 2)
        
        # Query with limit
        query = LogQuery(temp_analytics_file)
        results = query.query_all(limit=5)
        assert len(results) == 5
        
        # Query with offset
        results = query.query_all(limit=5, offset=5)
        assert len(results) == 5
    
    def test_get_statistics(self, temp_analytics_file):
        """Test getting statistics."""
        # Write test entries
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        writer.write_email_processing('12345', 'success', 9, 2)
        writer.write_email_processing('12346', 'success', 7, 1)
        writer.write_email_processing('12347', 'error', -1, -1)
        
        # Get statistics
        query = LogQuery(temp_analytics_file)
        stats = query.get_statistics()
        
        assert stats['total'] == 3
        assert stats['success_count'] == 2
        assert stats['error_count'] == 1
        assert stats['avg_importance_score'] == 8.0  # (9 + 7) / 2
        assert stats['avg_spam_score'] == 1.5  # (2 + 1) / 2
    
    def test_query_empty_file(self, tmp_path):
        """Test querying empty analytics file."""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()
        
        query = LogQuery(str(empty_file))
        results = query.query_by_uid('12345')
        assert len(results) == 0
        
        stats = query.get_statistics()
        assert stats['total'] == 0


class TestIntegration:
    """Integration tests for full logging workflow."""
    
    def test_full_logging_workflow(self, temp_analytics_file, caplog):
        """Test complete logging workflow."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        # Create analytics writer directly to avoid config loading
        from src.v3_logger import LogFileManager
        file_manager = LogFileManager(analytics_file=temp_analytics_file, log_file='dummy.log')
        analytics_writer = AnalyticsWriter(temp_analytics_file, file_manager=file_manager)
        email_logger = EmailLogger(analytics_writer=analytics_writer)
        
        # Log processing start
        email_logger.log_email_start('12345', 'Test Email')
        
        # Log classification
        email_logger.log_classification_result(
            uid='12345',
            importance_score=9,
            spam_score=2,
            is_important=True,
            is_spam=False
        )
        
        # Log processing completion
        email_logger.log_email_processed(
            uid='12345',
            status='success',
            importance_score=9,
            spam_score=2,
            subject='Test Email'
        )
        
        # Verify analytics entry
        query = LogQuery(temp_analytics_file)
        results = query.query_by_uid('12345')
        assert len(results) == 1
        assert results[0].status == 'success'
        assert results[0].importance_score == 9
        
        # Verify operational logs
        assert 'Starting email processing' in caplog.text
        assert 'Classification for UID 12345' in caplog.text
        assert 'Email processed: UID 12345' in caplog.text
