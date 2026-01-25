# V4 Configuration Reference

**Status:** Complete  
**Task:** 20.3  
**Audience:** Operators, System Administrators, Developers  
**PDD Reference:** [pdd_V4.md](pdd_V4.md) Section 3.1

---

## Overview

Complete reference for all V4 configuration options, including global configuration, account-specific overrides, and configuration examples. For detailed schema information, see [V4 Configuration Schema Reference](v4-config-schema-reference.md).

---

## Configuration Structure

V4 uses a "Default + Override" configuration model:

1. **Global Configuration** (`config/config.yaml`): Base settings for all accounts
2. **Account Configuration** (`config/accounts/*.yaml`): Account-specific overrides
3. **Merge Strategy**: Account configs deep-merge over global config
   - Dictionaries: Deep merged (keys in account config overwrite keys in global config)
   - Lists: Completely replaced (lists in account config replace lists in global config)
   - Primitives: Overwritten (values in account config replace values in global config)

**Configuration Precedence (highest to lowest):**
1. Environment variables (if supported)
2. Account-specific config (`config/accounts/*.yaml`)
3. Global config (`config/config.yaml`)

---

## Global Configuration (`config/config.yaml`)

The global configuration file defines base settings that apply to all accounts by default. Only specify differences in account-specific configs.

**File Location:** `config/config.yaml`  
**Required:** Yes  
**Template:** `config/config.yaml.example`

### Configuration Domains

V4 configuration is organized into the following domains:

1. **`imap`** - IMAP server connection settings
2. **`paths`** - File and directory paths
3. **`openrouter`** - OpenRouter API configuration
4. **`classification`** - Email classification settings
5. **`summarization`** - Email summarization settings (optional)
6. **`processing`** - Processing thresholds and limits
7. **`auth`** - Authentication settings (optional, V5 feature: OAuth 2.0 support)
8. **`safety_interlock`** - Safety interlock settings (optional)

See [V4 Configuration Schema Reference](v4-config-schema-reference.md) for complete schema details.

---

## Account-Specific Configuration (`config/accounts/*.yaml`)

Account-specific configuration files override global settings for individual accounts.

**File Location:** `config/accounts/<account-name>.yaml`  
**Required:** No (only needed for multi-account setups)  
**Naming:** Use descriptive names (e.g., `work.yaml`, `personal.yaml`)

### When to Use Account Configs

- Different IMAP servers per account
- Different email addresses/usernames
- Different Obsidian vaults per account
- Different processing thresholds per account
- Different LLM models per account

### Account Config Structure

Only specify settings that differ from global config:

```yaml
# config/accounts/work.yaml
# Only specify differences from global config

imap:
  server: 'imap.work.com'  # Override global server
  username: 'work@company.com'  # Override global username
  password_env: 'IMAP_PASSWORD_WORK'  # Different env var

paths:
  obsidian_vault: '/path/to/work/vault'  # Different vault

processing:
  importance_threshold: 7  # Lower threshold for work account
```

---

## Configuration Options

### IMAP Configuration (`imap`)

**Purpose:** IMAP server connection settings

**Commonly Overridden:** Yes (per account)

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `server` | `str` | Yes | - | IMAP server hostname (e.g., 'imap.gmail.com') |
| `port` | `int` | No | `143` | IMAP port (143 for STARTTLS, 993 for SSL/TLS) |
| `username` | `str` | Yes | - | Email account username (typically full email address) |
| `password_env` | `str` | No | `IMAP_PASSWORD` | Environment variable name containing IMAP password |
| `query` | `str` | No | `ALL` | IMAP search query (e.g., 'UNSEEN', 'SENTSINCE 01-Jan-2024') |
| `processed_tag` | `str` | No | `AIProcessed` | IMAP flag name for processed emails |
| `application_flags` | `list[str]` | No | `['AIProcessed', ...]` | Application-specific flags for cleanup |

**Examples:**
```yaml
# Gmail
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'user@gmail.com'
  password_env: 'IMAP_PASSWORD'

# Outlook
imap:
  server: 'outlook.office365.com'
  port: 993
  username: 'user@outlook.com'
  password_env: 'IMAP_PASSWORD'

# Custom IMAP server
imap:
  server: 'mail.example.com'
  port: 143
  username: 'user@example.com'
  password_env: 'IMAP_PASSWORD'
```

### OpenRouter Configuration (`openrouter`)

**Purpose:** OpenRouter API settings

**Commonly Overridden:** Rarely (usually shared)

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `api_key_env` | `str` | No | `OPENROUTER_API_KEY` | Environment variable name containing API key |
| `api_url` | `str` | No | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |

**Example:**
```yaml
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
```

### Classification Configuration (`classification`)

**Purpose:** Email classification (spam/importance scoring) settings

