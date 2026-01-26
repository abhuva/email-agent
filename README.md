# Email Agent (Headless AI Email Tagger)

## Overview

An extensible Python CLI agent that connects to IMAP accounts, fetches emails, tags/classifies them via AI (OpenAI-compatible or Google/Gemini via OpenRouter), and logs every step. Built for robust team, audit, and production use with comprehensive error handling and logging.

**Current Status:** 
- **V5 (OAuth Integration)** - OAuth 2.0 authentication for Google and Microsoft accounts
- **V4 (Orchestrator)** - Multi-tenant platform with rules engine, multi-account support, and V4-only CLI
- **V3 (Foundational Upgrade)** - Historical version (superseded by V4)
- **V1 and V2** - Historical versions

**Working Branch:** `main` (current development branch, OAuth integration complete)

---

## Features

### V5 Features (OAuth Integration)
- **OAuth 2.0 Authentication**: Secure token-based authentication for Google and Microsoft accounts
- **Automatic Token Refresh**: Tokens are automatically refreshed before expiry
- **Backward Compatible**: Works alongside password authentication (V4 style)
- **CLI Auth Command**: `python main.py auth --account <name>` for OAuth authentication flow
- **Secure Token Storage**: OAuth tokens stored securely with proper file permissions
- **CSRF Protection**: State parameter validation for OAuth flows
- **Token Management**: Automatic expiry checking with 5-minute buffer

### V4 Features (Production Version)
- **Multi-Account Support**: Process multiple email accounts with isolated state and configuration
- **Score-Based Classification**: Granular importance and spam scores (0-10) instead of rigid categories
- **CLI Controls**: Developer-friendly commands for targeted processing, debugging, and maintenance
  - `python main.py process --account <name>` - Process emails for a specific account
  - `python main.py process --all` - Process all configured accounts
  - `python main.py process --account <name> --uid <ID>` - Process specific email by UID
  - `python main.py process --account <name> --force-reprocess` - Reprocess already-processed emails
  - `python main.py cleanup-flags --account <name>` - Safely remove application-specific IMAP flags
  - `python main.py show-config --account <name>` - Display merged configuration for an account
- **Configuration System**: Default + Override model with deep merge (global config + account-specific overrides)
- **Rules Engine**: 
  - **Blacklist Rules**: Pre-processing rules to drop or record emails without AI processing
  - **Whitelist Rules**: Post-LLM modifiers that boost scores and add tags
- **HTML Content Parsing**: Convert HTML emails to Markdown using `html2text` with automatic fallback to plain text
- **Account Processor**: Isolated per-account processing pipeline with complete state isolation
- **Jinja2 Templating**: Flexible note generation using external template files
- **Modular Architecture**: Clean separation of concerns with dedicated modules for IMAP, LLM, decision logic, and note generation
- **Centralized Logging**: Operational logs with structured context and account lifecycle tracking
- **Threshold-Based Classification**: Configurable thresholds for importance and spam detection
- **Retry Logic**: Robust error handling with exponential backoff for LLM API calls
- **Dry-Run Mode**: Preview processing without making changes
- **Force-Reprocess**: Reprocess already-processed emails for testing and refinement
- **Safety Interlock**: Cost estimation and user confirmation before high-cost operations
- **EmailContext Data Model**: Structured data class for tracking email state through the pipeline

### Historical Versions
- **V3 (Foundational Upgrade)**: Score-based classification, CLI controls, Jinja2 templating (superseded by V4)
- **V2 (Obsidian Integration)**: Obsidian note creation, YAML frontmatter, conditional summarization
- **V1 (Email Tagging)**: Basic IMAP email fetching and AI classification

