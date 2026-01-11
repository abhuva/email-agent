#!/usr/bin/env python3
"""
Bootstrap script to create configuration directory structure.

This script creates the required configuration directories and placeholder files
for new environments. Run this after cloning the repository to set up the
configuration structure.

Usage:
    python scripts/bootstrap_config.py
"""
import os
import sys
from pathlib import Path

# Get project root (parent of scripts directory)
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / 'config'
ACCOUNTS_DIR = CONFIG_DIR / 'accounts'


def create_directories():
    """Create configuration directory structure."""
    print("Creating configuration directories...")
    
    CONFIG_DIR.mkdir(exist_ok=True)
    print(f"  [OK] Created {CONFIG_DIR}")
    
    ACCOUNTS_DIR.mkdir(exist_ok=True)
    print(f"  [OK] Created {ACCOUNTS_DIR}")
    
    return True


def verify_structure():
    """Verify that the directory structure exists."""
    if not CONFIG_DIR.exists():
        print(f"ERROR: {CONFIG_DIR} does not exist")
        return False
    
    if not ACCOUNTS_DIR.exists():
        print(f"ERROR: {ACCOUNTS_DIR} does not exist")
        return False
    
    print("[OK] Directory structure verified")
    return True


def main():
    """Main bootstrap function."""
    print("=" * 70)
    print("Email Agent - Configuration Bootstrap")
    print("=" * 70)
    print()
    
    # Create directories
    if not create_directories():
        print("ERROR: Failed to create directories")
        sys.exit(1)
    
    # Verify structure
    if not verify_structure():
        print("ERROR: Directory structure verification failed")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("Bootstrap complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Copy config/config.yaml.example to config/config.yaml")
    print("  2. Copy .env.example to .env (if it exists)")
    print("  3. Edit config/config.yaml with your settings")
    print("  4. Edit .env with your credentials")
    print("  5. See docs/v4-configuration.md for detailed configuration guide")
    print()


if __name__ == '__main__':
    main()
