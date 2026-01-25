# V4 Multi-Account Best Practices

**Status:** Complete  
**Task:** 20.4  
**Audience:** Operators, System Administrators, Developers  
**PDD Reference:** [pdd_V4.md](pdd_V4.md) Section 2

---

## Overview

Best practices for multi-account deployments, including architecture patterns, configuration strategies, security considerations, and performance optimization.

V4's multi-account architecture provides state isolation and configuration flexibility. This guide covers best practices for deploying and managing multiple email accounts effectively.

---

## Architecture Patterns

### Centralized Deployment

**Pattern:** Single V4 instance processing multiple accounts

**Best For:**
- Personal use (work + personal accounts)
- Small teams
- Accounts with similar processing needs

**Configuration:**
```yaml
# Global config with shared settings
# config/config.yaml
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

# Account-specific configs
# config/accounts/work.yaml
# config/accounts/personal.yaml
```

**Advantages:**
- Simple setup
- Shared resources (API keys, models)
- Easy management

**Considerations:**
- All accounts share same API key
- Processing is sequential (one account at a time)
- Single point of failure

### Per-Account Deployment

**Pattern:** Separate V4 instances per account (not recommended for V4)

**Best For:**
- Complete isolation requirements
- Different processing schedules
- Different API keys per account

**Note:** V4 is designed for centralized multi-account processing. Per-account deployment is not the recommended pattern.

### Hybrid Approach

**Pattern:** Centralized deployment with account-specific configurations

**Best For:**
- Most use cases
- Mix of shared and account-specific settings
- Flexible configuration needs

**Configuration:**
```yaml
# Global: Shared settings
# Account: Account-specific overrides
# Rules: Global rules with account-specific behavior
```

**Advantages:**
- Balance of simplicity and flexibility
- Shared resources where appropriate
- Account-specific customization where needed

---

## Configuration Strategies

### Configuration Sharing

**Principle:** Put shared settings in global config, account-specific settings in account configs.

**Shared Settings (Global Config):**
- OpenRouter API configuration
- Classification models (if shared)
- Processing defaults
- Safety interlock settings
- Rules files (blacklist/whitelist)

**Account-Specific Settings (Account Configs):**
- IMAP server/credentials
- Obsidian vault paths
- Processing thresholds
- Account-specific models

**Example:**
```yaml
# Global: Shared API key and model
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

# Account: Account-specific IMAP and vault
imap:
  server: 'imap.work.com'
  username: 'work@company.com'
paths:
  obsidian_vault: '/path/to/work/vault'
```

### Account-Specific Overrides

**Best Practices:**
- Only specify differences from global config
- Use descriptive account names
- Keep account configs minimal
- Document why overrides exist

**Example:**
```yaml
# config/accounts/work.yaml
# Only specify what differs from global config
imap:
  server: 'imap.work.com'  # Different server
  username: 'work@company.com'  # Different username
paths:
  obsidian_vault: '/path/to/work/vault'  # Different vault
processing:
  importance_threshold: 7  # Lower threshold for work
```

### Configuration Organization

**File Naming:**
- Use descriptive names: `work.yaml`, `personal.yaml`, `client-xyz.yaml`
- Avoid generic names: `account1.yaml`, `test.yaml`
- Use consistent naming convention

**Directory Structure:**
```
config/
├── config.yaml              # Global config
├── accounts/
│   ├── work.yaml           # Work account
│   ├── personal.yaml       # Personal account
│   └── client-abc.yaml     # Client account
├── blacklist.yaml          # Global blacklist rules
└── whitelist.yaml          # Global whitelist rules
```

---

## Account Isolation

### State Isolation

**Principle:** Each account is processed in complete isolation.

**Guaranteed Isolation:**
- Separate `AccountProcessor` instance per account
- No shared mutable state between accounts
- Configuration loaded fresh for each account
- IMAP connections isolated per account

