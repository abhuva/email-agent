"""
Mock services for integration testing.

This module provides mock implementations of external services (IMAP, LLM)
that can be used in integration tests to isolate component interactions
without requiring real external dependencies.

Mock Services:
- MockImapClient: In-memory IMAP client with configurable responses
- MockLLMClient: Deterministic LLM client with scenario-based responses
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from unittest.mock import Mock, MagicMock

from src.models import EmailContext, from_imap_dict
from src.imap_client import ImapClient, IMAPConnectionError, IMAPFetchError
from src.llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class MockEmailData:
    """Represents an email in the mock IMAP server."""
    uid: str
    sender: str
    subject: str
    body: str
    html_body: Optional[str] = None
    date: Optional[str] = None
    to: Optional[List[str]] = None
    flags: List[str] = None
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []
        if self.to is None:
            self.to = []
        if self.date is None:
            self.date = "2024-01-01T12:00:00Z"
        if self.html_body is None:
            self.html_body = f"<p>{self.body}</p>"


class MockImapClient(ImapClient):
    """
    Mock IMAP client that returns deterministic data from in-memory fixtures.
    
    This mock allows configuration of:
    - Mailboxes and messages
    - Error conditions (empty inbox, connection errors, malformed messages)
    - Edge cases for testing
    
    Example:
        >>> client = MockImapClient()
        >>> client.add_email(MockEmailData(
        ...     uid="123",
        ...     sender="test@example.com",
        ...     subject="Test",
        ...     body="Test body"
        ... ))
        >>> client.connect()
        >>> emails = client.fetch_emails()
        >>> assert len(emails) == 1
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize mock IMAP client.
        
        Args:
            config: Optional configuration dictionary (for compatibility with real client)
        """
        super().__init__()
        self.config = config or {}
        self._emails: Dict[str, MockEmailData] = {}
        self._connected = False
        self._should_fail_connect = False
        self._should_fail_fetch = False
        self._empty_inbox = False
        self._malformed_message = False
        
    def add_email(self, email: MockEmailData) -> None:
        """Add an email to the mock inbox."""
        self._emails[email.uid] = email
        
    def remove_email(self, uid: str) -> None:
        """Remove an email from the mock inbox."""
        if uid in self._emails:
            del self._emails[uid]
            
    def clear_emails(self) -> None:
        """Clear all emails from the mock inbox."""
        self._emails.clear()
        
    def set_connection_error(self, should_fail: bool = True) -> None:
        """Configure whether connection should fail."""
        self._should_fail_connect = should_fail
        
    def set_fetch_error(self, should_fail: bool = True) -> None:
        """Configure whether fetch operations should fail."""
        self._should_fail_fetch = should_fail
        
    def set_empty_inbox(self, empty: bool = True) -> None:
        """Configure whether inbox should be empty."""
        self._empty_inbox = empty
        
    def set_malformed_message(self, malformed: bool = True) -> None:
        """Configure whether to return malformed message."""
        self._malformed_message = malformed
        
    def connect(self) -> None:
        """Mock connection (always succeeds unless configured to fail)."""
        if self._should_fail_connect:
            raise IMAPConnectionError("Mock connection error")
        self._connected = True
        logger.debug("Mock IMAP client connected")
        
    def disconnect(self) -> None:
        """Mock disconnection."""
        self._connected = False
        logger.debug("Mock IMAP client disconnected")
        
    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected
        
    def fetch_emails(self, query: str = "ALL", max_emails: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch emails from mock inbox.
        
        Args:
            query: IMAP query string (ignored in mock, but kept for compatibility)
            max_emails: Maximum number of emails to return
            
        Returns:
            List of email dictionaries compatible with from_imap_dict()
            
        Raises:
            IMAPFetchError: If configured to fail or if not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
            
        if self._should_fail_fetch:
            raise IMAPFetchError("Mock fetch error")
            
        if self._empty_inbox:
            return []
            
        emails = []
        email_list = list(self._emails.values())
        
        if max_emails:
            email_list = email_list[:max_emails]
            
        for email_data in email_list:
            email_dict = {
                'uid': email_data.uid,
                'from': email_data.sender,
                'subject': email_data.subject,
                'body': email_data.body,
                'html_body': email_data.html_body,
                'date': email_data.date,
                'to': email_data.to,
                'flags': email_data.flags
            }
            
            if self._malformed_message and email_list.index(email_data) == 0:
                # Return malformed message for first email
                email_dict['body'] = None
                email_dict['html_body'] = None
                
            emails.append(email_dict)
            
        return emails
        
    def fetch_email_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific email by UID.
        
        Args:
            uid: Email UID
            
        Returns:
            Email dictionary or None if not found
            
        Raises:
            IMAPFetchError: If not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
            
        if uid not in self._emails:
            return None
            
        email_data = self._emails[uid]
        return {
            'uid': email_data.uid,
            'from': email_data.sender,
            'subject': email_data.subject,
            'body': email_data.body,
            'html_body': email_data.html_body,
            'date': email_data.date,
            'to': email_data.to,
            'flags': email_data.flags
        }
        
    def set_flag(self, uid: str, flag: str) -> bool:
        """
        Set a flag on an email.
        
        Args:
            uid: Email UID
            flag: Flag to set (e.g., 'AIProcessed')
            
        Returns:
            True if successful
            
        Raises:
            IMAPFetchError: If not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
            
        if uid in self._emails:
            if flag not in self._emails[uid].flags:
                self._emails[uid].flags.append(flag)
        return True
        
    def remove_flag(self, uid: str, flag: str) -> bool:
        """
        Remove a flag from an email.
        
        Args:
            uid: Email UID
            flag: Flag to remove
            
        Returns:
            True if successful
            
        Raises:
            IMAPFetchError: If not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
            
        if uid in self._emails and flag in self._emails[uid].flags:
            self._emails[uid].flags.remove(flag)
        return True
        
    def count_emails(self, query: str = "ALL") -> int:
        """
        Count emails matching query.
        
        Args:
            query: IMAP query string (ignored in mock)
            
        Returns:
            Number of emails in mock inbox
            
        Raises:
            IMAPFetchError: If not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
            
        if self._empty_inbox:
            return 0
            
        return len(self._emails)
        
    def count_unprocessed_emails(self, force_reprocess: bool = False) -> tuple[int, List[str]]:
        """
        Count unprocessed emails and return their UIDs.
        
        Args:
            force_reprocess: If True, ignore processed flags
            
        Returns:
            Tuple of (count, list of UIDs)
            
        Raises:
            IMAPFetchError: If not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
            
        if self._empty_inbox:
            return (0, [])
            
        if force_reprocess:
            # Return all emails
            uids = [email.uid for email in self._emails.values()]
            return (len(uids), uids)
        else:
            # Return only unprocessed emails (not flagged with AIProcessed)
            uids = [
                email.uid for email in self._emails.values()
                if 'AIProcessed' not in email.flags
            ]
            return (len(uids), uids)
            
    def get_unprocessed_emails(
        self,
        max_emails: Optional[int] = None,
        force_reprocess: bool = False,
        uids: Optional[List[str]] = None,
        min_uid: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get unprocessed emails from mock inbox.
        
        Args:
            max_emails: Maximum number of emails to return
            force_reprocess: If True, ignore processed flags
            uids: Optional list of UIDs to fetch (if provided, only fetch these)
            min_uid: Optional minimum UID to filter by (only process emails with UID > min_uid)
            
        Returns:
            List of email dictionaries
            
        Raises:
            IMAPFetchError: If not connected
        """
        if not self._connected:
            raise IMAPFetchError("Not connected to IMAP server")
        
        # If UIDs provided, fetch only those
        if uids:
            # Filter by min_uid if provided
            if min_uid is not None:
                uids = [uid for uid in uids if int(uid) > min_uid]
            
            emails = []
            for uid in uids:
                if uid in self._emails:
                    emails.append(self.fetch_email_by_uid(uid))
            if max_emails:
                emails = emails[:max_emails]
            return emails
            
        # Get unprocessed emails
        if force_reprocess:
            unprocessed = list(self._emails.values())
        else:
            unprocessed = [
                email for email in self._emails.values()
                if 'AIProcessed' not in email.flags
            ]
        
        # Filter by min_uid if provided
        if min_uid is not None:
            unprocessed = [
                email for email in unprocessed
                if int(email.uid) > min_uid
            ]
        
        if max_emails:
            unprocessed = unprocessed[:max_emails]
            
        return [self.fetch_email_by_uid(email.uid) for email in unprocessed]


