"""
V3 Orchestrator Module

This module provides high-level business logic orchestration for the email processing pipeline.
It coordinates all components (IMAP, LLM, decision logic, note generation, logging) into a
cohesive end-to-end processing flow with comprehensive error handling, performance optimizations,
and detailed logging.

Architecture:
    - Pipeline class: Main orchestration class that coordinates all modules (V3)
    - MasterOrchestrator class: Multi-account orchestrator for V4 (manages multiple AccountProcessor instances)
    - ProcessOptions: Configuration for pipeline execution (UID, force_reprocess, dry_run)
    - ProcessingResult: Result of processing a single email
    - PipelineSummary: Summary statistics for a pipeline execution
    - Error handling: Isolated per-email error handling to prevent crashes
    - Performance: Local operations < 1s, no memory leaks during batch processing

Pipeline Flow:
    1. Email Retrieval - Fetches emails from IMAP (by UID or all unprocessed)
    2. LLM Classification - Sends emails to LLM for spam/importance scoring
    3. Decision Logic - Applies thresholds to determine email categorization
    4. Note Generation - Generates Markdown notes using Jinja2 templates
    5. File Writing - Writes notes to Obsidian vault with proper error handling
    6. IMAP Flag Setting - Marks emails as processed (with error resilience)
    7. Logging - Records processing results to both logging systems
    8. Summary Generation - Provides comprehensive statistics and performance metrics

Key Features:
    - Per-email error isolation (failures don't affect other emails)
    - Comprehensive error handling with graceful degradation
    - Memory leak prevention (explicit cleanup, resource management)
    - Performance monitoring (tracks and reports processing times)
    - Detailed summary logging with statistics
    - Dry-run mode support throughout
    - Force reprocess capability

All configuration access is through the settings.py facade, not direct YAML access.

Usage:
    >>> from src.orchestrator import Pipeline, ProcessOptions
    >>> from src.settings import settings
    >>> 
    >>> # Initialize settings
    >>> settings.initialize('config/config.yaml', '.env')
    >>> 
    >>> # Create pipeline
    >>> pipeline = Pipeline()
    >>> 
    >>> # Process emails
    >>> options = ProcessOptions(
    ...     uid=None,  # Process all unprocessed emails
    ...     force_reprocess=False,
    ...     dry_run=False
    ... )
    >>> summary = pipeline.process_emails(options)
    >>> print(f"Processed {summary.successful} emails successfully")
    >>> print(f"Failed: {summary.failed}")
    >>> print(f"Total time: {summary.total_time:.2f}s")

See Also:
    - docs/v3-orchestrator.md - Complete documentation
    - docs/v4-orchestrator.md - V4 MasterOrchestrator documentation
    - src/cli_v3.py - CLI integration
"""
import logging
import time
import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Try to import rich for progress bars (optional dependency)
try:
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, SpinnerColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.settings import settings
from src.imap_client import ImapClient, IMAPClientError, IMAPConnectionError, IMAPFetchError
from src.llm_client import LLMClient, LLMResponse, LLMClientError
from src.decision_logic import DecisionLogic, ClassificationResult
from src.note_generator import NoteGenerator, TemplateRenderError
from src.v3_logger import EmailLogger
from src.dry_run import is_dry_run
from src.config import ConfigError
from src.summarization import check_summarization_required
from src.email_summarization import generate_email_summary
from src.openrouter_client import OpenRouterClient
from src.logging_context import set_account_context, set_correlation_id, clear_context, with_account_context
from src.logging_helpers import log_account_start, log_account_end, log_config_overrides, log_error_with_context

logger = logging.getLogger(__name__)


@dataclass
class ProcessOptions:
    """
    Options for email processing pipeline execution.
    
    Attributes:
        uid: Optional email UID to process (None = process all unprocessed)
        force_reprocess: If True, reprocess emails even if already marked as processed
        dry_run: If True, don't write files or set flags (preview mode)
        max_emails: Optional maximum number of emails to process (overrides config)
        debug_prompt: If True, write classification prompts to debug files
    """
    uid: Optional[str]
    force_reprocess: bool
    dry_run: bool
    max_emails: Optional[int] = None
    debug_prompt: bool = False


@dataclass
class ProcessingResult:
    """
    Result of processing a single email.
    
    Attributes:
        uid: Email UID
        success: Whether processing succeeded
        error: Error message if processing failed
        classification_result: Classification result if successful
        note_content: Generated note content if successful
        file_path: Path where note was written (or would be written in dry-run)
        processing_time: Time taken to process this email (seconds)
    """
    uid: str
    success: bool
    error: Optional[str] = None
    classification_result: Optional[ClassificationResult] = None
    note_content: Optional[str] = None
    file_path: Optional[str] = None
    processing_time: float = 0.0


@dataclass
class PipelineSummary:
    """
    Summary statistics for a pipeline execution.
    
    Attributes:
        total_emails: Total emails processed
        successful: Number of successfully processed emails
        failed: Number of failed emails
        total_time: Total processing time (seconds)
        average_time: Average processing time per email (seconds)
    """
    total_emails: int
    successful: int
    failed: int
    total_time: float
    average_time: float


