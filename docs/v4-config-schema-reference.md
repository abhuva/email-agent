# V4 Configuration Schema Reference

**Status:** Documentation for Task 14.1  
**Purpose:** Reference document defining all configuration settings, their types, defaults, and relationships  
**PDD Reference:** [pdd_V4.md](pdd_V4.md) Section 3.1

---

## Overview

This document defines the complete configuration schema for V4, including:
- All configuration domains and their settings
- Data types and default values
- Global vs. account-level settings
- Precedence rules
- Directory structure and file naming conventions

---

## Directory Structure

```
config/
├── config.yaml              # Global/base configuration (REQUIRED)
├── config.yaml.example      # Template for global configuration (this file)
├── accounts/                 # Account-specific configuration files (OPTIONAL)
│   ├── example-account.yaml # Example account configuration template
│   ├── work.yaml            # Account-specific overrides (user-created)
│   └── personal.yaml        # Account-specific overrides (user-created)
├── blacklist.yaml           # Global blacklist rules (OPTIONAL)
└── whitelist.yaml           # Global whitelist rules (OPTIONAL)
```

### File Naming Conventions

- **Global config:** `config.yaml` (required), `config.yaml.example` (template)
- **Account configs:** `<account-id>.yaml` or `<tenant-name>.yaml`
  - Examples: `work.yaml`, `personal.yaml`, `client-xyz.yaml`
  - Must be valid YAML filenames (no special characters, spaces, or path traversal)
- **Rules files:** `blacklist.yaml`, `whitelist.yaml` (fixed names)

---

## Configuration Domains

### 1. IMAP Configuration (`imap`)

**Scope:** Global (can be overridden per account)  
**Required:** Yes

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `server` | `str` | Yes | - | IMAP server hostname |
| `port` | `int` | No | `143` | IMAP port (143 for STARTTLS, 993 for SSL) |
| `username` | `str` | Yes | - | Email account username |
| `password_env` | `str` | No | `IMAP_PASSWORD` | Environment variable name containing IMAP password |
| `query` | `str` | No | `ALL` | IMAP search query (e.g., 'ALL', 'UNSEEN', 'SENTSINCE 01-Jan-2024') |
| `processed_tag` | `str` | No | `AIProcessed` | IMAP flag name for processed emails |
| `application_flags` | `list[str]` | No | `['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']` | Application-specific flags for cleanup |

**Constraints:**
- `port`: 1-65535
- `server`, `username`, `password_env`, `query`, `processed_tag`: min_length=1
- `application_flags`: min_length=1 (at least one flag required)

**Account Override Behavior:**
- Commonly overridden: `server`, `port`, `username`, `password_env`
- Rarely overridden: `query`, `processed_tag`, `application_flags`

---

### 2. Paths Configuration (`paths`)

**Scope:** Global (can be overridden per account)  
**Required:** Yes

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `template_file` | `str` | No | `config/note_template.md.j2` | Jinja2 template for generating Markdown notes |
| `obsidian_vault` | `str` | Yes | - | Obsidian vault directory (must exist) |
| `log_file` | `str` | No | `logs/agent.log` | Unstructured operational log file |
| `analytics_file` | `str` | No | `logs/analytics.jsonl` | Structured analytics log (JSONL format) |
| `changelog_path` | `str` | No | `logs/email_changelog.md` | Changelog/audit log file |
| `prompt_file` | `str` | No | `config/prompt.md` | LLM prompt file for email classification |
| `summarization_prompt_path` | `str \| None` | No | `None` | Optional: Prompt file for summarization |

**Constraints:**
- All string fields: min_length=1
- `summarization_prompt_path`: Can be `None` (optional feature)

**Account Override Behavior:**
- Commonly overridden: `obsidian_vault` (different vault per account)
- Rarely overridden: `template_file`, `log_file`, `analytics_file`, `changelog_path`, `prompt_file`

---

### 3. OpenRouter Configuration (`openrouter`)

**Scope:** Global (can be overridden per account)  
**Required:** Yes

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `api_key_env` | `str` | No | `OPENROUTER_API_KEY` | Environment variable name containing API key |
| `api_url` | `str` | No | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |

**Constraints:**
- All string fields: min_length=1

**Account Override Behavior:**
- Rarely overridden: Usually shared across accounts
- Can be overridden for different API keys per account (advanced use case)

---

