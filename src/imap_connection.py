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


class IMAPKeywordsNotSupportedError(Exception):
    """
    Raised when IMAP server doesn't support KEYWORDS capability.
    
    Note: This exception is deprecated as the codebase now uses FLAGS
    instead of KEYWORDS for better compatibility.
    """
    pass

# ... existing functions (connect_imap, load_imap_queries, etc.) ...

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

def search_emails_excluding_processed(
    imap, 
    user_query: str, 
    processed_tag: str = 'AIProcessed',
    obsidian_note_created_tag: str = 'Obsidian-Note-Created',
    note_creation_failed_tag: str = 'Note-Creation-Failed'
) -> List[bytes]:
    """
    Search emails using user query combined with idempotency checks.
    
    The user query is combined with NOT conditions to exclude emails that have
    already been processed (V1: AIProcessed, V2: Obsidian-Note-Created, Note-Creation-Failed).
    
    Args:
        imap: IMAP connection object
        user_query: User-defined IMAP query string from config
        processed_tag: V1 processed tag (for backward compatibility)
        obsidian_note_created_tag: V2 success tag
        note_creation_failed_tag: V2 failure tag
    
    Returns:
        List of email UIDs (bytes)
    """
    try:
        imap.select('INBOX')
        
        # Combine user query with idempotency checks
        # Format: ({user_query} NOT KEYWORD "tag1" NOT KEYWORD "tag2" NOT KEYWORD "tag3")
        # This ensures we never reprocess emails that have already been handled
        final_query = (
            f'({user_query} '
            f'NOT KEYWORD "{processed_tag}" '
            f'NOT KEYWORD "{obsidian_note_created_tag}" '
            f'NOT KEYWORD "{note_creation_failed_tag}")'
        )
        
        logging.debug(f"Executing IMAP query: {final_query}")
        
        # Note: IMAP uses "KEYWORD" keyword in SEARCH to search FLAGS
        # This is confusing naming in the IMAP spec, but it's correct
        # We're searching for custom FLAGS, not the KEYWORDS extension
        status, data = imap.search(None, final_query)
        
        if status != 'OK':
            logging.error(f"IMAP search failed on query: {final_query}")
            raise IMAPConnectionError(f"IMAP search failed: {status} {data}")
        
        ids = data[0].split() if data[0] else []
        logging.info(f"Found {len(ids)} unprocessed emails matching query.")
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
    parsed = []
    for msg_id in msg_ids:
        typ, data = imap.fetch(msg_id, '(RFC822)')
        if typ != 'OK':
            logging.error(f'Failed to fetch msg id {msg_id}: {data}')
            continue
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_header(msg.get('Subject'))
        sender = decode_mime_header(msg.get('From'))
        date = decode_mime_header(msg.get('Date'))
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
        parsed.append({
            'id': msg_id,
            'subject': subject,
            'sender': sender,
            'body': body,
            'date': date,
        })
    logging.info(f"Parsed {len(parsed)} emails.")
    return parsed

def fetch_emails(
    host: str, user: str, password: str,
    user_query: str,
    processed_tag: str = 'AIProcessed',
    obsidian_note_created_tag: str = 'Obsidian-Note-Created',
    note_creation_failed_tag: str = 'Note-Creation-Failed',
    max_retries: int = 3,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    High-level function to orchestrate config loading, connecting, searching, fetching, and parsing.
    
    Args:
        host: IMAP server hostname
        user: IMAP username
        password: IMAP password
        user_query: User-defined IMAP query string from config
        processed_tag: V1 processed tag (for backward compatibility)
        obsidian_note_created_tag: V2 success tag
        note_creation_failed_tag: V2 failure tag
        max_retries: Maximum retry attempts
        timeout: IMAP socket timeout in seconds
    
    Returns:
        List of parsed email dictionaries
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
                    processed_tag,
                    obsidian_note_created_tag,
                    note_creation_failed_tag
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
    """
    try:
        # Accept bytes or int, ensure string UID
        if isinstance(email_uid, bytes):
            uid_str = email_uid.decode()
        elif isinstance(email_uid, int):
            uid_str = str(email_uid)
        else:
            uid_str = str(email_uid)
        # IMAP expects tags as a space-separated string, in parens
        tagset = "(" + " ".join(tags) + ")"
        result, data = imap.uid('STORE', uid_str, '+FLAGS.SILENT', tagset)
        if result == 'OK':
            logging.info(f"Added tags {tags} to email UID {uid_str}.")
            return True
        else:
            logging.error(f"Failed to add tags {tags} to UID {uid_str}: {result} {data}")
            return False
    except Exception as e:
        logging.error(f"Error adding tags {tags} to UID {email_uid}: {e}")
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