**Commonly Overridden:** Yes (different models per account)

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `model` | `str` | Yes | - | LLM model (e.g., 'google/gemini-2.5-flash-lite-preview-09-2025') |
| `temperature` | `float` | No | `0.2` | LLM temperature (0.0-2.0, lower = more deterministic) |
| `retry_attempts` | `int` | No | `3` | Number of retry attempts for failed API calls |
| `retry_delay_seconds` | `int` | No | `5` | Initial delay between retries (exponential backoff) |
| `cost_per_1k_tokens` | `float` | No | - | Cost per 1000 tokens (for cost estimation) |
| `cost_per_email` | `float` | No | - | Direct cost per email (overrides token-based) |

**Examples:**
```yaml
# Fast, cost-effective model
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2
  cost_per_1k_tokens: 0.0001

# More accurate, more expensive model
classification:
  model: 'anthropic/claude-3-opus'
  temperature: 0.1
  cost_per_1k_tokens: 0.015
```

### Processing Configuration (`processing`)

**Purpose:** Processing thresholds and limits

**Commonly Overridden:** Yes (different thresholds per account)

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `importance_threshold` | `int` | No | `8` | Minimum importance score (0-10) to mark as important |
| `spam_threshold` | `int` | No | `5` | Maximum spam score (0-10) to consider as spam |
| `max_body_chars` | `int` | No | `4000` | Maximum characters to send to LLM (truncates longer emails) |
| `max_emails_per_run` | `int` | No | `15` | Maximum number of emails to process per execution |
| `summarization_tags` | `list[str] \| None` | No | `None` | Tags generated when importance_score >= threshold |

**Examples:**
```yaml
# Strict filtering (high threshold)
processing:
  importance_threshold: 9
  spam_threshold: 3
  max_emails_per_run: 10

# Lenient filtering (lower threshold)
processing:
  importance_threshold: 6
  spam_threshold: 7
  max_emails_per_run: 50
```

### Paths Configuration (`paths`)

**Purpose:** File and directory paths

**Commonly Overridden:** Yes (different vaults per account)

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `template_file` | `str` | No | `config/note_template.md.j2` | Jinja2 template for generating notes |
| `obsidian_vault` | `str` | Yes | - | Obsidian vault directory (must exist) |
| `log_file` | `str` | No | `logs/agent.log` | Operational log file |
| `analytics_file` | `str` | No | `logs/analytics.jsonl` | Structured analytics log (JSONL) |
| `changelog_path` | `str` | No | `logs/email_changelog.md` | Changelog/audit log file |
| `prompt_file` | `str` | No | `config/prompt.md` | LLM prompt file for classification |
| `summarization_prompt_path` | `str \| None` | No | `None` | Optional: Prompt file for summarization |

**Example:**
```yaml
paths:
  obsidian_vault: '/Users/username/Documents/Obsidian Vaults/Email Notes'
  log_file: 'logs/agent.log'
  analytics_file: 'logs/analytics.jsonl'
```

### Safety Interlock Configuration (`safety_interlock`)

**Purpose:** Safety mechanism to prevent accidental high-cost operations

**Commonly Overridden:** Rarely (usually set globally)

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `enabled` | `bool` | No | `true` | Enable/disable safety interlock |
| `cost_threshold` | `float` | No | `0.10` | Cost threshold in currency units |
| `skip_confirmation_below_threshold` | `bool` | No | `false` | Skip confirmation if cost below threshold |
| `average_tokens_per_email` | `int` | No | `2000` | Average tokens per email for cost estimation |
| `currency` | `str` | No | `$` | Currency symbol for cost display |

**Example:**
```yaml
safety_interlock:
  enabled: true
  cost_threshold: 0.10
  skip_confirmation_below_threshold: false
  average_tokens_per_email: 2000
  currency: '$'
```

---

## Configuration Examples

### Single-Account Configuration

**Global Config** (`config/config.yaml`):
```yaml
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'user@gmail.com'
  password_env: 'IMAP_PASSWORD'

openrouter:
  api_key_env: 'OPENROUTER_API_KEY'

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2
  cost_per_1k_tokens: 0.0001

processing:
  importance_threshold: 8
  spam_threshold: 5
  max_emails_per_run: 15

paths:
  obsidian_vault: '/path/to/vault'
```

**Environment Variables** (`.env`):
```bash
IMAP_PASSWORD=your-password
OPENROUTER_API_KEY=your-api-key
```

### Multi-Account Configuration

**Global Config** (`config/config.yaml`):
```yaml
# Shared settings
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2
  cost_per_1k_tokens: 0.0001

processing:
  importance_threshold: 8
  spam_threshold: 5
  max_emails_per_run: 15

# Default IMAP (can be overridden)
imap:
  server: 'imap.gmail.com'
  port: 993
  password_env: 'IMAP_PASSWORD'

# Default paths (can be overridden)
paths:
  log_file: 'logs/agent.log'
  analytics_file: 'logs/analytics.jsonl'
```

