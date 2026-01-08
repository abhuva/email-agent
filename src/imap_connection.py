"""
IMAP connection and email fetching utilities.

This module provides:
- IMAP connection management with SSL/TLS support
- Email search and fetching with configurable query exclusions
- Email parsing and flag/tag management
- Safe IMAP operations with retry logic
"""

import imaplib
import os
import logging
import yaml
from typing import List, Dict, Any, Callable, Optional
import email
from email.header import decode_header
import time
from contextlib import contextmanager

class IMAPConnectionError(Exception):
    """
    Raised when IMAP connection or authentication fails.
    
    This exception is raised for:
    - Connection failures (network, SSL/TLS errors)
    - Authentication failures (invalid credentials)
    - Mailbox selection failures
    """
    pass


class IMAPFetchError(Exception):
    """
    Raised when IMAP email fetching or operations fail.
    
    This exception is raised for:
    - Search query failures
    - Email fetch failures
    - Flag/tagging operation failures
    - Retry exhaustion after multiple attempts
    """
    pass


def connect_imap(host: str, user: str, password: str, port: int = 993):
    """
    Connect to IMAP server with SSL (port 993) or STARTTLS (port 143).
    Automatically detects connection type based on port.
    """
    try:
        if port == 993:
            # Use SSL from the start (IMAPS)
            imap = imaplib.IMAP4_SSL(host, port)
        elif port == 143:
            # Use STARTTLS (upgrade plain connection to TLS)
            imap = imaplib.IMAP4(host, port)
            imap.starttls()
        else:
            # Default to SSL for other ports (assume SSL)
            imap = imaplib.IMAP4_SSL(host, port)
        
        imap.login(user, password)
        logging.info(f"IMAP connection established with {host}:{port} as {user}.")
        return imap
    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP login failed: {e}")
        raise IMAPConnectionError(f"IMAP login failed: {e}")
    except Exception as e:
        logging.error(f"IMAP connection failed: {e}")
        raise IMAPConnectionError(f"IMAP connection failed: {e}")

