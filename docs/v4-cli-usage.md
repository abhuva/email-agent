# V4 Command-Line Usage Guide

**Status:** Complete  
**Task:** 20.3  
**Audience:** Operators, Developers, All Users  
**PDD Reference:** [pdd_V4.md](../pdd_V4.md) Section 3.1

---

## Overview

Complete reference for V4 command-line interface, including all commands, options, flags, and common workflows. V4 CLI uses V4 components exclusively (MasterOrchestrator, ConfigLoader) and supports multi-account processing with account isolation.

---

## CLI Overview

V4 CLI is built using the `click` library and supports:

- **Multi-Account Processing:** Process specific accounts or all accounts with account isolation
- **Dry-Run Mode:** Preview processing without side effects
- **Configuration Management:** View and validate configurations
- **Account-Specific Operations:** All commands support account-specific configuration

**Entry Point:**
```bash
python main.py <command> [options]
```

**Help:**
```bash
python main.py --help
python main.py <command> --help
```

---

## Main Commands

### Process Command

The `process` command is the main entry point for email processing. It requires either `--account <name>` or `--all` to specify which accounts to process.

**Command:**
```bash
python main.py process [OPTIONS]
```

**Usage:**
```bash
# Process specific account
python main.py process --account <name> [OPTIONS]

# Process all accounts
python main.py process --all [OPTIONS]
```

**Required Options:**
- `--account <name>`: Process a specific account by name (mutually exclusive with --all)
- `--all`: Process all available accounts (mutually exclusive with --account)

**Additional Options:**
- `--dry-run`: Preview processing without making changes (no file writes, no IMAP flag changes)
- `--uid <ID>`: Process a specific email by UID (requires --account, cannot be used with --all)
- `--force-reprocess`: Reprocess emails that have already been processed (ignores processed tags)
- `--max-emails <N>`: Maximum number of emails to process (overrides config max_emails_per_run)
- `--debug-prompt`: Write the formatted classification prompt to a debug file in logs/ directory

**Examples:**
```bash
# Process 'work' account
python main.py process --account work

# Process all accounts
python main.py process --all

# Preview processing for 'work' account
python main.py process --account work --dry-run

# Process specific email by UID
python main.py process --account work --uid 12345

# Force reprocess an email
python main.py process --account work --uid 12345 --force-reprocess

# Process with email limit
python main.py process --account work --max-emails 10

# Debug prompt generation
python main.py process --account work --uid 12345 --debug-prompt
```

**Behavior:**
- Uses `MasterOrchestrator` for multi-account processing
- Processes accounts in sequence with state isolation
- Shows safety interlock cost estimation before processing
- Logs account-specific processing information
- Requires account specification (no default single-account mode)

**Examples:**
```bash
# Process all unprocessed emails
python main.py process

# Process specific email by UID
python main.py process --uid 12345

# Force reprocess an email
python main.py process --uid 12345 --force-reprocess

# Preview what would happen (dry run)
python main.py process --dry-run

# Process only 5 emails
python main.py process --max-emails 5

# Debug prompt construction
python main.py process --uid 400 --debug-prompt
```

**Note:** The V4 CLI requires account specification. All processing uses V4 components (MasterOrchestrator, ConfigLoader) exclusively.

### Show-Config Command (V4)

The `show-config` command displays the merged configuration for a specific account.

**Command:**
```bash
python main.py show-config --account <name> [OPTIONS]
```

**Options:**
- `--account <name>`: Required. Account name to show configuration for
- `--format yaml|json`: Output format (default: yaml)
- `--with-sources`: Show configuration sources (global vs. account override)
- `--no-highlight`: Disable syntax highlighting

**Examples:**
```bash
# Show merged configuration for 'work' account
python main.py show-config --account work

# Show configuration in JSON format
python main.py show-config --account work --format json

# Show configuration with sources
python main.py show-config --account work --with-sources
```

**Output:**
- Shows merged configuration (global + account overrides)
- Highlights overridden values (if highlighting enabled)
- Validates configuration on load (errors shown if invalid)

### Cleanup-Flags Command

