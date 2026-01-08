"""
V3 Orchestrator Module

This module provides high-level business logic orchestration for the email processing pipeline.
It coordinates all components (IMAP, LLM, decision logic, note generation, logging) into a
cohesive end-to-end processing flow.

Architecture:
    - Pipeline class: Main orchestration class that coordinates all modules
    - ProcessOptions: Configuration for pipeline execution
    - Error handling: Isolated per-email error handling to prevent crashes
    - Performance: Local operations < 1s, no memory leaks during batch processing

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
    >>> results = pipeline.process_emails(options)
"""
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from src.settings import settings
from src.imap_client import ImapClient, IMAPClientError, IMAPConnectionError, IMAPFetchError
from src.llm_client import LLMClient, LLMResponse, LLMClientError
from src.decision_logic import DecisionLogic, ClassificationResult
from src.note_generator import NoteGenerator, TemplateRenderError
from src.v3_logger import EmailLogger
from src.dry_run import is_dry_run
from src.config import ConfigError

logger = logging.getLogger(__name__)


@dataclass
class ProcessOptions:
    """
    Options for email processing pipeline execution.
    
    Attributes:
        uid: Optional email UID to process (None = process all unprocessed)
        force_reprocess: If True, reprocess emails even if already marked as processed
        dry_run: If True, don't write files or set flags (preview mode)
    """
    uid: Optional[str]
    force_reprocess: bool
    dry_run: bool


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
        
        logger.info(f"Starting email processing pipeline (dry_run={options.dry_run}, force_reprocess={options.force_reprocess})")
        
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
            
            # Process each email
            for email_data in emails:
                result = self._process_single_email(email_data, options)
                results.append(result)
            
            # Generate summary
            total_time = time.time() - start_time
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            summary = PipelineSummary(
                total_emails=len(results),
                successful=successful,
                failed=failed,
                total_time=total_time,
                average_time=total_time / len(results) if results else 0.0
            )
            
            logger.info(f"Processing complete: {summary.successful} successful, {summary.failed} failed in {summary.total_time:.2f}s")
            
            return summary
            
        except IMAPClientError as e:
            logger.error(f"IMAP error during processing: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during processing: {e}", exc_info=True)
            raise
        finally:
            # Disconnect from IMAP
            try:
                self.imap_client.disconnect()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error disconnecting from IMAP: {e}")
    
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
                    max_emails = settings.get_max_emails_per_run()
                    processed_tag = settings.get_imap_processed_tag()
                    user_query = settings.get_imap_query()
                    
                    logger.debug(f"IMAP query: {user_query}")
                    logger.debug(f"Max emails per run: {max_emails}")
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
            # Stage 1: LLM Classification
            llm_response = self._classify_email(email_data)
            
            # Stage 2: Decision Logic
            classification_result = self.decision_logic.classify(llm_response)
            
            # Stage 3: Note Generation
            note_content = self._generate_note(email_data, classification_result)
            
            # Stage 4: File Writing
            file_path = self._write_note(email_data, note_content, options)
            
            # Stage 5: IMAP Flag Setting
            self._set_imap_flags(uid, options)
            
            # Stage 6: Logging
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
    
    def _classify_email(self, email_data: Dict[str, Any]) -> LLMResponse:
        """
        Classify email using LLM.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            LLMResponse with spam_score and importance_score
            
        Raises:
            LLMClientError: If LLM classification fails
        """
        # Extract email content for LLM
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        from_addr = email_data.get('from', '')
        
        # Truncate body if needed
        max_chars = settings.get_max_body_chars()
        if len(body) > max_chars:
            body = body[:max_chars] + "... [truncated]"
        
        # Build prompt
        prompt = self._build_classification_prompt(subject, from_addr, body)
        
        # Call LLM
        return self.llm_client.classify_email(prompt)
    
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
                'body': body
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
        
        Args:
            email_data: Email data dictionary
            classification_result: Classification result from decision logic
            
        Returns:
            Generated note content (Markdown)
            
        Raises:
            TemplateRenderError: If note generation fails
        """
        return self.note_generator.generate_note(
            email_data=email_data,
            classification_result=classification_result
        )
    
    def _write_note(self, email_data: Dict[str, Any], note_content: str, options: ProcessOptions) -> Optional[str]:
        """
        Write note to file system.
        
        Args:
            email_data: Email data dictionary
            note_content: Generated note content
            options: Processing options
            
        Returns:
            Path to written file (or None if dry-run)
        """
        from src.obsidian_note_creation import write_obsidian_note
        from datetime import datetime
        
        # Get vault path from settings
        vault_path = settings.get_obsidian_vault()
        email_subject = email_data.get('subject', '[No Subject]')
        
        # Get email date for timestamp
        email_date = email_data.get('date')
        timestamp = None
        if email_date:
            try:
                # Try to parse email date
                from email.utils import parsedate_to_datetime
                timestamp = parsedate_to_datetime(email_date)
            except Exception:
                # If parsing fails, use current time
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        
        # Determine if we should overwrite (force_reprocess means overwrite)
        overwrite = options.force_reprocess
        
        # Write note (safe_write_file respects dry-run mode)
        file_path = write_obsidian_note(
            note_content=note_content,
            email_subject=email_subject,
            vault_path=vault_path,
            timestamp=timestamp,
            overwrite=overwrite
        )
        
        logger.info(f"Note written to: {file_path}")
        return file_path
    
    def _set_imap_flags(self, uid: str, options: ProcessOptions) -> None:
        """
        Set IMAP flags to mark email as processed.
        
        Args:
            uid: Email UID
            options: Processing options
        """
        if is_dry_run() or options.dry_run:
            # In dry-run mode, don't set flags
            processed_tag = settings.get_imap_processed_tag()
            logger.info(f"[DRY RUN] Would set flag '{processed_tag}' for email UID: {uid}")
            return
        
        # Set processed flag
        processed_tag = settings.get_imap_processed_tag()
        self.imap_client.set_flag(uid, processed_tag)
        logger.info(f"Set flag '{processed_tag}' for email UID: {uid}")
    
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