def load_imap_queries(config_path: str = "config/config.yaml"):
    """
    Load IMAP search queries from configuration file.
    
    .. deprecated:: V2
        This function is deprecated. Use `ConfigManager.get_imap_query()` instead.
        This function is kept for backward compatibility and test support only.
        It will be removed in a future version.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        List of IMAP search query strings
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If queries are invalid (but not if missing - defaults to ['UNSEEN'])
        
    Note:
        Defaults to ['UNSEEN'] if neither 'imap_queries' nor 'imap_query' is found.
        This fetches unread emails, which is the most common use case.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    queries = config.get('imap_queries')
    if not queries:
        query = config.get('imap_query')
        if query:
            queries = [query]
        else:
            # Default to UNSEEN (unread emails) if not specified
            logging.info("No 'imap_queries' or 'imap_query' found in config. Using default: ['UNSEEN']")
            queries = ['UNSEEN']
    if not isinstance(queries, list):
        raise ValueError("'imap_queries' must be a list of IMAP search strings.")
    for q in queries:
        if not isinstance(q, str) or len(q.strip()) == 0:
            raise ValueError(f"IMAP query must be a non-empty string: {q}")
    logging.info(f"Loaded IMAP queries: {queries}")
    return queries

def build_imap_query_with_exclusions(
    user_query: str,
    exclude_tags: List[str],
    disable_idempotency: bool = False
) -> str:
    """
    Build IMAP query combining user query with tag exclusions.
    
    This function creates an IMAP query that combines the user's base query
    with NOT KEYWORD clauses to exclude emails with specific tags.
    
    Args:
        user_query: User-defined IMAP query (e.g., 'UNSEEN')
        exclude_tags: List of tags to exclude (e.g., ['AIProcessed', 'ObsidianNoteCreated'])
        disable_idempotency: If True, return only user_query (no exclusions)
    
    Returns:
        Combined IMAP query string
        
    Example:
        >>> build_imap_query_with_exclusions('UNSEEN', ['AIProcessed', 'ObsidianNoteCreated'])
        '(UNSEEN NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated")'
        
        >>> build_imap_query_with_exclusions('UNSEEN', [], disable_idempotency=True)
        'UNSEEN'
    """
    if disable_idempotency:
        return user_query
    
    if not exclude_tags:
        return user_query
    
    # Build NOT KEYWORD clauses for each tag
    # IMAP uses "KEYWORD" in SEARCH to search for FLAGS (confusing naming in IMAP spec)
    exclusion_clauses = ' '.join(f'NOT KEYWORD "{tag}"' for tag in exclude_tags)
    
    # Combine: ({user_query} NOT KEYWORD "tag1" NOT KEYWORD "tag2" ...)
    final_query = f'({user_query} {exclusion_clauses})'
    
    return final_query


def search_emails_excluding_processed(
    imap, 
    user_query: str, 
    exclude_tags: Optional[List[str]] = None,
    disable_idempotency: bool = False
) -> List[bytes]:
    """
    Search emails using user query combined with idempotency checks.
    
    The user query is combined with NOT conditions to exclude emails that have
    already been processed. Uses configurable exclude_tags list instead of hardcoded tags.
    
    Args:
        imap: IMAP connection object
        user_query: User-defined IMAP query string from config
        exclude_tags: List of tags to exclude (defaults to standard idempotency tags for backward compatibility)
        disable_idempotency: If True, skip idempotency checks and return only user_query results
    
    Returns:
        List of email UIDs (bytes)
        
    Note:
        For backward compatibility, if exclude_tags is None, defaults to:
        ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']
    """
    # Default exclude tags for backward compatibility
    if exclude_tags is None:
        from src.obsidian_note_creation import OBSIDIAN_NOTE_CREATED_TAG, NOTE_CREATION_FAILED_TAG
        exclude_tags = [
            'AIProcessed',
            OBSIDIAN_NOTE_CREATED_TAG,  # 'ObsidianNoteCreated'
            NOTE_CREATION_FAILED_TAG     # 'NoteCreationFailed'
        ]
    
    try:
        imap.select('INBOX')
        
        # Build query using new builder function
        final_query = build_imap_query_with_exclusions(
            user_query,
            exclude_tags,
            disable_idempotency
        )
        
        logging.debug(f"Executing IMAP query: {final_query}")
        
        # Use UID SEARCH instead of SEARCH to get UIDs directly
        # SEARCH returns sequence numbers which can change, UID SEARCH returns stable UIDs
        # Also, some IMAP servers may limit SEARCH results, UID SEARCH is more reliable
        # Note: IMAP uses "KEYWORD" keyword in SEARCH to search FLAGS
        # This is confusing naming in the IMAP spec, but it's correct
        # We're searching for custom FLAGS, not the KEYWORDS extension
        status, data = imap.uid('SEARCH', None, final_query)
        
        if status != 'OK':
            logging.error(f"IMAP search failed on query: {final_query}")
            raise IMAPConnectionError(f"IMAP search failed: {status} {data}")
        
        # Parse UIDs from response
        # data[0] is a bytes object containing space-separated UIDs like: b'1 2 3 420 421 422'
        ids = data[0].split() if data[0] else []
        
        # Log search results summary
        if ids:
            first_uid = ids[0].decode() if isinstance(ids[0], bytes) else str(ids[0])
            last_uid = ids[-1].decode() if isinstance(ids[-1], bytes) else str(ids[-1])
            logging.info(f"Found {len(ids)} unprocessed emails matching query (UID range: {first_uid} to {last_uid})")
            
            # Log sample UIDs for debugging (only in debug mode to avoid log bloat)
            if len(ids) > 10 and logging.getLogger().isEnabledFor(logging.DEBUG):
                first_few = [uid.decode() if isinstance(uid, bytes) else str(uid) for uid in ids[:5]]
                last_few = [uid.decode() if isinstance(uid, bytes) else str(uid) for uid in ids[-5:]]
                logging.debug(f"Sample UIDs - First 5: {first_few}, Last 5: {last_few}")
        else:
            logging.info(f"Found 0 unprocessed emails matching query.")
        
        return ids
        
    except Exception as e:
        logging.error(f"IMAP search failed: {e}")
        raise IMAPConnectionError(f"IMAP search failed: {e}")

def decode_mime_header(header) -> str:
    if not header:
        return ''
    parts = decode_header(header)
    decoded = ''
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded += part.decode(enc or 'utf-8', errors='replace')
        else:
            decoded += str(part)
    return decoded

def fetch_and_parse_emails(imap, msg_ids: List[bytes]) -> List[Dict[str, Any]]:
    """
    Fetch and parse emails using UID FETCH (not sequence number FETCH).
    
    Args:
        imap: Active IMAP connection
        msg_ids: List of email UIDs (bytes) from UID SEARCH
    
    Returns:
        List of parsed email dictionaries with 'id' set to the UID
    """
    parsed = []
    for msg_id in msg_ids:
        # Use UID FETCH, not FETCH, because msg_ids are UIDs, not sequence numbers
        # Convert bytes to string for UID FETCH
        uid_str = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
        
        typ, data = imap.uid('FETCH', uid_str, '(RFC822)')
        if typ != 'OK':
            logging.error(f'Failed to fetch UID {uid_str}: {data}')
            continue
        
        if not data or not data[0] or len(data[0]) < 2:
            logging.error(f'Invalid FETCH response for UID {uid_str}: {data}')
            continue
        
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_header(msg.get('Subject'))
        sender = decode_mime_header(msg.get('From'))
        date = decode_mime_header(msg.get('Date'))
        
        # Log the Date header for debugging
        date_header_raw = msg.get('Date', 'N/A')
        logging.debug(f"Email UID {uid_str} - Date header (raw): {date_header_raw}, Date header (decoded): {date}")
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = part.get('Content-Disposition')
                if ctype == 'text/plain' and disp != 'attachment':
                    charset = part.get_content_charset() or 'utf-8'
                    body = part.get_payload(decode=True).decode(charset, errors='replace')
                    break
        else:
            charset = msg.get_content_charset() or 'utf-8'
            body = msg.get_payload(decode=True)
            if isinstance(body, bytes):
                body = body.decode(charset, errors='replace')
            elif not isinstance(body, str):
                body = ''
        
        # Store UID as bytes to maintain consistency
        # This ensures email['id'] is the UID we can use for UID STORE
        parsed.append({
            'id': msg_id,  # Keep as bytes (UID) for consistency
            'subject': subject,
            'sender': sender,
            'body': body,
            'date': date,
        })
        logging.debug(f"Fetched email UID {uid_str} (subject: {subject[:50]})")
    logging.info(f"Parsed {len(parsed)} emails.")
    return parsed

def fetch_emails(
    host: str, user: str, password: str,
    user_query: str,
    exclude_tags: Optional[List[str]] = None,
    disable_idempotency: bool = False,
    max_retries: int = 3,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    Fetch emails from IMAP server using the provided query.
    
    This function handles connection, search, and parsing of emails.
    It automatically excludes emails that have already been processed
    based on the exclude_tags list (defaults to standard idempotency tags).
    
    Args:
        host: IMAP server hostname
        user: IMAP username (email address)
        password: IMAP password
        user_query: User-defined IMAP query string (e.g., 'UNSEEN')
        exclude_tags: List of tags to exclude (defaults to standard idempotency tags)
        disable_idempotency: If True, skip idempotency checks (NOT RECOMMENDED)
        max_retries: Maximum retry attempts for connection failures
        timeout: Connection timeout in seconds
    
    Returns:
        List of email dictionaries with keys: id, subject, sender, body, etc.
        
    Raises:
        IMAPFetchError: If fetching fails after all retries
        
    Note:
        For backward compatibility, if exclude_tags is None, defaults to:
        ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']
    """
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            logging.info(f"Connecting to IMAP server (attempt {attempt})...")
            imap = connect_imap(host, user, password)
            # Set global timeout for IMAP socket
            imap.sock.settimeout(timeout)
            try:
                ids = search_emails_excluding_processed(
                    imap, 
                    user_query, 
                    exclude_tags=exclude_tags,
                    disable_idempotency=disable_idempotency
                )
                emails = fetch_and_parse_emails(imap, ids)
                logging.info(f"Fetched and parsed {len(emails)} emails.")
                
                return emails
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass
        except IMAPConnectionError as e:
            logging.error(f"Attempt {attempt} - IMAP connection/search failed: {e}")
            if attempt < max_retries:
                sleep_secs = 2 ** attempt
                logging.info(f"Retrying in {sleep_secs}s...")
                time.sleep(sleep_secs)
            else:
                logging.error(f"All retry attempts failed. Raising IMAPFetchError.")
                raise IMAPFetchError(f"Failed after {max_retries} attempts: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during IMAP workflow: {e}")
            raise IMAPFetchError(f"Unexpected error during IMAP: {e}")

