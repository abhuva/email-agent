"""
Main processing loop for email agent.
Orchestrates email fetching, AI processing, and tagging.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import sys
import os
# Fix import path for when running as script
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.config import ConfigManager
from src.imap_connection import fetch_emails, safe_imap_operation, IMAPFetchError
from src.openrouter_client import OpenRouterClient, send_email_prompt_for_keywords, extract_keywords_from_openrouter_response, OpenRouterAPIError
from src.email_tagging import process_email_with_ai_tags
from src.email_truncation import truncate_email_body, get_max_truncation_length
from src.summarization import check_summarization_required
from src.email_summarization import generate_email_summary
from src.obsidian_note_creation import (
    create_obsidian_note_for_email,
    tag_email_note_created,
    tag_email_note_failed,
    OBSIDIAN_NOTE_CREATED_TAG,
    NOTE_CREATION_FAILED_TAG
)
from src.changelog import update_changelog

logger = logging.getLogger(__name__)

# Flag name for emails that failed AI processing
AI_PROCESSING_FAILED_FLAG = 'AIProcessingFailed'


def process_email_with_ai(
    email: Dict[str, Any],
    client: OpenRouterClient,
    config: ConfigManager,
    max_retries: int = 3
) -> Optional[str]:
    """
    Process a single email through AI API with error handling.
    
    Args:
        email: Email dict with 'body', 'subject', 'sender', 'id', etc.
        client: OpenRouterClient instance
        config: ConfigManager instance
        max_retries: Maximum retry attempts for API calls
    
    Returns:
        AI response string on success, None on failure
    """
    email_uid = email.get('id')
    email_body = email.get('body', '')
    email_subject = email.get('subject', 'N/A')
    
    if not email_body:
        logger.warning(f"Email UID {email_uid} has no body content, skipping AI processing")
        return None
    
    # Truncate email body if needed
    max_chars = get_max_truncation_length(config)
    content_type = email.get('content_type', 'text/plain')
    truncation_result = truncate_email_body(email_body, content_type, max_chars, config)
    truncated_body = truncation_result['truncatedBody']
    
    if truncation_result['isTruncated']:
        logger.debug(f"Email UID {email_uid} body truncated from {len(email_body)} to {len(truncated_body)} chars")
    
    # Attempt AI processing with retries
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            logger.debug(f"Processing email UID {email_uid} with AI (attempt {attempt}/{max_retries})")
            
            # Get model from config
            model = config.openrouter_model
            
            # Send to AI
            response = send_email_prompt_for_keywords(
                truncated_body,
                client,
                max_chars=max_chars,
                model=model,
                max_tokens=32
            )
            
            # Extract keywords from response
            keywords = extract_keywords_from_openrouter_response(response)
            if keywords:
                # Join keywords as comma-separated string (AI response format)
                ai_response = ', '.join(keywords)
                logger.info(f"AI processing successful for UID {email_uid}: {ai_response}")
                return ai_response
            else:
                logger.warning(f"No keywords extracted from AI response for UID {email_uid}")
                return None
                
        except OpenRouterAPIError as e:
            logger.error(f"OpenRouter API error for UID {email_uid} (attempt {attempt}): {e}")
            if attempt < max_retries:
                # Exponential backoff
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"All retry attempts failed for UID {email_uid}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error processing email UID {email_uid}: {e}", exc_info=True)
            return None
    
    return None


def run_email_processing_loop(
    config: ConfigManager,
    single_run: bool = True,
    max_emails: Optional[int] = None
) -> Dict[str, Any]:
    """
    Main processing loop: fetch emails, process with AI, tag, and log results.
    
    Args:
        config: ConfigManager instance
        single_run: If True, process once and exit. If False, loop continuously.
        max_emails: Maximum emails to process (overrides config.max_emails_per_run)
    
    Returns:
        Dict with processing results and analytics
    """
    # Initialize analytics counters
    analytics = {
        'run_id': datetime.now().isoformat(),
        'total_fetched': 0,
        'total_available': 0,  # Total emails available (before limit)
        'successfully_processed': 0,
        'failed': 0,
        'tag_breakdown': {},
        'errors': []
    }
    
    # Get max emails from config or parameter
    max_emails_to_process = max_emails or config.max_emails_per_run
    
    try:
        # Initialize OpenRouter client
        openrouter_params = config.openrouter_params()
        client = OpenRouterClient(
            api_key=openrouter_params['api_key'],
            api_url=openrouter_params['api_url']
        )
        
        # Get IMAP connection params
        imap_params = config.imap_connection_params()
        
        # Get IMAP query from config (V2: single query string)
        user_query = config.get_imap_query()
        logger.info(f"Using IMAP query: {user_query}")
        
        logger.info(f"Starting email processing loop (max_emails={max_emails_to_process}, single_run={single_run})")
        
        # Track total processed across all batches
        total_processed_this_run = 0
        
        # V2: Track processed emails for changelog (Task 10)
        processed_emails_for_changelog = []
        
        while True:
            try:
                # Check if we've hit the limit
                if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                    logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping.")
                    break
                
                # Fetch unprocessed emails
                logger.info("Fetching unprocessed emails...")
                logger.debug(f"Using IMAP query: {user_query}")
                emails = fetch_emails(
                    host=imap_params['host'],
                    user=imap_params['username'],
                    password=imap_params['password'],
                    user_query=user_query,
                    processed_tag=config.processed_tag
                )
                
                logger.info(f"IMAP returned {len(emails)} emails before code-level filtering")
                if emails:
                    logger.debug("Emails found by IMAP:")
                    for email in emails:
                        uid_str = email.get('id')
                        if isinstance(uid_str, bytes):
                            uid_str = uid_str.decode()
                        logger.debug(f"  - UID {uid_str}: subject='{email.get('subject', 'N/A')[:60]}', date='{email.get('date', 'N/A')}'")
                
                # Optional: Filter by sent date in code
                # DISABLED FOR DEBUGGING: Remove date filter to see all emails
                # TODO: Re-enable with proper date logic (maybe last N days, or received date)
                # from datetime import date, timedelta
                # from email.utils import parsedate_to_datetime
                # 
                # original_count = len(emails)
                # today = date.today()
                # # Option: Use last 7 days instead of just today
                # # cutoff_date = today - timedelta(days=7)
                # cutoff_date = today
                # 
                # filtered_emails = []
                # for email in emails:
                #     email_date_str = email.get('date')
                #     uid_str = email.get('id')
                #     if isinstance(uid_str, bytes):
                #         uid_str = uid_str.decode()
                #     
                #     if email_date_str:
                #         try:
                #             email_dt = parsedate_to_datetime(email_date_str)
                #             email_date = email_dt.date()
                #             
                #             if email_date >= cutoff_date:
                #                 filtered_emails.append(email)
                #                 logger.info(f"Including email UID {uid_str} - sent date: {email_date}, subject: {email.get('subject', 'N/A')[:50]}")
                #             else:
                #                 logger.info(f"Excluding email UID {uid_str} - sent date: {email_date} (before {cutoff_date}), subject: {email.get('subject', 'N/A')[:50]}")
                #         except (ValueError, TypeError) as e:
                #             logger.warning(f"Could not parse date '{email_date_str}' for email UID {uid_str}, including anyway: {e}")
                #             filtered_emails.append(email)
                #     else:
                #         logger.warning(f"No date header for email UID {uid_str}, including anyway")
                #         filtered_emails.append(email)
                # 
                # emails = filtered_emails
                # if len(emails) < original_count:
                #     logger.info(f"Filtered {original_count - len(emails)} emails by sent date (before {cutoff_date})")
                
                # TEMPORARY: No date filtering - process all emails found by IMAP
                logger.info(f"Date filtering DISABLED for debugging - processing all {len(emails)} emails found by IMAP")
                
                # CRITICAL: Sort emails by date (newest first) so we process the most recent emails
                # This ensures that when using --limit, we get the newest emails, not the oldest
                from email.utils import parsedate_to_datetime
                
                def get_email_date_for_sorting(email_dict):
                    """Extract date for sorting, returning a timezone-aware datetime or None."""
                    date_str = email_dict.get('date')
                    if not date_str:
                        return None
                    try:
                        dt = parsedate_to_datetime(date_str)
                        # Ensure timezone-aware (if naive, assume UTC)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except (ValueError, TypeError):
                        return None
                
                # Sort by date (newest first), emails without dates go to the end
                # Use a consistent timezone-aware datetime for comparison
                min_date = datetime.min.replace(tzinfo=timezone.utc)
                emails.sort(key=lambda e: get_email_date_for_sorting(e) or min_date, reverse=True)
                logger.info(f"Sorted {len(emails)} emails by date (newest first)")
                
                # Track total available (after date filtering)
                total_available_in_batch = len(emails)
                analytics['total_available'] += total_available_in_batch
                logger.info(f"Fetched {total_available_in_batch} unprocessed emails (after date filtering)")
                
                if not emails:
                    logger.info("No unprocessed emails found")
                    if single_run:
                        break
                    else:
                        logger.info("Sleeping 30s before next batch...")
                        time.sleep(30)
                        continue
                
                # Limit to remaining quota (max_emails_to_process - total_processed_this_run)
                remaining_quota = None
                if max_emails_to_process:
                    remaining_quota = max_emails_to_process - total_processed_this_run
                    if remaining_quota <= 0:
                        logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping.")
                        break
                    if len(emails) > remaining_quota:
                        emails = emails[:remaining_quota]
                        logger.info(f"Limited to {remaining_quota} emails (remaining quota of {max_emails_to_process} total)")
                        # Log which email will be processed (newest)
                        if emails:
                            first_email = emails[0]
                            uid_str = first_email.get('id')
                            if isinstance(uid_str, bytes):
                                uid_str = uid_str.decode()
                            logger.info(f"Processing newest email: UID {uid_str}, date: {first_email.get('date', 'N/A')}")
                
                analytics['total_fetched'] += len(emails)
                
                # Process each email
                for email in emails:
                    email_uid = email.get('id')
                    # Log UID for debugging - convert bytes to string for readability
                    uid_str = email_uid.decode() if isinstance(email_uid, bytes) else str(email_uid)
                    logger.debug(f"Processing email with UID: {uid_str} (type: {type(email_uid).__name__}), subject: {email.get('subject', 'N/A')[:50]}")
                    try:
                        # Process with AI
                        ai_response = process_email_with_ai(email, client, config)
                        
                        if ai_response:
                            # Tag email based on AI response
                            with safe_imap_operation(
                                imap_params['host'],
                                imap_params['username'],
                                imap_params['password'],
                                port=imap_params.get('port', 993)
                            ) as imap:
                                # Prepare config dict for tagging
                                tag_config = {
                                    'tag_mapping': config.tag_mapping,
                                    'processed_tag': config.processed_tag
                                }
                                
                                email_metadata = {
                                    'subject': email.get('subject', 'N/A'),
                                    'sender': email.get('sender', 'N/A')
                                }
                                
                                result = process_email_with_ai_tags(
                                    imap,
                                    email_uid,
                                    ai_response,
                                    tag_config,
                                    email_metadata
                                )
                                
                                if result['success']:
                                    analytics['successfully_processed'] += 1
                                    total_processed_this_run += 1
                                    # Track tag breakdown
                                    keyword = result.get('keyword', 'unknown')
                                    if keyword not in analytics['tag_breakdown']:
                                        analytics['tag_breakdown'][keyword] = 0
                                    analytics['tag_breakdown'][keyword] += 1
                                    logger.info(f"Successfully processed and tagged email UID {email_uid} ({total_processed_this_run}/{max_emails_to_process if max_emails_to_process else '∞'})")
                                    
                                    # V2: Check if summarization is required (Task 6)
                                    # Get applied tags (excluding processed_tag for summarization check)
                                    applied_tags = result.get('applied_tags', [])
                                    # Filter out processed_tag and AIProcessingFailed for summarization check
                                    content_tags = [tag for tag in applied_tags 
                                                   if tag not in [config.processed_tag, AI_PROCESSING_FAILED_FLAG]]
                                    
                                    # Create email dict with tags for summarization check
                                    email_with_tags = {**email, 'tags': content_tags}
                                    
                                    # Check if summarization is required
                                    try:
                                        summarization_result = check_summarization_required(email_with_tags, config)
                                        
                                        # Store summarization result in email dict for later use (Task 8)
                                        email['summarization'] = summarization_result
                                        
                                        if summarization_result['summarize']:
                                            logger.info(f"Summarization required for email UID {email_uid} (tags: {content_tags})")
                                            
                                            # V2: Generate summary using LLM (Task 7)
                                            try:
                                                summary_result = generate_email_summary(
                                                    email,
                                                    client,
                                                    config,
                                                    summarization_result
                                                )
                                                
                                                # Store summary result in email dict for note creation (Task 8)
                                                email['summary'] = summary_result
                                                
                                                if summary_result['success']:
                                                    logger.info(f"Successfully generated summary for email UID {email_uid}")
                                                else:
                                                    logger.warning(f"Summary generation failed for email UID {email_uid}: {summary_result.get('error', 'unknown')}")
                                            except Exception as e:
                                                # Graceful degradation - log but continue
                                                logger.error(f"Error generating summary for email UID {email_uid}: {e}", exc_info=True)
                                                email['summary'] = {
                                                    'success': False,
                                                    'summary': '',
                                                    'action_items': [],
                                                    'priority': 'medium',
                                                    'error': f'summary_generation_error: {str(e)}'
                                                }
                                        else:
                                            reason = summarization_result.get('reason', 'unknown')
                                            logger.debug(f"Summarization not required for email UID {email_uid}: {reason}")
                                    except Exception as e:
                                        # Graceful degradation - never let summarization check break the pipeline
                                        logger.warning(f"Error checking summarization requirement for email UID {email_uid}: {e}", exc_info=True)
                                        email['summarization'] = {
                                            'summarize': False,
                                            'prompt': None,
                                            'reason': f'check_error: {str(e)}'
                                        }
                                    
                                    # V2: Create Obsidian note (Task 9)
                                    # CRITICAL: Log email details to verify UID/content consistency
                                    uid_str = email_uid.decode() if isinstance(email_uid, bytes) else str(email_uid)
                                    email_subject = email.get('subject', 'N/A')
                                    email_sender = email.get('sender', 'N/A')
                                    logger.info(f"[V2] Starting Obsidian note creation for email UID {uid_str}")
                                    logger.info(f"[V2] Email details - Subject: {email_subject[:60]}, From: {email_sender[:50]}")
                                    logger.info(f"[V2] Config has obsidian_vault_path: {hasattr(config, 'obsidian_vault_path') and config.obsidian_vault_path is not None}")
                                    try:
                                        # Get summary result if available
                                        summary_result = email.get('summary')
                                        logger.debug(f"Summary result available: {summary_result is not None}")
                                        
                                        # Create the note
                                        logger.info(f"Creating Obsidian note for email UID {uid_str} (Subject: {email_subject[:50]})")
                                        note_result = create_obsidian_note_for_email(
                                            email,
                                            config,
                                            summary_result
                                        )
                                        
                                        logger.debug(f"Note creation result: success={note_result.get('success')}, path={note_result.get('note_path')}, error={note_result.get('error')}")
                                        
                                        # Tag email based on result
                                        logger.debug(f"Opening IMAP connection for tagging email UID {email_uid}")
                                        with safe_imap_operation(
                                            imap_params['host'],
                                            imap_params['username'],
                                            imap_params['password'],
                                            port=imap_params.get('port', 993)
                                        ) as imap:
                                            if note_result['success']:
                                                # Success - tag with ObsidianNoteCreated
                                                logger.info(f"Tagging email UID {email_uid} with ObsidianNoteCreated")
                                                tag_success = tag_email_note_created(
                                                    imap,
                                                    email_uid,
                                                    note_result.get('note_path')
                                                )
                                                if tag_success:
                                                    logger.info(f"Successfully created Obsidian note for email UID {email_uid}: {note_result.get('note_path')}")
                                                    
                                                    # V2: Collect email data for changelog (Task 10)
                                                    note_path = note_result.get('note_path', '')
                                                    # Extract just the filename from the full path
                                                    filename = Path(note_path).name if note_path else ''
                                                    
                                                    email_changelog_data = {
                                                        'email_account': imap_params['username'],
                                                        'subject': email.get('subject', 'N/A'),
                                                        'from_addr': email.get('sender', 'N/A'),
                                                        'filename': filename
                                                    }
                                                    processed_emails_for_changelog.append(email_changelog_data)
                                                    logger.debug(f"Added email to changelog queue: {email_changelog_data}")
                                                else:
                                                    logger.warning(f"Note created but tagging failed for email UID {email_uid}")
                                            else:
                                                # Failure - tag with NoteCreationFailed
                                                logger.warning(f"Note creation failed for email UID {email_uid}: {note_result.get('error')}")
                                                tag_success = tag_email_note_failed(
                                                    imap,
                                                    email_uid,
                                                    note_result.get('error')
                                                )
                                                if tag_success:
                                                    logger.info(f"Tagged email UID {email_uid} with NoteCreationFailed")
                                                else:
                                                    logger.warning(f"Note creation failed and tagging also failed for email UID {email_uid}")
                                        
                                    except Exception as e:
                                        # Graceful degradation - tag as failed and continue
                                        logger.error(f"Error creating Obsidian note for email UID {email_uid}: {e}", exc_info=True)
                                        try:
                                            logger.debug(f"Attempting to tag email UID {email_uid} as failed after exception")
                                            with safe_imap_operation(
                                                imap_params['host'],
                                                imap_params['username'],
                                                imap_params['password'],
                                                port=imap_params.get('port', 993)
                                            ) as imap:
                                                tag_success = tag_email_note_failed(imap, email_uid, f"unexpected_error: {str(e)}")
                                                if tag_success:
                                                    logger.info(f"Tagged email UID {email_uid} with NoteCreationFailed after exception")
                                                else:
                                                    logger.warning(f"Failed to tag email UID {email_uid} after note creation exception")
                                        except Exception as tag_error:
                                            logger.error(f"Failed to tag email UID {email_uid} after note creation error: {tag_error}", exc_info=True)
                                    
                                    # Check if we've hit the limit after this email
                                    if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                                        logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping after this batch.")
                                        break
                                else:
                                    analytics['failed'] += 1
                                    total_processed_this_run += 1  # Count failed attempts too
                                    logger.error(f"Failed to tag email UID {email_uid}")
                                    
                                    # Check if we've hit the limit after this email
                                    if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                                        logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping after this batch.")
                                        break
                        else:
                            # AI processing failed - mark with failure flag
                            analytics['failed'] += 1
                            total_processed_this_run += 1  # Count failed attempts too
                            logger.warning(f"AI processing failed for UID {email_uid}, marking with {AI_PROCESSING_FAILED_FLAG}")
                            
                            # Mark email with failure flag
                            with safe_imap_operation(
                                imap_params['host'],
                                imap_params['username'],
                                imap_params['password'],
                                port=imap_params.get('port', 993)
                            ) as imap:
                                from src.imap_connection import add_tags_to_email
                                add_tags_to_email(imap, email_uid, [AI_PROCESSING_FAILED_FLAG, config.processed_tag])
                            
                            # Check if we've hit the limit after this email
                            if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                                logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping after this batch.")
                                break
                            
                    except Exception as e:
                        # Isolate per-email errors - don't stop the loop
                        analytics['failed'] += 1
                        total_processed_this_run += 1  # Count errors too
                        error_msg = f"Error processing email UID {email_uid}: {e}"
                        analytics['errors'].append(error_msg)
                        logger.error(error_msg, exc_info=True)
                        
                        # Check if we've hit the limit after this error
                        if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                            logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping after this batch.")
                            break
                        continue
                
                # V2: Update changelog after processing batch (Task 10)
                if processed_emails_for_changelog and config.changelog_path:
                    try:
                        logger.info(f"Updating changelog with {len(processed_emails_for_changelog)} processed email(s)")
                        changelog_success = update_changelog(
                            path=config.changelog_path,
                            email_list=processed_emails_for_changelog
                        )
                        if changelog_success:
                            logger.info(f"Successfully updated changelog: {config.changelog_path}")
                            # Clear the list after successful update
                            processed_emails_for_changelog = []
                        else:
                            logger.warning(f"Failed to update changelog: {config.changelog_path}")
                            # Keep emails in list for retry on next batch
                    except Exception as e:
                        # Graceful degradation - log error but continue execution
                        logger.error(f"Error updating changelog: {e}", exc_info=True)
                        # Continue execution even if changelog fails
                elif processed_emails_for_changelog and not config.changelog_path:
                    logger.debug("Changelog path not configured, skipping changelog update")
                    # Clear the list since we won't be updating changelog
                    processed_emails_for_changelog = []
                
                # Check if we've hit the limit after processing batch
                if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                    logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping.")
                    break
                
                # If single run, exit after processing batch
                if single_run:
                    break
                else:
                    logger.info("Sleeping 30s before next batch...")
                    time.sleep(30)
                    
            except IMAPFetchError as e:
                logger.error(f"IMAP fetch error: {e}")
                analytics['errors'].append(f"IMAP fetch error: {e}")
                if single_run:
                    break
                else:
                    logger.info("Sleeping 30s before retry...")
                    time.sleep(30)
            except KeyboardInterrupt:
                logger.info("Received KeyboardInterrupt, stopping processing loop")
                break
            except Exception as e:
                logger.error(f"Unexpected error in processing loop: {e}", exc_info=True)
                analytics['errors'].append(f"Unexpected error: {e}")
                if single_run:
                    break
                else:
                    logger.info("Sleeping 30s before retry...")
                    time.sleep(30)
        
    except Exception as e:
        logger.error(f"Fatal error in processing loop: {e}", exc_info=True)
        analytics['errors'].append(f"Fatal error: {e}")
    
    # V2: Final changelog update for any remaining emails (Task 10)
    # This handles the case where the loop exits before processing a batch
    if processed_emails_for_changelog and config.changelog_path:
        try:
            logger.info(f"Performing final changelog update with {len(processed_emails_for_changelog)} email(s)")
            changelog_success = update_changelog(
                path=config.changelog_path,
                email_list=processed_emails_for_changelog
            )
            if changelog_success:
                logger.info(f"Successfully updated changelog: {config.changelog_path}")
            else:
                logger.warning(f"Failed to update changelog: {config.changelog_path}")
        except Exception as e:
            logger.error(f"Error in final changelog update: {e}", exc_info=True)
    
    # Generate and log analytics summary
    analytics_summary = generate_analytics_summary(analytics)
    logger.info(f"Processing complete. Summary: {analytics_summary}")
    
    # Return analytics with summary merged in
    analytics['summary'] = analytics_summary
    # Also add summary fields directly to analytics for backward compatibility
    analytics.update(analytics_summary)
    
    return analytics


def generate_analytics_summary(analytics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate analytics summary from processing results.
    
    Args:
        analytics: Dict with counters and results from processing loop
    
    Returns:
        Dict with computed percentages and formatted summary
    """
    total = analytics['total_fetched']
    total_available = analytics.get('total_available', total)  # Total available before limit
    successful = analytics['successfully_processed']
    failed = analytics['failed']
    
    # Calculate remaining unprocessed (PDD AC 7)
    remaining_unprocessed = max(0, total_available - total)
    
    summary = {
        'run_id': analytics['run_id'],
        'total': total,
        'total_available': total_available,
        'remaining_unprocessed': remaining_unprocessed,
        'successfully_processed': successful,
        'failed': failed,
        'success_rate': round((successful / total * 100) if total > 0 else 0, 2),
        'tags': analytics['tag_breakdown'],
        'error_count': len(analytics['errors'])
    }
    
    return summary
