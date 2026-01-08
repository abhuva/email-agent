# V3 Dry-Run Functionality

**Status:** ✅ Complete (Task 11)  
**Module:** `src/dry_run.py`, `src/dry_run_output.py`, `src/dry_run_processor.py`  
**Integration:** `src/cli_v3.py`, `src/obsidian_utils.py`, `src/imap_client.py`, `src/imap_connection.py`

## Overview

The V3 dry-run functionality provides a non-destructive testing mode that processes emails and generates output without writing files or setting IMAP flags. This is implemented as specified in PDD Section 6.

## Features

1. **Global Dry-Run Context**: Thread-safe dry-run mode that can be checked throughout the codebase
2. **File Writing Bypass**: All file writing operations respect dry-run mode
3. **IMAP Flag Bypass**: All IMAP flag setting operations respect dry-run mode
4. **Enhanced Console Output**: Formatted, color-coded output for readability
5. **Detailed Processing Information**: Comprehensive output showing what would happen

## Usage

### Command-Line

```bash
# Enable dry-run mode
python main.py process --dry-run

# Process specific email in dry-run mode
python main.py process --uid 12345 --dry-run

# Combine with other flags
python main.py process --force-reprocess --dry-run
```

### Programmatic Usage

```python
from src.dry_run import set_dry_run, is_dry_run, DryRunContext
from src.dry_run_output import DryRunOutput
from src.dry_run_processor import output_email_processing_info

# Set dry-run mode globally
set_dry_run(True)

# Check if in dry-run mode
if is_dry_run():
    print("Would write file here")
else:
    write_file()

# Use context manager for temporary dry-run mode
with DryRunContext(True):
    # Operations here are in dry-run mode
    process_email()

# Output processing information
output_email_processing_info(
    email_data={'uid': '123', 'subject': 'Test'},
    classification_result=result,
    note_content=note,
    file_path='/path/to/note.md',
    flags_to_set=['AIProcessed']
)
```

## Implementation Details

### Dry-Run Context (`src/dry_run.py`)

- Thread-local storage for dry-run state
- Global functions: `set_dry_run()`, `is_dry_run()`, `get_dry_run()`
- Context manager: `DryRunContext()` for temporary dry-run mode

### Console Output (`src/dry_run_output.py`)

- `DryRunOutput` class provides formatted output:
  - Headers (level 1-3)
  - Info, success, warning, error messages
  - Detail lines (label: value)
  - Code blocks
  - Tables
  - Summary statistics
- Color coding with colorama (cross-platform support)
- Graceful fallback if colorama not available

### Processing Information (`src/dry_run_processor.py`)

- `output_email_processing_info()`: Comprehensive email processing details
- `output_processing_summary()`: End-of-run statistics

## Integration Points

### File Writing

All file writing operations check dry-run mode:

- `src/obsidian_utils.py::safe_write_file()`: Skips actual writing, logs what would be written
- `src/obsidian_note_creation.py::write_obsidian_note()`: Uses `safe_write_file()` which respects dry-run

### IMAP Operations

All IMAP flag operations check dry-run mode:

- `src/imap_client.py::set_flag()`: Skips actual flag setting, logs what would be set
- `src/imap_client.py::clear_flag()`: Skips actual flag clearing, logs what would be cleared
- `src/imap_connection.py::add_tags_to_email()`: Skips actual tag addition, logs what would be added

### CLI Integration

- `src/cli_v3.py::process()`: Sets global dry-run mode when `--dry-run` flag is used
- Displays formatted output using `DryRunOutput` when in dry-run mode

## Output Format

Dry-run mode produces structured, readable output:

```
======================================================================
DRY-RUN MODE ACTIVE
======================================================================

----------------------------------------------------------------------
Email Processing Information
----------------------------------------------------------------------

Email Details
  UID: 12345
  Subject: Test Email
  From: sender@example.com
  Date: 2024-01-15T10:30:00Z

Classification Results
  Importance Score: 9/10 (threshold: 8)
  ✓ Email is IMPORTANT (score >= threshold)
  Spam Score: 2/10 (threshold: 5)
  ✓ Email is not spam (score < threshold)

Generated Note
  Content Length: 1234 characters
  ```markdown
  ---
  uid: 12345
  ...
  ```

File Operations
  ⚠️  Would write note to: /path/to/vault/2024-01-15-103000 - Test-Email.md

IMAP Flag Operations
  ⚠️  Would set IMAP flag: AIProcessed
  Total Flags: 1
```

## Testing

Dry-run mode can be tested by:

1. Running with `--dry-run` flag
2. Verifying no files are written
3. Verifying no IMAP flags are set
4. Checking console output for expected information

## Future Integration

When Task 14 (orchestrator) is implemented, the orchestrator should:

1. Check dry-run mode before file/IMAP operations
2. Call `output_email_processing_info()` for each email
3. Call `output_processing_summary()` at the end
4. Use `DryRunOutput` for all console output in dry-run mode

## Notes

- Dry-run mode is thread-safe using thread-local storage
- All operations that modify state (files, IMAP flags) check dry-run mode
- Console output is formatted for readability with optional color coding
- Processing information includes all relevant details for debugging
