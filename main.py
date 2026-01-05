#!/usr/bin/env python3
"""
Main entry point for the email agent.
Provides a simple command-line interface for running the agent.

Usage:
    python main.py [options]

See --help for available options.
"""

import sys
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