class MockLLMClient(LLMClient):
    """
    Mock LLM client that returns deterministic responses based on input prompts.
    
    This mock allows configuration of:
    - Normal responses (with configurable scores)
    - Long responses (for truncation testing)
    - Error conditions (timeouts, invalid JSON)
    - Scenario-based responses (based on prompt content)
    
    Example:
        >>> client = MockLLMClient()
        >>> client.set_response_for_scenario("spam", spam_score=9, importance_score=1)
        >>> response = client.classify_email("This is spam content")
        >>> assert response.spam_score == 9
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize mock LLM client.
        
        Args:
            config: Optional configuration dictionary (for compatibility with real client)
        """
        # Create default config if none provided
        if config is None:
            import os
            # Set a test API key if not already set
            if 'OPENROUTER_API_KEY' not in os.environ:
                os.environ['OPENROUTER_API_KEY'] = 'test_api_key'
            
            config = {
                'openrouter': {
                    'api_key_env': 'OPENROUTER_API_KEY',
                    'api_url': 'https://openrouter.ai/api/v1'
                },
                'classification': {
                    'model': 'test-model',
                    'temperature': 0.2,
                    'retry_attempts': 3,
                    'retry_delay_seconds': 1
                },
                'processing': {
                    'max_body_chars': 6000
                }
            }
        
        # Ensure required config sections exist
        if 'openrouter' not in config:
            config['openrouter'] = {
                'api_key_env': 'OPENROUTER_API_KEY',
                'api_url': 'https://openrouter.ai/api/v1'
            }
        if 'classification' not in config:
            config['classification'] = {
                'model': 'test-model',
                'temperature': 0.2
            }
        if 'processing' not in config:
            config['processing'] = {
                'max_body_chars': 6000
            }
        
        # Ensure API key is set in environment
        import os
        api_key_env = config['openrouter'].get('api_key_env', 'OPENROUTER_API_KEY')
        if api_key_env not in os.environ:
            os.environ[api_key_env] = 'test_api_key'
        
        # Call parent with valid config
        super().__init__(config)
        self.config = config
        self._scenario_responses: Dict[str, Dict[str, int]] = {}
        self._default_spam_score = 2
        self._default_importance_score = 7
        self._should_timeout = False
        self._should_return_invalid_json = False
        self._should_return_truncated = False
        self._response_delay = 0.0
        
    def set_default_response(self, spam_score: int = 2, importance_score: int = 7) -> None:
        """Set default response scores."""
        self._default_spam_score = spam_score
        self._default_importance_score = importance_score
        
    def set_response_for_scenario(
        self,
        scenario_id: str,
        spam_score: int,
        importance_score: int
    ) -> None:
        """
        Set response for a specific scenario.
        
        Scenarios are matched by checking if scenario_id appears in the prompt.
        
        Args:
            scenario_id: Identifier to match in prompt
            spam_score: Spam score to return
            importance_score: Importance score to return
        """
        self._scenario_responses[scenario_id] = {
            'spam_score': spam_score,
            'importance_score': importance_score
        }
        
    def set_timeout(self, should_timeout: bool = True) -> None:
        """Configure whether to simulate timeout."""
        self._should_timeout = should_timeout
        
    def set_invalid_json(self, should_return_invalid: bool = True) -> None:
        """Configure whether to return invalid JSON."""
        self._should_return_invalid_json = should_return_invalid
        
    def set_truncated_response(self, should_truncate: bool = True) -> None:
        """Configure whether to return truncated response."""
        self._should_return_truncated = should_truncate
        
    def set_response_delay(self, delay: float) -> None:
        """Set response delay in seconds (for timeout simulation)."""
        self._response_delay = delay
        
    def classify_email(
        self,
        email_content: str,
        user_prompt: Optional[str] = None,
        max_chars: Optional[int] = None,
        debug_prompt: bool = False,
        debug_uid: Optional[str] = None
    ) -> LLMResponse:
        """
        Classify email with mock response.
        
        Args:
            email_content: Email content to classify
            user_prompt: Optional user prompt
            max_chars: Optional maximum characters (ignored in mock)
            debug_prompt: If True, write the formatted prompt to a debug file (ignored in mock)
            debug_uid: Optional email UID for debug filename (ignored in mock)
            
        Returns:
            LLMResponse with scores
            
        Raises:
            LLMAPIError: If configured to timeout
            LLMResponseParseError: If configured to return invalid JSON
        """
        import time
        
        # Simulate delay
        if self._response_delay > 0:
            time.sleep(self._response_delay)
            
        # Check for timeout
        if self._should_timeout:
            raise Exception("Mock LLM timeout")
            
        # Check for scenario-based response
        prompt = user_prompt or email_content
        for scenario_id, scores in self._scenario_responses.items():
            if scenario_id.lower() in prompt.lower():
                spam_score = scores['spam_score']
                importance_score = scores['importance_score']
                break
        else:
            # Use default scores
            spam_score = self._default_spam_score
            importance_score = self._default_importance_score
            
        # Check for invalid JSON
        if self._should_return_invalid_json:
            return LLMResponse(
                spam_score=0,
                importance_score=0,
                raw_response="invalid json response"
            )
            
        # Check for truncated response
        if self._should_return_truncated:
            raw_response = '{"spam_score": ' + str(spam_score)  # Incomplete JSON
        else:
            raw_response = f'{{"spam_score": {spam_score}, "importance_score": {importance_score}}}'
            
        return LLMResponse(
            spam_score=spam_score,
            importance_score=importance_score,
            raw_response=raw_response
        )
