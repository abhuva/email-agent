"""
V4 Orchestrator Module

This module provides the V4 MasterOrchestrator for multi-account email processing.
It coordinates multiple AccountProcessor instances to handle email processing across
multiple accounts with complete state isolation.

Architecture:
    - MasterOrchestrator class: Multi-account orchestrator for V4 (manages multiple AccountProcessor instances)
    - OrchestrationResult: Result of orchestrating multiple account processing operations
    - Error handling: Isolated per-account error handling to prevent crashes
    - State isolation: Each account is processed in complete isolation

Key Features:
    - Multi-account support with complete state isolation
    - Per-account error isolation (failures don't affect other accounts)
    - Comprehensive error handling with graceful degradation
    - Configuration-based account discovery
    - CLI argument parsing for account selection

Usage:
    >>> from src.orchestrator import MasterOrchestrator
    >>> 
    >>> orchestrator = MasterOrchestrator(
    ...     config_base_dir='config',
    ...     logger=logger
    ... )
    >>> 
    >>> result = orchestrator.run(['--account', 'work'])
    >>> print(result)

See Also:
    - docs/v4-orchestrator.md - V4 MasterOrchestrator documentation
    - src/account_processor.py - AccountProcessor class
    - src/cli_v4.py - V4 CLI integration
"""
import logging
import time
import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Try to import rich for progress bars (optional dependency)
try:
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, SpinnerColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# V4 imports
from src.logging_context import set_account_context, set_correlation_id, clear_context, with_account_context
from src.logging_helpers import log_account_start, log_account_end, log_config_overrides, log_error_with_context

logger = logging.getLogger(__name__)


# ============================================================================
# V4 Master Orchestrator (Multi-Account Support)
# ============================================================================

import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# V4 imports
from src.account_processor import AccountProcessor, create_imap_client_from_config, AccountProcessorError, AccountProcessorSetupError, AccountProcessorRunError
from src.config_loader import ConfigLoader, ConfigurationError
from src.rules import load_blacklist_rules, load_whitelist_rules
from src.content_parser import parse_html_content
from src.llm_client import LLMClient
from src.note_generator import NoteGenerator
from src.decision_logic import DecisionLogic


@dataclass
class OrchestrationResult:
    """
    Result of orchestrating multiple account processing operations.
    
    Attributes:
        total_accounts: Total number of accounts processed
        successful_accounts: Number of accounts processed successfully
        failed_accounts: Number of accounts that failed
        account_results: Dictionary mapping account_id to (success: bool, error: Optional[str])
        total_time: Total orchestration time (seconds)
    """
    total_accounts: int
    successful_accounts: int
    failed_accounts: int
    account_results: Dict[str, Tuple[bool, Optional[str]]] = field(default_factory=dict)
    total_time: float = 0.0
    
    def __str__(self) -> str:
        """Format orchestration result for display."""
        return (
            f"Orchestration complete: {self.successful_accounts}/{self.total_accounts} accounts successful, "
            f"{self.failed_accounts} failed, total time: {self.total_time:.2f}s"
        )


# Note: Pipeline class and V3 dataclasses (ProcessOptions, ProcessingResult, PipelineSummary) 
# have been removed. They were only used by cli_v3.py and backfill.py, which will be 
# removed/updated in later subtasks (22.12 and backfill migration).


