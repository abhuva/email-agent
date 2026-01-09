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

**Current Status:** V3 (Foundational Upgrade) complete and production-ready. V1 and V2 are historical versions.

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
├── pdd.md                     # Product Design Doc V3 (current, complete)
├── pdd_v2.md                  # Product Design Doc V2 (historical)
│
├── src/                       # Source code modules
│   ├── __init__.py
│   ├── cli_v3.py              # V3 CLI interface (click-based)
│   ├── settings.py            # V3 configuration facade
│   ├── config_v3_loader.py    # V3 configuration loading
│   ├── config_v3_schema.py    # V3 configuration schema
│   ├── orchestrator.py        # V3 pipeline orchestration
│   ├── imap_client.py         # V3 IMAP operations
│   ├── llm_client.py          # V3 LLM API client with retry logic
│   ├── decision_logic.py      # V3 threshold-based classification
│   ├── note_generator.py      # V3 Jinja2 note generation
│   ├── prompt_renderer.py     # V3 prompt rendering
│   ├── v3_logger.py           # V3 logging system
│   ├── error_handling_v3.py   # V3 error handling
│   ├── dry_run.py             # V3 dry-run mode
│   ├── dry_run_processor.py   # V3 dry-run processing
│   ├── dry_run_output.py      # V3 dry-run output
│   ├── backfill.py            # V3 backfill functionality
│   ├── cleanup_flags.py       # V3 cleanup flags command
│   └── ...                    # Additional V3 modules
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
│   ├── test_integration_v3_workflow.py  # End-to-end V3 tests
│   └── ...                    # Additional module tests
│
├── config/                    # Configuration files
│   ├── config.yaml            # Main config (user-created, gitignored)
│   ├── config.yaml.example    # Example config template
│   ├── prompt.md.example      # Example AI prompt template
│   ├── note_template.md.j2     # Jinja2 note template (V3)
│   └── prompt.md                # LLM classification prompt (V3)
│
├── docs/                      # Documentation
│   ├── MAIN_DOCS.md           # Documentation index (developer-focused)
│   ├── COMPLETE_GUIDE.md      # Complete user guide (end-user focused)
│   ├── TROUBLESHOOTING.md     # Troubleshooting guide
│   ├── imap-fetching.md       # IMAP implementation details
│   ├── imap-keywords-vs-flags.md
│   ├── logging-system.md      # Logging architecture
│   ├── prompts.md             # Prompt management
│   ├── v3-*.md                 # V3 module documentation
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

### V3 Architecture (Current)
1. **Configuration Loading** → Load V3 config via `settings.py` facade
2. **IMAP Connection** → Fetch emails based on configured query
3. **LLM Classification** → Get granular scores (importance_score, spam_score)
4. **Decision Logic** → Apply threshold-based classification
5. **Note Generation** → Render Jinja2 template with email data and scores
6. **File Creation** → Save to Obsidian vault
7. **Tagging** → Tag email with `AIProcessed` flag
8. **Logging** → Record to operational log and structured analytics
9. **Changelog** → Append entry to changelog file

### Historical Architectures
- **V2**: Keyword-based classification (urgent/neutral/spam) with conditional summarization
- **V1**: Basic email tagging with simple AI classification

### Core Modules

**`src/orchestrator.py`** - V3 pipeline orchestration
- `process_emails()` - Main processing entry point
- `process_single_email()` - Process individual email
- Orchestrates: IMAP → LLM → Decision Logic → Note Generation → Tagging → Logging

**`src/imap_client.py`** - V3 IMAP operations
- `IMAPClient` - IMAP client class
- `connect()` - Connection management
- `fetch_emails()` - Email fetching with query support
- `fetch_email_by_uid()` - Fetch specific email by UID
- `tag_email()` - Flag/tag application
- `remove_flags()` - Flag removal (for cleanup)

**`src/settings.py`** - V3 configuration facade
- `settings` - Singleton facade instance
- `initialize()` - Initialize with config and env paths
- `get_imap_server()`, `get_openrouter_api_key()`, etc. - Getter methods
- Single source of truth for all configuration

**`src/llm_client.py`** - V3 LLM API client
- `LLMClient` - LLM client class
- `classify_email()` - Classification API call with retry logic
- Returns JSON with `importance_score` and `spam_score` (0-10)
- Exponential backoff retry on failures

**`src/decision_logic.py`** - V3 classification logic
- `classify_email()` - Threshold-based classification
- `is_important()` - Check if importance_score >= threshold
- `is_spam()` - Check if spam_score >= threshold

**`src/note_generator.py`** - V3 note generation
- `generate_note()` - Render Jinja2 template
- `load_template()` - Load template file
- Generates Markdown with YAML frontmatter

---

