#!/usr/bin/env python3
"""
Main entry point for the email agent V3.
Provides a command-line interface using click.

Usage:
    python main.py process [--uid <ID>] [--force-reprocess] [--dry-run]
    python main.py cleanup-flags

See --help for available options.
"""

import sys
from src.cli_v3 import cli

if __name__ == "__main__":
    # Use click's CLI entry point
    cli()
