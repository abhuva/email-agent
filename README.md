# Email Agent (Headless AI Email Tagger)

## Overview

An extensible Python CLI agent that connects to IMAP accounts, fetches emails, tags/classifies them via AI (OpenAI-compatible or Google/Gemini via OpenRouter), and logs every step. Built for robust team, audit, and production use with comprehensive error handling and logging.

**Current Status:** 
- **V3 (Foundational Upgrade)** - ✅ Complete and production-ready on `main` branch
- **V4 (Orchestrator)** - 🚧 In Development on `v4-orchestrator` branch - Multi-tenant platform with rules engine (Tasks 1-9 complete)
- **V1 and V2** - Historical versions

---

## Features

### V3 Features (Current Version)
- **Score-Based Classification**: Granular importance and spam scores (0-10) instead of rigid categories
- **CLI Controls**: Developer-friendly commands for targeted processing, debugging, and maintenance
  - `python main.py process` - Process emails with options for single UID, force-reprocess, and dry-run
  - `python main.py cleanup-flags` - Safely remove application-specific IMAP flags
  - `python main.py backfill` - Process historical emails with date range filtering
- **Jinja2 Templating**: Flexible note generation using external template files
- **Modular Architecture**: Clean separation of concerns with dedicated modules for IMAP, LLM, decision logic, and note generation
- **Settings Facade**: Centralized configuration management through `settings.py` facade
- **Dual Logging**: Operational logs (`agent.log`) and structured analytics (`analytics.jsonl`)
- **Threshold-Based Classification**: Configurable thresholds for importance and spam detection
- **Retry Logic**: Robust error handling with exponential backoff for LLM API calls
- **Dry-Run Mode**: Preview processing without making changes
- **Force-Reprocess**: Reprocess already-processed emails for testing and refinement
- **Backfill Support**: Process historical emails with progress tracking and throttling

### V4 Features (In Development - v4-orchestrator branch)
- **Multi-Account Support**: Process multiple email accounts with isolated state and configuration
- **Configuration System**: Default + Override model with deep merge (global config + account-specific overrides)
- **Rules Engine**: 
  - **Blacklist Rules**: Pre-processing rules to drop or record emails without AI processing
  - **Whitelist Rules**: Post-LLM modifiers that boost scores and add tags
- **HTML Content Parsing**: Convert HTML emails to Markdown using `html2text` with automatic fallback to plain text
- **Account Processor**: Isolated per-account processing pipeline with complete state isolation
- **Safety Interlock**: Cost estimation and user confirmation before high-cost operations
- **EmailContext Data Model**: Structured data class for tracking email state through the pipeline

**V4 Progress (Tasks 1-9 Complete):**
- ✅ Task 1: Configuration directory structure
- ✅ Task 2: Configuration loader with deep merge logic
- ✅ Task 3: Configuration schema validation
- ✅ Task 4: EmailContext data class
- ✅ Task 5: Content parser (HTML to Markdown)
- ✅ Task 6: Rules engine - Blacklist rules
- ✅ Task 7: Rules engine - Whitelist rules
- ✅ Task 8: Account Processor class
- ✅ Task 9: Safety interlock with cost estimation

### Historical Versions
- **V2 (Obsidian Integration)**: Obsidian note creation, YAML frontmatter, conditional summarization
- **V1 (Email Tagging)**: Basic IMAP email fetching and AI classification

