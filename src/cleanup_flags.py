"""
Cleanup Flags Module

This module implements the cleanup-flags command functionality for removing
application-specific IMAP flags from emails on the server.

Features:
    - Scans emails and identifies application-specific flags
    - Dry-run mode to preview operations
    - Mandatory confirmation prompt (PDD security requirement)
    - Detailed logging of all operations
    - Error isolation to prevent crashes

All configuration access is through account-specific configuration dictionaries.
"""
import logging
import re
from typing import List, Dict, Any
from dataclasses import dataclass

from src.imap_client import ImapClient, IMAPConnectionError, IMAPFetchError

logger = logging.getLogger(__name__)


@dataclass
class FlagScanResult:
    """Result of scanning an email for application-specific flags."""
    uid: str
    subject: str
    application_flags: List[str]
    all_flags: List[str]


@dataclass
class CleanupSummary:
    """Summary of cleanup operation."""
    total_emails_scanned: int
    emails_with_flags: int
    total_flags_removed: int
    emails_modified: int
    errors: int


class CleanupFlagsError(Exception):
    """Base exception for cleanup flags operations."""
    pass


class CleanupFlags:
    """
    Cleanup flags manager for removing application-specific IMAP flags.
    
    This class handles:
    - Scanning emails for application-specific flags
    - Dry-run preview mode
    - Flag removal with confirmation
    - Detailed logging
    
    Example:
        cleanup = CleanupFlags(config=account_config, imap_client=imap_client)
        summary = cleanup.scan_flags(dry_run=True)
        if not dry_run:
            cleanup.remove_flags(summary, confirm=True)
    """
    
    def __init__(self, config: Dict[str, Any], imap_client: ImapClient):
        """
        Initialize cleanup flags manager.
        
        Args:
            config: Account-specific configuration dictionary.
            imap_client: IMAP client instance.
        """
        self._config = config
        self.imap_client = imap_client
        
        self.application_flags: List[str] = []
        self._load_application_flags()
    
    def _load_application_flags(self) -> None:
        """Load application-specific flags from config."""
        try:
            imap_config = self._config.get('imap', {})
            self.application_flags = imap_config.get('application_flags', [])
            if not self.application_flags:
                # Fallback to defaults
                self.application_flags = ["AIProcessed", "ObsidianNoteCreated", "NoteCreationFailed"]
            
            logger.info(f"Loaded {len(self.application_flags)} application-specific flags: {self.application_flags}")
        except Exception as e:
            logger.error(f"Failed to load application flags: {e}")
            # Fallback to default flags
            self.application_flags = ["AIProcessed", "ObsidianNoteCreated", "NoteCreationFailed"]
            logger.warning(f"Using default application flags: {self.application_flags}")
    
    def connect(self) -> None:
        """Connect to IMAP server."""
        try:
            self.imap_client.connect()
            logger.info("Connected to IMAP server for cleanup operation")
        except IMAPConnectionError as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise CleanupFlagsError(f"IMAP connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        try:
            self.imap_client.disconnect()
            logger.info("Disconnected from IMAP server")
        except Exception as e:
            logger.warning(f"Error disconnecting from IMAP server: {e}")
    
    def scan_flags(self, dry_run: bool = False) -> List[FlagScanResult]:
        """
        Scan all emails and identify application-specific flags.
        
        Args:
            dry_run: If True, only scan without making changes
            
        Returns:
            List of FlagScanResult objects for emails with application flags
            
        Raises:
            CleanupFlagsError: If scanning fails
        """
        if not self.imap_client._connected:
            self.connect()
        
        logger.info(f"Scanning emails for application-specific flags (dry_run={dry_run})")
        
        try:
            # Get all emails (use ALL query to get everything)
            # We'll fetch flags for all emails
            imap_config = self._config.get('imap', {})
            user_query = imap_config.get('query', 'ALL')
            logger.debug(f"Using IMAP query: {user_query}")
            
            # Search for all emails matching the query
            typ, data = self.imap_client._imap.uid('SEARCH', None, user_query)
            
            if typ != 'OK':
                raise CleanupFlagsError(f"IMAP search failed: {data}")
            
            if not data or not data[0]:
                logger.info("No emails found")
                return []
            
            # Parse UIDs
            uid_bytes = data[0]
            if isinstance(uid_bytes, bytes):
                uid_str = uid_bytes.decode('utf-8')
            else:
                uid_str = str(uid_bytes)
            
            uids = [uid.strip() for uid in uid_str.split() if uid.strip()]
            
            if not uids:
                logger.info("No emails found")
                return []
            
            logger.info(f"Found {len(uids)} email(s) to scan")
            
            # Scan flags for each email
            results: List[FlagScanResult] = []
            
            for uid in uids:
                try:
                    scan_result = self._scan_email_flags(uid)
                    if scan_result.application_flags:  # Only include emails with application flags
                        results.append(scan_result)
                except Exception as e:
                    logger.warning(f"Error scanning flags for email UID {uid}: {e}")
                    continue
            
            logger.info(f"Scan complete: {len(results)} email(s) have application-specific flags")
            return results
            
        except Exception as e:
            error_msg = f"Error scanning flags: {e}"
            logger.error(error_msg)
            raise CleanupFlagsError(error_msg) from e
    
    def _scan_email_flags(self, uid: str) -> FlagScanResult:
        """
        Scan flags for a single email.
        
        Args:
            uid: Email UID
            
        Returns:
            FlagScanResult with flags information
        """
        try:
            # Fetch FLAGS and basic headers (subject) for the email
            typ, data = self.imap_client._imap.uid('FETCH', uid, '(FLAGS BODY[HEADER.FIELDS (SUBJECT)])')
            
            if typ != 'OK' or not data or not data[0]:
                logger.warning(f"Failed to fetch flags for email UID {uid}")
                return FlagScanResult(uid=uid, subject="[Unknown]", application_flags=[], all_flags=[])
            
            # Parse flags from response
            flags_str = str(data[0])
            all_flags = self._parse_flags_from_response(flags_str)
            
            # Extract subject if available
            subject = "[No Subject]"
            try:
                # Try to extract subject from response
                subject_match = re.search(r'Subject:\s*(.+)', flags_str, re.IGNORECASE)
                if subject_match:
                    subject = subject_match.group(1).strip()
            except Exception:
                pass
            
            # If subject not found in flags response, fetch it separately
            if subject == "[No Subject]":
                try:
                    email_data = self.imap_client.get_email_by_uid(uid)
                    subject = email_data.get('subject', '[No Subject]')
                except Exception:
                    pass
            
            # Identify application-specific flags
            application_flags = [flag for flag in all_flags if flag in self.application_flags]
            
            return FlagScanResult(
                uid=uid,
                subject=subject,
                application_flags=application_flags,
                all_flags=all_flags
            )
            
        except Exception as e:
            logger.warning(f"Error scanning email UID {uid}: {e}")
            return FlagScanResult(uid=uid, subject="[Error]", application_flags=[], all_flags=[])
    
    def _parse_flags_from_response(self, flags_str: str) -> List[str]:
        """
        Parse IMAP flags from FETCH response.
        
        Args:
            flags_str: Raw IMAP FETCH response string
            
        Returns:
            List of flag names (without backslashes)
        """
        flags = []
        try:
            # Extract flags between parentheses: FLAGS (\\Seen \\Flagged AIProcessed)
            flags_match = re.search(r'FLAGS\s+\(([^)]+)\)', flags_str)
            if flags_match:
                flags_raw = flags_match.group(1).split()
                # Remove backslashes and clean up
                flags = [f.strip('\\').strip() for f in flags_raw if f.strip()]
        except Exception as e:
            logger.warning(f"Error parsing flags from response: {e}")
        
        return flags
    
    def remove_flags(self, scan_results: List[FlagScanResult], dry_run: bool = False) -> CleanupSummary:
        """
        Remove application-specific flags from emails.
        
        Args:
            scan_results: List of FlagScanResult objects from scan_flags()
            dry_run: If True, only log what would be removed without making changes
            
        Returns:
            CleanupSummary with operation statistics
        """
        if not scan_results:
            logger.info("No emails to process")
            return CleanupSummary(
                total_emails_scanned=0,
                emails_with_flags=0,
                total_flags_removed=0,
                emails_modified=0,
                errors=0
            )
        
        logger.info(f"Removing flags from {len(scan_results)} email(s) (dry_run={dry_run})")
        
        summary = CleanupSummary(
            total_emails_scanned=len(scan_results),
            emails_with_flags=len(scan_results),
            total_flags_removed=0,
            emails_modified=0,
            errors=0
        )
        
        for result in scan_results:
            try:
                flags_removed = 0
                for flag in result.application_flags:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would remove flag '{flag}' from email UID {result.uid} ({result.subject})")
                        flags_removed += 1
                    else:
                        success = self.imap_client.clear_flag(result.uid, flag)
                        if success:
                            logger.info(f"Removed flag '{flag}' from email UID {result.uid} ({result.subject})")
                            flags_removed += 1
                        else:
                            logger.warning(f"Failed to remove flag '{flag}' from email UID {result.uid}")
                            summary.errors += 1
                
                if flags_removed > 0:
                    summary.total_flags_removed += flags_removed
                    summary.emails_modified += 1
                    
            except Exception as e:
                logger.error(f"Error removing flags from email UID {result.uid}: {e}")
                summary.errors += 1
        
        logger.info(
            f"Cleanup complete: {summary.emails_modified} email(s) modified, "
            f"{summary.total_flags_removed} flag(s) removed, {summary.errors} error(s)"
        )
        
        return summary
    
    def format_scan_results(self, results: List[FlagScanResult]) -> str:
        """
        Format scan results for display.
        
        Args:
            results: List of FlagScanResult objects
            
        Returns:
            Formatted string for console output
        """
        if not results:
            return "No emails with application-specific flags found."
        
        lines = []
        lines.append(f"\nFound {len(results)} email(s) with application-specific flags:\n")
        
        total_flags = sum(len(r.application_flags) for r in results)
        
        for i, result in enumerate(results, 1):
            lines.append(f"  {i}. UID: {result.uid}")
            lines.append(f"     Subject: {result.subject}")
            lines.append(f"     Application flags: {', '.join(result.application_flags) if result.application_flags else 'None'}")
            lines.append("")
        
        lines.append(f"Summary: {len(results)} email(s), {total_flags} flag(s) to remove")
        
        return "\n".join(lines)
