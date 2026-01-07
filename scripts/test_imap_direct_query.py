#!/usr/bin/env python3
"""
Direct IMAP query test - check if 2026 emails exist and can be fetched.

This script directly queries the IMAP server to see if 2026 emails exist,
regardless of tags or other filters.
"""

import os
import sys
from pathlib import Path
from email.utils import parsedate_to_datetime
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager, ConfigError, ConfigPathError, ConfigFormatError
from src.imap_connection import safe_imap_operation, fetch_and_parse_emails

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)

logger = logging.getLogger(__name__)


def test_direct_imap_queries():
    """
    Test direct IMAP queries to find 2026 emails.
    """
    logger.info("=" * 80)
    logger.info("Direct IMAP Query Test - Finding 2026 Emails")
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
    
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  IMAP Server: {imap_params['host']}:{imap_params['port']}")
    logger.info(f"  Username: {imap_params['username']}")
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
            # Test 1: Get ALL emails (no filters)
            logger.info("TEST 1: Query ALL emails (no filters)")
            logger.info("")
            
            status, data = imap.uid('SEARCH', None, 'ALL')
            if status != 'OK':
                logger.error(f"UID SEARCH failed: {status} {data}")
            else:
                all_uids = data[0].split() if data[0] else []
                logger.info(f"Found {len(all_uids)} total emails in mailbox")
                if all_uids:
                    first_uid = all_uids[0].decode() if isinstance(all_uids[0], bytes) else str(all_uids[0])
                    last_uid = all_uids[-1].decode() if isinstance(all_uids[-1], bytes) else str(all_uids[-1])
                    logger.info(f"  First UID: {first_uid}")
                    logger.info(f"  Last UID: {last_uid}")
            logger.info("")
            
            # Test 2: Query emails from 2026 using SENTSINCE
            logger.info("TEST 2: Query emails sent since 2026-01-01")
            logger.info("")
            
            status, data = imap.uid('SEARCH', None, 'SENTSINCE', '01-Jan-2026')
            if status != 'OK':
                logger.error(f"UID SEARCH SENTSINCE failed: {status} {data}")
            else:
                uids_2026 = data[0].split() if data[0] else []
                logger.info(f"Found {len(uids_2026)} emails sent since 2026-01-01")
                if uids_2026:
                    logger.info(f"  UIDs: {[uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids_2026[:10]]}")
                    if len(uids_2026) > 10:
                        logger.info(f"  ... and {len(uids_2026) - 10} more")
            logger.info("")
            
            # Test 3: Query emails received since 2026-01-01
            logger.info("TEST 3: Query emails received since 2026-01-01")
            logger.info("")
            
            status, data = imap.uid('SEARCH', None, 'SINCE', '01-Jan-2026')
            if status != 'OK':
                logger.error(f"UID SEARCH SINCE failed: {status} {data}")
            else:
                uids_received_2026 = data[0].split() if data[0] else []
                logger.info(f"Found {len(uids_received_2026)} emails received since 2026-01-01")
                if uids_received_2026:
                    logger.info(f"  UIDs: {[uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids_received_2026[:10]]}")
                    if len(uids_received_2026) > 10:
                        logger.info(f"  ... and {len(uids_received_2026) - 10} more")
            logger.info("")
            
            # Test 4: Fetch the highest UIDs (newest emails) and check their dates
            logger.info("TEST 4: Check dates of highest UIDs (newest emails)")
            logger.info("")
            
            if all_uids and len(all_uids) > 0:
                # Get the last 20 UIDs (should be newest)
                newest_uids = all_uids[-20:] if len(all_uids) >= 20 else all_uids
                logger.info(f"Fetching last {len(newest_uids)} UIDs to check dates...")
                logger.info("")
                
                # Fetch these emails
                emails = fetch_and_parse_emails(imap, newest_uids)
                
                logger.info(f"Fetched {len(emails)} emails")
                logger.info("")
                logger.info("Dates of newest emails:")
                logger.info("")
                
                emails_2026 = []
                for email in emails:
                    uid_str = email.get('id')
                    if isinstance(uid_str, bytes):
                        uid_str = uid_str.decode()
                    
                    date_str = email.get('date', 'N/A')
                    subject = email.get('subject', 'N/A')[:60]
                    
                    # Try to parse date
                    year = 'Unknown'
                    if date_str and date_str != 'N/A':
                        try:
                            email_dt = parsedate_to_datetime(date_str)
                            year = str(email_dt.year)
                            if email_dt.year >= 2026:
                                emails_2026.append((uid_str, date_str, subject))
                        except:
                            pass
                    
                    logger.info(f"  UID {uid_str}: Year={year}, Date={date_str}, Subject={subject}")
                
                logger.info("")
                if emails_2026:
                    logger.info(f"Found {len(emails_2026)} emails from 2026 in the newest batch:")
                    logger.info("")
                    for uid, date, subject in emails_2026:
                        logger.info(f"  UID {uid}: {date} - {subject}")
                else:
                    logger.warning("No 2026 emails found in the newest 20 emails!")
            logger.info("")
            
            # Test 5: Check if 2026 emails have processed tags
            logger.info("TEST 5: Check if 2026 emails have processed tags")
            logger.info("")
            
            if uids_2026 or uids_received_2026:
                # Use whichever found emails
                test_uids = uids_2026 if uids_2026 else uids_received_2026
                test_uids = test_uids[:10]  # Limit to first 10
                
                logger.info(f"Checking flags for {len(test_uids)} 2026 emails...")
                logger.info("")
                
                for uid_bytes in test_uids:
                    uid_str = uid_bytes.decode() if isinstance(uid_bytes, bytes) else str(uid_bytes)
                    
                    # Fetch flags
                    status, data = imap.uid('FETCH', uid_str, '(FLAGS)')
                    if status == 'OK' and data and data[0]:
                        flags_str = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
                        import re
                        flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
                        if flags_match:
                            flags = flags_match.group(1).split()
                            flags = [f.strip('\\') for f in flags if f.strip()]
                            
                            has_processed = any(tag in flags for tag in ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed'])
                            logger.info(f"  UID {uid_str}: flags={flags}, has_processed_tag={has_processed}")
                        else:
                            logger.warning(f"  UID {uid_str}: Could not parse flags")
                    else:
                        logger.warning(f"  UID {uid_str}: Could not fetch flags")
            else:
                logger.warning("No 2026 emails found to check flags")
            
            # Test 6: Test the actual query we use in the agent
            logger.info("TEST 6: Test the actual agent query")
            logger.info("")
            
            final_query = (
                f'(ALL '
                f'NOT KEYWORD "AIProcessed" '
                f'NOT KEYWORD "ObsidianNoteCreated" '
                f'NOT KEYWORD "NoteCreationFailed")'
            )
            
            logger.info(f"Query: {final_query}")
            logger.info("")
            
            status, data = imap.uid('SEARCH', None, final_query)
            if status != 'OK':
                logger.error(f"UID SEARCH failed: {status} {data}")
            else:
                uids_agent_query = data[0].split() if data[0] else []
                logger.info(f"Found {len(uids_agent_query)} emails matching agent query")
                if uids_agent_query:
                    first_uid = uids_agent_query[0].decode() if isinstance(uids_agent_query[0], bytes) else str(uids_agent_query[0])
                    last_uid = uids_agent_query[-1].decode() if isinstance(uids_agent_query[-1], bytes) else str(uids_agent_query[-1])
                    logger.info(f"  First UID: {first_uid}")
                    logger.info(f"  Last UID: {last_uid}")
                    
                    # Check if 2026 emails are in the results
                    uids_str = [uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids_agent_query]
                    uids_2026_in_results = [uid for uid in ['422', '423', '424', '425', '426', '427', '428', '429', '430', '431'] if uid in uids_str]
                    
                    if uids_2026_in_results:
                        logger.info(f"  ✓ Found {len(uids_2026_in_results)} 2026 emails in results: {uids_2026_in_results}")
                    else:
                        logger.warning(f"  ✗ NO 2026 emails found in results!")
                        logger.warning(f"  This is the problem - the query is excluding them somehow")
                    
                    # Show last 10 UIDs
                    if len(uids_agent_query) > 10:
                        last_10 = [uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids_agent_query[-10:]]
                        logger.info(f"  Last 10 UIDs: {last_10}")
            logger.info("")
            
            logger.info("=" * 80)
            logger.info("Test complete")
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)


if __name__ == '__main__':
    test_direct_imap_queries()