class MasterOrchestrator:
    """
    V4 Master Orchestrator for managing multiple account processing operations.
    
    This class coordinates the processing of multiple email accounts by:
    - Parsing CLI arguments for account selection
    - Discovering available accounts from configuration
    - Creating isolated AccountProcessor instances for each account
    - Managing the overall processing flow with robust error handling
    
    State Isolation:
        Each account is processed in complete isolation:
        - Separate AccountProcessor instances (no shared state)
        - Separate IMAP connections
        - Separate configuration (merged per account)
        - Failures in one account don't affect others
    
    Usage:
        >>> from src.orchestrator import MasterOrchestrator
        >>> 
        >>> orchestrator = MasterOrchestrator(
        ...     config_base_dir='config',
        ...     logger=logger
        ... )
        >>> 
        >>> result = orchestrator.run(['--account', 'work'])
        >>> print(result)
    
    See Also:
        - docs/v4-orchestrator.md - Complete V4 orchestrator documentation
        - src/account_processor.py - AccountProcessor class
        - pdd_V4.md - V4 Product Design Document
    """
    
    def __init__(
        self,
        config_base_dir: Path | str = "config",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize MasterOrchestrator with configuration directory and logger.
        
        Args:
            config_base_dir: Base directory containing configuration files
                           (default: 'config')
            logger: Optional logger instance (creates one if not provided)
        
        Note:
            The orchestrator uses ConfigLoader to discover and load account configurations.
            Account configs are expected in {config_base_dir}/accounts/*.yaml
        """
        # Configuration
        self.config_base_dir = Path(config_base_dir).resolve()
        
        # Logger
        if logger is None:
            logger = logging.getLogger(f"{__name__}.MasterOrchestrator")
        self.logger = logger
        
        # ConfigLoader for account discovery and config loading
        self.config_loader = ConfigLoader(
            base_dir=self.config_base_dir,
            enable_validation=True
        )
        
        # Account selection (set during run)
        self.accounts_to_process: List[str] = []
        
        # Note: Components are now created per-account with account-specific config
        # No longer using shared instances to support per-account configuration
        
        self.logger.info(f"MasterOrchestrator initialized with config_base_dir={self.config_base_dir}")
    
    @classmethod
    def parse_args(cls, argv: Optional[List[str]] = None) -> argparse.Namespace:
        """
        Parse CLI arguments for account selection and processing options.
        
        This method defines the CLI interface for the V4 orchestrator:
        - --account <id>: Process a single account (can be repeated)
        - --accounts <id1,id2,...>: Process multiple accounts (comma-separated)
        - --all-accounts: Process all available accounts
        - --config-dir <path>: Override config directory (default: 'config')
        - --dry-run: Run in preview mode (no side effects)
        - --log-level <level>: Set logging level (DEBUG, INFO, WARN, ERROR)
        
        Args:
            argv: Optional list of command-line arguments (default: sys.argv[1:])
        
        Returns:
            argparse.Namespace with parsed arguments
        
        Raises:
            SystemExit: If argument parsing fails or --help is requested
        """
        parser = argparse.ArgumentParser(
            description="V4 Email Agent: Multi-account email processing orchestrator",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --account work                    # Process single account
  %(prog)s --accounts work,personal         # Process multiple accounts
  %(prog)s --all-accounts                   # Process all available accounts
  %(prog)s --account work --dry-run         # Preview mode for single account
  %(prog)s --all-accounts --log-level DEBUG # Process all with debug logging
            """
        )
        
        # Account selection (mutually exclusive group)
        account_group = parser.add_mutually_exclusive_group()
        account_group.add_argument(
            '--account',
            action='append',
            dest='account_list',
            help='Process a specific account (can be repeated: --account work --account personal)'
        )
        account_group.add_argument(
            '--accounts',
            type=str,
            help='Process multiple accounts (comma-separated: --accounts work,personal)'
        )
        account_group.add_argument(
            '--all-accounts',
            action='store_true',
            help='Process all available accounts from config/accounts/'
        )
        
        # Configuration options
        parser.add_argument(
            '--config-dir',
            type=str,
            default='config',
            help='Base directory for configuration files (default: config)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in preview mode (no side effects, no file writes, no IMAP flag changes)'
        )
        parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            default='INFO',
            help='Set logging level (default: INFO)'
        )
        
        # Processing options
        parser.add_argument(
            '--uid',
            type=str,
            help='Target a specific email by UID. If not provided, processes emails according to configured query.'
        )
        parser.add_argument(
            '--force-reprocess',
            action='store_true',
            help='Ignore existing processed_tag and reprocess emails even if already marked as processed.'
        )
        parser.add_argument(
            '--max-emails',
            type=int,
            help='Maximum number of emails to process (overrides config max_emails_per_run). Useful for testing.'
        )
        parser.add_argument(
            '--debug-prompt',
            action='store_true',
            help='Write the formatted classification prompt to a debug file in logs/ directory. Useful for debugging prompt construction.'
        )
        
        return parser.parse_args(argv)
    
    def _discover_available_accounts(self) -> List[str]:
        """
        Discover all available accounts from the configuration directory.
        
        This method scans the config/accounts/ directory for YAML files
        and returns their names (without .yaml extension) as account identifiers.
        
        Returns:
            List of account identifiers (e.g., ['work', 'personal'])
        
        Raises:
            ConfigurationError: If the accounts directory doesn't exist or is invalid
        """
        accounts_dir = self.config_base_dir / 'accounts'
        
        if not accounts_dir.exists():
            self.logger.warning(
                f"Accounts directory not found: {accounts_dir}. "
                "No accounts will be discovered."
            )
            return []
        
        if not accounts_dir.is_dir():
            raise ConfigurationError(
                f"Accounts path exists but is not a directory: {accounts_dir}"
            )
        
        # Find all .yaml files in accounts directory
        account_files = list(accounts_dir.glob('*.yaml'))
        account_ids = [f.stem for f in account_files if f.is_file()]
        
        # Filter out example files
        account_ids = [aid for aid in account_ids if not aid.startswith('example')]
        
        self.logger.info(
            f"Discovered {len(account_ids)} account(s) in {accounts_dir}: {account_ids}"
        )
        
        return sorted(account_ids)
    
    def select_accounts(self, args: argparse.Namespace) -> List[str]:
        """
        Select accounts to process based on parsed CLI arguments.
        
        This method:
        1. Determines which accounts to process from CLI args
        2. Validates that requested accounts exist
        3. Returns a list of account identifiers to process
        
        Args:
            args: Parsed CLI arguments from parse_args()
        
        Returns:
            List of account identifiers to process
        
        Raises:
            ValueError: If an unknown account is requested
            ConfigurationError: If account discovery fails
        """
        account_ids: List[str] = []
        
        # Determine account selection strategy
        if args.all_accounts:
            # Process all available accounts
            account_ids = self._discover_available_accounts()
            if not account_ids:
                raise ConfigurationError(
                    f"No accounts found in {self.config_base_dir / 'accounts'}. "
                    "Create account configuration files (e.g., config/accounts/work.yaml)"
                )
            self.logger.info(f"Selected all accounts: {account_ids}")
        
        elif args.accounts:
            # Comma-separated list
            account_ids = [aid.strip() for aid in args.accounts.split(',') if aid.strip()]
            self.logger.info(f"Selected accounts from --accounts: {account_ids}")
        
        elif args.account_list:
            # Repeated --account flags
            account_ids = [aid.strip() for aid in args.account_list if aid.strip()]
            self.logger.info(f"Selected accounts from --account flags: {account_ids}")
        
        else:
            # Default: process all accounts
            account_ids = self._discover_available_accounts()
            if not account_ids:
                raise ConfigurationError(
                    f"No accounts found and no account specified. "
                    "Use --account <id>, --accounts <id1,id2>, or --all-accounts"
                )
            self.logger.info(f"No account specified, defaulting to all accounts: {account_ids}")
        
        # Validate that all requested accounts exist
        available_accounts = self._discover_available_accounts()
        invalid_accounts = [aid for aid in account_ids if aid not in available_accounts]
        
        if invalid_accounts:
            raise ValueError(
                f"Unknown account(s): {invalid_accounts}. "
                f"Available accounts: {available_accounts}"
            )
        
        # Store for use in processing loop
        self.accounts_to_process = account_ids
        
        self.logger.info(f"Selected {len(account_ids)} account(s) for processing: {account_ids}")
        
        return account_ids
    
    def _iter_accounts(self):
        """
        Iterator helper that yields each account identifier in turn.
        
        This encapsulates any future filtering, ordering, or batching logic.
        Currently just yields accounts in the order they were selected.
        
        Yields:
            Account identifier (str)
        """
        for account_id in self.accounts_to_process:
            yield account_id
    
    def _initialize_shared_services(self):
        """
        Initialize shared services that can be safely reused across accounts.
        
        These services are stateless or thread-safe and don't maintain
        account-specific state, so they can be shared to reduce overhead.
        
        Note:
            Services are initialized lazily on first use if not already initialized.
        """
        # Components are now created per-account with account-specific config
        # This method is kept for compatibility but does nothing
        pass
    
    def create_account_processor(self, account_id: str) -> AccountProcessor:
        """
        Create an isolated AccountProcessor instance for a specific account.
        
        This method:
        1. Loads merged configuration for the account
        2. Creates all required dependencies
        3. Instantiates AccountProcessor with account-specific config
        4. Ensures complete state isolation (no shared mutable state)
        
        Args:
            account_id: Account identifier (e.g., 'work', 'personal')
        
        Returns:
            AccountProcessor instance (not yet set up or run)
        
        Raises:
            ConfigurationError: If account configuration cannot be loaded
            AccountProcessorSetupError: If AccountProcessor creation fails
        """
        self.logger.info(f"Creating AccountProcessor for account: {account_id}")
        
        # Load merged configuration for this account
        try:
            account_config = self.config_loader.load_merged_config(account_id)
            self.logger.debug(f"Loaded merged configuration for account: {account_id}")
        except (FileNotFoundError, ConfigurationError) as e:
            raise ConfigurationError(
                f"Failed to load configuration for account '{account_id}': {e}"
            ) from e
        
        # Create account-specific logger
        account_logger = logging.getLogger(f"{__name__}.AccountProcessor.{account_id}")
        
        # Create components with account-specific configuration
        # Each account gets its own instances with account-specific config
        llm_client = LLMClient(account_config)
        note_generator = NoteGenerator(account_config)
        decision_logic = DecisionLogic(account_config)
        
        # Create AccountProcessor with isolated configuration and dependencies
        # All dependencies are injected to ensure testability and isolation
        processor = AccountProcessor(
            account_id=account_id,
            account_config=account_config,
            imap_client_factory=create_imap_client_from_config,
            llm_client=llm_client,
            blacklist_service=load_blacklist_rules,
            whitelist_service=load_whitelist_rules,
            note_generator=note_generator,
            parser=parse_html_content,
            decision_logic=decision_logic,
            logger=account_logger
        )
        
        self.logger.info(f"Successfully created AccountProcessor for account: {account_id}")
        
        return processor
    
    def run(self, argv: Optional[List[str]] = None) -> OrchestrationResult:
        """
        Main entry point: parse CLI args, select accounts, and orchestrate processing.
        
        This method coordinates the complete multi-account processing flow:
        1. Parse CLI arguments
        2. Select accounts to process
        3. Iterate through accounts
        4. Create isolated AccountProcessor for each account
        5. Execute processing with robust error handling
        6. Aggregate results and return summary
        
        Error Handling:
            Failures in one account are caught, logged, and recorded, but do not
            prevent processing of remaining accounts. All accounts are attempted
            even if some fail.
        
        Args:
            argv: Optional list of command-line arguments (default: sys.argv[1:])
        
        Returns:
            OrchestrationResult with processing summary
        
        Raises:
            SystemExit: If argument parsing fails
            ValueError: If account selection is invalid
            ConfigurationError: If configuration loading fails
        """
        start_time = time.time()
        result = OrchestrationResult(
            total_accounts=0,
            successful_accounts=0,
            failed_accounts=0
        )
        
        # Generate correlation ID for this orchestration run
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        self.logger.info("=" * 60)
        self.logger.info(f"V4 Master Orchestrator: Starting multi-account processing [correlation_id={correlation_id}]")
        self.logger.info("=" * 60)
        
        try:
            # Step 1: Parse CLI arguments
            args = self.parse_args(argv)
            
            # Update config_base_dir if specified
            if args.config_dir:
                self.config_base_dir = Path(args.config_dir).resolve()
                self.config_loader = ConfigLoader(
                    base_dir=self.config_base_dir,
                    enable_validation=True
                )
                self.logger.info(f"Using config directory: {self.config_base_dir}")
            
            # Set logging level
            if args.log_level:
                logging.getLogger().setLevel(getattr(logging, args.log_level))
                self.logger.info(f"Logging level set to: {args.log_level}")
            
            # Step 2: Select accounts
            account_ids = self.select_accounts(args)
            result.total_accounts = len(account_ids)
            
            if not account_ids:
                self.logger.warning("No accounts selected for processing")
                result.total_time = time.time() - start_time
                return result
            
            # Step 3: Process each account with error isolation
            for account_id in self._iter_accounts():
                account_start_time = time.time()
                processor = None
                
                # Set account context for this account's processing
                with with_account_context(account_id=account_id, correlation_id=correlation_id):
                    self.logger.info("=" * 60)
                    log_account_start(account_id, correlation_id=correlation_id)
                    self.logger.info("=" * 60)
                    
                    try:
                        # Create AccountProcessor for this account
                        processor = self.create_account_processor(account_id)
                        
                        # Set up account (IMAP connection, etc.)
                        processor.setup()
                        
                        # Run processing with options from CLI
                        processor.run(
                            force_reprocess=args.force_reprocess,
                            uid=args.uid,
                            max_emails=args.max_emails,
                            debug_prompt=args.debug_prompt
                        )
                        
                        # Teardown (cleanup, close connections)
                        processor.teardown()
                        
                        # Record success
                        account_time = time.time() - account_start_time
                        result.successful_accounts += 1
                        result.account_results[account_id] = (True, None)
                        log_account_end(account_id, success=True, processing_time=account_time, correlation_id=correlation_id)
                        
                    except AccountProcessorSetupError as e:
                        # Setup failed (e.g., IMAP connection error)
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"Setup failed: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='setup')
                        
                    except AccountProcessorRunError as e:
                        # Processing failed
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"Processing failed: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='processing')
                        
                    except AccountProcessorError as e:
                        # General AccountProcessor error
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"AccountProcessor error: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='account_processing')
                        
                    except Exception as e:
                        # Unexpected error
                        account_time = time.time() - account_start_time
                        result.failed_accounts += 1
                        error_msg = f"Unexpected error: {type(e).__name__}: {e}"
                        result.account_results[account_id] = (False, error_msg)
                        log_account_end(account_id, success=False, processing_time=account_time, correlation_id=correlation_id, error=error_msg)
                        log_error_with_context(e, account_id=account_id, correlation_id=correlation_id, operation='unexpected')
                        
                    finally:
                        # Ensure cleanup happens even on failure
                        if processor is not None:
                            try:
                                processor.teardown()
                            except Exception as cleanup_error:
                                self.logger.warning(
                                    f"Error during cleanup for account '{account_id}': {cleanup_error}",
                                    exc_info=True
                                )
            
            # Step 4: Generate summary
            result.total_time = time.time() - start_time
            
            self.logger.info("=" * 60)
            self.logger.info("V4 Master Orchestrator: Processing complete")
            self.logger.info("=" * 60)
            self.logger.info(f"Total accounts: {result.total_accounts}")
            self.logger.info(f"  [OK] Successful: {result.successful_accounts}")
            self.logger.info(f"  [FAILED] Failed: {result.failed_accounts}")
            self.logger.info(f"Total time: {result.total_time:.2f}s")
            
            if result.failed_accounts > 0:
                self.logger.warning("Some accounts failed processing - check logs for details")
                for account_id, (success, error) in result.account_results.items():
                    if not success:
                        self.logger.warning(f"  - {account_id}: {error}")
            
            return result
            
        except (ValueError, ConfigurationError) as e:
            # Configuration or validation errors
            result.total_time = time.time() - start_time
            self.logger.error(f"Orchestration failed: {e}", exc_info=True)
            raise
            
        except Exception as e:
            # Unexpected errors
            result.total_time = time.time() - start_time
            self.logger.error(f"Unexpected orchestration error: {e}", exc_info=True)
            raise


def main():
    """
    Top-level integration point for CLI usage.
    
    This function can be used as an entry point for the V4 orchestrator:
    
    Usage:
        python -m src.orchestrator
        # or
        from src.orchestrator import main
        main()
    """
    import sys
    
    # Initialize centralized logging (first thing on startup)
    try:
        from src.logging_config import init_logging
        init_logging()
    except Exception as e:
        # Fallback to basic logging if centralized logging fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger.warning(f"Could not initialize centralized logging, using basic logging: {e}")
    
    # Create orchestrator and run
    orchestrator = MasterOrchestrator()
    result = orchestrator.run()
    
    # Exit with appropriate code
    if result.failed_accounts > 0:
        sys.exit(1)
    else:
        sys.exit(0)