## Key Configuration

### Settings Facade (`src/settings.py`)
- Loads V3 `config/config.yaml` and `.env`
- Validates configuration structure
- Provides getter methods for all configuration values
- Single source of truth for configuration access

### V3 Configuration Structure
- `imap` - IMAP server configuration (server, port, username, query, processed_tag)
- `paths` - File and directory paths (template_file, obsidian_vault, log_file, etc.)
- `openrouter` - OpenRouter API configuration (api_key_env, api_url)
- `classification` - Classification settings (model, temperature, retry settings)
- `processing` - Processing thresholds and limits (importance_threshold, spam_threshold, max_emails_per_run)

### V3 Key Features
- Score-based classification (0-10 scores instead of keywords)
- Threshold-based decision logic
- Jinja2 templating for note generation
- CLI commands: `process`, `cleanup-flags`, `backfill`
- Dry-run mode for preview
- Force-reprocess capability

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

### Testing
- **334 tests total** (all passing)
- Run: `pytest` or `pytest -v`
- Integration tests: `tests/test_integration_v2_workflow.py`
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
- `main.py` → `src/cli_v3.py` → `src/orchestrator.py`
- `src/orchestrator.py` coordinates: `imap_client`, `llm_client`, `decision_logic`, `note_generator`, `v3_logger`

### Module Dependencies
- `orchestrator.py` depends on: `settings`, `imap_client`, `llm_client`, `decision_logic`, `note_generator`, `v3_logger`, `error_handling_v3`
- `note_generator.py` depends on: `settings`, `prompt_renderer` (for template rendering)
- `imap_client.py` depends on: `settings`, `error_handling_v3`
- `llm_client.py` depends on: `settings`, `error_handling_v3`

---

## Testing Strategy

### Test Organization
- **Unit tests:** One per V3 module in `tests/` (test_cli_v3.py, test_config_v3.py, test_imap_client.py, etc.)
- **Integration tests:** `test_integration_v3_workflow.py` - End-to-end V3 workflow tests
- **E2E tests:** Live tests with real IMAP connections (see `docs/v3-e2e-tests.md`)
- **Live tests:** Scripts in `scripts/` directory

### Mock Strategy
- IMAP: Mock `safe_imap_operation()` context manager
- OpenRouter: Mock `OpenRouterClient` and API responses
- File system: Use `tempfile` for Obsidian operations

---

## Current Task Status

**V3 Implementation:** ✅ **COMPLETE**
- All V3 tasks (1-18) completed
- Comprehensive test suite (unit, integration, E2E)
- All features implemented and tested
- Documentation complete

**Next:** Check `tasks/tasks.json` or run `task-master next` for next task

---

## Quick Reference for AI Agents

### When Starting Work:
1. **Read:** `README-AI.md` (this file) and `pdd.md` (V3 PDD)
2. **Check:** `tasks/tasks.json` or run `task-master next`
3. **Review:** Relevant V3 module docs in `docs/v3-*.md`
4. **Understand:** Current task context from `tasks/task_*.txt`

### When Making Changes:
1. **Follow:** `.cursor/rules/dev_workflow.mdc` - commit tasks.json after status changes
2. **Follow:** `.cursor/rules/git_commits.mdc` - commit after each subtask
3. **Test:** Run `pytest` before committing
4. **Document:** Update relevant docs if adding features

### Key Rules Files:
- `.cursor/rules/dev_workflow.mdc` - Development workflow (commit tasks.json!)
- `.cursor/rules/git_commits.mdc` - Commit message guidelines
- `.cursor/rules/taskmaster.mdc` - Task Master tool reference
- `.cursor/rules/imap_fetching.mdc` - IMAP module guidelines

### Important Patterns:
- **Error Handling:** Use `log_error_with_context()` from `error_handling.py`
- **IMAP Operations:** Use `safe_imap_operation()` context manager
- **Configuration:** Access via `ConfigManager` instance
- **Logging:** Use module-level `logger = logging.getLogger(__name__)`

---

## Common Operations

### Adding a New Feature:
1. Create/update task in Task Master
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Run full test suite
6. Commit with task ID in message

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

- **V3:** Foundational Upgrade (complete, current version)
  - Score-based classification
  - CLI controls
  - Jinja2 templating
  - Modular architecture
- **V2:** Obsidian integration (historical)
- **V1:** Email tagging (historical)

---

## Documentation Hierarchy

1. **README.md** - Human-facing overview
2. **README-AI.md** - This file (AI agent entry point)
3. **pdd.md** - V3 product requirements (current)
4. **docs/MAIN_DOCS.md** - Documentation index
5. **docs/COMPLETE_GUIDE.md** - Complete user guide
6. **docs/v3-*.md** - V3 module documentation

---

