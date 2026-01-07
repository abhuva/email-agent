# Live Test Setup Guide

## Current Status

✅ **Ready:**
- IMAP credentials configured
- OpenRouter API key set
- Basic configuration working

❌ **Missing (Required for V2):**
- `obsidian_vault_path` - Path to your Obsidian vault directory

⚠️ **Optional (Recommended):**
- `summarization_tags` - Tags that trigger AI summarization
- `summarization_prompt_path` - Path to summarization prompt file
- `changelog_path` - Path to changelog/audit log file
- `imap_query` - Primary IMAP query (V2, takes precedence over imap_queries)

## Step 1: Add Required V2 Configuration

Add these lines to your `config/config.yaml` file **after** the `openrouter:` section:

```yaml
# V2: Obsidian Integration Configuration
# REQUIRED: Path to the Obsidian vault directory where email notes will be created
# This directory must exist - the script will fail if it doesn't
# Use absolute path (Windows example below, adjust for your system)
obsidian_vault_path: 'C:/Users/Marc Bielert/YourObsidianVault/emails'
# OR on Linux/Mac:
# obsidian_vault_path: '/home/username/obsidian-vault/emails'
```

**Important:**
1. Replace `'C:/Users/Marc Bielert/YourObsidianVault/emails'` with your actual Obsidian vault path
2. The directory must exist (create it if needed)
3. Use forward slashes `/` or escaped backslashes `\\` on Windows
4. The path should point to a subdirectory (e.g., `/emails`) within your vault

## Step 2: Create the Obsidian Vault Directory

Before running the test, create the directory:

```powershell
# Windows PowerShell
New-Item -ItemType Directory -Path "C:\Users\Marc Bielert\YourObsidianVault\emails" -Force
```

Or manually create the folder in Windows Explorer.

## Step 3: Add Optional V2 Configuration (Recommended)

Add these optional sections to enable full V2 features:

```yaml
# V2: List of IMAP tags that trigger AI summarization
# Only emails with these tags will have summaries generated (saves API costs)
# Examples:
#   summarization_tags: ['Urgent', 'Important']
#   summarization_tags: ['Urgent']  # Only urgent emails get summaries
#   summarization_tags: []          # No summarization (base notes only)
summarization_tags:
  - 'Urgent'

# V2: Path to the Markdown prompt file used for email summarization
# This prompt is separate from the classification prompt and is only used
# when an email has a tag matching one in summarization_tags
summarization_prompt_path: 'config/summarization_prompt.md'

# V2: Path to the changelog/audit log file
# This file tracks all processed emails in a Markdown table format
# The file will be created if it doesn't exist
changelog_path: 'logs/email_changelog.md'

# V2: Primary IMAP query (takes precedence over imap_queries if set)
# Examples:
#   imap_query: 'UNSEEN'                    # Unread emails
#   imap_query: 'ALL'                       # All emails
#   imap_query: '(SINCE "01-Jan-2024")'     # Since specific date
#   imap_query: 'FROM "sender@example.com"'  # From specific sender
# The Obsidian-Note-Created exclusion is automatically added to exclude already processed emails
imap_query: 'UNSEEN'
```

## Step 4: Create Summarization Prompt (if using summarization)

If you added `summarization_tags`, create the prompt file:

```powershell
# Copy the example file
Copy-Item config\summarization_prompt.md.example config\summarization_prompt.md
```

Or manually create `config/summarization_prompt.md` with content from `config/summarization_prompt.md.example`.

## Step 5: Verify Configuration

Run the configuration checker:

```powershell
python scripts/check_live_test_config.py
```

You should see:
```
[OK] Configuration is ready for live test!
```

## Step 6: Prepare Test Email

1. Send yourself a test email with:
   - Subject: "TEST - Live Test Email"
   - Content: Some text (can be HTML or plain text)
   - Status: Unread (if using `imap_query: 'UNSEEN'`)

2. Ensure the email:
   - Is in your inbox (marc.bielert@nica.network)
   - Doesn't have `AIProcessed` tag (or it will be skipped)
   - Doesn't have `Obsidian-Note-Created` tag (or it will be skipped)

## Step 7: Run the Live Test

```powershell
# Process only 1 email for testing
python main.py --limit 1
```

Or modify `config.yaml` temporarily:
```yaml
max_emails_per_run: 1
```

Then run:
```powershell
python main.py
```

## Step 8: Verify Results

1. **Check note file:**
   - Navigate to your `obsidian_vault_path` directory
   - Look for a new `.md` file with timestamp and email subject

2. **Check note content:**
   - Open the `.md` file
   - Verify YAML frontmatter at the top
   - Verify email body content
   - Verify summary callout (if summarization was triggered)

3. **Check email tags:**
   - Email should have `Obsidian-Note-Created` tag
   - Email should have `AIProcessed` tag
   - Email should have classification tag (`Urgent`, `Neutral`, or `Spam`)

4. **Check logs:**
   ```powershell
   Get-Content logs/agent.log -Tail 50
   ```

## Example Complete Config

Here's what your complete `config/config.yaml` should look like (with V2 additions):

```yaml
# Example configuration for email-agent
imap:
  server: 'nica-network.netcup-mail.de'
  port: 143
  username: 'marc.bielert@nica.network'
  password_env: 'IMAP_PASSWORD'
imap_queries:
  - 'UNSEEN'
prompt_file: 'config/prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'
processed_tag: 'AIProcessed'
max_body_chars: 4000
max_emails_per_run: 15
log_file: 'logs/agent.log'
log_level: 'INFO'
analytics_file: 'logs/analytics.jsonl'
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

# V2: Obsidian Integration Configuration
obsidian_vault_path: 'C:/Users/Marc Bielert/YourObsidianVault/emails'  # CHANGE THIS!
summarization_tags:
  - 'Urgent'
summarization_prompt_path: 'config/summarization_prompt.md'
changelog_path: 'logs/email_changelog.md'
imap_query: 'UNSEEN'
```

## Troubleshooting

### "obsidian_vault_path does not exist"
- Create the directory first
- Verify the path is absolute (not relative)
- Check for typos in the path

### "No emails found"
- Check that your test email is unread (if using `UNSEEN`)
- Verify the email doesn't have `AIProcessed` or `Obsidian-Note-Created` tags
- Check IMAP connection in logs

### "Note creation failed"
- Check logs for specific error
- Verify write permissions on vault directory
- Ensure disk space is available

## Next Steps

After successful live test:
1. Process more emails (increase `max_emails_per_run`)
2. Verify notes in Obsidian
3. Test edge cases (HTML emails, long emails, etc.)
4. Proceed to Task 10 (changelog functionality)

---

**Need help?** Check `docs/live-test-guide.md` for detailed troubleshooting.