### 4. Classification Configuration (`classification`)

**Scope:** Global (can be overridden per account)  
**Required:** Yes

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | `str` | Yes | - | LLM model to use for classification (e.g., 'google/gemini-2.5-flash-lite-preview-09-2025') |
| `temperature` | `float` | No | `0.2` | LLM temperature (0.0-2.0, lower = more deterministic) |
| `retry_attempts` | `int` | No | `3` | Number of retry attempts for failed API calls |
| `retry_delay_seconds` | `int` | No | `5` | Initial delay between retries (exponential backoff) |
| `cost_per_1k_tokens` | `float` | No | - | Cost per 1000 tokens (for cost estimation) |
| `cost_per_email` | `float` | No | - | Direct cost per email (overrides token-based pricing) |

**Constraints:**
- `temperature`: 0.0-2.0
- `retry_attempts`: min=1
- `retry_delay_seconds`: min=1
- `model`: min_length=1

**Account Override Behavior:**
- Commonly overridden: `model`, `temperature` (different models/behavior per account)
- Rarely overridden: `retry_attempts`, `retry_delay_seconds`
- Cost fields: Usually set globally, can be overridden for account-specific pricing

**Note:** Either `cost_per_1k_tokens` or `cost_per_email` should be set for safety interlock cost estimation.

---

### 5. Summarization Configuration (`summarization`)

**Scope:** Global (can be overridden per account)  
**Required:** Yes

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | `str` | Yes | - | LLM model to use for summarization (can be different from classification model) |
| `temperature` | `float` | No | `0.3` | LLM temperature (0.0-2.0, typically higher for summarization) |
| `retry_attempts` | `int` | No | `3` | Number of retry attempts for failed API calls |
| `retry_delay_seconds` | `int` | No | `5` | Initial delay between retries (exponential backoff) |

**Constraints:**
- `temperature`: 0.0-2.0
- `retry_attempts`: min=1
- `retry_delay_seconds`: min=1
- `model`: min_length=1

**Account Override Behavior:**
- Rarely overridden: Usually shared across accounts
- Can be overridden for account-specific summarization models

---

### 6. Processing Configuration (`processing`)

**Scope:** Global (can be overridden per account)  
**Required:** Yes

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `importance_threshold` | `int` | No | `8` | Minimum importance score (0-10) to mark email as important |
| `spam_threshold` | `int` | No | `5` | Maximum spam score (0-10) to consider email as spam |
| `max_body_chars` | `int` | No | `4000` | Maximum characters to send to LLM (truncates longer emails) |
| `max_emails_per_run` | `int` | No | `15` | Maximum number of emails to process per execution |
| `summarization_tags` | `list[str] \| None` | No | `None` | Optional: Tags generated when importance_score >= threshold |

**Constraints:**
- `importance_threshold`: 0-10
- `spam_threshold`: 0-10
- `max_body_chars`: min=1
- `max_emails_per_run`: min=1
- `summarization_tags`: If list, items must be strings

**Account Override Behavior:**
- Commonly overridden: `importance_threshold`, `spam_threshold`, `max_emails_per_run` (different thresholds per account)
- Rarely overridden: `max_body_chars`, `summarization_tags`

---

### 7. Authentication Configuration (`auth`)

**Scope:** Account-specific (optional, defaults to password authentication)  
**Required:** No (optional section)  
**V5 Feature:** OAuth 2.0 support for Google and Microsoft accounts

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `method` | `str` | No | `'password'` | Authentication method: `'password'` or `'oauth'` |
| `provider` | `str \| None` | Conditional | `None` | OAuth provider: `'google'` or `'microsoft'` (required when `method='oauth'`) |
| `password_env` | `str \| None` | Conditional | `None` | Environment variable name containing IMAP password (required when `method='password'`) |
| `oauth` | `dict \| None` | Conditional | `None` | OAuth 2.0 configuration (required when `method='oauth'`) |

**OAuth Configuration (`oauth` sub-section):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `client_id` | `str` | Yes | - | OAuth 2.0 client ID from provider |
| `client_secret_env` | `str` | Yes | - | Environment variable name containing OAuth client secret |
| `redirect_uri` | `str` | Yes | - | OAuth redirect URI (e.g., `'http://localhost:8080/callback'`) |
| `scopes` | `list[str]` | No | `[]` | OAuth scopes (e.g., `['https://mail.google.com/']` for Google) |
| `access_type` | `str` | No | `'offline'` | OAuth access type (Google-specific: `'offline'` for refresh tokens) |
| `include_granted_scopes` | `bool` | No | `true` | Include previously granted scopes (Google-specific) |

