# V4 Troubleshooting Guide

**Status:** Complete  
**Task:** 20.5  
**Audience:** All Users, Operators, System Administrators

---

## Overview

Comprehensive troubleshooting guide for common V4 issues, including configuration errors, rule syntax errors, CLI errors, and multi-account issues.

This guide consolidates solutions from across the V4 documentation and provides step-by-step troubleshooting procedures.

---

## Common Issues

### Quick Diagnosis

**Before troubleshooting, check:**
1. Python version: `python --version` (should be 3.8+)
2. Dependencies installed: `pip list | grep pydantic`
3. Configuration exists: `ls config/config.yaml`
4. Environment variables set: `echo $IMAP_PASSWORD`
5. Logs available: `tail -f logs/agent.log`

---

## Configuration Errors

### Invalid YAML Syntax

**Error:**
```
yaml.scanner.ScannerError: while scanning
```

**Symptoms:**
- Configuration file fails to load
- YAML parser errors

**Solutions:**
1. **Validate YAML syntax:**
   ```bash
   # Use online YAML validator or Python
   python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
   ```

2. **Common YAML issues:**
   - Missing colons after keys
   - Incorrect indentation (use spaces, not tabs)
   - Unclosed quotes
   - Invalid characters

3. **Fix:**
   - Check indentation (2 spaces per level)
   - Ensure all keys have colons
   - Close all quotes
   - Remove special characters

**Example Fix:**
```yaml
# Bad
imap
  server: 'imap.gmail.com'  # Missing colon

# Good
imap:
  server: 'imap.gmail.com'
```

### Schema Validation Errors

**Error:**
```
ValidationError: Field required: imap.server
```

**Symptoms:**
- Configuration validation fails
- Missing required fields

**Solutions:**
1. **Check required fields:**
   - See [V4 Configuration Schema Reference](v4-config-schema-reference.md)
   - Ensure all required fields are present

2. **Common missing fields:**
   - `imap.server` (required)
   - `imap.username` (required)
   - `paths.obsidian_vault` (required)
   - `classification.model` (required)

3. **Fix:**
   - Add missing required fields
   - Check field names match schema exactly

### Missing Required Fields

**Error:**
```
ValidationError: Field required: <field>
```

**Solutions:**
1. **Review schema:**
   - Check [V4 Configuration Reference](v4-configuration-reference.md)
   - Identify required fields

2. **Add missing fields:**
   ```yaml
   # Add required field
   imap:
     server: 'imap.gmail.com'  # Required
     username: 'user@gmail.com'  # Required
   ```

### Configuration Merge Issues

**Error:**
```
Configuration merge failed
```

**Symptoms:**
- Account config not merging correctly
- Unexpected configuration values

**Solutions:**
1. **Understand merge strategy:**
   - Dictionaries: Deep merged
   - Lists: Completely replaced
   - Primitives: Overwritten

2. **Check account config:**
   ```bash
   python main.py show-config --account work --with-sources
   ```

3. **Verify merge:**
   - Check which values are overridden
   - Ensure account config only specifies differences

---

## Rule Syntax Errors

### Invalid Rule Format

**Error:**
```
InvalidRuleError: Missing required field: action
```

**Solutions:**
1. **Check rule structure:**
   - Required fields: `trigger`, `value`, `action`
   - Whitelist also requires: `score_boost`

2. **Validate rule format:**
   ```yaml
   # Blacklist rule
   - trigger: "sender"
     value: "spam@example.com"
     action: "drop"
   
   # Whitelist rule
   - trigger: "domain"
     value: "important.com"
     action: "boost"
     score_boost: 20
   ```

### Regex Pattern Errors

**Error:**
```
Invalid regex pattern
```

**Solutions:**
1. **Escape special characters:**
   ```yaml
   # Bad
   value: ".*@example.com"  # Unescaped dot
   
   # Good
   value: ".*@example\\.com"  # Escaped dot
   ```

2. **Test regex patterns:**
   - Use online regex testers
   - Test in Python before using

### Rule Matching Issues

**Symptoms:**
- Rules defined but not matching
- Emails not being dropped/boosted

**Solutions:**
1. **Check pattern matching:**
   - Sender/Subject: Case-insensitive substring matching
   - Domain: Case-insensitive exact matching
   - Regex: Full Python regex support

2. **Test with dry-run:**
   ```bash
   python main.py process --account work --dry-run
   ```

3. **Check rule order:**
   - First matching rule wins
   - Place specific rules before general ones

---

## CLI Errors

### Command Not Found

**Error:**
```
command not found: python main.py
```

**Solutions:**
1. **Check working directory:**
   ```bash
   pwd  # Should be in project root
   ls main.py  # Should exist
   ```

2. **Use correct Python:**
   ```bash
   python3 main.py  # If python doesn't work
   ```

### Invalid Arguments

**Error:**
```
Error: --account and --all are mutually exclusive
```

**Solutions:**
1. **Use only one option:**
   ```bash
   # Bad
   python main.py process --account work --all
   
   # Good
   python main.py process --account work
   # OR
   python main.py process --all
   ```

