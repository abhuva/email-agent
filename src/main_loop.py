"""
Main processing loop for email agent.
Orchestrates email fetching, AI processing, and tagging.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
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
        
        while True:
            try:
                # Check if we've hit the limit
                if max_emails_to_process and total_processed_this_run >= max_emails_to_process:
                    logger.info(f"Reached max_emails limit ({max_emails_to_process}). Stopping.")
                    break
                
                # Fetch unprocessed emails
                logger.info("Fetching unprocessed emails...")
                emails = fetch_emails(
                    host=imap_params['host'],
                    user=imap_params['username'],
                    password=imap_params['password'],
                    user_query=user_query,
                    processed_tag=config.processed_tag
                )
                
                # Track total available (before limiting)
                total_available_in_batch = len(emails)
                analytics['total_available'] += total_available_in_batch
                logger.info(f"Fetched {total_available_in_batch} unprocessed emails")
                
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
                
                analytics['total_fetched'] += len(emails)
                
                # Process each email
                for email in emails:
                    email_uid = email.get('id')
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
                                    try:
                                        # Get summary result if available
                                        summary_result = email.get('summary')
                                        
                                        # Create the note
                                        note_result = create_obsidian_note_for_email(
                                            email,
                                            config,
                                            summary_result
                                        )
                                        
                                        # Tag email based on result
                                        with safe_imap_operation(
                                            imap_params['host'],
                                            imap_params['username'],
                                            imap_params['password'],
                                            port=imap_params.get('port', 993)
                                        ) as imap:
                                            if note_result['success']:
                                                # Success - tag with Obsidian-Note-Created
                                                tag_email_note_created(
                                                    imap,
                                                    email_uid,
                                                    note_result.get('note_path')
                                                )
                                                logger.info(f"Successfully created Obsidian note for email UID {email_uid}: {note_result.get('note_path')}")
                                            else:
                                                # Failure - tag with Note-Creation-Failed
                                                tag_email_note_failed(
                                                    imap,
                                                    email_uid,
                                                    note_result.get('error')
                                                )
                                                logger.error(f"Failed to create Obsidian note for email UID {email_uid}: {note_result.get('error')}")
                                        
                                    except Exception as e:
                                        # Graceful degradation - tag as failed and continue
                                        logger.error(f"Error creating Obsidian note for email UID {email_uid}: {e}", exc_info=True)
                                        try:
                                            with safe_imap_operation(
                                                imap_params['host'],
                                                imap_params['username'],
                                                imap_params['password'],
                                                port=imap_params.get('port', 993)
                                            ) as imap:
                                                tag_email_note_failed(imap, email_uid, f"unexpected_error: {str(e)}")
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
