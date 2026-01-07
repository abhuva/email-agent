# Email Agent - AI Agent Entry Point

> **Purpose:** This document is optimized for AI agents (like Cursor) to quickly understand the project structure, architecture, key files, and development context. For human users, see [README.md](README.md).

---

## Project Overview

**Email Agent** is a Python CLI application that:
1. Connects to IMAP email servers
2. Fetches unprocessed emails
3. Uses AI (via OpenRouter API) to classify emails
4. Applies IMAP tags/flags based on AI classification
5. (V2) Creates structured Obsidian notes from processed emails

**Current Status:** V1 complete, V2 (Obsidian Integration) complete

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
├── pdd.md                     # Product Design Doc V1 (complete)
├── pdd_v2.md                  # Product Design Doc V2 (current focus)
│
├── src/                       # Source code modules
│   ├── __init__.py
│   ├── cli.py                 # Command-line interface
│   ├── config.py              # Configuration loading/validation
│   ├── main_loop.py           # Main email processing orchestration
│   ├── imap_connection.py     # IMAP operations (connect, search, fetch, tag)
│   ├── openrouter_client.py   # OpenRouter API client
│   ├── email_tagging.py       # Email tagging workflow
│   ├── email_truncation.py    # Email body truncation
│   ├── email_to_markdown.py   # HTML/plain text to Markdown conversion
│   ├── email_summarization.py # AI summarization (V2)
│   ├── summarization.py       # Summarization decision logic (V2)
│   ├── tag_mapping.py         # AI keyword → IMAP tag mapping
│   ├── prompt_loader.py       # Prompt file loading
│   ├── logger.py              # Logging setup
│   ├── analytics.py           # Analytics tracking (V1 + V2 metrics)
│   ├── changelog.py            # Changelog/audit log (V2)
│   ├── error_handling.py      # Error handling utilities (V2)
│   ├── obsidian_utils.py      # Obsidian file system utilities (V2)
│   ├── obsidian_note_creation.py  # Obsidian note creation (V2)
│   ├── obsidian_note_assembly.py  # Note content assembly (V2)
│   └── yaml_frontmatter.py    # YAML frontmatter generation (V2)
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
│   ├── test_integration_v2_workflow.py  # End-to-end V2 tests
│   └── ...                    # Additional module tests
│
├── config/                    # Configuration files
│   ├── config.yaml            # Main config (user-created, gitignored)
│   ├── config.yaml.example    # Example config template
│   ├── prompt.md.example      # Example AI prompt template
│   └── summarization_prompt.md  # Summarization prompt (V2)
│
├── docs/                      # Documentation
│   ├── MAIN_DOCS.md           # Documentation index (developer-focused)
│   ├── COMPLETE_GUIDE.md      # Complete user guide (end-user focused)
│   ├── TROUBLESHOOTING.md     # Troubleshooting guide
│   ├── imap-fetching.md       # IMAP implementation details
│   ├── imap-keywords-vs-flags.md
│   ├── logging-system.md      # Logging architecture
│   ├── prompts.md             # Prompt management
│   ├── summarization.md       # Summarization system (V2)
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

### V1 Architecture (Email Tagging)
1. **IMAP Connection** → Fetch emails → **AI Classification** → **Tagging** → **Logging**
2. Uses `AIProcessed` flag for idempotency
3. Single-pass processing with error isolation

### V2 Architecture (Obsidian Integration)
1. **IMAP Connection** → Fetch emails → **AI Classification** → **Tagging**
2. **Conditional Summarization** (if email has specific tags)
3. **Obsidian Note Creation** → **YAML Frontmatter** → **Markdown Conversion**
4. **Changelog Tracking** → **Analytics** → **Logging**
5. Uses `ObsidianNoteCreated` and `NoteCreationFailed` flags for idempotency

### Core Modules

**`src/main_loop.py`** - Central orchestration
- `run_email_processing_loop()` - Main entry point
- `process_email_with_ai()` - AI classification
- Orchestrates: fetching → AI → tagging → note creation → changelog

**`src/imap_connection.py`** - IMAP operations
- `connect_imap()` - Connection management
- `fetch_emails()` - Email fetching with configurable exclusions (Task 16)
- `search_emails_excluding_processed()` - Query building with exclusions
- `build_imap_query_with_exclusions()` - Query builder (Task 16)
- `add_tags_to_email()` - Flag/tag application
- `safe_imap_operation()` - Context manager for safe IMAP ops

**`src/config.py`** - Configuration management
- `ConfigManager` - Main config class
- Validates V2 paths and formats
- `exclude_tags` and `disable_idempotency` (Task 16)
- `get_imap_query()` - Gets primary IMAP query

