# V3 CLI Module

**Status:** ✅ Complete (Task 2)  
**Module:** `src/cli_v3.py`  
**Tests:** `tests/test_cli_v3.py`

## Overview

The V3 CLI module implements a command-line interface using the `click` library as specified in PDD Section 6. It replaces the argparse-based CLI with a more flexible, subcommand-based structure.

## CLI Structure

### Main Commands

```bash
python main.py process [OPTIONS]        # Process emails
python main.py cleanup-flags [OPTIONS]  # Clean up IMAP flags
```

### Process Command

The `process` command is the main entry point for email processing:

```bash
python main.py process [--uid <ID>] [--force-reprocess] [--dry-run]
```

**Options:**
- `--uid <ID>`: Process a specific email by UID
- `--force-reprocess`: Reprocess emails that have already been processed (ignores processed tags)
- `--dry-run`: Preview processing without making changes (no file writes, no IMAP flag changes)

**Examples:**
```bash
# Process all unprocessed emails
python main.py process

# Process a specific email by UID
python main.py process --uid 12345

# Force reprocess an email (even if already processed)
python main.py process --uid 12345 --force-reprocess

# Preview what would happen (dry run)
python main.py process --dry-run

# Process specific email in dry-run mode
python main.py process --uid 12345 --dry-run
```

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
