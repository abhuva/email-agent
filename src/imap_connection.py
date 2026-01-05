import imaplib
import os
import logging
import yaml
from typing import List

class IMAPConnectionError(Exception):
    """Raised when IMAP connection fails."""
    pass

def connect_imap(host: str, user: str, password: str, port: int = 993):
    """
    Establish a secure IMAP connection.
    Args:
        host (str): IMAP server hostname
        user (str): IMAP username
        password (str): IMAP password
        port (int): IMAP SSL port (default: 993)
    Returns:
        imaplib.IMAP4_SSL: connected IMAP client
    Raises:
        IMAPConnectionError: if authentication or connection fails
    """
    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(user, password)
        logging.info(f"IMAP connection established with {host} as {user}.")
        return imap
    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP login failed: {e}")
        raise IMAPConnectionError(f"IMAP login failed: {e}")
    except Exception as e:
        logging.error(f"IMAP connection failed: {e}")
        raise IMAPConnectionError(f"IMAP connection failed: {e}")

def load_imap_queries(config_path: str = "config/config.yaml"):
    """Load and validate IMAP queries from config.yaml."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    queries = config.get('imap_queries')
    if not queries:
        # fallback to 'imap_query' key for backwards compatibility
        query = config.get('imap_query')
        if query:
            queries = [query]
        else:
            raise ValueError("No 'imap_queries' or 'imap_query' found in config.")
    if not isinstance(queries, list):
        raise ValueError("'imap_queries' must be a list of IMAP search strings.")
    for q in queries:
        if not isinstance(q, str) or len(q.strip()) == 0:
            raise ValueError(f"IMAP query must be a non-empty string: {q}")
    logging.info(f"Loaded IMAP queries: {queries}")
    return queries

def search_emails_excluding_processed(imap, queries: List[str], processed_tag: str = '[AI-Processed]') -> List[bytes]:
    """
    Search INBOX for emails matching queries, excluding those with [AI-Processed] tag.
    Args:
        imap: Connected IMAP4_SSL instance
        queries: List of IMAP search query strings
        processed_tag: The tag to exclude (default: '[AI-Processed]')
    Returns:
        List of email message UIDs as bytes
    Raises:
        IMAPConnectionError if search fails
    """
    try:
        imap.select('INBOX')
        all_ids = set()
        for q in queries:
            # Exclude processed_tag: Use NOT KEYWORD (for Gmail: X-GM-LABELS for other providers)
            # IMAP syntax: '(%s NOT KEYWORD "%s")' % (q, processed_tag)
            status, data = imap.search(None, f'{q} NOT KEYWORD "{processed_tag}"')
            if status != 'OK':
                logging.error(f"IMAP search failed on query: {q}")
                continue
            ids = data[0].split()
            all_ids.update(ids)
        logging.info(f"Found {len(all_ids)} unprocessed emails matching queries.")
        return list(all_ids)
    except Exception as e:
        logging.error(f"IMAP search failed: {e}")
        raise IMAPConnectionError(f"IMAP search failed: {e}")
