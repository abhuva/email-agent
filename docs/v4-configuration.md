# V4 Configuration System

**Status:** In Development  
**Tasks:** Task 1 (Complete), Task 2 (Complete), Task 3 (Complete)  
**PDD Reference:** [pdd_V4.md](../pdd_V4.md) Section 3.1

---

## Overview

V4 introduces a multi-tenant configuration system that supports multiple email accounts with isolated configurations. The system uses a "Default + Override" model where global settings are defined in a base configuration file, and account-specific settings override the defaults.

## Directory Structure

```
config/
├── config.yaml              # Global/base configuration (V3 compatible)
├── config.yaml.example      # Example global configuration template
├── accounts/                 # Account-specific configuration files
│   └── example-account.yaml  # Example account configuration
├── blacklist.yaml           # Global blacklist rules (pre-processing)
└── whitelist.yaml           # Global whitelist rules (post-processing)
```

### Configuration Files

#### `config/config.yaml` (Global Base Configuration)
- **Purpose:** Base configuration that applies to all accounts by default
- **Structure:** V3-compatible YAML structure (see [v3-configuration.md](v3-configuration.md))
- **Override Strategy:** Account-specific configs deep-merge over this file
- **Status:** Already exists (V3 configuration file)

#### `config/accounts/*.yaml` (Account-Specific Overrides)
- **Purpose:** Account-specific configuration that overrides global defaults
- **Naming Convention:** `<account-id>.yaml` or `<tenant-name>.yaml`
  - Examples: `work.yaml`, `personal.yaml`, `client-xyz.yaml`
- **Location:** `config/accounts/` directory
- **Merge Strategy:** Deep merge with global config (see Merge Strategy below)

#### `config/blacklist.yaml` (Blacklist Rules)
- **Purpose:** Pre-processing rules that can drop or record emails without AI processing
- **Structure:** List of rule objects (see Rules Schema below)
- **Application:** Applied BEFORE LLM classification

#### `config/whitelist.yaml` (Whitelist Rules)
- **Purpose:** Post-processing rules that boost scores and add tags
- **Structure:** List of rule objects (see Rules Schema below)
- **Application:** Applied AFTER LLM classification

## Merge Strategy

When loading an account configuration, the system performs a deep merge:

1. **Dictionaries:** Deep merged (keys in account config overwrite keys in global config)
2. **Lists:** Completely replaced (lists in account config replace lists in global config)
3. **Primitives:** Overwritten (values in account config replace values in global config)

### Example Merge

**Global config.yaml:**
```yaml
imap:
  server: imap.example.com
  port: 143
  query: ALL
processing:
  importance_threshold: 8
  max_emails_per_run: 15
```

**Account config (work.yaml):**
```yaml
imap:
  server: imap.work.com
  port: 993
processing:
  importance_threshold: 7
```

**Merged Result:**
```yaml
imap:
  server: imap.work.com      # Overridden
  port: 993                   # Overridden
  query: ALL                  # From global (preserved)
processing:
  importance_threshold: 7     # Overridden
  max_emails_per_run: 15      # From global (preserved)
```

## Rules Schema

### Blacklist Rules (`config/blacklist.yaml`)

Blacklist rules are applied before AI processing. They can either:
- **`drop`**: Skip the email entirely (no processing, no file generation)
- **`record`**: Generate a raw markdown file without AI classification

**Schema:**
```yaml
- trigger: "sender" | "subject" | "domain"
  value: "<match-value>"
  action: "drop" | "record"
```

**Examples:**
```yaml
# Drop all emails from a specific sender
- trigger: "sender"
  value: "no-reply@spam.com"
  action: "drop"

# Drop all emails from a domain
- trigger: "domain"
  value: "spam-domain.com"
  action: "drop"

# Record emails with specific subject (skip AI but create file)
- trigger: "subject"
  value: "Unsubscribe"
  action: "record"
```

### Whitelist Rules (`config/whitelist.yaml`)

Whitelist rules are applied after AI processing. They can:
- **`boost`**: Increase importance score and add tags

**Schema:**
```yaml
- trigger: "sender" | "subject" | "domain"
  value: "<match-value>"
  action: "boost"
  score_boost: <integer>  # Points to add to importance_score
  add_tags: ["#tag1", "#tag2"]  # Tags to add
```

**Examples:**
```yaml
# Boost importance for important client domain
- trigger: "domain"
  value: "important-client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip", "#work"]

# Boost importance for boss emails
- trigger: "sender"
  value: "boss@company.com"
  action: "boost"
  score_boost: 15
  add_tags: ["#priority"]
```

## Filesystem Permissions

### Recommended Permissions

**Unix/Linux/macOS:**
- **Directories:** `750` (owner read/write/execute, group read/execute, others no access)
  - `chmod 750 config/ config/accounts/`
- **Configuration Files:** `640` (owner read/write, group read, others no access)
  - `chmod 640 config/*.yaml config/accounts/*.yaml`
- **Ownership:** Application service user/group
  - `chown app-user:app-group config/ config/accounts/ config/*.yaml config/accounts/*.yaml`

