# V3 to V4 Migration Guide

**Status:** Complete  
**Task:** 20.4  
**Audience:** Existing V3 Users  
**PDD Reference:** [pdd_V4.md](../pdd_V4.md)

---

## Overview

Complete guide for migrating from V3 to V4, including key differences, migration paths, step-by-step checklist, and compatibility information.

V4 introduces multi-account support, a rules engine, and enhanced HTML content parsing while maintaining backward compatibility with V3 for single-account usage.

---

## Key Differences Between V3 and V4

### Architecture Changes

**V3:**
- Single-account processing
- Global configuration (`config/config.yaml`)
- Single `Pipeline` class for processing
- Settings facade singleton

**V4:**
- Multi-account processing with state isolation
- Global + account-specific configuration (`config/config.yaml` + `config/accounts/*.yaml`)
- `MasterOrchestrator` + `AccountProcessor` architecture
- Configuration loader with deep merge

**Key Architectural Principle:**
- **State Isolation:** Each account is processed in complete isolation
- **No State Bleeding:** Data from one account never affects another

### Configuration Changes

**V3 Configuration:**
- Single `config/config.yaml` file
- All settings in one file
- No account-specific overrides

**V4 Configuration:**
- Global `config/config.yaml` (base settings)
- Account-specific `config/accounts/*.yaml` (overrides)
- Deep merge strategy (dictionaries merged, lists replaced, primitives overwritten)
- New: `safety_interlock` section (optional)
- New: Rules files (`blacklist.yaml`, `whitelist.yaml`)

**Configuration Compatibility:**
- V3 `config.yaml` is fully compatible with V4 global config
- No changes required for single-account usage
- Account-specific configs are optional

### Feature Changes

**New Features in V4:**
1. **Multi-Account Support:**
   - Process multiple accounts in one run
   - Account-specific configuration overrides
   - Isolated state per account

2. **Rules Engine:**
   - Blacklist rules (pre-processing: drop/record emails)
   - Whitelist rules (post-processing: boost scores, add tags)
   - YAML-based rule configuration

3. **HTML Content Parsing:**
   - Automatic HTML to Markdown conversion
   - Fallback to plain text on parsing failure

4. **Safety Interlock:**
   - Cost estimation before processing
   - User confirmation for high-cost operations

5. **Enhanced CLI:**
   - `--account <name>`: Process specific account
   - `--all`: Process all accounts
   - `show-config`: Display merged configuration

**Unchanged Features:**
- V3 CLI commands still work (backward compatible)
- Same configuration structure (for single account)
- Same processing pipeline (for single account)
- Same note generation
- Same logging system

### Breaking Changes

**No Breaking Changes for Single-Account Usage:**
- V3 `config.yaml` works as-is in V4
- V3 CLI commands work in V4 (V3 mode)
- V3 processing behavior unchanged

**Breaking Changes for Multi-Account Usage:**
- Must use V4 CLI commands (`--account` or `--all`)
- Must create account-specific configs for multi-account
- Must understand deep merge strategy

**Deprecated (Not Yet):**
- No features deprecated in V4
- V3 mode fully supported

---

## Migration Paths

### In-Place Upgrade

**Best For:**
- Single-account users
- Users wanting to upgrade without major changes
- Users who want to keep existing configuration

**Process:**
1. Switch to V4 branch
2. Keep existing `config/config.yaml` (no changes needed)
3. Continue using V3 CLI commands
4. Gradually adopt V4 features as needed

**Advantages:**
- Minimal changes required
- Backward compatible
- Can adopt V4 features incrementally

**Disadvantages:**
- Don't get multi-account benefits immediately
- May need to restructure config later for multi-account

### Parallel Deployment

**Best For:**
- Multi-account users
- Users wanting to test V4 before full migration
- Users with complex configurations

**Process:**
1. Keep V3 on `main` branch
2. Test V4 on `v4-orchestrator` branch
3. Create account-specific configs in V4
4. Test multi-account processing
5. Migrate fully when ready

**Advantages:**
- Can test V4 without affecting V3
- Can migrate gradually
- Can rollback easily

**Disadvantages:**
- More complex setup
- Need to maintain two branches

---

## Pre-Migration Checklist

Before migrating, ensure:

- [ ] V3 is working correctly
- [ ] Current `config/config.yaml` is backed up
- [ ] Environment variables are documented
- [ ] Obsidian vault paths are known
- [ ] Processing thresholds are documented
- [ ] Test email account is available for testing
- [ ] Git repository is clean (commit or stash changes)

---

## Step-by-Step Migration Process

### Step 1: Backup Current Configuration

```bash
# Backup V3 config
cp config/config.yaml config/config.yaml.v3.backup

# Backup .env if it exists
cp .env .env.v3.backup

# Create backup directory
mkdir -p backups
cp config/config.yaml backups/config.yaml.v3.backup
```