**Note:** V5 OAuth integration is complete and available on the `v5-oauth` branch. V4 remains the stable production version on the `v4-orchestrator` branch.

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
   # Copy example global configuration
   cp config/config.yaml.example config/config.yaml
   
   # Copy example account configuration
   cp config/accounts/example-account.yaml config/accounts/my-account.yaml
   
   # Copy example environment file
   cp .env.example .env
   ```

4. **Edit configuration files:**
   - Edit `config/config.yaml` with global settings (IMAP defaults, LLM settings, etc.)
   - Edit `config/accounts/my-account.yaml` with account-specific settings (IMAP server, credentials, etc.)
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
# Process emails for a specific account
python main.py process --account work

# Process all configured accounts
python main.py process --all

# Process a specific email by UID (requires account)
python main.py process --account work --uid 12345

# Force reprocess an already-processed email
python main.py process --account work --uid 12345 --force-reprocess

# Preview processing without making changes (dry-run)
python main.py process --account work --dry-run

# Clean up application-specific IMAP flags (with confirmation)
python main.py cleanup-flags --account work

# Display merged configuration for an account
python main.py show-config --account work
```

### OAuth Authentication (V5)

Email Agent now supports OAuth 2.0 authentication for Google and Microsoft accounts, providing a more secure alternative to app passwords.

**Quick Setup:**

1. **Set up OAuth credentials** in Google Cloud Console or Azure Portal
2. **Add credentials to `.env`**:
   ```bash
   # For Google
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   
   # For Microsoft
   MS_CLIENT_ID=your_client_id
   MS_CLIENT_SECRET=your_client_secret
   ```
3. **Configure account** with OAuth:
   ```yaml
   auth:
     method: oauth
     provider: google  # or microsoft
   ```
4. **Authenticate account**:
   ```bash
   python main.py auth --account <account-name>
   ```

**Features:**
- ✅ Secure token-based authentication
- ✅ Automatic token refresh
- ✅ Backward compatible with password authentication
- ✅ Supports Google and Microsoft accounts

**Documentation:**
- [V5 OAuth User Guide](docs/v5-oauth-user-guide.md) - Complete setup instructions
- [V5 OAuth Troubleshooting](docs/v5-oauth-troubleshooting.md) - Troubleshooting guide
- [V5 OAuth Flow](docs/v5-oauth-flow.md) - Technical implementation details

**Example Configurations:**
- `config/accounts/example-google-oauth.yaml` - Google OAuth example
- `config/accounts/example-microsoft-oauth.yaml` - Microsoft OAuth example
- `config/accounts/example-password.yaml` - Password authentication (V4 style)

---

### Command-Line Options

**Main Commands:**
- `process` - Process emails with AI classification and note generation
  - `--account <name>` - Process a specific account (required, mutually exclusive with --all)
  - `--all` - Process all configured accounts (mutually exclusive with --account)
  - `--uid <ID>` - Process a specific email by UID (requires --account)
  - `--force-reprocess` - Ignore processed_tag and reprocess email
  - `--dry-run` - Preview processing without making changes
  - `--max-emails <N>` - Maximum number of emails to process
  - `--debug-prompt` - Write classification prompt to debug file
- `cleanup-flags` - Remove application-specific IMAP flags (requires confirmation)
  - `--account <name>` - Account name (required)
  - `--dry-run` - Preview which flags would be removed
- `show-config` - Display merged configuration for an account
  - `--account <name>` - Account name (required)
  - `--format yaml|json` - Output format (default: yaml)
  - `--with-sources` - Include source fields in JSON output
  - `--no-highlight` - Disable highlighting of overridden values
- `auth` - Initiate OAuth 2.0 authentication flow (V5)
  - `--account <name>` - Account name to authenticate (required)
  - Requires OAuth credentials in `.env` (GOOGLE_CLIENT_ID/SECRET or MS_CLIENT_ID/SECRET)
  - Account must be configured with `auth.method='oauth'` in account config

**Global Options:**
- `--config-dir <PATH>` - Base directory for configuration files (default: config)
- `--log-level DEBUG|INFO|WARNING|ERROR` - Set logging level (default: INFO)
- `--version` - Show program version
- `--help` - Show help message

---

## Configuration

V4 uses a multi-account configuration system with global defaults and account-specific overrides. Configuration is stored in two places:

1. **Global Configuration** (`config/config.yaml`) - Default settings for all accounts
2. **Account-Specific Configuration** (`config/accounts/<account-name>.yaml`) - Overrides for specific accounts

### Global Configuration File (`config/config.yaml`)

The global configuration file contains default settings that apply to all accounts unless overridden:

