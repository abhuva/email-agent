# V4 Main Entry Point Integration Design

**Task:** 18.1 - Analyze new architecture integration points for main.py  
**Status:** Design Document  
**Date:** 2026-01-05

## Overview

This document analyzes how `main.py` should integrate with the new V4 architecture components (MasterOrchestrator, new CLI, multi-account configuration) based on the PDD and existing codebase.

## Current State (V3)

### Current main.py
```python
#!/usr/bin/env python3
from src.cli_v3 import cli

if __name__ == "__main__":
    cli()
```

**Current Flow:**
1. `main.py` → `cli_v3.py` (Click-based CLI)
2. CLI commands initialize `settings` facade (singleton)
3. Commands call `Pipeline.process_emails()` from `orchestrator.py`
4. Single-account processing with global configuration

## Target State (V4)

### Required Components

#### 1. MasterOrchestrator (Task 10 - Pending)
**Expected Location:** `src/orchestrator.py` (refactored) or `src/master_orchestrator.py`

**Expected API:**
```python
class MasterOrchestrator:
    def __init__(self, config_base_dir: Path, accounts_dir: Path):
        """Initialize with configuration paths"""
        pass
    
    def process_account(self, account_name: str, options: ProcessOptions) -> ProcessingResult:
        """Process a single account"""
        pass
    
    def process_all_accounts(self, options: ProcessOptions) -> List[ProcessingResult]:
        """Process all configured accounts"""
        pass
    
    def discover_accounts(self) -> List[str]:
        """Discover available accounts from config/accounts/ directory"""
        pass
    
    def shutdown(self) -> None:
        """Clean up resources"""
        pass
```

**Lifecycle Methods:**
- `__init__()`: Initialize with config paths, set up logging
- `process_account()`: Process single account (creates isolated AccountProcessor)
- `process_all_accounts()`: Loop through all accounts
- `discover_accounts()`: Scan config/accounts/ for available accounts
- `shutdown()`: Clean up connections, close resources

**Dependencies:**
- `ConfigLoader` (from `src/config_loader.py` - ✅ Done)
- `AccountProcessor` (to be created in future task)
- Logging system (Task 12 - Pending)

#### 2. New CLI (Task 11 - Pending)
**Expected Location:** `src/cli_v4.py` or updated `src/cli_v3.py`

**Expected Commands:**
```python
@click.group()
def cli():
    """V4 Multi-account CLI"""
    pass

@cli.command()
@click.option('--account', type=str, help='Process specific account')
@click.option('--all', 'all_accounts', is_flag=True, help='Process all accounts')
@click.option('--dry-run', is_flag=True, help='Preview mode')
def process(account: Optional[str], all_accounts: bool, dry_run: bool):
    """Process emails for account(s)"""
    pass

@cli.command()
@click.option('--account', type=str, required=True, help='Show config for account')
def show_config(account: str):
    """Show merged configuration for an account"""
    pass
```

**Argument Structure:**
- `--account <name>`: Single account processing
- `--all`: Process all accounts
- `--dry-run`: Preview mode (no side effects)
- Mutually exclusive: `--account` and `--all` cannot both be specified

**Integration Points:**
- CLI parses arguments and validates
- CLI calls `MasterOrchestrator` methods based on arguments
- CLI handles error display and exit codes

#### 3. Configuration System

**Configuration Sources (Priority Order):**
1. **CLI Arguments** (highest priority)
   - `--account`, `--all`, `--dry-run`
   - `--config` (optional, override default config path)
   - `--env` (optional, override default .env path)

2. **Environment Variables**
   - `ACCOUNT_IDS`: Comma-separated list of account IDs (if not using CLI)
   - `DEFAULT_ACCOUNT`: Default account name
   - `CONFIG_DIR`: Override config directory (default: `config`)
   - `DRY_RUN`: Global dry-run flag (default: `false`)

3. **Configuration Files**
   - `config/config.yaml`: Global/base configuration
   - `config/accounts/{account_name}.yaml`: Account-specific overrides
   - `.env`: Secrets (API keys, passwords)

