# V4 End-to-End Test Setup Guide

**Task:** 19.1  
**Status:** ✅ Complete  
**PDD Reference:** Task 19 - Perform End-to-End Testing

## Overview

This guide helps you set up real test email accounts and secure configuration for V4 end-to-end testing. E2E tests validate the complete email processing pipeline from fetching to note generation using real email accounts and services.

## Prerequisites

Before setting up test accounts, ensure you have:

- [ ] Access to create test email accounts (Gmail, Outlook, or custom IMAP)
- [ ] Ability to configure 2FA and app passwords (if required)
- [ ] Environment variable access (for storing credentials securely)
- [ ] Understanding of V4 configuration system (see `docs/v4-configuration.md`)

## Step 1: Create Test Email Accounts

### 1.1 Account Requirements

For comprehensive E2E testing, create at least:

- **2 test accounts per provider** (Gmail, Outlook, custom IMAP)
- **Accounts with different capabilities** (IMAP, SMTP)
- **Dedicated test accounts** (not production accounts)

### 1.2 Provider-Specific Setup

#### Gmail Test Accounts

1. **Create Gmail account** (or use existing test account)
2. **Enable IMAP:**
   - Go to Gmail Settings > Forwarding and POP/IMAP
   - Enable IMAP access
3. **Enable 2FA:**
   - Go to Google Account > Security
   - Enable 2-Step Verification
4. **Generate App Password:**
   - Go to Google Account > Security > App passwords
   - Select "Mail" and device type
   - Copy the generated 16-character password
5. **IMAP Settings:**
   - Server: `imap.gmail.com`
   - Port: `993` (SSL/TLS)
   - Username: Full email address
   - Password: App password (not regular password)

#### Outlook Test Accounts

1. **Create Outlook account** (or use existing test account)
2. **Enable IMAP:**
   - Go to Outlook Settings > Mail > Sync email
   - Enable IMAP access
3. **Enable 2FA:**
   - Go to Microsoft Account > Security
   - Enable 2-Step Verification
4. **Generate App Password:**
   - Go to Microsoft Account > Security > App passwords
   - Create app password for "Mail"
   - Copy the generated password
5. **IMAP Settings:**
   - Server: `outlook.office365.com`
   - Port: `993` (SSL/TLS)
   - Username: Full email address
   - Password: App password (not regular password)

#### Custom IMAP Test Accounts

1. **Create account** on your custom IMAP server
2. **Configure IMAP access** per provider documentation
3. **Note IMAP settings:**
   - Server: Provider-specific
   - Port: Usually `993` (SSL/TLS) or `143` (STARTTLS)
   - Username: Provider-specific format
   - Password: Provider-specific requirements

## Step 2: Configure Test Account Settings

### 2.1 Inbox Configuration

For each test account, configure inbox settings to avoid interference:

- **Disable spam filters** (or whitelist test senders)
- **Disable forwarding rules** (to prevent email routing)
- **Create test folders/labels** (for organized testing)
- **Clear existing flags** (remove AIProcessed, etc. from test emails)

### 2.2 Rate Limits and Security

- **Verify rate limits** are appropriate for automated testing
- **Configure 2FA** if required by provider
- **Generate app passwords** (use app passwords, not main passwords)
- **Document any special requirements** (IP whitelisting, etc.)

## Step 3: Store Credentials Securely

### 3.1 Environment Variables

Store all credentials in environment variables (never in config files):

```bash
# Gmail Test Account 1
export IMAP_PASSWORD_TEST_GMAIL_1='your-app-password-here'

# Gmail Test Account 2
export IMAP_PASSWORD_TEST_GMAIL_2='your-app-password-here'

# Outlook Test Account 1
export IMAP_PASSWORD_TEST_OUTLOOK_1='your-app-password-here'

# Custom IMAP Test Account
export IMAP_PASSWORD_TEST_CUSTOM_1='your-password-here'
```

### 3.2 .env File (Recommended)

Add credentials to `.env` file (which is gitignored):

```bash
# Test Account Credentials
IMAP_PASSWORD_TEST_GMAIL_1=your-app-password-here
IMAP_PASSWORD_TEST_GMAIL_2=your-app-password-here
IMAP_PASSWORD_TEST_OUTLOOK_1=your-app-password-here
IMAP_PASSWORD_TEST_CUSTOM_1=your-password-here

# OpenRouter API Key (for LLM testing)
OPENROUTER_API_KEY=your-api-key-here
```

## Step 4: Create Account Configuration Files

### 4.1 Account Config Structure

For each test account, create a config file in `config/accounts/`:

```yaml
# config/accounts/test-gmail-1.yaml
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'test-account-1@gmail.com'
  password_env: 'IMAP_PASSWORD_TEST_GMAIL_1'  # References env var
  query: 'UNSEEN'  # Or 'ALL' for testing
  processed_tag: 'AIProcessed'

paths:
  obsidian_vault: '/tmp/test-vault-gmail-1'  # Test vault path

processing:
  max_emails_per_run: 5  # Limit for testing
  importance_threshold: 7
  spam_threshold: 5
```

