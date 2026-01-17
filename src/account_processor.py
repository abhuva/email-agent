"""
V4 Account Processor for isolated per-account email processing.

This module provides the AccountProcessor class that handles the complete processing
pipeline for a single account, ensuring complete state isolation between accounts.

The AccountProcessor orchestrates:
- IMAP connection management
- Email fetching
- Blacklist rule checking
- Content parsing (HTML to Markdown)
- LLM classification
- Whitelist rule application
- Note generation
- Safety interlock with cost estimation

State Isolation:
    Each AccountProcessor instance maintains its own:
    - IMAP connection (not shared)
    - Configuration (account-specific merged config)
    - Processing context (per-run state)
    - Logger (with account identifier)

Usage:
    >>> from src.account_processor import AccountProcessor
    >>> from src.config_loader import ConfigLoader
    >>> 
    >>> loader = ConfigLoader('config')
    >>> account_config = loader.load_merged_config('work')
    >>> 
    >>> processor = AccountProcessor(
    ...     account_id='work',
    ...     account_config=account_config,
    ...     imap_client_factory=create_imap_client_from_config,
    ...     llm_client=LLMClient(),
    ...     blacklist_service=load_blacklist_rules,
    ...     whitelist_service=load_whitelist_rules,
    ...     note_generator=NoteGenerator(),
    ...     parser=parse_html_content,
    ...     logger=logger
    ... )
    >>> 
    >>> processor.setup()
    >>> processor.run()
    >>> processor.teardown()
"""
import logging
import imaplib
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from dataclasses import dataclass

from src.models import EmailContext, from_imap_dict
from src.content_parser import parse_html_content
from src.rules import (
    load_blacklist_rules,
    load_whitelist_rules,
    check_blacklist,
    apply_whitelist,
    ActionEnum
)
from src.imap_client import ImapClient, IMAPConnectionError, IMAPFetchError
from src.llm_client import LLMClient, LLMResponse
from src.note_generator import NoteGenerator
from src.decision_logic import DecisionLogic, ClassificationResult
from src.progress import create_progress_bar, tqdm_write

logger = logging.getLogger(__name__)


@dataclass
class CostEstimate:
    """Cost estimation result for email processing operation."""
    email_count: int
    estimated_cost: float
    currency: str
    cost_per_email: float
    tokens_per_email: int
    model_name: str
    breakdown: Dict[str, Any]
    
    def __str__(self) -> str:
        """Format cost estimate for display."""
        return (
            f"Estimated cost: {self.currency}{self.estimated_cost:.4f} "
            f"for {self.email_count} email(s) "
            f"({self.currency}{self.cost_per_email:.4f} per email, "
            f"model: {self.model_name})"
        )


def prompt_user_confirmation(
    cost_estimate: CostEstimate,
    confirmation_callback: Optional[Callable[[str], str]] = None
) -> bool:
    """
    Prompt user for confirmation before proceeding with high-cost operation.
    
    This function displays the cost estimate and asks for explicit user confirmation.
    It can be used in CLI environments or with custom confirmation handlers.
    
    Args:
        cost_estimate: CostEstimate object with cost information
        confirmation_callback: Optional callback function for custom confirmation handling.
                             If provided, should accept a prompt string and return user input.
                             If None, uses built-in input() function.
    
    Returns:
        True if user confirmed, False if cancelled
    """
    # Display cost information
    print("\n" + "=" * 70)
    print("SAFETY INTERLOCK: Cost Estimation")
    print("=" * 70)
    print(f"Emails to process: {cost_estimate.email_count}")
    print(f"Model: {cost_estimate.model_name}")
    print(f"Estimated cost: {cost_estimate.currency}{cost_estimate.estimated_cost:.4f}")
    print(f"Cost per email: {cost_estimate.currency}{cost_estimate.cost_per_email:.4f}")
    if cost_estimate.tokens_per_email > 0:
        print(f"Estimated tokens per email: {cost_estimate.tokens_per_email:,}")
    print("=" * 70)
    print("\n⚠️  WARNING: This is a potentially high-cost operation.")
    print("Processing will make API calls that may incur charges.")
    print("=" * 70 + "\n")
    
    # Get user confirmation
    if confirmation_callback:
        response = confirmation_callback(
            "Type 'yes' to confirm and proceed, or anything else to cancel: "
        )
    else:
        response = input("Type 'yes' to confirm and proceed, or anything else to cancel: ")
    
    confirmed = response.lower().strip() == 'yes'
    
    if confirmed:
        print("✓ Confirmed. Proceeding with email processing...\n")
    else:
        print("✗ Cancelled. Email processing aborted by safety interlock.\n")
    
    return confirmed


