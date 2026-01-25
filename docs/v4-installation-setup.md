# V4 Installation & Setup Guide

**Status:** Complete  
**Task:** 20.2  
**Audience:** Operators, System Administrators, New Users  
**PDD Reference:** [pdd_V4.md](pdd_V4.md)

---

## Overview

This guide covers installation, setup, and initial configuration for Email Agent V4. It includes prerequisites, installation steps, configuration basics, and verification procedures.

V4 introduces multi-account support with isolated state and configuration, a rules engine for email filtering, and enhanced HTML content parsing. This guide will help you get V4 up and running, whether you're doing a fresh installation or upgrading from V3.

---

## Prerequisites

### System Requirements

**Python:**
- **Minimum:** Python 3.8
- **Recommended:** Python 3.10 or higher
- Verify with: `python --version` or `python3 --version`

**Operating System:**
- Windows 10/11
- macOS 10.15 or later
- Linux (most distributions)

**Disk Space:**
- Minimum: 100 MB for application and dependencies
- Recommended: 500 MB+ for logs and generated notes

**Network:**
- Internet connection for IMAP email access
- Internet connection for OpenRouter API access

### Required Accounts

**IMAP Email Account:**
- Any IMAP-compatible email provider (Gmail, Outlook, custom IMAP server)
- IMAP access enabled (may require enabling in account settings)
- For Gmail: Enable "Less secure app access" or use App Password
- For accounts with 2FA: Use app-specific passwords

