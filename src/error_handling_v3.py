"""
V3 Error Handling Module for LLM Failures

This module provides comprehensive error handling for LLM API failures as specified
in Task 10. It ensures the system continues processing other emails after an LLM failure
by generating error notes with default values and proper error tagging.

All configuration access is through the settings.py facade, not direct YAML access.

Architecture:
    - ErrorResponseGenerator: Creates standardized error responses with -1, -1 scores
    - ErrorNoteGenerator: Generates error notes with #process_error tag
    - ErrorIsolation: Ensures failures don't affect other email processing
    - ErrorMonitor: Tracks and monitors LLM failure patterns

Usage:
    >>> from src.error_handling_v3 import ErrorResponseGenerator, ErrorNoteGenerator
    >>> from src.llm_client import LLMAPIError
    >>> 
    >>> generator = ErrorResponseGenerator()
    >>> error_result = generator.create_error_response(
    ...     email_uid='12345',
    ...     error=LLMAPIError("API failed"),
    ...     model_used='claude-3-opus'
    ... )
    >>> 
    >>> note_gen = ErrorNoteGenerator()
    >>> error_note = note_gen.generate_error_note(
    ...     email_data={'uid': '12345', 'subject': 'Test'},
    ...     error_result=error_result,
    ...     error_message='LLM API failed after retries'
    ... )
"""
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from src.decision_logic import ClassificationResult, ClassificationStatus
from src.llm_client import LLMClientError, LLMAPIError, LLMResponseParseError
from src.settings import settings
from src.v3_logger import get_email_logger

logger = logging.getLogger(__name__)


