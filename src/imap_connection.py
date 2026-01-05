import imaplib
import os
import logging

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