### Step 2: Review V4 Requirements

- Read [V4 Installation & Setup](v4-installation-setup.md)
- Review [V4 Configuration Reference](v4-configuration-reference.md)
- Understand multi-account concepts
- Review rules engine capabilities

### Step 3: Switch to V4 Branch

```bash
# Switch to V4 branch
git checkout v4-orchestrator

# Pull latest changes
git pull origin v4-orchestrator

# Verify branch
git branch
```

### Step 4: Update Dependencies

```bash
# Install/update dependencies
pip install -r requirements.txt --upgrade
```

### Step 5: Verify Configuration

**For Single-Account (No Changes Needed):**
```bash
# Your existing config.yaml should work as-is
# Test configuration loading
python main.py show-config  # May not work in V3 mode, but config should load

# Test processing (V3 mode)
python main.py process --dry-run
```

**For Multi-Account (Create Account Configs):**
```bash
# Create accounts directory
mkdir -p config/accounts

# Option 1: Use existing config as account config
cp config/config.yaml config/accounts/personal.yaml

# Option 2: Create minimal global config + account config
# (See Configuration Mapping section)
```

### Step 6: Test Migration

```bash
# Test single account (V3 mode)
python main.py process --dry-run

# Test multi-account (V4 mode)
python main.py process --account personal --dry-run
python main.py process --all --dry-run
```

### Step 7: Validate and Deploy

```bash
# Validate configuration
python main.py show-config --account personal

# Process with dry-run
python main.py process --account personal --dry-run

# Process for real
python main.py process --account personal
```

---

## Configuration Mapping

### V3 to V4 Configuration Mapping

V3 configuration maps directly to V4 global configuration. No changes required for single-account usage.

**V3 Config Structure:**
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

processing:
  importance_threshold: 8
  spam_threshold: 5

paths:
  obsidian_vault: '/path/to/vault'
```

**V4 Global Config (Same Structure):**
```yaml
# config/config.yaml - Same as V3
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

processing:
  importance_threshold: 8
  spam_threshold: 5

paths:
  obsidian_vault: '/path/to/vault'
