# V3 Migration Guide: Using settings.py Facade

This guide documents the migration from direct configuration access to the `settings.py` facade pattern as required by the PDD.

## Architecture Change

**V2 (Old):**
- Direct access to `ConfigManager` or `config` dictionary
- Modules access configuration like: `config.imap['server']`, `config.openrouter['api_key']`

**V3 (New):**
- All configuration access through `settings.py` facade
- Modules access configuration like: `settings.get_imap_server()`, `settings.get_openrouter_api_key()`

## Migration Pattern

### Before (V2 - Direct Access)

```python
from src.config import ConfigManager

config = ConfigManager('config/config.yaml', '.env')

# Direct dictionary access
server = config.imap['server']
api_key = config.openrouter['api_key']
max_emails = config.max_emails_per_run
```

### After (V3 - Facade Pattern)

```python
from src.settings import settings

# Initialize settings (typically done once at startup)
settings.initialize('config/config.yaml', '.env')

# Use facade getter methods
server = settings.get_imap_server()
api_key = settings.get_openrouter_api_key()
max_emails = settings.get_max_emails_per_run()
```

## Complete Mapping

### IMAP Configuration

| V2 Access | V3 Facade Method |
|-----------|------------------|
| `config.imap['server']` | `settings.get_imap_server()` |
| `config.imap['port']` | `settings.get_imap_port()` |
| `config.imap['username']` | `settings.get_imap_username()` |
| `config.imap['password']` (from env) | `settings.get_imap_password()` |
| `config.imap['query']` | `settings.get_imap_query()` |
| `config.processed_tag` | `settings.get_imap_processed_tag()` |

### Paths Configuration

| V2 Access | V3 Facade Method |
|-----------|------------------|
| `config.prompt_file` | `settings.get_prompt_file()` |
| `config.obsidian_vault_path` | `settings.get_obsidian_vault()` |
| `config.log_file` | `settings.get_log_file()` |
| `config.analytics_file` | `settings.get_analytics_file()` |
| `config.changelog_path` | `settings.get_changelog_path()` |
| (new) | `settings.get_template_file()` |

### OpenRouter Configuration

| V2 Access | V3 Facade Method |
|-----------|------------------|
| `config.openrouter['api_key']` (from env) | `settings.get_openrouter_api_key()` |
| `config.openrouter['api_url']` | `settings.get_openrouter_api_url()` |
| `config.openrouter['model']` | `settings.get_openrouter_model()` |
| (new) | `settings.get_openrouter_temperature()` |
| (new) | `settings.get_openrouter_retry_attempts()` |
| (new) | `settings.get_openrouter_retry_delay_seconds()` |

### Processing Configuration

| V2 Access | V3 Facade Method |
|-----------|------------------|
| `config.max_body_chars` | `settings.get_max_body_chars()` |
| `config.max_emails_per_run` | `settings.get_max_emails_per_run()` |
| (new) | `settings.get_importance_threshold()` |
| (new) | `settings.get_spam_threshold()` |

## Migration Steps

### 1. Update Imports

**Remove:**
```python
from src.config import ConfigManager
```

**Add:**
```python
from src.settings import settings
```

### 2. Remove ConfigManager Initialization

**Remove:**
```python
config = ConfigManager('config/config.yaml', '.env')
```

**Add (at application startup):**
```python
settings.initialize('config/config.yaml', '.env')
```

### 3. Replace Direct Access

Replace all direct configuration access with facade method calls.

### 4. Update Function Signatures

**Before:**
```python
def process_email(email, config: ConfigManager):
    server = config.imap['server']
    ...
```

**After:**
```python
def process_email(email):
    # No config parameter needed - use settings facade
    server = settings.get_imap_server()
    ...
```

## V3 Module Requirements

**All new V3 modules MUST:**
1. Use `settings.py` facade for configuration access
2. NOT accept `ConfigManager` or `config` dictionary as parameters
3. NOT access configuration directly from YAML
4. Import and use: `from src.settings import settings`

## Backward Compatibility

- V2 code can continue using `ConfigManager` for now
- V3 modules will use `settings.py` facade exclusively
- Migration will happen incrementally as V3 modules are implemented

## Examples

### Example 1: IMAP Connection

**V2:**
```python
def connect_imap(config: ConfigManager):
    server = config.imap['server']
    port = config.imap['port']
    username = config.imap['username']
    password = os.environ.get(config.imap['password_env'])
```

**V3:**
```python
from src.settings import settings

def connect_imap():
    server = settings.get_imap_server()
    port = settings.get_imap_port()
    username = settings.get_imap_username()
    password = settings.get_imap_password()  # Handles env var lookup
```

### Example 2: LLM Client

**V2:**
```python
def call_llm(config: ConfigManager):
    api_key = os.environ.get(config.openrouter['api_key_env'])
    api_url = config.openrouter['api_url']
    model = config.openrouter['model']
```

**V3:**
```python
from src.settings import settings

def call_llm():
    api_key = settings.get_openrouter_api_key()  # Handles env var lookup
    api_url = settings.get_openrouter_api_url()
    model = settings.get_openrouter_model()
    temperature = settings.get_openrouter_temperature()
```

## Testing

When migrating tests:

1. Mock the `settings` facade instead of `ConfigManager`
2. Use `settings.initialize()` with test configuration
3. Reset settings between tests if needed

## Checklist

- [ ] Replace `ConfigManager` imports with `settings` facade
- [ ] Remove `config` parameters from function signatures
- [ ] Replace all `config.*` access with `settings.get_*()` calls
- [ ] Update tests to use settings facade
- [ ] Verify no direct YAML access remains
- [ ] Update documentation

## Reference

- **PDD Specification**: `pdd.md` Section 2 (Architecture) and Section 5.2 (settings.py Facade)
- **Settings Facade**: `src/settings.py`
- **Configuration Guide**: `docs/v3-configuration.md`
