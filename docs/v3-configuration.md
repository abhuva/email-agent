# V3 Configuration Guide

This document explains the V3 configuration system as specified in `pdd.md`.

## Overview

The V3 configuration system uses a structured YAML format with four main sections:
- `imap`: IMAP server connection settings
- `paths`: File and directory paths
- `openrouter`: OpenRouter API configuration
- `processing`: Processing thresholds and limits

All configuration must conform to the PDD Section 3.1 specification exactly.

## Quick Start

1. Copy `config/config.yaml.example` to `config/config.yaml`
2. Customize the values for your setup
3. Set required environment variables (see below)
4. The configuration will be automatically validated on load

## Configuration Structure

### IMAP Section

```yaml
imap:
  server: 'imap.example.com'      # IMAP server hostname
  port: 143                        # IMAP port (143 for STARTTLS, 993 for SSL)
  username: 'your-email@example.com'
  password_env: 'IMAP_PASSWORD'    # Environment variable name (MUST be set)
  query: 'ALL'                     # IMAP search query
  processed_tag: 'AIProcessed'     # IMAP flag for processed emails
```

**Required Environment Variable:**
- `IMAP_PASSWORD`: Your IMAP account password (security requirement)

### Paths Section

```yaml
paths:
  template_file: 'config/note_template.md.j2'  # Jinja2 template
  obsidian_vault: '/path/to/vault'              # Obsidian vault (must exist)
  log_file: 'logs/agent.log'                   # Operational logs
  analytics_file: 'logs/analytics.jsonl'        # Structured analytics
  changelog_path: 'logs/email_changelog.md'    # Changelog file
  prompt_file: 'config/prompt.md'              # LLM prompt file
```

**Validation:**
- `obsidian_vault` must be an existing directory
- `prompt_file` and `template_file` must be existing files

### OpenRouter Section

```yaml
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'           # Environment variable name (MUST be set)
  api_url: 'https://openrouter.ai/api/v1'     # API endpoint
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # LLM model
  temperature: 0.2                            # Temperature (0.0-2.0)
  retry_attempts: 3                            # Retry attempts
  retry_delay_seconds: 5                       # Initial retry delay
```

**Required Environment Variable:**
- `OPENROUTER_API_KEY`: Your OpenRouter API key (security requirement)

**Validation:**
- `temperature` must be between 0.0 and 2.0
- `retry_attempts` and `retry_delay_seconds` must be at least 1

### Processing Section

```yaml
processing:
  importance_threshold: 8        # Minimum importance score (0-10)
  spam_threshold: 5              # Maximum spam score (0-10)
  max_body_chars: 4000           # Max characters for LLM
  max_emails_per_run: 15         # Max emails per execution
```

**Validation:**
- Score thresholds must be between 0 and 10
- `max_body_chars` and `max_emails_per_run` must be at least 1

## Environment Variable Overrides

Any configuration value can be overridden using environment variables.

### Naming Convention

Format: `EMAIL_AGENT_<SECTION>_<KEY>` (uppercase, underscores)

Examples:
- `EMAIL_AGENT_IMAP_SERVER=imap.custom.com`
- `EMAIL_AGENT_IMAP_PORT=993`
- `EMAIL_AGENT_OPENROUTER_MODEL=openai/gpt-4`
- `EMAIL_AGENT_OPENROUTER_TEMPERATURE=0.3`
- `EMAIL_AGENT_PROCESSING_IMPORTANCE_THRESHOLD=7`
- `EMAIL_AGENT_PATHS_OBSIDIAN_VAULT=/custom/path`

### Type Conversion

The loader automatically converts environment variable values to appropriate types:
- **Integers**: `port`, `retry_attempts`, `retry_delay_seconds`, thresholds, `max_body_chars`, `max_emails_per_run`
- **Floats**: `temperature`
- **Strings**: All other values

### Usage

Environment variables are checked when the configuration is loaded. They override values from the YAML file, but the final configuration must still pass schema validation.

## Security Requirements

**CRITICAL:** Credentials MUST come from environment variables, not the config file.

The config file only specifies which environment variable names to use:
- `imap.password_env`: Environment variable name for IMAP password
- `openrouter.api_key_env`: Environment variable name for API key

The actual values must be set in your environment before running the application.

## Validation

The configuration is validated using a Pydantic schema that ensures:
- All required fields are present
- Data types are correct
- Values are within valid ranges
- Required files and directories exist
- Required environment variables are set

### Error Messages

If validation fails, you'll receive detailed error messages indicating:
- Which field failed validation
- What the expected type/format is
- What value was provided

## Loading Configuration

### Using ConfigLoader

```python
from src.config_v3_loader import ConfigLoader

loader = ConfigLoader('config/config.yaml')
config = loader.load()

# Access configuration values
print(config.imap.server)
print(config.openrouter.model)
print(config.processing.importance_threshold)
```

### Using settings.py Facade (Recommended)

```python
from src.settings import settings

# All modules should use the settings facade
api_url = settings.get_openrouter_api_url()
api_key = settings.get_openrouter_api_key()
```

See `src/settings.py` for the complete facade API.

## Migration from V2

If you're migrating from V2 configuration:

1. **Structure Change**: V2 used a flat structure, V3 uses grouped sections
2. **New Sections**: Configuration is now organized into `imap`, `paths`, `openrouter`, `processing`
3. **Path Changes**: Some paths moved to the `paths` section
4. **New Parameters**: V3 adds `temperature`, `retry_attempts`, `retry_delay_seconds` to `openrouter`
5. **New Parameters**: V3 adds `importance_threshold` and `spam_threshold` to `processing`

See `config/config.yaml.example` for the complete V3 structure.

## Reference

- **Technical Specification**: `pdd.md` Section 3.1
- **Example Configuration**: `config/config.yaml.example`
- **Schema Definition**: `src/config_v3_schema.py`
- **Loader Implementation**: `src/config_v3_loader.py`
- **Settings Facade**: `src/settings.py`