```yaml
# IMAP Server Configuration (defaults - can be overridden per account)
imap:
  port: 143                            # IMAP port (143 for STARTTLS, 993 for SSL)
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

### Account-Specific Configuration (`config/accounts/<account-name>.yaml`)

Each account has its own configuration file that can override global settings:

**Password Authentication (V4 style):**
```yaml
# Account-specific IMAP settings (overrides global defaults)
imap:
  server: 'imap.example.com'          # IMAP server hostname (required per account)
  username: 'your-email@example.com'   # Email account username (required per account)
  password_env: 'IMAP_PASSWORD'        # Environment variable name containing IMAP password

# Authentication (optional - defaults to password if not specified)
auth:
  method: password

# Account-specific paths (overrides global defaults)
paths:
  obsidian_vault: '/path/to/account/vault'  # Account-specific Obsidian vault
```

**OAuth Authentication (V5):**
```yaml
imap:
  server: 'imap.gmail.com'            # IMAP server hostname
  username: 'your-email@gmail.com'    # Email account username

# OAuth 2.0 authentication
auth:
  method: oauth
  provider: google  # or 'microsoft'

paths:
  obsidian_vault: '/path/to/account/vault'
```

**Note:** Account-specific configs only need to include values that differ from global defaults. The V4 configuration system uses deep merge to combine global and account-specific settings.

See `config/accounts/example-account.yaml` for a complete example.

### Environment Variables (`.env`)

The `.env` file contains sensitive credentials:

**Password Authentication:**
```bash
IMAP_PASSWORD=your-imap-password-here
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**OAuth Authentication (V5):**
```bash
# Google OAuth (for Google accounts)
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Microsoft OAuth (for Microsoft/Outlook accounts)
MS_CLIENT_ID=your_microsoft_client_id
MS_CLIENT_SECRET=your_microsoft_client_secret

# Still required for LLM API
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**Important:** Never commit `.env` to version control! Use `.env.example` as a template.

### AI Prompt File (`config/prompt.md`)

The prompt file contains the instructions sent to the AI for email classification. It should be a Markdown file with YAML frontmatter. See `config/prompt.md.example` for a template.

**See Also:** [V4 Configuration Reference](docs/v4-configuration-reference.md) for complete configuration documentation.

---

## How It Works

### V5 Workflow (OAuth Integration)
V5 adds OAuth 2.0 authentication while maintaining full backward compatibility with V4 password authentication. The authentication flow is handled transparently by the `IMAPClient` and authentication strategies.

**OAuth Authentication Flow:**
1. User runs `python main.py auth --account <name>` for OAuth accounts
2. OAuth flow opens browser for user consent
3. Authorization code exchanged for access/refresh tokens
4. Tokens stored securely in `credentials/` directory
5. Tokens automatically refreshed before expiry during IMAP operations

**Processing Flow:** Same as V4 (see below), with OAuth authentication instead of password authentication for OAuth-configured accounts.

### V4 Workflow (Production Version)

1. **Configuration Loading**: Loads global config and account-specific overrides using `ConfigLoader`
2. **Account Processing**: For each account (or specified account):
   a. **Rules Engine**: Applies blacklist rules to filter emails before processing
   b. **Email Fetching**: Connects to IMAP server and fetches emails based on configured query (excluding processed emails)
   c. **Content Parsing**: Converts HTML emails to Markdown using `html2text` with fallback to plain text
   d. **AI Classification**: Sends email content to LLM API, receives JSON with `importance_score` and `spam_score` (0-10)
   e. **Rules Engine**: Applies whitelist rules to boost scores and add tags
   f. **Decision Logic**: Applies threshold-based classification:
      - If `importance_score >= importance_threshold` → marks as important
      - If `spam_score >= spam_threshold` → marks as spam
   g. **Note Generation**: Uses Jinja2 template to generate Markdown note with:
      - YAML frontmatter (metadata, scores, processing info)
      - Email body (converted from HTML/plain text to Markdown)
   h. **File Creation**: Saves note to Obsidian vault directory
   i. **Tagging**: Tags email with `AIProcessed` flag to prevent reprocessing
   j. **Logging**: Records to operational log with structured context and account lifecycle tracking
3. **Summary**: Displays processing summary for all accounts

### Complete Processing Flow (V4)

```
Start → Load Global Config → Load Account Configs → For each account:
  ↓