**OpenRouter API Account:**
- Sign up at [https://openrouter.ai/](https://openrouter.ai/)
- Get API key from [https://openrouter.ai/keys](https://openrouter.ai/keys)
- Free tier available for testing

**Obsidian Vault (Optional):**
- Obsidian vault directory for storing generated notes
- Directory must exist and be writable

### Required Tools

- **Git:** For cloning the repository
  - Verify: `git --version`
- **pip:** Python package manager (usually included with Python)
  - Verify: `pip --version` or `pip3 --version`

### Network Considerations

- **IMAP Ports:** Ensure ports 143 (STARTTLS) or 993 (SSL/TLS) are accessible
- **Firewall:** May need to allow outbound connections to IMAP servers and OpenRouter API
- **Proxy:** If behind a corporate proxy, configure proxy settings for Python/requests

---

## Installation Steps

### Fresh Installation

#### Step 1: Clone the Repository

```bash
# Clone the repository
git clone <repository-url>
cd email-agent

# Switch to V4 branch (if not already on it)
git checkout v4-orchestrator

# Verify you're in the correct directory
ls -la  # Should show main.py, requirements.txt, src/, config/, etc.
```

**Expected Directory Structure:**
```
email-agent/
├── main.py
├── requirements.txt
├── src/
├── config/
│   ├── config.yaml.example
│   ├── accounts/
│   ├── blacklist.yaml
│   └── whitelist.yaml
├── docs/
└── tests/
```

#### Step 2: Install Python Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Or use pip3 if needed
pip3 install -r requirements.txt

# For virtual environment (recommended):
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Verify Installation:**
```bash
python --version  # Should show Python 3.8+
pip list | grep -E "pydantic|pyyaml|click|requests|html2text|rich"
```

**Expected Key Packages:**
```
pydantic         2.x.x
pyyaml           6.x.x
click             8.x.x
requests          2.x.x
html2text         2020.x.x
rich              13.x.x
jinja2            3.x.x
```

#### Step 3: Set Up Configuration Files

```bash
# Copy example configuration files
cp config/config.yaml.example config/config.yaml

# Create accounts directory (if it doesn't exist)
mkdir -p config/accounts

# Create log directory
mkdir -p logs

# Verify structure
ls -la config/
# Should show: config.yaml, accounts/, blacklist.yaml, whitelist.yaml
```

#### Step 4: Set Up Environment Variables

**Create `.env` file** (if it doesn't exist):
```bash
# Create .env file
touch .env  # or create manually

# Edit .env file
nano .env  # or use your preferred editor
```

**Add Required Environment Variables:**
```bash
# IMAP password (required)
IMAP_PASSWORD=your-imap-password-here

# OpenRouter API key (required)
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**Security Notes:**
- Never commit `.env` to version control (it's in `.gitignore`)
- Use app-specific passwords for email accounts with 2FA
- Keep your OpenRouter API key secure
- For multiple accounts, use different environment variable names (e.g., `IMAP_PASSWORD_WORK`, `IMAP_PASSWORD_PERSONAL`)

#### Step 5: Configure Global Configuration

Edit `config/config.yaml` with your settings:

```yaml
# Basic IMAP configuration
imap:
  server: 'imap.gmail.com'  # Your IMAP server
  port: 993                  # 993 for SSL, 143 for STARTTLS
  username: 'your-email@example.com'
  password_env: 'IMAP_PASSWORD'  # Environment variable name

# OpenRouter API configuration
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'

# Classification settings
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2

# Paths
paths:
  obsidian_vault: '/path/to/your/obsidian/vault'
  log_file: 'logs/agent.log'
  analytics_file: 'logs/analytics.jsonl'
```

**Important:** Ensure the `obsidian_vault` directory exists:
```bash
mkdir -p /path/to/your/obsidian/vault
```

#### Step 6: (Optional) Set Up Account-Specific Configuration

For multi-account setups, create account-specific configs:

```bash
# Create account config file
cp config/accounts/example-account.yaml config/accounts/work.yaml

# Edit account config
nano config/accounts/work.yaml
```

**Example Account Config** (`config/accounts/work.yaml`):
```yaml
# Account-specific overrides for 'work' account
imap:
  server: 'imap.work.com'
  username: 'work@company.com'
  password_env: 'IMAP_PASSWORD_WORK'  # Different env var

paths:
  obsidian_vault: '/path/to/work/vault'  # Different vault

processing:
  importance_threshold: 7  # Account-specific threshold
```

**Set Account-Specific Environment Variables:**
```bash
# In .env file
IMAP_PASSWORD_WORK=work-account-password
```

#### Step 7: (Optional) Configure Rules

Edit rule files if needed:

```bash
# Edit blacklist rules (pre-processing)
nano config/blacklist.yaml

# Edit whitelist rules (post-processing)
nano config/whitelist.yaml
```

See [V4 Rule Syntax Guide](v4-rule-syntax-guide.md) for rule syntax and examples.

### Upgrade from V3

If you're upgrading from V3, follow these steps:

#### Step 1: Backup Current Configuration

```bash
# Backup V3 config
cp config/config.yaml config/config.yaml.v3.backup

# Backup .env if it exists
cp .env .env.v3.backup
```

#### Step 2: Switch to V4 Branch

```bash
# Ensure you're on the V4 branch
git checkout v4-orchestrator

# Pull latest changes
git pull origin v4-orchestrator
```

#### Step 3: Update Dependencies

```bash
# Install/update dependencies
pip install -r requirements.txt --upgrade
```

#### Step 4: Migrate Configuration

**Option A: Use Existing V3 Config as Global Config**
- Your existing `config/config.yaml` can serve as the global config
- No changes needed if using single account

**Option B: Create Account-Specific Config**
- If you want to prepare for multi-account:
  ```bash
  # Create accounts directory
  mkdir -p config/accounts
  
  # Copy your V3 config as an account config
  cp config/config.yaml config/accounts/personal.yaml
  
  # Update global config with shared settings
  # Edit config/config.yaml to contain only shared settings
  ```

#### Step 5: Review Configuration Changes

- Check [V4 Migration Guide](v4-migration-guide.md) for configuration changes
- Review new V4 configuration options
- Update any deprecated settings

#### Step 6: Test Installation

```bash
# Test configuration loading
python main.py show-config  # V4 command

# Test with dry-run
python main.py process --dry-run  # V3 mode (backward compatible)
```

---

## Initial Configuration

### Core Configuration Concepts

**Global Configuration (`config/config.yaml`):**
- Base settings that apply to all accounts by default
- Contains shared settings (API keys, models, paths)
- Can be overridden by account-specific configs

**Account Configuration (`config/accounts/*.yaml`):**
- Account-specific overrides
- Deep-merged over global config
- Only specify differences from global config

**Rules Files:**
- `config/blacklist.yaml`: Pre-processing rules (drop/record emails)
- `config/whitelist.yaml`: Post-processing rules (boost scores, add tags)

### Minimal Working Configuration

**Single-Account Setup:**

1. **Global Config** (`config/config.yaml`):
```yaml
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'your-email@gmail.com'
  password_env: 'IMAP_PASSWORD'

openrouter:
  api_key_env: 'OPENROUTER_API_KEY'

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

paths:
  obsidian_vault: '/path/to/vault'
```

2. **Environment Variables** (`.env`):
```bash
IMAP_PASSWORD=your-password
OPENROUTER_API_KEY=your-api-key
```

3. **Verify:**
```bash
python main.py show-config  # Should show merged config
```

**Multi-Account Setup:**

1. **Global Config** (`config/config.yaml`): Shared settings
2. **Account Configs** (`config/accounts/*.yaml`): Account-specific overrides
3. **Environment Variables**: Account-specific passwords

See [V4 Configuration Reference](v4-configuration-reference.md) for complete configuration options.

---

## Verification

### Test 1: Verify Python Installation

```bash
python --version
# Should output: Python 3.8.x or higher
```

### Test 2: Verify Dependencies

```bash
pip list | grep -E "pydantic|pyyaml|click|requests|html2text"
# Should show installed packages
```

### Test 3: Verify Configuration Loading

```bash
# V4: Show merged configuration
python main.py show-config

# Should output YAML configuration without errors
```

### Test 4: Verify Environment Variables

```bash
# Check if environment variables are set
echo $IMAP_PASSWORD  # Should show password (or empty if not set)
echo $OPENROUTER_API_KEY  # Should show API key (or empty if not set)

# Or use Python to check
python -c "import os; print('IMAP_PASSWORD:', 'SET' if os.getenv('IMAP_PASSWORD') else 'NOT SET')"
```

### Test 5: Verify Directory Structure

```bash
# Check required directories exist
ls -la config/
ls -la config/accounts/
ls -la logs/

# Check config files exist
test -f config/config.yaml && echo "config.yaml exists" || echo "config.yaml missing"
test -f config/blacklist.yaml && echo "blacklist.yaml exists" || echo "blacklist.yaml missing"
test -f config/whitelist.yaml && echo "whitelist.yaml exists" || echo "whitelist.yaml missing"
```

### Test 6: Test Configuration Validation

```bash
# V4: Validate configuration
python main.py show-config --account work  # If account config exists

# Should output merged configuration or error if invalid
```

### Test 7: Dry-Run Test

```bash
# Test processing without side effects
python main.py process --dry-run

# V4 multi-account mode:
python main.py process --account work --dry-run
python main.py process --all --dry-run
```

**Expected Output:**
- Configuration loads without errors
- No file writes or IMAP flag changes (dry-run mode)
- Processing logs show expected behavior

---

## Common Installation Issues

### Issue: Python Version Too Old

**Error:**
```
SyntaxError: invalid syntax
```

**Solution:**
- Upgrade Python to 3.8 or higher
- Use `python3` instead of `python` if both versions installed
- Verify: `python --version`

### Issue: Missing Dependencies

**Error:**
```
ModuleNotFoundError: No module named 'pydantic'
```

**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# Or install specific package
pip install pydantic pyyaml click requests html2text rich jinja2
```

### Issue: Configuration File Not Found

**Error:**
```
FileNotFoundError: config/config.yaml
```

**Solution:**
```bash
# Copy example config
cp config/config.yaml.example config/config.yaml

# Verify file exists
ls -la config/config.yaml
```

### Issue: Environment Variables Not Set

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

# Load .env (if using python-dotenv)
source .env  # Or use python-dotenv to load automatically
```

### Issue: Obsidian Vault Path Doesn't Exist

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

### Issue: IMAP Connection Failed

**Error:**
```
Connection refused
```

**Solution:**
- Verify IMAP server and port are correct
- Check firewall settings
- For Gmail: Enable "Less secure app access" or use App Password
- Test IMAP connection manually:
  ```bash
  # Test IMAP connection (if tools available)
  telnet imap.gmail.com 993
  ```

### Issue: Invalid YAML Syntax

**Error:**
```
yaml.scanner.ScannerError: while scanning
```

**Solution:**
- Validate YAML syntax using online YAML validator
- Check for:
  - Missing colons after keys
  - Incorrect indentation (use spaces, not tabs)
  - Unclosed quotes
  - Invalid characters

### Issue: Account Config Not Found (V4)

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

### Issue: Permission Denied

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
- Check file/directory permissions
- Ensure log directory is writable: `chmod 755 logs`
- Ensure vault directory is writable: `chmod 755 /path/to/vault`

### Getting More Help

- Check [V4 Troubleshooting Guide](v4-troubleshooting.md) for detailed solutions
- Review logs: `logs/agent.log`
- Enable debug mode: `python main.py process --debug`
- See [V4 Configuration Reference](v4-configuration-reference.md) for configuration details

---

## Next Steps

After installation and setup:
- See [Configuration Reference](v4-configuration-reference.md) for detailed configuration options
- See [Quick Start Guide](v4-quick-start.md) for a minimal working example
- See [Migration Guide](v4-migration-guide.md) if upgrading from V3

---

## Related Documentation

- [V4 Configuration Reference](v4-configuration-reference.md)
- [V4 Quick Start](v4-quick-start.md)
- [V4 Migration Guide](v4-migration-guide.md)
- [V4 Troubleshooting](v4-troubleshooting.md)