**Constraints:**
- `method`: Must be `'password'` or `'oauth'`
- `provider`: Must be `'google'` or `'microsoft'` (only valid when `method='oauth'`)
- `password_env`: Required when `method='password'`, ignored when `method='oauth'`
- `provider`: Required when `method='oauth'`, ignored when `method='password'`
- `oauth.client_id`, `oauth.client_secret_env`, `oauth.redirect_uri`: Required when `method='oauth'`
- `oauth.scopes`: If provided, must be a list of strings
- `oauth.access_type`: Must be a string (typically `'offline'` for Google)
- `oauth.include_granted_scopes`: Must be a boolean

**Conditional Validation Rules:**
- **Password Method:** When `method='password'`, `password_env` is required. `provider` and `oauth` are ignored.
- **OAuth Method:** When `method='oauth'`, `provider` is required and must be `'google'` or `'microsoft'`. `oauth` configuration with `client_id`, `client_secret_env`, and `redirect_uri` is required. `password_env` is ignored.

**Backward Compatibility:**
- If `auth` section is missing, defaults to `method='password'` and uses `imap.password_env` from IMAP configuration
- Existing V4 configurations without `auth` block continue to work (deprecation warning logged)
- Migration: Add explicit `auth` block with `method='password'` and `password_env` for future compatibility

**Account Override Behavior:**
- Always account-specific: Each account can have different authentication method
- Commonly used: OAuth for Google/Microsoft accounts, password for other providers
- OAuth configuration is account-specific (different client IDs/secrets per account)

**Example Configurations:**

```yaml
# Password authentication (default, backward compatible)
auth:
  method: password
  password_env: IMAP_PASSWORD

# Google OAuth authentication
auth:
  method: oauth
  provider: google
  oauth:
    client_id: your-google-client-id
    client_secret_env: GOOGLE_CLIENT_SECRET
    redirect_uri: http://localhost:8080/callback
    scopes:
      - https://mail.google.com/
    access_type: offline
    include_granted_scopes: true

# Microsoft OAuth authentication
auth:
  method: oauth
  provider: microsoft
  oauth:
    client_id: your-microsoft-client-id
    client_secret_env: MS_CLIENT_SECRET
    redirect_uri: http://localhost:8080/callback
    scopes:
      - https://outlook.office.com/IMAP.AccessAsUser.All
      - https://outlook.office.com/User.Read
      - offline_access
```

**Note:** This is a V5 feature. For OAuth setup instructions, see the OAuth integration documentation.

---

### 8. Safety Interlock Configuration (`safety_interlock`)

**Scope:** Global (can be overridden per account)  
**Required:** No (optional section)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | `bool` | No | `true` | Enable/disable safety interlock |
| `cost_threshold` | `float` | No | `0.10` | Cost threshold in currency units (operations below this may skip confirmation) |
| `skip_confirmation_below_threshold` | `bool` | No | `false` | Skip confirmation if cost is below threshold |
| `average_tokens_per_email` | `int` | No | `2000` | Average tokens per email for cost estimation |
| `currency` | `str` | No | `'$'` | Currency symbol for cost display |

**Constraints:**
- `cost_threshold`: Should be >= 0.0
- `average_tokens_per_email`: Should be > 0
- `currency`: Typically single character or short string

**Account Override Behavior:**
- Rarely overridden: Usually set globally
- Can be overridden for account-specific cost thresholds or currency

**Note:** This section is optional. If not present, safety interlock defaults to enabled with default values.

---

## Merge Strategy

When loading an account configuration, the system performs a **deep merge**:

1. **Dictionaries:** Deep merged recursively
   - Keys in account config overwrite keys in global config
   - Nested dictionaries are merged recursively
   - Example: `imap.port` in account config overrides `imap.port` in global config

2. **Lists:** Completely replaced
   - Lists in account config replace lists in global config (no concatenation)
   - Example: `application_flags` in account config completely replaces global `application_flags`

3. **Primitives:** Overwritten
   - String, int, float, bool values in account config replace values in global config
   - Example: `processing.importance_threshold` in account config replaces global value

### Precedence Rules