Account Processor:
  ↓
Blacklist Rules → Filter Emails
  ↓
Connect IMAP → Fetch Emails
  ↓
For each email:
  ↓
Parse HTML → Markdown → Truncate body → Send to LLM API → Receive JSON scores
  ↓
Whitelist Rules → Apply thresholds → Determine classification
  ↓
Render Jinja2 template → Generate Markdown note
  ↓
Save to Obsidian vault → Tag email (AIProcessed)
  ↓
Log with context → Next email
  ↓
Account Summary → Next account
  ↓
Overall Summary → Exit
```

### Historical Workflows

- **V3**: Single-account processing with settings facade (superseded by V4)
- **V2**: Used keyword-based classification (urgent/neutral/spam) and conditional summarization
- **V1**: Basic email tagging with simple AI classification

---

## Documentation

### V5 OAuth Documentation
- **[V5 OAuth User Guide](docs/v5-oauth-user-guide.md)** — Complete OAuth setup and usage guide
- **[V5 OAuth Troubleshooting](docs/v5-oauth-troubleshooting.md)** — Detailed troubleshooting for OAuth issues
- **[V5 OAuth Flow](docs/v5-oauth-flow.md)** — Technical OAuth flow implementation
- **[V5 Token Manager](docs/v5-token-manager.md)** — Token storage and refresh system
- **[V5 Google Provider](docs/v5-google-provider.md)** — Google OAuth provider implementation
- **[V5 Microsoft Provider](docs/v5-microsoft-provider.md)** — Microsoft OAuth provider implementation
- **[V5 Auth Interfaces](docs/v5-auth-interfaces.md)** — Authentication interfaces and protocols
- **[V5 Auth Strategies](docs/v5-auth-strategies.md)** — Authentication strategy pattern implementation

### V4 Documentation (Production Version)
- **[Product Design Doc V4 (PDD)](pdd_V4.md)** — V4 project strategy and requirements (✅ Complete)
- **[V4 CLI Usage Guide](docs/v4-cli-usage.md)** — Complete command-line interface reference
- **[V4 Configuration System](docs/v4-configuration.md)** — Multi-tenant configuration with account-specific overrides
- **[V4 Configuration Reference](docs/v4-configuration-reference.md)** — Complete configuration reference with all options
- **[V4 Rules Engine](docs/v4-rules-engine.md)** — Blacklist and whitelist rules for email filtering
- **[V4 Account Processor](docs/v4-account-processor.md)** — Isolated per-account email processing pipeline
- **[V4 Master Orchestrator](docs/v4-orchestrator.md)** — Multi-account orchestrator with CLI integration
- **[V4 Content Parser](docs/v4-content-parser.md)** — HTML to Markdown conversion with fallback
- **[V4 Models](docs/v4-models.md)** — EmailContext data class for pipeline state tracking
- **[V4 Installation & Setup](docs/v4-installation-setup.md)** — Installation, setup, and initial configuration guide
- **[V4 Quick Start](docs/v4-quick-start.md)** — Minimal setup guide to get V4 running quickly
- **[V4 Migration Guide](docs/v4-migration-guide.md)** — Step-by-step guide for migrating from V3 to V4
- **[V4 Troubleshooting](docs/v4-troubleshooting.md)** — Comprehensive troubleshooting guide for common V4 issues
- **[Scoring Criteria](docs/scoring-criteria.md)** — Email scoring system

### V5 OAuth Documentation
- **[V5 OAuth User Guide](docs/v5-oauth-user-guide.md)** — Complete OAuth setup and usage guide
- **[V5 OAuth Troubleshooting](docs/v5-oauth-troubleshooting.md)** — Detailed troubleshooting for OAuth issues
- **[V5 OAuth Flow](docs/v5-oauth-flow.md)** — Technical OAuth flow implementation
- **[V5 Token Manager](docs/v5-token-manager.md)** — Token storage and refresh system
- **[V5 Google Provider](docs/v5-google-provider.md)** — Google OAuth provider implementation
- **[V5 Microsoft Provider](docs/v5-microsoft-provider.md)** — Microsoft OAuth provider implementation
- **[V5 Auth Interfaces](docs/v5-auth-interfaces.md)** — Authentication interfaces and protocols
- **[V5 Auth Strategies](docs/v5-auth-strategies.md)** — Authentication strategy pattern implementation

### Historical Documentation
- **[Product Design Doc V3 (PDD)](pdd.md)** — V3 project strategy (historical, superseded by V4)
- **[V3 Configuration Guide](docs/v3-configuration.md)** — V3 configuration system (historical)
- **[V3 CLI Guide](docs/v3-cli.md)** — V3 command-line interface (historical)
- **[V3 Migration Guide](docs/v3-migration-guide.md)** — Migrating from V2 to V3 (historical)

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

### Unit and Integration Tests

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

### V5 OAuth End-to-End Testing

V5 includes comprehensive OAuth end-to-end tests that validate OAuth authentication flows:

```bash
# Run V5 OAuth E2E tests (requires OAuth credentials)
pytest tests/test_e2e_oauth.py -v -m e2e_oauth

