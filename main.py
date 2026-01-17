#!/usr/bin/env python3
"""
Main entry point for the email agent V4.

V4 CLI Commands (V4-only architecture):
    python main.py process --account <name> [--dry-run] [--uid <ID>] [--force-reprocess] [--max-emails <N>] [--debug-prompt]
    python main.py process --all [--dry-run] [--max-emails <N>]
    python main.py cleanup-flags --account <name> [--dry-run]
    python main.py show-config --account <name> [--format yaml|json] [--with-sources] [--no-highlight]

Note: All commands require account specification. The V4 CLI uses V4 components exclusively
(MasterOrchestrator, ConfigLoader) and no longer supports V3 mode.

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
