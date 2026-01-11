#!/usr/bin/env python3
"""
Main entry point for the email agent.
Supports both V3 (single-account) and V4 (multi-account) processing modes.

V3 Mode (Click CLI):
    python main.py process [--uid <ID>] [--force-reprocess] [--dry-run]
    python main.py cleanup-flags

V4 Mode (MasterOrchestrator):
    python main.py --account <name> [--dry-run]
    python main.py --all-accounts [--dry-run]

See --help for available options.
"""

import sys
import signal
import logging
from pathlib import Path
from typing import Optional

# Import V4 components
from src.orchestrator import MasterOrchestrator
from src.runtime_config import build_runtime_config
from src.logging_config import init_logging

# Import V3 CLI for backward compatibility
from src.cli_v3 import cli as cli_v3


def _is_v4_mode(argv: list[str]) -> bool:
    """
    Detect if command-line arguments indicate V4 multi-account mode.
    
    V4 mode is indicated by:
    - --account flag
    - --all-accounts flag
    - --accounts flag (comma-separated)
    
    Args:
        argv: Command-line arguments (excluding script name)
        
    Returns:
        True if V4 mode, False if V3 mode
    """
    v4_flags = ['--account', '--all-accounts', '--accounts']
    return any(flag in argv for flag in v4_flags)


def _setup_signal_handlers(orchestrator: Optional[MasterOrchestrator]) -> None:
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        orchestrator: MasterOrchestrator instance (can be None if not initialized)
    """
    def signal_handler(signum, frame):
        """Handle termination signals."""
        signal_name = signal.Signals(signum).name
        logger = logging.getLogger('email_agent')
        logger.warning(f"Received {signal_name}, initiating graceful shutdown...")
        
        # Note: MasterOrchestrator.run() handles cleanup internally
        # This handler is mainly for logging and future extensions
        sys.exit(130 if signum == signal.SIGINT else 128 + signum)
    
    # Register handlers for common termination signals
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


def _adapt_parsed_args_for_runtime_config(parsed_args) -> object:
    """
    Adapt MasterOrchestrator.parse_args() output to match build_runtime_config() expectations.
    
    MasterOrchestrator uses:
    - account_list (list from --account flags)
    - accounts (string from --accounts flag)
    - all_accounts (bool)
    
    build_runtime_config expects:
    - account (single string, or None)
    - all_accounts (bool)
    
    Args:
        parsed_args: argparse.Namespace from MasterOrchestrator.parse_args()
        
    Returns:
        Adapted namespace object compatible with build_runtime_config()
    """
    from argparse import Namespace
    
    # Determine account selection
    account = None
    all_accounts = False
    
    if hasattr(parsed_args, 'all_accounts') and parsed_args.all_accounts:
        all_accounts = True
    elif hasattr(parsed_args, 'accounts') and parsed_args.accounts:
        # Comma-separated accounts - take first one for build_runtime_config
        # (build_runtime_config handles single account, MasterOrchestrator handles multiple)
        account = parsed_args.accounts.split(',')[0].strip()
    elif hasattr(parsed_args, 'account_list') and parsed_args.account_list:
        # Multiple --account flags - take first one
        account = parsed_args.account_list[0]
    
    # Create adapted namespace
    adapted = Namespace(
        account=account,
        all_accounts=all_accounts,
        dry_run=getattr(parsed_args, 'dry_run', False),
        config_dir=getattr(parsed_args, 'config_dir', None),
        env_file=None,  # MasterOrchestrator doesn't parse env_file, use default
        log_level=getattr(parsed_args, 'log_level', None)
    )
    
    return adapted


def main_v4(argv: Optional[list[str]] = None) -> int:
    """
    V4 main entry point using MasterOrchestrator.
    
    This function:
    1. Parses CLI arguments using MasterOrchestrator.parse_args()
    2. Builds runtime configuration using build_runtime_config()
    3. Initializes centralized logging
    4. Constructs and runs MasterOrchestrator
    5. Handles shutdown and returns appropriate exit codes
    
    Args:
        argv: Optional list of command-line arguments (default: sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = None
    orchestrator = None
    
    try:
        # Step 1: Parse CLI arguments
        parsed_args = MasterOrchestrator.parse_args(argv)
        
        # Step 2: Adapt parsed_args for build_runtime_config()
        adapted_args = _adapt_parsed_args_for_runtime_config(parsed_args)
        
        # Step 3: Build runtime configuration
        try:
            runtime_config = build_runtime_config(adapted_args)
        except ValueError as e:
            # Configuration validation failed
            print(f"Configuration error: {e}", file=sys.stderr)
            return 1
        
        # Step 4: Initialize centralized logging
        # Use log level from runtime config
        log_overrides = {'level': runtime_config.log_level}
        init_logging(overrides=log_overrides)
        logger = logging.getLogger('email_agent')
        logger.info("Starting email agent V4 (multi-account mode)")
        logger.debug(f"Runtime config: accounts={runtime_config.account_names if runtime_config.account_names else 'all'}, "
                    f"dry_run={runtime_config.dry_run}, config_dir={runtime_config.config_base_dir}")
        
        # Step 5: Set up signal handlers for graceful shutdown
        # (orchestrator will be created next, so pass None for now)
        _setup_signal_handlers(None)
        
        # Step 6: Construct MasterOrchestrator
        # Use config_base_dir from runtime_config
        orchestrator = MasterOrchestrator(
            config_base_dir=runtime_config.config_base_dir,
            logger=logger
        )
        
        # Update signal handler with orchestrator reference
        _setup_signal_handlers(orchestrator)
        
        # Step 7: Run orchestration
        # MasterOrchestrator.run() handles its own argument parsing internally.
        # We pass argv so it uses the same arguments we parsed, ensuring consistency.
        # The orchestrator will use its own parse_args() method internally.
        result = orchestrator.run(argv)
        
        # Step 8: Determine exit code based on results
        if result.failed_accounts > 0:
            logger.warning(f"Processing completed with {result.failed_accounts} failed account(s)")
            return 1
        else:
            logger.info("Processing completed successfully")
            return 0
            
    except KeyboardInterrupt:
        if logger:
            logger.warning("Interrupted by user")
        return 130  # SIGINT exit code
        
    except (ValueError, SystemExit) as e:
        # SystemExit from argparse --help, ValueError from validation
        if isinstance(e, SystemExit):
            # Re-raise SystemExit (from --help, etc.)
            raise
        if logger:
            logger.error(f"Configuration or validation error: {e}", exc_info=True)
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1
        
    except Exception as e:
        if logger:
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        return 1
        
    finally:
        # Step 9: Cleanup (MasterOrchestrator handles its own cleanup,
        # but we ensure logging is finalized)
        if logger:
            logger.info("Shutting down email agent V4")


def main() -> int:
    """
    Main entry point that routes to V3 or V4 mode based on command-line arguments.
    
    Flow:
    1. Check if V4 mode is requested (--account, --all-accounts, --accounts)
    2. If V4: Use MasterOrchestrator directly
    3. If V3: Use Click CLI (backward compatibility)
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Get command-line arguments (excluding script name)
    argv = sys.argv[1:]
    
    # Check if V4 mode is requested
    if _is_v4_mode(argv):
        # V4 mode: Use MasterOrchestrator directly
        return main_v4(argv)
    else:
        # V3 mode: Use Click CLI (backward compatibility)
        # Click CLI handles its own exit codes, so we just call it
        cli_v3()
        # Click CLI exits internally, so this line is only reached if no command is executed
        return 0


if __name__ == "__main__":
    sys.exit(main())
