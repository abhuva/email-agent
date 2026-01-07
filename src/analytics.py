import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_analytics(log_file, analytics_file):
    """
    Generate analytics from log file (V1 compatibility function).
    
    This function parses log files to generate analytics summaries.
    For V2 analytics with note creation metrics, use write_analytics() instead.
    """
    level_counts = {}
    tags_applied = {}
    total = 0
    start_ts = datetime.now().isoformat()

    try:
        with open(log_file, 'r') as f:
            for line in f:
                total += 1
                # Parse basic structure: 2024-01-01T12:34:56 INFO [msgid] message
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                level = parts[1]
                level_counts[level] = level_counts.get(level, 0) + 1
                # Optionally track 'tags_applied' if in message (requires specific log format down the line)
    except FileNotFoundError:
        pass  # zero logs edge case
    summary = {
        "timestamp": start_ts,
        "total_processed": total,
        "level_counts": level_counts,
        "tags_applied": tags_applied,  # can be filled in by higher-level app if needed
    }
    with open(analytics_file, 'a') as af:
        af.write(json.dumps(summary) + '\n')


def write_analytics(
    analytics_file: str,
    analytics_data: Dict[str, Any],
    include_v1_fields: bool = True
) -> bool:
    """
    Write analytics data to analytics file with V2 schema.
    
    V2 Schema (PDD V2):
    {
        "timestamp": "...",
        "total_processed": N,
        "notes_created": N,
        "summaries_generated": N,
        "note_creation_failures": N
    }
    
    Args:
        analytics_file: Path to analytics JSONL file
        analytics_data: Dictionary with analytics metrics from main_loop
        include_v1_fields: If True, include V1 fields (level_counts, tags_applied) for backward compatibility
    
    Returns:
        True if write succeeded, False otherwise
        
    Example:
        >>> analytics = {
        ...     'run_id': '2026-01-06T12:00:00',
        ...     'total_fetched': 10,
        ...     'notes_created': 8,
        ...     'summaries_generated': 3,
        ...     'note_creation_failures': 1
        ... }
        >>> write_analytics('logs/analytics.jsonl', analytics)
        True
    """
    try:
        # Ensure parent directory exists
        analytics_path = Path(analytics_file)
        analytics_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract timestamp (use run_id if available, otherwise current time)
        timestamp = analytics_data.get('run_id') or datetime.now().isoformat()
        
        # Get total_processed (use total_fetched as fallback for backward compatibility)
        total_processed = analytics_data.get('total_fetched', 0)
        
        # Build V2 analytics record with required fields
        analytics_record = {
            "timestamp": timestamp,
            "total_processed": total_processed,
            "notes_created": analytics_data.get('notes_created', 0),
            "summaries_generated": analytics_data.get('summaries_generated', 0),
            "note_creation_failures": analytics_data.get('note_creation_failures', 0)
        }
        
        # Optionally include V1 fields for backward compatibility
        if include_v1_fields:
            # Add level_counts if available (from log parsing)
            if 'level_counts' in analytics_data:
                analytics_record['level_counts'] = analytics_data['level_counts']
            
            # Add tags_applied if available
            if 'tag_breakdown' in analytics_data:
                analytics_record['tags_applied'] = analytics_data['tag_breakdown']
            elif 'tags_applied' in analytics_data:
                analytics_record['tags_applied'] = analytics_data['tags_applied']
        
        # Write as JSONL (one JSON object per line)
        with open(analytics_file, 'a', encoding='utf-8') as af:
            af.write(json.dumps(analytics_record) + '\n')
        
        logger.debug(f"Wrote analytics to {analytics_file}: {analytics_record}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write analytics to {analytics_file}: {e}", exc_info=True)
        return False