def add_tags_to_email(imap, email_uid, tags: List[str]) -> bool:
    """
    Add tags (IMAP keywords/flags) to a specific email message.
    Uses UID STORE (RFC 3501 §6.4.6) with +FLAGS.SILENT to add tags non-destructively.
    Returns True on OK, False on error.
    Email UIDs are bytes or string.
    Tags should be IMAP-compliant (escaped if needed).
    Respects dry-run mode (skips actual IMAP operations).
    """
    try:
        # Accept bytes or int, ensure string UID
        if isinstance(email_uid, bytes):
            uid_str = email_uid.decode()
        elif isinstance(email_uid, int):
            uid_str = str(email_uid)
        else:
            uid_str = str(email_uid)
        
        # Log UID type and value for debugging
        logger = logging.getLogger(__name__)
        logger.info(f"[IMAP] Attempting to add tags {tags} to email UID {uid_str} (input type: {type(email_uid).__name__})")
        
        # Check if in dry-run mode
        try:
            from src.dry_run import is_dry_run
            from src.dry_run_output import DryRunOutput
            dry_run = is_dry_run()
        except ImportError:
            dry_run = False
        
        if dry_run:
            # In dry-run mode, just log what would be set
            try:
                output = DryRunOutput()
                output.warning(f"Would add IMAP tags {tags} to email UID {uid_str}")
            except Exception:
                logger.info(f"[DRY RUN] Would add tags {tags} to email UID {uid_str}")
            return True  # Return True to indicate "would succeed"
        
        # IMAP expects tags as a space-separated string, in parens
        tagset = "(" + " ".join(tags) + ")"
        logger.debug(f"[IMAP] STORE command: UID {uid_str}, tagset={tagset}")
        
        # Check if IMAP connection is still open
        try:
            # Try to check connection state
            if hasattr(imap, 'state') and imap.state != 'SELECTED':
                logger.warning(f"[IMAP] Connection state is '{imap.state}', not 'SELECTED'. Attempting to select INBOX...")
                status, _ = imap.select('INBOX')
                if status != 'OK':
                    logger.error(f"[IMAP] Failed to select INBOX: {status}")
                    return False
        except Exception as e:
            logger.warning(f"[IMAP] Could not check connection state: {e}")
        
        result, data = imap.uid('STORE', uid_str, '+FLAGS.SILENT', tagset)
        logger.info(f"[IMAP] STORE response: result={result}, data={data if data else 'None'}")
        
        if result == 'OK':
            logger.info(f"[IMAP] Successfully added tags {tags} to email UID {uid_str}.")
            return True
        else:
            logger.error(f"[IMAP] Failed to add tags {tags} to UID {uid_str}: IMAP response={result}, data={data}")
            return False
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error adding tags {tags} to UID {email_uid}: {e}", exc_info=True)
        return False

