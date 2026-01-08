"""
Tests for V3 error handling module.

These tests verify error handling functionality for LLM failures:
1. Error response generation with -1, -1 scores
2. Error note generation with #process_error tag
3. Error isolation and system continuity
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.error_handling_v3 import (
    ErrorResponseGenerator,
    ErrorNoteGenerator,
    ErrorMonitor,
    isolate_email_processing_error,
    create_error_response,
    generate_error_note_data
)
from src.decision_logic import ClassificationResult, ClassificationStatus
from src.llm_client import LLMAPIError, LLMResponseParseError


class TestErrorResponseGenerator:
    """Tests for ErrorResponseGenerator class."""
    
    def test_create_error_response_basic(self):
        """Test creating a basic error response."""
        generator = ErrorResponseGenerator()
        error = LLMAPIError("API connection failed")
        
        result = generator.create_error_response(
            email_uid='12345',
            error=error
        )
        
        assert result.importance_score == -1
        assert result.spam_score == -1
        assert result.status == ClassificationStatus.ERROR
        assert result.is_important is False
        assert result.is_spam is False
        assert result.confidence == 0.0
        assert result.raw_scores == {"spam_score": -1, "importance_score": -1}
    
    def test_create_error_response_with_model(self):
        """Test creating error response with model information."""
        generator = ErrorResponseGenerator()
        error = LLMAPIError("API connection failed")
        
        result = generator.create_error_response(
            email_uid='12345',
            error=error,
            model_used='claude-3-opus'
        )
        
        assert result.metadata['model_used'] == 'claude-3-opus'
        assert result.metadata['error_type'] == 'LLMAPIError'
        assert result.metadata['error_message'] == 'API connection failed'
        assert 'processed_at' in result.metadata
    
    def test_create_error_response_with_retry_attempts(self):
        """Test creating error response with retry attempt information."""
        generator = ErrorResponseGenerator()
        error = LLMAPIError("All retries failed")
        
        result = generator.create_error_response(
            email_uid='12345',
            error=error,
            retry_attempts=3
        )
        
        assert result.metadata['retry_attempts'] == 3
    
    def test_create_error_response_from_llm_error(self):
        """Test creating error response from LLM client error."""
        generator = ErrorResponseGenerator()
        error = LLMResponseParseError("Invalid JSON response")
        
        result = generator.create_error_response_from_llm_error(
            email_uid='12345',
            llm_error=error,
            model_used='claude-3-opus'
        )
        
        assert result.importance_score == -1
        assert result.spam_score == -1
        assert result.status == ClassificationStatus.ERROR
        assert result.metadata['error_type'] == 'LLMResponseParseError'
        assert result.metadata['model_used'] == 'claude-3-opus'


class TestErrorNoteGenerator:
    """Tests for ErrorNoteGenerator class."""
    
    def test_generate_error_note_basic(self):
        """Test generating a basic error note."""
        generator = ErrorNoteGenerator()
        email_data = {
            'uid': '12345',
            'subject': 'Test Email',
            'from': 'test@example.com',
            'to': ['recipient@example.com'],
            'date': '2024-01-01T12:00:00Z',
            'body': 'Test content'
        }
        
        error_result = ClassificationResult(
            is_important=False,
            is_spam=False,
            importance_score=-1,
            spam_score=-1,
            confidence=0.0,
            status=ClassificationStatus.ERROR,
            raw_scores={"spam_score": -1, "importance_score": -1},
            metadata={'model_used': 'claude-3-opus', 'error_type': 'LLMAPIError'}
        )
        
        note_data = generator.generate_error_note(
            email_data=email_data,
            error_result=error_result,
            error_message='LLM API failed'
        )
        
        assert 'email_data' in note_data
        assert 'classification_result' in note_data
        assert '#process_error' in note_data['email_data']['tags']
        assert note_data['classification_result'].status == ClassificationStatus.ERROR
    
    def test_generate_error_note_with_original_error(self):
        """Test generating error note with original error information."""
        generator = ErrorNoteGenerator()
        email_data = {
            'uid': '12345',
            'subject': 'Test Email',
            'from': 'test@example.com',
            'to': ['recipient@example.com'],
            'date': '2024-01-01T12:00:00Z',
            'body': 'Test content'
        }
        
        original_error = LLMAPIError("Connection timeout")
        error_result = ClassificationResult(
            is_important=False,
            is_spam=False,
            importance_score=-1,
            spam_score=-1,
            confidence=0.0,
            status=ClassificationStatus.ERROR,
            raw_scores={"spam_score": -1, "importance_score": -1},
            metadata={'model_used': 'claude-3-opus'}
        )
        
        note_data = generator.generate_error_note(
            email_data=email_data,
            error_result=error_result,
            error_message='LLM API failed',
            original_error=original_error
        )
        
        metadata = note_data['classification_result'].metadata
        assert metadata['original_error_type'] == 'LLMAPIError'
        assert metadata['original_error_message'] == 'Connection timeout'
        assert metadata['user_error_message'] == 'LLM API failed'
    
    def test_generate_error_note_from_exception(self):
        """Test generating error note directly from exception."""
        generator = ErrorNoteGenerator()
        email_data = {
            'uid': '12345',
            'subject': 'Test Email',
            'from': 'test@example.com',
            'to': ['recipient@example.com'],
            'date': '2024-01-01T12:00:00Z',
            'body': 'Test content'
        }
        
        error = LLMAPIError("API connection failed")
        
        note_data = generator.generate_error_note_from_exception(
            email_data=email_data,
            error=error,
            model_used='claude-3-opus',
            error_message='LLM processing failed'
        )
        
        assert 'email_data' in note_data
        assert 'classification_result' in note_data
        assert '#process_error' in note_data['email_data']['tags']
        assert note_data['classification_result'].importance_score == -1
        assert note_data['classification_result'].spam_score == -1
        assert note_data['classification_result'].status == ClassificationStatus.ERROR
        assert note_data['classification_result'].metadata['model_used'] == 'claude-3-opus'
        assert note_data['classification_result'].metadata['error_type'] == 'LLMAPIError'
    
    def test_generate_error_note_preserves_existing_tags(self):
        """Test that error note generation preserves existing tags."""
        generator = ErrorNoteGenerator()
        email_data = {
            'uid': '12345',
            'subject': 'Test Email',
            'tags': ['email', 'important']
        }
        
        error_result = ClassificationResult(
            is_important=False,
            is_spam=False,
            importance_score=-1,
            spam_score=-1,
            confidence=0.0,
            status=ClassificationStatus.ERROR,
            raw_scores={"spam_score": -1, "importance_score": -1},
            metadata={}
        )
        
        note_data = generator.generate_error_note(
            email_data=email_data,
            error_result=error_result
        )
        
        tags = note_data['email_data']['tags']
        assert 'email' in tags
        assert 'important' in tags
        assert '#process_error' in tags


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_error_response_function(self):
        """Test create_error_response convenience function."""
        error = LLMAPIError("Test error")
        
        result = create_error_response(
            email_uid='12345',
            error=error,
            model_used='claude-3-opus'
        )
        
        assert result.importance_score == -1
        assert result.spam_score == -1
        assert result.status == ClassificationStatus.ERROR
        assert result.metadata['model_used'] == 'claude-3-opus'
    
    def test_generate_error_note_data_function(self):
        """Test generate_error_note_data convenience function."""
        email_data = {
            'uid': '12345',
            'subject': 'Test Email',
            'from': 'test@example.com',
            'to': ['recipient@example.com'],
            'date': '2024-01-01T12:00:00Z',
            'body': 'Test content'
        }
        
        error = LLMAPIError("API failed")
        
        note_data = generate_error_note_data(
            email_data=email_data,
            error=error,
            model_used='claude-3-opus',
            error_message='Processing failed'
        )
        
        assert 'email_data' in note_data
        assert 'classification_result' in note_data
        assert '#process_error' in note_data['email_data']['tags']
        assert note_data['classification_result'].importance_score == -1
        assert note_data['classification_result'].spam_score == -1


class TestErrorTagGeneration:
    """Tests for #process_error tag generation in ClassificationResult."""
    
    def test_error_result_includes_process_error_tag(self):
        """Test that ClassificationResult with ERROR status includes #process_error tag."""
        error_result = ClassificationResult(
            is_important=False,
            is_spam=False,
            importance_score=-1,
            spam_score=-1,
            confidence=0.0,
            status=ClassificationStatus.ERROR,
            raw_scores={"spam_score": -1, "importance_score": -1},
            metadata={}
        )
        
        frontmatter = error_result.to_frontmatter_dict()
        tags = frontmatter['tags']
        
        assert 'email' in tags
        assert '#process_error' in tags
        assert frontmatter['processing_meta']['status'] == 'error'
    
    def test_success_result_does_not_include_process_error_tag(self):
        """Test that ClassificationResult with SUCCESS status does not include #process_error tag."""
        success_result = ClassificationResult(
            is_important=True,
            is_spam=False,
            importance_score=9,
            spam_score=2,
            confidence=0.9,
            status=ClassificationStatus.SUCCESS,
            raw_scores={"spam_score": 2, "importance_score": 9},
            metadata={}
        )
        
        frontmatter = success_result.to_frontmatter_dict()
        tags = frontmatter['tags']
        
        assert 'email' in tags
        assert 'important' in tags
        assert '#process_error' not in tags
        assert frontmatter['processing_meta']['status'] == 'success'


