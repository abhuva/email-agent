"""
IMAP client module for email retrieval and flag management.

This module provides a clean interface for IMAP operations.
Configuration is provided via account-specific configuration dictionaries or factory methods.
"""
import imaplib
import logging
import email
from email.header import decode_header
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from src.settings import settings
from src.config import ConfigError

logger = logging.getLogger(__name__)


class IMAPClientError(Exception):
    """Base exception for IMAP client errors."""
    pass


class IMAPConnectionError(IMAPClientError):
    """Raised when IMAP connection or authentication fails."""
    pass


class IMAPFetchError(IMAPClientError):
    """Raised when IMAP email fetching or operations fail."""
    pass


class ImapClient:
    """
    IMAP client for email retrieval and flag management.
    
    This class provides a clean interface for IMAP operations.
    
    Example:
        client = ImapClient()
        client.connect()
        emails = client.get_unprocessed_emails()
        client.disconnect()
    """
    
    def __init__(self):
        """Initialize IMAP client (does not connect yet)."""
        self._imap: Optional[imaplib.IMAP4] = None
        self._connected = False
    
    def connect(self) -> None:
        """
        Establish connection to IMAP server using credentials from settings facade.
        
        Raises:
            IMAPConnectionError: If connection or authentication fails
            ConfigError: If required configuration is missing
        """
        if self._connected:
            logger.warning("Already connected to IMAP server")
            return
        
        try:
            # Get configuration from settings facade
            server = settings.get_imap_server()
            port = settings.get_imap_port()
            username = settings.get_imap_username()
            password = settings.get_imap_password()
            
            logger.info(f"Connecting to IMAP server {server}:{port} as {username}")
            
            # Connect based on port (SSL for 993, STARTTLS for 143)
            if port == 993:
                # Use SSL from the start (IMAPS)
                self._imap = imaplib.IMAP4_SSL(server, port)
            elif port == 143:
                # Use STARTTLS (upgrade plain connection to TLS)
                self._imap = imaplib.IMAP4(server, port)
                self._imap.starttls()
            else:
                # Default to SSL for other ports
                logger.warning(f"Port {port} not standard (143/993), defaulting to SSL")
                self._imap = imaplib.IMAP4_SSL(server, port)
            
            # Authenticate
            self._imap.login(username, password)
            
            # Select INBOX (default mailbox)
            typ, data = self._imap.select('INBOX')
            if typ != 'OK':
                raise IMAPConnectionError(f"Failed to select INBOX: {data}")
            
            self._connected = True
            logger.info("IMAP connection established successfully")
            
        except imaplib.IMAP4.error as e:
            error_msg = f"IMAP authentication failed: {e}"
            logger.error(error_msg)
            raise IMAPConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"IMAP connection failed: {e}"
            logger.error(error_msg)
            raise IMAPConnectionError(error_msg) from e
    
    def disconnect(self) -> None:
        """Close IMAP connection."""
        if self._imap and self._connected:
            try:
                self._imap.logout()
                logger.info("IMAP connection closed")
            except Exception as e:
                logger.warning(f"Error closing IMAP connection: {e}")
            finally:
                self._imap = None
                self._connected = False
    
    def _ensure_connected(self) -> None:
        """Ensure IMAP connection is established."""
        if not self._connected or not self._imap:
            raise IMAPConnectionError("Not connected to IMAP server. Call connect() first.")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._connected:
            self.disconnect()
    
    def get_email_by_uid(self, uid: str) -> Dict[str, Any]:
        """
        Retrieve a specific email by its UID.
        
        Args:
            uid: Email UID (string)
            
        Returns:
            Dictionary with email data:
            - uid: Email UID
            - subject: Email subject
            - from: Sender address
            - to: Recipient addresses (list)
            - date: Email date
            - body: Plain text body
            - html_body: HTML body (if available)
            - headers: All email headers
            
        Raises:
            IMAPFetchError: If email not found or fetch fails
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()
        
        try:
            # Use UID FETCH (not FETCH) to maintain UID consistency
            typ, data = self._imap.uid('FETCH', uid, '(RFC822)')
            
            if typ != 'OK':
                raise IMAPFetchError(f"Failed to fetch email UID {uid}: {data}")
            
            if not data or not data[0] or len(data[0]) < 2:
                raise IMAPFetchError(f"Invalid FETCH response for UID {uid}")
            
            # Parse email
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Decode headers
            subject = self._decode_mime_header(msg.get('Subject', ''))
            sender = self._decode_mime_header(msg.get('From', ''))
            to_header = msg.get('To', '')
            recipients = [addr.strip() for addr in to_header.split(',')] if to_header else []
            date = self._decode_mime_header(msg.get('Date', ''))
            
            # Extract body
            body = ''
            html_body = ''
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))
                    
                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue
                    
                    # Extract text/plain
                    if content_type == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            try:
                                charset = part.get_content_charset() or 'utf-8'
                                body = payload.decode(charset, errors='replace')
                            except Exception as e:
                                logger.warning(f"Error decoding plain text body for UID {uid}: {e}")
                                body = payload.decode('utf-8', errors='replace')
                    
                    # Extract text/html
                    elif content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        if payload:
                            try:
                                charset = part.get_content_charset() or 'utf-8'
                                html_body = payload.decode(charset, errors='replace')
                            except Exception as e:
                                logger.warning(f"Error decoding HTML body for UID {uid}: {e}")
                                html_body = payload.decode('utf-8', errors='replace')
            else:
                # Single part message
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        charset = msg.get_content_charset() or 'utf-8'
                        content = payload.decode(charset, errors='replace')
                        if msg.get_content_type() == 'text/html':
                            html_body = content
                        else:
                            body = content
                    except Exception as e:
                        logger.warning(f"Error decoding body for UID {uid}: {e}")
                        body = payload.decode('utf-8', errors='replace')
            
            # Extract all headers
            headers = {}
            for key, value in msg.items():
                headers[key] = self._decode_mime_header(value)
            
            return {
                'uid': uid,
                'subject': subject,
                'from': sender,
                'to': recipients,
                'date': date,
                'body': body,
                'html_body': html_body,
                'headers': headers
            }
            
        except IMAPFetchError:
            raise
        except Exception as e:
            error_msg = f"Error fetching email UID {uid}: {e}"
            logger.error(error_msg)
            raise IMAPFetchError(error_msg) from e
    
    def _decode_mime_header(self, header_value: str) -> str:
        """
        Decode MIME-encoded header value.
        
        Args:
            header_value: Raw header value (may be MIME-encoded)
            
        Returns:
            Decoded header string
        """
        if not header_value:
            return ''
        
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ''
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        # Handle known problematic encodings
                        if encoding.lower() in ('unknown-8bit', 'unknown'):
                            # Try common encodings for unknown-8bit
                            for fallback_encoding in ['latin-1', 'cp1252', 'utf-8']:
                                try:
                                    decoded_string += part.decode(fallback_encoding, errors='replace')
                                    break
                                except (UnicodeDecodeError, LookupError):
                                    continue
                            else:
                                # If all fallbacks fail, use replace errors
                                decoded_string += part.decode('utf-8', errors='replace')
                        else:
                            decoded_string += part.decode(encoding, errors='replace')
                    else:
                        decoded_string += part.decode('utf-8', errors='replace')
                else:
                    decoded_string += part
            return decoded_string.strip()
        except Exception as e:
            # Log at debug level since we handle it gracefully
            # These are often spam filter headers or other non-critical headers with encoding issues
            logger.debug(f"Error decoding header (using fallback): {e}")
            # Try to return the string as-is, or decode with errors='replace' if it's bytes
            if isinstance(header_value, bytes):
                try:
                    return header_value.decode('utf-8', errors='replace')
                except Exception:
                    return str(header_value)
            return str(header_value)
    
    def get_unprocessed_emails(self, max_emails: Optional[int] = None, force_reprocess: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieve all unprocessed emails from the IMAP server.
        
        Emails are considered unprocessed if they don't have the processed_tag flag.
        When force_reprocess=True, includes all emails regardless of processed status.
        
        Args:
            max_emails: Maximum number of emails to retrieve (None = all)
            force_reprocess: If True, include processed emails (for reprocessing)
            
        Returns:
            List of email dictionaries (same format as get_email_by_uid)
            
        Raises:
            IMAPFetchError: If search or fetch fails
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()
        
        try:
            # Get configuration from settings facade
            user_query = settings.get_imap_query()
            processed_tag = settings.get_imap_processed_tag()
            max_emails_per_run = max_emails or settings.get_max_emails_per_run()
            
            if force_reprocess:
                logger.info(f"Searching for emails (force-reprocess mode, query: {user_query})")
                # In force-reprocess mode, don't exclude processed emails
                search_query = user_query
            else:
                logger.info(f"Searching for unprocessed emails (query: {user_query}, exclude: {processed_tag})")
                # Build search query excluding processed emails
                # Use NOT KEYWORD to exclude emails with the processed tag
                search_query = f'({user_query} NOT KEYWORD "{processed_tag}")'
            
            # Search for UIDs (use UID SEARCH, not SEARCH)
            typ, data = self._imap.uid('SEARCH', None, search_query)
            
            if typ != 'OK':
                raise IMAPFetchError(f"IMAP search failed: {data}")
            
            if not data or not data[0]:
                logger.info("No unprocessed emails found")
                return []
            
            # Parse UIDs (they come as space-separated bytes)
            uid_bytes = data[0]
            if isinstance(uid_bytes, bytes):
                uid_str = uid_bytes.decode('utf-8')
            else:
                uid_str = str(uid_bytes)
            
            uids = [uid.strip() for uid in uid_str.split() if uid.strip()]
            
            if not uids:
                logger.info("No emails found" if force_reprocess else "No unprocessed emails found")
                return []
            
            logger.info(f"Found {len(uids)} email(s)" + (" (including processed)" if force_reprocess else ""))
            
            # Limit number of emails if specified
            if max_emails_per_run and len(uids) > max_emails_per_run:
                logger.info(f"Limiting to {max_emails_per_run} emails (found {len(uids)})")
                uids = uids[:max_emails_per_run]
            
            # Fetch emails
            emails = []
            for uid in uids:
                try:
                    email_data = self.get_email_by_uid(uid)
                    emails.append(email_data)
                except IMAPFetchError as e:
                    logger.warning(f"Skipping email UID {uid} due to fetch error: {e}")
                    continue
            
            logger.info(f"Successfully retrieved {len(emails)} email(s)")
            return emails
            
        except IMAPFetchError:
            raise
        except Exception as e:
            error_msg = f"Error retrieving unprocessed emails: {e}"
            logger.error(error_msg)
            raise IMAPFetchError(error_msg) from e
    
    def set_flag(self, uid: str, flag: str) -> bool:
        """
        Set an IMAP flag on an email.
        
        Args:
            uid: Email UID
            flag: Flag name (e.g., '\\Seen', 'AIProcessed')
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            IMAPConnectionError: If not connected
        """
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
                output.warning(f"Would set IMAP flag '{flag}' on email UID {uid}")
            except Exception:
                logger.info(f"[DRY RUN] Would set flag '{flag}' on email UID {uid}")
            return True  # Return True to indicate "would succeed"
        
        self._ensure_connected()
        
        try:
            # Use UID STORE to set flag
            typ, data = self._imap.uid('STORE', uid, '+FLAGS', f'({flag})')
            if typ == 'OK':
                logger.debug(f"Set flag '{flag}' on email UID {uid}")
                return True
            else:
                logger.warning(f"Failed to set flag '{flag}' on email UID {uid}: {data}")
                return False
        except Exception as e:
            logger.error(f"Error setting flag '{flag}' on email UID {uid}: {e}")
            return False
    
    def clear_flag(self, uid: str, flag: str) -> bool:
        """
        Clear an IMAP flag from an email.
        
        Args:
            uid: Email UID
            flag: Flag name (e.g., '\\Seen', 'AIProcessed')
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            IMAPConnectionError: If not connected
        """
        # Check if in dry-run mode
        try:
            from src.dry_run import is_dry_run
            from src.dry_run_output import DryRunOutput
            dry_run = is_dry_run()
        except ImportError:
            dry_run = False
        
        if dry_run:
            # In dry-run mode, just log what would be cleared
            try:
                output = DryRunOutput()
                output.warning(f"Would clear IMAP flag '{flag}' from email UID {uid}")
            except Exception:
                logger.info(f"[DRY RUN] Would clear flag '{flag}' from email UID {uid}")
            return True  # Return True to indicate "would succeed"
        
        self._ensure_connected()
        
        try:
            # Use UID STORE to clear flag
            typ, data = self._imap.uid('STORE', uid, '-FLAGS', f'({flag})')
            if typ == 'OK':
                logger.debug(f"Cleared flag '{flag}' from email UID {uid}")
                return True
            else:
                logger.warning(f"Failed to clear flag '{flag}' from email UID {uid}: {data}")
                return False
        except Exception as e:
            logger.error(f"Error clearing flag '{flag}' from email UID {uid}: {e}")
            return False
    
    def has_flag(self, uid: str, flag: str) -> bool:
        """
        Check if an email has a specific IMAP flag.
        
        Args:
            uid: Email UID
            flag: Flag name (e.g., '\\Seen', 'AIProcessed')
            
        Returns:
            True if email has the flag, False otherwise
            
        Raises:
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()
        
        try:
            # Fetch FLAGS for the email
            typ, data = self._imap.uid('FETCH', uid, '(FLAGS)')
            
            if typ != 'OK' or not data or not data[0]:
                logger.warning(f"Failed to fetch flags for email UID {uid}")
                return False
            
            # Parse flags from response
            flags_str = str(data[0])
            has_flag = flag in flags_str
            
            logger.debug(f"Email UID {uid} has flag '{flag}': {has_flag}")
            return has_flag
            
        except Exception as e:
            logger.error(f"Error checking flag '{flag}' for email UID {uid}: {e}")
            return False
    
    def is_processed(self, uid: str) -> bool:
        """
        Check if an email has been processed.
        
        Uses the processed_tag from settings to determine processed status.
        
        Args:
            uid: Email UID
            
        Returns:
            True if email has been processed, False otherwise
            
        Raises:
            IMAPConnectionError: If not connected
        """
        processed_tag = settings.get_imap_processed_tag()
        return self.has_flag(uid, processed_tag)
    
    def mark_as_processed(self, uid: str) -> bool:
        """
        Mark an email as processed by setting the processed tag.
        
        Args:
            uid: Email UID
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            IMAPConnectionError: If not connected
        """
        processed_tag = settings.get_imap_processed_tag()
        return self.set_flag(uid, processed_tag)
    
    def get_next_unprocessed_email(self, force_reprocess: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get the next unprocessed email (convenience method).
        
        Args:
            force_reprocess: If True, include processed emails (for reprocessing)
        
        Returns:
            Email dictionary if found, None otherwise
            
        Raises:
            IMAPFetchError: If search or fetch fails
            IMAPConnectionError: If not connected
        """
        emails = self.get_unprocessed_emails(max_emails=1, force_reprocess=force_reprocess)
        return emails[0] if emails else None
    
    def get_email_for_processing(self, uid: Optional[str] = None, force_reprocess: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get email(s) for processing, supporting both single UID and batch modes.
        
        Args:
            uid: Specific email UID to retrieve (None = get unprocessed emails)
            force_reprocess: If True, include processed emails (for reprocessing)
        
        Returns:
            Email dictionary if uid provided, or list of emails if uid is None
            Returns None if email not found or no emails available
            
        Raises:
            IMAPFetchError: If search or fetch fails
            IMAPConnectionError: If not connected
        """
        if uid:
            # Single email by UID
            try:
                email_data = self.get_email_by_uid(uid)
                # Check if already processed (unless force_reprocess)
                if not force_reprocess and self.is_processed(uid):
                    logger.info(f"Email UID {uid} already processed, skipping (use --force-reprocess to override)")
                    return None
                return email_data
            except IMAPFetchError:
                return None
        else:
            # Get unprocessed emails
            return self.get_next_unprocessed_email(force_reprocess=force_reprocess)
