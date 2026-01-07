# Troubleshooting Guide

This guide covers common issues and their solutions when using the email agent.

---

## Table of Contents

- [Configuration Issues](#configuration-issues)
- [IMAP Connection Problems](#imap-connection-problems)
- [AI Processing Errors](#ai-processing-errors)
- [Tagging Issues](#tagging-issues)
- [Performance Issues](#performance-issues)
- [Logging and Debugging](#logging-and-debugging)

---

## Configuration Issues

### Missing Environment Variables

**Error:**
```
ConfigError: Missing required env vars: ['IMAP_PASSWORD']
```

**Solution:**
1. Ensure `.env` file exists in the project root
2. Add the required variables:
   ```bash
   IMAP_PASSWORD=your-password-here
   OPENROUTER_API_KEY=your-api-key-here
   ```
3. Verify the variable names match those in `config/config.yaml`:
   - `imap.password_env` should match the IMAP password variable name
   - `openrouter.api_key_env` should match the API key variable name

### Config File Not Found

**Error:**
```
ConfigError: Config file not found: config/config.yaml
```

**Solution:**
1. Copy the example config:
   ```bash
   cp config/config.yaml.example config/config.yaml
   ```
2. Edit `config/config.yaml` with your settings
3. Or specify a custom path: `python main.py --config /path/to/config.yaml`

### Invalid YAML Syntax

**Error:**
```
ConfigError: YAML parse error: ...
```

**Solution:**
1. Validate your YAML syntax (use an online YAML validator)
2. Check for:
   - Missing colons after keys
   - Incorrect indentation (use spaces, not tabs)
   - Unclosed quotes
   - Special characters that need escaping

---

## IMAP Connection Problems

### Processing Old Emails Instead of New Ones

**Symptom:** When using `--limit 1`, the oldest email is processed instead of the newest.

**Explanation:**
- Emails are fetched in UID order (1, 2, 3... N), which is chronological
- Without sorting, `--limit 1` would process the oldest email (UID 1)

**Solution:**
- The code automatically sorts emails by date (newest first) before limiting
- `--limit 1` now processes the **newest** unprocessed email
- This ensures recent emails are prioritized

**If you still see old emails:**
- Check that emails have valid `Date` headers
- Emails without dates are placed at the end of the sorted list
- Verify the date parsing in logs (enable `--debug`)

### UID vs Sequence Number Mismatch

**Symptom:** Tags are applied to the wrong emails (e.g., tag appears on email A but note was created for email B).

**Explanation:**
- IMAP has two identifier systems: UIDs (stable) and sequence numbers (can change)
- Mixing them causes mismatches where tags are applied to wrong emails

**Solution:**
- The code uses **UID-based operations** throughout:
  - `imap.uid('SEARCH', ...)` - Returns UIDs
  - `imap.uid('FETCH', ...)` - Fetches by UID
  - `imap.uid('STORE', ...)` - Tags by UID
- This ensures consistency between fetching and tagging

**Verification:**
- Check logs for UID values at each step
- All UIDs should match between fetch, processing, and tagging
- Use `--debug` to see detailed UID logging

### Authentication Failed

**Error:**
```
IMAPConnectionError: IMAP login failed: ...
```

**Solutions:**

1. **Verify credentials:**
   - Check username and password in `.env`
   - Ensure password doesn't have extra spaces or newlines

2. **App-specific passwords:**
   - Some providers (Gmail, Outlook) require app-specific passwords
   - Generate one in your account security settings
   - Use the app password instead of your regular password

3. **Enable IMAP access:**
   - Gmail: Settings → Forwarding and POP/IMAP → Enable IMAP
   - Outlook: Settings → Mail → Sync email → Enable IMAP
   - Other providers: Check account settings for IMAP/POP access

4. **Two-factor authentication:**
   - If 2FA is enabled, you must use an app-specific password
   - Regular passwords won't work with 2FA enabled

### Connection Timeout

**Error:**
```
IMAPConnectionError: IMAP connection failed: ...
```

**Solutions:**

1. **Check server and port:**
   - Verify `imap.server` and `imap.port` in config
   - Common ports: 993 (SSL), 143 (STARTTLS)
   - Try both ports if one doesn't work

2. **Firewall/Network:**
   - Ensure your firewall allows outbound connections on IMAP ports
   - Check if your network blocks IMAP (some corporate networks do)
   - Try from a different network to isolate the issue

3. **SSL/TLS issues:**
   - If using port 993, ensure SSL is enabled
   - If using port 143, the code automatically uses STARTTLS
   - Some servers require specific SSL/TLS versions

### Wrong Version Number (SSL Error)

**Error:**
```
[SSL: WRONG_VERSION_NUMBER] wrong version number
```

**Solution:**
- This happens when trying SSL on a STARTTLS server
- The code handles this automatically
- Ensure `port: 143` in config for STARTTLS servers
- The code will detect and use STARTTLS automatically

### Server Doesn't Support KEYWORDS

**Error:**
```
IMAPKeywordsNotSupportedError: Server does not support KEYWORDS
```

**Note:** This error is deprecated. The codebase now uses FLAGS instead of KEYWORDS for better compatibility. If you see this error, update to the latest version.

**Solution:**
- The code automatically uses FLAGS (which all IMAP servers support)
- Custom flags work the same way as keywords
- See [docs/imap-keywords-vs-flags.md](imap-keywords-vs-flags.md) for details

---

## AI Processing Errors

### Unauthorized (401)

**Error:**
```
OpenRouterAPIError: HTTP 401: Unauthorized
```

**Solution:**
1. Verify your OpenRouter API key in `.env`
2. Check that the key starts with `sk-or-v1-`
3. Ensure there are no extra spaces or newlines in the key
4. Get a new API key from https://openrouter.ai/ if needed

### Rate Limit Exceeded (429)

**Error:**
```
OpenRouterAPIError: HTTP 429: Rate limit exceeded
```

**Solutions:**

1. **Reduce processing rate:**
   - Lower `max_emails_per_run` in config
   - Add delays between runs in continuous mode
   - Process emails in smaller batches

2. **Wait and retry:**
   - The code automatically retries with exponential backoff
   - Wait a few minutes and try again
   - Check your OpenRouter account for rate limit details

3. **Upgrade API plan:**
   - Consider upgrading your OpenRouter plan for higher rate limits

### Invalid Model

**Error:**
```
OpenRouterAPIError: HTTP 400: Invalid model
```

**Solution:**
1. Check the model name in `config/config.yaml`
2. Verify the model is available on OpenRouter
3. Use a supported model format: `provider/model-name`
4. Examples:
   - `openai/gpt-3.5-turbo`
   - `google/gemini-2.5-flash-lite-preview-09-2025`
   - `anthropic/claude-3-haiku`

### Network/Connection Errors

**Error:**
```
OpenRouterAPIError: Connection timeout
```

**Solution:**
1. Check your internet connection
2. Verify OpenRouter API is accessible: `curl https://openrouter.ai/api/v1/models`
3. Check firewall/proxy settings
4. The code retries automatically, but persistent failures may indicate network issues

---

## Tagging Issues

### Invalid Characters in Flag Name

**Error:**
```
NO [b'[CANNOT] Invalid characters in keyword']
```

**Solution:**
- IMAP servers don't allow brackets `[]` in flag names
- The code uses `AIProcessed` (no brackets) by default
- Ensure `processed_tag` in config doesn't contain brackets or special characters
- Use alphanumeric characters and hyphens/underscores only

### Flags Not Visible in Thunderbird

**Symptom:** Custom flags are applied but not visible in Thunderbird's "Schlagworte" (Tags) view.

**Explanation:**
- Thunderbird's "Schlagworte" view only displays tags from the IMAP KEYWORDS extension
- The code uses FLAGS (which all servers support) instead of KEYWORDS
- Flags are still applied and searchable via IMAP, just not visible in Thunderbird's UI

**Solution:**
- This is a Thunderbird limitation, not a bug
- Flags are functional and searchable
- Use IMAP search commands or other email clients to verify flags
- See [docs/imap-keywords-vs-flags.md](imap-keywords-vs-flags.md) for details

### Tags Not Applied

**Symptom:** Emails are processed but tags aren't appearing.

**Solutions:**

1. **Check logs:**
   ```bash
   tail -f logs/agent.log
   ```
   Look for tagging errors or warnings

2. **Verify IMAP permissions:**
   - Ensure your IMAP account has write permissions
   - Some read-only accounts can't modify flags

3. **Check flag format:**
   - Flags must be valid IMAP flag names (alphanumeric, no special chars)
   - Verify `tag_mapping` in config uses valid flag names
   - **Important:** No hyphens in flag names - use `ObsidianNoteCreated` not `Obsidian-Note-Created`

4. **Test manually:**
   ```bash
   python scripts/test_imap_flags.py
   ```
   This will test flag operations on your server

5. **Verify UID consistency:**
   - The code uses `UID SEARCH` and `UID FETCH` to ensure consistency
   - Tags are applied using `UID STORE` with the same UID
   - If tags appear on wrong emails, check logs for UID mismatches

---

## Performance Issues

### Slow Processing

**Symptom:** Processing takes a long time or hangs.

**Solutions:**

1. **Reduce email body size:**
   - Lower `max_body_chars` in config (default: 4000)
   - Smaller bodies = faster AI processing

2. **Process fewer emails:**
   - Use `--limit N` to process fewer emails per run
   - **Note:** Emails are sorted by date (newest first), so `--limit 1` processes the **newest** email, not the oldest
   - Process in smaller batches

3. **Check network:**
   - Slow IMAP or API connections will slow processing
   - Test network speed to OpenRouter API

4. **Enable debug mode:**
   ```bash
   python main.py --debug
   ```
   Check logs to identify bottlenecks

### High API Costs

**Symptom:** OpenRouter API costs are higher than expected.

**Solutions:**

1. **Use cheaper models:**
   - `openai/gpt-3.5-turbo` is cheaper than `gpt-4`
   - `google/gemini-2.5-flash-lite-preview-09-2025` is very cost-effective

2. **Reduce email body size:**
   - Lower `max_body_chars` reduces token usage
   - Truncation happens automatically

3. **Process fewer emails:**
   - Use `max_emails_per_run` to limit processing
   - Process only new/unprocessed emails

4. **Monitor usage:**
   - Check OpenRouter dashboard for usage statistics
   - Review `logs/analytics.jsonl` for processing counts

---

## Logging and Debugging

### Enable Debug Mode

**Command:**
```bash
python main.py --debug
# or
python main.py --log-level DEBUG
```

**What you'll see:**
- Full email content sent to AI
- Raw AI API responses
- Detailed IMAP operations
- Complete error stack traces
- Step-by-step processing flow

### Check Log Files

**Location:** `logs/agent.log`

**View recent logs:**
```bash
tail -f logs/agent.log
```

**Search for errors:**
```bash
grep ERROR logs/agent.log
```

**View analytics:**
```bash
cat logs/analytics.jsonl
```

### Common Log Messages

**"No unprocessed emails found"**
- Normal: All emails have been processed
- Run again later when new emails arrive

**"Reached max_emails limit"**
- Normal: Processing stopped at configured limit
- Use `--limit N` to process more, or check `max_emails_per_run` in config
- **Note:** Emails are sorted by date (newest first), so the newest emails are processed first

**"AI processing failed for UID X"**
- Email marked with `AIProcessingFailed` flag
- Check logs for specific error
- May be due to API errors, network issues, or invalid email content

### Getting More Help

1. **Check documentation:**
   - [Main README](../README.md)
   - [Module-specific docs](MAIN_DOCS.md)

2. **Review logs:**
   - Enable debug mode
   - Check `logs/agent.log` for detailed errors

3. **Test components:**
   - `python scripts/test_imap_live.py` - Test IMAP connection
   - `python scripts/test_imap_flags.py` - Test flag operations
   - `pytest` - Run test suite

4. **Check configuration:**
   - Verify all required config keys are present
   - Ensure environment variables are set
   - Validate YAML syntax

---

## Still Having Issues?

If you've tried the solutions above and still have problems:

1. **Gather information:**
   - Full error message from logs
   - Configuration (redact sensitive info)
   - Python version: `python --version`
   - Operating system

2. **Check for updates:**
   - Ensure you're using the latest code
   - Check if the issue is a known bug

3. **Create a minimal test case:**
   - Reproduce the issue with minimal configuration
   - Test individual components (IMAP, API, etc.)

4. **Review error handling:**
   - The code includes comprehensive error handling
   - Check if errors are being caught and logged properly