**Windows:**
- Windows uses ACLs (Access Control Lists) instead of Unix-style permissions
- Recommended: Restrict access to application service account and administrators
- Use Windows File Properties → Security tab to set appropriate permissions
- Ensure the application service account has Read/Write access
- Restrict access for other users/groups as needed

### Bootstrap Script

A bootstrap script is provided to create the configuration directory structure:

```bash
python scripts/bootstrap_config.py
```

This script:
- Creates `config/` directory if it doesn't exist
- Creates `config/accounts/` directory if it doesn't exist
- Verifies the directory structure is correct

**Note:** The bootstrap script only creates directories. You still need to:
1. Copy `config/config.yaml.example` to `config/config.yaml`
2. Copy `.env.example` to `.env` (if it exists)
3. Configure your settings in the copied files

### Security Considerations

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

## Usage Examples

### Creating an Account Configuration

1. Copy the example account file:
   ```bash
   cp config/accounts/example-account.yaml config/accounts/work.yaml
   ```

2. Edit `config/accounts/work.yaml` with account-specific settings:
   ```yaml
   imap:
     server: imap.work.com
     username: work@company.com
     password_env: IMAP_PASSWORD_WORK
   paths:
     obsidian_vault: /path/to/work/vault
   ```

3. The system will automatically merge `work.yaml` over `config.yaml` when processing the "work" account.

### Adding Blacklist Rules

Edit `config/blacklist.yaml`:
```yaml
- trigger: "domain"
  value: "spam.com"
  action: "drop"
```

### Adding Whitelist Rules

Edit `config/whitelist.yaml`:
```yaml
- trigger: "sender"
  value: "important@client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip"]
```

## Configuration Loader

The V4 configuration system uses `src/config_loader.py` to load and merge configurations.

### ConfigLoader Class

The `ConfigLoader` class handles loading global and account-specific configurations with deep merge logic.

#### Basic Usage

```python
from src.config_loader import ConfigLoader

# Initialize loader
loader = ConfigLoader('config')

# Load merged configuration for an account
config = loader.load_merged_config('work')
print(config['imap']['server'])
```

#### Module-Level Convenience Function

```python
from src.config_loader import load_merged_config

# Convenience function (uses default 'config' directory)
config = load_merged_config('work')
```

### Deep Merge Rules

The configuration loader implements the following merge rules:

1. **Dictionaries:** Deep merged recursively
   - Keys in account config overwrite keys in global config
   - Nested dictionaries are merged recursively
   
2. **Lists:** Completely replaced
   - Lists in account config replace lists in global config (no concatenation)
   
3. **Primitives:** Overwritten
   - String, int, float, bool values in account config replace values in global config

#### Example

```yaml
# config/config.yaml (Global)
imap:
  server: global.imap.com
  port: 143
  query: ALL
items: [1, 2, 3]

# config/accounts/work.yaml (Account Override)
imap:
  server: work.imap.com
  port: 993
items: [4, 5]

# Result (Merged)
imap:
  server: work.imap.com  # Overridden
  port: 993              # Overridden
  query: ALL             # Preserved from global
items: [4, 5]            # List replaced (not [1, 2, 3, 4, 5])
```

### Error Handling

The configuration loader provides robust error handling:

- **Missing Global Config:** Raises `FileNotFoundError` (global config is required)
- **Missing Account Config:** Returns global-only configuration (account config is optional)
- **Invalid YAML:** Raises `ConfigurationError` with detailed error message
- **Non-Dict Root:** Raises `ConfigurationError` if YAML root is not a dictionary
- **Invalid Account Name:** Raises `ValueError` for:
  - Empty or whitespace-only names
  - Path traversal patterns (`../`, `..\\`)
  - Non-string types

### Account Name Validation

Account names are validated to prevent security issues:

- Strips whitespace automatically
- Disallows path traversal patterns (`../`, `..\\`, `/`, `\\`)
- Must be non-empty after stripping
- Must be a string type

### API Reference

#### ConfigLoader Class

```python
class ConfigLoader:
    def __init__(
        self,
        base_dir: Path | str = "config",
        global_filename: str = "config.yaml",
        accounts_dirname: str = "accounts"
    ) -> None
    
    def load_global_config(self) -> Dict:
        """Load global configuration file."""
    
    def load_account_config(self, account_name: str) -> Dict:
        """Load account-specific configuration (returns {} if missing)."""
    
    def load_merged_config(self, account_name: str, validate: Optional[bool] = None) -> Dict:
        """Load and merge global + account configurations (with optional validation)."""
    
    def get_last_validation_result(self) -> Optional[ValidationResult]:
        """Get validation result from last load_merged_config call."""
    
    def validate_config(self, config: Dict) -> ValidationResult:
        """Validate a configuration dictionary against the schema."""
    
    @staticmethod
    def deep_merge(base: Dict, override: Dict) -> Dict:
        """Deep merge two configuration dictionaries."""
```

#### Module-Level Function

```python
def load_merged_config(
    account_name: str,
    base_dir: Path | str = DEFAULT_BASE_DIR
) -> Dict:
    """Convenience function to load merged configuration."""
```

## Schema Validation