1. **Account config** > **Global config** (account overrides always win)
2. **Environment variables** > **Config files** (if environment variable overrides are enabled)
3. **Rules files** (`blacklist.yaml`, `whitelist.yaml`) are **additive** (not merged, loaded separately)

---

## Rules Schema

### Blacklist Rules (`config/blacklist.yaml`)

**Purpose:** Pre-processing rules applied BEFORE AI processing  
**Structure:** List of rule objects

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trigger` | `str` | Yes | Field to match: `"sender"`, `"subject"`, or `"domain"` |
| `value` | `str` | Yes | Value to match (exact match for sender/subject, domain match for domain) |
| `action` | `str` | Yes | Action to take: `"drop"` (skip entirely) or `"record"` (generate raw markdown without AI) |

**Evaluation:**
- Rules are evaluated in order (first match wins)
- Whitelist rules are checked before blacklist rules (whitelist takes precedence)
- If no match, email proceeds to normal processing

---

### Whitelist Rules (`config/whitelist.yaml`)

**Purpose:** Post-processing rules applied AFTER AI processing  
**Structure:** List of rule objects

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trigger` | `str` | Yes | Field to match: `"sender"`, `"subject"`, or `"domain"` |
| `value` | `str` | Yes | Value to match (exact match for sender/subject, domain match for domain) |
| `action` | `str` | Yes | Must be `"boost"` for whitelist rules |
| `score_boost` | `int` | Yes | Points to add to importance_score (e.g., 20 adds 20 points) |
| `add_tags` | `list[str]` | Yes | Tags to add to the email (e.g., `["#vip", "#work"]`) |

**Evaluation:**
- Rules are evaluated in order (all matching rules are applied)
- Whitelist rules are applied after LLM classification but before note generation
- Multiple whitelist rules can match and all boosts/tags are accumulated

---

## Configuration Validation

All configurations are validated against the schema defined in `src/config_schema.py`:

- **Required sections:** Must be present (e.g., `imap`, `paths`, `openrouter`, `classification`, `summarization`, `processing`)
- **Required fields:** Must be present within required sections
- **Type checking:** Field types must match expected types
- **Constraints:** Values must meet constraints (ranges, lengths, etc.)
- **Default values:** Optional fields receive defaults if not specified

**Validation Errors:**
- Missing required sections → `ConfigurationError`
- Missing required fields → `ConfigurationError`
- Invalid types → `ConfigurationError`
- Values outside constraints → `ConfigurationError`

**Validation Warnings:**
- Non-critical issues (if any are defined)

---

## Environment Variable Overrides

Configuration values can be overridden using environment variables:

**Naming Convention:** `EMAIL_AGENT_<SECTION>_<KEY>` (uppercase, underscores)

**Examples:**
- `EMAIL_AGENT_IMAP_SERVER=imap.custom.com`
- `EMAIL_AGENT_IMAP_PORT=993`
- `EMAIL_AGENT_CLASSIFICATION_MODEL=openai/gpt-4`
- `EMAIL_AGENT_PROCESSING_IMPORTANCE_THRESHOLD=7`

**Type Conversion:**
- Integer values are automatically converted (port, thresholds, retry settings)
- Float values are automatically converted (temperature)
- String values remain as strings

**Precedence:** Environment variables > Config files

---

## Security Considerations

1. **Credentials:** Never store passwords or API keys in configuration files
   - Use environment variables (e.g., `IMAP_PASSWORD`, `OPENROUTER_API_KEY`)
   - Configuration files only specify which environment variable names to use

2. **File Permissions:** Restrict access to configuration files
   - Only application service account should have read/write access
   - Administrators may have read access for maintenance

3. **Version Control:**
   - `config.yaml` is typically gitignored (contains user-specific settings)
   - `config.yaml.example` should be in version control (template)
   - Account-specific configs in `config/accounts/` should be gitignored
   - `example-account.yaml` can be in version control (template)
   - `blacklist.yaml` and `whitelist.yaml` can be in version control (rules, not secrets)

---

## Related Documentation

- [V4 Configuration Guide](v4-configuration.md) - Complete configuration system documentation
- [pdd_V4.md](pdd_V4.md) - V4 Product Design Document Section 3.1
- [src/config_schema.py](../src/config_schema.py) - Schema definition source code
- [src/config_loader.py](../src/config_loader.py) - Configuration loader implementation
