# V4 Quick Start Guide

**Status:** Complete  
**Task:** 20.2  
**Audience:** New Users

---

## Overview

This guide provides the fastest path to get V4 running with a single account. For complete installation instructions, see [V4 Installation & Setup](v4-installation-setup.md).

---

## Quick Installation

### 1. Clone and Install

```bash
# Clone repository
git clone <repository-url>
cd email-agent
git checkout v4-orchestrator

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up Configuration

```bash
# Copy example config
cp config/config.yaml.example config/config.yaml

# Create log directory
mkdir -p logs
```

### 3. Set Environment Variables

Create `.env` file:
```bash
IMAP_PASSWORD=your-imap-password
OPENROUTER_API_KEY=your-api-key
```

---

## Minimal Configuration

Edit `config/config.yaml`:

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
  obsidian_vault: '/path/to/your/vault'
```

**Important:** Create the vault directory:
```bash
mkdir -p /path/to/your/vault
```

---

## First Run

### Verify Configuration

```bash
# Show merged configuration
python main.py show-config
```

### Test with Dry-Run

```bash
# Process emails without side effects
python main.py process --dry-run
```

### Process Emails

```bash
# Process emails (V3 mode - single account)
python main.py process

# Or use V4 mode explicitly
python main.py process --account default
```

---

## Next Steps

- **Multi-Account Setup:** See [V4 Configuration Reference](v4-configuration-reference.md)
- **Rules Configuration:** See [V4 Rule Syntax Guide](v4-rule-syntax-guide.md)
- **Complete Guide:** See [V4 Installation & Setup](v4-installation-setup.md)
- **Troubleshooting:** See [V4 Troubleshooting](v4-troubleshooting.md)

---

## Related Documentation

- [V4 Installation & Setup](v4-installation-setup.md) - Complete installation guide
- [V4 Configuration Reference](v4-configuration-reference.md) - Detailed configuration
- [V4 CLI Usage](v4-cli-usage.md) - Command-line reference