2. **Check command syntax:**
   ```bash
   python main.py <command> --help
   ```

### Exit Code Issues

**Exit Codes:**
- `0`: Success
- `1`: General error
- `2`: Usage error

**Solutions:**
1. **Check exit code:**
   ```bash
   python main.py process --account work
   echo $?  # Check exit code
   ```

2. **Review error messages:**
   - Check logs: `logs/agent.log`
   - Review error output

---

## Multi-Account Issues

### Account Not Found

**Error:**
```
Account 'work' not found
```

**Solutions:**
1. **Check account config exists:**
   ```bash
   ls config/accounts/work.yaml
   ```

2. **Verify account name:**
   - Account name must match filename (without .yaml)
   - Case-sensitive

3. **Create account config:**
   ```bash
   cp config/accounts/example-account.yaml config/accounts/work.yaml
   ```

### State Isolation Issues

**Symptoms:**
- Data from one account affecting another
- Configuration bleeding between accounts

**Solutions:**
1. **Verify isolation:**
   - Each account uses separate `AccountProcessor` instance
   - Configuration loaded fresh per account

2. **Check configuration:**
   - Ensure account configs are independent
   - Don't rely on shared state

### Configuration Override Issues

**Symptoms:**
- Account config not overriding global config
- Unexpected configuration values

**Solutions:**
1. **Check merge:**
   ```bash
   python main.py show-config --account work --with-sources
   ```

2. **Verify override:**
   - Only specify differences in account config
   - Check merge strategy (dictionaries merged, lists replaced)

---

## IMAP Connection Issues

**Error:**
```
ConnectionError: Failed to connect to IMAP server
```

**Solutions:**
1. **Verify IMAP settings:**
   - Check `imap.server` and `imap.port`
   - Verify `imap.username`

2. **Test connection:**
   ```bash
   # Test IMAP connection (if tools available)
   telnet imap.gmail.com 993
   ```

3. **Check credentials:**
   - Verify environment variable is set
   - Test password manually

4. **Gmail-specific:**
   - Enable "Less secure app access" or use App Password
   - Use App Password for 2FA accounts

5. **Firewall/Network:**
   - Check firewall settings
   - Verify network connectivity
   - Check proxy settings if behind corporate proxy

---

## LLM API Issues

**Error:**
```
APIError: Failed to call OpenRouter API
```

**Solutions:**
1. **Check API key:**
   ```bash
   echo $OPENROUTER_API_KEY
   ```

2. **Verify API key:**
   - Check key is valid
   - Check key has sufficient credits

3. **Check API endpoint:**
   - Verify `openrouter.api_url` is correct
   - Test API endpoint manually

4. **Rate limiting:**
   - Check API rate limits
   - Reduce `max_emails_per_run` if needed

5. **Model availability:**
   - Verify model name is correct
   - Check model is available on OpenRouter

---

## Advanced Troubleshooting

### Debug Mode

**Enable debug logging:**
```bash
# Set debug environment variable
export DEBUG=true

# Or use Python logging
python -c "import logging; logging.basicConfig(level=logging.DEBUG)" main.py process --account work
```

### Log Analysis

**Check logs:**
```bash
# View recent logs
tail -f logs/agent.log

# Search for errors
grep -i error logs/agent.log

# Check account-specific logs
grep "account: work" logs/agent.log
```

### Verbose Logging

**Enable verbose output:**
- Check log level in configuration
- Review `logs/agent.log` for detailed information
- Check `logs/analytics.jsonl` for structured data

---

## Known Issues

### Configuration File Encoding

**Issue:** Configuration files must use UTF-8 encoding.

**Solution:** Ensure files are saved as UTF-8.

### Windows Path Issues

**Issue:** Windows paths may need special handling.

**Solution:** Use forward slashes or raw strings in paths:
```yaml
paths:
  obsidian_vault: 'C:/Users/username/Documents/Vault'
  # OR
  obsidian_vault: 'C:\\Users\\username\\Documents\\Vault'
```

### Environment Variable Loading

**Issue:** Environment variables not loading from `.env` file.

**Solution:** Ensure `python-dotenv` is installed and `.env` file exists.

---

## Getting Help

### Documentation

- [V4 Installation & Setup](v4-installation-setup.md)
- [V4 Configuration Reference](v4-configuration-reference.md)
- [V4 Rule Syntax Guide](v4-rule-syntax-guide.md)
- [V4 CLI Usage](v4-cli-usage.md)
- [V4 Migration Guide](v4-migration-guide.md)

### Logs

- Check `logs/agent.log` for detailed error messages
- Review `logs/analytics.jsonl` for processing metrics

### Testing

- Use `--dry-run` mode to test without side effects
- Validate configuration: `python main.py show-config --account <name>`

---

## Related Documentation

- [V4 Installation & Setup](v4-installation-setup.md) - Installation troubleshooting
- [V4 Configuration Reference](v4-configuration-reference.md) - Configuration details
- [V4 Rule Syntax Guide](v4-rule-syntax-guide.md) - Rule syntax details
- [V4 CLI Usage](v4-cli-usage.md) - CLI reference
