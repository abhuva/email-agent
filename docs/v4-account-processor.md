# V4 Account Processor Module

**Task:** 8, 9  
**Status:** ✅ Complete  
**PDD Reference:** Section 2.1, 4.2.1

## Overview

The AccountProcessor class provides isolated per-account email processing for the V4 multi-tenant orchestrator. It ensures complete state isolation between accounts, with each instance maintaining its own IMAP connection, configuration, and processing context.

## Purpose

The AccountProcessor provides:
- **State Isolation:** Complete separation of data and configuration between accounts
- **Pipeline Orchestration:** Coordinates the complete email processing pipeline
- **Resource Management:** Handles IMAP connection lifecycle and cleanup
- **Error Isolation:** Failures in one account don't affect others
- **Safety Interlock:** Cost estimation and user confirmation before high-cost operations (Task 9)

## Module Location

- **File:** `src/account_processor.py`
- **Test File:** `tests/test_account_processor.py`
- **Dependencies:**
  - `src/imap_client.py` (via ConfigurableImapClient)
  - `src/rules.py` (blacklist/whitelist)
  - `src/content_parser.py` (HTML to Markdown)
  - `src/llm_client.py` (email classification)
  - `src/decision_logic.py` (score processing)
  - `src/note_generator.py` (note generation)
  - `src/models.py` (EmailContext)

## Architecture

### Core Components

1. **AccountProcessor:** Main class that orchestrates the processing pipeline
2. **ConfigurableImapClient:** IMAP client that accepts account-specific config
3. **create_imap_client_from_config:** Factory function for creating IMAP clients

### Processing Pipeline

The AccountProcessor executes the following pipeline:

**Pre-Processing (Safety Interlock):**
```
0. Email Counting → IMAP.search to count emails before fetching
1. Cost Estimation → Calculate estimated cost based on email count and model pricing
2. User Confirmation → Prompt user for explicit approval (if cost exceeds threshold)
```

**Processing Pipeline (per email):**
```
3. Blacklist Check → DROP, RECORD, or PASS
4. Content Parsing → HTML to Markdown (with fallback)
5. LLM Classification → Spam and importance scores
6. Decision Logic → Classification result
7. Whitelist Rules → Score boost and tags
8. Note Generation → Obsidian note creation
9. IMAP Flag Setting → Mark as processed
```

## State Isolation

The AccountProcessor ensures complete state isolation through:

- **Per-Instance State:** All state stored on `self` (no class variables)
- **Separate IMAP Connections:** Each account has its own connection
- **Account-Specific Config:** Configuration passed at construction (immutable)
- **Isolated Processing Context:** Per-run state stored separately
- **Account-Specific Logging:** Logger includes account identifier

## Usage

### Basic Usage

```python
from src.account_processor import AccountProcessor, create_imap_client_from_config
from src.config_loader import ConfigLoader
from src.llm_client import LLMClient
from src.note_generator import NoteGenerator
from src.decision_logic import DecisionLogic
from src.rules import load_blacklist_rules, load_whitelist_rules
from src.content_parser import parse_html_content

# Load account configuration
loader = ConfigLoader('config')
account_config = loader.load_merged_config('work')

# Create dependencies
llm_client = LLMClient()
note_generator = NoteGenerator()
decision_logic = DecisionLogic()

# Create processor
processor = AccountProcessor(
    account_id='work',
    account_config=account_config,
    imap_client_factory=create_imap_client_from_config,
    llm_client=llm_client,
    blacklist_service=load_blacklist_rules,
    whitelist_service=load_whitelist_rules,
    note_generator=note_generator,
    parser=parse_html_content,
    decision_logic=decision_logic
)

# Execute processing
processor.setup()
processor.run()
processor.teardown()
```

### Context Manager Usage

The AccountProcessor can be used as a context manager (future enhancement):

```python
with AccountProcessor(...) as processor:
    processor.run()
# Automatic teardown on exit
```

## Configuration

The AccountProcessor requires a merged configuration dictionary with the following structure:

```yaml
imap:
  server: 'imap.example.com'
  port: 993
  username: 'user@example.com'
  password: 'password'  # or password_env: 'IMAP_PASSWORD'
  query: 'ALL'
  processed_tag: 'AIProcessed'

processing:
  max_emails_per_run: 10

safety_interlock:
  enabled: true
  cost_threshold: 0.10
  skip_confirmation_below_threshold: false
  average_tokens_per_email: 2000
  currency: '$'

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  cost_per_1k_tokens: 0.0001  # Required for cost estimation
  # OR use direct pricing:
  # cost_per_email: 0.001
```

## API Reference

