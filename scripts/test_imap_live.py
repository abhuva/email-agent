"""
Live integration test for IMAP connection, email fetching, and tagging.
This script tests against a real IMAP server using credentials from .env.

Usage:
    python scripts/test_imap_live.py

Requirements:
    - Valid IMAP configuration in config/config.yaml:
      * imap.server: IMAP server hostname
      * imap.username: IMAP username
      * imap.port: IMAP port (default: 993)
    - IMAP_PASSWORD environment variable in .env file
    - At least one unprocessed email in the INBOX
    - IMAP server must support KEYWORDS capability (most modern servers do)
"""

import sys
import os
import logging
from pathlib import Path
from email import message_from_bytes

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager
from src.imap_connection import (
    connect_imap,
    search_emails_excluding_processed,
    fetch_and_parse_emails,
    safe_imap_operation,
    IMAPConnectionError,
    IMAPFetchError
)
from src.email_tagging import process_email_with_ai_tags

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imap_connection(config: ConfigManager):
    """Test 1: Basic IMAP connection"""
    logger.info("=" * 60)
    logger.info("TEST 1: IMAP Connection")
    logger.info("=" * 60)
    
    try:
        imap_host = config.yaml['imap']['server']
        imap_user = config.yaml['imap']['username']
        imap_password = os.getenv(config.yaml['imap']['password_env'])
        imap_port = config.yaml['imap'].get('port', 993)
        
        logger.info(f"Connecting to {imap_host}:{imap_port} as {imap_user}...")
        logger.info(f"Port {imap_port} - using {'SSL' if imap_port == 993 else 'STARTTLS' if imap_port == 143 else 'SSL (default)'}")
        imap = connect_imap(imap_host, imap_user, imap_password, imap_port)
        logger.info("✓ Connection successful!")
        
        # Test capability check
        status, capabilities = imap.capability()
        logger.info(f"Server capabilities: {capabilities}")
        
        if b'KEYWORDS' in capabilities:
            logger.info("✓ Server supports KEYWORDS (required for tagging)")
        else:
            logger.warning("⚠ Server does NOT support KEYWORDS - tagging will fail!")
        
        imap.logout()
        return True
    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False


