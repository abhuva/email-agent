"""
Diagnostic script to check what IMAP flags are actually stored and how they appear.
This helps debug why Thunderbird might not show the flags.

Usage:
    python scripts/check_imap_flags.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager
from src.imap_connection import connect_imap

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_email_flags(imap, uid):
    """Check all flag information for a specific email"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Checking flags for UID {uid}")
    logger.info(f"{'='*60}")
    
    # Method 1: UID FETCH with FLAGS
    logger.info("\n1. UID FETCH (FLAGS):")
    status, data = imap.uid('FETCH', uid, '(FLAGS)')
    if status == 'OK' and data:
        logger.info(f"   Response: {data[0]}")
        # Parse flags
        import re
        flags_str = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
        flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
        if flags_match:
            flags = flags_match.group(1).split()
            flags = [f.strip('\\') for f in flags if f.strip()]
            logger.info(f"   Parsed flags: {flags}")
            logger.info(f"   System flags (with \\): {[f for f in flags_match.group(1).split() if f.startswith('\\')]}")
            logger.info(f"   Custom flags (no \\): {[f for f in flags_match.group(1).split() if not f.startswith('\\')]}")
    
    # Method 2: UID FETCH with all metadata
    logger.info("\n2. UID FETCH (ALL metadata):")
    status, data = imap.uid('FETCH', uid, '(FLAGS INTERNALDATE ENVELOPE)')
    if status == 'OK' and data:
        logger.info(f"   Response: {data[0][:200]}...")  # First 200 chars
    
    # Method 3: Check if server supports KEYWORDS extension
    logger.info("\n3. Server capabilities:")
    status, capabilities = imap.capability()
    if status == 'OK':
        caps_str = b' '.join(capabilities).decode('utf-8', errors='ignore')
        logger.info(f"   Capabilities: {caps_str[:200]}...")
        if 'KEYWORDS' in caps_str:
            logger.info("   ✓ Server supports KEYWORDS extension")
        else:
            logger.info("   ✗ Server does NOT support KEYWORDS extension")
    
    # Method 4: Try to search by the flag
    logger.info("\n4. Testing search by custom flag:")
    test_flag = 'AIProcessed'
    status, data = imap.uid('SEARCH', None, f'KEYWORD "{test_flag}"')
    if status == 'OK' and data and data[0]:
        uids = data[0].split()
        logger.info(f"   Found {len(uids)} email(s) with flag '{test_flag}'")
        if uid in uids or (isinstance(uid, bytes) and uid in uids):
            logger.info(f"   ✓ Email UID {uid} found in search results")
        else:
            logger.warning(f"   ⚠ Email UID {uid} NOT found in search results")
    else:
        logger.warning(f"   ⚠ Search failed or returned no results")


def main():
    """Check flags on a recently tagged email"""
    logger.info("IMAP Flags Diagnostic Tool")
    logger.info("="*60)
    
    # Load configuration
    try:
        config_path = project_root / 'config' / 'config.yaml'
        env_path = project_root / '.env'
        config = ConfigManager(str(config_path), str(env_path))
        logger.info("✓ Configuration loaded")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Get IMAP credentials
    imap_host = config.yaml['imap']['server']
    imap_user = config.yaml['imap']['username']
    imap_password = os.getenv(config.yaml['imap']['password_env'])
    imap_port = config.yaml['imap'].get('port', 993)
    
    if not imap_password:
        logger.error("✗ Missing IMAP_PASSWORD in .env")
        return 1
    
    imap = None
    try:
        # Connect
        logger.info(f"\nConnecting to {imap_host}:{imap_port}...")
        imap = connect_imap(imap_host, imap_user, imap_password, imap_port)
        
        # Select INBOX
        status, data = imap.select('INBOX')
        if status != 'OK':
            logger.error(f"✗ Failed to select INBOX: {data}")
            return 1
        
        # Find emails with AIProcessed flag (the one we just tagged)
        logger.info("\nSearching for emails with 'AIProcessed' flag...")
        status, data = imap.uid('SEARCH', None, 'KEYWORD "AIProcessed"')
        if status != 'OK' or not data or not data[0]:
            logger.warning("⚠ No emails found with AIProcessed flag")
            logger.info("Trying to find any recently tagged email...")
            # Try to find emails with Urgent flag
            status, data = imap.uid('SEARCH', None, 'KEYWORD "Urgent"')
        
        if status == 'OK' and data and data[0]:
            uids = data[0].split()
            if uids:
                # Check the first one
                test_uid = uids[0]
                uid_str = test_uid.decode() if isinstance(test_uid, bytes) else str(test_uid)
                logger.info(f"✓ Found email UID {uid_str} with custom flags")
                check_email_flags(imap, test_uid)
            else:
                logger.warning("⚠ No emails found with custom flags")
        else:
            logger.warning("⚠ Could not find any tagged emails")
            logger.info("\nTrying to check the most recent email...")
            # Get the most recent email
            status, data = imap.uid('SEARCH', None, 'ALL')
            if status == 'OK' and data and data[0]:
                uids = data[0].split()
                if uids:
                    test_uid = uids[-1]  # Last one (most recent)
                    uid_str = test_uid.decode() if isinstance(test_uid, bytes) else str(test_uid)
                    logger.info(f"Checking most recent email UID {uid_str}...")
                    check_email_flags(imap, test_uid)
        
        logger.info("\n" + "="*60)
        logger.info("Thunderbird Compatibility Notes:")
        logger.info("="*60)
        logger.info("1. Thunderbird's 'Schlagworte' (Keywords) may only show:")
        logger.info("   - System flags (\\Seen, \\Flagged, etc.)")
        logger.info("   - KEYWORDS extension tags (if server supports it)")
        logger.info("   - Custom flags might not appear in the Keywords view")
        logger.info("\n2. To see custom flags in Thunderbird:")
        logger.info("   - Check View → Sort By → Flagged")
        logger.info("   - Use IMAP search: Edit → Find → Search Messages")
        logger.info("   - Custom flags might appear in message properties")
        logger.info("\n3. Alternative: Use Thunderbird's Tags feature")
        logger.info("   - Thunderbird has its own tagging system")
        logger.info("   - These are stored separately from IMAP flags")
        logger.info("   - Not synced with IMAP flags")
        
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if imap:
            try:
                imap.logout()
            except Exception:
                pass
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
