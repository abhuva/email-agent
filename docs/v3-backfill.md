# V3 Backfill Module

**Status:** ✅ Complete (Task 15)  
**Module:** `src/backfill.py`  
**Integration:** `src/cli_v3.py`

## Overview

The V3 backfill module provides functionality to process all historical emails in a mailbox with the new V3 classification system. It supports date range filtering, folder selection, progress tracking, API throttling, and comprehensive logging.

## Features

- **Date Range Filtering**: Process emails within a specific date range
- **Folder Selection**: Target specific IMAP folders (INBOX, Sent, etc.)
- **Progress Tracking**: Real-time progress updates with ETA calculations
- **API Throttling**: Prevents rate limiting with configurable call limits
- **Comprehensive Logging**: Detailed logging with summary statistics
- **Dry-Run Mode**: Preview mode without side effects
- **Batch Processing**: Process large volumes of emails efficiently

## Architecture

The backfill system consists of three main components:

1. **BackfillProcessor**: Main orchestration class that coordinates backfill operations
2. **ProgressTracker**: Tracks and displays progress (determinate/indeterminate modes)
3. **Throttler**: Manages API call rate limiting to prevent rate limit errors

## Usage

### Command-Line Interface

```bash
# Process all emails
python main.py backfill

# Process emails from a date range
python main.py backfill --start-date 2024-01-01 --end-date 2024-12-31

# Process specific folder
python main.py backfill --folder "Sent"

# Limit number of emails (useful for testing)
python main.py backfill --max-emails 100

# Dry-run mode (preview without side effects)
python main.py backfill --dry-run --max-emails 10

# Custom throttling rate
python main.py backfill --calls-per-minute 30
```

### Programmatic Usage

```python
from src.backfill import BackfillProcessor
from src.settings import settings
from datetime import date

# Initialize settings
settings.initialize('config/config.yaml', '.env')

# Create processor
processor = BackfillProcessor()

# Backfill all emails
summary = processor.backfill_emails()

# Backfill with date range
start_date = date(2024, 1, 1)
end_date = date(2024, 12, 31)
summary = processor.backfill_emails(
    start_date=start_date,
    end_date=end_date
)

# Backfill specific folder
summary = processor.backfill_emails(folder='INBOX')

# Backfill with all options
summary = processor.backfill_emails(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    folder='Sent',
    force_reprocess=True,
    dry_run=False,
    max_emails=1000
)

# Access summary statistics
print(f"Processed: {summary.processed}")
print(f"Failed: {summary.failed}")
print(f"Total time: {summary.total_time:.2f}s")
```

## CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--start-date` | YYYY-MM-DD | None (all time) | Start date for date range filter |
| `--end-date` | YYYY-MM-DD | None (all time) | End date for date range filter |
| `--folder` | string | INBOX | IMAP folder to process |
| `--force-reprocess` | flag | True | Reprocess emails even if already processed |
| `--dry-run` | flag | False | Preview mode (no files written, no flags set) |
| `--max-emails` | integer | None (unlimited) | Maximum number of emails to process |
| `--calls-per-minute` | integer | From settings or 60 | Maximum API calls per minute |

## Progress Tracking

The backfill system provides real-time progress updates:

```
Progress: 50/100 (50.0%) - Processed: 48, Failed: 2, Skipped: 0, ETA: 45.2s
```

**Features:**
- Determinate mode: Shows percentage and ETA when total count is known
- Indeterminate mode: Shows counts and elapsed time when total is unknown
- Auto-updates every second during processing
- Final summary with complete statistics

## Throttling

The throttling system prevents API rate limiting:

- **Configurable Rate**: Set via `--calls-per-minute` or from settings
- **Sliding Window**: Tracks calls over the last 60 seconds
- **Automatic Waiting**: Waits when rate limit would be exceeded
- **Exponential Backoff**: Built-in retry logic with backoff for rate limit errors

**Default Throttling:**
- Uses `settings.get_openrouter_retry_delay_seconds()` to calculate default rate
- Default: 60 calls per minute (if settings not available)

## Logging

The backfill system provides comprehensive logging:

### Operational Logs (`agent.log`)
- Start/end times
- Configuration parameters
- Progress updates at regular intervals
- Error messages with stack traces
- Summary statistics

