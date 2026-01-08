# V3 Cleanup Flags Command

**Status:** ✅ Complete (Task 13)  
**Module:** `src/cleanup_flags.py`  
**CLI Integration:** `src/cli_v3.py`

## Overview

The cleanup-flags command provides a safeguarded way to remove application-specific IMAP flags from emails on the server. This is useful for resetting processing state or cleaning up flags after testing or configuration changes.

## Features

- **Application-specific flag removal** - Only removes flags defined in configuration
- **Mandatory confirmation prompt** - Security requirement from PDD (prevents accidental execution)
- **Dry-run mode** - Preview what would be removed without making changes
- **Comprehensive scanning** - Identifies all emails with application-specific flags
- **Detailed logging** - Logs all operations with timestamps and email details
- **Error isolation** - Failures on individual emails don't stop the operation

## Configuration

The cleanup command uses the `application_flags` configuration in `config.yaml`:

```yaml
imap:
  application_flags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
```

These flags are considered "application-specific" and safe to remove. The command will **only** remove flags that are in this list, protecting system flags and other application flags.

## Usage

### Basic Usage

```bash
# Preview what would be removed (dry-run)
python main.py cleanup-flags --dry-run

# Actually remove flags (requires confirmation)
python main.py cleanup-flags
```

### Command Options

```bash
python main.py cleanup-flags [OPTIONS]
```

**Options:**
- `--dry-run`: Preview which flags would be removed without actually removing them
- `--config <PATH>`: Path to YAML configuration file (default: `config/config.yaml`)
- `--env <PATH>`: Path to .env file (default: `.env`)

### Dry-Run Mode

Dry-run mode allows you to preview the cleanup operation without making any changes:

```bash
python main.py cleanup-flags --dry-run
```

**Output includes:**
- List of emails that would be affected (UID and subject)
- Application-specific flags that would be removed from each email
- Summary statistics (total emails, total flags)

**Example output:**
```
Found 3 email(s) with application-specific flags:

  1. UID: 12345
     Subject: Test Email 1
     Application flags: AIProcessed, ObsidianNoteCreated

  2. UID: 12346
     Subject: Test Email 2
     Application flags: AIProcessed

Summary: 3 email(s), 4 flag(s) to remove
```

### Confirmation Prompt

When running without `--dry-run`, the command requires explicit confirmation:

```
======================================================================
WARNING: This command will remove application-specific flags from emails
in your IMAP mailbox. This action cannot be undone.
======================================================================

Application-specific flags to remove: AIProcessed, ObsidianNoteCreated, NoteCreationFailed

This may cause emails to be reprocessed on the next run.

Type 'yes' to confirm and proceed, or anything else to cancel: 
```

**Security:** The confirmation prompt is a **mandatory requirement** from the PDD. The command will abort if you don't type 'yes' exactly.

### Execution Flow

1. **Scan Phase**: Connects to IMAP server and scans all emails for application-specific flags
2. **Display Phase**: Shows which emails and flags would be affected
3. **Confirmation Phase**: (Non-dry-run only) Requires explicit 'yes' confirmation
4. **Removal Phase**: Removes flags from emails (or previews in dry-run)
5. **Summary Phase**: Displays statistics about the operation

### Output Summary

After execution, the command displays a summary:

```
======================================================================
Cleanup Summary:
  Emails scanned: 10
  Emails with flags: 3
  Flags removed: 4
  Emails modified: 3
  Errors: 0
======================================================================
```

## Implementation Details

### Module Structure

The cleanup functionality is implemented in `src/cleanup_flags.py`:

- **CleanupFlags**: Main class that orchestrates the cleanup operation
- **FlagScanResult**: Dataclass representing scan results for a single email
- **CleanupSummary**: Dataclass with operation statistics

### Key Methods

- `scan_flags(dry_run)`: Scans all emails and identifies application-specific flags
- `remove_flags(scan_results, dry_run)`: Removes flags from emails
- `format_scan_results(results)`: Formats scan results for display
- `connect()` / `disconnect()`: IMAP connection management

