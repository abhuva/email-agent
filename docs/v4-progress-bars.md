# V4 Progress Bars for Processing Steps

**Task:** 13  
**Status:** ✅ Complete  
**Module:** `src/progress.py`, `src/account_processor.py`

## Overview

The V4 email processing system includes comprehensive progress bars for all major processing steps, providing visual feedback during long-running operations. Progress bars are implemented using the `tqdm` library and are designed to work seamlessly with multi-account processing.

## Features

- **Email Fetching Progress:** Shows progress while fetching emails from IMAP server per account
- **Email Processing Progress:** Shows overall progress for email processing (parsing, LLM, note generation)
- **Multi-Account Support:** Progress bars are properly isolated per account and don't interfere with each other
- **Configurable:** Progress bars can be disabled via environment variable for CI/CD or non-interactive environments
- **Logging Integration:** Uses `tqdm_write()` for log messages to avoid mangling progress bar display

## Implementation

### Progress Utility Module (`src/progress.py`)

The progress utility module provides a standardized interface for creating and managing progress bars:

```python
from src.progress import create_progress_bar, tqdm_write

# Iterable-based progress (wraps existing iterable)
for email in create_progress_bar(emails, desc="Processing emails", unit="emails"):
    process_email(email)

# Manual-update mode (context manager)
with create_progress_bar(total=100, desc="Processing", unit="items") as pbar:
    for i in range(100):
        do_work()
        pbar.update(1)

# Logging inside progress bars
tqdm_write("Log message that won't interfere with progress bar")
```

### Key Functions

- **`create_progress_bar()`:** Creates a progress bar for iterable-based or manual-update scenarios
- **`tqdm_write()`:** Writes log messages without interfering with progress bar display
- **`is_progress_enabled()`:** Checks if progress bars should be enabled (based on environment variables)

### Configuration

Progress bars can be disabled by setting the `DISABLE_PROGRESS` environment variable:

```bash
# Disable progress bars
export DISABLE_PROGRESS=true

# Or in Python
import os
os.environ['DISABLE_PROGRESS'] = 'true'
```

## Integration Points

### Email Fetching (`src/account_processor.py`)

Progress bars are added to the email fetching loop in `ConfigurableImapClient.get_unprocessed_emails()`:

```python
for uid in create_progress_bar(
    uids,
    desc=f"Fetching emails ({account_name})",
    unit="emails"
):
    email_data = self.get_email_by_uid(uid)
    emails.append(email_data)
```

### Email Processing (`src/account_processor.py`)

Progress bars are added to the main email processing loop in `AccountProcessor.run()`:

```python
for email_dict in create_progress_bar(
    emails,
    desc=f"Processing emails ({self.account_id})",
    unit="emails"
):
    self._process_message(email_dict)
```

The processing progress bar covers all stages:
- Content parsing (HTML to Markdown)
- LLM classification
- Whitelist rule application
- Note generation

## Multi-Account Behavior

When processing multiple accounts:

1. **Per-Account Progress Bars:** Each account gets its own progress bars for fetching and processing
2. **Isolation:** Progress bars are properly isolated between accounts and don't interfere with each other
3. **Account Identification:** Progress bars include the account identifier in the description for clarity

Example output when processing multiple accounts:

```
Fetching emails (work@example.com): 100%|██████████| 10/10 [00:05<00:00,  1.98emails/s]
Processing emails (work): 100%|██████████| 10/10 [00:30<00:00,  3.33emails/s]
Fetching emails (personal@example.com): 100%|██████████| 5/5 [00:03<00:00,  1.67emails/s]
Processing emails (personal): 100%|██████████| 5/5 [00:15<00:00,  3.33emails/s]
```

## Dependencies

- **tqdm:** Progress bar library (added to `requirements.txt`)
- **tqdm.auto:** Automatically selects the best progress bar implementation for the environment (CLI, notebook, etc.)

## Testing

Progress bars are tested as part of the account processor tests. The progress utility module includes:

- Automatic fallback when tqdm is not available (dummy progress bar that does nothing)
- Environment variable detection for disabling progress bars
- Proper handling of logging within progress bar loops

## Usage Examples

### Basic Usage

```python
from src.progress import create_progress_bar

# Process emails with progress bar
emails = fetch_emails()
for email in create_progress_bar(emails, desc="Processing", unit="emails"):
    process_email(email)
```

### Manual Update Mode

```python
from src.progress import create_progress_bar

# Process with manual updates
with create_progress_bar(total=100, desc="Processing", unit="items") as pbar:
    for i in range(100):
        do_work()
        pbar.update(1)
```

### Logging Inside Progress Bars

```python
from src.progress import create_progress_bar, tqdm_write

for item in create_progress_bar(items, desc="Processing"):
    if should_log():
        tqdm_write(f"Processing item: {item}")  # Won't break progress bar
    process(item)
```

## Configuration Options

Progress bars support various configuration options:

- **`desc`:** Description text for the progress bar
- **`unit`:** Unit label (e.g., "emails", "items", "notes")
- **`mininterval`:** Minimum update interval in seconds (default: 0.1)
- **`ncols`:** Number of columns for progress bar (None = auto)
- **`disable`:** Override automatic disable detection

## Best Practices

1. **Use Descriptive Labels:** Include account identifiers or operation names in progress bar descriptions
2. **Use Appropriate Units:** Choose units that make sense (emails, items, notes, etc.)
3. **Log with tqdm_write():** Always use `tqdm_write()` for logging inside progress bar loops
4. **Disable in CI/CD:** Set `DISABLE_PROGRESS=true` in CI/CD environments
5. **Handle Errors Gracefully:** Progress bars should not break if an operation fails

## Related Documentation

- [V4 Account Processor](v4-account-processor.md) - Account processing pipeline
- [V4 Master Orchestrator](v4-orchestrator.md) - Multi-account orchestration
- [V4 Configuration System](v4-configuration.md) - Configuration management

## PDD Alignment

This implementation aligns with PDD V4 requirements for:
- Multi-account processing with visual feedback
- Progress tracking for long-running operations
- User experience improvements for batch processing

## Future Enhancements

Potential future improvements:
- Nested progress bars for multi-stage operations
- Progress persistence across restarts
- Estimated time remaining per account
- Progress aggregation across multiple accounts
