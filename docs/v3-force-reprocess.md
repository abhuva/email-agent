# V3 Force-Reprocess Feature

**Status:** ✅ Complete (Task 12)  
**Module:** `src/imap_client.py`, `src/obsidian_note_creation.py`, `src/v3_logger.py`  
**CLI Flag:** `--force-reprocess`

## Overview

The force-reprocess feature allows reprocessing of emails that have already been processed. This is useful when:
- You want to update notes with new classification logic
- You need to regenerate notes after template changes
- You want to reprocess emails after fixing bugs in the processing pipeline
- You need to update notes with new metadata or formatting

## Usage

### Command-Line Usage

```bash
# Reprocess a specific email
python main.py process --uid 12345 --force-reprocess

# Reprocess all emails (including already processed ones)
python main.py process --force-reprocess

# Combine with dry-run to preview
python main.py process --force-reprocess --dry-run
```

### How It Works

When `--force-reprocess` is enabled:

1. **IMAP Query**: The system includes processed emails in the search query (normally they are excluded)
2. **File Overwriting**: Existing note files are overwritten instead of creating new unique filenames
3. **IMAP Flags**: Flags are updated normally after reprocessing (processed tag is re-applied)
4. **Logging**: Reprocessing events are logged with distinct "REPROCESSED" indicators

## Implementation Details

### IMAP Client Changes

The `ImapClient.get_unprocessed_emails()` method now accepts a `force_reprocess` parameter:

```python
from src.imap_client import ImapClient

client = ImapClient()
client.connect()

# Normal mode: excludes processed emails
emails = client.get_unprocessed_emails()

# Force-reprocess mode: includes all emails
emails = client.get_unprocessed_emails(force_reprocess=True)
```

**Search Query Behavior:**
- **Normal mode**: `(user_query NOT KEYWORD "AIProcessed")` - excludes processed emails
- **Force-reprocess mode**: `user_query` - includes all emails matching the query

### Note File Handling

The `write_obsidian_note()` and `create_obsidian_note_for_email()` functions now accept an `overwrite` parameter:

```python
from src.obsidian_note_creation import write_obsidian_note

# Normal mode: creates unique filename if file exists
note_path = write_obsidian_note(
    note_content=content,
    email_subject="Test Email",
    vault_path="/path/to/vault",
    overwrite=False  # Default
)

# Force-reprocess mode: overwrites existing file
note_path = write_obsidian_note(
    note_content=content,
    email_subject="Test Email",
    vault_path="/path/to/vault",
    overwrite=True  # Overwrites if exists
)
```

**File Naming:**
- **Normal mode**: If file exists, creates unique filename (e.g., `note (1).md`)
- **Force-reprocess mode**: Overwrites existing file with same name

### Logging

The `EmailLogger` class includes a dedicated method for reprocessing events:

```python
from src.v3_logger import get_email_logger

logger = get_email_logger()

# Normal processing
logger.log_email_processed(
    uid='12345',
    status='success',
    importance_score=9,
    spam_score=2
)

# Reprocessing (distinct logging)
logger.log_email_reprocessed(
    uid='12345',
    status='success',
    importance_score=9,
    spam_score=2
)
```

**Log Output:**
- **Normal processing**: `Email processed: UID 12345 | Importance: 9/10, Spam: 2/10`
- **Reprocessing**: `Email REPROCESSED: UID 12345 | Importance: 9/10, Spam: 2/10`

Both events are logged to:
1. **Operational logs** (`agent.log`): Human-readable log entries
2. **Structured analytics** (`analytics.jsonl`): JSONL format with uid, timestamp, status, scores

## Integration with Orchestrator

When the orchestrator (Task 14) is implemented, it will use these functions as follows:

```python
from src.imap_client import ImapClient
from src.obsidian_note_creation import create_obsidian_note_for_email
from src.v3_logger import get_email_logger

# Get force_reprocess flag from CLI options
force_reprocess = options.force_reprocess

# Retrieve emails (including processed if force_reprocess=True)
client = ImapClient()
client.connect()
emails = client.get_unprocessed_emails(force_reprocess=force_reprocess)

# Process each email
logger = get_email_logger()
for email in emails:
    # ... classification logic ...
    
    # Create note with overwrite flag
    result = create_obsidian_note_for_email(
        email=email,
        config=config,
        overwrite=force_reprocess  # Overwrite if reprocessing
    )
    
    # Log with appropriate method
    if force_reprocess:
        logger.log_email_reprocessed(
            uid=email['uid'],
            status='success',
            importance_score=score,
            spam_score=spam_score
        )
    else:
        logger.log_email_processed(
            uid=email['uid'],
            status='success',
            importance_score=score,
            spam_score=spam_score
        )
```

## Use Cases

### 1. Template Updates

After updating the note template, reprocess emails to regenerate notes with new format:

```bash
python main.py process --force-reprocess
```

### 2. Classification Logic Updates

After improving the scoring criteria or thresholds, reprocess to get updated classifications:

```bash
python main.py process --force-reprocess
```

### 3. Bug Fixes

After fixing bugs in the processing pipeline, reprocess affected emails:

```bash
python main.py process --uid 12345 --force-reprocess
```

### 4. Testing

Use with `--dry-run` to preview what would happen:

```bash
python main.py process --force-reprocess --dry-run
```

## Safety Considerations

1. **File Overwriting**: Force-reprocess overwrites existing note files. Make backups if needed.
2. **IMAP Flags**: The processed flag is re-applied after successful reprocessing.
3. **Logging**: All reprocessing events are logged for audit purposes.
4. **Dry-Run**: Always test with `--dry-run` first to preview changes.

## Testing

The force-reprocess feature is tested in:
- `tests/test_imap_client.py`: Tests for `get_unprocessed_emails(force_reprocess=True)`
- `tests/test_cli_v3.py`: Tests for `--force-reprocess` flag parsing
- `tests/test_obsidian_utils.py`: Tests for file overwriting behavior

Run tests:
```bash
pytest tests/test_imap_client.py -v
pytest tests/test_cli_v3.py::test_process_command_force_reprocess -v
```

## PDD Alignment

This feature implements:
- **PDD Section 6**: `--force-reprocess` flag for the `process` subcommand
- **Task 12**: Force-reprocess capability with file overwriting and distinct logging

## Reference

- **PDD Specification**: `pdd.md` Section 6
- **CLI Module**: `src/cli_v3.py`
- **IMAP Client**: `src/imap_client.py`
- **Note Creation**: `src/obsidian_note_creation.py`
- **Logging**: `src/v3_logger.py`
- **Tests**: `tests/test_imap_client.py`, `tests/test_cli_v3.py`
