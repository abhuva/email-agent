# Live End-to-End Test Guide (Task 9.6)

This guide helps you perform a complete live test of the V2 Obsidian integration with real email processing.

## Prerequisites Checklist

Before running the live test, ensure you have:

- [ ] **IMAP credentials** configured in `config/config.yaml` and `.env`
- [ ] **OpenRouter API key** set in `.env` as `OPENROUTER_API_KEY`
- [ ] **Obsidian vault path** configured and directory exists
- [ ] **Summarization prompt file** exists (if using summarization)
- [ ] **Test email** ready in your inbox (unread, or matching your `imap_query`)

## Step 1: Verify Configuration

### 1.1 Check `config/config.yaml`

Ensure these V2 parameters are set:

```yaml
# Required for V2
obsidian_vault_path: '/absolute/path/to/your/obsidian/vault/emails'

# Optional - only if you want summarization
summarization_tags:
  - 'Urgent'  # Or other tags you use
summarization_prompt_path: 'config/summarization_prompt.md'

# Optional - changelog tracking
changelog_path: 'logs/email_changelog.md'

# V2: Primary IMAP query (what emails to process)
imap_query: 'ALL'  # Or your custom query (e.g., 'UNSEEN', 'UNSEEN SENTSINCE 07-Jan-2026')
```

**Important Notes:**
- `imap_query` is combined with idempotency checks automatically: `(user_query NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated" NOT KEYWORD "NoteCreationFailed")`
- Use `SENTSINCE` to filter by sent date (Date header), `SINCE` to filter by received date (INTERNALDATE)
- Date format: `DD-MMM-YYYY` (e.g., `07-Jan-2026`)
- Emails are **sorted by date (newest first)** before processing, so `--limit N` processes the newest N emails

**Important Notes:**
- `obsidian_vault_path` must be an **absolute path** to an **existing directory**
- The directory will be where all email notes are created
- If the directory doesn't exist, the script will fail with a clear error

### 1.2 Check `.env` file

Ensure you have:

```bash
IMAP_PASSWORD=your_imap_password
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 1.3 Verify Obsidian Vault Path

Run this to check if your vault path exists:

```bash
# On Windows PowerShell
Test-Path "C:\path\to\your\obsidian\vault\emails"

# On Linux/Mac
test -d "/path/to/your/obsidian/vault/emails" && echo "Exists" || echo "Missing"
```

**If the directory doesn't exist:**
```bash
# Create it
mkdir -p "/path/to/your/obsidian/vault/emails"
```

### 1.4 Verify Summarization Prompt (if using)

If you have `summarization_tags` configured, ensure the prompt file exists:

```bash
# Check if file exists
Test-Path "config/summarization_prompt.md"  # Windows
test -f "config/summarization_prompt.md" && echo "Exists" || echo "Missing"  # Linux/Mac
```

**If missing, create a basic one:**
```markdown
# Email Summarization Prompt

Please provide a concise summary of this email, including:
- Main topic or purpose
- Key action items (if any)
- Priority level (high/medium/low)

