"""
V4 Analytics Writer Module

This module provides structured analytics logging for V4 email processing.
It writes per-email analytics data to JSONL files in a thread-safe manner.

Key Features:
    - Thread-safe JSONL writing
    - Per-email analytics entries
    - Configurable file path
    - Automatic directory creation

Usage:
    >>> from src.analytics_writer import AnalyticsWriter
    >>> 
    >>> writer = AnalyticsWriter('logs/analytics.jsonl')
    >>> writer.write_email_processing(
    ...     uid='12345',
    ...     status='success',
    ...     importance_score=9,
    ...     spam_score=2
    ... )
    True

See Also:
    - docs/v4-logging-design.md - Complete logging design documentation
    - Task 22.6 - Migrate Logging from v3_logger to V4 Logging System
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AnalyticsWriter:
    """
    Thread-safe writer for structured email analytics to JSONL files.
    
    Each line in the JSONL file is a complete JSON object representing
    one processed email with uid, timestamp, status, and scores.
    """
    
    def __init__(self, analytics_file: str):
        """
        Initialize analytics writer.
        
        Args:
            analytics_file: Path to analytics JSONL file
        """
        self._analytics_file = analytics_file
        self._analytics_path = Path(analytics_file)
        self._lock = threading.Lock()
        
        # Ensure parent directory exists
        self._analytics_path.parent.mkdir(parents=True, exist_ok=True)
    
    def write_email_processing(
        self,
        uid: str,
        status: str,
        importance_score: int = -1,
        spam_score: int = -1
    ) -> bool:
        """
        Write email processing event to analytics JSONL file.
        
        Args:
            uid: Email UID
            status: Processing status ('success' or 'error')
            importance_score: Importance score (0-10, or -1 for errors)
            spam_score: Spam score (0-10, or -1 for errors)
            
        Returns:
            True if write succeeded, False otherwise
        """
        try:
            entry = {
                'uid': uid,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': status,
                'importance_score': importance_score,
                'spam_score': spam_score
            }
            
            with self._lock:
                # Append to JSONL file (one JSON object per line)
                with open(self._analytics_path, 'a', encoding='utf-8') as f:
                    json_str = json.dumps(entry, ensure_ascii=False)
                    f.write(json_str + '\n')
                
                logger.debug(f"Wrote analytics entry for UID {uid}")
                return True
        except Exception as e:
            logger.error(
                f"Failed to write analytics entry for UID {uid}: {e}",
                exc_info=True
            )
            return False
