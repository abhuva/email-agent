# CLI Module

**Status:** ✅ Complete (Task 2, Task 11)  
**Module:** `src/cli_v3.py`  
**Tests:** `tests/test_cli_v3.py`

## Overview

The CLI module implements a command-line interface using the `click` library as specified in PDD Section 6. It supports both V3 (single-account) and V4 (multi-account) processing modes. The V3 mode uses the original Pipeline class, while V4 mode uses the MasterOrchestrator for multi-account processing.

## CLI Structure

### Main Commands

```bash
python main.py process [OPTIONS]        # Process emails (V3 or V4 mode)
python main.py cleanup-flags [OPTIONS]  # Clean up IMAP flags
python main.py backfill [OPTIONS]       # Process historical emails (backfill)
python main.py show-config [OPTIONS]    # Display merged configuration (V4 mode)
```

### Process Command

The `process` command is the main entry point for email processing. It supports both V3 (single-account) and V4 (multi-account) modes:

```bash
# V3 Mode (single account, default behavior)
python main.py process [--uid <ID>] [--force-reprocess] [--dry-run] [--max-emails <N>] [--debug-prompt]

# V4 Mode (multi-account)
python main.py process --account <name> [--dry-run]
python main.py process --all [--dry-run]
```

**V3 Mode Options:**
- `--uid <ID>`: Process a specific email by UID
- `--force-reprocess`: Reprocess emails that have already been processed (ignores processed tags)
- `--dry-run`: Preview processing without making changes (no file writes, no IMAP flag changes)
- `--max-emails <N>`: Maximum number of emails to process
- `--debug-prompt`: Write the formatted classification prompt to a debug file

**V4 Mode Options:**
- `--account <name>`: Process a specific account by name (mutually exclusive with --all)
- `--all`: Process all available accounts (mutually exclusive with --account)
- `--dry-run`: Preview processing without making changes

**Examples:**
```bash
# V3 Mode: Process all unprocessed emails
python main.py process

# V3 Mode: Process a specific email by UID
python main.py process --uid 12345

# V3 Mode: Force reprocess an email
python main.py process --uid 12345 --force-reprocess

# V3 Mode: Preview what would happen (dry run)
python main.py process --dry-run

# V4 Mode: Process 'work' account
python main.py process --account work

# V4 Mode: Process all accounts
python main.py process --all

# V4 Mode: Preview processing for 'work' account
python main.py process --account work --dry-run
```

**Note:** When `--account` or `--all` is specified, the command uses V4 MasterOrchestrator for multi-account processing. Otherwise, it uses V3 Pipeline for single-account processing.

### Cleanup Flags Command

The `cleanup-flags` command removes application-specific IMAP flags from emails on the server:

```bash
python main.py cleanup-flags [--dry-run]
```

**Options:**
- `--dry-run`: Preview which flags would be removed without actually removing them

**Features:**
- **Mandatory confirmation prompt** (security requirement from PDD)
- Removes only application-specific flags (as configured in `imap.application_flags`)
- Includes safety warnings before execution
- Comprehensive scanning and logging

**Examples:**
```bash
# Preview what would be removed (dry-run)
python main.py cleanup-flags --dry-run

# Actually remove flags (requires confirmation)
python main.py cleanup-flags
# Will prompt: "Type 'yes' to confirm and proceed, or anything else to cancel: "
```

**See Also:** [V3 Cleanup Flags Documentation](v3-cleanup-flags.md) for complete details.

### Backfill Command

The `backfill` command processes all historical emails with the new V3 classification system:

```bash
python main.py backfill [OPTIONS]
```

**Options:**
- `--start-date <YYYY-MM-DD>`: Start date for date range filter
- `--end-date <YYYY-MM-DD>`: End date for date range filter
- `--folder <FOLDER>`: IMAP folder to process (default: INBOX)
- `--force-reprocess`: Reprocess emails even if already processed (default: True)
- `--dry-run`: Preview mode without side effects
- `--max-emails <N>`: Maximum number of emails to process
- `--calls-per-minute <N>`: Maximum API calls per minute for throttling

**Examples:**
```bash
# Process all emails
python main.py backfill

# Process emails from a date range
python main.py backfill --start-date 2024-01-01 --end-date 2024-12-31

# Process specific folder with limit
python main.py backfill --folder "Sent" --max-emails 100

# Test with dry-run
python main.py backfill --dry-run --max-emails 10
```

**Features:**
- Date range filtering
- Folder selection
- Progress tracking with ETA
- API throttling to prevent rate limiting
- Comprehensive logging and summary statistics

**See Also:** [V3 Backfill Documentation](v3-backfill.md) for complete details.

### Show-Config Command (V4)

The `show-config` command displays the merged configuration for a specific account:

