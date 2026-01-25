# Email Agent - AI Agent Entry Point

> **Purpose:** This document is optimized for AI agents (like Cursor) to quickly understand the project structure, architecture, key files, and development context. For human users, see [README.md](README.md).

---

## Project Overview

**Email Agent** is a Python CLI application that:
1. Connects to IMAP email servers
2. Fetches unprocessed emails
3. Uses AI (via OpenRouter API) to classify emails with granular scores
4. Applies threshold-based classification
5. Generates structured Obsidian notes using Jinja2 templates

**Current Status:** 
- **V4** (Orchestrator) - ✅ Complete and production-ready - Multi-tenant platform with rules engine, multi-account support, and V4-only CLI
- **V3** (Foundational Upgrade) - Historical version (superseded by V4)
- **V1 and V2** - Historical versions

**Working Branch:** `v4-orchestrator` (current production branch)

---

## Project Structure

```
email-agent/
├── main.py                    # CLI entry point
├── setup.py                   # Package setup
├── requirements.txt           # Python dependencies
├── README.md                  # Human-facing documentation
├── README-AI.md              # This file - AI agent entry point
├── README-task-master.md      # Task Master workflow docs
├── pdd_V4.md                  # Product Design Doc V4 (current, complete)
├── pdd.md                     # Product Design Doc V3 (historical, superseded by V4)
├── pdd_v2.md                  # Product Design Doc V2 (historical)
│
├── src/                       # Source code modules (V4)
│   ├── __init__.py
│   ├── cli_v4.py              # V4 CLI interface (click-based) - Current production CLI
│   ├── orchestrator.py        # V4 MasterOrchestrator (multi-account orchestration)
│   ├── account_processor.py   # V4 Account Processor (per-account pipeline with safety interlock)
│   ├── config_loader.py       # V4 configuration loader with deep merge
│   ├── config_schema.py       # V4 configuration schema validation
│   ├── config_validator.py    # V4 configuration validator
│   ├── models.py              # V4 EmailContext data class
│   ├── content_parser.py      # V4 HTML to Markdown parser
│   ├── rules.py               # V4 Rules engine (blacklist/whitelist)
│   ├── imap_client.py         # IMAP operations (shared)
│   ├── llm_client.py          # LLM API client with retry logic (shared)
│   ├── decision_logic.py      # Threshold-based classification (shared)
│   ├── note_generator.py      # Jinja2 note generation (shared)
│   ├── prompt_renderer.py     # Prompt rendering (shared)
│   ├── dry_run.py             # Dry-run mode (shared)
│   ├── dry_run_output.py      # Dry-run output formatting (shared)
│   ├── logging_config.py      # V4 centralized logging configuration
│   └── ...                    # Additional modules
│
├── tests/                     # Test suite
│   ├── conftest.py            # Pytest fixtures
│   ├── test_cli.py            # CLI tests
│   ├── test_config.py         # Configuration tests
│   ├── test_imap_connection.py
│   ├── test_email_tagging.py
│   ├── test_email_tagging_workflow.py
│   ├── test_email_to_markdown.py
│   ├── test_email_truncation.py
│   ├── test_email_summarization.py
│   ├── test_summarization.py
│   ├── test_obsidian_*.py      # Obsidian integration tests
│   ├── test_e2e_v4_pipeline.py  # V4 end-to-end tests with real email accounts
│   └── ...                    # Additional module tests
│
├── config/                    # Configuration files
│   ├── config.yaml            # Main config (user-created, gitignored)
│   ├── config.yaml.example    # Example global configuration template
│   ├── prompt.md.example      # Example AI prompt template
│   ├── note_template.md.j2    # Jinja2 note template
│   ├── prompt.md              # LLM classification prompt
│   ├── accounts/              # Account-specific configurations
│   │   └── *.yaml             # Account-specific config files (e.g., example-account.yaml)
│   ├── blacklist.yaml         # Global blacklist rules
│   └── whitelist.yaml         # Global whitelist rules
│
├── docs/                      # Documentation
│   ├── MAIN_DOCS.md           # Documentation index (developer-focused)
│   ├── COMPLETE_GUIDE.md      # Complete user guide (end-user focused)
│   ├── TROUBLESHOOTING.md     # Troubleshooting guide
│   ├── imap-fetching.md       # IMAP implementation details
│   ├── imap-keywords-vs-flags.md
│   ├── logging-system.md      # Logging architecture
│   ├── prompts.md             # Prompt management
│   ├── v4-configuration.md    # V4 configuration system
│   ├── v4-configuration-reference.md # Complete V4 configuration reference
│   ├── v4-cli-usage.md        # V4 CLI usage guide
│   ├── v4-models.md           # V4 EmailContext data model
│   ├── v4-content-parser.md   # V4 HTML to Markdown parser
│   ├── v4-rules-engine.md     # V4 Rules engine
│   ├── v4-account-processor.md # V4 Account Processor
│   ├── v4-orchestrator.md     # V4 MasterOrchestrator
│   ├── v4-migration-guide.md   # Migration guide from V3 to V4
│   ├── v4-installation-setup.md # V4 installation and setup
│   ├── v4-quick-start.md       # V4 quick start guide
│   ├── v4-troubleshooting.md   # V4 troubleshooting guide
│   ├── v4-e2e-test-setup.md   # V4 E2E test account setup
│   ├── v4-e2e-test-environment.md # V4 E2E test environment
│   ├── v4-e2e-test-scenarios.md # V4 E2E test scenarios
│   ├── v4-e2e-test-execution.md # V4 E2E test execution guide
│   │
│   # Historical Documentation
│   ├── v3-*.md                 # V3 module documentation (historical)
│   │
│   ├── live-test-guide.md    # Live testing guide
│   ├── CODE_REVIEW_2026-01.md
│   ├── CLEANUP_REPORT_2026-01.md
│   └── ...                    # Additional docs
│
├── scripts/                   # Utility scripts
│   ├── test_imap_live.py      # Live IMAP connection test
│   ├── test_imap_flags.py     # IMAP flags test
│   ├── test_imap_direct_query.py
│   ├── test_imap_flags_query.py
│   ├── test_imap_search_filter.py
│   ├── check_imap_flags.py
│   ├── check_live_test_config.py
│   ├── test_html_truncation_debug.py
│   ├── prd.txt                # Product Requirements Document
│   └── example_prd.txt        # PRD template
│
├── tasks/                     # Task Master task management
│   ├── tasks.json             # Main task file
│   └── task_*.txt             # Individual task files
│
├── logs/                      # Log files (gitignored)
│   ├── agent.log              # Main application log
│   ├── analytics.jsonl        # Analytics data (JSONL format)
│   └── email_changelog.md     # Email processing changelog (V2)
│
└── .env                       # Environment variables (gitignored, user-created)
```

