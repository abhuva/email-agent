# Email Agent (Headless AI Email Tagger)

## Overview

An extensible Python CLI agent that connects to IMAP accounts, fetches emails, tags/classifies them via AI (OpenAI-compatible or Google/Gemini via OpenRouter), and logs every step. Built for robust team, audit, and production use with comprehensive error handling and logging.

---

## Features

- **IMAP Email Fetching**: Secure connection to IMAP servers with STARTTLS/SSL support
- **AI Classification**: Uses OpenRouter API to classify emails as Urgent, Neutral, or Spam
- **Non-Destructive Tagging**: Adds IMAP flags to emails without modifying content
- **Comprehensive Logging**: File and console logging with analytics summaries
- **Configurable Limits**: Control processing limits per run and email body truncation
- **Error Handling**: Robust error handling with retry logic and graceful degradation
- **TDD-Based**: Test-driven development with comprehensive test coverage

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
# Run with default configuration (single batch)
python main.py

# Process maximum 5 emails
python main.py --limit 5

# Enable debug mode
python main.py --debug

# Run continuously (not single batch)
python main.py --continuous

# Use custom config file
python main.py --config custom-config.yaml
```

### Command-Line Options

```
--config CONFIG       Path to YAML configuration file (default: config/config.yaml)
--env ENV             Path to .env secrets file (default: .env)
--debug               Enable debug mode (equivalent to --log-level DEBUG)
--log-level LEVEL     Set logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
--limit N             Override max_emails_per_run from config (PDD AC 6)
--continuous          Run continuously instead of single batch (default: single batch)
--version             Show program version
--help                Show help message
```

---

## Configuration

### Configuration File (`config/config.yaml`)

The main configuration file contains all operational parameters:

```yaml
imap:
  server: 'imap.example.com'          # IMAP server hostname
  port: 993                            # Port (993 for SSL, 143 for STARTTLS)
  username: 'your-email@example.com'   # Email address
  password_env: 'IMAP_PASSWORD'        # Environment variable name

prompt_file: 'config/prompt.md'        # Path to AI prompt file

tag_mapping:                           # AI keyword → IMAP tag mapping
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'

processed_tag: 'AIProcessed'           # Tag for processed emails
max_body_chars: 4000                  # Max characters sent to AI
max_emails_per_run: 15                # Max emails per run

log_file: 'logs/agent.log'            # Log file path
log_level: 'INFO'                      # Logging level
analytics_file: 'logs/analytics.jsonl' # Analytics file path

openrouter:
  api_key_env: 'OPENROUTER_API_KEY'   # Environment variable name
  api_url: 'https://openrouter.ai/api/v1'
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # Optional, defaults to gpt-3.5-turbo
```

See `config/config.yaml.example` for a complete example with comments.

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

1. **Email Fetching**: Connects to IMAP server and fetches unprocessed emails (excluding those with `AIProcessed` flag)
2. **AI Processing**: Sends email content (truncated to `max_body_chars`) to OpenRouter API for classification
3. **Tagging**: Maps AI response keywords (`urgent`, `neutral`, `spam`) to IMAP tags and applies them
4. **Logging**: Logs all operations to file and console, generates analytics summaries
5. **Error Handling**: Isolates per-email errors, retries transient failures, marks failed emails

### Processing Flow

```
Start → Load Config → Connect IMAP → Fetch Emails
  ↓
For each email:
  ↓
Truncate body → Send to AI → Extract keyword → Map to tag
  ↓
Apply IMAP flags (tag + AIProcessed) → Log result
  ↓
Generate analytics summary → Exit
```

---

## Documentation

- **[Product Design Doc (PDD)](pdd.md)** — Project strategy, requirements, roadmap
- **[Logging System](docs/logging-system.md)** — Logger, analytics, config, test patterns
- **[IMAP Email Fetching](docs/imap-fetching.md)** — IMAP workflow, error handling, FLAGS vs KEYWORDS
- **[Prompt Loader](docs/prompts.md)** — How AI prompts are loaded and managed
- **[Main Documentation Map](docs/MAIN_DOCS.md)** — Centralized documentation index
- **[Task Master Workflow](README-task-master.md)** — AI-driven task/project management

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

Enable debug mode for detailed logging:

```bash
python main.py --debug
# or
python main.py --log-level DEBUG
```

This will show:
- Full email content sent to AI
- Raw AI responses
- Detailed IMAP operations
- All error stack traces

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

> To restart after a break, or for Cursor AI:

1. Open this `README.md` and [pdd.md](pdd.md)
2. Run:
   ```bash
   task-master list
   task-master next
   ```
   to see project state/tasks
3. Review the doc links above for any system/module orientation

*Don't forget: Secrets and configs are in `.env` and `config/config.yaml`. See docs above for details.*

---

## FAQ

**Q: How do I switch AI models?**  
A: Edit `openrouter.model` in `config/config.yaml`. Supported models: `openai/gpt-3.5-turbo`, `google/gemini-2.5-flash-lite-preview-09-2025`, `openai/gpt-4o-mini`, etc.

**Q: Can I process more than `max_emails_per_run`?**  
A: Use the `--limit N` flag to override the config value, or use `--continuous` mode to process in batches.

**Q: Why aren't tags visible in Thunderbird?**  
A: Thunderbird's "Schlagworte" view only shows KEYWORDS extension tags. The flags are still applied and searchable via IMAP. See [docs/imap-keywords-vs-flags.md](docs/imap-keywords-vs-flags.md).

**Q: How do I restart the agent after a break?**  
A: Simply run `python main.py` again. The agent automatically excludes emails with the `AIProcessed` flag.

**Q: What if an email fails to process?**  
A: Failed emails are marked with `AIProcessingFailed` flag and logged. The agent continues processing other emails.

**Q: How do I reset processed emails?**  
A: Remove the `AIProcessed` flag from emails via your email client or IMAP command. The agent will then reprocess them.

---

## Development

### Project Structure

```
email-agent/
├── src/                    # Source code
│   ├── cli.py             # CLI interface
│   ├── config.py          # Configuration management
│   ├── imap_connection.py # IMAP operations
│   ├── openrouter_client.py # OpenRouter API client
│   ├── main_loop.py       # Main processing loop
│   └── ...
├── tests/                  # Test suite
├── config/                 # Configuration files
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── logs/                   # Log files (gitignored)
├── main.py                 # Entry point
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

> **For AI agents:** Always reread this file and the PDD before making code changes or automation decisions!
