"""
V3 Backfill Module

This module provides functionality to process historical emails with the new classification system.
Supports date range filtering, folder selection, progress tracking, throttling, and comprehensive logging.

All configuration access is through the settings.py facade, not direct YAML access.

Usage:
    >>> from src.backfill import BackfillProcessor
    >>> from src.settings import settings
    >>> 
    >>> settings.initialize('config/config.yaml', '.env')
    >>> processor = BackfillProcessor()
    >>> 
    >>> # Backfill all emails
    >>> summary = processor.backfill_emails()
    >>> 
    >>> # Backfill with date range
    >>> from datetime import datetime, date
    >>> start_date = date(2024, 1, 1)
    >>> end_date = date(2024, 12, 31)
    >>> summary = processor.backfill_emails(start_date=start_date, end_date=end_date)
    >>> 
    >>> # Backfill specific folder
    >>> summary = processor.backfill_emails(folder='INBOX')
"""
import logging
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

from src.settings import settings
from src.imap_client import ImapClient, IMAPClientError, IMAPFetchError
from src.orchestrator import Pipeline, ProcessOptions, PipelineSummary
from src.config import ConfigError

logger = logging.getLogger(__name__)


@dataclass
class BackfillOptions:
    """
    Options for backfill operations.
    
    Attributes:
        start_date: Start date for date range filter (None = all time)
        end_date: End date for date range filter (None = all time)
        folder: IMAP folder to process (None = default folder from config)
        force_reprocess: If True, reprocess emails even if already processed
        dry_run: If True, don't write files or set flags (preview mode)
        max_emails: Maximum number of emails to process (None = all)
    """
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    folder: Optional[str] = None
    force_reprocess: bool = True  # Default True for backfill (process all)
    dry_run: bool = False
    max_emails: Optional[int] = None


@dataclass
class BackfillSummary:
    """
    Summary statistics for a backfill operation.
    
    Attributes:
        total_emails: Total emails found matching criteria
        processed: Number of emails successfully processed
        failed: Number of emails that failed processing
        skipped: Number of emails skipped (e.g., already processed if not force_reprocess)
        total_time: Total processing time (seconds)
        average_time: Average processing time per email (seconds)
        start_time: Backfill start timestamp
        end_time: Backfill end timestamp
    """
    total_emails: int
    processed: int
    failed: int
    skipped: int
    total_time: float
    average_time: float
    start_time: datetime
    end_time: datetime