class TestErrorMonitor:
    """Tests for ErrorMonitor class."""
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_record_error_basic(self, mock_get_logger):
        """Test recording a basic error."""
        mock_get_logger.return_value = Mock()
        monitor = ErrorMonitor()
        error = LLMAPIError("API failed")
        
        monitor.record_error(error, email_uid='12345')
        
        stats = monitor.get_statistics()
        assert stats['total_errors'] == 1
        assert stats['error_counts_by_type']['LLMAPIError'] == 1
        assert stats['last_error_type'] == 'LLMAPIError'
        assert stats['last_error_message'] == 'API failed'
    
    def test_record_error_with_retry_info(self):
        """Test recording error with retry information."""
        monitor = ErrorMonitor()
        error = LLMAPIError("API failed")
        
        monitor.record_error(error, email_uid='12345', retry_attempts=3, retry_succeeded=False)
        
        stats = monitor.get_statistics()
        assert stats['retry_failure_count'] == 1
        assert stats['retry_success_count'] == 0
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_record_retry_success(self, mock_get_logger):
        """Test recording successful retry."""
        mock_get_logger.return_value = Mock()
        monitor = ErrorMonitor()
        error = LLMAPIError("API failed")
        
        monitor.record_error(error, email_uid='12345', retry_attempts=2, retry_succeeded=True)
        
        stats = monitor.get_statistics()
        assert stats['retry_success_count'] == 1
        assert stats['retry_failure_count'] == 0
        assert stats['retry_success_rate'] == 1.0
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_record_process_error_note(self, mock_get_logger):
        """Test recording process error note creation."""
        mock_get_logger.return_value = Mock()
        monitor = ErrorMonitor()
        
        monitor.record_process_error_note('12345')
        monitor.record_process_error_note('12346')
        
        stats = monitor.get_statistics()
        assert stats['process_error_notes_count'] == 2
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_multiple_error_types(self, mock_get_logger):
        """Test tracking multiple error types."""
        mock_get_logger.return_value = Mock()
        monitor = ErrorMonitor()
        
        monitor.record_error(LLMAPIError("API failed"), '12345')
        monitor.record_error(LLMAPIError("API failed"), '12346')
        monitor.record_error(LLMResponseParseError("Invalid JSON"), '12347')
        
        stats = monitor.get_statistics()
        assert stats['total_errors'] == 3
        assert stats['error_counts_by_type']['LLMAPIError'] == 2
        assert stats['error_counts_by_type']['LLMResponseParseError'] == 1
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_check_error_rate_threshold(self, mock_get_logger):
        """Test error rate threshold checking."""
        mock_get_logger.return_value = Mock()
        monitor = ErrorMonitor()
        
        # Record 3 errors out of 10 processed
        for i in range(3):
            monitor.record_error(LLMAPIError("API failed"), f'uid{i}')
        
        # Check 20% threshold (should exceed)
        assert monitor.check_error_rate_threshold(0.2, 10) is True
        
        # Check 50% threshold (should not exceed)
        assert monitor.check_error_rate_threshold(0.5, 10) is False
    
    def test_reset_statistics(self):
        """Test resetting statistics."""
        monitor = ErrorMonitor()
        
        monitor.record_error(LLMAPIError("API failed"), '12345')
        monitor.record_process_error_note('12345')
        
        monitor.reset_statistics()
        
        stats = monitor.get_statistics()
        assert stats['total_errors'] == 0
        assert stats['process_error_notes_count'] == 0