def test_email_search_and_fetch(config: ConfigManager):
    """Test 2: Search and fetch emails"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Email Search and Fetch")
    logger.info("=" * 60)
    
    try:
        imap_host = config.yaml['imap']['server']
        imap_user = config.yaml['imap']['username']
        imap_password = os.getenv(config.yaml['imap']['password_env'])
        processed_tag = config.yaml.get('processed_tag', '[AI-Processed]')
        
        # Load queries from config (fallback to UNSEEN if not specified)
        queries = config.yaml.get('imap_queries', ['UNSEEN'])
        if not queries:
            queries = ['UNSEEN']
        if isinstance(queries, str):
            queries = [queries]
        
        logger.info(f"Searching with queries: {queries}")
        logger.info(f"Excluding emails tagged: {processed_tag}")
        
        imap = connect_imap(imap_host, imap_user, imap_password)
        try:
            # Use UID SEARCH to get UIDs directly (needed for tagging)
            imap.select('INBOX')
            all_uids = set()
            for q in queries:
                # Use UID SEARCH instead of regular SEARCH to get UIDs
                status, data = imap.uid('SEARCH', None, f'{q} NOT KEYWORD "{processed_tag}"')
                if status != 'OK':
                    logger.error(f"UID SEARCH failed on query: {q}")
                    continue
                if data and data[0]:
                    uids = data[0].split()
                    all_uids.update(uids)
            
            uids_list = list(all_uids)
            logger.info(f"✓ Found {len(uids_list)} unprocessed emails")
            
            if len(uids_list) == 0:
                logger.warning("⚠ No unprocessed emails found.")
                logger.info("Trying to find ANY email (ignoring [AI-Processed] tag) for testing...")
                # Try without the processed tag exclusion for testing
                all_uids = set()
                for q in queries:
                    status, data = imap.uid('SEARCH', None, q)
                    if status == 'OK' and data and data[0]:
                        uids = data[0].split()
                        all_uids.update(uids)
                
                if all_uids:
                    uids_list = list(all_uids)[:1]  # Take first email
                    logger.info(f"✓ Found {len(uids_list)} email(s) for testing (may already be processed)")
                else:
                    logger.warning("⚠ No emails found at all. Please ensure your INBOX has at least one email.")
                    return False
            
            # Fetch first email as sample using UID FETCH
            logger.info(f"\nFetching first email (UID: {uids_list[0].decode() if isinstance(uids_list[0], bytes) else uids_list[0]})...")
            status, data = imap.uid('FETCH', uids_list[0], '(RFC822)')
            if status != 'OK':
                logger.error(f"Failed to fetch email: {data}")
                return False
            
            # Parse the email
            raw_email = data[0][1]
            from src.imap_connection import decode_mime_header
            msg = message_from_bytes(raw_email)
            subject = decode_mime_header(msg.get('Subject'))
            sender = decode_mime_header(msg.get('From'))
            
            # Extract body
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == 'text/plain':
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='replace')
                        break
            else:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True)
                if isinstance(body, bytes):
                    body = body.decode(charset, errors='replace')
            
            email = {
                'id': uids_list[0],  # This is now a UID (bytes)
                'subject': subject,
                'sender': sender,
                'body': body
            }
            emails = [email]
            
            if emails:
                email = emails[0]
                logger.info(f"✓ Email fetched successfully:")
                logger.info(f"  Subject: {email.get('subject', 'N/A')[:80]}")
                logger.info(f"  From: {email.get('sender', 'N/A')[:80]}")
                logger.info(f"  Body length: {len(email.get('body', ''))} chars")
                logger.info(f"  UID: {email.get('id')}")
                return email
            else:
                logger.error("✗ Failed to parse email")
                return False
        finally:
            imap.logout()
    except Exception as e:
        logger.error(f"✗ Search/fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_safe_imap_operation(config: ConfigManager):
    """Test 3: Safe IMAP operation context manager"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Safe IMAP Operation Context Manager")
    logger.info("=" * 60)
    
    try:
        imap_host = config.yaml['imap']['server']
        imap_user = config.yaml['imap']['username']
        imap_password = os.getenv(config.yaml['imap']['password_env'])
        imap_port = config.yaml['imap'].get('port', 993)
        
        logger.info("Testing safe_imap_operation context manager...")
        
        with safe_imap_operation(imap_host, imap_user, imap_password, port=imap_port) as imap:
            # Test mailbox selection (mailbox is already selected by safe_imap_operation)
            # Just verify we can use the connection
            status, data = imap.uid('SEARCH', None, 'ALL')
            if status == 'OK':
                logger.info(f"✓ Connection verified - can perform UID operations")
            else:
                logger.error(f"✗ UID operation failed: {data}")
                return False
        
        logger.info("✓ Context manager closed connection successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Safe IMAP operation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_tagging_workflow(config: ConfigManager, test_email: dict):
    """Test 4: Complete email tagging workflow"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Email Tagging Workflow")
    logger.info("=" * 60)
    
    if not test_email:
        logger.error("✗ No test email provided")
        return False
    
    try:
        imap_host = config.yaml['imap']['server']
        imap_user = config.yaml['imap']['username']
        imap_password = os.getenv(config.yaml['imap']['password_env'])
        imap_port = config.yaml['imap'].get('port', 993)
        email_uid = test_email['id']
        
        # Simulate AI response (for testing, we'll use a mock response)
        # In real usage, this would come from OpenRouter
        mock_ai_response = "urgent"
        logger.info(f"Using mock AI response: '{mock_ai_response}'")
        
        # Prepare config for tagging
        tag_config = {
            'tag_mapping': config.yaml.get('tag_mapping', {}),
            'processed_tag': config.yaml.get('processed_tag', 'AIProcessed')
        }
        
        logger.info(f"Tagging email UID {email_uid}...")
        logger.info(f"Tag mapping: {tag_config['tag_mapping']}")
        
        try:
            with safe_imap_operation(imap_host, imap_user, imap_password, port=imap_port) as imap:
                # Get email metadata for logging
                email_metadata = {
                    'subject': test_email.get('subject', 'N/A'),
                    'sender': test_email.get('sender', 'N/A')
                }
                
                # Process email with AI tags
                result = process_email_with_ai_tags(
                    imap,
                    email_uid,
                    mock_ai_response,
                    tag_config,
                    email_metadata=email_metadata
                )
                
                logger.info(f"\nTagging result:")
                logger.info(f"  Success: {result['success']}")
                logger.info(f"  Keyword: {result['keyword']}")
                logger.info(f"  Applied tags: {result['applied_tags']}")
                logger.info(f"  Before tags: {result['before_tags']}")
                logger.info(f"  After tags: {result['after_tags']}")
                
                if result['success']:
                    logger.info("✓ Email tagged successfully!")
                    
                    # Verify AIProcessed tag was added
                    if tag_config['processed_tag'] in result['after_tags']:
                        logger.info(f"✓ {tag_config['processed_tag']} tag verified")
                    else:
                        logger.warning(f"⚠ {tag_config['processed_tag']} tag not found in after_tags")
                    
                    return True
                else:
                    logger.error("✗ Tagging failed")
                    return False
        except Exception as e:
            logger.error(f"✗ Tagging workflow failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    except Exception as e:
        logger.error(f"✗ Tagging workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all live integration tests"""
    logger.info("Starting IMAP Live Integration Tests")
    logger.info("=" * 60)
    
    # Load configuration
    try:
        config_path = project_root / 'config' / 'config.yaml'
        env_path = project_root / '.env'
        config = ConfigManager(str(config_path), str(env_path))
        logger.info(f"✓ Configuration loaded from {config_path}")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Verify required env vars
    password_env_key = config.yaml['imap'].get('password_env', 'IMAP_PASSWORD')
    if not password_env_key:
        logger.error("✗ password_env is not set in config.yaml")
        logger.error("Please set 'password_env: IMAP_PASSWORD' in config.yaml")
        return 1
    
    required_vars = [password_env_key]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"✗ Missing required environment variables: {missing}")
        logger.error(f"Please set {password_env_key} in .env file")
        return 1
    
    results = []
    
    # Test 1: Connection
    results.append(("Connection", test_imap_connection(config)))
    
    # Test 2: Search and Fetch
    test_email = test_email_search_and_fetch(config)
    results.append(("Search & Fetch", test_email is not False))
    
    # Test 3: Safe IMAP Operation
    results.append(("Safe IMAP Operation", test_safe_imap_operation(config)))
    
    # Test 4: Tagging (only if we have a test email)
    if test_email:
        results.append(("Tagging Workflow", test_email_tagging_workflow(config, test_email)))
    else:
        logger.warning("\n⚠ Skipping tagging test - no test email available")
        results.append(("Tagging Workflow", None))
    
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
        logger.info("✓ All tests passed!")
        return 0
    else:
        logger.warning("⚠ Some tests failed - review logs above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
