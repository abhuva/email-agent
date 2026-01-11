# V4 End-to-End Test Environment Setup

**Task:** 19.2  
**Status:** ✅ Complete  
**PDD Reference:** Task 19 - Perform End-to-End Testing

## Overview

This document describes the dedicated end-to-end test environment setup for V4 email processing pipeline tests. The E2E environment mirrors production and includes all services, queues, and databases needed for complete pipeline testing.

## Test Environment Architecture

### Components

The E2E test environment includes:

1. **Email Fetching Service** - IMAP client for fetching emails
2. **Rules Engine** - Blacklist/whitelist rule processing
3. **Content Parser** - HTML to Markdown conversion
4. **LLM Client** - Email classification via OpenRouter API
5. **Note Generator** - Obsidian note creation
6. **Storage** - File system for generated notes
7. **Logging** - Operational logs and analytics

### Test Environment Structure

```
test-environment/
├── config/                    # Test configuration
│   ├── config.yaml            # Global test config
│   ├── accounts/              # Test account configs
│   │   ├── test-gmail-1.yaml
│   │   └── test-gmail-2.yaml
│   ├── blacklist.yaml         # Test blacklist rules
│   └── whitelist.yaml         # Test whitelist rules
├── vaults/                    # Test Obsidian vaults
│   ├── test-gmail-1/          # Account-specific vaults
│   └── test-gmail-2/
├── logs/                      # Test logs
│   ├── agent.log
│   └── analytics.jsonl
└── test-data/                 # Test email data
    └── templates/             # Email templates
```

## Test Environment Configuration

### Global Test Configuration

The test environment uses a minimal global configuration (`config/config.yaml`) with test-safe defaults:

```yaml
imap:
  server: 'imap.example.com'  # Overridden per account
  port: 993
  username: 'test@example.com'  # Overridden per account
  password_env: 'IMAP_PASSWORD'  # Overridden per account
  query: 'UNSEEN'
  processed_tag: 'AIProcessed'

paths:
  template_file: 'config/note_template.md.j2'
  obsidian_vault: '/tmp/test-vault'  # Overridden per account
  log_file: 'logs/agent.log'
  analytics_file: 'logs/analytics.jsonl'

openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'

classification:
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2
  retry_attempts: 3
  retry_delay_seconds: 1
  cost_per_1k_tokens: 0.0001

processing:
  importance_threshold: 8
  spam_threshold: 5
  max_body_chars: 4000
  max_emails_per_run: 15  # Lower for testing

safety_interlock:
  enabled: true
  cost_threshold: 0.10
  skip_confirmation_below_threshold: false
  average_tokens_per_email: 2000
  currency: '$'
```

### Test Account Configuration

Each test account has its own configuration file in `config/accounts/`:

```yaml
# config/accounts/test-gmail-1.yaml
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'test-account-1@gmail.com'
  password_env: 'IMAP_PASSWORD_TEST_GMAIL_1'
  query: 'UNSEEN'
  processed_tag: 'AIProcessed'

paths:
  obsidian_vault: '/tmp/test-vault-gmail-1'
  log_file: 'logs/test-gmail-1.log'
  analytics_file: 'logs/test-gmail-1-analytics.jsonl'

processing:
  max_emails_per_run: 5  # Low limit for testing
  importance_threshold: 7
  spam_threshold: 5
```

### Test Rules Configuration

Test rules files (`config/blacklist.yaml`, `config/whitelist.yaml`) contain rules for testing:

```yaml
# config/blacklist.yaml (test rules)
- trigger: "sender"
  value: "spam@example.com"
  action: "drop"

- trigger: "domain"
  value: "unwanted-domain.com"
  action: "drop"

# config/whitelist.yaml (test rules)
- trigger: "domain"
  value: "important-client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip", "#work"]
```

## Test Data Seeding

### Test Email Templates

Test email templates are defined in `tests/e2e_helpers.py`:

- **Plain Text Email** - Basic text email for simple processing
- **HTML Email** - HTML content for parsing tests
- **Blacklist Match** - Email that matches blacklist rules
- **Whitelist Match** - Email that matches whitelist rules
- **Complex HTML** - Complex HTML with tables, images, links

### Test Data Preparation

Before running E2E tests, prepare test data:

1. **Send Test Emails** to test accounts:
   - Plain text emails
   - HTML emails
   - Emails with attachments
   - Emails matching blacklist rules
   - Emails matching whitelist rules

2. **Verify Email Availability**:
   - Check that test emails are in INBOX
   - Verify emails are unprocessed (no AIProcessed flag)
   - Confirm emails match test query criteria

3. **Prepare Test Rules**:
   - Configure blacklist rules for test scenarios
   - Configure whitelist rules for test scenarios
   - Verify rules match test email senders/domains

## Test Environment Setup

### Automated Setup (via pytest fixtures)

The test environment is automatically set up using pytest fixtures in `tests/conftest_e2e_v4.py`:

- `e2e_test_config_dir` - Creates temporary config directory
- `e2e_test_vault` - Creates temporary vault directory
- `e2e_test_account_config` - Creates test account config
- `e2e_master_orchestrator` - Creates MasterOrchestrator instance

