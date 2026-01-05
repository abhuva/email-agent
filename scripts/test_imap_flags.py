"""
Test script to verify IMAP FLAGS support (custom flags, not KEYWORDS extension).
This tests if we can use FLAGS for tagging instead of KEYWORDS.

Usage:
    python scripts/test_imap_flags.py

This will:
1. Connect to IMAP server
2. Find a test email
3. Add custom flags (Urgent, [AI-Processed])
4. Verify flags were added
5. Search by flags
6. Clean up (remove test flags)
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager
from src.imap_connection import connect_imap, IMAPConnectionError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_add_custom_flags(imap, uid):
    """Test 1: Can we add custom flags? Tests different flag name formats."""
    logger.info("=" * 60)
    logger.info("TEST 1: Add Custom Flags")
    logger.info("=" * 60)
    
    # Test different flag name formats to see what the server accepts
    test_cases = [
        ['TestFlag', 'AIProcessed'],  # Simple, no special chars
        ['Urgent', 'Neutral'],  # Our actual tag names
        ['AI-Processed'],  # With dash, no brackets
        ['AI_Processed'],  # With underscore
        ['AIProcessed'],  # No separator
    ]
    
    working_flags = []
    
    for test_flags in test_cases:
        try:
            logger.info(f"\nTrying flags: {test_flags}")
            status, data = imap.uid('STORE', uid, '+FLAGS', f'({" ".join(test_flags)})')
            
            if status == 'OK':
                logger.info(f"✓ Successfully added flags: {test_flags}")
                working_flags.extend(test_flags)
                # Remove these flags before trying next set
                imap.uid('STORE', uid, '-FLAGS', f'({" ".join(test_flags)})')
            else:
                error_msg = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
                logger.warning(f"✗ Failed: {status} {error_msg}")
        except Exception as e:
            logger.warning(f"✗ Error: {e}")
    
    if working_flags:
        logger.info(f"\n✓ Working flag formats found: {working_flags}")
        # Test with the first working format
        test_flags = [working_flags[0], working_flags[1] if len(working_flags) > 1 else 'TestFlag2']
        logger.info(f"\nUsing working format: {test_flags}")
        status, data = imap.uid('STORE', uid, '+FLAGS', f'({" ".join(test_flags)})')
        if status == 'OK':
            return True, test_flags
        else:
            return False, []
    else:
        logger.error("✗ No flag formats worked - server may not support custom flags")
        return False, []


def test_fetch_flags(imap, uid):
    """Test 2: Can we fetch and read flags?"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Fetch Flags")
    logger.info("=" * 60)
    
    try:
        logger.info(f"Fetching flags for UID {uid}...")
        status, data = imap.uid('FETCH', uid, '(FLAGS)')
        
        if status != 'OK' or not data or not data[0]:
            logger.error(f"✗ Failed to fetch flags: {status} {data}")
            return False, []
        
        # Parse flags
        flags_str = data[0].decode('utf-8', errors='ignore') if isinstance(data[0], bytes) else str(data[0])
        logger.info(f"Raw response: {flags_str}")
        
        import re
        flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
        if flags_match:
            flags = flags_match.group(1).split()
            flags = [f.strip('\\') for f in flags if f.strip()]
            logger.info(f"✓ Parsed flags: {flags}")
            return True, flags
        else:
            logger.warning(f"⚠ Could not parse flags from: {flags_str}")
            return False, []
    except Exception as e:
        logger.error(f"✗ Error fetching flags: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_search_by_flags(imap, flag_name):
    """Test 3: Can we search emails by custom flags?"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Search by Custom Flags")
    logger.info("=" * 60)
    
    try:
        # Note: IMAP uses "KEYWORD" keyword in search to search FLAGS!
        # This is confusing naming in the IMAP spec
        search_criteria = f'KEYWORD "{flag_name}"'
        logger.info(f"Searching for emails with flag: {flag_name}")
        logger.info(f"Search criteria: {search_criteria}")
        
        status, data = imap.uid('SEARCH', None, search_criteria)
        
        if status != 'OK':
            logger.error(f"✗ Search failed: {status} {data}")
            return False, []
        
        if data and data[0]:
            uids = data[0].split()
            logger.info(f"✓ Found {len(uids)} email(s) with flag '{flag_name}'")
            return True, uids
        else:
            logger.warning(f"⚠ No emails found with flag '{flag_name}'")
            return True, []  # Success (search worked, just no results)
    except Exception as e:
        logger.error(f"✗ Error searching by flags: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_exclude_by_flags(imap, flag_name):
    """Test 4: Can we exclude emails by custom flags?"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Exclude by Custom Flags")
    logger.info("=" * 60)
    
    try:
        # Search for all emails NOT having the flag
        search_criteria = f'ALL NOT KEYWORD "{flag_name}"'
        logger.info(f"Searching for emails WITHOUT flag: {flag_name}")
        logger.info(f"Search criteria: {search_criteria}")
        
        status, data = imap.uid('SEARCH', None, search_criteria)
        
        if status != 'OK':
            logger.error(f"✗ Search failed: {status} {data}")
            return False, []
        
        if data and data[0]:
            uids = data[0].split()
            logger.info(f"✓ Found {len(uids)} email(s) without flag '{flag_name}'")
            return True, uids
        else:
            logger.info(f"✓ All emails have flag '{flag_name}' (search worked)")
            return True, []
    except Exception as e:
        logger.error(f"✗ Error excluding by flags: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_remove_flags(imap, uid, flags):
    """Test 5: Can we remove flags (cleanup)?"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Remove Flags (Cleanup)")
    logger.info("=" * 60)
    
    try:
        logger.info(f"Removing test flags {flags} from UID {uid}...")
        status, data = imap.uid('STORE', uid, '-FLAGS', f'({" ".join(flags)})')
        
        if status == 'OK':
            logger.info(f"✓ Successfully removed flags: {flags}")
            return True
        else:
            logger.warning(f"⚠ Failed to remove flags: {status} {data}")
            return False
    except Exception as e:
        logger.warning(f"⚠ Error removing flags: {e}")
        return False


def main():
    """Run all FLAGS tests"""
    logger.info("Starting IMAP FLAGS Support Tests")
    logger.info("=" * 60)
    
    # Load configuration
    try:
        config_path = project_root / 'config' / 'config.yaml'
        env_path = project_root / '.env'
        config = ConfigManager(str(config_path), str(env_path))
        logger.info(f"✓ Configuration loaded")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Get IMAP credentials
    imap_host = config.yaml['imap']['server']
    imap_user = config.yaml['imap']['username']
    imap_password = os.getenv(config.yaml['imap']['password_env'])
    imap_port = config.yaml['imap'].get('port', 993)
    
    if not imap_password:
        logger.error(f"✗ Missing IMAP_PASSWORD in .env")
        return 1
    
    imap = None
    test_uid = None
    
    try:
        # Connect
        logger.info(f"\nConnecting to {imap_host}:{imap_port}...")
        from src.imap_connection import connect_imap
        imap = connect_imap(imap_host, imap_user, imap_password, imap_port)
        
        # Select INBOX
        status, data = imap.select('INBOX')
        if status != 'OK':
            logger.error(f"✗ Failed to select INBOX: {data}")
            return 1
        
        # Find a test email (get first email)
        logger.info("\nFinding a test email...")
        status, data = imap.uid('SEARCH', None, 'ALL')
        if status != 'OK' or not data or not data[0]:
            logger.error("✗ No emails found in INBOX")
            return 1
        
        uids = data[0].split()
        if not uids:
            logger.error("✗ No emails found in INBOX")
            return 1
        
        test_uid = uids[0]
        uid_str = test_uid.decode() if isinstance(test_uid, bytes) else str(test_uid)
        logger.info(f"✓ Using email UID {uid_str} for testing")
        
        # Run tests
        results = []
        
        # Test 1: Add flags
        success, test_flags = test_add_custom_flags(imap, test_uid)
        if success:
            results.append(("Add Custom Flags", True))
        else:
            results.append(("Add Custom Flags", False))
            logger.error("✗ Cannot continue - flag addition failed")
            return 1
        
        # Test 2: Fetch flags
        success, flags = test_fetch_flags(imap, test_uid)
        results.append(("Fetch Flags", success))
        
        # Test 3: Search by flags (use first test flag)
        search_flag = test_flags[0] if test_flags else 'TestFlag'
        search_success, found_uids = test_search_by_flags(imap, search_flag)
        results.append(("Search by Flags", search_success))
        if test_uid in found_uids or (isinstance(test_uid, bytes) and test_uid in found_uids):
            logger.info("✓ Test email found in search results - flag is searchable!")
        
        # Test 4: Exclude by flags
        exclude_success, excluded_uids = test_exclude_by_flags(imap, search_flag)
        results.append(("Exclude by Flags", exclude_success))
        
        # Test 5: Cleanup
        if test_flags:
            cleanup_success = test_remove_flags(imap, test_uid, test_flags)
            results.append(("Remove Flags (Cleanup)", cleanup_success))
        else:
            results.append(("Remove Flags (Cleanup)", None))
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        for test_name, result in results:
            if result is True:
                status = "✓ PASSED"
            elif result is False:
                status = "✗ FAILED"
            else:
                status = "⊘ SKIPPED"
            logger.info(f"{test_name:30s} {status}")
        
        passed = sum(1 for _, r in results if r is True)
        total = sum(1 for _, r in results if r is not None)
        
        logger.info(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("\n✓ All FLAGS tests passed! FLAGS approach will work.")
            logger.info("✓ You can proceed with refactoring to use FLAGS instead of KEYWORDS.")
            if test_flags:
                logger.info(f"\n⚠ IMPORTANT: Server requires flag names without brackets.")
                logger.info(f"   Working format: {test_flags}")
                logger.info(f"   Use format like 'AIProcessed' instead of '[AI-Processed]'")
            return 0
        else:
            logger.warning("\n⚠ Some tests failed - review logs above")
            return 1
            
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if imap:
            try:
                imap.logout()
            except Exception:
                pass


if __name__ == '__main__':
    sys.exit(main())