```

**V4 Account Config (Optional, for Multi-Account):**
```yaml
# config/accounts/personal.yaml - Only differences from global
# (If using multi-account, only specify what differs)
```

### Configuration Migration Strategies

**Strategy 1: Keep V3 Config as Global (Single Account)**
- Keep existing `config/config.yaml` as-is
- No account configs needed
- Use V3 CLI commands (backward compatible)

**Strategy 2: Convert to Multi-Account**
- Move shared settings to global `config/config.yaml`
- Create account-specific configs in `config/accounts/*.yaml`
- Use V4 CLI commands (`--account` or `--all`)

---

## Compatibility Matrix

### Direct Compatibility

**Fully Compatible (No Changes Needed):**
- `config/config.yaml` structure
- Environment variables
- IMAP configuration
- OpenRouter configuration
- Classification settings
- Processing thresholds
- Paths configuration
- V3 CLI commands (single-account mode)

### Manual Changes Required

**For Multi-Account Usage:**
- Create `config/accounts/` directory
- Create account-specific config files
- Use V4 CLI commands (`--account` or `--all`)
- Understand deep merge strategy

**For Rules Engine:**
- Create `config/blacklist.yaml` (optional)
- Create `config/whitelist.yaml` (optional)
- Define rules (see [V4 Rule Syntax Guide](v4-rule-syntax-guide.md))

**For Safety Interlock:**
- Add `safety_interlock` section to config (optional)
- Configure cost thresholds
- Set up cost estimation

### No Longer Supported

**Nothing Deprecated:**
- All V3 features work in V4
- V3 mode fully supported
- No breaking changes

---

## Migration Examples

### Example 1: Single-Account V3 to V4 (No Changes)

**V3 Setup:**
```yaml
# config/config.yaml
imap:
  server: 'imap.gmail.com'
  username: 'user@gmail.com'
  password_env: 'IMAP_PASSWORD'
# ... rest of config
```

**V4 Setup (Same):**
```yaml
# config/config.yaml - No changes needed
imap:
  server: 'imap.gmail.com'
  username: 'user@gmail.com'
  password_env: 'IMAP_PASSWORD'
# ... rest of config (same as V3)
```

**Usage:**
```bash
# V3 command (still works in V4)
python main.py process

# Or use V4 command (same result)
python main.py process --account default  # If account config exists
```

### Example 2: Multi-Account Setup

**V3 Config (Original):**
```yaml
# config/config.yaml (V3)
imap:
  server: 'imap.gmail.com'
  username: 'personal@gmail.com'
  password_env: 'IMAP_PASSWORD'
paths:
  obsidian_vault: '/path/to/personal/vault'
```

**V4 Global Config:**
```yaml
# config/config.yaml (V4 - Shared settings)
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2

processing:
  importance_threshold: 8
  spam_threshold: 5
```

**V4 Personal Account Config:**
```yaml
# config/accounts/personal.yaml
imap:
  server: 'imap.gmail.com'
  username: 'personal@gmail.com'
  password_env: 'IMAP_PASSWORD_PERSONAL'
paths:
  obsidian_vault: '/path/to/personal/vault'
```

**V4 Work Account Config:**
```yaml
# config/accounts/work.yaml
imap:
  server: 'imap.work.com'
  username: 'work@company.com'
  password_env: 'IMAP_PASSWORD_WORK'
paths:
  obsidian_vault: '/path/to/work/vault'
processing:
  importance_threshold: 7  # Lower threshold for work
```

**Usage:**
```bash
# Process personal account
python main.py process --account personal

# Process work account
python main.py process --account work

# Process all accounts
python main.py process --all
```

---

## Rollback Strategy

### Rollback to V3

If you need to rollback to V3:

```bash
# Switch back to main branch
git checkout main

# Restore V3 config
cp config/config.yaml.v3.backup config/config.yaml
cp .env.v3.backup .env

# Verify V3 works
python main.py process --dry-run
```

### Partial Rollback

If only some features need rollback:

1. **Keep V4 but use V3 mode:**
   ```bash
   # Use V3 CLI commands (backward compatible)
   python main.py process  # V3 mode
   ```

2. **Remove account configs:**
   ```bash
   # Remove account configs, use global config only
   rm -rf config/accounts/
   ```

3. **Disable V4 features:**
   - Don't use `--account` or `--all` flags
   - Don't create account configs
   - Don't use rules engine

---

## Migration Troubleshooting

### Configuration Not Loading

**Error:**
```
ValidationError: Field required: imap.server
```

**Solution:**
- Ensure all required fields are present
- Check YAML syntax
- Verify configuration structure matches schema

### Account Not Found

**Error:**
```
Account 'work' not found
```

**Solution:**
- Check account config exists: `ls config/accounts/work.yaml`
- Verify account name matches filename (without .yaml)
- Create account config if missing

### Environment Variables Not Set

**Error:**
```
KeyError: 'IMAP_PASSWORD'
```

**Solution:**
- Set environment variables: `export IMAP_PASSWORD='password'`
- Or create `.env` file
- Check `password_env` in config matches env var name

### Processing Errors

**Error:**
```
ConnectionError: Failed to connect
```

**Solution:**
- Verify IMAP settings in config
- Check network connectivity
- Test IMAP connection manually

For more troubleshooting, see [V4 Troubleshooting Guide](v4-troubleshooting.md).

---

## Migration Paths

*To be completed in Task 20.4*

### In-Place Upgrade

*To be completed in Task 20.4*

### Parallel Deployment

*To be completed in Task 20.4*

---

## Pre-Migration Checklist

*To be completed in Task 20.4*

---

## Step-by-Step Migration Process

*To be completed in Task 20.4*

### Step 1: Backup Current Configuration

*To be completed in Task 20.4*

### Step 2: Review V4 Requirements

*To be completed in Task 20.4*

### Step 3: Update Configuration Structure

*To be completed in Task 20.4*

### Step 4: Map V3 Configuration to V4

*To be completed in Task 20.4*

### Step 5: Test Migration

*To be completed in Task 20.4*

### Step 6: Validate and Deploy

*To be completed in Task 20.4*

---

## Configuration Mapping

*To be completed in Task 20.4*

### V3 to V4 Configuration Mapping Table

*To be completed in Task 20.4*

---

## Compatibility Matrix

*To be completed in Task 20.4*

### Direct Compatibility

*To be completed in Task 20.4*

### Manual Changes Required

*To be completed in Task 20.4*

### No Longer Supported

*To be completed in Task 20.4*

---

## Migration Examples

*To be completed in Task 20.4*

### Example: Single-Account V3 to V4

*To be completed in Task 20.4*

### Example: Multi-Account Setup

*To be completed in Task 20.4*

---

## Rollback Strategy

*To be completed in Task 20.4*

---

## Migration Troubleshooting

*To be completed in Task 20.4*

---

## Related Documentation

- [V4 Installation & Setup](v4-installation-setup.md) - Installation instructions
- [V4 Configuration Reference](v4-configuration-reference.md) - V4 configuration details
- [V3 Configuration Guide](v3-configuration.md) - V3 configuration reference
- [V4 Multi-Account Best Practices](v4-multi-account-best-practices.md) - Multi-account guidance
