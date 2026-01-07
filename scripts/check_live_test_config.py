#!/usr/bin/env python3
"""
Configuration checker for live end-to-end test.

This script verifies that all required V2 configuration is in place
before running the live test.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import ConfigManager, ConfigError, ConfigPathError, ConfigFormatError


def check_config():
    """Check if configuration is ready for live test."""
    print("=" * 60)
    print("Live Test Configuration Checker")
    print("=" * 60)
    print()
    
    errors = []
    warnings = []
    
    # Check config file exists
    config_path = project_root / 'config' / 'config.yaml'
    env_path = project_root / '.env'
    
    if not config_path.exists():
        errors.append(f"Config file not found: {config_path}")
        return errors, warnings
    
    if not env_path.exists():
        errors.append(f"Environment file not found: {env_path}")
        return errors, warnings
    
    print(f"[OK] Config file found: {config_path}")
    print(f"[OK] Environment file found: {env_path}")
    print()
    
    # Try to load config
    try:
        config = ConfigManager(str(config_path), str(env_path))
        print("[OK] Configuration loaded successfully")
        print()
    except ConfigError as e:
        errors.append(f"Configuration error: {e}")
        return errors, warnings
    except ConfigPathError as e:
        errors.append(f"Configuration path error: {e}")
        return errors, warnings
    except ConfigFormatError as e:
        errors.append(f"Configuration format error: {e}")
        return errors, warnings
    except Exception as e:
        errors.append(f"Unexpected error loading config: {e}")
        return errors, warnings
    
    # Check V2 parameters
    print("Checking V2 Parameters:")
    print("-" * 60)
    
    # Check obsidian_vault_path (required for V2)
    if not hasattr(config, 'obsidian_vault_path') or not config.obsidian_vault_path:
        errors.append("obsidian_vault_path is not configured (required for V2)")
    else:
        vault_path = Path(config.obsidian_vault_path)
        if not vault_path.exists():
            errors.append(f"Obsidian vault path does not exist: {vault_path}")
            print(f"  → Create the directory: mkdir -p \"{vault_path}\"")
        elif not vault_path.is_dir():
            errors.append(f"Obsidian vault path is not a directory: {vault_path}")
        else:
            # Check write permission
            try:
                test_file = vault_path / '.write_test'
                test_file.write_text('test')
                test_file.unlink()
                print(f"[OK] obsidian_vault_path: {vault_path} (exists, writable)")
            except Exception as e:
                errors.append(f"Cannot write to Obsidian vault path: {e}")
                print(f"[ERROR] obsidian_vault_path: {vault_path} (exists but not writable)")
    
    # Check summarization_tags (optional)
    if hasattr(config, 'summarization_tags') and config.summarization_tags:
        print(f"[OK] summarization_tags: {config.summarization_tags}")
        
        # Check summarization_prompt_path if tags are configured
        if not hasattr(config, 'summarization_prompt_path') or not config.summarization_prompt_path:
            errors.append("summarization_prompt_path is required when summarization_tags is configured")
        else:
            prompt_path = Path(config.summarization_prompt_path)
            if not prompt_path.exists():
                errors.append(f"Summarization prompt file does not exist: {prompt_path}")
                print(f"  -> Create the file: {prompt_path}")
            elif not prompt_path.is_file():
                errors.append(f"Summarization prompt path is not a file: {prompt_path}")
            else:
                print(f"[OK] summarization_prompt_path: {prompt_path}")
    else:
        warnings.append("summarization_tags not configured (summarization will be skipped)")
        print("[WARN] summarization_tags: Not configured (optional)")
    
    # Check changelog_path (optional)
    if hasattr(config, 'changelog_path') and config.changelog_path:
        changelog_path = Path(config.changelog_path)
        changelog_dir = changelog_path.parent
        if not changelog_dir.exists():
            errors.append(f"Changelog directory does not exist: {changelog_dir}")
            print(f"  -> Create the directory: mkdir -p \"{changelog_dir}\"")
        else:
            print(f"[OK] changelog_path: {changelog_path} (directory exists)")
    else:
        warnings.append("changelog_path not configured (changelog will be skipped)")
        print("[WARN] changelog_path: Not configured (optional)")
    
    # Check imap_query (V2)
    if hasattr(config, 'imap_query') and config.imap_query:
        print(f"[OK] imap_query: {config.imap_query}")
    else:
        warnings.append("imap_query not configured (will use imap_queries from V1)")
        print("[WARN] imap_query: Not configured (will use imap_queries)")
    
    print()
    
    # Check environment variables
    print("Checking Environment Variables:")
    print("-" * 60)
    
    if 'IMAP_PASSWORD' in os.environ:
        print("[OK] IMAP_PASSWORD: Set")
    else:
        errors.append("IMAP_PASSWORD environment variable not set")
        print("[ERROR] IMAP_PASSWORD: Not set")
    
    if 'OPENROUTER_API_KEY' in os.environ:
        print("[OK] OPENROUTER_API_KEY: Set")
    else:
        errors.append("OPENROUTER_API_KEY environment variable not set")
        print("[ERROR] OPENROUTER_API_KEY: Not set")
    
    print()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    if errors:
        print(f"\n[ERROR] {len(errors)} error(s) found:")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print("\n[WARN] Please fix these errors before running the live test.")
    else:
        print("\n[OK] Configuration is ready for live test!")
    
    if warnings:
        print(f"\n[WARN] {len(warnings)} warning(s):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
        print("\n[INFO] These are optional - the test will work without them.")
    
    print()
    
    return errors, warnings


if __name__ == '__main__':
    errors, warnings = check_config()
    
    if errors:
        sys.exit(1)
    elif warnings:
        print("[OK] Ready to test (with warnings)")
        sys.exit(0)
    else:
        print("[OK] Ready to test!")
        sys.exit(0)