---

## Key Architecture Concepts

### V4 Architecture (Current Production)
1. **Configuration Loading** → Load global config + account-specific overrides via `ConfigLoader`
2. **Account Discovery** → Discover accounts from `config/accounts/` directory
3. **Account Processing** (per account with isolated state):
   a. **Blacklist Rules** → Pre-processing rules to filter emails
   b. **IMAP Connection** → Fetch emails based on configured query (excluding processed)
   c. **Content Parsing** → Convert HTML emails to Markdown using `html2text`
   d. **LLM Classification** → Get granular scores (importance_score, spam_score)
   e. **Whitelist Rules** → Post-LLM modifiers to boost scores and add tags
   f. **Decision Logic** → Apply threshold-based classification
   g. **Note Generation** → Render Jinja2 template with email data and scores
   h. **File Creation** → Save to Obsidian vault (account-specific path)
   i. **Tagging** → Tag email with `AIProcessed` flag
   j. **Logging** → Record to operational log with structured context and account lifecycle tracking
4. **Summary** → Display processing summary for all accounts

### Historical Architectures
- **V3**: Single-account processing with settings facade (superseded by V4)
- **V2**: Keyword-based classification (urgent/neutral/spam) with conditional summarization
- **V1**: Basic email tagging with simple AI classification