**`src/openrouter_client.py`** - AI API client
- `OpenRouterClient` - API client class
- `send_email_prompt_for_keywords()` - Classification API call
- `extract_keywords_from_openrouter_response()` - Response parsing

**`src/obsidian_note_creation.py`** - V2 note creation
- `create_obsidian_note_for_email()` - Main note creation function
- `tag_email_note_created()` - Success tagging
- `tag_email_note_failed()` - Failure tagging

---

## Key Configuration

### ConfigManager (`src/config.py`)
- Loads `config/config.yaml` and `.env`
- Validates all paths and formats
- Provides: `exclude_tags`, `disable_idempotency`, `obsidian_vault_path`, etc.

### IMAP Query System (Task 16)
- `imap_query` - Primary query string (V2)
- `imap_query_exclusions` - Configurable tag exclusions
  - `exclude_tags` - Tags to exclude (default: AIProcessed, ObsidianNoteCreated, NoteCreationFailed)
  - `additional_exclude_tags` - Additional exclusions
  - `disable_idempotency` - Disable exclusions (NOT RECOMMENDED)

### V2 Configuration
- `obsidian_vault_path` - Obsidian vault directory
- `summarization_tags` - Tags that trigger summarization
- `summarization_prompt_path` - Summarization prompt file
- `changelog_path` - Changelog file path

---

## Important Constants

**IMAP Tag Names** (`src/obsidian_note_creation.py`):
- `OBSIDIAN_NOTE_CREATED_TAG = 'ObsidianNoteCreated'`
- `NOTE_CREATION_FAILED_TAG = 'NoteCreationFailed'`
- `AIProcessed` - V1 processed tag

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
- **V1:** Uses `AIProcessed` flag
- **V2:** Uses `ObsidianNoteCreated` and `NoteCreationFailed` flags
- **Task 16:** Made configurable via `exclude_tags`
- **Default:** Excludes all three tags automatically

### Error Handling
- **Strategy:** Isolate per-email errors, continue processing
- **Tools:** `ErrorCode` constants, `log_error_with_context()`, `categorize_error()`
- **Location:** `src/error_handling.py`

### V2 Note Creation
- **Format:** YAML frontmatter + Markdown body
- **Location:** Obsidian vault directory (configurable)
- **Naming:** `YYYY-MM-DD-HHMMSS - <Sanitized-Subject>.md`
- **Verification:** Tags email after successful creation

---

## File Dependencies

### Critical Entry Points
- `main.py` → `src/cli.py` → `src/main_loop.py`
- `src/main_loop.py` imports most other modules

### Module Dependencies
- `main_loop.py` depends on: `config`, `imap_connection`, `openrouter_client`, `email_tagging`, `obsidian_note_creation`, `changelog`, `analytics`, `error_handling`
- `obsidian_note_creation.py` depends on: `obsidian_utils`, `obsidian_note_assembly`, `yaml_frontmatter`, `email_to_markdown`
- `email_tagging.py` depends on: `tag_mapping`, `imap_connection`

---

## Testing Strategy

### Test Organization
- **Unit tests:** One per module in `tests/`
- **Integration tests:** `test_integration_v2_workflow.py` (9 tests)
- **Live tests:** Scripts in `scripts/` directory

### Mock Strategy
- IMAP: Mock `safe_imap_operation()` context manager
- OpenRouter: Mock `OpenRouterClient` and API responses
- File system: Use `tempfile` for Obsidian operations

---

## Current Task Status

**Task 17: Codebase Cleanup and Documentation Consolidation** ✅ **COMPLETE**
- All subtasks completed
- 334 tests passing
- Code cleaned up
- Documentation improved

**Next:** Check `tasks/tasks.json` or run `task-master next` for next task

---

## Quick Reference for AI Agents

### When Starting Work:
1. **Read:** `README-AI.md` (this file) and `pdd_v2.md`
2. **Check:** `tasks/tasks.json` or run `task-master next`
3. **Review:** Relevant module docs in `docs/`
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

- **V1:** Email tagging (complete)
- **V2:** Obsidian integration (in progress)
- **Current Focus:** V2 features (see `pdd_v2.md`)

---

## Documentation Hierarchy

1. **README.md** - Human-facing overview
2. **README-AI.md** - This file (AI agent entry point)
3. **pdd_v2.md** - Current product requirements
4. **docs/MAIN_DOCS.md** - Documentation index
5. **docs/COMPLETE_GUIDE.md** - Complete user guide
6. **Module docs** - Implementation details

---

*Last Updated: 2026-01-07 (Task 17 Complete)*
