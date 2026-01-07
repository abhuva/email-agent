#!/usr/bin/env python3
"""
Test script to query IMAP server for emails with AIProcessed flag.

This script helps verify that flags are actually being set on the IMAP server,
even if the email client doesn't display them.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager, ConfigError, ConfigPathError, ConfigFormatError
from src.imap_connection import safe_imap_operation
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


def query_emails_with_flag(flag_name: str = 'AIProcessed', limit: int = 10):
    """
    Query IMAP server for emails with a specific flag.
    
    Args:
        flag_name: Name of the flag to search for (default: 'AIProcessed')
        limit: Maximum number of emails to return (default: 10)
    """
    print("=" * 70)
    print(f"IMAP Flag Query Test: Searching for emails with '{flag_name}' flag")
    print("=" * 70)
    print()
    
    # Load configuration
    config_path = project_root / 'config' / 'config.yaml'
    env_path = project_root / '.env'
    
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        return
    
    if not env_path.exists():
        print(f"[ERROR] Environment file not found: {env_path}")
        return
    
    try:
        config = ConfigManager(str(config_path), str(env_path))
        print(f"[OK] Configuration loaded from: {config_path}")
        print()
    except (ConfigError, ConfigPathError, ConfigFormatError) as e:
        print(f"[ERROR] Configuration error: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Unexpected error loading config: {e}")
        return
    
    # Get IMAP parameters using ConfigManager's method
    imap_params = config.imap_connection_params()
    
    if not imap_params['password']:
        print("[ERROR] IMAP_PASSWORD environment variable not set")
        return
    
    print(f"IMAP Server: {imap_params['host']}:{imap_params['port']}")
    print(f"Username: {imap_params['username']}")
    print(f"Flag to search: {flag_name}")
    print(f"Limit: {limit}")
    print()
    print("-" * 70)
    print()
    
    try:
        with safe_imap_operation(
            imap_params['host'],
            imap_params['username'],
            imap_params['password'],
            port=imap_params['port']
        ) as imap:
            # Search for emails with the flag
            # IMAP search syntax: KEYWORD "flag_name"
            search_query = f'KEYWORD "{flag_name}"'
            logger.info(f"Searching with query: {search_query}")
            
            status, data = imap.uid('SEARCH', None, search_query)
            
            if status != 'OK':
                print(f"[ERROR] IMAP SEARCH failed: {status}")
                print(f"Response data: {data}")
                return
            
            # Parse UIDs from response
            if not data or not data[0]:
                print(f"[INFO] No emails found with flag '{flag_name}'")
                return
            
            uids = data[0].split()
            total_found = len(uids)
            
            print(f"[OK] Found {total_found} email(s) with flag '{flag_name}'")
            print()
            
            if total_found == 0:
                return
            
            # Limit results
            uids_to_check = uids[:limit] if limit > 0 else uids
            print(f"Checking first {len(uids_to_check)} email(s):")
            print()
            
            # Fetch flags for each email
            for i, uid_bytes in enumerate(uids_to_check, 1):
                uid_str = uid_bytes.decode() if isinstance(uid_bytes, bytes) else str(uid_bytes)
                
                # Fetch flags
                status, data = imap.uid('FETCH', uid_str, '(FLAGS)')
                
                if status != 'OK' or not data or not data[0]:
                    print(f"  {i}. UID {uid_str}: [ERROR] Could not fetch flags")
                    continue
                
                # Parse flags
                flags_str = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
                
                # Extract flags between parentheses
                import re
                flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
                if flags_match:
                    flags = flags_match.group(1).split()
                    flags = [f.strip('\\') for f in flags if f.strip()]
                else:
                    flags = []
                
                # Fetch subject for better identification
                status_subj, data_subj = imap.uid('FETCH', uid_str, '(BODY[HEADER.FIELDS (SUBJECT)])')
                subject = "N/A"
                if status_subj == 'OK' and data_subj and data_subj[0]:
                    try:
                        header_str = data_subj[0].decode('utf-8', errors='ignore') if isinstance(data_subj[0], bytes) else str(data_subj[0])
                        # Extract subject from header
                        subject_match = re.search(r'Subject:\s*(.+?)(?:\r?\n|$)', header_str, re.IGNORECASE)
                        if subject_match:
                            subject = subject_match.group(1).strip()
                            # Remove any encoding markers
                            subject = subject.replace('=?UTF-8?B?', '').replace('=?UTF-8?Q?', '')
                    except:
                        pass
                
                # Check if flag is present
                has_flag = flag_name in flags
                flag_status = "✅ PRESENT" if has_flag else "❌ MISSING"
                
                print(f"  {i}. UID {uid_str}")
                print(f"     Subject: {subject[:60]}{'...' if len(subject) > 60 else ''}")
                print(f"     Flag '{flag_name}': {flag_status}")
                print(f"     All flags: {flags}")
                print()
            
            print("-" * 70)
            print(f"Summary: Found {total_found} email(s) with flag '{flag_name}'")
            if limit > 0 and total_found > limit:
                print(f"         (Showing first {limit}, {total_found - limit} more available)")
            print()
            
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        logger.exception("Error during IMAP query")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Query IMAP server for emails with a specific flag"
    )
    parser.add_argument(
        '--flag',
        type=str,
        default='AIProcessed',
        help='Flag name to search for (default: AIProcessed)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of emails to display (default: 10, 0 for all)'
    )
    
    args = parser.parse_args()
    
    query_emails_with_flag(flag_name=args.flag, limit=args.limit)