### Manual Setup

For manual testing, set up the environment:

```bash
# 1. Create test config directory
mkdir -p test-env/config/accounts
mkdir -p test-env/vaults
mkdir -p test-env/logs

# 2. Copy config files
cp config/config.yaml.example test-env/config/config.yaml
cp config/accounts/example-account.yaml test-env/config/accounts/test-gmail-1.yaml

# 3. Edit test account config
# Update test-env/config/accounts/test-gmail-1.yaml with test account settings

# 4. Set environment variables
export IMAP_PASSWORD_TEST_GMAIL_1='your-app-password'
export OPENROUTER_API_KEY='your-api-key'

# 5. Verify setup
python -c "from src.config_loader import ConfigLoader; loader = ConfigLoader('test-env/config'); print(loader.discover_accounts())"
```

## Test Environment Verification

### Verify Configuration Loading

```python
from src.config_loader import ConfigLoader

loader = ConfigLoader('test-env/config')
accounts = loader.discover_accounts()
print(f"Discovered accounts: {accounts}")

for account_id in accounts:
    config = loader.load_merged_config(account_id)
    print(f"Account {account_id}: {config['imap']['server']}")
```

### Verify IMAP Connection

```python
from src.account_processor import create_imap_client_from_config
from src.config_loader import ConfigLoader

loader = ConfigLoader('test-env/config')
config = loader.load_merged_config('test-gmail-1')

imap_client = create_imap_client_from_config(config)
imap_client.connect()
print("IMAP connection successful")
imap_client.disconnect()
```

### Verify Test Environment

```bash
# Run E2E test environment verification
pytest tests/test_e2e_v4_environment.py::TestE2EEnvironmentVerification -v
```

## Test Environment Isolation

### Per-Test Isolation

Each E2E test runs in isolation:

- **Separate vault directories** - Each test gets its own vault
- **Separate log files** - Each test writes to its own log
- **Clean state** - Vaults are cleaned before each test
- **No shared state** - Tests don't interfere with each other

### Account Isolation

Multi-account tests ensure complete isolation:

- **Separate AccountProcessor instances** - No shared state
- **Separate IMAP connections** - No connection sharing
- **Separate configurations** - Account-specific configs
- **Separate vaults** - Account-specific vault directories

## Logging and Tracing

### Correlation IDs

Each E2E test run gets a unique correlation ID for tracing:

- **Orchestration correlation ID** - Tracks entire orchestration run
- **Account correlation IDs** - Tracks individual account processing
- **Email correlation IDs** - Tracks individual email processing

### Log Structure

E2E test logs include:

- **Startup logs** - Configuration loading, account discovery
- **Processing logs** - Email fetching, classification, note generation
- **Error logs** - Failures, retries, error handling
- **Summary logs** - Processing statistics, performance metrics

### Log Analysis

Analyze E2E test logs:

```bash
# View orchestration logs
grep "correlation_id" logs/agent.log

# View account-specific logs
grep "test-gmail-1" logs/agent.log

# View error logs
grep "ERROR" logs/agent.log
```

## Test Environment Cleanup

### Automated Cleanup

Pytest fixtures automatically clean up:

- **Test vaults** - Removed after tests (optional, can keep for debugging)
- **Temporary configs** - Removed after tests
- **Test logs** - Can be kept for analysis

### Manual Cleanup

For manual cleanup:

```bash
# Remove test vaults
rm -rf test-env/vaults/*

# Remove test logs (optional)
rm -rf test-env/logs/*

# Keep configs for reuse
# (configs are not removed)
```

## Test Environment Best Practices

1. **Use Test Accounts** - Never use production accounts
2. **Low Limits** - Use low `max_emails_per_run` for testing
3. **Isolated Vaults** - Use separate vaults per test/account
4. **Test Rules** - Use test-specific rules (not production rules)
5. **Clean State** - Start each test with clean state
6. **Monitor Costs** - Watch API costs during testing
7. **Log Analysis** - Review logs after test runs

## Troubleshooting

### Issue: Test Environment Not Set Up

**Solution:**
- Verify pytest fixtures are working
- Check that test config directory exists
- Verify test account configs are present

### Issue: IMAP Connection Fails

**Solution:**
- Check credentials in environment variables
- Verify IMAP server settings
- Test IMAP connection manually

### Issue: Test Vault Not Writable

**Solution:**
- Check vault directory permissions
- Verify vault path is correct
- Ensure vault directory exists

### Issue: Configuration Loading Fails

**Solution:**
- Verify config files are valid YAML
- Check config file paths
- Review config schema validation errors

## Next Steps

After setting up the test environment:

1. **Proceed to Subtask 19.3:** Design comprehensive test scenarios
2. **Proceed to Subtask 19.4:** Implement automated E2E test suite
3. **Proceed to Subtask 19.5:** Execute and iterate on test runs

## Related Documentation

- `docs/v4-e2e-test-setup.md` - Test account setup guide
- `tests/conftest_e2e_v4.py` - E2E test fixtures
- `tests/e2e_helpers.py` - E2E test utilities
- `docs/v4-configuration.md` - V4 configuration system
