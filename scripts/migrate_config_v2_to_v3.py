"""
Migrate V2 config.yaml to V3 format.

This script converts a V2 (flat) configuration file to V3 (nested) format
as specified in the PDD.

Usage:
    python scripts/migrate_config_v2_to_v3.py [config_path] [output_path]

If output_path is not specified, creates a backup and updates the original file.
"""

import sys
import os
import yaml
import shutil
from pathlib import Path
from datetime import datetime

def migrate_v2_to_v3(v2_config: dict) -> dict:
    """
    Convert V2 config dictionary to V3 format.
    
    Args:
        v2_config: V2 configuration dictionary (flat structure)
        
    Returns:
        V3 configuration dictionary (nested structure)
    """
    v3_config = {}
    
    # IMAP section
    v3_config['imap'] = {
        'server': v2_config['imap']['server'],
        'port': v2_config['imap'].get('port', 993),
        'username': v2_config['imap']['username'],
        'password_env': v2_config['imap']['password_env'],
        'query': v2_config.get('imap_query', 'ALL'),
        'processed_tag': v2_config.get('processed_tag', 'AIProcessed'),
        'application_flags': v2_config.get('application_flags', [
            'AIProcessed',
            'ObsidianNoteCreated',
            'NoteCreationFailed'
        ])
    }
    
    # Paths section
    v3_config['paths'] = {
        'template_file': v2_config.get('template_file', 'config/note_template.md.j2'),
        'obsidian_vault': v2_config.get('obsidian_vault_path', ''),
        'log_file': v2_config.get('log_file', 'logs/agent.log'),
        'analytics_file': v2_config.get('analytics_file', 'logs/analytics.jsonl'),
        'changelog_path': v2_config.get('changelog_path', 'logs/email_changelog.md'),
        'prompt_file': v2_config.get('prompt_file', 'config/prompt.md')
    }
    
    # OpenRouter section
    openrouter = v2_config.get('openrouter', {})
    v3_config['openrouter'] = {
        'api_key_env': openrouter.get('api_key_env', 'OPENROUTER_API_KEY'),
        'api_url': openrouter.get('api_url', 'https://openrouter.ai/api/v1'),
        'model': openrouter.get('model', ''),
        'temperature': openrouter.get('temperature', 0.2),
        'retry_attempts': openrouter.get('retry_attempts', 3),
        'retry_delay_seconds': openrouter.get('retry_delay_seconds', 5)
    }
    
    # Processing section
    v3_config['processing'] = {
        'importance_threshold': v2_config.get('importance_threshold', 8),
        'spam_threshold': v2_config.get('spam_threshold', 5),
        'max_body_chars': v2_config.get('max_body_chars', 4000),
        'max_emails_per_run': v2_config.get('max_emails_per_run', 15)
    }
    
    return v3_config


def main():
    """Main migration function."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate_config_v2_to_v3.py <config_path> [output_path]")
        print("  If output_path is not specified, creates backup and updates original file")
        sys.exit(1)
    
    config_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    # Load V2 config
    print(f"Loading V2 config from: {config_path}")
    with open(config_path, 'r') as f:
        v2_config = yaml.safe_load(f)
    
    # Check if already V3 format
    if 'paths' in v2_config and 'processing' in v2_config:
        print("Config appears to already be in V3 format!")
        print("V3 config has 'paths' and 'processing' sections.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            sys.exit(0)
    
    # Migrate to V3
    print("Converting to V3 format...")
    v3_config = migrate_v2_to_v3(v2_config)
    
    # Determine output path
    if output_path:
        # Write to specified output path
        print(f"Writing V3 config to: {output_path}")
        with open(output_path, 'w') as f:
            yaml.dump(v3_config, f, default_flow_style=False, sort_keys=False)
        print("Migration complete!")
    else:
        # Create backup and update original
        backup_path = config_path.with_suffix(f'.yaml.v2_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        print(f"Creating backup: {backup_path}")
        shutil.copy2(config_path, backup_path)
        
        print(f"Writing V3 config to: {config_path}")
        with open(config_path, 'w') as f:
            yaml.dump(v3_config, f, default_flow_style=False, sort_keys=False)
        
        print("Migration complete!")
        print(f"Original config backed up to: {backup_path}")


if __name__ == '__main__':
    main()