V4 includes automatic schema validation to ensure configurations meet required structure and constraints. Validation is performed automatically when loading merged configurations.

### Validation Features

- **Automatic Validation:** Configurations are validated after merging (global + account-specific)
- **Required Fields:** Validates that all required fields are present
- **Type Checking:** Ensures field types match expected types (str, int, float, list, etc.)
- **Constraint Validation:** Validates constraints such as:
  - Min/max values for numeric fields (e.g., port: 1-65535, temperature: 0.0-2.0)
  - Min/max length for strings and lists
  - Enum values (if specified)
  - Item types for lists
- **Default Values:** Automatically applies default values for optional fields
- **Error Reporting:** Provides detailed error messages with field paths and error codes

### Validation Behavior

**Fatal Errors (ConfigurationError raised):**
- Missing required sections (e.g., `imap`, `paths`, `openrouter`)
- Missing required fields (e.g., `imap.server`, `imap.username`)
- Invalid field types (e.g., port must be int, not string)
- Values outside allowed ranges (e.g., port > 65535, temperature > 2.0)
- Invalid list item types

**Warnings (logged, processing continues):**
- Non-critical validation issues (if any are defined)

### Disabling Validation

Validation can be disabled when creating a ConfigLoader instance:

```python
from src.config_loader import ConfigLoader

# Disable validation
loader = ConfigLoader('config', enable_validation=False)
config = loader.load_merged_config('work')
```

Or for a single call:

```python
loader = ConfigLoader('config', enable_validation=True)
# Disable validation for this call only
config = loader.load_merged_config('work', validate=False)
```

### Accessing Validation Results

After loading a configuration, you can access the validation results:

```python
from src.config_loader import ConfigLoader

loader = ConfigLoader('config')
try:
    config = loader.load_merged_config('work')
except ConfigurationError as e:
    # Get detailed validation errors
    validation_result = loader.get_last_validation_result()
    if validation_result:
        for error in validation_result.errors:
            print(f"{error.path}: {error.message}")
```

### Schema Definition

The configuration schema is defined in `src/config_schema.py`. The schema defines:

- **Required sections:** `imap`, `paths`, `openrouter`, `classification`, `summarization`, `processing`
- **Required fields:** Within each section (e.g., `imap.server`, `imap.username`)
- **Field types:** Expected types for each field
- **Default values:** Default values for optional fields
- **Constraints:** Min/max values, length constraints, etc.

### Extending the Schema

To add new configuration options:

1. **Update the schema** in `src/config_schema.py`:
   ```python
   'new_section': {
       'required': True,  # or False
       'fields': {
           'new_field': {
               'type': str,  # or int, float, list, etc.
               'required': True,  # or False
               'default': 'default_value',  # optional
               'constraints': {
                   'min_length': 1,  # optional constraints
                   # ... other constraints
               }
           }
       }
   }
   ```

2. **Update tests** in `tests/test_config_schema.py` to include the new section/field

3. **Update documentation** (this file) to document the new option

### Validation Error Codes

Common validation error codes:

- `MISSING_REQUIRED_SECTION`: Required section is missing
- `MISSING_REQUIRED_FIELD`: Required field is missing
- `INVALID_TYPE`: Field type doesn't match expected type
- `INVALID_SECTION_TYPE`: Section is not a dictionary
- `VALUE_BELOW_MIN`: Numeric value is below minimum
- `VALUE_ABOVE_MAX`: Numeric value is above maximum
- `LENGTH_BELOW_MIN`: String/list length is below minimum
- `LENGTH_ABOVE_MAX`: String/list length is above maximum
- `INVALID_ITEM_TYPE`: List item type doesn't match expected type

### Example Validation Errors

```python
# Missing required field
ERROR[MISSING_REQUIRED_FIELD] imap.server: Required field 'server' is missing

# Invalid type
ERROR[INVALID_TYPE] imap.port: Expected type int, got str (value: 'not-a-number')

# Value out of range
ERROR[VALUE_ABOVE_MAX] imap.port: Value 70000 is above maximum 65535

# Missing required section
ERROR[MISSING_REQUIRED_SECTION] openrouter: Required section 'openrouter' is missing
```

## Implementation Status

- ✅ **Task 1.1:** Base configuration directory structure created
- ✅ **Task 1.2:** Global configuration file placeholder (already exists)
- ✅ **Task 1.3:** Account-specific configuration file placeholders created
- ✅ **Task 1.4:** Blacklist and whitelist configuration placeholders created
- ✅ **Task 1.5:** Filesystem permissions documented
- ✅ **Task 2:** Configuration loader with deep merge logic (complete)
- ✅ **Task 3:** Configuration schema validation (complete)

## Related Documentation

- [V3 Configuration Guide](v3-configuration.md) - V3 configuration system (base structure)
- [pdd_V4.md](../pdd_V4.md) - V4 Product Design Document
- [prd-v4.md](../prd-v4.md) - V4 Product Requirements Document

## References

- **PDD Section:** [pdd_V4.md](../pdd_V4.md) Section 3.1 - Configuration Schema
- **Task:** Task 1 - Create Configuration Directory Structure
