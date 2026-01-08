"""
V3 Logging Module

This module provides dual logging functionality for V3 email processing:
1. Unstructured operational logs → agent.log (via standard Python logging)
2. Structured analytics → analytics.jsonl (per-email records with uid, timestamp, status, scores)

Both logging systems must write for every processed email, regardless of success or failure.

All configuration access is through the settings.py facade, not direct YAML access.

Architecture:
    - EmailLogger: Main logging interface for email processing events
    - AnalyticsWriter: Handles structured JSONL analytics logging
    - LogQuery: Query functionality for structured analytics logs

Usage:
    >>> from src.v3_logger import EmailLogger
    >>> from src.settings import settings
    >>> 
    >>> logger = EmailLogger()
    >>> logger.log_email_processed(
    ...     uid='12345',
    ...     status='success',
    ...     importance_score=9,
    ...     spam_score=2
    ... )
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from src.settings import settings
from src.config import ConfigError

logger = logging.getLogger(__name__)


@dataclass
class EmailLogEntry:
    """
    Structured analytics log entry for a single processed email.
    
    This matches the PDD Section 7 requirement for structured analytics:
    uid, timestamp, status, scores
    
    Attributes:
        uid: Email UID from IMAP server
        timestamp: ISO 8601 timestamp of processing
        status: Processing status ('success' or 'error')
        importance_score: Importance score (0-10, or -1 for errors)
        spam_score: Spam score (0-10, or -1 for errors)
    """
    uid: str
    timestamp: str
    status: str
    importance_score: int
    spam_score: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailLogEntry':
        """Create from dictionary (for deserialization)."""
        return cls(**data)


class LogFileManager:
    """
    Manages log file operations including creation, rotation, and size limits.
    
    Handles both operational logs and analytics files with thread-safe operations.
    """
    
    def __init__(
        self,
        log_file: Optional[str] = None,
        analytics_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB default
        backup_count: int = 5
    ):
        """
        Initialize log file manager.
        
        Args:
            log_file: Path to operational log file (defaults to settings)
            analytics_file: Path to analytics JSONL file (defaults to settings)
            max_file_size: Maximum file size in bytes before rotation (default: 10MB)
            backup_count: Number of backup files to keep (default: 5)
        """
        self._log_file = log_file or settings.get_log_file()
        self._analytics_file = analytics_file or settings.get_analytics_file()
        self._max_file_size = max_file_size
        self._backup_count = backup_count
        self._lock = threading.Lock()
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure log file directories exist."""
        try:
            Path(self._log_file).parent.mkdir(parents=True, exist_ok=True)
            Path(self._analytics_file).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create log directories: {e}")
            raise
    
    def _rotate_file_if_needed(self, file_path: str) -> None:
        """
        Rotate log file if it exceeds maximum size.
        
        Args:
            file_path: Path to log file to check and rotate
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return
            
            if path.stat().st_size >= self._max_file_size:
                # Rotate existing backups
                for i in range(self._backup_count - 1, 0, -1):
                    old_backup = Path(f"{file_path}.{i}")
                    new_backup = Path(f"{file_path}.{i + 1}")
                    if old_backup.exists():
                        old_backup.rename(new_backup)
                
                # Move current file to backup.1
                backup_path = Path(f"{file_path}.1")
                path.rename(backup_path)
                
                logger.info(f"Rotated log file {file_path} (size exceeded {self._max_file_size} bytes)")
        except Exception as e:
            logger.warning(f"Failed to rotate log file {file_path}: {e}")
    
    def ensure_log_file(self) -> None:
        """Ensure operational log file exists and is ready for writing."""
        with self._lock:
            self._rotate_file_if_needed(self._log_file)
            Path(self._log_file).touch(exist_ok=True)
    
    def ensure_analytics_file(self) -> None:
        """Ensure analytics file exists and is ready for writing."""
        with self._lock:
            self._rotate_file_if_needed(self._analytics_file)
            Path(self._analytics_file).touch(exist_ok=True)
    
    def get_log_file(self) -> str:
        """Get operational log file path."""
        return self._log_file
    
    def get_analytics_file(self) -> str:
        """Get analytics file path."""
        return self._analytics_file


class AnalyticsWriter:
    """
    Handles writing structured analytics to JSONL file.
    
    Thread-safe implementation for concurrent logging operations.
    Each line in the JSONL file is a complete JSON object representing
    one processed email.
    """
    
    def __init__(
        self,
        analytics_file: Optional[str] = None,
        file_manager: Optional[LogFileManager] = None
    ):
        """
        Initialize analytics writer.
        
        Args:
            analytics_file: Path to analytics JSONL file (defaults to settings)
            file_manager: LogFileManager instance (optional, creates new if not provided)
        """
        self._file_manager = file_manager or LogFileManager()
        self._analytics_file = analytics_file or self._file_manager.get_analytics_file()
        self._analytics_path = Path(self._analytics_file)
        self._lock = threading.Lock()
        self._file_manager.ensure_analytics_file()
    
    def write_entry(self, entry: EmailLogEntry) -> bool:
        """
        Write a single analytics entry to JSONL file.
        
        Args:
            entry: EmailLogEntry to write
            
        Returns:
            True if write succeeded, False otherwise
        """
        try:
            with self._lock:
                # Append to JSONL file (one JSON object per line)
                with open(self._analytics_path, 'a', encoding='utf-8') as f:
                    json_str = json.dumps(entry.to_dict(), ensure_ascii=False)
                    f.write(json_str + '\n')
                
                logger.debug(f"Wrote analytics entry for UID {entry.uid}")
                return True
        except Exception as e:
            logger.error(f"Failed to write analytics entry for UID {entry.uid}: {e}", exc_info=True)
            return False
    
    def write_email_processing(
        self,
        uid: str,
        status: str,
        importance_score: int = -1,
        spam_score: int = -1
    ) -> bool:
        """
        Write email processing event to analytics.
        
        Convenience method that creates and writes an EmailLogEntry.
        
        Args:
            uid: Email UID
            status: Processing status ('success' or 'error')
            importance_score: Importance score (0-10, or -1 for errors)
            spam_score: Spam score (0-10, or -1 for errors)
            
        Returns:
            True if write succeeded, False otherwise
        """
        entry = EmailLogEntry(
            uid=uid,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status,
            importance_score=importance_score,
            spam_score=spam_score
        )
        return self.write_entry(entry)


class EmailLogger:
    """
    Main logging interface for email processing events.
    
    Provides methods to log email processing to both:
    1. Unstructured operational logs (via Python logging)
    2. Structured analytics (via AnalyticsWriter)
    
    Both systems write for every processed email as required by PDD Section 7.
    """
    
    def __init__(
        self,
        operational_logger: Optional[logging.Logger] = None,
        analytics_writer: Optional[AnalyticsWriter] = None
    ):
        """
        Initialize email logger.
        
        Args:
            operational_logger: Python logger for operational logs (defaults to module logger)
            analytics_writer: AnalyticsWriter instance (defaults to new instance)
        """
        self._op_logger = operational_logger or logger
        self._analytics = analytics_writer or AnalyticsWriter()
    
    def log_email_processed(
        self,
        uid: str,
        status: str = 'success',
        importance_score: int = -1,
        spam_score: int = -1,
        subject: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log email processing event to both logging systems.
        
        This is the main method for logging email processing. It writes to:
        1. Operational logs (unstructured)
        2. Analytics JSONL (structured)
        
        Args:
            uid: Email UID
            status: Processing status ('success' or 'error')
            importance_score: Importance score (0-10, or -1 for errors)
            spam_score: Spam score (0-10, or -1 for errors)
            subject: Email subject (optional, for operational logs)
            error_message: Error message if status is 'error' (optional)
        """
        # Write to structured analytics (required for every email)
        self._analytics.write_email_processing(
            uid=uid,
            status=status,
            importance_score=importance_score,
            spam_score=spam_score
        )
        
        # Write to unstructured operational logs
        subject_str = f" '{subject}'" if subject else ""
        if status == 'success':
            self._op_logger.info(
                f"Email processed: UID {uid}{subject_str} | "
                f"Importance: {importance_score}/10, Spam: {spam_score}/10"
            )
        else:
            error_str = f": {error_message}" if error_message else ""
            self._op_logger.error(
                f"Email processing failed: UID {uid}{subject_str}{error_str}"
            )
    
    def log_email_start(self, uid: str, subject: Optional[str] = None) -> None:
        """
        Log start of email processing.
        
        Args:
            uid: Email UID
            subject: Email subject (optional)
        """
        subject_str = f" '{subject}'" if subject else ""
        self._op_logger.debug(f"Starting email processing: UID {uid}{subject_str}")
    
    def log_classification_result(
        self,
        uid: str,
        importance_score: int,
        spam_score: int,
        is_important: bool = False,
        is_spam: bool = False
    ) -> None:
        """
        Log classification result.
        
        Args:
            uid: Email UID
            importance_score: Importance score (0-10)
            spam_score: Spam score (0-10)
            is_important: Whether email meets importance threshold
            is_spam: Whether email meets spam threshold
        """
        classification = []
        if is_important:
            classification.append("important")
        if is_spam:
            classification.append("spam")
        classification_str = f" [{', '.join(classification)}]" if classification else ""
        
        self._op_logger.info(
            f"Classification for UID {uid}: "
            f"Importance={importance_score}/10, Spam={spam_score}/10{classification_str}"
        )
    
    def log_email_reprocessed(
        self,
        uid: str,
        status: str = 'success',
        importance_score: int = -1,
        spam_score: int = -1,
        subject: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log email reprocessing event to both logging systems.
        
        This method is specifically for reprocessing events (when --force-reprocess is used).
        It logs to both operational logs and structured analytics with a clear indication
        that this is a reprocessing event.
        
        Args:
            uid: Email UID
            status: Processing status ('success' or 'error')
            importance_score: Importance score (0-10, or -1 for errors)
            spam_score: Spam score (0-10, or -1 for errors)
            subject: Email subject (optional, for operational logs)
            error_message: Error message if status is 'error' (optional)
        """
        # Write to structured analytics (required for every email)
        # Note: We still use the same analytics format, but the operational log
        # will clearly indicate this is a reprocessing event
        self._analytics.write_email_processing(
            uid=uid,
            status=status,
            importance_score=importance_score,
            spam_score=spam_score
        )
        
        # Write to unstructured operational logs with reprocessing indicator
        subject_str = f" '{subject}'" if subject else ""
        if status == 'success':
            self._op_logger.info(
                f"Email REPROCESSED: UID {uid}{subject_str} | "
                f"Importance: {importance_score}/10, Spam: {spam_score}/10"
            )
        else:
            error_str = f": {error_message}" if error_message else ""
            self._op_logger.error(
                f"Email reprocessing failed: UID {uid}{subject_str}{error_str}"
            )


class LogQuery:
    """
    Query functionality for structured analytics logs.
    
    Provides methods to search and filter analytics entries from JSONL file.
    """
    
    def __init__(self, analytics_file: Optional[str] = None):
        """
        Initialize log query.
        
        Args:
            analytics_file: Path to analytics JSONL file (defaults to settings)
        """
        self._analytics_file = analytics_file or settings.get_analytics_file()
        self._analytics_path = Path(self._analytics_file)
    
    def query_by_uid(self, uid: str) -> List[EmailLogEntry]:
        """
        Query analytics entries by email UID.
        
        Args:
            uid: Email UID to search for
            
        Returns:
            List of EmailLogEntry objects matching the UID
        """
        if not self._analytics_path.exists():
            return []
        
        results = []
        try:
            with open(self._analytics_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get('uid') == uid:
                            results.append(EmailLogEntry.from_dict(data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error querying analytics by UID {uid}: {e}")
        
        return results
    
    def query_by_status(self, status: str) -> List[EmailLogEntry]:
        """
        Query analytics entries by processing status.
        
        Args:
            status: Status to filter by ('success' or 'error')
            
        Returns:
            List of EmailLogEntry objects matching the status
        """
        if not self._analytics_path.exists():
            return []
        
        results = []
        try:
            with open(self._analytics_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get('status') == status:
                            results.append(EmailLogEntry.from_dict(data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error querying analytics by status {status}: {e}")
        
        return results
    
    def query_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[EmailLogEntry]:
        """
        Query analytics entries by date range.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            List of EmailLogEntry objects within the date range
        """
        if not self._analytics_path.exists():
            return []
        
        results = []
        try:
            with open(self._analytics_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        timestamp_str = data.get('timestamp', '')
                        if not timestamp_str:
                            continue
                        
                        # Parse ISO timestamp
                        entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        
                        # Check date range
                        if start_date and entry_time < start_date:
                            continue
                        if end_date and entry_time > end_date:
                            continue
                        
                        results.append(EmailLogEntry.from_dict(data))
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Error querying analytics by date range: {e}")
        
        return results
    
    def query_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[EmailLogEntry]:
        """
        Query all analytics entries with pagination support.
        
        Args:
            limit: Maximum number of entries to return (None for all)
            offset: Number of entries to skip (for pagination)
            
        Returns:
            List of EmailLogEntry objects
        """
        if not self._analytics_path.exists():
            return []
        
        results = []
        skipped = 0
        try:
            with open(self._analytics_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Skip entries for pagination
                    if skipped < offset:
                        skipped += 1
                        continue
                    
                    # Check limit
                    if limit and len(results) >= limit:
                        break
                    
                    try:
                        data = json.loads(line)
                        results.append(EmailLogEntry.from_dict(data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error querying all analytics: {e}")
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about analytics entries.
        
        Returns:
            Dictionary with statistics (total, success_count, error_count, etc.)
        """
        if not self._analytics_path.exists():
            return {
                'total': 0,
                'success_count': 0,
                'error_count': 0,
                'avg_importance_score': 0.0,
                'avg_spam_score': 0.0
            }
        
        total = 0
        success_count = 0
        error_count = 0
        importance_scores = []
        spam_scores = []
        
        try:
            with open(self._analytics_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        total += 1
                        
                        if data.get('status') == 'success':
                            success_count += 1
                        elif data.get('status') == 'error':
                            error_count += 1
                        
                        importance = data.get('importance_score', -1)
                        spam = data.get('spam_score', -1)
                        
                        if importance >= 0:
                            importance_scores.append(importance)
                        if spam >= 0:
                            spam_scores.append(spam)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
        
        return {
            'total': total,
            'success_count': success_count,
            'error_count': error_count,
            'avg_importance_score': sum(importance_scores) / len(importance_scores) if importance_scores else 0.0,
            'avg_spam_score': sum(spam_scores) / len(spam_scores) if spam_scores else 0.0
        }


# Convenience function for easy integration
def get_email_logger(
    operational_logger: Optional[logging.Logger] = None,
    analytics_file: Optional[str] = None
) -> EmailLogger:
    """
    Get an EmailLogger instance configured for email processing.
    
    This is a convenience function for easy integration into email processing
    workflows. It creates an EmailLogger with default configuration from settings.
    
    Args:
        operational_logger: Python logger for operational logs (defaults to module logger)
        analytics_file: Path to analytics JSONL file (defaults to settings)
        
    Returns:
        Configured EmailLogger instance
        
    Example:
        >>> from src.v3_logger import get_email_logger
        >>> email_logger = get_email_logger()
        >>> email_logger.log_email_processed(
        ...     uid='12345',
        ...     status='success',
        ...     importance_score=9,
        ...     spam_score=2
        ... )
    """
    analytics_writer = None
    if analytics_file:
        file_manager = LogFileManager(analytics_file=analytics_file)
        analytics_writer = AnalyticsWriter(analytics_file, file_manager=file_manager)
    
    return EmailLogger(operational_logger=operational_logger, analytics_writer=analytics_writer)
