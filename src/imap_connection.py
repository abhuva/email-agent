import imaplib
import os
import logging
import yaml

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
    # Optionally: validate queries with a simple check; real validation is left to imaplib server response
    for q in queries:
        if not isinstance(q, str) or len(q.strip()) == 0:
            raise ValueError(f"IMAP query must be a non-empty string: {q}")
    logging.info(f"Loaded IMAP queries: {queries}")
    return queries