def estimate_processing_cost(
    email_count: int,
    model_config: Dict[str, Any],
    safety_config: Optional[Dict[str, Any]] = None
) -> CostEstimate:
    """
    Estimate the cost of processing emails based on email count and model configuration.
    
    This function calculates the estimated cost using:
    - Email count (from IMAP search)
    - Model pricing (from config)
    - Average tokens per email (from config or default)
    
    Args:
        email_count: Number of emails to process
        model_config: Model configuration dictionary containing pricing info
                     Expected keys:
                     - model: Model name/identifier
                     - cost_per_1k_tokens: Cost per 1000 tokens (float)
                     - cost_per_email: Optional direct cost per email (overrides token-based)
        safety_config: Optional safety interlock configuration
                      Expected keys:
                      - average_tokens_per_email: Average tokens per email (default: 2000)
                      - currency: Currency symbol (default: '$')
    
    Returns:
        CostEstimate object with cost breakdown and formatted display string
    
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    if email_count < 0:
        raise ValueError(f"Email count must be non-negative, got {email_count}")
    
    if email_count == 0:
        # Return zero cost for zero emails
        model_name = model_config.get('model', 'unknown')
        currency = (safety_config or {}).get('currency', '$')
        return CostEstimate(
            email_count=0,
            estimated_cost=0.0,
            currency=currency,
            cost_per_email=0.0,
            tokens_per_email=0,
            model_name=model_name,
            breakdown={'total_emails': 0, 'total_tokens': 0, 'cost': 0.0}
        )
    
    # Get model name
    model_name = model_config.get('model', 'unknown')
    
    # Get safety config defaults
    safety = safety_config or {}
    average_tokens_per_email = safety.get('average_tokens_per_email', 2000)
    currency = safety.get('currency', '$')
    
    # Check if direct cost_per_email is specified (takes precedence)
    if 'cost_per_email' in model_config:
        cost_per_email = float(model_config['cost_per_email'])
        total_cost = email_count * cost_per_email
        
        return CostEstimate(
            email_count=email_count,
            estimated_cost=total_cost,
            currency=currency,
            cost_per_email=cost_per_email,
            tokens_per_email=0,  # Not applicable for direct pricing
            model_name=model_name,
            breakdown={
                'total_emails': email_count,
                'pricing_model': 'direct_per_email',
                'cost_per_email': cost_per_email,
                'total_cost': total_cost
            }
        )
    
    # Token-based pricing
    if 'cost_per_1k_tokens' not in model_config:
        raise ValueError(
            f"Model config must contain either 'cost_per_email' or 'cost_per_1k_tokens', "
            f"got: {list(model_config.keys())}"
        )
    
    cost_per_1k_tokens = float(model_config['cost_per_1k_tokens'])
    total_tokens = email_count * average_tokens_per_email
    total_cost = (total_tokens / 1000.0) * cost_per_1k_tokens
    cost_per_email = total_cost / email_count if email_count > 0 else 0.0
    
    return CostEstimate(
        email_count=email_count,
        estimated_cost=total_cost,
        currency=currency,
        cost_per_email=cost_per_email,
        tokens_per_email=average_tokens_per_email,
        model_name=model_name,
        breakdown={
            'total_emails': email_count,
            'pricing_model': 'token_based',
            'tokens_per_email': average_tokens_per_email,
            'total_tokens': total_tokens,
            'cost_per_1k_tokens': cost_per_1k_tokens,
            'total_cost': total_cost
        }
    )


class AccountProcessorError(Exception):
    """Base exception for AccountProcessor errors."""
    pass


class AccountProcessorSetupError(AccountProcessorError):
    """Raised when AccountProcessor setup fails."""
    pass


class AccountProcessorRunError(AccountProcessorError):
    """Raised when AccountProcessor run fails."""
    pass


class ConfigurableImapClient(ImapClient):
    """
    Configurable IMAP client that accepts config directly instead of using settings facade.
    
    This class extends ImapClient to support account-specific configurations for V4.
    It overrides the connect() method to use config passed at construction time.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize configurable IMAP client with account-specific config.
        
        Args:
            config: Configuration dictionary containing IMAP settings under 'imap' key
        """
        super().__init__()
        self._account_config = config
        self._imap_config = config.get('imap', {})
        
        # Validate required fields
        required_fields = ['server', 'port', 'username']
        missing_fields = [field for field in required_fields if field not in self._imap_config]
        if missing_fields:
            raise AccountProcessorSetupError(
                f"Missing required IMAP configuration fields: {missing_fields}"
            )
    
    def connect(self) -> None:
        """
        Establish connection to IMAP server using credentials from config.
        
        Overrides parent connect() to use account-specific config instead of settings facade.
        
        Raises:
            IMAPConnectionError: If connection or authentication fails
            AccountProcessorSetupError: If required configuration is missing
        """
        if self._connected:
            self.logger.warning("Already connected to IMAP server")
            return
        
        try:
            # Get configuration from account config (not settings facade)
            server = self._imap_config['server']
            port = self._imap_config['port']
            username = self._imap_config['username']
            
            # Get password (from config or environment variable)
            password = self._imap_config.get('password')
            if not password:
                # Try password_env
                password_env = self._imap_config.get('password_env')
                if password_env:
                    import os
                    password = os.getenv(password_env)
                    if not password:
                        raise AccountProcessorSetupError(
                            f"Password environment variable '{password_env}' not set"
                        )
                else:
                    raise AccountProcessorSetupError(
                        "IMAP password not provided (neither 'password' nor 'password_env' in config)"
                    )
            
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
    
    def count_unprocessed_emails(self, force_reprocess: bool = False) -> tuple[int, List[str]]:
        """
        Count unprocessed emails using IMAP.search without fetching.
        
        This method performs a search to get the list of matching email UIDs
        and returns the count and UID list. This is used for cost estimation
        before actual email fetching.
        
        Args:
            force_reprocess: If True, include processed emails in search
            
        Returns:
            Tuple of (email_count, list_of_uids)
            - email_count: Number of matching emails
            - list_of_uids: List of email UIDs (as strings)
            
        Raises:
            IMAPFetchError: If search fails
        """
        self._ensure_connected()
        
        try:
            # Get query and processed_tag from account config
            user_query = self._imap_config.get('query', 'ALL')
            processed_tag = self._imap_config.get('processed_tag', 'AIProcessed')
            
            if force_reprocess:
                logger.info(f"Counting emails (force-reprocess mode, query: {user_query})")
                search_query = user_query
            else:
                logger.info(f"Counting unprocessed emails (query: {user_query}, exclude: {processed_tag})")
                search_query = f'({user_query} NOT KEYWORD "{processed_tag}")'
            
            # Search for UIDs (no fetching)
            typ, data = self._imap.uid('SEARCH', None, search_query)
            
            if typ != 'OK':
                raise IMAPFetchError(f"IMAP search failed: {data}")
            
            if not data or not data[0]:
                logger.info("No unprocessed emails found")
                return (0, [])
            
            # Parse UIDs
            uid_bytes = data[0]
            if isinstance(uid_bytes, bytes):
                uid_str = uid_bytes.decode('utf-8')
            else:
                uid_str = str(uid_bytes)
            
            uids = [uid.strip() for uid in uid_str.split() if uid.strip()]
            
            if not uids:
                logger.info("No emails found" if force_reprocess else "No unprocessed emails found")
                return (0, [])
            
            logger.info(f"Found {len(uids)} email(s)" + (" (including processed)" if force_reprocess else ""))
            return (len(uids), uids)
            
        except IMAPFetchError:
            raise
        except Exception as e:
            error_msg = f"Error counting unprocessed emails: {e}"
            logger.error(error_msg)
            raise IMAPFetchError(error_msg) from e
    
    def get_unprocessed_emails(self, max_emails: Optional[int] = None, force_reprocess: bool = False, uids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Retrieve unprocessed emails using account-specific query and processed_tag.
        
        Overrides parent method to use account-specific config instead of settings facade.
        
        Args:
            max_emails: Maximum number of emails to fetch
            force_reprocess: If True, include processed emails
            uids: Optional pre-fetched list of UIDs to use (for safety interlock flow)
        """
        self._ensure_connected()
        
        try:
            # If UIDs are provided (from safety interlock), use them directly
            if uids is not None:
                logger.info(f"Fetching {len(uids)} email(s) using provided UIDs")
                # Limit number of emails if specified
                if max_emails and len(uids) > max_emails:
                    logger.info(f"Limiting to {max_emails} emails (found {len(uids)})")
                    uids = uids[:max_emails]
            else:
                # Get query and processed_tag from account config
                user_query = self._imap_config.get('query', 'ALL')
                processed_tag = self._imap_config.get('processed_tag', 'AIProcessed')
                max_emails_per_run = max_emails or self._account_config.get('processing', {}).get('max_emails_per_run')
                
                if force_reprocess:
                    logger.info(f"Searching for emails (force-reprocess mode, query: {user_query})")
                    search_query = user_query
                else:
                    logger.info(f"Searching for unprocessed emails (query: {user_query}, exclude: {processed_tag})")
                    search_query = f'({user_query} NOT KEYWORD "{processed_tag}")'
                
                # Search for UIDs
                typ, data = self._imap.uid('SEARCH', None, search_query)
                
                if typ != 'OK':
                    raise IMAPFetchError(f"IMAP search failed: {data}")
                
                if not data or not data[0]:
                    logger.info("No unprocessed emails found")
                    return []
                
                # Parse UIDs
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
            
            # Fetch emails with progress bar
            emails = []
            # Get account identifier from config (username as fallback)
            account_name = self._imap_config.get('username', 'account')
            for uid in create_progress_bar(
                uids,
                desc=f"Fetching emails ({account_name})",
                unit="emails"
            ):
                try:
                    email_data = self.get_email_by_uid(uid)
                    emails.append(email_data)
                except IMAPFetchError as e:
                    tqdm_write(f"Skipping email UID {uid} due to fetch error: {e}")
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


