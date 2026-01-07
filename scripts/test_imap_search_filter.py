#!/usr/bin/env python3
"""
Test script to debug IMAP search and filtering logic.

This script executes the same search and filtering logic as the main agent,
but only logs the results to a separate log file for debugging.
"""

import os
import sys
from pathlib import Path
from datetime import date
from email.utils import parsedate_to_datetime
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager, ConfigError, ConfigPathError, ConfigFormatError
from src.imap_connection import safe_imap_operation, search_emails_excluding_processed, fetch_and_parse_emails

# Set up logging to a separate file
log_file = project_root / 'logs' / 'imap_search_test.log'
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)


def test_imap_search_and_filter():
    """
    Test IMAP search and filtering logic, logging all results.
    """
    logger.info("=" * 80)
    logger.info("IMAP Search and Filter Test")
    logger.info("=" * 80)
    logger.info("")
    
    # Load configuration
    config_path = project_root / 'config' / 'config.yaml'
    env_path = project_root / '.env'
    
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return
    
    if not env_path.exists():
        logger.error(f"Environment file not found: {env_path}")
        return
    
    try:
        config = ConfigManager(str(config_path), str(env_path))
        logger.info(f"Configuration loaded from: {config_path}")
    except (ConfigError, ConfigPathError, ConfigFormatError) as e:
        logger.error(f"Configuration error: {e}")
        return
    except Exception as e:
        logger.error(f"Unexpected error loading config: {e}")
        return
    
    # Get IMAP parameters
    imap_params = config.imap_connection_params()
    user_query = config.get_imap_query()
    
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  IMAP Server: {imap_params['host']}:{imap_params['port']}")
    logger.info(f"  Username: {imap_params['username']}")
    logger.info(f"  User Query: {user_query}")
    logger.info(f"  Processed Tag: {config.processed_tag}")
    logger.info("")
    logger.info("-" * 80)
    logger.info("")
    
    try:
        with safe_imap_operation(
            imap_params['host'],
            imap_params['username'],
            imap_params['password'],
            port=imap_params['port']
        ) as imap:
            # Step 1: Execute search
            logger.info("STEP 1: Executing IMAP search...")
            logger.info("")
            
            # First, let's check what the final query looks like
            from src.imap_connection import search_emails_excluding_processed
            import imaplib
            
            # Manually construct the query to log it
            imap.select('INBOX')
            final_query = (
                f'({user_query} '
                f'NOT KEYWORD "{config.processed_tag}" '
                f'NOT KEYWORD "ObsidianNoteCreated" '
                f'NOT KEYWORD "NoteCreationFailed")'
            )
            logger.info(f"Final IMAP query: {final_query}")
            logger.info("")
            
            # Also test what we get WITHOUT the processed tag exclusions
            logger.info("Testing query WITHOUT processed tag exclusions:")
            status, data = imap.search(None, user_query)
            if status == 'OK':
                all_ids = data[0].split() if data[0] else []
                logger.info(f"  Query '{user_query}' found {len(all_ids)} emails")
                if all_ids:
                    # Show first and last few UIDs
                    logger.info(f"  First 5 UIDs: {[uid.decode() if isinstance(uid, bytes) else uid for uid in all_ids[:5]]}")
                    logger.info(f"  Last 5 UIDs: {[uid.decode() if isinstance(uid, bytes) else uid for uid in all_ids[-5:]]}")
            logger.info("")
            
            ids = search_emails_excluding_processed(
                imap,
                user_query,
                processed_tag=config.processed_tag,
                obsidian_note_created_tag='ObsidianNoteCreated',
                note_creation_failed_tag='NoteCreationFailed'
            )
            
            logger.info(f"Found {len(ids)} email UIDs from IMAP search (after excluding processed)")
            if ids:
                # Show first and last few UIDs
                logger.info(f"  First 5 UIDs: {[uid.decode() if isinstance(uid, bytes) else uid for uid in ids[:5]]}")
                logger.info(f"  Last 5 UIDs: {[uid.decode() if isinstance(uid, bytes) else uid for uid in ids[-5:]]}")
            logger.info("")
            
            if not ids:
                logger.warning("No emails found by IMAP search!")
                return
            
            # Step 2: Fetch and parse emails
            logger.info("STEP 2: Fetching and parsing emails...")
            logger.info("")
            
            emails = fetch_and_parse_emails(imap, ids)
            
            logger.info(f"Fetched and parsed {len(emails)} emails")
            logger.info("")
            
            # Step 3: Log all fetched emails
            logger.info("STEP 3: All emails found by IMAP (before code-level filtering):")
            logger.info("")
            
            for i, email in enumerate(emails, 1):
                uid_str = email.get('id')
                if isinstance(uid_str, bytes):
                    uid_str = uid_str.decode()
                
                subject = email.get('subject', 'N/A')
                sender = email.get('sender', 'N/A')
                date_str = email.get('date', 'N/A')
                
                logger.info(f"  {i}. UID {uid_str}")
                logger.info(f"     Subject: {subject[:80]}")
                logger.info(f"     From: {sender[:80]}")
                logger.info(f"     Date: {date_str}")
                logger.info("")
            
            # Step 4: Apply code-level date filtering
            logger.info("STEP 4: Applying code-level date filtering...")
            logger.info("")
            
            today = date.today()
            logger.info(f"Today's date: {today}")
            logger.info("")
            
            filtered_emails = []
            for email in emails:
                email_date_str = email.get('date')
                uid_str = email.get('id')
                if isinstance(uid_str, bytes):
                    uid_str = uid_str.decode()
                
                subject = email.get('subject', 'N/A')[:60]
                
                if email_date_str:
                    try:
                        # Parse the email's Date header
                        email_dt = parsedate_to_datetime(email_date_str)
                        email_date = email_dt.date()
                        
                        # Only include emails sent today or later
                        if email_date >= today:
                            filtered_emails.append(email)
                            logger.info(f"  ✓ INCLUDED - UID {uid_str}: sent date {email_date} >= today {today}")
                            logger.info(f"    Subject: {subject}")
                        else:
                            logger.info(f"  ✗ EXCLUDED - UID {uid_str}: sent date {email_date} < today {today}")
                            logger.info(f"    Subject: {subject}")
                    except (ValueError, TypeError) as e:
                        # If date parsing fails, include the email
                        logger.warning(f"  ⚠ INCLUDED (date parse failed) - UID {uid_str}: {e}")
                        logger.warning(f"    Subject: {subject}")
                        logger.warning(f"    Date string: {email_date_str}")
                        filtered_emails.append(email)
                else:
                    # If no date, include the email
                    logger.warning(f"  ⚠ INCLUDED (no date header) - UID {uid_str}")
                    logger.warning(f"    Subject: {subject}")
                    filtered_emails.append(email)
            
            logger.info("")
            logger.info("-" * 80)
            logger.info("")
            logger.info("SUMMARY:")
            logger.info(f"  Emails found by IMAP search: {len(emails)}")
            logger.info(f"  Emails after date filtering: {len(filtered_emails)}")
            logger.info(f"  Emails filtered out: {len(emails) - len(filtered_emails)}")
            logger.info("")
            
            if filtered_emails:
                logger.info("Final list of emails to process:")
                logger.info("")
                for i, email in enumerate(filtered_emails, 1):
                    uid_str = email.get('id')
                    if isinstance(uid_str, bytes):
                        uid_str = uid_str.decode()
                    
                    subject = email.get('subject', 'N/A')
                    sender = email.get('sender', 'N/A')
                    date_str = email.get('date', 'N/A')
                    
                    logger.info(f"  {i}. UID {uid_str}")
                    logger.info(f"     Subject: {subject[:80]}")
                    logger.info(f"     From: {sender[:80]}")
                    logger.info(f"     Date: {date_str}")
                    logger.info("")
            else:
                logger.warning("No emails remain after filtering!")
            
            logger.info("=" * 80)
            logger.info(f"Test complete. Full log saved to: {log_file}")
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)


if __name__ == '__main__':
    test_imap_search_and_filter()