```bash
python main.py show-config --account <name> [--format yaml|json]
```

**Options:**
- `--account <name>`: **Required.** Account name to show configuration for
- `--format <format>`: Output format - `yaml` (default) or `json`

**Examples:**
```bash
# Show configuration for 'work' account (YAML format)
python main.py show-config --account work

# Show configuration for 'work' account (JSON format)
python main.py show-config --account work --format json

# Show configuration for 'personal' account
python main.py show-config --account personal
```

**Features:**
- Displays merged configuration (global config + account-specific overrides)
- Useful for debugging configuration issues
- Supports both YAML and JSON output formats
- Validates account name format

**Note:** This command requires V4 multi-account configuration structure with `config/accounts/` directory.

## Configuration Options

Both commands support configuration file options:

```bash
--config <PATH>  # Path to YAML configuration file (default: config/config.yaml)
--env <PATH>     # Path to .env file (default: .env)
```

**Example:**
```bash
python main.py process --config config/custom.yaml --env .env.production
```

## Architecture

### Click-Based Structure

The CLI uses `click` groups and commands:

```python
@click.group()
def cli():
    """Main CLI group"""

@cli.command()
@click.option('--uid', ...)
@click.option('--force-reprocess', ...)
@click.option('--dry-run', ...)
def process(uid, force_reprocess, dry_run):
    """Process emails"""
```

### Options Structure

Options are structured into dataclasses for type safety:

```python
@dataclass
class ProcessOptions:
    uid: Optional[str]
    force_reprocess: bool
    dry_run: bool
    config_path: str
    env_path: str
```

## Integration with Settings Facade

The CLI initializes the settings facade before processing:

```python
from src.settings import settings

# Initialize settings with config files
settings.initialize(config_path, env_path)
```

All downstream modules then access configuration through the settings facade.

## Error Handling

The CLI handles:
- **Configuration errors**: Invalid YAML, missing files, validation failures
- **Missing environment variables**: Clear error messages for required secrets
- **IMAP connection errors**: Connection failures, authentication issues
- **LLM API errors**: API failures, rate limiting, invalid responses

All errors are logged and displayed with clear messages.

## Usage Examples

### Example 1: Normal Processing

```bash
# Process all unprocessed emails
python main.py process

# Output:
# Connecting to IMAP server...
# Found 5 unprocessed emails
# Processing email 1/5...
# Processing email 2/5...
# ...
# Processing complete: 5 emails processed, 0 errors
```

### Example 2: Single Email Processing

```bash
# Process specific email
python main.py process --uid 12345

# Output:
# Connecting to IMAP server...
# Fetching email UID 12345...
# Processing email...
# Classification: important=True, spam=False
# Note created: /path/to/vault/2024-01-15-143022 - Subject.md
# Processing complete
```

### Example 3: Dry Run

```bash
# Preview processing without changes
python main.py process --dry-run

# Output:
# [DRY RUN MODE]
# Connecting to IMAP server...
# Found 5 unprocessed emails
# 
# Email 1:
#   UID: 12345
#   Subject: Important Meeting
#   Would classify as: important=True, spam=False
#   Would create note: /path/to/vault/2024-01-15-143022 - Important Meeting.md
#   Would set IMAP flag: AIProcessed
# 
# Email 2:
#   ...
# 
# [DRY RUN] No changes made
```

### Example 4: Force Reprocess

```bash
# Reprocess an already-processed email
python main.py process --uid 12345 --force-reprocess

# Output:
# Warning: Email UID 12345 already processed (has AIProcessed flag)
# Force reprocessing enabled - proceeding...
# Processing email...
# ...
```

## Migration from V2 CLI

### V2 (Old - argparse)

```bash
python main.py --config config.yaml --max-emails 10
```

### V3 (New - click)

```bash
python main.py process --config config.yaml
# max_emails_per_run is now in config.yaml
```

**Key Changes:**
- Subcommands instead of flags (`process` instead of direct execution)
- Configuration options moved to config file
- More structured error handling
- Better help text and documentation

## Testing

Run CLI tests:
```bash
pytest tests/test_cli_v3.py -v
```

Test coverage includes:
- Command parsing and validation
- Option handling
- Error handling
- Settings initialization
- Dry-run mode

## PDD Alignment

This module implements:
- **PDD Section 5.1**: Refactor CLI from argparse to click
- **PDD Section 6**: CLI design with `process` subcommand and flags
- **PDD Section 6**: `cleanup-flags` subcommand with confirmation prompt

## Reference

- **PDD Specification**: `pdd.md` Sections 5.1, 6
- **Module Code**: `src/cli_v3.py`
- **Tests**: `tests/test_cli_v3.py`
- **Click Documentation**: https://click.palletsprojects.com/
- **Configuration**: `docs/v3-configuration.md`
