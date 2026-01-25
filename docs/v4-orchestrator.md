# V4 Master Orchestrator Module

**Task:** 10  
**Status:** ✅ Complete  
**PDD Reference:** Section 2.1, 4.2.1

## Overview

The MasterOrchestrator class provides multi-account email processing coordination for the V4 orchestrator. It manages multiple AccountProcessor instances, handles CLI argument parsing for account selection, and ensures complete state isolation between accounts.

## Purpose

The MasterOrchestrator provides:
- **Multi-Account Management:** Coordinates processing across multiple email accounts
- **CLI Integration:** Handles account selection via command-line arguments
- **Account Discovery:** Automatically discovers available accounts from configuration
- **Error Isolation:** Failures in one account don't affect others
- **State Isolation:** Each account is processed with complete isolation

## Module Location

- **File:** `src/orchestrator.py` (MasterOrchestrator class)
- **Test File:** `tests/test_master_orchestrator.py` (to be created)
- **Dependencies:**
  - `src/account_processor.py` (AccountProcessor)
  - `src/config_loader.py` (ConfigLoader)
  - `src/llm_client.py` (LLMClient)
  - `src/note_generator.py` (NoteGenerator)
  - `src/decision_logic.py` (DecisionLogic)
  - `src/rules.py` (blacklist/whitelist)
  - `src/content_parser.py` (HTML to Markdown)

## Architecture

### Core Components

1. **MasterOrchestrator:** Main class that orchestrates multi-account processing
2. **OrchestrationResult:** Result dataclass with processing summary
3. **Account Discovery:** Automatic discovery of accounts from `config/accounts/`
4. **CLI Argument Parsing:** Command-line interface for account selection

### Processing Flow

The MasterOrchestrator executes the following flow:

```
1. Parse CLI Arguments → Account selection, config paths, options
2. Discover Accounts → Scan config/accounts/ for available accounts
3. Select Accounts → Filter based on CLI arguments
4. For Each Account:
   a. Create AccountProcessor → Isolated instance with account-specific config
   b. Setup → IMAP connection, rule loading
   c. Run → Execute complete processing pipeline
   d. Teardown → Cleanup, close connections
5. Aggregate Results → Collect success/failure statistics
6. Return Summary → OrchestrationResult with processing summary
```

## State Isolation

The MasterOrchestrator ensures complete state isolation through:

- **Separate AccountProcessor Instances:** Each account gets its own processor
- **Separate IMAP Connections:** Each account has its own connection
- **Account-Specific Configuration:** Configuration loaded per account
- **Error Isolation:** Failures in one account don't stop others
- **Shared Services:** Stateless services (LLMClient, NoteGenerator) are safely shared

## Usage

### Basic Usage

```python
from src.orchestrator import MasterOrchestrator
import logging

# Create orchestrator
orchestrator = MasterOrchestrator(
    config_base_dir='config',
    logger=logging.getLogger(__name__)
)

# Run with CLI arguments
result = orchestrator.run(['--account', 'work'])

# Check results
print(f"Processed {result.successful_accounts}/{result.total_accounts} accounts")
print(f"Failed: {result.failed_accounts}")
for account_id, (success, error) in result.account_results.items():
    if not success:
        print(f"  - {account_id}: {error}")
```

### CLI Usage

```bash
# Process single account
python -m src.orchestrator --account work

# Process multiple accounts
python -m src.orchestrator --accounts work,personal

# Process all accounts
python -m src.orchestrator --all-accounts

# Dry-run mode
python -m src.orchestrator --account work --dry-run

# Custom config directory
python -m src.orchestrator --account work --config-dir /path/to/config

# Debug logging
python -m src.orchestrator --account work --log-level DEBUG
```

### CLI Arguments

- `--account <id>`: Process a specific account (can be repeated)
- `--accounts <id1,id2,...>`: Process multiple accounts (comma-separated)
- `--all-accounts`: Process all available accounts
- `--config-dir <path>`: Override config directory (default: 'config')
- `--dry-run`: Run in preview mode (no side effects)
- `--log-level <level>`: Set logging level (DEBUG, INFO, WARNING, ERROR)

## Account Discovery

The orchestrator automatically discovers accounts by scanning the `config/accounts/` directory for YAML files:

```
config/
├── config.yaml              # Global configuration
└── accounts/
    ├── work.yaml            # Account: 'work'
    ├── personal.yaml        # Account: 'personal'
    └── example-account.yaml # Ignored (starts with 'example')
```

Account identifiers are derived from filenames (without `.yaml` extension). Files starting with `example` are ignored.

## Error Handling

The orchestrator implements robust error handling:

1. **Account-Level Isolation:** Failures in one account don't stop processing of others
2. **Error Aggregation:** All errors are collected and reported in the result
3. **Cleanup Guarantees:** Teardown is always called, even on failure
4. **Detailed Logging:** Full stack traces for debugging

### Error Types