### Core Modules

**`src/orchestrator.py`** - V4 MasterOrchestrator (multi-account orchestration)
- `MasterOrchestrator` - Main orchestrator class
- `process_account()` - Process a single account
- `process_all_accounts()` - Process all configured accounts
- `discover_accounts()` - Discover accounts from config/accounts/ directory
- Orchestrates: Account discovery → Account processing → Summary

**`src/account_processor.py`** - V4 Account Processor (per-account pipeline)
- `AccountProcessor` - Isolated per-account processing pipeline
- `process_emails()` - Process emails for a single account
- `process_single_email()` - Process individual email
- Orchestrates: Blacklist Rules → IMAP → Content Parsing → LLM → Whitelist Rules → Decision Logic → Note Generation → Tagging → Logging
- Includes safety interlock with cost estimation

**`src/cli_v4.py`** - V4 CLI interface
- `cli` - Click command group
- `process` - Process emails command (--account or --all)
- `cleanup-flags` - Cleanup IMAP flags command
- `show-config` - Display merged configuration
- Uses `MasterOrchestrator` and `ConfigLoader` exclusively

**`src/config_loader.py`** - V4 configuration loader
- `ConfigLoader` - Configuration loader with deep merge
- `load()` - Load global config + account-specific overrides
- Deep merge logic for configuration hierarchy
- Environment variable support

**`src/rules.py`** - V4 Rules engine
- `RulesEngine` - Rules engine class
- `apply_blacklist()` - Pre-processing blacklist rules
- `apply_whitelist()` - Post-LLM whitelist rules
- Supports drop, record, boost_score, and add_tag actions

**`src/imap_client.py`** - IMAP operations (shared)
- `IMAPClient` - IMAP client class
- `connect()` - Connection management
- `fetch_emails()` - Email fetching with query support
- `fetch_email_by_uid()` - Fetch specific email by UID
- `tag_email()` - Flag/tag application
- `remove_flags()` - Flag removal (for cleanup)

**`src/llm_client.py`** - LLM API client (shared)
- `LLMClient` - LLM client class
- `classify_email()` - Classification API call with retry logic
- Returns JSON with `importance_score` and `spam_score` (0-10)
- Exponential backoff retry on failures

**`src/decision_logic.py`** - Threshold-based classification (shared)
- `classify_email()` - Threshold-based classification
- `is_important()` - Check if importance_score >= threshold
- `is_spam()` - Check if spam_score >= threshold

**`src/note_generator.py`** - Jinja2 note generation (shared)
- `generate_note()` - Render Jinja2 template
- `load_template()` - Load template file
- Generates Markdown with YAML frontmatter

---

## Key Configuration

### V4 Configuration System (`src/config_loader.py`)
- **Multi-Account Configuration**: Global defaults + account-specific overrides
- **Deep Merge**: Account configs override global config with deep merging
- **Configuration Files**:
  - `config/config.yaml` - Global default configuration
  - `config/accounts/<account-name>.yaml` - Account-specific overrides
  - `.env` - Environment variables (IMAP passwords, API keys)
- **ConfigLoader**: Loads and merges configurations with validation
- **Schema Validation**: Validates configuration structure using Pydantic models

### V4 Configuration Structure
- **Global Config** (`config/config.yaml`):
  - `imap` - IMAP server defaults (port, query, processed_tag, application_flags)
  - `paths` - File and directory paths (template_file, obsidian_vault, log_file, etc.)
  - `openrouter` - OpenRouter API configuration (api_key_env, api_url)
  - `classification` - Classification settings (model, temperature, retry settings)
  - `summarization` - Summarization settings (optional)
  - `processing` - Processing thresholds and limits (importance_threshold, spam_threshold, max_emails_per_run)