4. **Defaults**
   - Config directory: `config/`
   - Accounts directory: `config/accounts/`
   - If no account specified: process all accounts

**Configuration Model:**
```python
@dataclass
class RuntimeConfig:
    """Multi-account runtime configuration"""
    # Account selection
    account_names: List[str]  # Empty = all accounts
    process_all: bool
    
    # Paths
    config_base_dir: Path
    accounts_dir: Path
    env_file: Path
    
    # Options
    dry_run: bool
    log_level: str
    
    # Per-account configs (loaded on demand)
    account_configs: Dict[str, dict] = field(default_factory=dict)
```

## Integration Flow Design

### High-Level Flow

```
main.py
  ↓
1. Parse CLI arguments (new CLI module)
  ↓
2. Build RuntimeConfig (merge CLI + env + defaults)
  ↓
3. Initialize logging (Task 12 - centralized logging)
  ↓
4. Construct MasterOrchestrator (with config paths)
  ↓
5. Dispatch command:
   - process --account <name> → orchestrator.process_account()
   - process --all → orchestrator.process_all_accounts()
   - show-config --account <name> → orchestrator.show_config()
  ↓
6. Handle shutdown (cleanup, exit codes)
```

### Detailed Flow

#### Step 1: CLI Parsing
```python
# In main.py or cli_v4.py
parsed_args = parse_cli_arguments(sys.argv[1:])
# Returns: Namespace with account, all_accounts, dry_run, config_path, etc.
```

#### Step 2: Configuration Building
```python
# In main.py
def build_runtime_config(parsed_args) -> RuntimeConfig:
    # 1. Read environment variables
    env_accounts = os.getenv('ACCOUNT_IDS', '').split(',') if os.getenv('ACCOUNT_IDS') else []
    env_dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    # 2. Merge with CLI args (CLI takes precedence)
    account_names = parsed_args.account if parsed_args.account else []
    if parsed_args.all_accounts:
        account_names = []  # Empty = all accounts
    dry_run = parsed_args.dry_run or env_dry_run
    
    # 3. Resolve paths
    config_base_dir = Path(parsed_args.config_dir or 'config')
    accounts_dir = config_base_dir / 'accounts'
    env_file = Path(parsed_args.env_file or '.env')
    
    # 4. Build config object
    return RuntimeConfig(
        account_names=account_names,
        process_all=parsed_args.all_accounts,
        config_base_dir=config_base_dir,
        accounts_dir=accounts_dir,
        env_file=env_file,
        dry_run=dry_run,
        log_level=parsed_args.log_level or 'INFO'
    )
```

#### Step 3: MasterOrchestrator Construction
```python
# In main.py
def main():
    parsed_args = parse_cli_arguments()
    config = build_runtime_config(parsed_args)
    
    # Initialize logging (Task 12)
    init_logging(config.log_level)
    
    # Construct orchestrator
    orchestrator = MasterOrchestrator(
        config_base_dir=config.config_base_dir,
        accounts_dir=config.accounts_dir
    )
    
    try:
        # Dispatch command
        if parsed_args.command == 'process':
            if config.process_all:
                results = orchestrator.process_all_accounts(config)
            else:
                results = orchestrator.process_account(config.account_names[0], config)
        elif parsed_args.command == 'show-config':
            config_dict = orchestrator.get_account_config(config.account_names[0])
            print(yaml.dump(config_dict))
    finally:
        orchestrator.shutdown()
```

## Configuration Sources Summary

