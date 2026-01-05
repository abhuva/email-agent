import json
from datetime import datetime

def generate_analytics(log_file, analytics_file):
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