The `cleanup-flags` command removes application-specific IMAP flags from emails.

**Command:**
```bash
python main.py cleanup-flags [--dry-run]
```

**Options:**
- `--dry-run`: Preview which flags would be removed without actually removing them

**Examples:**
```bash
# Preview what would be removed (dry-run)
python main.py cleanup-flags --dry-run

# Actually remove flags (requires confirmation)
python main.py cleanup-flags
# Will prompt: "Type 'yes' to confirm and proceed, or anything else to cancel: "
```

**Features:**
- **Mandatory confirmation prompt** (security requirement)
- Removes only application-specific flags (as configured in `imap.application_flags`)
- Includes safety warnings before execution
- Comprehensive scanning and logging

**See Also:** [V3 Cleanup Flags Documentation](v3-cleanup-flags.md) for complete details.

### Backfill Command

The `backfill` command processes historical emails with date range filtering.

**Command:**
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

---

## Command Options and Flags

### Global Options

These options apply to all commands:

- `--help`: Show help message for command
- `--version`: Show version information (if available)

### Process Command Options

**Required Options (choose one):**
- `--account <name>`: Process specific account (mutually exclusive with --all)
- `--all`: Process all accounts (mutually exclusive with --account)

**Additional Options:**
- `--dry-run`: Preview mode (no side effects)
- `--uid <ID>`: Process specific email by UID (requires --account, cannot be used with --all)
- `--force-reprocess`: Ignore processed tags and reprocess emails
- `--max-emails <N>`: Limit number of emails to process
- `--debug-prompt`: Write classification prompt to debug file

### Show-Config Command Options

- `--account <name>`: Required. Account name
- `--format yaml|json`: Output format
- `--with-sources`: Show configuration sources
- `--no-highlight`: Disable syntax highlighting

### Cleanup-Flags Command Options

- `--account <name>`: Required. Account name for cleanup operation
- `--dry-run`: Preview mode (shows what would be removed without actually removing)

### Backfill Command Options

- `--start-date <YYYY-MM-DD>`: Start date
- `--end-date <YYYY-MM-DD>`: End date
- `--folder <FOLDER>`: IMAP folder
- `--force-reprocess`: Reprocess emails
- `--dry-run`: Preview mode
- `--max-emails <N>`: Limit number of emails
- `--calls-per-minute <N>`: API throttling

---

## Common Workflows

### Processing Single Account

**Workflow:**
1. Verify account configuration exists
2. Test with dry-run
3. Process account

**Example:**
```bash
# Step 1: Verify account config
python main.py show-config --account work

# Step 2: Test with dry-run
python main.py process --account work --dry-run

# Step 3: Process account
python main.py process --account work
```

### Processing All Accounts

**Workflow:**
1. Verify all account configurations
2. Test with dry-run
3. Process all accounts

**Example:**
```bash
# Step 1: List available accounts (check config/accounts/)
ls config/accounts/

# Step 2: Test with dry-run
python main.py process --all --dry-run

# Step 3: Process all accounts
python main.py process --all
```

### Dry-Run Mode

**Purpose:** Preview processing without side effects

**Use Cases:**
- Testing configuration changes
- Validating rule changes
- Previewing processing behavior
- Debugging issues

**Example:**
```bash
# Preview single account
python main.py process --account work --dry-run

# Preview all accounts
python main.py process --all --dry-run

# Preview cleanup
python main.py cleanup-flags --dry-run
```

**What Dry-Run Shows:**
- Configuration loading
- Email fetching
- Rule evaluation
- Processing decisions
- Cost estimates
- **No file writes**
- **No IMAP flag changes**

### Configuration Validation

**Workflow:**
1. Check global configuration
2. Check account configurations
3. Validate merged configurations

**Example:**
```bash
# Check account config exists
ls config/accounts/work.yaml

# Show merged config (validates on load)
python main.py show-config --account work

# Test processing (validates config during load)
python main.py process --account work --dry-run
```

---

## Exit Codes

V4 CLI uses standard exit codes:

| Exit Code | Meaning | Description |
|-----------|---------|-------------|
| `0` | Success | Command completed successfully |
| `1` | General Error | Command failed with error |
| `2` | Usage Error | Invalid command or options |