### Structured Analytics (`analytics.jsonl`)
- Per-email processing results
- Success/failure status
- Classification scores
- Processing timestamps

### Summary Report
At the end of backfill, a comprehensive summary is displayed:

```
======================================================================
BACKFILL OPERATION COMPLETE
======================================================================
Total emails found: 1000
  ✓ Successfully processed: 985
  ✗ Failed: 15
  ⊘ Skipped: 0
Total time: 1234.56s
Average time per email: 1.23s
Success rate: 98.5%
Start time: 2024-01-15 10:00:00
End time: 2024-01-15 10:20:34
======================================================================
```

## Error Handling

The backfill system handles errors gracefully:

- **Per-Email Isolation**: Failures for one email don't affect others
- **Comprehensive Logging**: All errors are logged with full context
- **Summary Statistics**: Failed emails are tracked and reported
- **Graceful Degradation**: Processing continues even if some emails fail

## Performance Considerations

- **Memory Management**: Emails are processed one at a time to prevent memory leaks
- **Connection Sharing**: IMAP connection is shared between backfill processor and pipeline
- **Batch Processing**: Large volumes are handled efficiently with progress tracking
- **Throttling**: API rate limits are respected to prevent service disruptions

## Use Cases

1. **Initial Migration**: Process all historical emails when upgrading to V3
2. **Date Range Processing**: Reprocess emails from a specific time period
3. **Folder-Specific Backfill**: Process emails in specific folders (Sent, Archive, etc.)
4. **Testing**: Use `--max-emails` and `--dry-run` to test before full backfill
5. **Recovery**: Reprocess emails that failed during initial processing

## Configuration

The backfill system uses the settings facade for configuration:

- **IMAP Settings**: Server, port, credentials, query
- **Throttling**: Retry attempts, retry delay (used to calculate default rate)
- **Processing**: Max emails per run, thresholds
- **Paths**: Log files, analytics files

All configuration access is through `settings.py` facade, not direct YAML access.

## Integration

The backfill module integrates with:

- **Pipeline** (`src/orchestrator.py`): Uses pipeline's email processing logic
- **IMAP Client** (`src/imap_client.py`): Retrieves emails from IMAP server
- **Settings** (`src/settings.py`): Accesses all configuration values
- **Logging** (`src/v3_logger.py`): Writes to operational logs and structured analytics

## Examples

### Example 1: Backfill Last Year's Emails

```bash
python main.py backfill \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --max-emails 5000
```

### Example 2: Test Backfill on Small Sample

```bash
python main.py backfill \
  --dry-run \
  --max-emails 10 \
  --start-date 2024-01-01
```

### Example 3: Backfill Sent Folder

```bash
python main.py backfill \
  --folder "Sent" \
  --force-reprocess
```

### Example 4: Programmatic Backfill with Custom Throttling

```python
from src.backfill import BackfillProcessor
from datetime import date

processor = BackfillProcessor(calls_per_minute=30)
summary = processor.backfill_emails(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 6, 30),
    folder='INBOX',
    max_emails=1000
)
```

## Troubleshooting

### Issue: Rate Limiting Errors

**Solution**: Reduce `--calls-per-minute` or increase retry delay in settings

```bash
python main.py backfill --calls-per-minute 30
```

### Issue: Backfill Takes Too Long

**Solution**: Use date range filtering or limit with `--max-emails`

```bash
python main.py backfill --start-date 2024-01-01 --max-emails 100
```

### Issue: Memory Issues with Large Backfills

**Solution**: The system processes emails one at a time to prevent memory leaks. If issues persist, use `--max-emails` to process in batches.

### Issue: Some Emails Fail Processing

**Solution**: Check logs for error details. Failed emails are logged with full context. You can reprocess failed emails by running backfill again (they won't be skipped if `--force-reprocess` is used).

## See Also

- [V3 Orchestrator](v3-orchestrator.md) - Pipeline orchestration
- [V3 CLI](v3-cli.md) - Command-line interface
- [V3 IMAP Client](v3-imap-client.md) - IMAP operations
- [V3 Logging Integration](v3-logging-integration.md) - Logging system