### 4.2 Template

Use `config/accounts/example-account.yaml` as a template:

```bash
cp config/accounts/example-account.yaml config/accounts/test-gmail-1.yaml
# Edit test-gmail-1.yaml with your test account settings
```

## Step 5: Document Test Accounts

### 5.1 Test Accounts Configuration File

Create `config/test-accounts.yaml` (copy from example):

```bash
cp config/test-accounts.yaml.example config/test-accounts.yaml
```

Edit `config/test-accounts.yaml` to document your test accounts:

```yaml
test_accounts:
  - account_id: "test-gmail-1"
    provider: "Gmail"
    email_address: "test-account-1@gmail.com"
    capabilities:
      - "IMAP"
      - "SMTP"
    password_env: "IMAP_PASSWORD_TEST_GMAIL_1"
    notes: |
      - Requires app password (2FA enabled)
      - IMAP server: imap.gmail.com:993
      - Test mailbox: Use dedicated test folder
```

### 5.2 Security Note

**Never commit actual credentials** to version control. The `test-accounts.yaml` file is for documentation only - it helps testers understand which accounts are available.

## Step 6: Verify Configuration

### 6.1 Test IMAP Connection

Use the test script to verify IMAP connection:

```bash
python scripts/test_imap_live.py
```

Or use pytest to test connection:

```bash
pytest tests/test_e2e_imap.py::TestE2EIMAPConnection -v
```

### 6.2 Verify Account Discovery

Test that accounts are discovered correctly:

```bash
python -c "from src.config_loader import ConfigLoader; loader = ConfigLoader('config'); print(loader.discover_accounts())"
```

### 6.3 Test Account Processing

Test processing a single account:

```bash
python main.py process --account test-gmail-1 --limit 1
```

## Step 7: Test Data Preparation

### 7.1 Send Test Emails

Send test emails to each test account:

- **Plain text emails**
- **HTML emails**
- **Emails with attachments**
- **Emails with complex HTML** (tables, images, etc.)
- **Emails from different senders** (for rule testing)

### 7.2 Test Email Templates

Create reusable test email templates:

- **Subject:** "E2E Test - Plain Text"
- **Subject:** "E2E Test - HTML Content"
- **Subject:** "E2E Test - Blacklist Match"
- **Subject:** "E2E Test - Whitelist Match"

## Step 8: Verify Test Environment

### 8.1 Checklist

Before running E2E tests, verify:

- [ ] All test accounts created and configured
- [ ] All credentials stored in environment variables
- [ ] All account config files created (`config/accounts/*.yaml`)
- [ ] Test accounts documented in `config/test-accounts.yaml`
- [ ] IMAP connections verified for all accounts
- [ ] Test emails sent to test accounts
- [ ] Test vault directories created and writable
- [ ] OpenRouter API key configured (for LLM testing)

### 8.2 Test Account Status

Verify each test account:

```bash
# Check account discovery
python -c "from src.config_loader import ConfigLoader; loader = ConfigLoader('config'); accounts = loader.discover_accounts(); print(f'Discovered accounts: {accounts}')"

# Test connection for each account
for account in test-gmail-1 test-gmail-2 test-outlook-1; do
  echo "Testing $account..."
  python main.py process --account $account --limit 0 --dry-run
done
```

## Security Best Practices

1. **Never commit credentials** - Use environment variables only
2. **Use app passwords** - Don't use main account passwords
3. **Dedicated test accounts** - Never use production accounts
4. **Rotate passwords** - Change test account passwords periodically
5. **Monitor usage** - Watch for suspicious activity on test accounts
6. **Separate test data** - Keep test accounts separate from personal accounts

## Troubleshooting

### Issue: IMAP Connection Fails

**Check:**
- Credentials are correct (app password, not regular password)
- IMAP is enabled in account settings
- Server and port are correct
- Firewall/network allows IMAP connections

### Issue: 2FA Required

**Solution:**
- Enable 2FA in account settings
- Generate app password
- Use app password (not regular password) in environment variable

### Issue: Rate Limits

**Solution:**
- Use dedicated test accounts (not production)
- Space out test runs
- Use test folders to organize emails
- Consider using test email services with higher limits

### Issue: Spam Filters Interfere

**Solution:**
- Disable spam filters for test accounts
- Whitelist test senders
- Use test folders instead of INBOX
- Configure account to allow all test emails

## Next Steps

After completing test account setup:

1. **Proceed to Subtask 19.2:** Set up dedicated end-to-end test environment
2. **Proceed to Subtask 19.3:** Design comprehensive test scenarios
3. **Proceed to Subtask 19.4:** Implement automated E2E test suite

## Related Documentation

- `docs/v4-configuration.md` - V4 configuration system
- `config/test-accounts.yaml.example` - Test accounts template
- `config/accounts/example-account.yaml` - Account config template
- `docs/v3-e2e-tests.md` - V3 E2E test patterns (reference)