- **Account Config** (`config/accounts/<account-name>.yaml`):
  - `imap` - Account-specific IMAP settings (server, username, password_env) - **required**
  - `paths` - Account-specific path overrides (e.g., obsidian_vault)
  - Any other overrides as needed

### V4 Key Features
- Multi-account support with isolated state and configuration
- Score-based classification (0-10 scores)
- Rules engine (blacklist/whitelist)
- HTML content parsing to Markdown
- Threshold-based decision logic
- Jinja2 templating for note generation
- CLI commands: `process`, `cleanup-flags`, `show-config`
- Dry-run mode for preview
- Force-reprocess capability
- Safety interlock with cost estimation

---

## Important Constants

**IMAP Tag Names**:
- `AIProcessed` - V3 processed tag (default: 'AIProcessed')
- Application flags managed by cleanup command: `AIProcessed`, `ObsidianNoteCreated`, `NoteCreationFailed`

**Error Codes** (`src/error_handling.py`):
- `ErrorCode` class with standardized error codes (E1xxx, E2xxx, etc.)

---

## Development Workflow

### Task Management
- Uses **Task Master** for task tracking
- Tasks in `tasks/tasks.json`
- Individual task files in `tasks/task_*.txt`
- **Always commit tasks.json after status changes** (see `.cursor/rules/dev_workflow.mdc`)

### Mandatory Task Completion Workflow
**Every task has a mandatory final stage that MUST be completed before marking the task done:**

1. **Validate Tests:**
   - Run full test suite: `pytest -v`
   - Ensure all tests pass (new and existing)
   - Fix any failing tests before proceeding

2. **Update Documentation:**
   - Update/create module documentation in `docs/` directory
   - Update `docs/MAIN_DOCS.md` if adding new documentation
   - Reference relevant PDD sections
   - Follow [documentation.mdc](.cursor/rules/documentation.mdc) guidelines

3. **Review for Rule Learnings:**
   - Check if new patterns emerged that should be captured in rules
   - Review [self_improve.mdc](.cursor/rules/self_improve.mdc) for guidance
   - Add new rules if: new technology/pattern used in 3+ files, common bugs could be prevented, or new best practices emerged
   - Update existing rules if better examples exist
   - Tag rule updates with `[rule]` in commit message

4. **Mark Task Done:**
   - Update task status: `task-master set-status --id=<task_id> --status=done`
   - Commit tasks.json: `git add tasks/tasks.json && git commit -m "chore(tasks): Mark task <id> complete"`

5. **Commit All Changes:**
   - Commit all code/docs/rule changes: `git add . && git commit -m "feat(module): Task <id> - <description> [docs]"`
   - Include task ID in commit message
   - Tag with `[docs]` for documentation, `[rule]` for rule updates

**This workflow is MANDATORY and must not be skipped.** See [task_completion_workflow.mdc](.cursor/rules/task_completion_workflow.mdc) for complete details.

### Testing
- **334+ tests total** (all passing)
- Run: `pytest` or `pytest -v`
- Integration tests: `tests/test_integration_v3_workflow.py`
- V3 E2E tests: `tests/test_e2e_imap.py`, `tests/test_e2e_llm.py`
- V4 E2E tests: `tests/test_e2e_v4_pipeline.py` (Task 19) ✅
- Live tests: `scripts/test_imap_live.py`

### Code Style
- Follow existing patterns
- Use `log_error_with_context()` for error logging
- Use `safe_imap_operation()` context manager for IMAP ops
- Commit after each subtask completion

---

## Key Design Decisions

### IMAP Flags vs KEYWORDS
- **Decision:** Use FLAGS (not KEYWORDS extension)
- **Reason:** Better compatibility across IMAP servers
- **Note:** Flags may not be visible in Thunderbird UI, but are functional

### Idempotency System
- **V3:** Uses `AIProcessed` flag (configurable via `imap.processed_tag`)
- **Default:** Automatically excludes emails with `AIProcessed` flag
- **Force Reprocess:** Use `--force-reprocess` flag to ignore processed tag