### Error Handling

- **Connection errors**: Logged and raised as `CleanupFlagsError`
- **Individual email errors**: Logged but don't stop the operation
- **Flag removal errors**: Counted in summary but don't abort the operation

### Logging

All operations are logged to the operational log file (`logs/agent.log`):

- **INFO**: Scan start/complete, summary statistics
- **DEBUG**: Individual email flag details
- **WARNING**: Errors on individual emails
- **ERROR**: Connection failures, critical errors

## Examples

### Example 1: Preview Cleanup

```bash
$ python main.py cleanup-flags --dry-run

======================================================================
WARNING: This command will remove application-specific flags from emails
in your IMAP mailbox. This action cannot be undone.
======================================================================

Application-specific flags to remove: AIProcessed, ObsidianNoteCreated, NoteCreationFailed

This may cause emails to be reprocessed on the next run.

[DRY RUN MODE] No flags will actually be removed.

Scanning emails for application-specific flags...

Found 2 email(s) with application-specific flags:

  1. UID: 12345
     Subject: Important Meeting
     Application flags: AIProcessed, ObsidianNoteCreated

  2. UID: 12346
     Subject: Newsletter
     Application flags: AIProcessed

Summary: 2 email(s), 3 flag(s) to remove

[DRY RUN] Preview of what would be removed:

======================================================================
Cleanup Summary:
  Emails scanned: 2
  Emails with flags: 2
  Flags removed: 3
  Emails modified: 2
  Errors: 0
======================================================================

[DRY RUN] No flags were actually removed.
```

### Example 2: Actual Cleanup

```bash
$ python main.py cleanup-flags

======================================================================
WARNING: This command will remove application-specific flags from emails
in your IMAP mailbox. This action cannot be undone.
======================================================================

Application-specific flags to remove: AIProcessed, ObsidianNoteCreated, NoteCreationFailed

This may cause emails to be reprocessed on the next run.

Type 'yes' to confirm and proceed, or anything else to cancel: yes

Scanning emails for application-specific flags...

Found 2 email(s) with application-specific flags:

  1. UID: 12345
     Subject: Important Meeting
     Application flags: AIProcessed, ObsidianNoteCreated

  2. UID: 12346
     Subject: Newsletter
     Application flags: AIProcessed

Summary: 2 email(s), 3 flag(s) to remove

Removing application-specific flags...

======================================================================
Cleanup Summary:
  Emails scanned: 2
  Emails with flags: 2
  Flags removed: 3
  Emails modified: 2
  Errors: 0
======================================================================

Cleanup complete!
```

## Safety Features

1. **Configuration-based flag list**: Only removes flags explicitly listed in configuration
2. **Mandatory confirmation**: Prevents accidental execution
3. **Dry-run mode**: Allows safe preview before actual execution
4. **Error isolation**: Individual email failures don't stop the operation
5. **Comprehensive logging**: All operations are logged for audit purposes

## Use Cases

- **Reset processing state**: Remove all processing flags to reprocess emails
- **Clean up after testing**: Remove test flags from emails
- **Configuration changes**: Clean up flags when changing flag names
- **Troubleshooting**: Remove flags to diagnose processing issues

## Related Documentation

- **[V3 CLI](v3-cli.md)** - Complete CLI documentation
- **[V3 Configuration](v3-configuration.md)** - Configuration system
- **[V3 IMAP Client](v3-imap-client.md)** - IMAP operations
- **[PDD Section 6](pdd.md)** - PDD specification for cleanup-flags command

## Reference

- **PDD Specification**: `pdd.md` Section 6 (Frontend Implementation Plan)
- **Module Code**: `src/cleanup_flags.py`
- **CLI Integration**: `src/cli_v3.py`
- **Configuration**: `config/config.yaml.example` (see `imap.application_flags`)