---

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- IMAP email account credentials
- OpenRouter API key ([Get one here](https://openrouter.ai/))

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd email-agent
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the agent:**
   ```bash
   # Copy example configuration
   cp config/config.yaml.example config/config.yaml
   
   # Copy example environment file
   cp .env.example .env
   ```

4. **Edit configuration files:**
   - Edit `config/config.yaml` with your IMAP server details
   - Edit `.env` with your IMAP password and OpenRouter API key
   - See [Configuration](#configuration) section for details

5. **Create log directory:**
   ```bash
   mkdir -p logs
   ```

---

## Quick Start

### Basic Usage

```bash
# Process emails (default: processes up to max_emails_per_run from config)
python main.py process

# Process a specific email by UID
python main.py process --uid 12345

# Force reprocess an already-processed email
python main.py process --uid 12345 --force-reprocess

# Preview processing without making changes (dry-run)
python main.py process --dry-run

# Use custom config and env files
python main.py --config custom-config.yaml --env .env.production process

# Clean up application-specific IMAP flags (with confirmation)
python main.py cleanup-flags

# Process historical emails (backfill)
python main.py backfill --since 2024-01-01 --until 2024-12-31
```

### Command-Line Options

**Main Commands:**
- `process` - Process emails with AI classification and note generation
  - `--uid <ID>` - Process a specific email by UID
  - `--force-reprocess` - Ignore processed_tag and reprocess email
  - `--dry-run` - Preview processing without making changes
- `cleanup-flags` - Remove application-specific IMAP flags (requires confirmation)
- `backfill` - Process historical emails
  - `--since <DATE>` - Start date (YYYY-MM-DD)
  - `--until <DATE>` - End date (YYYY-MM-DD)
  - `--throttle <SECONDS>` - Delay between emails (default: 2)

**Global Options:**
- `--config <PATH>` - Path to YAML configuration file (default: config/config.yaml)
- `--env <PATH>` - Path to .env secrets file (default: .env)
- `--version` - Show program version
- `--help` - Show help message

---

## Configuration

### Configuration File (`config/config.yaml`)

V3 uses a grouped configuration structure. The main configuration file contains all operational parameters:

```yaml
# IMAP Server Configuration
imap:
  server: 'imap.example.com'          # IMAP server hostname
  port: 143                            # IMAP port (143 for STARTTLS, 993 for SSL)
  username: 'your-email@example.com'   # Email account username
  password_env: 'IMAP_PASSWORD'        # Environment variable name containing IMAP password
  query: 'ALL'                         # IMAP search query (e.g., 'ALL', 'UNSEEN', 'SENTSINCE 01-Jan-2024')
  processed_tag: 'AIProcessed'         # IMAP flag name for processed emails
  application_flags:                   # Application-specific flags for cleanup command
    - 'AIProcessed'                    # Flags managed by this application (safe to remove)
    - 'ObsidianNoteCreated'            # These flags can be cleaned up using cleanup-flags command
    - 'NoteCreationFailed'              # Default includes all V1/V2 processing flags

# File and Directory Paths
paths:
  template_file: 'config/note_template.md.j2'  # Jinja2 template for generating Markdown notes
  obsidian_vault: '/path/to/obsidian/vault'    # Obsidian vault directory (must exist)
  log_file: 'logs/agent.log'                   # Unstructured operational log file
  analytics_file: 'logs/analytics.jsonl'        # Structured analytics log (JSONL format)
  changelog_path: 'logs/email_changelog.md'    # Changelog/audit log file
  prompt_file: 'config/prompt.md'              # LLM prompt file for email classification
  summarization_prompt_path: 'config/summarization_prompt.md'  # Optional: Prompt file for summarization

# OpenRouter API Configuration
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'   # Environment variable name containing API key
  api_url: 'https://openrouter.ai/api/v1'  # OpenRouter API endpoint

# Classification Configuration
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # LLM model to use for classification
  temperature: 0.2                     # LLM temperature (0.0-2.0, lower = more deterministic)
  retry_attempts: 3                     # Number of retry attempts for failed API calls
  retry_delay_seconds: 5                # Initial delay between retries (exponential backoff)

# Summarization Configuration
summarization:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # LLM model to use for summarization
  temperature: 0.3                     # LLM temperature (0.0-2.0, typically higher for summarization)
  retry_attempts: 3                     # Number of retry attempts for failed API calls
  retry_delay_seconds: 5                # Initial delay between retries (exponential backoff)

# Processing Configuration
processing:
  importance_threshold: 8               # Minimum importance score (0-10) to mark email as important
  spam_threshold: 5                     # Maximum spam score (0-10) to consider email as spam
  max_body_chars: 4000                  # Maximum characters to send to LLM (truncates longer emails)
  max_emails_per_run: 15                # Maximum number of emails to process per execution
  summarization_tags:                  # Optional - only if you want summarization
    - 'important'                       # Tag generated when importance_score >= threshold
```

See `config/config.yaml.example` for a complete example with detailed comments.

### Environment Variables (`.env`)

The `.env` file contains sensitive credentials:

```bash
IMAP_PASSWORD=your-imap-password-here
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**Important:** Never commit `.env` to version control! Use `.env.example` as a template.

### AI Prompt File (`config/prompt.md`)

The prompt file contains the instructions sent to the AI for email classification. It should be a Markdown file with YAML frontmatter. See `config/prompt.md.example` for a template.

---

## How It Works

### V3 Workflow (Current Version)

1. **Configuration Loading**: Loads V3 configuration structure through `settings.py` facade
2. **Email Fetching**: Connects to IMAP server and fetches emails based on configured query (excluding processed emails)
3. **AI Classification**: Sends email content to LLM API, receives JSON with `importance_score` and `spam_score` (0-10)
4. **Decision Logic**: Applies threshold-based classification:
   - If `importance_score >= importance_threshold` → marks as important
   - If `spam_score >= spam_threshold` → marks as spam
5. **Note Generation**: Uses Jinja2 template to generate Markdown note with:
   - YAML frontmatter (metadata, scores, processing info)
   - Email body (converted from HTML/plain text to Markdown)
6. **File Creation**: Saves note to Obsidian vault directory
7. **Tagging**: Tags email with `AIProcessed` flag to prevent reprocessing
8. **Logging**: Records to operational log and structured analytics
9. **Changelog**: Appends entry to changelog file

### Complete Processing Flow (V3)

```
Start → Load Config (settings.py) → Connect IMAP → Fetch Emails
  ↓
For each email:
  ↓
Truncate body → Send to LLM API → Receive JSON scores
  ↓
Apply thresholds → Determine classification
  ↓
Render Jinja2 template → Generate Markdown note
  ↓
Save to Obsidian vault → Tag email (AIProcessed)
  ↓
Log to analytics.jsonl → Append to changelog
  ↓
Generate summary → Exit
```

### Historical Workflows

- **V2**: Used keyword-based classification (urgent/neutral/spam) and conditional summarization
- **V1**: Basic email tagging with simple AI classification

---

## Documentation

### V3 Documentation (Current Production Version)
- **[Product Design Doc V3 (PDD)](pdd.md)** — V3 project strategy, requirements, roadmap (✅ Complete)
- **[V3 Configuration Guide](docs/v3-configuration.md)** — V3 configuration system and settings facade
- **[V3 CLI Guide](docs/v3-cli.md)** — Command-line interface documentation
- **[V3 Migration Guide](docs/v3-migration-guide.md)** — Migrating from V2 to V3
- **[V3 Orchestrator](docs/v3-orchestrator.md)** — Pipeline orchestration
- **[V3 Note Generator](docs/v3-note-generator.md)** — Jinja2 templating system
- **[V3 Decision Logic](docs/v3-decision-logic.md)** — Threshold-based classification
- **[Scoring Criteria](docs/scoring-criteria.md)** — Email scoring system

### V4 Documentation (In Development - v4-orchestrator branch)
- **[Product Design Doc V4 (PDD)](pdd_V4.md)** — V4 project strategy and requirements
- **[V4 Configuration System](docs/v4-configuration.md)** — Multi-tenant configuration with account-specific overrides (Tasks 1-3) ✅
- **[V4 Models](docs/v4-models.md)** — EmailContext data class for pipeline state tracking (Task 4) ✅
- **[V4 Content Parser](docs/v4-content-parser.md)** — HTML to Markdown conversion with fallback (Task 5) ✅
- **[V4 Rules Engine](docs/v4-rules-engine.md)** — Blacklist and whitelist rules for email filtering (Tasks 6-7) ✅
- **[V4 Account Processor](docs/v4-account-processor.md)** — Isolated per-account email processing pipeline (Tasks 8-9) ✅

### General Documentation
- **[Main Documentation Map](docs/MAIN_DOCS.md)** — Centralized documentation index
- **[Task Master Workflow](README-task-master.md)** — AI-driven task/project management

**Historical Documentation:**
- **[Product Design Doc V2 (PDD)](pdd_v2.md)** — V2 project strategy (historical)
- **[Product Design Doc V1 (PDD)](old pdd+prd/pdd.md)** — V1 project strategy (historical)

---

## Troubleshooting

### Common Issues

#### Configuration Errors

**Error:** `ConfigError: Missing required env vars: ['IMAP_PASSWORD']`

**Solution:** Ensure your `.env` file exists and contains all required variables:
```bash
IMAP_PASSWORD=your-password
OPENROUTER_API_KEY=your-api-key
```

**Error:** `ConfigError: Config file not found: config/config.yaml`

**Solution:** Copy the example config file:
```bash
cp config/config.yaml.example config/config.yaml
# Then edit it with your settings
```

#### IMAP Connection Errors

**Error:** `IMAPConnectionError: IMAP login failed`

**Solution:**
- Verify your IMAP credentials in `.env`
- Check if your email provider requires app-specific passwords
- Ensure port 993 (SSL) or 143 (STARTTLS) is correct
- Some providers require enabling "Less secure app access" or IMAP access

**Error:** `[SSL: WRONG_VERSION_NUMBER] wrong version number`

**Solution:** Your server uses STARTTLS on port 143, not direct SSL. The code handles this automatically, but ensure `port: 143` in config.

#### AI Processing Errors

**Error:** `OpenRouterAPIError: HTTP 401: Unauthorized`

**Solution:** Check your OpenRouter API key in `.env` and ensure it's valid.

**Error:** `OpenRouterAPIError: HTTP 429: Rate limit exceeded`

**Solution:** The code retries with exponential backoff. If persistent, reduce `max_emails_per_run` or add delays between runs.

#### Tagging Errors

**Error:** `NO [b'[CANNOT] Invalid characters in keyword']`

**Solution:** The server doesn't allow brackets in flag names. The code uses `AIProcessed` (no brackets) by default. Ensure `processed_tag` in config doesn't contain brackets.

**Note:** Custom IMAP flags may not be visible in Thunderbird's "Schlagworte" view if the server doesn't support the KEYWORDS extension. The flags are still applied and searchable via IMAP.

### Debug Mode

Use dry-run mode to preview processing without making changes:

```bash
python main.py process --dry-run
```

This will show:
- Emails that would be processed
- Classification scores that would be assigned
- Notes that would be generated
- All operations without modifying IMAP flags or creating files

### Getting Help

1. Check the logs in `logs/agent.log` for detailed error messages
2. Review the analytics in `logs/analytics.jsonl` for processing statistics
3. Enable debug mode to see detailed operation logs
4. Check the [documentation](docs/) for module-specific details

---

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src
```

### Live Testing

Test IMAP connection and email fetching:

```bash
python scripts/test_imap_live.py
```

Test IMAP flags functionality:

```bash
python scripts/test_imap_flags.py
```

---

## Maintaining Context (For AI Agents and Developers)

> **For AI Agents (Cursor, etc.):**
> 
> **Start here:** [README-AI.md](README-AI.md) - Optimized entry point with complete project structure, architecture, and development context.
> 
> Then:
> 1. Review [pdd.md](pdd.md) for V3 implementation details (current version)
> 2. Run `task-master list` and `task-master next` to see project state/tasks
> 3. Review module docs in `docs/` as needed

> **For Human Developers:**
> 
> 1. Read this README.md for overview
> 2. See [docs/COMPLETE_GUIDE.md](docs/COMPLETE_GUIDE.md) for detailed user guide
> 3. See [docs/MAIN_DOCS.md](docs/MAIN_DOCS.md) for documentation index
> 4. See [docs/v3-migration-guide.md](docs/v3-migration-guide.md) if migrating from V2

*Don't forget: Secrets and configs are in `.env` and `config/config.yaml`. See docs above for details.*

**Note:** 
- **V3** (Foundational Upgrade) is the current production version on `main` branch. See [pdd.md](pdd.md) for V3 implementation details.
- **V4** (Orchestrator) is in development on `v4-orchestrator` branch. See [pdd_V4.md](pdd_V4.md) for V4 implementation details.
- **V1 and V2** are historical versions.

---

## FAQ

**Q: How do I switch AI models?**  
A: Edit `classification.model` in `config/config.yaml`. Supported models: `openai/gpt-3.5-turbo`, `google/gemini-2.5-flash-lite-preview-09-2025`, `openai/gpt-4o-mini`, `anthropic/claude-3-haiku`, etc.

**Q: How do I process a specific email?**  
A: Use `python main.py process --uid <UID>` to process a single email by its UID.

**Q: How do I reprocess an already-processed email?**  
A: Use `python main.py process --uid <UID> --force-reprocess` to ignore the processed tag and reprocess.

**Q: How do I preview processing without making changes?**  
A: Use `python main.py process --dry-run` to see what would happen without modifying IMAP flags or creating files.

**Q: How do I process historical emails?**  
A: Use `python main.py backfill --since 2024-01-01 --until 2024-12-31` to process emails from a date range.

**Q: How do I clean up application flags?**  
A: Use `python main.py cleanup-flags` (requires confirmation) to remove all application-specific IMAP flags.

**Q: Why aren't tags visible in Thunderbird?**  
A: Thunderbird's "Schlagworte" view only shows KEYWORDS extension tags. The flags are still applied and searchable via IMAP. See [docs/imap-keywords-vs-flags.md](docs/imap-keywords-vs-flags.md).

**Q: How do I customize the note format?**  
A: Edit the Jinja2 template at `config/note_template.md.j2` to customize the Markdown note structure.

---

## Development

### Project Structure

```
email-agent/
├── src/                    # Source code
│   ├── cli_v3.py          # V3 CLI interface (click-based)
│   ├── settings.py        # V3 configuration facade
│   ├── config_v3_loader.py # V3 configuration loading
│   ├── orchestrator.py   # V3 pipeline orchestration
│   ├── imap_client.py    # V3 IMAP operations
│   ├── llm_client.py      # V3 LLM API client
│   ├── decision_logic.py  # V3 threshold-based classification
│   ├── note_generator.py  # V3 Jinja2 note generation
│   ├── v3_logger.py       # V3 logging system
│   └── ...                # Additional modules
├── tests/                  # Test suite
├── config/                 # Configuration files
│   ├── config.yaml.example # V3 configuration template
│   └── note_template.md.j2 # Jinja2 note template
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── logs/                   # Log files (gitignored)
├── main.py                 # Entry point (V3)
└── requirements.txt        # Dependencies
```

### Contributing

1. Follow TDD: Write tests first, then implement
2. Update documentation when adding features
3. Follow existing code style and error handling patterns
4. Run tests before committing: `pytest`

---

## License

[Add your license here]

---

> **For AI agents:** Always start with [README-AI.md](README-AI.md) for complete project context, then review the PDD and current tasks before making changes!