### AccountProcessor

#### `__init__(account_id, account_config, imap_client_factory, llm_client, blacklist_service, whitelist_service, note_generator, parser, decision_logic=None, logger=None)`

Initialize AccountProcessor with account-specific configuration and dependencies.

**Parameters:**
- `account_id` (str): Unique identifier for this account
- `account_config` (dict): Merged configuration dictionary
- `imap_client_factory` (callable): Factory function to create IMAP clients
- `llm_client` (LLMClient): LLM client instance
- `blacklist_service` (callable): Function to load blacklist rules
- `whitelist_service` (callable): Function to load whitelist rules
- `note_generator` (NoteGenerator): Note generator instance
- `parser` (callable): Content parser function
- `decision_logic` (DecisionLogic, optional): Decision logic instance
- `logger` (Logger, optional): Logger instance

#### `setup() -> None`

Set up resources required for processing this account.

- Establishes IMAP connection
- Loads account-specific rules
- Initializes processing context

**Raises:**
- `AccountProcessorSetupError`: If setup fails

#### `run(force_reprocess: bool = False) -> None`

Execute the processing pipeline for this account.

**Safety Interlock Flow:**
1. Counts emails using `IMAP.search` (no fetching yet)
2. Estimates cost based on email count and model pricing
3. Prompts user for confirmation if cost exceeds threshold (or if forced)
4. Only proceeds with fetching if confirmed

**Processing Flow:**
- Fetches emails from IMAP (using pre-counted UIDs)
- Processes each email through the pipeline
- Generates notes and sets IMAP flags

**Parameters:**
- `force_reprocess` (bool): If True, include processed emails in search

**Raises:**
- `AccountProcessorRunError`: If run fails critically

#### `teardown() -> None`

Clean up resources allocated during setup() and run().

- Closes IMAP connection
- Clears processing context
- Resets per-run state

### ConfigurableImapClient

Extends `ImapClient` to support account-specific configurations.

#### `__init__(config: Dict[str, Any])`

Initialize with account-specific config dictionary.

#### `connect() -> None`

Connect using credentials from config (not settings facade).

### Factory Functions

#### `create_imap_client_from_config(config: Dict[str, Any]) -> ImapClient`

Create a ConfigurableImapClient from configuration dictionary.

**Parameters:**
- `config`: Configuration dictionary with IMAP settings

**Returns:**
- `ConfigurableImapClient` instance (not connected)

**Raises:**
- `AccountProcessorSetupError`: If required config fields are missing

## Error Handling

The AccountProcessor handles errors gracefully:

- **Setup Errors:** Raised as `AccountProcessorSetupError`
- **Run Errors:** Individual email failures are logged but don't stop processing
- **Teardown Errors:** Logged but not raised (ensures cleanup completes)

## Testing

Comprehensive test suite in `tests/test_account_processor.py` covers:

- State isolation between instances
- Setup/run/teardown lifecycle
- Pipeline execution (all stages)
- Error handling and resource cleanup
- ConfigurableImapClient functionality

Run tests with:
```bash
pytest tests/test_account_processor.py -v
```

## Integration with V4 Orchestrator

The AccountProcessor is designed to be used by a MasterOrchestrator (future task) that:

1. Loads account configurations
2. Creates AccountProcessor instances for each account
3. Executes setup/run/teardown for each account
4. Handles errors and aggregates results

## Limitations and Future Enhancements

### Current Limitations

1. **Note Writing:** Note generation creates content but doesn't write to filesystem yet
2. **Context Manager:** Not yet implemented (can be added if needed)
3. **Concurrent Processing:** Currently sequential (can be parallelized later)

### Future Enhancements

1. **File Writing:** Integrate with file writing module
2. **Progress Reporting:** Add progress callbacks for long-running operations
3. **Retry Logic:** Add retry logic for transient failures
4. **Metrics:** Add processing metrics and statistics

## Related Documentation

- [V4 Configuration](v4-configuration.md) - Configuration system
- [V4 Rules Engine](v4-rules-engine.md) - Blacklist/whitelist rules
- [V3 IMAP Client](v3-imap-client.md) - IMAP client (base class)
- [V3 LLM Client](v3-llm-client.md) - LLM classification
- [V3 Note Generator](v3-note-generator.md) - Note generation

## PDD Alignment

This module implements:
- **Section 2.1:** Account Processor architecture
- **Section 4.2.1:** Account Processor lifecycle (setup/run/teardown)
- **Section 5.1:** EmailContext data model usage
- **State Isolation:** Complete separation between accounts
- **Task 9:** Safety interlock with cost estimation and user confirmation
