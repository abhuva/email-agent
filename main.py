#!/usr/bin/env python3
"""
Main entry point for the email agent V4.

V4 CLI Commands:
    python main.py process [--account <name>] [--all] [--dry-run] [--uid <ID>] [--force-reprocess]
    python main.py cleanup-flags [--account <name>] [--dry-run]
    python main.py backfill [--account <name>] [--start-date <date>] [--end-date <date>] [--dry-run]
    python main.py show-config [--account <name>] [--format <format>]

See --help for available options.
"""

import sys

# Import V4 CLI
from src.cli_v4 import cli


def main() -> int:
    """
    Main entry point for V4 email agent.
    
    This function delegates to the V4 Click CLI, which handles all command
    parsing, execution, and error handling.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
        Note: Click CLI may call sys.exit() directly, so this may not always be reached
    """
    # Click CLI handles its own exit codes and may call sys.exit() directly
    # We just call it and let it handle everything
    cli()
    # This line is only reached if no command is executed (e.g., just --help)
    return 0


if __name__ == "__main__":
    sys.exit(main())