**Examples:**
```bash
# Success
python main.py process --account work
echo $?  # Output: 0

# Error
python main.py process --account nonexistent
echo $?  # Output: 1

# Usage error
python main.py process --account work --all
echo $?  # Output: 2 (mutually exclusive options)
```

---

## Error Handling

### Common Errors

**Account Not Found:**
```
Error: Account 'work' not found
```

**Solution:**
- Check account config exists: `ls config/accounts/work.yaml`
- Verify account name matches filename (without .yaml extension)

**Configuration Error:**
```
ValidationError: Field required: imap.server
```

**Solution:**
- Check configuration file syntax
- Verify required fields are present
- See [V4 Configuration Reference](v4-configuration-reference.md)

**Environment Variable Not Set:**
```
KeyError: 'IMAP_PASSWORD'
```

**Solution:**
- Set environment variables: `export IMAP_PASSWORD='password'`
- Or create `.env` file with required variables

**Mutually Exclusive Options:**
```
Error: --account and --all are mutually exclusive
```

**Solution:**
- Use either `--account <name>` OR `--all`, not both

### Error Messages

Error messages include:
- Error type and description
- Affected configuration/account
- Suggested solutions
- Reference to relevant documentation

---

## CLI Examples

### Basic Examples

**Process single account:**
```bash
python main.py process --account work
```

**Process all accounts:**
```bash
python main.py process --all
```

**Preview processing:**
```bash
python main.py process --account work --dry-run
```

**Show configuration:**
```bash
python main.py show-config --account work
```

### Advanced Examples

**Process with debugging:**
```bash
# Debug prompt (requires account)
python main.py process --account work --uid 400 --debug-prompt

# Check logs
tail -f logs/agent.log
```

**Process with limits:**
```bash
# Limit emails (requires account)
python main.py process --account work --max-emails 5

# Process all accounts with limit
python main.py process --all --max-emails 10
```

**Configuration management:**
```bash
# Show config in JSON
python main.py show-config --account work --format json

# Show config with sources
python main.py show-config --account work --with-sources
```

### Workflow Examples

**Daily Processing:**
```bash
# Process all accounts daily
python main.py process --all
```

**Testing Configuration:**
```bash
# Test new account config
python main.py show-config --account new-account
python main.py process --account new-account --dry-run
python main.py process --account new-account
```

**Maintenance:**
```bash
# Cleanup flags (with confirmation)
python main.py cleanup-flags

# Backfill historical emails
python main.py backfill --start-date 2024-01-01 --max-emails 50
```

---

## CLI Troubleshooting

### Command Not Found

**Error:**
```
command not found: python main.py
```

**Solution:**
- Ensure you're in the project directory
- Use `python3` instead of `python` if needed
- Check Python is installed: `python --version`

### Invalid Arguments

**Error:**
```
Error: Invalid value for '--account': Account name required
```

**Solution:**
- Provide account name: `--account work`
- Check account config exists: `ls config/accounts/work.yaml`

### Configuration Errors

**Error:**
```
ValidationError: Invalid configuration
```

**Solution:**
- Validate configuration: `python main.py show-config --account work`
- Check [V4 Configuration Reference](v4-configuration-reference.md)
- Review configuration file syntax

### Processing Errors

**Error:**
```
ConnectionError: Failed to connect to IMAP server
```

**Solution:**
- Check IMAP server and port settings
- Verify network connectivity
- Check firewall settings
- Test IMAP connection manually

### Performance Issues

**Symptoms:**
- Slow processing
- High memory usage

**Solution:**
- Use `--max-emails` to limit batch size
- Check processing thresholds
- Review rule complexity
- Monitor logs for bottlenecks

For more troubleshooting, see [V4 Troubleshooting Guide](v4-troubleshooting.md).

---

## Related Documentation

- [V3 CLI](v3-cli.md) - V3 CLI reference (for comparison)
- [V4 Configuration Reference](v4-configuration-reference.md) - Configuration context
- [V4 Troubleshooting](v4-troubleshooting.md) - Common issues