class TestErrorIsolation:
    """Tests for error isolation context manager."""
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_isolate_email_processing_error_success(self, mock_get_logger):
        """Test error isolation with successful processing."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        email_uid = '12345'
        email_subject = 'Test Email'
        
        with isolate_email_processing_error(email_uid, email_subject):
            # Successful processing - no exception
            result = "success"
        
        assert result == "success"
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_isolate_email_processing_error_llm_error(self, mock_get_logger):
        """Test error isolation with LLM error."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        email_uid = '12345'
        email_subject = 'Test Email'
        monitor = ErrorMonitor()
        
        with pytest.raises(LLMAPIError):
            with isolate_email_processing_error(email_uid, email_subject, monitor):
                raise LLMAPIError("API connection failed")
        
        stats = monitor.get_statistics()
        assert stats['total_errors'] == 1
        assert stats['error_counts_by_type']['LLMAPIError'] == 1
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_isolate_email_processing_error_general_exception(self, mock_get_logger):
        """Test error isolation with general exception."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        email_uid = '12345'
        email_subject = 'Test Email'
        monitor = ErrorMonitor()
        
        with pytest.raises(ValueError):
            with isolate_email_processing_error(email_uid, email_subject, monitor):
                raise ValueError("Invalid value")
        
        stats = monitor.get_statistics()
        assert stats['total_errors'] == 1
        assert stats['error_counts_by_type']['ValueError'] == 1
    
    @patch('src.error_handling_v3.get_email_logger')
    def test_isolate_email_processing_error_continues_after_error(self, mock_get_logger):
        """Test that processing continues after error in isolation context."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        email_uid = '12345'
        results = []
        
        # First email - error
        try:
            with isolate_email_processing_error(email_uid):
                raise LLMAPIError("API failed")
        except LLMAPIError:
            results.append("error")
        
        # Second email - success (should still work)
        email_uid2 = '12346'
        with isolate_email_processing_error(email_uid2):
            results.append("success")
        
        assert results == ["error", "success"]
