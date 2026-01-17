"""
Dry-run processing information output.

This module provides functions to output detailed processing information
during dry-run mode, including classification scores, decision logic results,
generated note content, file paths, and IMAP flags.
"""
from typing import Dict, Any, Optional
from src.dry_run_output import DryRunOutput
from src.dry_run import is_dry_run


def output_email_processing_info(
    email_data: Dict[str, Any],
    classification_result: Optional[Any] = None,
    note_content: Optional[str] = None,
    file_path: Optional[str] = None,
    flags_to_set: Optional[list] = None
) -> None:
    """
    Output comprehensive processing information for an email in dry-run mode.
    
    This function formats and displays:
    - Email metadata (UID, subject, from, date)
    - Classification scores with threshold explanations
    - Decision logic results
    - Generated note content preview
    - File path where note would be written
    - IMAP flags that would be set
    
    Args:
        email_data: Email data dictionary with uid, subject, from, date, etc.
        classification_result: ClassificationResult object (optional)
        note_content: Generated note content (optional)
        file_path: Path where note would be written (optional)
        flags_to_set: List of IMAP flags that would be set (optional)
    """
    if not is_dry_run():
        return  # Only output in dry-run mode
    
    output = DryRunOutput()
    
    # Email Information Section
    output.header("Email Processing Information", level=2)
    output.section("Email Details")
    output.detail("UID", email_data.get('uid', 'unknown'))
    output.detail("Subject", email_data.get('subject', '[No Subject]'))
    output.detail("From", email_data.get('from', '[Unknown]'))
    output.detail("Date", email_data.get('date', '[Unknown]'))
    output.end_section()
    
    # Classification Results Section
    if classification_result:
        output.section("Classification Results")
        
        # Get scores
        importance_score = getattr(classification_result, 'importance_score', -1)
        spam_score = getattr(classification_result, 'spam_score', -1)
        is_important = getattr(classification_result, 'is_important', False)
        is_spam = getattr(classification_result, 'is_spam', False)
        
        # Display scores with thresholds
        # Use default thresholds (can be made configurable if needed)
        importance_threshold = 8
        spam_threshold = 5
        
        output.detail("Importance Score", f"{importance_score}/10 (threshold: {importance_threshold})")
        if importance_score >= importance_threshold:
            output.success(f"Email is IMPORTANT (score >= threshold)")
        else:
            output.info(f"Email is not important (score < threshold)")
        
        output.detail("Spam Score", f"{spam_score}/10 (threshold: {spam_threshold})")
        if spam_score >= spam_threshold:
            output.warning(f"Email is SPAM (score >= threshold)")
        else:
            output.success(f"Email is not spam (score < threshold)")
        
        # Decision logic results
        output.section("Decision Logic")
        if is_important:
            output.success("Decision: Email marked as important")
        if is_spam:
            output.warning("Decision: Email marked as spam")
        
        # Status
        status = getattr(classification_result, 'status', 'unknown')
        if hasattr(status, 'value'):
            status = status.value
        output.detail("Processing Status", str(status))
        
        output.end_section()
        output.end_section()
    
    # Note Generation Section
    if note_content:
        output.section("Generated Note")
        output.detail("Content Length", f"{len(note_content)} characters")
        
        # Show preview (first 500 chars)
        preview_length = 500
        if len(note_content) > preview_length:
            preview = note_content[:preview_length] + "\n... (truncated)"
        else:
            preview = note_content
        
        output.code_block(preview, "markdown")
        output.end_section()
    
    # File Operations Section
    if file_path:
        output.section("File Operations")
        output.warning(f"Would write note to: {file_path}")
        output.detail("File Path", file_path)
        output.end_section()
    
    # IMAP Operations Section
    if flags_to_set:
        output.section("IMAP Flag Operations")
        for flag in flags_to_set:
            output.warning(f"Would set IMAP flag: {flag}")
        output.detail("Total Flags", len(flags_to_set))
        output.end_section()
    
    output._print("", prefix="")


def output_processing_summary(
    stats: Dict[str, Any]
) -> None:
    """
    Output summary statistics at the end of processing.
    
    Args:
        stats: Dictionary of statistic name -> value
            Expected keys: total_processed, successful, failed, notes_created, etc.
    """
    if not is_dry_run():
        return  # Only output in dry-run mode
    
    output = DryRunOutput()
    output.summary(stats)