# Run V5 backward compatibility tests (password auth)
pytest tests/test_e2e_oauth_backward_compat.py -v

# Run OAuth flow unit tests
pytest tests/test_oauth_flow.py -v
```

### V4 End-to-End Testing

V4 includes comprehensive end-to-end tests that validate the complete email processing pipeline using real email accounts:

- **Test Account Setup**: See `docs/v4-e2e-test-setup.md` for setting up test email accounts
- **Test Environment**: See `docs/v4-e2e-test-environment.md` for test environment configuration
- **Test Scenarios**: See `docs/v4-e2e-test-scenarios.md` for comprehensive test scenarios
- **Execution Guide**: See `docs/v4-e2e-test-execution.md` for running and analyzing E2E tests

Run V4 E2E tests:

```bash
# Run all V4 E2E tests (requires test account credentials)
pytest tests/test_e2e_v4_pipeline.py -v -m e2e_v4

# Skip E2E tests if credentials not available
pytest tests/test_e2e_v4_pipeline.py -v -m "not e2e_v4"
```

---

## Maintaining Context (For AI Agents and Developers)

> **For AI Agents (Cursor, etc.):**
> 
> **Start here:** [README-AI.md](README-AI.md) - Optimized entry point with complete project structure, architecture, and development context.
> 
> Then:
> 1. Review [pdd_v5.md](pdd_v5.md) for V5 OAuth implementation details (current development)
> 2. Review [pdd_V4.md](pdd_V4.md) for V4 implementation details (production version)
> 3. Run `task-master list` and `task-master next` to see project state/tasks
> 4. Review module docs in `docs/` as needed

> **For Human Developers:**
> 
> 1. Read this README.md for overview
> 2. See [docs/COMPLETE_GUIDE.md](docs/COMPLETE_GUIDE.md) for detailed user guide
> 3. See [docs/MAIN_DOCS.md](docs/MAIN_DOCS.md) for documentation index
> 4. See [docs/v5-oauth-user-guide.md](docs/v5-oauth-user-guide.md) for OAuth setup (V5)
> 5. See [docs/v4-migration-guide.md](docs/v4-migration-guide.md) if migrating from V3

*Don't forget: Secrets and configs are in `.env`, `config/config.yaml` (global), and `config/accounts/*.yaml` (account-specific). OAuth tokens are stored in `credentials/` directory. See docs above for details.*

---

## FAQ

**Q: How do I switch AI models?**  
A: Edit `classification.model` in `config/config.yaml`. Supported models: `openai/gpt-3.5-turbo`, `google/gemini-2.5-flash-lite-preview-09-2025`, `openai/gpt-4o-mini`, `anthropic/claude-3-haiku`, etc.

**Q: How do I process emails for an account?**  
A: Use `python main.py process --account <name>` to process emails for a specific account, or `python main.py process --all` to process all accounts.

**Q: How do I process a specific email?**  
A: Use `python main.py process --account <name> --uid <UID>` to process a single email by its UID.

**Q: How do I reprocess an already-processed email?**  
A: Use `python main.py process --account <name> --uid <UID> --force-reprocess` to ignore the processed tag and reprocess.

**Q: How do I preview processing without making changes?**  
A: Use `python main.py process --account <name> --dry-run` to see what would happen without modifying IMAP flags or creating files.

**Q: How do I clean up application flags?**  
A: Use `python main.py cleanup-flags --account <name>` (requires confirmation) to remove all application-specific IMAP flags for an account.

**Q: How do I view the merged configuration for an account?**  
A: Use `python main.py show-config --account <name>` to display the merged configuration (global + account-specific overrides).

**Q: How do I set up OAuth authentication?**  
A: See [V5 OAuth User Guide](docs/v5-oauth-user-guide.md) for complete setup instructions. Quick steps: 1) Create OAuth credentials in Google Cloud Console or Azure Portal, 2) Add credentials to `.env`, 3) Configure account with `auth.method='oauth'`, 4) Run `python main.py auth --account <name>`.

**Q: Can I use both OAuth and password authentication?**  
A: Yes! OAuth and password authentication can coexist. Configure each account with the appropriate `auth.method` in its configuration file.

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
│   ├── cli_v4.py          # V4 CLI interface (click-based, includes V5 auth command)
│   ├── orchestrator.py    # V4 MasterOrchestrator (multi-account)
│   ├── account_processor.py # V4 Account Processor (per-account pipeline)
│   ├── config_loader.py   # V4 configuration loader with deep merge
│   ├── config_schema.py   # V4 configuration schema validation (includes V5 OAuth auth block)
│   ├── rules.py           # V4 rules engine (blacklist/whitelist)
│   ├── content_parser.py  # V4 HTML to Markdown parser
│   ├── models.py          # V4 EmailContext data class
│   ├── imap_client.py     # IMAP operations (supports OAuth authentication)
│   ├── llm_client.py      # LLM API client with retry logic
│   ├── decision_logic.py  # Threshold-based classification
│   ├── note_generator.py  # Jinja2 note generation
│   ├── auth/               # V5 OAuth authentication module
│   │   ├── interfaces.py   # Authentication protocols and OAuth provider interfaces
│   │   ├── oauth_flow.py   # OAuth 2.0 flow orchestration for CLI
│   │   ├── token_manager.py # OAuth token storage, loading, and refresh
│   │   ├── strategies.py   # Password and OAuth authenticator implementations
│   │   └── providers/      # OAuth provider implementations
│   │       ├── google.py   # Google OAuth provider
│   │       └── microsoft.py # Microsoft OAuth provider
│   └── ...                # Additional modules
├── tests/                  # Test suite
│   ├── test_e2e_oauth.py  # V5 OAuth end-to-end tests
│   ├── test_oauth_flow.py  # V5 OAuth flow tests
│   └── ...                # Additional tests
├── config/                 # Configuration files
│   ├── config.yaml.example # Global configuration template
│   ├── accounts/           # Account-specific configurations
│   │   ├── example-account.yaml
│   │   ├── example-google-oauth.yaml    # V5 Google OAuth example
│   │   ├── example-microsoft-oauth.yaml # V5 Microsoft OAuth example
│   │   └── example-password.yaml        # V4 password auth example
│   └── note_template.md.j2 # Jinja2 note template
├── credentials/            # OAuth token storage (V5, gitignored)
│   └── *.json             # OAuth tokens per account (0600 permissions)
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── logs/                   # Log files (gitignored)
├── main.py                 # Entry point (V4/V5)
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

> **For AI agents:** Always start with [README-AI.md](README-AI.md) for complete project context, then review the PDD V5 (current development) or PDD V4 (production) and current tasks before making changes!

**Note:** 
- **V5** (OAuth Integration) is complete on the `v5-oauth` branch. See [pdd_v5.md](pdd_v5.md) for V5 implementation details.
- **V4** (Orchestrator) is the current production version on the `v4-orchestrator` branch. See [pdd_V4.md](pdd_V4.md) for V4 implementation details.
- **V3** (Foundational Upgrade) is a historical version that has been superseded by V4. See [pdd.md](pdd.md) for historical V3 implementation details.
- **V1 and V2** are historical versions.