class Pipeline:
    """
    Main orchestration class for email processing pipeline.
    
    This class coordinates all components of the email processing system:
    - IMAP email retrieval
    - LLM classification
    - Decision logic application
    - Note generation
    - File writing
    - IMAP flag setting
    - Logging
    
    The pipeline handles errors gracefully, isolating failures per email
    to prevent crashes and ensure maximum processing throughput.
    
    Example:
        >>> pipeline = Pipeline()
        >>> options = ProcessOptions(uid=None, force_reprocess=False, dry_run=False)
        >>> summary = pipeline.process_emails(options)
        >>> print(f"Processed {summary.successful} emails successfully")
    """
    
    def __init__(self):
        """
        Initialize the pipeline with all required components.
        
        All components are initialized here to ensure they're ready for use.
        Configuration is accessed through the settings facade.
        """
        # Ensure settings are initialized
        try:
            settings._ensure_initialized()
        except ConfigError as e:
            logger.error(f"Configuration error: {e}")
            raise
        
        # Initialize components
        self.imap_client = ImapClient()
        self.llm_client = LLMClient()
        self.decision_logic = DecisionLogic()
        self.note_generator = NoteGenerator()
        self.email_logger = EmailLogger()
        
        # Initialize OpenRouter client for summarization
        try:
            api_key = settings.get_openrouter_api_key()
            api_url = settings.get_openrouter_api_url()
            self.openrouter_client = OpenRouterClient(api_key, api_url)
        except Exception as e:
            logger.warning(f"Could not initialize OpenRouter client for summarization: {e}")
            self.openrouter_client = None
        
        logger.info("Pipeline initialized successfully")
    
    def process_emails(self, options: ProcessOptions) -> PipelineSummary:
        """
        Process emails according to the provided options.
        
        This is the main entry point for email processing. It handles:
        - Email retrieval (all or by UID)
        - LLM classification
        - Decision logic application
        - Note generation
        - File writing
        - IMAP flag setting
        - Logging
        
        Args:
            options: Processing options (UID, force_reprocess, dry_run)
            
        Returns:
            PipelineSummary with processing statistics
            
        Raises:
            IMAPClientError: If IMAP connection fails
            ConfigError: If configuration is invalid
        """
        start_time = time.time()
        results: List[ProcessingResult] = []
        
        logger.info(f"Starting email processing pipeline (dry_run={options.dry_run}, force_reprocess={options.force_reprocess}, debug_prompt={options.debug_prompt})")
        
        # Store debug_prompt flag for use in classification
        self._debug_prompt = options.debug_prompt
        
        try:
            # Connect to IMAP
            self.imap_client.connect()
            logger.info("Connected to IMAP server")
            
            # Retrieve emails
            emails = self._retrieve_emails(options)
            logger.info(f"Retrieved {len(emails)} email(s) to process")
            
            if not emails:
                logger.info("No emails to process")
                return PipelineSummary(
                    total_emails=0,
                    successful=0,
                    failed=0,
                    total_time=time.time() - start_time,
                    average_time=0.0
                )
            
            # Set up progress bar if rich is available
            progress = None
            progress_task = None
            if RICH_AVAILABLE and len(emails) > 0:
                console = Console()
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console
                )
                progress.start()
                progress_task = progress.add_task(
                    f"[cyan]Processing {len(emails)} email(s)...",
                    total=len(emails)
                )
            
            # Process each email
            # Note: Processing emails one at a time to prevent memory leaks during batch processing
            # Each email is processed and result is stored, but email_data is not kept in memory
            for idx, email_data in enumerate(emails, 1):
                logger.debug(f"Processing email {idx}/{len(emails)}")
                result = self._process_single_email(email_data, options)
                results.append(result)
                
                # Clear email_data reference to help with memory management
                # (Python GC will handle cleanup, but explicit clearing helps)
                del email_data
                
                # Update progress bar if available
                if progress and progress_task is not None:
                    progress.update(progress_task, advance=1)
                # Fallback: Log progress for large batches if no progress bar
                elif len(emails) > 10 and idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{len(emails)} emails processed")
            
            # Stop progress bar after processing
            if progress:
                progress.stop()
            
            # Generate summary with detailed statistics
            total_time = time.time() - start_time
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            average_time = total_time / len(results) if results else 0.0
            
            # Calculate additional statistics
            total_processing_time = sum(r.processing_time for r in results)
            avg_processing_time = total_processing_time / len(results) if results else 0.0
            
            summary = PipelineSummary(
                total_emails=len(results),
                successful=successful,
                failed=failed,
                total_time=total_time,
                average_time=average_time
            )
            
            # Comprehensive summary logging
            logger.info("=" * 60)
            logger.info("EMAIL PROCESSING SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total emails processed: {summary.total_emails}")
            logger.info(f"  [OK] Successful: {summary.successful}")
            logger.info(f"  [FAILED] Failed: {summary.failed}")
            logger.info(f"Total pipeline time: {summary.total_time:.2f}s")
            logger.info(f"Average time per email: {summary.average_time:.2f}s")
            logger.info(f"Average processing time (per email): {avg_processing_time:.2f}s")
            
            if summary.successful > 0:
                success_rate = (summary.successful / summary.total_emails) * 100
                logger.info(f"Success rate: {success_rate:.1f}%")
            
            if summary.failed > 0:
                logger.warning(f"⚠ {summary.failed} email(s) failed processing - check logs for details")
                # Log details of failed emails
                failed_uids = [r.uid for r in results if not r.success]
                failed_errors = [r.error for r in results if not r.success and r.error]
                logger.debug(f"Failed email UIDs: {failed_uids}")
                if failed_errors:
                    logger.debug(f"Error messages: {failed_errors[:5]}")  # Show first 5 errors
                    if len(failed_errors) > 5:
                        logger.debug(f"... and {len(failed_errors) - 5} more errors")
            
            # Performance check (requirement: local operations < 1s)
            if avg_processing_time > 1.0:
                logger.warning(
                    f"⚠ Performance warning: Average processing time ({avg_processing_time:.2f}s) "
                    f"exceeds requirement (< 1s). Consider optimization."
                )
            else:
                logger.debug(f"[OK] Performance requirement met: {avg_processing_time:.2f}s < 1s")
            
            logger.info("=" * 60)
            
            return summary
            
        except IMAPClientError as e:
            logger.error(f"IMAP error during processing: {e}")
            # Return partial summary if we processed some emails before the error
            if results:
                total_time = time.time() - start_time
                successful = sum(1 for r in results if r.success)
                failed = len(results) - successful
                logger.warning(f"Returning partial results: {successful} successful, {failed} failed")
                return PipelineSummary(
                    total_emails=len(results),
                    successful=successful,
                    failed=failed,
                    total_time=total_time,
                    average_time=total_time / len(results) if results else 0.0
                )
            raise
        except Exception as e:
            logger.error(f"Unexpected error during processing: {e}", exc_info=True)
            # Return partial summary if we processed some emails before the error
            if results:
                total_time = time.time() - start_time
                successful = sum(1 for r in results if r.success)
                failed = len(results) - successful
                logger.warning(f"Returning partial results after unexpected error: {successful} successful, {failed} failed")
                return PipelineSummary(
                    total_emails=len(results),
                    successful=successful,
                    failed=failed,
                    total_time=total_time,
                    average_time=total_time / len(results) if results else 0.0
                )
            raise
        finally:
            # Cleanup operations: Disconnect from IMAP and release resources
            # This ensures no memory leaks and proper resource cleanup
            try:
                if self.imap_client and hasattr(self.imap_client, '_connected') and self.imap_client._connected:
                    self.imap_client.disconnect()
                    logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error disconnecting from IMAP during cleanup: {e}")
            
            # Additional cleanup: Clear any cached data to prevent memory leaks
            # (Currently no cached data, but this is a placeholder for future optimizations)
            logger.debug("Pipeline cleanup complete")
    
    def _retrieve_emails(self, options: ProcessOptions) -> List[Dict[str, Any]]:
        """
        Retrieve emails to process based on options.
        
        This method handles:
        - Single email retrieval by UID (with processed status check)
        - Batch retrieval of unprocessed emails
        - Force reprocess mode (ignores processed status)
        - Comprehensive error handling and logging
        
        Args:
            options: Processing options (uid, force_reprocess, dry_run)
            
        Returns:
            List of email data dictionaries ready for processing
            
        Raises:
            IMAPClientError: If IMAP operations fail
        """
        try:
            if options.uid:
                # Process specific email by UID
                logger.info(f"Retrieving email with UID: {options.uid}")
                
                try:
                    # Retrieve email by UID
                    email_data = self.imap_client.get_email_by_uid(options.uid)
                    
                    if not email_data:
                        logger.warning(f"Email with UID {options.uid} not found")
                        return []
                    
                    # Check if already processed (unless force_reprocess is set)
                    if not options.force_reprocess:
                        processed_tag = settings.get_imap_processed_tag()
                        if self.imap_client.is_processed(options.uid):
                            logger.info(
                                f"Email UID {options.uid} already processed (has flag '{processed_tag}'). "
                                f"Use --force-reprocess to reprocess."
                            )
                            return []
                        else:
                            logger.debug(f"Email UID {options.uid} is not processed, proceeding")
                    else:
                        logger.info(f"Force reprocess mode: processing email UID {options.uid} even if already processed")
                    
                    logger.info(f"Successfully retrieved email UID {options.uid}: '{email_data.get('subject', '[No Subject]')}'")
                    return [email_data]
                    
                except IMAPFetchError as e:
                    logger.error(f"Failed to retrieve email UID {options.uid}: {e}")
                    # Return empty list to allow processing to continue with other emails
                    return []
                except Exception as e:
                    logger.error(f"Unexpected error retrieving email UID {options.uid}: {e}", exc_info=True)
                    return []
            else:
                # Process all unprocessed emails
                logger.info("Retrieving unprocessed emails from IMAP server")
                
                try:
                    # Get configuration from settings facade
                    # Use CLI-provided max_emails if available, otherwise use config
                    max_emails = options.max_emails if options.max_emails is not None else settings.get_max_emails_per_run()
                    processed_tag = settings.get_imap_processed_tag()
                    user_query = settings.get_imap_query()
                    
                    logger.debug(f"IMAP query: {user_query}")
                    logger.debug(f"Max emails per run: {max_emails} {'(from CLI)' if options.max_emails is not None else '(from config)'}")
                    logger.debug(f"Processed tag: {processed_tag}")
                    logger.debug(f"Force reprocess: {options.force_reprocess}")
                    
                    # Retrieve unprocessed emails
                    emails = self.imap_client.get_unprocessed_emails(
                        max_emails=max_emails,
                        force_reprocess=options.force_reprocess
                    )
                    
                    logger.info(f"Retrieved {len(emails)} email(s) for processing")
                    
                    if emails and logger.isEnabledFor(logging.DEBUG):
                        # Log details of retrieved emails
                        for email_data in emails:
                            uid = email_data.get('uid', 'unknown')
                            subject = email_data.get('subject', '[No Subject]')
                            logger.debug(f"  - UID {uid}: '{subject[:60]}'")
                    
                    return emails
                    
                except IMAPFetchError as e:
                    logger.error(f"Failed to retrieve unprocessed emails: {e}")
                    # Return empty list to allow graceful handling
                    return []
                except Exception as e:
                    logger.error(f"Unexpected error retrieving unprocessed emails: {e}", exc_info=True)
                    return []
                    
        except IMAPConnectionError as e:
            logger.error(f"IMAP connection error during email retrieval: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in email retrieval: {e}", exc_info=True)
            raise
    
    def _process_single_email(self, email_data: Dict[str, Any], options: ProcessOptions) -> ProcessingResult:
        """
        Process a single email through the complete pipeline.
        
        This method handles all stages of processing:
        1. LLM classification
        2. Decision logic application
        3. Note generation
        4. File writing
        5. IMAP flag setting
        6. Logging
        
        Errors are isolated per email to prevent crashes.
        
        Args:
            email_data: Email data dictionary from IMAP
            options: Processing options
            
        Returns:
            ProcessingResult with processing outcome
        """
        start_time = time.time()
        uid = email_data.get('uid', 'unknown')
        
        logger.info(f"Processing email UID: {uid}")
        
        try:
            # Stage 1: LLM Classification (with error handling)
            llm_response = self._classify_email_with_fallback(email_data, uid)
            
            # Stage 2: Decision Logic (with comprehensive logging)
            classification_result = self._apply_decision_logic(llm_response, uid, options)
            
            # Log classification results to both logging systems
            self._log_classification_results(uid, llm_response, classification_result, options)
            
            # Stage 2.5: Summarization (if email is important and summarization is configured)
            self._generate_summary_if_needed(email_data, classification_result, uid)
            
            # Stage 3: Note Generation
            note_content = self._generate_note(email_data, classification_result)
            
            # Stage 4: File Writing (respects dry-run)
            file_path = self._write_note(email_data, note_content, options)
            
            # Stage 5: IMAP Flag Setting (respects dry-run)
            self._set_imap_flags(uid, options)
            
            # Stage 6: Final Logging
            self._log_email_processed(uid, classification_result, success=True)
            
            processing_time = time.time() - start_time
            logger.info(f"Successfully processed email UID: {uid} in {processing_time:.2f}s")
            
            return ProcessingResult(
                uid=uid,
                success=True,
                classification_result=classification_result,
                note_content=note_content,
                file_path=file_path,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Error processing email UID {uid}: {error_msg}", exc_info=True)
            
            # Log failure
            self._log_email_processed(uid, None, success=False, error=error_msg)
            
            return ProcessingResult(
                uid=uid,
                success=False,
                error=error_msg,
                processing_time=processing_time
            )
    
    def _classify_email_with_fallback(self, email_data: Dict[str, Any], uid: str) -> LLMResponse:
        """
        Classify email using LLM with comprehensive error handling and fallback strategies.
        
        This method implements the error handling requirements from Task 10:
        - Retries with exponential backoff (handled by LLMClient)
        - Fallback to error response (-1, -1) if all retries fail
        - Detailed logging of classification attempts
        
        Args:
            email_data: Email data dictionary
            uid: Email UID for logging
            
        Returns:
            LLMResponse with spam_score and importance_score (or error values -1, -1 on failure)
        """
        # Extract email content for LLM
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        from_addr = email_data.get('from', '')
        
        logger.info(f"Starting LLM classification for email UID: {uid}")
        logger.debug(f"Email subject: {subject[:60]}...")
        logger.debug(f"Email from: {from_addr}")
        
        # Truncate body if needed
        max_chars = settings.get_max_body_chars()
        original_body_length = len(body)
        if len(body) > max_chars:
            body = body[:max_chars] + "... [truncated]"
            logger.debug(f"Truncated email body from {original_body_length} to {max_chars} characters")
        
        # Build prompt (this renders the template with email data)
        rendered_prompt = self._build_classification_prompt(subject, from_addr, body)
        
        # Call LLM with error handling
        # The rendered_prompt already contains the email content via Jinja2 template,
        # so we pass it as user_prompt and pass empty string as email_content
        # (the LLM client will still format it for JSON response)
        try:
            logger.debug("Calling LLM API for classification")
            # Get debug_prompt from options if available (passed through from CLI)
            debug_prompt = getattr(self, '_debug_prompt', False)
            # Pass rendered prompt as user_prompt since it already contains email data
            llm_response = self.llm_client.classify_email(
                email_content="",  # Empty since email is already in rendered_prompt
                user_prompt=rendered_prompt,
                debug_prompt=debug_prompt,
                debug_uid=uid
            )
            
            logger.info(
                f"LLM classification successful for UID {uid}: "
                f"spam_score={llm_response.spam_score}, "
                f"importance_score={llm_response.importance_score}"
            )
            
            return llm_response
            
        except LLMClientError as e:
            # LLM API failed after all retries - use fallback error response
            logger.error(
                f"LLM classification failed for email UID {uid} after retries: {e}. "
                f"Using error fallback response with -1 scores."
            )
            
            # Create error LLMResponse with -1 scores (Task 10 requirement)
            # The decision logic will handle converting this to an error ClassificationResult
            error_response = LLMResponse(
                spam_score=-1,
                importance_score=-1,
                raw_response=f"Error: {type(e).__name__} - {str(e)}"
            )
            
            logger.warning(
                f"Using error fallback for UID {uid}: "
                f"spam_score={error_response.spam_score}, "
                f"importance_score={error_response.importance_score}"
            )
            
            return error_response
            
        except Exception as e:
            # Unexpected error - use fallback
            logger.error(
                f"Unexpected error during LLM classification for UID {uid}: {e}",
                exc_info=True
            )
            
            # Create error LLMResponse with -1 scores
            error_response = LLMResponse(
                spam_score=-1,
                importance_score=-1,
                raw_response=f"Unexpected error: {type(e).__name__} - {str(e)}"
            )
            
            return error_response
    
    def _classify_email(self, email_data: Dict[str, Any]) -> LLMResponse:
        """
        Classify email using LLM (legacy method, kept for compatibility).
        
        Use _classify_email_with_fallback for new code.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            LLMResponse with spam_score and importance_score
            
        Raises:
            LLMClientError: If LLM classification fails
        """
        uid = email_data.get('uid', 'unknown')
        return self._classify_email_with_fallback(email_data, uid)
    
    def _apply_decision_logic(
        self,
        llm_response: LLMResponse,
        uid: str,
        options: ProcessOptions
    ) -> ClassificationResult:
        """
        Apply decision logic to LLM response with comprehensive logging.
        
        This method:
        - Applies thresholds from settings facade
        - Logs decision-making process
        - Handles edge cases
        - Respects dry-run mode (classification still happens, just logged)
        
        Args:
            llm_response: LLM response with scores
            uid: Email UID for logging
            options: Processing options
            
        Returns:
            ClassificationResult with final classification decision
        """
        # Get thresholds from settings facade
        importance_threshold = settings.get_importance_threshold()
        spam_threshold = settings.get_spam_threshold()
        
        logger.info(
            f"Applying decision logic for UID {uid}: "
            f"scores (spam={llm_response.spam_score}, importance={llm_response.importance_score}), "
            f"thresholds (spam={spam_threshold}, importance={importance_threshold})"
        )
        
        # Apply decision logic
        classification_result = self.decision_logic.classify(llm_response)
        
        # Log decision results
        logger.info(
            f"Classification decision for UID {uid}: "
            f"is_important={classification_result.is_important}, "
            f"is_spam={classification_result.is_spam}, "
            f"confidence={classification_result.confidence}, "
            f"status={classification_result.status.value}"
        )
        
        # Log threshold comparisons
        if classification_result.status.value != 'error':
            importance_met = llm_response.importance_score >= importance_threshold
            spam_met = llm_response.spam_score >= spam_threshold
            
            logger.debug(
                f"Threshold comparison for UID {uid}: "
                f"importance_score {llm_response.importance_score} >= {importance_threshold} = {importance_met}, "
                f"spam_score {llm_response.spam_score} >= {spam_threshold} = {spam_met}"
            )
        
        # In dry-run mode, log what decision would be made
        if options.dry_run:
            try:
                from src.dry_run_output import DryRunOutput
                output = DryRunOutput()
                output.info(f"Classification Decision (UID {uid}):")
                output.detail("  Importance", f"{llm_response.importance_score}/10 (threshold: {importance_threshold})")
                output.detail("  Spam", f"{llm_response.spam_score}/10 (threshold: {spam_threshold})")
                output.detail("  Result", f"Important={classification_result.is_important}, Spam={classification_result.is_spam}")
            except ImportError:
                logger.info(
                    f"[DRY RUN] Classification: UID {uid} - "
                    f"Important={classification_result.is_important}, Spam={classification_result.is_spam}"
                )
        
        return classification_result
    
    def _generate_summary_if_needed(
        self,
        email_data: Dict[str, Any],
        classification_result: ClassificationResult,
        uid: str
    ) -> None:
        """
        Generate summary for email if summarization is required.
        
        This method:
        - Checks if email tags match summarization_tags from config
        - Calls LLM to generate summary if required
        - Stores summary result in email_data for template rendering
        - Handles errors gracefully (summarization failure doesn't break pipeline)
        
        Args:
            email_data: Email data dictionary (will be modified to include summary)
            classification_result: Classification result with tags
            uid: Email UID for logging
        """
        # Skip if OpenRouter client not available
        if not self.openrouter_client:
            logger.debug(f"Skipping summarization for UID {uid} (OpenRouter client not available)")
            return
        
        try:
            # Get tags from classification result
            email_tags = classification_result.to_frontmatter_dict().get('tags', [])
            
            # Create email dict with tags for summarization check
            email_with_tags = {**email_data, 'tags': email_tags}
            
            # Check if summarization is required (uses V3 settings directly)
            summarization_result = check_summarization_required(email_with_tags)
            
            if not summarization_result.get('summarize', False):
                reason = summarization_result.get('reason', 'unknown')
                logger.info(f"Summarization not required for UID {uid}: {reason} (tags: {email_tags})")
                return
            
            logger.info(f"Summarization required for email UID {uid} (tags: {email_tags})")
            
            # Generate summary using LLM (uses V3 settings directly)
            try:
                summary_result = generate_email_summary(
                    email_data,
                    self.openrouter_client,
                    summarization_result
                )
                
                # Store summary result in email_data for template rendering
                email_data['summary'] = summary_result
                
                if summary_result.get('success', False):
                    summary_text = summary_result.get('summary', '')
                    logger.info(f"Successfully generated summary for email UID {uid} ({len(summary_text)} chars)")
                    logger.debug(f"Summary data: success={summary_result.get('success')}, summary_length={len(summary_text)}, action_items={len(summary_result.get('action_items', []))}, priority={summary_result.get('priority')}")
                else:
                    error = summary_result.get('error', 'unknown')
                    logger.warning(f"Summary generation failed for email UID {uid}: {error}")
                    
            except Exception as e:
                # Graceful degradation - log but continue
                logger.error(f"Error generating summary for email UID {uid}: {e}", exc_info=True)
                email_data['summary'] = {
                    'success': False,
                    'summary': '',
                    'action_items': [],
                    'priority': 'medium',
                    'error': f'summary_generation_error: {str(e)}'
                }
                
        except Exception as e:
            # Never let summarization check break the pipeline
            logger.error(f"Unexpected error in summarization check for UID {uid}: {e}", exc_info=True)
            # Don't set summary - template will handle missing summary gracefully
    
    def _log_classification_results(
        self,
        uid: str,
        llm_response: LLMResponse,
        classification_result: ClassificationResult,
        options: ProcessOptions
    ) -> None:
        """
        Log classification results to both logging systems.
        
        This implements the requirement to log classification results and decisions
        to both operational logs and structured analytics.
        
        Args:
            uid: Email UID
            llm_response: LLM response with raw scores
            classification_result: Final classification result
            options: Processing options
        """
        # Log to operational logs (unstructured)
        logger.info(
            f"Classification complete for UID {uid}: "
            f"LLM scores (spam={llm_response.spam_score}, importance={llm_response.importance_score}), "
            f"Decision (important={classification_result.is_important}, spam={classification_result.is_spam}), "
            f"Status={classification_result.status.value}"
        )
        
        # Log to structured analytics (via EmailLogger)
        # This will be written to analytics.jsonl
        self.email_logger.log_classification_result(
            uid=uid,
            importance_score=llm_response.importance_score,
            spam_score=llm_response.spam_score,
            is_important=classification_result.is_important,
            is_spam=classification_result.is_spam
        )
    
    def _build_classification_prompt(self, subject: str, from_addr: str, body: str) -> str:
        """
        Build classification prompt from email data.
        
        Uses prompt renderer if available, otherwise uses simple format.
        The LLM client will format this for JSON response.
        
        Args:
            subject: Email subject
            from_addr: Email sender
            body: Email body
            
        Returns:
            Formatted prompt string
        """
        # Try to use prompt renderer
        try:
            from src.prompt_renderer import render_email_prompt
            email_data = {
                'subject': subject,
                'from': from_addr,
                'email_content': body  # Template expects 'email_content', not 'body'
            }
            prompt = render_email_prompt(email_data)
            return prompt
        except Exception as e:
            logger.warning(f"Could not use prompt renderer: {e}, using simple format")
            # Fallback to simple format
            email_content = f"Subject: {subject}\nFrom: {from_addr}\n\nBody:\n{body}"
            return email_content
    
    def _generate_note(self, email_data: Dict[str, Any], classification_result: ClassificationResult) -> str:
        """
        Generate note content from email data and classification result.
        
        This method:
        - Calls the note generation module (src/note_generator.py)
        - Handles template rendering errors with fallback
        - Logs note generation operations
        - Uses decision logic results to determine note content (tags, classification)
        
        Notes are generated for all emails. The decision logic affects the content
        (tags, classification metadata) but not whether a note is generated.
        
        Args:
            email_data: Email data dictionary
            classification_result: Classification result from decision logic
            
        Returns:
            Generated note content (Markdown)
            
        Raises:
            TemplateRenderError: If both primary and fallback template rendering fails
        """
        uid = email_data.get('uid', 'unknown')
        email_subject = email_data.get('subject', '[No Subject]')
        
        logger.info(f"Generating note for email UID: {uid}")
        logger.debug(f"Email subject: {email_subject[:60]}...")
        logger.debug(
            f"Classification: important={classification_result.is_important}, "
            f"spam={classification_result.is_spam}, status={classification_result.status.value}"
        )
        
        try:
            # Generate note using note generator
            # The note generator uses the classification result to determine:
            # - Tags (important, spam, #process_error)
            # - Frontmatter metadata (scores, status)
            # - Conditional content sections
            note_content = self.note_generator.generate_note(
                email_data=email_data,
                classification_result=classification_result
            )
            
            logger.info(f"Successfully generated note for UID {uid} ({len(note_content)} characters)")
            logger.debug(f"Note preview (first 200 chars): {note_content[:200]}...")
            
            return note_content
            
        except TemplateRenderError as e:
            error_msg = f"Note generation failed for email UID {uid}: {e}"
            logger.error(error_msg, exc_info=True)
            raise
        except Exception as e:
            error_msg = f"Unexpected error generating note for email UID {uid}: {e}"
            logger.error(error_msg, exc_info=True)
            raise TemplateRenderError(error_msg) from e
    
    def _write_note(self, email_data: Dict[str, Any], note_content: str, options: ProcessOptions) -> Optional[str]:
        """
        Write note to file system.
        
        This method handles:
        - Note generation for all emails (decision logic affects content, not generation)
        - File writing with proper naming conventions
        - Directory structure creation (handled by safe_write_file)
        - Comprehensive logging of file operations
        - Error handling for file system issues
        - Dry-run mode support (logs what would be written)
        
        Args:
            email_data: Email data dictionary
            note_content: Generated note content
            options: Processing options
            
        Returns:
            Path to written file (or path that would be used in dry-run mode)
            
        Raises:
            FileWriteError: If file writing fails
            InvalidPathError: If vault path is invalid
            WritePermissionError: If write permission is denied
        """
        from src.obsidian_note_creation import write_obsidian_note
        from src.obsidian_utils import InvalidPathError, WritePermissionError, FileWriteError
        from datetime import datetime
        
        uid = email_data.get('uid', 'unknown')
        email_subject = email_data.get('subject', '[No Subject]')
        
        # Check if in dry-run mode
        dry_run_mode = is_dry_run() or options.dry_run
        
        # Log file operation start
        if dry_run_mode:
            logger.info(f"[DRY RUN] Would write note for email UID: {uid}")
        else:
            logger.info(f"Writing note for email UID: {uid}")
        
        logger.debug(f"Email subject: {email_subject[:60]}...")
        logger.debug(f"Note content length: {len(note_content)} characters")
        
        try:
            # Get vault path from settings facade
            vault_path = settings.get_obsidian_vault()
            logger.debug(f"Obsidian vault path: {vault_path}")
            
            # Get email date for timestamp
            email_date = email_data.get('date')
            timestamp = None
            if email_date:
                try:
                    # Try to parse email date
                    from email.utils import parsedate_to_datetime
                    timestamp = parsedate_to_datetime(email_date)
                    logger.debug(f"Using email date for timestamp: {timestamp}")
                except Exception as e:
                    # If parsing fails, use current time
                    logger.warning(f"Failed to parse email date '{email_date}': {e}, using current time")
                    timestamp = datetime.now(timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)
                logger.debug("No email date available, using current time")
            
            # Determine if we should overwrite (force_reprocess means overwrite)
            overwrite = options.force_reprocess
            if overwrite:
                logger.info(f"Force reprocess mode: will overwrite existing file if present")
            
            # Write note (safe_write_file respects dry-run mode and handles directory creation)
            file_path = write_obsidian_note(
                note_content=note_content,
                email_subject=email_subject,
                vault_path=vault_path,
                timestamp=timestamp,
                overwrite=overwrite
            )
            
            # Log successful file operation
            if dry_run_mode:
                logger.info(f"[DRY RUN] Would write note to: {file_path}")
                # In dry-run mode, also log what would be written
                try:
                    from src.dry_run_output import DryRunOutput
                    output = DryRunOutput()
                    output.info(f"File Writing (UID {uid}):")
                    output.detail("Path", file_path)
                    output.detail("Content length", f"{len(note_content)} characters")
                    output.detail("Overwrite", str(overwrite))
                except ImportError:
                    pass  # DryRunOutput not available, skip
            else:
                logger.info(f"Successfully wrote note to: {file_path}")
            
            return file_path
            
        except InvalidPathError as e:
            error_msg = f"Invalid vault path for email UID {uid}: {e}"
            logger.error(error_msg)
            raise
        except WritePermissionError as e:
            error_msg = f"Write permission denied for email UID {uid}: {e}"
            logger.error(error_msg)
            raise
        except FileWriteError as e:
            error_msg = f"Failed to write note for email UID {uid}: {e}"
            logger.error(error_msg, exc_info=True)
            raise
        except Exception as e:
            error_msg = f"Unexpected error writing note for email UID {uid}: {e}"
            logger.error(error_msg, exc_info=True)
            raise FileWriteError(error_msg) from e
    
    def _set_imap_flags(self, uid: str, options: ProcessOptions) -> None:
        """
        Set IMAP flags to mark email as processed after successful handling.
        
        This method:
        - Sets the processed tag to mark email as processed
        - Respects dry-run mode (logs what would be set without actually setting)
        - Handles errors gracefully to prevent pipeline crashes
        - Logs all flag operations for audit trail
        
        Args:
            uid: Email UID
            options: Processing options
            
        Raises:
            IMAPClientError: If IMAP operation fails (but errors are logged, not propagated)
        """
        processed_tag = settings.get_imap_processed_tag()
        dry_run_mode = is_dry_run() or options.dry_run
        
        if dry_run_mode:
            # In dry-run mode, don't set flags but log what would be set
            logger.info(f"[DRY RUN] Would set flag '{processed_tag}' for email UID: {uid}")
            try:
                from src.dry_run_output import DryRunOutput
                output = DryRunOutput()
                output.info(f"IMAP Flag Setting (UID {uid}):")
                output.detail("Flag", processed_tag)
                output.detail("Action", "Would set processed flag")
            except ImportError:
                pass  # DryRunOutput not available, skip
            return
        
        # Set processed flag (actual operation)
        try:
            logger.debug(f"Setting IMAP flag '{processed_tag}' for email UID: {uid}")
            success = self.imap_client.set_flag(uid, processed_tag)
            
            if success:
                logger.info(f"Successfully set flag '{processed_tag}' for email UID: {uid}")
            else:
                logger.warning(f"Failed to set flag '{processed_tag}' for email UID: {uid} (operation returned False)")
                # Don't raise exception - flag setting failure shouldn't crash the pipeline
                # The email will be retried on next run if it doesn't have the flag
                
        except IMAPConnectionError as e:
            error_msg = f"IMAP connection error while setting flag for UID {uid}: {e}"
            logger.error(error_msg)
            # Don't raise - allow pipeline to continue with other emails
            # Connection issues will be handled at the pipeline level
        except IMAPClientError as e:
            error_msg = f"IMAP error while setting flag '{processed_tag}' for UID {uid}: {e}"
            logger.error(error_msg)
            # Don't raise - flag setting failure shouldn't crash the pipeline
        except Exception as e:
            error_msg = f"Unexpected error setting flag '{processed_tag}' for UID {uid}: {e}"
            logger.error(error_msg, exc_info=True)
            # Don't raise - unexpected errors shouldn't crash the pipeline
    
    def _log_email_processed(self, uid: str, classification_result: Optional[ClassificationResult], 
                            success: bool, error: Optional[str] = None) -> None:
        """
        Log email processing result to both logging systems.
        
        Args:
            uid: Email UID
            classification_result: Classification result (if successful)
            success: Whether processing succeeded
            error: Error message (if failed)
        """
        if success and classification_result:
            # Log successful processing
            self.email_logger.log_email_processed(
                uid=uid,
                status='success',
                importance_score=classification_result.importance_score,
                spam_score=classification_result.spam_score
            )
        else:
            # Log failure
            self.email_logger.log_email_processed(
                uid=uid,
                status='error',
                importance_score=-1,
                spam_score=-1,
                error=error
            )


# ============================================================================
# V4 Master Orchestrator (Multi-Account Support)
# ============================================================================

import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# V4 imports
from src.account_processor import AccountProcessor, create_imap_client_from_config, AccountProcessorError, AccountProcessorSetupError, AccountProcessorRunError
from src.config_loader import ConfigLoader, ConfigurationError
from src.rules import load_blacklist_rules, load_whitelist_rules
from src.content_parser import parse_html_content
# Note: LLMClient, NoteGenerator, DecisionLogic are already imported above for V3


@dataclass
class OrchestrationResult:
    """
    Result of orchestrating multiple account processing operations.
    
    Attributes:
        total_accounts: Total number of accounts processed
        successful_accounts: Number of accounts processed successfully
        failed_accounts: Number of accounts that failed
        account_results: Dictionary mapping account_id to (success: bool, error: Optional[str])
        total_time: Total orchestration time (seconds)
    """
    total_accounts: int
    successful_accounts: int
    failed_accounts: int
    account_results: Dict[str, Tuple[bool, Optional[str]]] = field(default_factory=dict)
    total_time: float = 0.0
    
    def __str__(self) -> str:
        """Format orchestration result for display."""
        return (
            f"Orchestration complete: {self.successful_accounts}/{self.total_accounts} accounts successful, "
            f"{self.failed_accounts} failed, total time: {self.total_time:.2f}s"
        )


class MasterOrchestrator:
    """
    V4 Master Orchestrator for managing multiple account processing operations.
    
    This class coordinates the processing of multiple email accounts by:
    - Parsing CLI arguments for account selection
    - Discovering available accounts from configuration
    - Creating isolated AccountProcessor instances for each account
    - Managing the overall processing flow with robust error handling
    
    State Isolation:
        Each account is processed in complete isolation:
        - Separate AccountProcessor instances (no shared state)
        - Separate IMAP connections
        - Separate configuration (merged per account)
        - Failures in one account don't affect others
    
    Usage:
        >>> from src.orchestrator import MasterOrchestrator
        >>> 
        >>> orchestrator = MasterOrchestrator(
        ...     config_base_dir='config',
        ...     logger=logger
        ... )
        >>> 
        >>> result = orchestrator.run(['--account', 'work'])
        >>> print(result)
    
    See Also:
        - docs/v4-orchestrator.md - Complete V4 orchestrator documentation
        - src/account_processor.py - AccountProcessor class
        - pdd_V4.md - V4 Product Design Document
    """
    
    def __init__(
        self,
        config_base_dir: Path | str = "config",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize MasterOrchestrator with configuration directory and logger.
        
        Args:
            config_base_dir: Base directory containing configuration files
                           (default: 'config')
            logger: Optional logger instance (creates one if not provided)
        
        Note:
            The orchestrator uses ConfigLoader to discover and load account configurations.
            Account configs are expected in {config_base_dir}/accounts/*.yaml
        """
        # Configuration
        self.config_base_dir = Path(config_base_dir).resolve()
        
        # Logger
        if logger is None:
            logger = logging.getLogger(f"{__name__}.MasterOrchestrator")
        self.logger = logger
        
        # ConfigLoader for account discovery and config loading
        self.config_loader = ConfigLoader(
            base_dir=self.config_base_dir,
            enable_validation=True
        )
        
        # Account selection (set during run)
        self.accounts_to_process: List[str] = []
        
        # Note: Components are now created per-account with account-specific config
        # No longer using shared instances to support per-account configuration
        
        self.logger.info(f"MasterOrchestrator initialized with config_base_dir={self.config_base_dir}")
    
    @classmethod
    def parse_args(cls, argv: Optional[List[str]] = None) -> argparse.Namespace:
        """
        Parse CLI arguments for account selection and processing options.
        
        This method defines the CLI interface for the V4 orchestrator:
        - --account <id>: Process a single account (can be repeated)
        - --accounts <id1,id2,...>: Process multiple accounts (comma-separated)
        - --all-accounts: Process all available accounts
        - --config-dir <path>: Override config directory (default: 'config')
        - --dry-run: Run in preview mode (no side effects)
        - --log-level <level>: Set logging level (DEBUG, INFO, WARN, ERROR)
        
        Args:
            argv: Optional list of command-line arguments (default: sys.argv[1:])
        
        Returns:
            argparse.Namespace with parsed arguments
        
        Raises:
            SystemExit: If argument parsing fails or --help is requested
        """
        parser = argparse.ArgumentParser(
            description="V4 Email Agent: Multi-account email processing orchestrator",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --account work                    # Process single account
  %(prog)s --accounts work,personal         # Process multiple accounts
  %(prog)s --all-accounts                   # Process all available accounts
  %(prog)s --account work --dry-run         # Preview mode for single account
  %(prog)s --all-accounts --log-level DEBUG # Process all with debug logging
            """
        )
        
        # Account selection (mutually exclusive group)
        account_group = parser.add_mutually_exclusive_group()
        account_group.add_argument(
            '--account',
            action='append',
            dest='account_list',
            help='Process a specific account (can be repeated: --account work --account personal)'
        )
        account_group.add_argument(
            '--accounts',
            type=str,
            help='Process multiple accounts (comma-separated: --accounts work,personal)'
        )
        account_group.add_argument(
            '--all-accounts',
            action='store_true',
            help='Process all available accounts from config/accounts/'
        )
        
        # Configuration options
        parser.add_argument(
            '--config-dir',
            type=str,
            default='config',
            help='Base directory for configuration files (default: config)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in preview mode (no side effects, no file writes, no IMAP flag changes)'
        )
        parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            default='INFO',
            help='Set logging level (default: INFO)'
        )
        
        # Processing options
        parser.add_argument(
            '--uid',
            type=str,
            help='Target a specific email by UID. If not provided, processes emails according to configured query.'
        )
        parser.add_argument(
            '--force-reprocess',
            action='store_true',
            help='Ignore existing processed_tag and reprocess emails even if already marked as processed.'
        )
        parser.add_argument(
            '--max-emails',
            type=int,
            help='Maximum number of emails to process (overrides config max_emails_per_run). Useful for testing.'
        )
        parser.add_argument(
            '--debug-prompt',
            action='store_true',
            help='Write the formatted classification prompt to a debug file in logs/ directory. Useful for debugging prompt construction.'
        )
        
        return parser.parse_args(argv)
    
    def _discover_available_accounts(self) -> List[str]:
        """
        Discover all available accounts from the configuration directory.
        
        This method scans the config/accounts/ directory for YAML files
        and returns their names (without .yaml extension) as account identifiers.
        
        Returns:
            List of account identifiers (e.g., ['work', 'personal'])
        
        Raises:
            ConfigurationError: If the accounts directory doesn't exist or is invalid
        """
        accounts_dir = self.config_base_dir / 'accounts'
        
        if not accounts_dir.exists():
            self.logger.warning(
                f"Accounts directory not found: {accounts_dir}. "
                "No accounts will be discovered."
            )
            return []
        
        if not accounts_dir.is_dir():
            raise ConfigurationError(
                f"Accounts path exists but is not a directory: {accounts_dir}"
            )
        
        # Find all .yaml files in accounts directory
        account_files = list(accounts_dir.glob('*.yaml'))
        account_ids = [f.stem for f in account_files if f.is_file()]
        
        # Filter out example files
        account_ids = [aid for aid in account_ids if not aid.startswith('example')]
        
        self.logger.info(
            f"Discovered {len(account_ids)} account(s) in {accounts_dir}: {account_ids}"
        )
        
        return sorted(account_ids)
    
    def select_accounts(self, args: argparse.Namespace) -> List[str]:
        """
        Select accounts to process based on parsed CLI arguments.
        
        This method:
        1. Determines which accounts to process from CLI args
        2. Validates that requested accounts exist
        3. Returns a list of account identifiers to process
        
        Args:
            args: Parsed CLI arguments from parse_args()
        
        Returns:
            List of account identifiers to process
        
        Raises:
            ValueError: If an unknown account is requested
            ConfigurationError: If account discovery fails
        """
        account_ids: List[str] = []
        
        # Determine account selection strategy
        if args.all_accounts:
            # Process all available accounts
            account_ids = self._discover_available_accounts()
            if not account_ids:
                raise ConfigurationError(
                    f"No accounts found in {self.config_base_dir / 'accounts'}. "
                    "Create account configuration files (e.g., config/accounts/work.yaml)"
                )
            self.logger.info(f"Selected all accounts: {account_ids}")
        
        elif args.accounts:
            # Comma-separated list
            account_ids = [aid.strip() for aid in args.accounts.split(',') if aid.strip()]
            self.logger.info(f"Selected accounts from --accounts: {account_ids}")
        
        elif args.account_list:
            # Repeated --account flags
            account_ids = [aid.strip() for aid in args.account_list if aid.strip()]
            self.logger.info(f"Selected accounts from --account flags: {account_ids}")
        
        else:
            # Default: process all accounts
            account_ids = self._discover_available_accounts()
            if not account_ids:
                raise ConfigurationError(
                    f"No accounts found and no account specified. "
                    "Use --account <id>, --accounts <id1,id2>, or --all-accounts"
                )
            self.logger.info(f"No account specified, defaulting to all accounts: {account_ids}")
        
        # Validate that all requested accounts exist
        available_accounts = self._discover_available_accounts()
        invalid_accounts = [aid for aid in account_ids if aid not in available_accounts]
        
        if invalid_accounts:
            raise ValueError(
                f"Unknown account(s): {invalid_accounts}. "
                f"Available accounts: {available_accounts}"
            )
        
        # Store for use in processing loop
        self.accounts_to_process = account_ids
        
        self.logger.info(f"Selected {len(account_ids)} account(s) for processing: {account_ids}")
        
        return account_ids
    
    def _iter_accounts(self):
        """
        Iterator helper that yields each account identifier in turn.
        
        This encapsulates any future filtering, ordering, or batching logic.
        Currently just yields accounts in the order they were selected.
        
        Yields:
            Account identifier (str)
        """
        for account_id in self.accounts_to_process:
            yield account_id
    
    def _initialize_shared_services(self):
        """
        Initialize shared services that can be safely reused across accounts.
        
        These services are stateless or thread-safe and don't maintain
        account-specific state, so they can be shared to reduce overhead.
        
        Note:
            Services are initialized lazily on first use if not already initialized.
        """
        # Components are now created per-account with account-specific config
        # This method is kept for compatibility but does nothing
        pass
    
    def create_account_processor(self, account_id: str) -> AccountProcessor:
        """
        Create an isolated AccountProcessor instance for a specific account.
        
        This method:
        1. Loads merged configuration for the account
        2. Creates all required dependencies
        3. Instantiates AccountProcessor with account-specific config
        4. Ensures complete state isolation (no shared mutable state)
        
        Args:
            account_id: Account identifier (e.g., 'work', 'personal')
        
        Returns:
            AccountProcessor instance (not yet set up or run)
        
        Raises:
            ConfigurationError: If account configuration cannot be loaded
            AccountProcessorSetupError: If AccountProcessor creation fails
        """
        self.logger.info(f"Creating AccountProcessor for account: {account_id}")
        
        # Load merged configuration for this account
        try:
            account_config = self.config_loader.load_merged_config(account_id)
            self.logger.debug(f"Loaded merged configuration for account: {account_id}")
        except (FileNotFoundError, ConfigurationError) as e:
            raise ConfigurationError(
                f"Failed to load configuration for account '{account_id}': {e}"
            ) from e
        
        # Create account-specific logger
        account_logger = logging.getLogger(f"{__name__}.AccountProcessor.{account_id}")
        
        # Create components with account-specific configuration
        # Each account gets its own instances with account-specific config
        llm_client = LLMClient(account_config)
        note_generator = NoteGenerator(account_config)
        decision_logic = DecisionLogic(account_config)
        
        # Create AccountProcessor with isolated configuration and dependencies
        # All dependencies are injected to ensure testability and isolation
        processor = AccountProcessor(
            account_id=account_id,
            account_config=account_config,
            imap_client_factory=create_imap_client_from_config,
            llm_client=llm_client,
            blacklist_service=load_blacklist_rules,
            whitelist_service=load_whitelist_rules,
            note_generator=note_generator,
            parser=parse_html_content,
            decision_logic=decision_logic,
            logger=account_logger
        )
        
        self.logger.info(f"Successfully created AccountProcessor for account: {account_id}")
        
        return processor
    
    def run(self, argv: Optional[List[str]] = None) -> OrchestrationResult:
        """
        Main entry point: parse CLI args, select accounts, and orchestrate processing.
        
        This method coordinates the complete multi-account processing flow:
        1. Parse CLI arguments
        2. Select accounts to process
        3. Iterate through accounts
        4. Create isolated AccountProcessor for each account
        5. Execute processing with robust error handling
        6. Aggregate results and return summary
        
        Error Handling:
            Failures in one account are caught, logged, and recorded, but do not
            prevent processing of remaining accounts. All accounts are attempted
            even if some fail.
        
        Args:
            argv: Optional list of command-line arguments (default: sys.argv[1:])
        
        Returns:
            OrchestrationResult with processing summary
        
        Raises:
            SystemExit: If argument parsing fails
            ValueError: If account selection is invalid
            ConfigurationError: If configuration loading fails
        """
        start_time = time.time()
        result = OrchestrationResult(
            total_accounts=0,
            successful_accounts=0,
            failed_accounts=0
        )
        
        # Generate correlation ID for this orchestration run
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        self.logger.info("=" * 60)
        self.logger.info(f"V4 Master Orchestrator: Starting multi-account processing [correlation_id={correlation_id}]")
        self.logger.info("=" * 60)
        
        try:
            # Step 1: Parse CLI arguments
            args = self.parse_args(argv)
            
            # Update config_base_dir if specified
            if args.config_dir:
                self.config_base_dir = Path(args.config_dir).resolve()
                self.config_loader = ConfigLoader(
                    base_dir=self.config_base_dir,
                    enable_validation=True
                )
                self.logger.info(f"Using config directory: {self.config_base_dir}")
            
            # Set logging level
            if args.log_level:
                logging.getLogger().setLevel(getattr(logging, args.log_level))
                self.logger.info(f"Logging level set to: {args.log_level}")
            
            # Step 2: Select accounts
            account_ids = self.select_accounts(args)
            result.total_accounts = len(account_ids)
            
            if not account_ids:
                self.logger.warning("No accounts selected for processing")
                result.total_time = time.time() - start_time
                return result
            
            # Step 3: Process each account with error isolation
            for account_id in self._iter_accounts():
                account_start_time = time.time()
                processor = None
                
                # Set account context for this account's processing
                with with_account_context(account_id=account_id, correlation_id=correlation_id):
                    self.logger.info("=" * 60)
                    log_account_start(account_id, correlation_id=correlation_id)
                    self.logger.info("=" * 60)
                    
                    try:
                        # Create AccountProcessor for this account
                        processor = self.create_account_processor(account_id)
                        
                        # Set up account (IMAP connection, etc.)
                        processor.setup()
                        
                        # Run processing with options from CLI
                        processor.run(
                            force_reprocess=args.force_reprocess,
                            uid=args.uid,
                            max_emails=args.max_emails,
                            debug_prompt=args.debug_prompt
                        )
                        
                        # Teardown (cleanup, close connections)
                        processor.teardown()
                        
                        # Record success
                        account_time = time.time() - account_start_time
                        result.successful_accounts += 1
                        result.account_results[account_id] = (True, None)
                        log_account_end(account_id, success=True, processing_time=account_time, correlation_id=correlation_id)
                        
                    except AccountProcessorSetupError as e:
                        # Setup failed (e.g., IMAP connection error)
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"Setup failed: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='setup')
                        
                    except AccountProcessorRunError as e:
                        # Processing failed
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"Processing failed: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='processing')
                        
                    except AccountProcessorError as e:
                        # General AccountProcessor error
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"AccountProcessor error: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='account_processing')
                        
                    except Exception as e:
                        # Unexpected error
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"Unexpected error: {type(e).__name__}: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='unexpected')
                        
                    finally:
                        # Ensure cleanup happens even on failure
                        if processor is not None:
                            try:
                                processor.teardown()
                            except Exception as cleanup_error:
                                self.logger.warning(
                                    f"Error during cleanup for account '{account_id}': {cleanup_error}",
                                    exc_info=True
                                )
            
            # Step 4: Generate summary
            result.total_time = time.time() - start_time
            
            self.logger.info("=" * 60)
            self.logger.info("V4 Master Orchestrator: Processing complete")
            self.logger.info("=" * 60)
            self.logger.info(f"Total accounts: {result.total_accounts}")
            self.logger.info(f"  [OK] Successful: {result.successful_accounts}")
            self.logger.info(f"  [FAILED] Failed: {result.failed_accounts}")
            self.logger.info(f"Total time: {result.total_time:.2f}s")
            
            if result.failed_accounts > 0:
                self.logger.warning("Some accounts failed processing - check logs for details")
                for account_id, (success, error) in result.account_results.items():
                    if not success:
                        self.logger.warning(f"  - {account_id}: {error}")
            
            return result
            
        except (ValueError, ConfigurationError) as e:
            # Configuration or validation errors
            result.total_time = time.time() - start_time
            self.logger.error(f"Orchestration failed: {e}", exc_info=True)
            raise
            
        except Exception as e:
            # Unexpected errors
            result.total_time = time.time() - start_time
            self.logger.error(f"Unexpected orchestration error: {e}", exc_info=True)
            raise


def main():
    """
    Top-level integration point for CLI usage.
    
    This function can be used as an entry point for the V4 orchestrator:
    
    Usage:
        python -m src.orchestrator
        # or
        from src.orchestrator import main
        main()
    """
    import sys
    
    # Initialize centralized logging (first thing on startup)
    try:
        from src.logging_config import init_logging
        init_logging()
    except Exception as e:
        # Fallback to basic logging if centralized logging fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger.warning(f"Could not initialize centralized logging, using basic logging: {e}")
    
    # Create orchestrator and run
    orchestrator = MasterOrchestrator()
    result = orchestrator.run()
    
    # Exit with appropriate code
    if result.failed_accounts > 0:
        sys.exit(1)
    else:
        sys.exit(0)