| Source | Key Names | Expected Types | Consumed By |
|--------|-----------|----------------|-------------|
| CLI `--account` | `account` | `str` | MasterOrchestrator |
| CLI `--all` | `all_accounts` | `bool` | MasterOrchestrator |
| CLI `--dry-run` | `dry_run` | `bool` | MasterOrchestrator, AccountProcessor |
| CLI `--config` | `config_dir` | `Path` | ConfigLoader |
| CLI `--env` | `env_file` | `Path` | ConfigLoader |
| Env `ACCOUNT_IDS` | `ACCOUNT_IDS` | `str` (comma-separated) | RuntimeConfig builder |
| Env `DRY_RUN` | `DRY_RUN` | `str` ('true'/'false') | RuntimeConfig builder |
| Env `CONFIG_DIR` | `CONFIG_DIR` | `str` | RuntimeConfig builder |
| File `config/config.yaml` | N/A | `dict` | ConfigLoader |
| File `config/accounts/*.yaml` | N/A | `dict` | ConfigLoader |
| File `.env` | Various | `str` | ConfigLoader (secrets) |

## Responsibility Mapping

### Old Responsibilities (V3) → New Equivalents (V4)

| V3 Responsibility | V4 Equivalent | Delegated To |
|-------------------|---------------|--------------|
| Argument parsing | Argument parsing | New CLI module (`cli_v4.py`) |
| Single-account setup | Multi-account setup | MasterOrchestrator |
| Settings initialization | Config loading | ConfigLoader (per account) |
| Logging setup | Logging setup | Centralized logging (Task 12) |
| Pipeline execution | Account processing | AccountProcessor (per account) |
| Error handling | Error handling | MasterOrchestrator (aggregates) |

### What main.py Should Do

1. **Parse CLI** → Delegate to new CLI module
2. **Build RuntimeConfig** → Merge CLI + env + defaults
3. **Initialize Logging** → Call centralized logging init
4. **Construct MasterOrchestrator** → Pass config paths
5. **Dispatch Commands** → Call orchestrator methods
6. **Handle Shutdown** → Call orchestrator.shutdown(), set exit codes

### What main.py Should NOT Do

- ❌ Direct configuration loading (delegate to ConfigLoader)
- ❌ Account discovery (delegate to MasterOrchestrator)
- ❌ Per-account processing logic (delegate to AccountProcessor)
- ❌ Complex error recovery (delegate to MasterOrchestrator)
- ❌ Logging configuration details (delegate to centralized logging)

## Design Notes

### main() Function Flow

```python
def main() -> int:
    """
    Main entry point for V4 email agent.
    
    Flow:
    1. Parse CLI arguments
    2. Build runtime configuration
    3. Initialize logging
    4. Construct MasterOrchestrator
    5. Dispatch command
    6. Handle shutdown
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        # Step 1: Parse CLI
        parsed_args = parse_cli_arguments()
        
        # Step 2: Build config
        config = build_runtime_config(parsed_args)
        
        # Step 3: Initialize logging
        init_logging(config.log_level)
        logger.info("Starting email agent V4")
        
        # Step 4: Construct orchestrator
        orchestrator = MasterOrchestrator(
            config_base_dir=config.config_base_dir,
            accounts_dir=config.accounts_dir
        )
        
        # Step 5: Dispatch command
        exit_code = dispatch_command(orchestrator, parsed_args, config)
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130  # SIGINT exit code
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        # Step 6: Shutdown
        if 'orchestrator' in locals():
            orchestrator.shutdown()
        logger.info("Shutting down email agent V4")
```

## Dependencies Status

- ✅ **ConfigLoader** (Task 2): Complete - `src/config_loader.py` exists
- ✅ **EmailContext** (Task 4): Complete - `src/models.py` exists
- ⏳ **MasterOrchestrator** (Task 10): Pending
- ⏳ **New CLI** (Task 11): Pending
- ⏳ **Enhanced Logging** (Task 12): Pending

## Next Steps

1. **Subtask 18.2**: Implement `build_runtime_config()` function
2. **Subtask 18.3**: Refactor `main.py` to use MasterOrchestrator (when Task 10 is complete)
3. **Subtask 18.4**: Integrate new CLI (when Task 11 is complete)
4. **Subtask 18.5**: Add shutdown and lifecycle management

## Notes

- This design assumes Tasks 10, 11, and 12 will be completed before Task 18.3-18.4
- The design is flexible enough to work with partial implementations
- Configuration precedence: CLI > Env > Defaults
- All account processing must be isolated (no state bleeding)