**Work Account** (`config/accounts/work.yaml`):
```yaml
imap:
  server: 'imap.work.com'
  username: 'work@company.com'
  password_env: 'IMAP_PASSWORD_WORK'

paths:
  obsidian_vault: '/path/to/work/vault'

processing:
  importance_threshold: 7  # Lower threshold for work
```

**Personal Account** (`config/accounts/personal.yaml`):
```yaml
imap:
  server: 'imap.gmail.com'
  username: 'personal@gmail.com'
  password_env: 'IMAP_PASSWORD_PERSONAL'

paths:
  obsidian_vault: '/path/to/personal/vault'

processing:
  importance_threshold: 9  # Higher threshold for personal
```

**Environment Variables** (`.env`):
```bash
IMAP_PASSWORD_WORK=work-password
IMAP_PASSWORD_PERSONAL=personal-password
OPENROUTER_API_KEY=shared-api-key
```

### Performance-Tuned Configuration

**High-Volume Account:**
```yaml
# config/accounts/high-volume.yaml
processing:
  max_emails_per_run: 100
  max_body_chars: 2000  # Shorter emails for faster processing

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # Fast model
  temperature: 0.1  # Lower temperature for consistency
  cost_per_1k_tokens: 0.0001  # Cost-effective

safety_interlock:
  enabled: true
  cost_threshold: 1.00  # Higher threshold for high-volume
  skip_confirmation_below_threshold: true  # Skip confirmation for small batches
```

**Quality-Focused Account:**
```yaml
# config/accounts/quality-focused.yaml
processing:
  max_emails_per_run: 10
  max_body_chars: 8000  # Longer emails for better context

classification:
  model: 'anthropic/claude-3-opus'  # More accurate model
  temperature: 0.2
  cost_per_1k_tokens: 0.015  # More expensive but accurate

safety_interlock:
  enabled: true
  cost_threshold: 0.05  # Lower threshold for quality checks
  skip_confirmation_below_threshold: false  # Always confirm
```

---

## Configuration Validation

V4 validates configuration at runtime:

1. **Schema Validation:** All configuration must match the schema (see [V4 Configuration Schema Reference](v4-config-schema-reference.md))
2. **Required Fields:** All required fields must be present
3. **Type Validation:** Values must match expected types
4. **Constraint Validation:** Values must meet constraints (ranges, min/max lengths)

**Validation Errors:**
- Invalid YAML syntax
- Missing required fields
- Invalid types (e.g., string instead of integer)
- Constraint violations (e.g., port out of range)

**Check Configuration:**
```bash
# Show merged configuration (validates on load)
python main.py show-config

# Show specific account config
python main.py show-config --account work
```

---

## Configuration Troubleshooting

### Invalid YAML Syntax

**Error:**
```
yaml.scanner.ScannerError: while scanning
```

**Solution:**
- Validate YAML syntax using online YAML validator
- Check for missing colons, incorrect indentation, unclosed quotes
- Use spaces, not tabs for indentation

### Missing Required Fields

**Error:**
```
ValidationError: Field required: imap.server
```

**Solution:**
- Ensure all required fields are present in global config
- Check [V4 Configuration Schema Reference](v4-config-schema-reference.md) for required fields

### Configuration Not Found

**Error:**
```
FileNotFoundError: config/config.yaml
```

**Solution:**
```bash
# Copy example config
cp config/config.yaml.example config/config.yaml
```

### Account Config Not Found

**Error:**
```
Account 'work' not found
```

**Solution:**
```bash
# Check if account config exists
ls -la config/accounts/work.yaml

# Create account config if missing
cp config/accounts/example-account.yaml config/accounts/work.yaml
```

### Environment Variables Not Set

**Error:**
```
KeyError: 'IMAP_PASSWORD'
```

**Solution:**
```bash
# Set environment variables
export IMAP_PASSWORD='your-password'
export OPENROUTER_API_KEY='your-api-key'

# Or create .env file
echo "IMAP_PASSWORD=your-password" > .env
echo "OPENROUTER_API_KEY=your-api-key" >> .env
```

### Path Does Not Exist

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/path/to/vault'
```

**Solution:**
```bash
# Create vault directory
mkdir -p /path/to/vault

# Verify path in config.yaml
# paths:
#   obsidian_vault: '/path/to/vault'
```

For more troubleshooting, see [V4 Troubleshooting Guide](v4-troubleshooting.md).

---

## Related Documentation

- [V4 Configuration System](v4-configuration.md) - Technical implementation details
- [V4 Configuration Examples](v4-config-examples.md) - Real-world examples
- [V4 Migration Guide](v4-migration-guide.md) - V3 to V4 configuration mapping