class ProgressTracker:
    """
    Tracks and displays progress during backfill operations.
    
    Supports both determinate (when total count is known) and indeterminate
    (when total count is unknown) modes. Provides console output for progress
    updates and maintains statistics.
    
    Example:
        tracker = ProgressTracker(total=100)
        tracker.update(processed=10, failed=2)
        tracker.display()  # Shows: "Progress: 10/100 (10.0%) - Processed: 10, Failed: 2"
    """
    
    def __init__(self, total: Optional[int] = None):
        """
        Initialize progress tracker.
        
        Args:
            total: Total number of items to process (None = indeterminate mode)
        """
        self.total = total
        self.processed = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.time()
        self.last_update_time = time.time()
        self._update_interval = 1.0  # Update display every 1 second
        
    def update(self, processed: int = 0, failed: int = 0, skipped: int = 0) -> None:
        """
        Update progress counters.
        
        Args:
            processed: Number of items successfully processed (increment)
            failed: Number of items that failed (increment)
            skipped: Number of items skipped (increment)
        """
        self.processed += processed
        self.failed += failed
        self.skipped += skipped
        
        # Auto-display if enough time has passed
        current_time = time.time()
        if current_time - self.last_update_time >= self._update_interval:
            self.display()
            self.last_update_time = current_time
    
    def display(self) -> None:
        """
        Display current progress to console.
        
        Shows progress percentage, counts, and estimated time remaining
        (if in determinate mode).
        """
        current = self.processed + self.failed + self.skipped
        
        if self.total is not None:
            # Determinate mode
            percentage = (current / self.total * 100) if self.total > 0 else 0.0
            elapsed = time.time() - self.start_time
            
            # Estimate time remaining
            if current > 0:
                avg_time_per_item = elapsed / current
                remaining_items = self.total - current
                estimated_remaining = avg_time_per_item * remaining_items
                remaining_str = f", ETA: {estimated_remaining:.1f}s"
            else:
                remaining_str = ""
            
            logger.info(
                f"Progress: {current}/{self.total} ({percentage:.1f}%) - "
                f"Processed: {self.processed}, Failed: {self.failed}, Skipped: {self.skipped}{remaining_str}"
            )
        else:
            # Indeterminate mode
            elapsed = time.time() - self.start_time
            logger.info(
                f"Progress: {current} items - "
                f"Processed: {self.processed}, Failed: {self.failed}, Skipped: {self.skipped} "
                f"(Elapsed: {elapsed:.1f}s)"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current progress statistics.
        
        Returns:
            Dictionary with progress statistics
        """
        current = self.processed + self.failed + self.skipped
        elapsed = time.time() - self.start_time
        
        stats = {
            'current': current,
            'total': self.total,
            'processed': self.processed,
            'failed': self.failed,
            'skipped': self.skipped,
            'elapsed': elapsed,
            'percentage': (current / self.total * 100) if self.total and self.total > 0 else None
        }
        
        if self.total and current > 0:
            avg_time_per_item = elapsed / current
            remaining_items = self.total - current
            estimated_remaining = avg_time_per_item * remaining_items
            stats['estimated_remaining'] = estimated_remaining
        
        return stats


class Throttler:
    """
    Throttles API calls to prevent rate limiting.
    
    Uses a simple time-based throttling mechanism that limits calls
    to a configurable rate (e.g., X calls per minute). Supports
    retry logic with exponential backoff for handling rate limit errors.
    
    Example:
        throttler = Throttler(calls_per_minute=60)
        throttler.wait_if_needed()  # Waits if needed to maintain rate
    """
    
    def __init__(self, calls_per_minute: Optional[int] = None):
        """
        Initialize throttler.
        
        Args:
            calls_per_minute: Maximum number of calls per minute (None = no throttling)
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = (60.0 / calls_per_minute) if calls_per_minute else 0.0
        self.last_call_time = 0.0
        self.call_times = deque()  # Track recent call times for sliding window
        
        # Get retry configuration from settings
        try:
            self.retry_attempts = settings.get_openrouter_retry_attempts()
            self.retry_delay = settings.get_openrouter_retry_delay_seconds()
        except Exception:
            # Defaults if settings not available
            self.retry_attempts = 3
            self.retry_delay = 5
    
    def wait_if_needed(self) -> None:
        """
        Wait if necessary to maintain the rate limit.
        
        Calculates the time since the last call and waits if needed
        to ensure we don't exceed the calls_per_minute limit.
        """
        if not self.calls_per_minute or self.min_interval == 0:
            return  # No throttling
        
        current_time = time.time()
        
        # Remove call times older than 1 minute
        while self.call_times and current_time - self.call_times[0] > 60.0:
            self.call_times.popleft()
        
        # If we've made too many calls in the last minute, wait
        if len(self.call_times) >= self.calls_per_minute:
            # Wait until the oldest call is more than 1 minute old
            wait_time = 60.0 - (current_time - self.call_times[0]) + 0.1  # Add small buffer
            if wait_time > 0:
                logger.debug(f"Throttling: waiting {wait_time:.2f}s to maintain rate limit")
                time.sleep(wait_time)
                current_time = time.time()
        
        # Record this call
        self.call_times.append(current_time)
        self.last_call_time = current_time
    
    def wait_with_backoff(self, attempt: int, base_delay: Optional[float] = None) -> None:
        """
        Wait with exponential backoff for retry attempts.
        
        Args:
            attempt: Current retry attempt number (1-based)
            base_delay: Base delay in seconds (uses retry_delay from settings if None)
        """
        if base_delay is None:
            base_delay = self.retry_delay
        
        # Exponential backoff: delay = base_delay * (2 ^ (attempt - 1))
        delay = base_delay * (2 ** (attempt - 1))
        
        logger.debug(f"Exponential backoff: waiting {delay:.2f}s before retry attempt {attempt}")
        time.sleep(delay)


class BackfillProcessor:
    """
    Processor for backfilling historical emails.
    
    This class provides functionality to process all emails in a mailbox,
    regardless of their current flag status, with support for:
    - Date range filtering
    - Folder selection
    - Progress tracking
    - API throttling
    - Comprehensive logging
    
    Example:
        processor = BackfillProcessor()
        summary = processor.backfill_emails(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            folder='INBOX'
        )
    """
    
    def __init__(self, calls_per_minute: Optional[int] = None):
        """
        Initialize the backfill processor.
        
        All components are initialized here to ensure they're ready for use.
        Configuration is accessed through the settings facade.
        
        Args:
            calls_per_minute: Maximum API calls per minute for throttling (None = use settings or no limit)
        """
        # Ensure settings are initialized
        try:
            settings._ensure_initialized()
        except ConfigError as e:
            logger.error(f"Configuration error: {e}")
            raise
        
        # Initialize components
        self.imap_client = ImapClient()
        self.pipeline = Pipeline()
        
        # Initialize throttler (use provided value or default from settings)
        if calls_per_minute is None:
            # Try to get from settings, or use a reasonable default
            try:
                # Use retry delay as a proxy for rate limiting (60 / delay = calls per minute)
                retry_delay = settings.get_openrouter_retry_delay_seconds()
                calls_per_minute = max(1, int(60 / retry_delay)) if retry_delay > 0 else 60
            except Exception:
                calls_per_minute = 60  # Default: 60 calls per minute
        
        self.throttler = Throttler(calls_per_minute=calls_per_minute)
        
        logger.info(f"BackfillProcessor initialized successfully (throttling: {calls_per_minute} calls/min)")
    
    def backfill_emails(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        folder: Optional[str] = None,
        force_reprocess: bool = True,
        dry_run: bool = False,
        max_emails: Optional[int] = None
    ) -> BackfillSummary:
        """
        Process all emails matching the specified criteria.
        
        This is the main entry point for backfill operations. It:
        - Retrieves emails matching date range and folder criteria
        - Processes each email through the pipeline
        - Tracks progress and provides statistics
        - Handles errors gracefully (isolates per-email failures)
        
        Args:
            start_date: Start date for date range filter (None = all time)
            end_date: End date for date range filter (None = all time)
            folder: IMAP folder to process (None = default folder from config)
            force_reprocess: If True, reprocess emails even if already processed
            dry_run: If True, don't write files or set flags (preview mode)
            max_emails: Maximum number of emails to process (None = all)
            
        Returns:
            BackfillSummary with processing statistics
            
        Raises:
            IMAPClientError: If IMAP connection fails
            ConfigError: If configuration is invalid
            ValueError: If date range is invalid (start_date > end_date)
        """
        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise ValueError(f"Invalid date range: start_date ({start_date}) > end_date ({end_date})")
        
        # Create options object
        options = BackfillOptions(
            start_date=start_date,
            end_date=end_date,
            folder=folder,
            force_reprocess=force_reprocess,
            dry_run=dry_run,
            max_emails=max_emails
        )
        
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("BACKFILL OPERATION STARTED")
        logger.info("=" * 60)
        logger.info(f"Start date: {start_date or 'All time'}")
        logger.info(f"End date: {end_date or 'All time'}")
        logger.info(f"Folder: {folder or 'Default (from config)'}")
        logger.info(f"Force reprocess: {force_reprocess}")
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Max emails: {max_emails or 'Unlimited'}")
        logger.info("=" * 60)
        
        try:
            # Connect to IMAP (both backfill processor and pipeline need connection)
            self.imap_client.connect()
            logger.info("Connected to IMAP server (backfill processor)")
            
            # Also ensure pipeline's IMAP client is connected
            # Share the connection by using the same client instance
            self.pipeline.imap_client = self.imap_client
            if not self.pipeline.imap_client._connected:
                self.pipeline.imap_client.connect()
                logger.info("Connected to IMAP server (pipeline)")
            
            # Retrieve emails matching criteria
            emails = self._retrieve_backfill_emails(options)
            total_emails = len(emails)
            
            logger.info(f"Found {total_emails} email(s) matching backfill criteria")
            
            if not emails:
                logger.info("No emails to process")
                end_time = datetime.now()
                total_time = (end_time - start_time).total_seconds()
                return BackfillSummary(
                    total_emails=0,
                    processed=0,
                    failed=0,
                    skipped=0,
                    total_time=total_time,
                    average_time=0.0,
                    start_time=start_time,
                    end_time=end_time
                )
            
            # Initialize progress tracker
            progress_tracker = ProgressTracker(total=total_emails)
            
            # Process emails
            processed = 0
            failed = 0
            skipped = 0
            
            for idx, email_data in enumerate(emails, 1):
                uid = email_data.get('uid', 'unknown')
                logger.info(f"Processing email {idx}/{total_emails} (UID: {uid})")
                
                # Throttle API calls to prevent rate limiting
                self.throttler.wait_if_needed()
                
                # Create process options for pipeline
                process_options = ProcessOptions(
                    uid=uid,
                    force_reprocess=force_reprocess,
                    dry_run=dry_run
                )
                
                # Process single email through pipeline
                try:
                    # Use pipeline's single email processing
                    result = self.pipeline._process_single_email(email_data, process_options)
                    
                    if result.success:
                        processed += 1
                        progress_tracker.update(processed=1)
                        logger.info(f"✓ Successfully processed email {idx}/{total_emails} (UID: {uid})")
                    else:
                        failed += 1
                        progress_tracker.update(failed=1)
                        logger.warning(f"✗ Failed to process email {idx}/{total_emails} (UID: {uid}): {result.error}")
                        
                except Exception as e:
                    failed += 1
                    progress_tracker.update(failed=1)
                    logger.error(f"✗ Error processing email {idx}/{total_emails} (UID: {uid}): {e}", exc_info=True)
            
            # Final progress display
            progress_tracker.display()
            
            # Generate summary
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            average_time = total_time / total_emails if total_emails > 0 else 0.0
            
            summary = BackfillSummary(
                total_emails=total_emails,
                processed=processed,
                failed=failed,
                skipped=skipped,
                total_time=total_time,
                average_time=average_time,
                start_time=start_time,
                end_time=end_time
            )
            
            # Log summary
            logger.info("=" * 60)
            logger.info("BACKFILL OPERATION COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Total emails found: {summary.total_emails}")
            logger.info(f"  ✓ Successfully processed: {summary.processed}")
            logger.info(f"  ✗ Failed: {summary.failed}")
            logger.info(f"  ⊘ Skipped: {summary.skipped}")
            logger.info(f"Total time: {summary.total_time:.2f}s")
            logger.info(f"Average time per email: {summary.average_time:.2f}s")
            if summary.processed > 0:
                success_rate = (summary.processed / summary.total_emails) * 100
                logger.info(f"Success rate: {success_rate:.1f}%")
            logger.info(f"Start time: {summary.start_time}")
            logger.info(f"End time: {summary.end_time}")
            logger.info("=" * 60)
            
            return summary
            
        except IMAPClientError as e:
            logger.error(f"IMAP error during backfill: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during backfill: {e}", exc_info=True)
            raise
        finally:
            # Cleanup: Disconnect from IMAP
            try:
                if self.imap_client and hasattr(self.imap_client, '_connected') and self.imap_client._connected:
                    self.imap_client.disconnect()
                    logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error disconnecting from IMAP during cleanup: {e}")
    
    def _retrieve_backfill_emails(self, options: BackfillOptions) -> List[Dict[str, Any]]:
        """
        Retrieve emails matching backfill criteria.
        
        This method:
        - Builds IMAP search query with date range and folder filters
        - Retrieves all matching emails (ignoring processed status if force_reprocess)
        - Handles folder selection
        - Returns list of email data dictionaries
        
        Args:
            options: Backfill options with date range, folder, etc.
            
        Returns:
            List of email data dictionaries ready for processing
            
        Raises:
            IMAPFetchError: If IMAP search or fetch fails
            IMAPConnectionError: If not connected
        """
        self.imap_client._ensure_connected()
        
        try:
            # Select folder (default to INBOX if not specified)
            folder = options.folder or 'INBOX'
            logger.info(f"Selecting IMAP folder: {folder}")
            
            typ, data = self.imap_client._imap.select(folder)
            if typ != 'OK':
                raise IMAPFetchError(f"Failed to select folder '{folder}': {data}")
            
            # Build search query
            search_parts = []
            
            # Add date range filters if specified
            if options.start_date:
                # IMAP SENTSINCE expects format: DD-MMM-YYYY (e.g., "01-Jan-2024")
                start_date_str = options.start_date.strftime("%d-%b-%Y")
                search_parts.append(f'SENTSINCE {start_date_str}')
                logger.debug(f"Added date filter: SENTSINCE {start_date_str}")
            
            if options.end_date:
                # IMAP SENTBEFORE expects format: DD-MMM-YYYY
                # Note: SENTBEFORE is exclusive, so we add 1 day to include the end date
                end_date_inclusive = options.end_date + timedelta(days=1)
                end_date_str = end_date_inclusive.strftime("%d-%b-%Y")
                search_parts.append(f'SENTBEFORE {end_date_str}')
                logger.debug(f"Added date filter: SENTBEFORE {end_date_str}")
            
            # If no date filters, use ALL
            if not search_parts:
                search_parts.append('ALL')
            
            # Build final query
            search_query = ' '.join(search_parts)
            
            # In backfill mode, we typically want to process all emails regardless of processed status
            # But we can still respect force_reprocess for flexibility
            if not options.force_reprocess:
                # Exclude processed emails
                processed_tag = settings.get_imap_processed_tag()
                search_query = f'({search_query} NOT KEYWORD "{processed_tag}")'
                logger.debug(f"Excluding processed emails (tag: {processed_tag})")
            
            logger.info(f"Executing IMAP search query: {search_query}")
            
            # Search for UIDs
            typ, data = self.imap_client._imap.uid('SEARCH', None, search_query)
            
            if typ != 'OK':
                raise IMAPFetchError(f"IMAP search failed: {data}")
            
            if not data or not data[0]:
                logger.info("No emails found matching criteria")
                return []
            
            # Parse UIDs
            uid_bytes = data[0]
            if isinstance(uid_bytes, bytes):
                uid_str = uid_bytes.decode('utf-8')
            else:
                uid_str = str(uid_bytes)
            
            uids = [uid.strip() for uid in uid_str.split() if uid.strip()]
            
            if not uids:
                logger.info("No emails found")
                return []
            
            logger.info(f"Found {len(uids)} email(s) matching criteria")
            
            # Limit number of emails if specified
            if options.max_emails and len(uids) > options.max_emails:
                logger.info(f"Limiting to {options.max_emails} emails (found {len(uids)})")
                uids = uids[:options.max_emails]
            
            # Fetch emails
            emails = []
            for uid in uids:
                try:
                    email_data = self.imap_client.get_email_by_uid(uid)
                    emails.append(email_data)
                except IMAPFetchError as e:
                    logger.warning(f"Skipping email UID {uid} due to fetch error: {e}")
                    continue
            
            logger.info(f"Successfully retrieved {len(emails)} email(s)")
            return emails
            
        except IMAPFetchError:
            raise
        except Exception as e:
            error_msg = f"Error retrieving backfill emails: {e}"
            logger.error(error_msg)
            raise IMAPFetchError(error_msg) from e