@contextmanager
def safe_imap_operation(
    host: str,
    user: str,
    password: str,
    mailbox: str = 'INBOX',
    max_retries: int = 3,
    port: int = 993,
    timeout: int = 30
):
    """
    Context manager for safe IMAP operations with retry logic and mailbox context.
    
    Ensures:
    - Mailbox is selected before UID operations
    - Exponential backoff retry on transient errors (NO/TRYAGAIN)
    - Proper connection cleanup
    - Uses FLAGS (not KEYWORDS extension) for tagging - supported by all IMAP servers
    
    Usage:
        with safe_imap_operation(host, user, password) as imap:
            # Perform IMAP operations (mailbox already selected)
            add_tags_to_email(imap, uid, tags)
    """
    imap = None
    attempt = 0
    
    try:
        while attempt < max_retries:
            attempt += 1
            try:
                # Connect to IMAP server
                imap = connect_imap(host, user, password, port)
                if imap.sock:
                    imap.sock.settimeout(timeout)
                
                # Note: We use FLAGS (not KEYWORDS extension) for tagging.
                # FLAGS are supported by all IMAP servers, so no capability check needed.
                
                # Select mailbox (ensures context for UID operations)
                status, data = imap.select(mailbox)
                if status != 'OK':
                    try:
                        imap.logout()
                    except Exception:
                        pass
                    raise IMAPConnectionError(f"Failed to select mailbox {mailbox}: {data}")
                
                logging.debug(f"Safe IMAP operation context established (mailbox: {mailbox})")
                
                # Yield the connection for use
                # Note: Errors during operations (after yield) are not retried here.
                # Individual operations should handle their own retries if needed.
                yield imap
                # Success - break retry loop
                break
                
            except IMAPConnectionError as e:
                # Retry connection errors
                if imap:
                    try:
                        imap.logout()
                    except Exception:
                        pass
                if attempt < max_retries:
                    sleep_secs = 2 ** attempt
                    logging.warning(f"IMAP connection error (attempt {attempt}/{max_retries}): {e}. Retrying in {sleep_secs}s...")
                    time.sleep(sleep_secs)
                    imap = None
                else:
                    raise IMAPFetchError(f"IMAP operation failed after {max_retries} retries: {e}")
            except Exception as e:
                if imap:
                    try:
                        imap.logout()
                    except Exception:
                        pass
                if attempt < max_retries:
                    sleep_secs = 2 ** attempt
                    logging.warning(f"IMAP connection error (attempt {attempt}/{max_retries}): {e}. Retrying in {sleep_secs}s...")
                    time.sleep(sleep_secs)
                    imap = None
                else:
                    raise IMAPFetchError(f"IMAP operation failed after {max_retries} retries: {e}")
        else:
            # All retries exhausted
            raise IMAPFetchError(f"IMAP operation failed after {max_retries} attempts")
    finally:
        # Cleanup on exit (success or failure)
        if imap:
            try:
                imap.logout()
            except Exception:
                pass