- **AccountProcessorSetupError:** IMAP connection or setup failures
- **AccountProcessorRunError:** Processing pipeline failures
- **AccountProcessorError:** General AccountProcessor errors
- **ConfigurationError:** Configuration loading or validation failures
- **ValueError:** Invalid account selection

## API Reference

### MasterOrchestrator

#### `__init__(config_base_dir: Path | str = "config", logger: Optional[logging.Logger] = None)`

Initialize MasterOrchestrator with configuration directory and logger.

**Parameters:**
- `config_base_dir`: Base directory containing configuration files (default: 'config')
- `logger`: Optional logger instance (creates one if not provided)

#### `parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace`

Parse CLI arguments for account selection and processing options.

**Parameters:**
- `argv`: Optional list of command-line arguments (default: sys.argv[1:])

**Returns:**
- `argparse.Namespace` with parsed arguments

#### `select_accounts(args: argparse.Namespace) -> List[str]`

Select accounts to process based on parsed CLI arguments.

**Parameters:**
- `args`: Parsed CLI arguments from `parse_args()`

**Returns:**
- List of account identifiers to process

**Raises:**
- `ValueError`: If an unknown account is requested
- `ConfigurationError`: If account discovery fails

#### `create_account_processor(account_id: str) -> AccountProcessor`

Create an isolated AccountProcessor instance for a specific account.

**Parameters:**
- `account_id`: Account identifier (e.g., 'work', 'personal')

**Returns:**
- `AccountProcessor` instance (not yet set up or run)

**Raises:**
- `ConfigurationError`: If account configuration cannot be loaded
- `AccountProcessorSetupError`: If AccountProcessor creation fails

#### `run(argv: Optional[List[str]] = None) -> OrchestrationResult`

Main entry point: parse CLI args, select accounts, and orchestrate processing.

**Parameters:**
- `argv`: Optional list of command-line arguments (default: sys.argv[1:])

**Returns:**
- `OrchestrationResult` with processing summary

**Raises:**
- `SystemExit`: If argument parsing fails
- `ValueError`: If account selection is invalid
- `ConfigurationError`: If configuration loading fails

### OrchestrationResult

Result dataclass with processing summary.

**Attributes:**
- `total_accounts`: Total number of accounts processed
- `successful_accounts`: Number of accounts processed successfully
- `failed_accounts`: Number of accounts that failed
- `account_results`: Dictionary mapping account_id to (success: bool, error: Optional[str])
- `total_time`: Total orchestration time (seconds)

## Integration with AccountProcessor

The MasterOrchestrator creates and manages AccountProcessor instances:

```python
# For each account:
processor = orchestrator.create_account_processor(account_id)
processor.setup()      # IMAP connection, rule loading
processor.run()        # Execute processing pipeline
processor.teardown()   # Cleanup, close connections
```

Each AccountProcessor instance is completely isolated:
- Separate IMAP connection
- Separate configuration (merged per account)
- Separate processing context
- Separate logger (with account identifier)

## Shared Services

Some services are safely shared across accounts because they are stateless or thread-safe:

- **LLMClient:** Stateless API client
- **NoteGenerator:** Stateless template renderer
- **DecisionLogic:** Stateless classification logic

These services are initialized once and reused to reduce overhead.

## Testing

### Unit Tests

Test the orchestrator with mocked dependencies:

```python
from unittest.mock import Mock, patch
from src.orchestrator import MasterOrchestrator

@patch('src.orchestrator.ConfigLoader')
@patch('src.orchestrator.AccountProcessor')
def test_orchestrator_single_account(mock_processor, mock_loader):
    # Setup mocks
    # ...
    
    # Create orchestrator
    orchestrator = MasterOrchestrator()
    
    # Run
    result = orchestrator.run(['--account', 'work'])
    
    # Assert
    assert result.successful_accounts == 1
    assert result.failed_accounts == 0
```

### Integration Tests

Test with real configuration and AccountProcessor:

```python
def test_orchestrator_integration(tmp_path):
    # Create test config structure
    # ...
    
    # Create orchestrator
    orchestrator = MasterOrchestrator(config_base_dir=tmp_path)
    
    # Run
    result = orchestrator.run(['--all-accounts'])
    
    # Assert
    assert result.total_accounts > 0
```

## PDD Alignment

This implementation aligns with PDD V4 Section 2.1 and 4.2.1:

- ✅ Handles CLI arguments for account selection
- ✅ Iterates through selected accounts
- ✅ Creates isolated AccountProcessor instances
- ✅ Manages overall processing flow
- ✅ Ensures proper error handling (one account failure doesn't stop others)
- ✅ Complete state isolation between accounts

## See Also

- [V4 Account Processor](v4-account-processor.md) - AccountProcessor documentation
- [V4 Configuration System](v4-configuration.md) - Configuration loading and merging
- [PDD V4](pdd_V4.md) - Product Design Document
- [V3 Orchestrator](v3-orchestrator.md) - V3 Pipeline class (single-account)