**Best Practices:**
- Don't rely on shared state between accounts
- Each account has its own processing context
- Logs clearly identify which account is being processed

### Configuration Isolation

**Principle:** Account configs don't affect other accounts.

**Isolation Guarantees:**
- Account configs are merged independently
- Changes to one account config don't affect others
- Global config changes affect all accounts

**Best Practices:**
- Test account configs independently
- Use account-specific environment variables for credentials
- Validate each account config separately

### Data Isolation

**Principle:** Generated notes and logs are isolated per account.

**Isolation:**
- Different Obsidian vaults per account (recommended)
- Account-specific log files (optional)
- Separate analytics tracking per account

**Best Practices:**
- Use different vault paths per account
- Consider account-specific log files for large deployments
- Monitor account-specific metrics

---

## Security Considerations

### Credential Management

**Best Practices:**
- Use separate environment variables per account
- Never commit credentials to version control
- Use app-specific passwords for email accounts
- Rotate credentials regularly

**Example:**
```bash
# .env file
IMAP_PASSWORD_WORK=work-password
IMAP_PASSWORD_PERSONAL=personal-password
OPENROUTER_API_KEY=shared-api-key
```

**Account Config:**
```yaml
# config/accounts/work.yaml
imap:
  password_env: 'IMAP_PASSWORD_WORK'  # Account-specific env var
```

### Access Control

**Best Practices:**
- Limit access to configuration files
- Use file permissions to protect credentials
- Restrict access to `.env` file
- Use separate API keys for different environments

**File Permissions:**
```bash
# Protect .env file
chmod 600 .env

# Protect config files
chmod 644 config/config.yaml
chmod 644 config/accounts/*.yaml
```

### Audit Logging

**Best Practices:**
- Enable comprehensive logging
- Log account-specific processing
- Track configuration changes
- Monitor for anomalies

**Logging:**
- Account name in log messages
- Configuration override logging
- Processing statistics per account
- Error tracking per account

---

## Performance Optimization

### Processing Order

**Best Practices:**
- Process high-priority accounts first
- Group accounts by processing time
- Consider account-specific limits

**Example:**
```bash
# Process important accounts first
python main.py process --account work
python main.py process --account personal
```

### Resource Management

**Best Practices:**
- Set appropriate `max_emails_per_run` per account
- Use account-specific processing limits
- Monitor resource usage per account

**Configuration:**
```yaml
# High-volume account: Lower limit
processing:
  max_emails_per_run: 50

# Low-volume account: Higher limit
processing:
  max_emails_per_run: 100
```

### Cost Optimization

**Best Practices:**
- Use cost-effective models for high-volume accounts
- Set appropriate cost thresholds
- Use safety interlock for cost control
- Monitor costs per account

**Configuration:**
```yaml
# High-volume: Cost-effective model
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  cost_per_1k_tokens: 0.0001

# Low-volume: More accurate model
classification:
  model: 'anthropic/claude-3-opus'
  cost_per_1k_tokens: 0.015
```

---

## Maintenance and Monitoring

### Configuration Updates

**Best Practices:**
- Test configuration changes with dry-run
- Update one account at a time
- Document configuration changes
- Version control configuration files

**Workflow:**
```bash
# Test config change
python main.py show-config --account work
python main.py process --account work --dry-run

# Apply change
# Edit config/accounts/work.yaml

# Verify change
python main.py process --account work --dry-run
```

### Monitoring Strategies

**Best Practices:**
- Monitor processing success rates per account
- Track processing times per account
- Monitor cost per account
- Alert on processing failures

**Metrics to Monitor:**
- Emails processed per account
- Processing time per account
- Cost per account
- Error rates per account

### Logging Best Practices

**Best Practices:**
- Use account-specific log context
- Log configuration overrides
- Log processing decisions
- Include account name in all log messages

**Log Structure:**
```
[INFO] Processing account: work
[INFO] Overriding 'imap.server' to 'imap.work.com'
[INFO] Account work: Processed 10 emails
```