class ErrorResponseGenerator:
    """
    Generates standardized error responses when LLM processing fails.
    
    Creates ClassificationResult objects with default error values:
    - spam_score: -1
    - importance_score: -1
    - status: "error"
    
    As specified in PDD Section 4 and Task 10 requirements.
    """
    
    def create_error_response(
        self,
        email_uid: str,
        error: Exception,
        model_used: Optional[str] = None,
        retry_attempts: Optional[int] = None
    ) -> ClassificationResult:
        """
        Create a standardized error response when LLM processing fails.
        
        This method creates a ClassificationResult with error values as specified
        in the PDD: spam_score=-1, importance_score=-1, status="error".
        
        Args:
            email_uid: Email UID for logging
            error: The exception that occurred
            model_used: LLM model that was attempted (optional)
            retry_attempts: Number of retry attempts made (optional)
            
        Returns:
            ClassificationResult with error values and status
        """
        # Determine error type
        error_type = type(error).__name__
        error_message = str(error)
        
        # Get model from settings if not provided
        if model_used is None:
            try:
                model_used = settings.get_openrouter_model()
            except Exception:
                model_used = "unknown"
        
        # Get retry attempts from settings if not provided
        if retry_attempts is None:
            try:
                retry_attempts = settings.get_openrouter_retry_attempts()
            except Exception:
                retry_attempts = 3
        
        # Create metadata with error information
        metadata = {
            "model_used": model_used,
            "error_type": error_type,
            "error_message": error_message,
            "retry_attempts": retry_attempts,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Create error response with default values (-1, -1) as specified in PDD
        error_result = ClassificationResult(
            is_important=False,
            is_spam=False,
            importance_score=-1,
            spam_score=-1,
            confidence=0.0,
            status=ClassificationStatus.ERROR,
            raw_scores={"spam_score": -1, "importance_score": -1},
            metadata=metadata
        )
        
        logger.warning(
            f"Created error response for UID {email_uid}: "
            f"{error_type} - {error_message}"
        )
        
        return error_result
    
    def create_error_response_from_llm_error(
        self,
        email_uid: str,
        llm_error: LLMClientError,
        model_used: Optional[str] = None
    ) -> ClassificationResult:
        """
        Create error response specifically from LLM client errors.
        
        Convenience method that extracts additional context from LLM errors.
        
        Args:
            email_uid: Email UID for logging
            llm_error: LLMClientError exception
            model_used: LLM model that was attempted (optional)
            
        Returns:
            ClassificationResult with error values and status
        """
        return self.create_error_response(
            email_uid=email_uid,
            error=llm_error,
            model_used=model_used
        )


class ErrorNoteGenerator:
    """
    Generates error notes with #process_error tag when LLM processing fails.
    
    Creates comprehensive error notes that include:
    - #process_error tag
    - Default error values (spam_score: -1, importance_score: -1)
    - Original email metadata
    - Error type, message, and timestamp
    - Processing status set to "error"
    
    As specified in Task 10 requirements.
    """
    
    def __init__(self):
        """Initialize error note generator."""
        self._error_response_gen = ErrorResponseGenerator()
    
    def generate_error_note(
        self,
        email_data: Dict[str, Any],
        error_result: ClassificationResult,
        error_message: Optional[str] = None,
        original_error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """
        Generate error note data structure for note generation.
        
        This method prepares the data structure that will be used by NoteGenerator
        to create the actual error note with #process_error tag.
        
        Args:
            email_data: Email data dictionary (uid, subject, from, to, date, body, etc.)
            error_result: ClassificationResult with error values
            error_message: Human-readable error message (optional)
            original_error: Original exception that occurred (optional)
            
        Returns:
            Dictionary with email data and error classification result,
            ready for NoteGenerator.generate_note()
        """
        # Ensure error_result has status="error"
        if error_result.status != ClassificationStatus.ERROR:
            logger.warning(
                f"Error result status is {error_result.status}, "
                f"expected ERROR. Forcing to ERROR."
            )
            error_result.status = ClassificationStatus.ERROR
        
        # Add #process_error tag to email data
        tags = email_data.get('tags', [])
        if isinstance(tags, list):
            if '#process_error' not in tags and 'process_error' not in tags:
                tags.append('#process_error')
        else:
            tags = ['#process_error']
        
        email_data['tags'] = tags
        
        # Add error information to metadata
        error_metadata = error_result.metadata.copy()
        if error_message:
            error_metadata['user_error_message'] = error_message
        if original_error:
            error_metadata['original_error_type'] = type(original_error).__name__
            error_metadata['original_error_message'] = str(original_error)
        
        error_result.metadata = error_metadata
        
        logger.info(
            f"Generated error note data for UID {email_data.get('uid', 'unknown')} "
            f"with #process_error tag"
        )
        
        return {
            'email_data': email_data,
            'classification_result': error_result
        }
    
    def generate_error_note_from_exception(
        self,
        email_data: Dict[str, Any],
        error: Exception,
        model_used: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate error note directly from an exception.
        
        Convenience method that creates both error response and error note
        from a single exception.
        
        Args:
            email_data: Email data dictionary
            error: Exception that occurred
            model_used: LLM model that was attempted (optional)
            error_message: Human-readable error message (optional)
            
        Returns:
            Dictionary with email data and error classification result
        """
        email_uid = str(email_data.get('uid', 'unknown'))
        
        # Create error response
        error_result = self._error_response_gen.create_error_response(
            email_uid=email_uid,
            error=error,
            model_used=model_used
        )
        
        # Generate error note
        return self.generate_error_note(
            email_data=email_data,
            error_result=error_result,
            error_message=error_message,
            original_error=error
        )


# Convenience functions for easy integration
def create_error_response(
    email_uid: str,
    error: Exception,
    model_used: Optional[str] = None
) -> ClassificationResult:
    """
    Create an error response for LLM failures.
    
    Convenience function for easy integration into email processing workflows.
    
    Args:
        email_uid: Email UID
        error: Exception that occurred
        model_used: LLM model that was attempted (optional)
        
    Returns:
        ClassificationResult with error values
    """
    generator = ErrorResponseGenerator()
    return generator.create_error_response(
        email_uid=email_uid,
        error=error,
        model_used=model_used
    )


def generate_error_note_data(
    email_data: Dict[str, Any],
    error: Exception,
    model_used: Optional[str] = None,
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate error note data from an exception.
    
    Convenience function for easy integration into email processing workflows.
    
    Args:
        email_data: Email data dictionary
        error: Exception that occurred
        model_used: LLM model that was attempted (optional)
        error_message: Human-readable error message (optional)
        
    Returns:
        Dictionary with email data and error classification result
    """
    generator = ErrorNoteGenerator()
    return generator.generate_error_note_from_exception(
        email_data=email_data,
        error=error,
        model_used=model_used,
        error_message=error_message
    )


@dataclass
class ErrorStatistics:
    """Statistics for LLM error monitoring."""
    total_errors: int = 0
    error_counts_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    retry_success_count: int = 0
    retry_failure_count: int = 0
    process_error_notes_count: int = 0
    last_error_time: Optional[datetime] = None
    last_error_type: Optional[str] = None
    last_error_message: Optional[str] = None


class ErrorMonitor:
    """
    Monitors and tracks LLM failure patterns.
    
    Tracks error rates, error types, retry success rates, and frequency
    of #process_error notes. Provides statistics for monitoring and alerting.
    
    As specified in Task 10, subtask 5.
    """
    
    def __init__(self, email_logger: Optional[Any] = None):
        """
        Initialize error monitor.
        
        Args:
            email_logger: EmailLogger instance (optional, creates new if not provided)
        """
        self._stats = ErrorStatistics()
        try:
            self._email_logger = email_logger or get_email_logger()
        except Exception:
            # If logger initialization fails (e.g., in tests), use None
            self._email_logger = email_logger
    
    def record_error(
        self,
        error: Exception,
        email_uid: str,
        retry_attempts: Optional[int] = None,
        retry_succeeded: bool = False
    ) -> None:
        """
        Record an LLM error for monitoring.
        
        Args:
            error: The exception that occurred
            email_uid: Email UID where error occurred
            retry_attempts: Number of retry attempts made (optional)
            retry_succeeded: Whether retry eventually succeeded (optional)
        """
        error_type = type(error).__name__
        
        self._stats.total_errors += 1
        self._stats.error_counts_by_type[error_type] += 1
        self._stats.last_error_time = datetime.now(timezone.utc)
        self._stats.last_error_type = error_type
        self._stats.last_error_message = str(error)
        
        if retry_attempts:
            if retry_succeeded:
                self._stats.retry_success_count += 1
            else:
                self._stats.retry_failure_count += 1
        
        logger.debug(
            f"Error recorded: {error_type} for UID {email_uid} "
            f"(Total errors: {self._stats.total_errors})"
        )
    
    def record_process_error_note(self, email_uid: str) -> None:
        """
        Record creation of a #process_error note.
        
        Args:
            email_uid: Email UID where error note was created
        """
        self._stats.process_error_notes_count += 1
        logger.debug(
            f"Process error note recorded for UID {email_uid} "
            f"(Total: {self._stats.process_error_notes_count})"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        total_retries = self._stats.retry_success_count + self._stats.retry_failure_count
        retry_success_rate = (
            self._stats.retry_success_count / total_retries
            if total_retries > 0
            else 0.0
        )
        
        return {
            'total_errors': self._stats.total_errors,
            'error_counts_by_type': dict(self._stats.error_counts_by_type),
            'retry_success_count': self._stats.retry_success_count,
            'retry_failure_count': self._stats.retry_failure_count,
            'retry_success_rate': retry_success_rate,
            'process_error_notes_count': self._stats.process_error_notes_count,
            'last_error_time': (
                self._stats.last_error_time.isoformat()
                if self._stats.last_error_time
                else None
            ),
            'last_error_type': self._stats.last_error_type,
            'last_error_message': self._stats.last_error_message
        }
    
    def reset_statistics(self) -> None:
        """Reset all error statistics."""
        self._stats = ErrorStatistics()
        logger.info("Error statistics reset")
    
    def check_error_rate_threshold(
        self,
        threshold: float,
        total_processed: int
    ) -> bool:
        """
        Check if error rate exceeds threshold.
        
        Args:
            threshold: Error rate threshold (0.0-1.0, e.g., 0.1 for 10%)
            total_processed: Total number of emails processed
            
        Returns:
            True if error rate exceeds threshold, False otherwise
        """
        if total_processed == 0:
            return False
        
        error_rate = self._stats.total_errors / total_processed
        exceeds_threshold = error_rate > threshold
        
        if exceeds_threshold:
            logger.warning(
                f"Error rate threshold exceeded: {error_rate:.2%} > {threshold:.2%} "
                f"({self._stats.total_errors} errors / {total_processed} processed)"
            )
        
        return exceeds_threshold


@contextmanager
def isolate_email_processing_error(
    email_uid: str,
    email_subject: Optional[str] = None,
    error_monitor: Optional[ErrorMonitor] = None,
    email_logger: Optional[Any] = None
):
    """
    Context manager for error isolation in email processing.
    
    Ensures that errors in processing one email don't affect processing
    of other emails. Catches all exceptions, logs them, and allows
    processing to continue.
    
    As specified in Task 10, subtask 4.
    
    Args:
        email_uid: Email UID being processed
        email_subject: Email subject (optional, for logging)
        error_monitor: ErrorMonitor instance (optional, for tracking)
        email_logger: EmailLogger instance (optional, creates new if not provided)
        
    Yields:
        None (context manager)
        
    Example:
        >>> with isolate_email_processing_error('12345', 'Test Email'):
        ...     # Process email - any exceptions will be caught and logged
        ...     result = process_email(email)
    """
    try:
        email_logger = email_logger or get_email_logger()
    except Exception:
        # If logger initialization fails (e.g., in tests), use None
        email_logger = None
    
    subject_str = f" '{email_subject}'" if email_subject else ""
    
    try:
        if email_logger:
            email_logger.log_email_start(uid=email_uid, subject=email_subject)
        yield
    except LLMClientError as e:
        # LLM-specific errors - log and track
        error_type = type(e).__name__
        error_message = str(e)
        
        logger.error(
            f"LLM error processing email UID {email_uid}{subject_str}: "
            f"{error_type} - {error_message}",
            exc_info=True
        )
        
        # Log to both logging systems if logger is available
        if email_logger:
            email_logger.log_email_processed(
                uid=email_uid,
                status='error',
                importance_score=-1,
                spam_score=-1,
                subject=email_subject,
                error_message=f"{error_type}: {error_message}"
            )
        
        # Track in error monitor if provided
        if error_monitor:
            error_monitor.record_error(e, email_uid)
        
        # Re-raise to allow caller to handle (e.g., generate error note)
        raise
    except Exception as e:
        # Other errors - log and track
        error_type = type(e).__name__
        error_message = str(e)
        
        logger.error(
            f"Unexpected error processing email UID {email_uid}{subject_str}: "
            f"{error_type} - {error_message}",
            exc_info=True
        )
        
        # Log to both logging systems
        email_logger.log_email_processed(
            uid=email_uid,
            status='error',
            importance_score=-1,
            spam_score=-1,
            subject=email_subject,
            error_message=f"{error_type}: {error_message}"
        )
        
        # Track in error monitor if provided
        if error_monitor:
            error_monitor.record_error(e, email_uid)
        
        # Re-raise to allow caller to handle
        raise
