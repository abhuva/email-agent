"""
Utility functions for scanning Obsidian vault for email metadata.

This module provides functions to:
- Scan markdown files in vault directories for UID values
- Extract maximum UID from account-specific vault directories
- Support incremental processing based on existing notes
"""
import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from src.prompt_loader import parse_markdown_frontmatter

logger = logging.getLogger(__name__)


def get_max_uid_from_vault(account_id: str, vault_path: str) -> Optional[int]:
    """
    Scan markdown files in account-specific vault directory and return highest UID.
    
    This function:
    1. Converts account_id to subdirectory name (e.g., 'info.nica' -> 'info-nica')
    2. Scans all .md files in that subdirectory
    3. Extracts UID from YAML frontmatter
    4. Returns the highest UID found, or None if no UIDs found
    
    Args:
        account_id: Account identifier (e.g., 'info.nica')
        vault_path: Base Obsidian vault path
        
    Returns:
        Highest UID found as integer, or None if no UIDs found or directory doesn't exist
        
    Examples:
        >>> get_max_uid_from_vault('info.nica', '/path/to/vault')
        12345
        >>> get_max_uid_from_vault('work', '/path/to/vault')
        None  # No UIDs found or directory doesn't exist
    """
    # Convert account_id to subdirectory name (same logic as AccountProcessor._write_note_to_disk)
    account_subdir = account_id.replace('.', '-')
    account_vault_path = Path(vault_path) / account_subdir
    
    if not account_vault_path.exists():
        logger.debug(f"Vault directory does not exist: {account_vault_path}")
        return None
    
    if not account_vault_path.is_dir():
        logger.warning(f"Vault path is not a directory: {account_vault_path}")
        return None
    
    max_uid = None
    files_scanned = 0
    files_with_uid = 0
    
    # Scan all .md files in the account directory
    for md_file in account_vault_path.glob('*.md'):
        files_scanned += 1
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter
            parsed = parse_markdown_frontmatter(content)
            metadata = parsed.get('metadata', {})
            
            # Extract UID (can be string or int)
            uid_value = metadata.get('uid')
            if uid_value:
                try:
                    uid_int = int(uid_value)
                    files_with_uid += 1
                    if max_uid is None or uid_int > max_uid:
                        max_uid = uid_int
                except (ValueError, TypeError):
                    # Skip invalid UIDs (log at debug level)
                    logger.debug(f"Invalid UID value in {md_file}: {uid_value}")
                    continue
        except Exception as e:
            # Log and continue with other files
            logger.warning(f"Error reading {md_file}: {e}")
            continue
    
    if max_uid is not None:
        logger.info(
            f"Scanned {files_scanned} files in {account_vault_path}, "
            f"found {files_with_uid} files with UIDs, max UID: {max_uid}"
        )
    else:
        logger.debug(
            f"Scanned {files_scanned} files in {account_vault_path}, "
            f"no UIDs found"
        )
    
    return max_uid


def scan_vault_stats(account_id: str, vault_path: str) -> Dict[str, Any]:
    """
    Scan vault directory and return statistics about UIDs found.
    
    Args:
        account_id: Account identifier (e.g., 'info.nica')
        vault_path: Base Obsidian vault path
        
    Returns:
        Dictionary with keys:
        - max_uid: Highest UID found (int or None)
        - min_uid: Lowest UID found (int or None)
        - total_files: Total number of .md files scanned
        - files_with_uid: Number of files containing a valid UID
        - account_subdir: The subdirectory path that was scanned
    """
    account_subdir = account_id.replace('.', '-')
    account_vault_path = Path(vault_path) / account_subdir
    
    stats = {
        'max_uid': None,
        'min_uid': None,
        'total_files': 0,
        'files_with_uid': 0,
        'account_subdir': str(account_vault_path)
    }
    
    if not account_vault_path.exists() or not account_vault_path.is_dir():
        return stats
    
    uids_found = []
    
    for md_file in account_vault_path.glob('*.md'):
        stats['total_files'] += 1
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            parsed = parse_markdown_frontmatter(content)
            metadata = parsed.get('metadata', {})
            uid_value = metadata.get('uid')
            
            if uid_value:
                try:
                    uid_int = int(uid_value)
                    uids_found.append(uid_int)
                    stats['files_with_uid'] += 1
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            logger.debug(f"Error reading {md_file}: {e}")
            continue
    
    if uids_found:
        stats['max_uid'] = max(uids_found)
        stats['min_uid'] = min(uids_found)
    
    return stats