### Error Handling
- **Strategy:** Isolate per-email errors, continue processing
- **Tools:** `ErrorCode` constants, `log_error_with_context()`, `categorize_error()`
- **Location:** `src/error_handling.py`

### V3 Note Generation
- **Format:** YAML frontmatter + Markdown body (via Jinja2 template)
- **Template:** `config/note_template.md.j2` (configurable)
- **Location:** Obsidian vault directory (configurable via `paths.obsidian_vault`)
- **Naming:** `YYYY-MM-DD-HHMMSS - <Sanitized-Subject>.md`
- **Content:** Includes email metadata, LLM scores, processing info, and email body
- **Verification:** Tags email with `AIProcessed` after successful creation

---

## File Dependencies

### Critical Entry Points
- `main.py` → `src/cli_v4.py` → `src/orchestrator.py` (MasterOrchestrator)
- `src/orchestrator.py` (MasterOrchestrator) creates: `AccountProcessor` instances
- `AccountProcessor` coordinates: `config_loader`, `rules`, `imap_client`, `content_parser`, `llm_client`, `decision_logic`, `note_generator`, `logging_config`

### Module Dependencies
- `cli_v4.py` depends on: `orchestrator` (MasterOrchestrator), `config_loader`, `logging_config`, `dry_run_output`
- `orchestrator.py` (MasterOrchestrator) depends on: `config_loader`, `account_processor`, `logging_config`
- `account_processor.py` depends on: `config_loader`, `rules`, `imap_client`, `content_parser`, `llm_client`, `decision_logic`, `note_generator`, `models`, `logging_config`
- `config_loader.py` depends on: `config_schema`, `config_validator`
- `rules.py` depends on: `config_loader`, `models`
- `note_generator.py` depends on: `config_loader`, `prompt_renderer` (for template rendering)
- `imap_client.py` depends on: `config_loader`, `logging_config`
- `llm_client.py` depends on: `config_loader`, `logging_config`

---

## Testing Strategy

### Test Organization
- **Unit tests:** One per module in `tests/` (test_config.py, test_imap_client.py, test_llm_client.py, etc.)
- **Integration tests:** Module integration tests
- **V4 E2E tests:** `test_e2e_v4_pipeline.py` - Complete V4 pipeline E2E tests with real email accounts
- **Live tests:** Scripts in `scripts/` directory

### Mock Strategy
- IMAP: Mock `safe_imap_operation()` context manager
- OpenRouter: Mock `OpenRouterClient` and API responses
- File system: Use `tempfile` for Obsidian operations

---

## Current Task Status

**V4 Implementation:** ✅ **COMPLETE** (on `v4-orchestrator` branch)
- All V4 tasks completed (Tasks 1-22)
- V3 to V4 migration complete (Task 22) - All V3 code removed, V4-only architecture
- Comprehensive test suite (unit, integration, E2E)
- All features implemented and tested
- Documentation complete
- **Key Features:**
  - Multi-account support with isolated state
  - Configuration system with deep merge
  - Rules engine (blacklist/whitelist)
  - HTML content parsing
  - Account Processor with safety interlock
  - MasterOrchestrator for multi-account coordination
  - V4-only CLI (cli_v4.py)

**V3 Implementation:** Historical (superseded by V4)
- V3 was the foundational upgrade version
- All V3 code has been removed in Task 22 migration
- V3 documentation preserved for historical reference

**Next:** Check `tasks/tasks.json` or run `task-master next` for current tasks

---

## Quick Reference for AI Agents

### When Starting Work:
1. **Read:** `README-AI.md` (this file) - **This is the main entry point**
2. **Check Branch:** 
   - Current work: `v4-orchestrator` branch (see `pdd_V4.md`)
   - Historical: `main` branch (V3, superseded by V4)
3. **Check:** `tasks/tasks.json` or run `task-master next` for current task
4. **Review:** Relevant module docs in `docs/` directory
   - V4: `docs/v4-*.md` (current production documentation)
   - Historical: `docs/v3-*.md` (historical reference)