Email content:
```

## Step 2: Prepare Test Email

### 2.1 Create a Test Email

Send yourself an email with:
- **Subject:** Something identifiable like "TEST - Live Test Email"
- **Content:** Some text that will be converted to Markdown
- **Status:** Unread (if using `imap_query: 'UNSEEN'`)

### 2.2 Verify Email is Accessible

The email should:
- Be in the mailbox configured in `config.yaml`
- Match your `imap_query` criteria (e.g., `UNSEEN` for unread)
- Not have the `AIProcessed` tag (or it will be skipped)
- Not have the `ObsidianNoteCreated` tag (or it will be skipped)

## Step 3: Run the Live Test

### 3.1 Run with Limited Emails

Start with a small limit to test safely:

```bash
# Process only 1 email for testing (will process the NEWEST email)
python main.py --limit 1
```

**Important:** Emails are sorted by date (newest first) before limiting, so `--limit 1` will process the **newest** unprocessed email, not the oldest.

Or modify `config.yaml` temporarily:
```yaml
max_emails_per_run: 1
```

### 3.2 Monitor Output

Watch for:
- ✅ **Success messages:** "Successfully created Obsidian note for email UID X"
- ✅ **Tagging confirmation:** "Tagged email UID X with ObsidianNoteCreated"
- ⚠️ **Warnings:** Any warnings about summarization, file writing, etc.
- ❌ **Errors:** Any errors that prevent note creation

### 3.3 Check Logs

Review the log file for detailed information:

```bash
# View recent log entries
tail -n 50 logs/agent.log  # Linux/Mac
Get-Content logs/agent.log -Tail 50  # Windows PowerShell
```

## Step 4: Verify Results

### 4.1 Check Note File Creation

1. **Navigate to your Obsidian vault path:**
   ```bash
   cd "C:\path\to\your\obsidian\vault\emails"  # Windows
   cd "/path/to/your/obsidian/vault/emails"    # Linux/Mac
   ```

2. **List files:**
   ```bash
   ls -lt *.md | head -5  # Linux/Mac (most recent first)
   Get-ChildItem *.md | Sort-Object LastWriteTime -Descending | Select-Object -First 5  # Windows
   ```

3. **Verify file exists and has recent timestamp**

### 4.2 Verify Note Content

Open the created `.md` file and check:

- [ ] **YAML Frontmatter** is present at the top:
  ```yaml
  ---
  subject: "Your Email Subject"
  from: "sender@example.com"
  date: "2024-01-15T10:30:00Z"
  ...
  ---
  ```

- [ ] **Summary Callout** (if summarization was triggered):
  ```markdown
  > [!summary] Summary
  > [Summary text here]
  ```

- [ ] **Original Content** section:
  ```markdown
  # Original Content
  
  [Email body content in Markdown]
  ```

### 4.3 Verify Email Tagging

Check your email client or IMAP flags:

- [ ] Email should have `ObsidianNoteCreated` tag (if note creation succeeded)
- [ ] Email should have `AIProcessed` tag (from V1 classification)
- [ ] Email should have classification tag (`Urgent`, `Neutral`, or `Spam`)

**If note creation failed:**
- Email should have `NoteCreationFailed` tag
- Check logs for error details

### 4.4 Verify Summarization (if applicable)

If your email had a tag matching `summarization_tags`:

- [ ] Summary callout should be present in the note
- [ ] Summary should be relevant to the email content
- [ ] Check logs for "Successfully generated summary" message

## Step 5: Troubleshooting

### Issue: "obsidian_vault_path does not exist"

**Solution:**
1. Create the directory:
   ```bash
   mkdir -p "/path/to/your/obsidian/vault/emails"
   ```
2. Verify the path in `config.yaml` is **absolute** (not relative)
3. On Windows, use forward slashes or escaped backslashes:
   ```yaml
   obsidian_vault_path: 'C:/Users/YourName/Obsidian Vault/emails'
   # OR
   obsidian_vault_path: 'C:\\Users\\YourName\\Obsidian Vault\\emails'
   ```

### Issue: "No emails found"

**Possible causes:**
1. All emails already have `AIProcessed` or `ObsidianNoteCreated` tags
2. `imap_query` doesn't match any emails
3. IMAP connection/authentication failed

**Solution:**
1. Check IMAP connection in logs
2. Verify `imap_query` matches your test email
3. Remove tags from test email to reprocess:
   ```python
   # Use a script to remove tags if needed
   ```

### Issue: "Note creation failed"

**Check logs for specific error:**
- **InvalidPathError:** Vault path doesn't exist or isn't a directory
- **WritePermissionError:** No write permission to vault directory
- **FileWriteError:** General file writing issue

**Solution:**
1. Verify vault path exists and is writable
2. Check file system permissions
3. Ensure disk space is available

### Issue: "Summarization not working"

**Check:**
1. Email has a tag matching `summarization_tags` in config
2. `summarization_prompt_path` file exists
3. OpenRouter API key is valid
4. Check logs for summarization errors

## Step 6: Success Criteria

Your live test is successful if:

✅ **Note file created** in the correct location with proper filename  
✅ **YAML frontmatter** contains correct email metadata  
✅ **Email body** is present and properly formatted as Markdown  
✅ **Summary callout** is present (if summarization was triggered)  
✅ **Email tagged** with `ObsidianNoteCreated`  
✅ **No errors** in logs (warnings are OK if handled gracefully)  
✅ **Note opens correctly** in Obsidian with proper formatting  

## Step 7: Next Steps

After successful live test:

1. **Process more emails:** Increase `max_emails_per_run` or run multiple times
2. **Verify in Obsidian:** Open the vault and check note appearance
3. **Test edge cases:** Empty emails, HTML emails, long emails, etc.
4. **Monitor costs:** Check OpenRouter API usage for summarization
5. **Proceed to Task 10:** Changelog/audit log functionality

## Quick Test Command

For a quick test with minimal setup:

```bash
# 1. Ensure config is set up
# 2. Ensure test email is ready
# 3. Run:
python main.py --limit 1

# 4. Check results:
# - Note file in vault path
# - Email tags in email client
# - Logs for any errors
```

---

**Note:** This live test validates the complete V2 workflow. If everything works, you're ready to proceed with remaining V2 tasks (changelog, analytics updates, etc.).