def create_imap_client_from_config(config: Dict[str, Any]) -> ImapClient:
    """
    Factory function to create an IMAP client from a configuration dictionary.
    
    This function extracts IMAP settings from the config dict and creates
    a ConfigurableImapClient instance that can work with account-specific configs.
    
    Args:
        config: Configuration dictionary containing IMAP settings under 'imap' key.
               Expected structure:
               {
                   'imap': {
                       'server': str,
                       'port': int,
                       'username': str,
                       'password': str,  # or 'password_env': str for env var
                       'query': str,
                       'processed_tag': str
                   }
               }
    
    Returns:
        ConfigurableImapClient instance (not connected yet)
    
    Raises:
        AccountProcessorSetupError: If required IMAP config is missing
    
    Note:
        The returned client is not connected. Call connect() on it separately.
    """
    return ConfigurableImapClient(config)


class AccountProcessor:
    """
    Isolated per-account email processing pipeline.
    
    This class handles the complete email processing pipeline for a single account,
    ensuring complete state isolation. Each instance maintains its own:
    - IMAP connection (not shared with other accounts)
    - Configuration (account-specific merged config)
    - Processing context (per-run state)
    - Logger (with account identifier)
    
    The processing pipeline follows this flow:
    1. Blacklist Check → DROP, RECORD, or PASS
    2. Content Parsing → HTML to Markdown (with fallback)
    3. LLM Processing → Classification and scoring
    4. Whitelist Modifiers → Score boost and tag addition
    5. Note Generation → Create Obsidian notes
    
    State Isolation:
        - All state is stored on self (instance variables)
        - No class variables or shared singletons
        - Configuration is immutable (passed in, not modified)
        - IMAP connection is per-instance
        - Processing context is per-run
    
    Example:
        >>> processor = AccountProcessor(
        ...     account_id='work',
        ...     account_config=config,
        ...     imap_client_factory=create_imap_client_from_config,
        ...     llm_client=LLMClient(),
        ...     blacklist_service=load_blacklist_rules,
        ...     whitelist_service=load_whitelist_rules,
        ...     note_generator=NoteGenerator(),
        ...     parser=parse_html_content,
        ...     logger=logger
        ... )
        >>> processor.setup()
        >>> processor.run()
        >>> processor.teardown()
    """
    
    def __init__(
        self,
        account_id: str,
        account_config: Dict[str, Any],
        imap_client_factory: Callable[[Dict[str, Any]], ImapClient],
        llm_client: LLMClient,
        blacklist_service: Callable[[str], List],
        whitelist_service: Callable[[str], List],
        note_generator: NoteGenerator,
        parser: Callable[[str, str], tuple],
        decision_logic: Optional[DecisionLogic] = None,
        logger: Optional[logging.Logger] = None,
        confirmation_callback: Optional[Callable[[str], str]] = None
    ):
        """
        Initialize AccountProcessor with account-specific configuration and dependencies.
        
        All dependencies are injected to ensure:
        - Testability (can mock dependencies)
        - State isolation (no shared mutable state)
        - Flexibility (can swap implementations)
        
        Args:
            account_id: Unique identifier for this account (e.g., 'work', 'personal')
            account_config: Merged configuration dictionary for this account
                           (from ConfigLoader.load_merged_config)
            imap_client_factory: Factory function to create IMAP clients from config
            llm_client: LLM client instance for email classification
            blacklist_service: Function to load blacklist rules (e.g., load_blacklist_rules)
            whitelist_service: Function to load whitelist rules (e.g., load_whitelist_rules)
            note_generator: Note generator instance for creating Obsidian notes
            parser: Content parser function (e.g., parse_html_content)
            logger: Optional logger instance (creates one if not provided)
        
        Note:
            The account_config should be immutable (not modified after construction).
            All account-specific state is stored on self to ensure isolation.
        """
        # Account identification
        self.account_id = account_id
        
        # Configuration (immutable - passed in, not modified)
        self.config = account_config
        
        # Dependencies (injected for testability and isolation)
        self._imap_client_factory = imap_client_factory
        self.llm_client = llm_client
        self._blacklist_service = blacklist_service
        self._whitelist_service = whitelist_service
        self.note_generator = note_generator
        self.parser = parser
        self.decision_logic = decision_logic or DecisionLogic()
        
        # Logger (with account identifier)
        if logger is None:
            logger = logging.getLogger(f"{__name__}.{account_id}")
        self.logger = logger
        
        # Confirmation callback (for testing/mocking)
        self._confirmation_callback = confirmation_callback
        
        # Runtime state (per-instance, not shared)
        self._imap_conn: Optional[ImapClient] = None
        self._processing_context: Dict[str, Any] = {}
        
        # Processing results (per-run)
        self._processed_emails: List[EmailContext] = []
        self._dropped_emails: List[EmailContext] = []
        self._recorded_emails: List[EmailContext] = []
        
        self.logger.info(f"AccountProcessor initialized for account: {account_id}")
    
    def setup(self) -> None:
        """
        Set up resources required for processing this account.
        
        This method:
        - Establishes IMAP connection using account-specific credentials
        - Loads account-specific blacklist/whitelist rules
        - Initializes processing context
        
        Raises:
            AccountProcessorSetupError: If setup fails (e.g., IMAP connection fails)
        """
        self.logger.info(f"Setting up AccountProcessor for account: {self.account_id}")
        
        try:
            # Create IMAP client using factory (with account-specific config)
            self._imap_conn = self._imap_client_factory(self.config)
            
            # Connect to IMAP server using account-specific credentials
            self._imap_conn.connect()
            
            self.logger.info(f"IMAP connection established for account: {self.account_id}")
            
            # Initialize processing context
            self._processing_context = {
                'account_id': self.account_id,
                'start_time': None,  # Set in run()
                'emails_fetched': 0,
                'emails_processed': 0,
                'emails_dropped': 0,
                'emails_recorded': 0
            }
            
            # Reset per-run results
            self._processed_emails = []
            self._dropped_emails = []
            self._recorded_emails = []
            
            self.logger.info(f"AccountProcessor setup complete for account: {self.account_id}")
            
        except IMAPConnectionError as e:
            error_msg = f"IMAP connection failed for account {self.account_id}: {e}"
            self.logger.error(error_msg)
            raise AccountProcessorSetupError(error_msg) from e
        except Exception as e:
            error_msg = f"Setup failed for account {self.account_id}: {e}"
            self.logger.error(error_msg)
            raise AccountProcessorSetupError(error_msg) from e
    
    def run(
        self,
        force_reprocess: bool = False,
        uid: Optional[str] = None,
        max_emails: Optional[int] = None,
        debug_prompt: bool = False
    ) -> None:
        """
        Execute the processing pipeline for this account.
        
        This method assumes setup() has been called successfully. It:
        1. Counts emails using IMAP.search (safety interlock)
        2. Estimates cost based on email count and model config
        3. Prompts user for confirmation if cost exceeds threshold
        4. Fetches emails from IMAP (only if confirmed)
        5. For each email:
           - Checks blacklist rules
           - Parses content (HTML to Markdown)
           - Calls LLM for classification
           - Applies whitelist rules
           - Generates notes
        
        Args:
            force_reprocess: If True, include processed emails in search
            uid: Optional specific email UID to process (if provided, only this email is processed)
            max_emails: Optional maximum number of emails to process (overrides config)
            debug_prompt: If True, write classification prompts to debug files
        
        Raises:
            AccountProcessorRunError: If run fails critically
        """
        if self._imap_conn is None:
            raise AccountProcessorRunError(
                f"AccountProcessor not set up for account {self.account_id}. Call setup() first."
            )
        
        self.logger.info(f"Starting processing run for account: {self.account_id}")
        
        # Update processing context
        import time
        self._processing_context['start_time'] = time.time()
        
        try:
            # If UID is specified, process only that email (skip safety interlock)
            if uid:
                self.logger.info(f"Processing specific email UID: {uid}")
                try:
                    email_data = self._imap_conn.get_email_by_uid(uid)
                    if email_data:
                        self._process_message(email_data, debug_prompt=debug_prompt)
                        self.logger.info(f"Successfully processed email UID {uid}")
                    else:
                        self.logger.warning(f"Email UID {uid} not found")
                except Exception as e:
                    self.logger.error(f"Failed to process email UID {uid}: {e}")
                    raise AccountProcessorRunError(f"Failed to process email UID {uid}: {e}") from e
                return
            
            # Safety Interlock: Step 1 - Count emails before fetching
            self.logger.info("Safety interlock: Counting emails before processing...")
            email_count, uids = self._imap_conn.count_unprocessed_emails(force_reprocess=force_reprocess)
            
            if email_count == 0:
                self.logger.info("No emails to process. Exiting.")
                return
            
            # Safety Interlock: Step 2 - Estimate cost
            safety_config = self.config.get('safety_interlock', {})
            model_config = self.config.get('classification', {})
            
            # Check if safety interlock is enabled
            interlock_enabled = safety_config.get('enabled', True)
            cost_threshold = safety_config.get('cost_threshold', 0.0)
            skip_below_threshold = safety_config.get('skip_confirmation_below_threshold', False)
            
            if interlock_enabled:
                try:
                    cost_estimate = estimate_processing_cost(
                        email_count=email_count,
                        model_config=model_config,
                        safety_config=safety_config
                    )
                    
                    self.logger.info(f"Cost estimate: {cost_estimate}")
                    
                    # Safety Interlock: Step 3 - Check threshold and prompt for confirmation
                    needs_confirmation = True
                    if skip_below_threshold and cost_estimate.estimated_cost <= cost_threshold:
                        self.logger.info(
                            f"Cost ({cost_estimate.currency}{cost_estimate.estimated_cost:.4f}) "
                            f"is below threshold ({cost_estimate.currency}{cost_threshold:.4f}). "
                            f"Skipping confirmation."
                        )
                        needs_confirmation = False
                    
                    if needs_confirmation:
                        # Safety Interlock: Step 4 - Prompt user for confirmation
                        confirmed = prompt_user_confirmation(
                            cost_estimate,
                            confirmation_callback=self._confirmation_callback
                        )
                        
                        if not confirmed:
                            self.logger.warning(
                                f"Processing aborted by safety interlock for account {self.account_id}. "
                                f"User cancelled operation."
                            )
                            return
                    
                except (ValueError, KeyError) as e:
                    self.logger.warning(
                        f"Cost estimation failed: {e}. "
                        f"Proceeding without cost check (safety interlock may be misconfigured)."
                    )
                    # Continue without cost check if estimation fails
            else:
                self.logger.info("Safety interlock is disabled. Proceeding without cost check.")
            
            # Safety Interlock: Step 5 - Fetch emails using pre-counted UIDs
            # Use max_emails parameter if provided, otherwise use config
            max_emails_config = max_emails if max_emails is not None else self.config.get('processing', {}).get('max_emails_per_run')
            emails = self._imap_conn.get_unprocessed_emails(
                max_emails=max_emails_config,
                force_reprocess=force_reprocess,
                uids=uids  # Use pre-counted UIDs to avoid re-searching
            )
            self._processing_context['emails_fetched'] = len(emails)
            
            self.logger.info(
                f"Fetched {len(emails)} email(s) for account {self.account_id}"
            )
            
            # Process each email with progress bar
            for email_dict in create_progress_bar(
                emails,
                desc=f"Processing emails ({self.account_id})",
                unit="emails"
            ):
                try:
                    self._process_message(email_dict, debug_prompt=debug_prompt)
                except Exception as e:
                    # Log error but continue processing other emails
                    error_msg = (
                        f"Error processing email UID {email_dict.get('uid', 'unknown')} "
                        f"for account {self.account_id}: {e}"
                    )
                    tqdm_write(error_msg)
                    self.logger.error(error_msg, exc_info=True)
                    continue
            
            # Log summary
            self._log_processing_summary()
            
        except Exception as e:
            error_msg = f"Processing run failed for account {self.account_id}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise AccountProcessorRunError(error_msg) from e
    
    def teardown(self) -> None:
        """
        Clean up resources allocated during setup() and run().
        
        This method:
        - Closes IMAP connection
        - Clears processing context
        - Resets per-run state
        
        Note:
            Exceptions during teardown are logged but not raised to ensure
            cleanup always completes.
        """
        self.logger.info(f"Tearing down AccountProcessor for account: {self.account_id}")
        
        # Close IMAP connection
        if self._imap_conn is not None:
            try:
                self._imap_conn.disconnect()
                self.logger.info(f"IMAP connection closed for account: {self.account_id}")
            except Exception as e:
                self.logger.warning(
                    f"Error closing IMAP connection for account {self.account_id}: {e}"
                )
            finally:
                self._imap_conn = None
        
        # Clear processing context
        self._processing_context = {}
        
        # Note: We keep processed/dropped/recorded lists for potential inspection
        # but they're reset on next setup()
        
        self.logger.info(f"AccountProcessor teardown complete for account: {self.account_id}")
    
    def _fetch_emails(self) -> List[Dict[str, Any]]:
        """
        Fetch emails from IMAP server for this account.
        
        Returns:
            List of email dictionaries from IMAP client
        
        Raises:
            AccountProcessorRunError: If email fetching fails
        """
        try:
            # Get max_emails from config
            max_emails = self.config.get('processing', {}).get('max_emails_per_run')
            
            # Fetch unprocessed emails
            emails = self._imap_conn.get_unprocessed_emails(max_emails=max_emails)
            return emails
            
        except IMAPFetchError as e:
            error_msg = f"Failed to fetch emails for account {self.account_id}: {e}"
            self.logger.error(error_msg)
            raise AccountProcessorRunError(error_msg) from e
    
    def _process_message(self, email_dict: Dict[str, Any], debug_prompt: bool = False) -> None:
        """
        Process a single email through the complete pipeline.
        
        Pipeline stages:
        1. Create EmailContext from IMAP data
        2. Check blacklist rules
        3. Parse content (HTML to Markdown)
        4. Call LLM for classification
        5. Apply whitelist rules
        6. Generate note
        
        Args:
            email_dict: Email dictionary from IMAP client
            debug_prompt: If True, write classification prompts to debug files
        """
        # Create EmailContext from IMAP data
        email_context = from_imap_dict(email_dict)
        uid = email_context.uid
        
        self.logger.debug(f"Processing email UID {uid} for account {self.account_id}")
        
        # Stage 1: Blacklist Check
        blacklist_action = self._check_blacklist(email_context)
        
        if blacklist_action == ActionEnum.DROP:
            self.logger.info(f"Email UID {uid} dropped by blacklist for account {self.account_id}")
            email_context.result_action = "DROPPED"
            self._dropped_emails.append(email_context)
            return
        
        if blacklist_action == ActionEnum.RECORD:
            self.logger.info(f"Email UID {uid} recorded by blacklist for account {self.account_id}")
            email_context.result_action = "RECORDED"
            # Generate raw markdown without AI
            self._generate_raw_note(email_context)
            self._recorded_emails.append(email_context)
            return
        
        # Stage 2: Content Parsing
        self._parse_content(email_context)
        
        # Stage 3: LLM Classification
        llm_response = self._classify_with_llm(email_context, debug_prompt=debug_prompt)
        if not llm_response:
            self.logger.warning(
                f"LLM classification failed for UID {uid}, skipping note generation"
            )
            return
        
        # Store LLM scores
        email_context.llm_score = llm_response.importance_score
        
        # Apply decision logic to get ClassificationResult
        classification_result = self.decision_logic.classify(llm_response)
        
        # Stage 4: Whitelist Rules (applied after LLM, before note generation)
        self._apply_whitelist(email_context)
        
        # Update classification result with whitelist-adjusted score
        if email_context.llm_score != llm_response.importance_score:
            # Re-run decision logic with adjusted score
            adjusted_llm_response = LLMResponse(
                spam_score=llm_response.spam_score,
                importance_score=int(email_context.llm_score),
                raw_response=llm_response.raw_response
            )
            classification_result = self.decision_logic.classify(adjusted_llm_response)
        
        # Stage 4.5: Summarization (if email is important and summarization is configured)
        self._generate_summary_if_needed(email_context, classification_result, uid)
        
        # Stage 5: Note Generation
        self._generate_note(email_context, classification_result)
        
        # Mark as processed
        email_context.result_action = "PROCESSED"
        self._processed_emails.append(email_context)
        self._processing_context['emails_processed'] += 1
        
        # Set IMAP flag
        self._mark_email_processed(uid)
        
        # Log to structured analytics (if available)
        self._log_email_processed(uid, classification_result, success=True)
        
        self.logger.info(
            f"Successfully processed email UID {uid} for account {self.account_id}"
        )
    
    def _check_blacklist(self, email_context: EmailContext) -> ActionEnum:
        """
        Check email against blacklist rules.
        
        Args:
            email_context: EmailContext to check
        
        Returns:
            ActionEnum indicating action to take (DROP, RECORD, or PASS)
        """
        # Load blacklist rules
        # TODO: Get blacklist path from config
        blacklist_path = Path("config/blacklist.yaml")
        rules = self._blacklist_service(str(blacklist_path))
        
        # Check against rules
        return check_blacklist(email_context, rules)
    
    def _parse_content(self, email_context: EmailContext) -> None:
        """
        Parse email content (HTML to Markdown).
        
        Updates email_context.parsed_body and email_context.is_html_fallback.
        
        Args:
            email_context: EmailContext to parse
        """
        html_body = email_context.raw_html or ""
        plain_text = email_context.raw_text or ""
        
        parsed_content, is_fallback = self.parser(html_body, plain_text)
        
        email_context.parsed_body = parsed_content
        email_context.is_html_fallback = is_fallback
        
        if is_fallback:
            self.logger.debug(
                f"HTML parsing failed for UID {email_context.uid}, "
                f"using plain text fallback for account {self.account_id}"
            )
    
    def _classify_with_llm(self, email_context: EmailContext, debug_prompt: bool = False) -> Optional[LLMResponse]:
        """
        Classify email using LLM.
        
        Args:
            email_context: EmailContext to classify
            debug_prompt: If True, write classification prompts to debug files
        
        Returns:
            LLMResponse if classification succeeds, None otherwise
        """
        try:
            # Build email content for LLM
            email_content = email_context.parsed_body or email_context.raw_text or ""
            
            # Call LLM
            llm_response = self.llm_client.classify_email(
                email_content=email_content,
                user_prompt=None,  # TODO: Load prompt from config if needed
                max_chars=None,  # TODO: Get from config
                debug_prompt=debug_prompt,
                debug_uid=email_context.uid
            )
            
            self.logger.debug(
                f"LLM classification for UID {email_context.uid} "
                f"(account {self.account_id}): "
                f"spam={llm_response.spam_score}, "
                f"importance={llm_response.importance_score}"
            )
            
            return llm_response
            
        except Exception as e:
            self.logger.error(
                f"LLM classification failed for UID {email_context.uid} "
                f"(account {self.account_id}): {e}",
                exc_info=True
            )
            return None
    
    def _apply_whitelist(self, email_context: EmailContext) -> None:
        """
        Apply whitelist rules to email.
        
        Updates email_context.whitelist_boost and email_context.whitelist_tags.
        
        Args:
            email_context: EmailContext to apply whitelist to
        """
        if not email_context.is_scored():
            # Can't apply whitelist without a score
            return
        
        # Load whitelist rules
        # TODO: Get whitelist path from config
        whitelist_path = Path("config/whitelist.yaml")
        rules = self._whitelist_service(str(whitelist_path))
        
        # Apply whitelist rules
        current_score = email_context.llm_score or 0.0
        new_score, tags = apply_whitelist(email_context, rules, current_score)
        
        # Update email context
        email_context.llm_score = new_score
        email_context.whitelist_boost = new_score - current_score
        email_context.whitelist_tags = tags

        if tags or email_context.whitelist_boost != 0.0:
            self.logger.debug(
                f"Whitelist applied to UID {email_context.uid} "
                f"(account {self.account_id}): "
                f"boost={email_context.whitelist_boost}, tags={tags}"
            )
    
    def _generate_summary_if_needed(
        self,
        email_context: EmailContext,
        classification_result: ClassificationResult,
        uid: str
    ) -> None:
        """
        Generate summary for email if summarization is required.
        
        This method:
        - Checks if email tags match summarization_tags from config
        - Calls LLM to generate summary if required
        - Stores summary result in email_context for template rendering
        - Handles errors gracefully (summarization failure doesn't break pipeline)
        
        Args:
            email_context: EmailContext to check and potentially summarize
            classification_result: Classification result with tags
            uid: Email UID for logging
        """
        try:
            # Get summarization tags from config
            summarization_tags = self.config.get('processing', {}).get('summarization_tags')
            if not summarization_tags or not isinstance(summarization_tags, list):
                self.logger.debug(
                    f"Summarization not configured for account {self.account_id}, skipping"
                )
                return
            
            # Get tags from classification result
            email_tags = classification_result.to_frontmatter_dict().get('tags', [])
            
            # Check if email should be summarized
            from src.summarization import should_summarize_email
            if not should_summarize_email(email_tags, summarization_tags):
                reason = f"tags {email_tags} do not match summarization_tags {summarization_tags}"
                self.logger.debug(f"Summarization not required for UID {uid}: {reason}")
                return
            
            self.logger.info(
                f"Summarization required for email UID {uid} "
                f"(account {self.account_id}, tags: {email_tags})"
            )
            
            # Get summarization prompt path from config
            summarization_prompt_path = self.config.get('paths', {}).get('summarization_prompt_path')
            
            # Load summarization prompt
            from src.summarization import load_summarization_prompt
            prompt = load_summarization_prompt(summarization_prompt_path)
            
            if not prompt:
                self.logger.warning(
                    f"Summarization required but prompt failed to load "
                    f"(path: {summarization_prompt_path}) for UID {uid}"
                )
                return
            
            # Create email dict for summarization (needs email content)
            email_data = {
                'uid': email_context.uid,
                'subject': email_context.subject,
                'from': email_context.sender,
                'body': email_context.parsed_body or email_context.raw_text or '',
                'html_body': email_context.raw_html or '',
                'date': email_context.date or '',
                'to': email_context.to,
                'tags': email_tags
            }
            
            # Create OpenRouter client from config for summarization
            try:
                from src.openrouter_client import OpenRouterClient
                import os
                
                openrouter_config = self.config.get('openrouter', {})
                api_key_env = openrouter_config.get('api_key_env', 'OPENROUTER_API_KEY')
                api_url = openrouter_config.get('api_url', 'https://openrouter.ai/api/v1')
                
                api_key = os.getenv(api_key_env)
                if not api_key:
                    self.logger.warning(
                        f"OpenRouter API key not found (env: {api_key_env}), "
                        f"skipping summarization for UID {uid}"
                    )
                    return
                
                openrouter_client = OpenRouterClient(api_key, api_url)
            except Exception as e:
                self.logger.warning(
                    f"Failed to create OpenRouter client for summarization: {e}"
                )
                return
            
            # Generate summary using LLM
            try:
                from src.email_summarization import generate_email_summary
                summarization_result = {
                    'summarize': True,
                    'prompt': prompt,
                    'reason': None
                }
                
                summary_result = generate_email_summary(
                    email_data,
                    openrouter_client,
                    summarization_result
                )
                
                # Store summary result in email_context for template rendering
                # We'll add it to email_data dict in _generate_note
                email_context.summary = summary_result
                
                if summary_result.get('success', False):
                    summary_text = summary_result.get('summary', '')
                    self.logger.info(
                        f"Successfully generated summary for email UID {uid} "
                        f"({len(summary_text)} chars, account {self.account_id})"
                    )
                else:
                    error = summary_result.get('error', 'unknown')
                    self.logger.warning(
                        f"Summary generation failed for email UID {uid} "
                        f"(account {self.account_id}): {error}"
                    )
                    
            except Exception as e:
                # Graceful degradation - log but continue
                self.logger.error(
                    f"Error generating summary for email UID {uid} "
                    f"(account {self.account_id}): {e}",
                    exc_info=True
                )
                email_context.summary = {
                    'success': False,
                    'summary': '',
                    'action_items': [],
                    'priority': 'medium',
                    'error': f'summary_generation_error: {str(e)}'
                }
                
        except Exception as e:
            # Never let summarization check break the pipeline
            self.logger.error(
                f"Unexpected error in summarization check for UID {uid} "
                f"(account {self.account_id}): {e}",
                exc_info=True
            )
            # Don't set summary - template will handle missing summary gracefully
    
    def _generate_note(
        self,
        email_context: EmailContext,
        classification_result: ClassificationResult
    ) -> None:
        """
        Generate note for processed email.
        
        Args:
            email_context: EmailContext to generate note for
            classification_result: ClassificationResult from decision logic
        """
        try:
            # Convert EmailContext to email_data dict for note generator
            # Include all extracted metadata (date, to, cc, message_id)
            email_data = {
                'uid': email_context.uid,
                'subject': email_context.subject,
                'from': email_context.sender,
                'body': email_context.parsed_body or email_context.raw_text or '',
                'html_body': email_context.raw_html or '',
                'date': email_context.date or '',  # Use extracted date (empty string if None)
                'to': email_context.to,  # Use extracted recipients
                'cc': email_context.cc,  # Use extracted CC recipients
                'message_id': email_context.message_id,  # Use extracted Message-ID
            }
            
            # Add summary if available (from summarization step)
            if email_context.summary:
                email_data['summary'] = email_context.summary
            
            # Generate note using note generator
            note_content = self.note_generator.generate_note(
                email_data=email_data,
                classification_result=classification_result
            )
            
            # Write note to file system with account-specific subdirectory
            self._write_note_to_disk(
                note_content=note_content,
                email_subject=email_context.subject,
                email_uid=email_context.uid,
                email_date=email_context.date  # Pass date for file timestamp
            )
            
        except Exception as e:
            self.logger.error(
                f"Note generation failed for UID {email_context.uid} "
                f"(account {self.account_id}): {e}",
                exc_info=True
            )
    
    def _generate_raw_note(self, email_context: EmailContext) -> None:
        """
        Generate raw markdown note without AI classification.
        
        Args:
            email_context: EmailContext to generate note for
        """
        try:
            # Parse content for raw note
            self._parse_content(email_context)
            
            # Create email_data for raw note with all metadata
            email_data = {
                'uid': email_context.uid,
                'subject': email_context.subject,
                'from': email_context.sender,
                'body': email_context.parsed_body or email_context.raw_text or '',
                'html_body': email_context.raw_html or '',
                'date': email_context.date or '',  # Use extracted date
                'to': email_context.to,  # Use extracted recipients
                'cc': email_context.cc,  # Use extracted CC recipients
                'message_id': email_context.message_id,  # Use extracted Message-ID
            }
            
            # Generate note without classification result (raw markdown)
            note_content = self.note_generator.generate_note(
                email_data=email_data,
                classification_result=None  # No AI classification for raw notes
            )
            
            # Write note to file system with account-specific subdirectory
            self._write_note_to_disk(
                note_content=note_content,
                email_subject=email_context.subject,
                email_uid=email_context.uid,
                email_date=email_context.date  # Pass date for file timestamp
            )
            
        except Exception as e:
            self.logger.error(
                f"Raw note generation failed for UID {email_context.uid} "
                f"(account {self.account_id}): {e}",
                exc_info=True
            )
    
    def _write_note_to_disk(
        self,
        note_content: str,
        email_subject: str,
        email_uid: str,
        email_date: Optional[str] = None
    ) -> None:
        """
        Write note to file system with account-specific subdirectory.
        
        Creates a subdirectory in the Obsidian vault named after the account
        (e.g., 'info-nica' for account_id 'info.nica') and writes the note there.
        
        Args:
            note_content: Generated note content (Markdown)
            email_subject: Email subject for filename generation
            email_uid: Email UID for logging
            email_date: Optional email date string (RFC 2822 format) for file timestamp
        """
        from src.obsidian_note_creation import write_obsidian_note
        from src.obsidian_utils import InvalidPathError, WritePermissionError, FileWriteError
        from src.dry_run import is_dry_run
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime
        
        try:
            # Get vault path from config
            vault_path = self.config.get('paths', {}).get('obsidian_vault')
            if not vault_path:
                self.logger.error(
                    f"Cannot write note for UID {email_uid}: "
                    f"obsidian_vault not configured in paths"
                )
                return
            
            # Create account-specific subdirectory name
            # Convert account_id (e.g., 'info.nica') to subdirectory name (e.g., 'info-nica')
            account_subdir = self.account_id.replace('.', '-')
            account_vault_path = Path(vault_path) / account_subdir
            
            # Check if in dry-run mode
            dry_run_mode = is_dry_run()
            
            if dry_run_mode:
                self.logger.info(
                    f"[DRY RUN] Would write note for UID {email_uid} "
                    f"to {account_vault_path}"
                )
            else:
                # Ensure account subdirectory exists
                account_vault_path.mkdir(parents=True, exist_ok=True)
                self.logger.debug(
                    f"Using account-specific vault path: {account_vault_path}"
                )
            
            # Parse email date for file timestamp (use email date if available)
            timestamp = None
            if email_date:
                try:
                    # Parse RFC 2822 date format (e.g., "Wed, 13 Sep 2023 14:34:53 +0200")
                    timestamp = parsedate_to_datetime(email_date)
                    # Convert to UTC if timezone-aware
                    if timestamp.tzinfo:
                        timestamp = timestamp.astimezone(timezone.utc)
                    self.logger.debug(f"Using email date for timestamp: {timestamp}")
                except (ValueError, TypeError) as e:
                    self.logger.warning(
                        f"Failed to parse email date '{email_date}': {e}, using current time"
                    )
                    timestamp = datetime.now(timezone.utc)
            else:
                # No email date available, use current time
                timestamp = datetime.now(timezone.utc)
                self.logger.debug("No email date available, using current time")
            
            # Write note using existing write_obsidian_note function
            # Note: write_obsidian_note respects dry-run mode internally
            file_path = write_obsidian_note(
                note_content=note_content,
                email_subject=email_subject,
                vault_path=str(account_vault_path),
                timestamp=timestamp,  # Use parsed email date or current time
                overwrite=False  # Don't overwrite existing files
            )
            
            self.logger.info(
                f"Successfully wrote note for UID {email_uid} "
                f"(account {self.account_id}): {file_path}"
            )
            
        except (InvalidPathError, WritePermissionError, FileWriteError) as e:
            self.logger.error(
                f"Failed to write note for UID {email_uid} "
                f"(account {self.account_id}): {e}",
                exc_info=True
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error writing note for UID {email_uid} "
                f"(account {self.account_id}): {e}",
                exc_info=True
            )
    
    def _log_email_processed(
        self,
        uid: str,
        classification_result: Optional[ClassificationResult],
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Log email processing result to structured analytics.
        
        Args:
            uid: Email UID
            classification_result: Classification result (if successful)
            success: Whether processing succeeded
            error: Error message (if failed)
        """
        try:
            # Try to use V3's EmailLogger for structured analytics
            from src.v3_logger import EmailLogger, AnalyticsWriter, LogFileManager
            
            # Get analytics file path from config
            analytics_file = self.config.get('paths', {}).get('analytics_file', 'logs/analytics.jsonl')
            
            # Create EmailLogger instance with account-specific analytics file
            # Need to create AnalyticsWriter first, then pass it to EmailLogger
            file_manager = LogFileManager(analytics_file=analytics_file)
            analytics_writer = AnalyticsWriter(analytics_file, file_manager=file_manager)
            email_logger = EmailLogger(analytics_writer=analytics_writer)
            
            if success and classification_result:
                # Log successful processing
                email_logger.log_email_processed(
                    uid=uid,
                    status='success',
                    importance_score=int(classification_result.importance_score) if classification_result.importance_score >= 0 else -1,
                    spam_score=int(classification_result.spam_score) if classification_result.spam_score >= 0 else -1
                )
            else:
                # Log failed processing
                email_logger.log_email_processed(
                    uid=uid,
                    status='error',
                    importance_score=-1,
                    spam_score=-1
                )
        except ImportError:
            # EmailLogger not available, skip structured logging
            self.logger.debug("EmailLogger not available, skipping structured analytics")
        except Exception as e:
            # Don't let logging failures break the pipeline
            self.logger.warning(
                f"Failed to log to structured analytics for UID {uid}: {e}"
            )
    
    def _mark_email_processed(self, uid: str) -> None:
        """
        Mark email as processed in IMAP.
        
        Args:
            uid: Email UID
        """
        try:
            processed_tag = self.config.get('imap', {}).get('processed_tag', 'AIProcessed')
            self._imap_conn.set_flag(uid, processed_tag)
        except Exception as e:
            self.logger.warning(
                f"Failed to mark email UID {uid} as processed "
                f"for account {self.account_id}: {e}"
            )
    
    def _log_processing_summary(self) -> None:
        """Log summary of processing run."""
        context = self._processing_context
        import time
        
        elapsed_time = time.time() - context.get('start_time', 0)
        
        self.logger.info(
            f"Processing summary for account {self.account_id}: "
            f"fetched={context.get('emails_fetched', 0)}, "
            f"processed={context.get('emails_processed', 0)}, "
            f"dropped={len(self._dropped_emails)}, "
            f"recorded={len(self._recorded_emails)}, "
            f"time={elapsed_time:.2f}s"
        )