---

## Common Patterns

### Pattern 1: Work and Personal Accounts

**Use Case:** Separate work and personal email processing

**Configuration:**
```yaml
# Global: Shared settings
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

# Work account
imap:
  server: 'imap.work.com'
  username: 'work@company.com'
paths:
  obsidian_vault: '/path/to/work/vault'
processing:
  importance_threshold: 7

# Personal account
imap:
  server: 'imap.gmail.com'
  username: 'personal@gmail.com'
paths:
  obsidian_vault: '/path/to/personal/vault'
processing:
  importance_threshold: 9
```

**Usage:**
```bash
# Process work account
python main.py process --account work

# Process personal account
python main.py process --account personal

# Process both
python main.py process --all
```

### Pattern 2: Client Accounts

**Use Case:** Process emails for multiple clients

**Configuration:**
```yaml
# Global: Shared API and model
# Client-specific: IMAP, vault, thresholds

# config/accounts/client-abc.yaml
imap:
  server: 'imap.client-abc.com'
  username: 'support@client-abc.com'
paths:
  obsidian_vault: '/path/to/client-abc/vault'
processing:
  importance_threshold: 6  # Lower threshold for client emails
```

**Best Practices:**
- Use descriptive client names
- Separate vaults per client
- Client-specific processing thresholds
- Client-specific rules (if needed)

### Pattern 3: High-Volume Accounts

**Use Case:** Process high-volume email accounts efficiently

**Configuration:**
```yaml
# High-volume account config
processing:
  max_emails_per_run: 100
  max_body_chars: 2000  # Shorter emails for faster processing

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # Fast model
  cost_per_1k_tokens: 0.0001  # Cost-effective

safety_interlock:
  cost_threshold: 1.00  # Higher threshold
  skip_confirmation_below_threshold: true  # Skip confirmation for small batches
```

**Best Practices:**
- Use fast, cost-effective models
- Set higher processing limits
- Optimize for throughput
- Monitor costs closely

---

## Anti-Patterns to Avoid

### ❌ Don't: Share Credentials Between Accounts

**Bad:**
```yaml
# All accounts use same password_env
imap:
  password_env: 'IMAP_PASSWORD'  # Shared for all accounts
```

**Good:**
```yaml
# Each account has separate password_env
# config/accounts/work.yaml
imap:
  password_env: 'IMAP_PASSWORD_WORK'

# config/accounts/personal.yaml
imap:
  password_env: 'IMAP_PASSWORD_PERSONAL'
```

### ❌ Don't: Duplicate Global Config in Account Configs

**Bad:**
```yaml
# Account config duplicates everything
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
# ... duplicates all global settings
```

**Good:**
```yaml
# Account config only specifies differences
imap:
  server: 'imap.work.com'
  username: 'work@company.com'
```

### ❌ Don't: Use Generic Account Names

**Bad:**
```yaml
# Generic names
config/accounts/account1.yaml
config/accounts/account2.yaml
```

**Good:**
```yaml
# Descriptive names
config/accounts/work.yaml
config/accounts/personal.yaml
config/accounts/client-abc.yaml
```

### ❌ Don't: Ignore State Isolation

**Bad:**
- Assuming state persists between accounts
- Sharing mutable data between accounts
- Relying on global state

**Good:**
- Each account is processed independently
- No shared mutable state
- Configuration loaded fresh per account

### ❌ Don't: Skip Testing

**Bad:**
- Deploying config changes without testing
- Not using dry-run mode
- Not validating configurations

**Good:**
- Always test with dry-run first
- Validate configurations before deploying
- Test one account at a time

---

## Related Documentation

- [V4 Configuration Reference](v4-configuration-reference.md) - Configuration details
- [V4 Migration Guide](v4-migration-guide.md) - Migration considerations
- [V4 Account Processor](v4-account-processor.md) - Technical implementation