5. **Understand:** Current task context from `tasks/task_*.txt`
6. **Note:** All tasks include a mandatory final stage - see [task_completion_workflow.mdc](.cursor/rules/task_completion_workflow.mdc)

### When Making Changes:
1. **Follow:** `.cursor/rules/dev_workflow.mdc` - commit tasks.json after status changes
2. **Follow:** `.cursor/rules/git_commits.mdc` - commit after each subtask
3. **Follow:** `.cursor/rules/task_completion_workflow.mdc` - **MANDATORY** final stage for every task
4. **Test:** Run `pytest` before committing
5. **Document:** Update relevant docs if adding features
6. **Review Rules:** Check for learnings that should be captured in rules

### Key Rules Files:
- `.cursor/rules/task_completion_workflow.mdc` - **MANDATORY** task completion workflow (tests, docs, rules, commit)
- `.cursor/rules/dev_workflow.mdc` - Development workflow (commit tasks.json!)
- `.cursor/rules/git_commits.mdc` - Commit message guidelines
- `.cursor/rules/documentation.mdc` - Documentation requirements
- `.cursor/rules/self_improve.mdc` - Rule improvement guidelines
- `.cursor/rules/taskmaster.mdc` - Task Master tool reference
- `.cursor/rules/imap_fetching.mdc` - IMAP module guidelines

### Important Patterns:
- **Error Handling:** Use structured logging with context
- **IMAP Operations:** Use `IMAPClient` with proper connection management
- **Configuration:** Access via `ConfigLoader` instance (V4)
- **Logging:** Use `logging_config.init_logging()` for centralized logging (V4)
- **Account Processing:** Use `AccountProcessor` for per-account isolated processing
- **Orchestration:** Use `MasterOrchestrator` for multi-account coordination

---

## Common Operations

### Adding a New Feature:
1. Create/update task in Task Master
2. Complete all subtasks
3. **MANDATORY Final Stage:**
   - Run full test suite: `pytest -v`
   - Update documentation in `docs/` directory
   - Review for rule learnings and update rules if needed
   - Mark task done: `task-master set-status --id=<id> --status=done`
   - Commit tasks.json
   - Commit all changes with task ID in message
4. See [task_completion_workflow.mdc](.cursor/rules/task_completion_workflow.mdc) for complete workflow

### Debugging:
- Enable debug: `python main.py --debug`
- Check logs: `logs/agent.log`
- Check analytics: `logs/analytics.jsonl`
- Check changelog: `logs/email_changelog.md`

### Testing IMAP:
- Live test: `python scripts/test_imap_live.py`
- Flags test: `python scripts/test_imap_flags.py`

---

## Version Information

- **V4:** Orchestrator (✅ Complete and production-ready, `v4-orchestrator` branch)
  - Multi-account support with state isolation
  - Configuration system (default + override model with deep merge)
  - Rules engine (blacklist/whitelist)
  - HTML content parsing
  - Account Processor with safety interlock
  - MasterOrchestrator for multi-account coordination
  - V4-only CLI (cli_v4.py)
  - All V3 code removed (Task 22 migration complete)
- **V3:** Foundational Upgrade (historical, superseded by V4)
  - Score-based classification
  - CLI controls
  - Jinja2 templating
  - Modular architecture
  - **Status:** All V3 code removed in Task 22 migration
- **V2:** Obsidian integration (historical)
- **V1:** Email tagging (historical)

---

## Documentation Hierarchy

1. **README.md** - Human-facing overview
2. **README-AI.md** - This file (AI agent entry point) ⭐ **START HERE**
3. **pdd_V4.md** - V4 product requirements (current production, v4-orchestrator branch)
4. **pdd.md** - V3 product requirements (historical, superseded by V4)
5. **docs/MAIN_DOCS.md** - Documentation index
6. **docs/COMPLETE_GUIDE.md** - Complete user guide
7. **docs/v4-*.md** - V4 module documentation (current production)
8. **docs/v3-*.md** - V3 module documentation (historical reference)

---

