# Complete Guide: Email Agent V2

**Version:** 2.0  
**Last Updated:** January 2026  
**Status:** Production Ready

> **Note for Developers:** For implementation details, module-specific documentation, and project strategy, see [MAIN_DOCS.md](MAIN_DOCS.md).

---

## Table of Contents

1. [Installation and Setup](#1-installation-and-setup)
2. [Configuration Options](#2-configuration-options)
3. [Usage Instructions](#3-usage-instructions)
4. [Obsidian Note Format](#4-obsidian-note-format)
5. [Troubleshooting](#5-troubleshooting)
6. [Phased Rollout Plan](#6-phased-rollout-plan)
7. [Deployment Instructions](#7-deployment-instructions)

---

## 1. Installation and Setup

### 1.1 Prerequisites

**System Requirements:**
- **Python:** 3.8 or higher (Python 3.10+ recommended)
- **Operating System:** Windows, macOS, or Linux
- **Disk Space:** At least 100 MB for the application and dependencies
- **Network:** Internet connection for IMAP and OpenRouter API access

**Required Accounts:**
- IMAP email account (Gmail, Outlook, or any IMAP-compatible provider)
- OpenRouter API account ([Sign up here](https://openrouter.ai/))
- Obsidian vault (for V2 features)

**Required Tools:**
- `git` (for cloning the repository)
- `pip` (Python package manager, usually included with Python)

### 1.2 Installation Steps

#### Step 1: Clone the Repository

```bash
# Clone the repository
git clone <repository-url>
cd email-agent

# Verify you're in the correct directory
ls -la  # Should show main.py, requirements.txt, src/, config/, etc.
```

#### Step 2: Install Python Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
python --version  # Should show Python 3.8+
pip list | grep -E "requests|pyyaml|beautifulsoup4"  # Verify key packages
```

**Expected Output:**
```
requests         2.31.0
pyyaml           6.0.1
beautifulsoup4   4.12.2
html2text        2020.1.16
rich             13.7.0
```

#### Step 3: Set Up Configuration Files

```bash
# Copy example configuration files
cp config/config.yaml.example config/config.yaml
cp .env.example .env  # If .env.example exists

# Create log directory
mkdir -p logs
```

#### Step 4: Configure Your Environment

**Edit `.env` file:**
```bash
# Open .env in your preferred editor
nano .env  # or use vim, code, etc.
```

Add your credentials:
```bash
IMAP_PASSWORD=your-imap-password-here
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

**Important Security Notes:**
- Never commit `.env` to version control
- Use app-specific passwords for email accounts with 2FA enabled
- Keep your OpenRouter API key secure

#### Step 5: Configure `config/config.yaml`

Edit `config/config.yaml` with your settings:

```yaml
imap:
  server: 'imap.gmail.com'  # Your IMAP server
  port: 993                  # 993 for SSL, 143 for STARTTLS
  username: 'your-email@example.com'
  password_env: 'IMAP_PASSWORD'

openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

# V2: Obsidian Integration
obsidian_vault_path: '/path/to/your/obsidian/vault/emails'
```

**For V2 (Obsidian Integration):**
- Ensure the `obsidian_vault_path` directory exists
- The script will fail if the path doesn't exist (safety feature)
- Create the directory if needed: `mkdir -p /path/to/vault/emails`

#### Step 6: Set Up Prompt Files

```bash
# Copy example prompts if they don't exist
cp config/prompt.md.example config/prompt.md
cp config/summarization_prompt.md.example config/summarization_prompt.md  # If exists

# Edit prompts as needed
nano config/prompt.md
```

### 1.3 Verification Steps

**Test 1: Verify Python Installation**
```bash
python --version
# Should output: Python 3.8.x or higher
```

**Test 2: Verify Dependencies**
```bash
python -c "import requests, yaml, bs4, html2text, rich; print('All dependencies installed')"
# Should output: All dependencies installed
```

**Test 3: Verify Configuration**
```bash
python -c "from src.config import ConfigManager; c = ConfigManager('config/config.yaml', '.env'); print('Config loaded successfully')"
# Should output: Config loaded successfully
```

**Test 4: Test IMAP Connection (Optional)**
```bash
python scripts/test_imap_live.py
# Should connect and list mailboxes
```

**Test 5: Run a Dry Run**
```bash
python main.py --limit 1 --debug
# Should process one email (if available) with detailed logging
```

### 1.4 Platform-Specific Notes

**Windows:**
- Use PowerShell or Command Prompt
- Paths use backslashes: `C:\Users\YourName\email-agent`
- Use `python` or `py` command (depending on installation)

**macOS:**
- Use Terminal
- May need to use `python3` instead of `python`
- Install via Homebrew: `brew install python3`

**Linux:**
- Use your distribution's package manager for Python if needed
- May need `python3` instead of `python`
- Ensure `pip3` is available: `sudo apt-get install python3-pip` (Debian/Ubuntu)

---

## 2. Configuration Options

### 2.1 Configuration File Structure

The main configuration file (`config/config.yaml`) uses YAML format. Here's a complete reference:

### 2.2 IMAP Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `imap.server` | string | Required | IMAP server hostname (e.g., `imap.gmail.com`) |
| `imap.port` | integer | `993` | IMAP port (993 for SSL, 143 for STARTTLS) |
| `imap.username` | string | Required | Email address for IMAP login |
| `imap.password_env` | string | `IMAP_PASSWORD` | Environment variable name for password |

**Example:**
```yaml
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'your-email@gmail.com'
  password_env: 'IMAP_PASSWORD'
```

**Common IMAP Servers:**
- **Gmail:** `imap.gmail.com:993`
- **Outlook:** `outlook.office365.com:993`
- **Yahoo:** `imap.mail.yahoo.com:993`
- **Custom:** Check your email provider's documentation

### 2.3 Email Processing Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `imap_query` | string | `'UNSEEN'` | IMAP search query (see examples below) |
| `max_emails_per_run` | integer | `15` | Maximum emails to process per execution |
| `max_body_chars` | integer | `4000` | Maximum characters sent to AI (truncates longer emails) |
| `processed_tag` | string | `'AIProcessed'` | IMAP flag for processed emails |

**IMAP Query Examples:**
```yaml
# Process unread emails (default)
imap_query: 'UNSEEN'

# Process all emails
imap_query: 'ALL'

# Process emails from specific sender
imap_query: 'FROM "sender@example.com"'

# Process emails sent since a date
imap_query: 'SENTSINCE 01-Jan-2026'

# Process emails received since a date
imap_query: 'SINCE 01-Jan-2026'

# Combine criteria (unread emails from today)
imap_query: 'UNSEEN SENTSINCE 07-Jan-2026'

# Process emails with specific subject
imap_query: 'SUBJECT "Important"'
```

**Note:** The query automatically excludes emails with idempotency tags (see `imap_query_exclusions` below).

### 2.4 AI Classification Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt_file` | string | `'config/prompt.md'` | Path to classification prompt file |
| `tag_mapping` | object | See below | Maps AI keywords to IMAP tags |

**Tag Mapping Example:**
```yaml
tag_mapping:
  urgent: 'Urgent'    # AI keyword 'urgent' → IMAP tag 'Urgent'
  neutral: 'Neutral'  # AI keyword 'neutral' → IMAP tag 'Neutral'
  spam: 'Spam'        # AI keyword 'spam' → IMAP tag 'Spam'
```

### 2.5 OpenRouter API Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `openrouter.api_key_env` | string | `OPENROUTER_API_KEY` | Environment variable name |
| `openrouter.api_url` | string | `'https://openrouter.ai/api/v1'` | API endpoint |
| `openrouter.model` | string | `'openai/gpt-3.5-turbo'` | AI model to use |

**Supported Models:**
```yaml
# Cost-effective options
model: 'google/gemini-2.5-flash-lite-preview-09-2025'  # Very fast, low cost
model: 'openai/gpt-3.5-turbo'                          # Balanced

# Higher quality (more expensive)
model: 'openai/gpt-4o-mini'                            # Better quality
model: 'anthropic/claude-3-haiku'                      # High quality
```

### 2.6 V2: IMAP Query Exclusions Configuration (Task 16)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `imap_query_exclusions.exclude_tags` | list | `['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']` | Tags to exclude from IMAP queries |
| `imap_query_exclusions.additional_exclude_tags` | list | `[]` | Additional tags to exclude |
| `imap_query_exclusions.disable_idempotency` | boolean | `false` | Disable idempotency checks (NOT RECOMMENDED) |

**Important:** IMAP flag names must follow RFC3501 - only alphanumeric characters, underscores, and periods are allowed. No hyphens, spaces, or special characters!

**Example Configurations:**
```yaml
# Default (backward compatible - no config needed)
# Uses: ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']

# Custom exclusions
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
    - 'CustomTag'  # Additional custom tag

# Minimal exclusions (only V2 tags)
imap_query_exclusions:
  exclude_tags:
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
  # Note: AIProcessed not excluded (V1 emails can be reprocessed)

# Additional tags
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
  additional_exclude_tags:
    - 'Archived'
    - 'ProcessedByOtherTool'
```

### 2.7 V2: Obsidian Integration Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `obsidian_vault_path` | string | Required | Path to Obsidian vault emails directory |
| `summarization_tags` | list | `['Urgent']` | IMAP tags that trigger summarization |
| `summarization_prompt_path` | string | `'config/summarization_prompt.md'` | Path to summarization prompt |
| `changelog_path` | string | `'logs/email_changelog.md'` | Path to changelog file |

**Example V2 Configuration:**
```yaml
# Obsidian Integration
obsidian_vault_path: '/Users/marc/Documents/Obsidian/emails'

# Only generate summaries for urgent emails (saves API costs)
summarization_tags:
  - 'Urgent'
  # - 'Important'  # Uncomment to also summarize 'Important' emails

# Summarization prompt
summarization_prompt_path: 'config/summarization_prompt.md'

# Changelog location
changelog_path: 'logs/email_changelog.md'
```

### 2.8 Logging Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_file` | string | `'logs/agent.log'` | Path to log file |
| `log_level` | string | `'INFO'` | Log level: DEBUG, INFO, WARNING, ERROR |
| `analytics_file` | string | `'logs/analytics.jsonl'` | Path to analytics file |

### 2.8 Complete Configuration Example

```yaml
# IMAP Configuration
imap:
  server: 'imap.gmail.com'
  port: 993
  username: 'your-email@gmail.com'
  password_env: 'IMAP_PASSWORD'

# Email Processing
imap_query: 'UNSEEN'
max_emails_per_run: 15
max_body_chars: 4000
processed_tag: 'AIProcessed'

# AI Classification
prompt_file: 'config/prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'

# OpenRouter API
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'

# V2: IMAP Query Exclusions (Task 16)
imap_query_exclusions:
  exclude_tags:
    - 'AIProcessed'
    - 'ObsidianNoteCreated'
    - 'NoteCreationFailed'
  additional_exclude_tags: []
  disable_idempotency: false

# V2: Obsidian Integration
obsidian_vault_path: '/path/to/obsidian/vault/emails'
summarization_tags:
  - 'Urgent'
summarization_prompt_path: 'config/summarization_prompt.md'
changelog_path: 'logs/email_changelog.md'

# Logging
log_file: 'logs/agent.log'
log_level: 'INFO'
analytics_file: 'logs/analytics.jsonl'
```

### 2.9 Configuration Validation

The agent validates configuration on startup. Common validation errors:

**Missing Required Path:**
```
ConfigPathError: Obsidian vault path does not exist: /path/to/vault/emails
```
**Solution:** Create the directory: `mkdir -p /path/to/vault/emails`

**Invalid YAML:**
```
ConfigFormatError: YAML parse error: ...
```
**Solution:** Use a YAML validator or check indentation (use spaces, not tabs)

**Missing Environment Variables:**
```
ConfigError: Missing required env vars: ['IMAP_PASSWORD']
```
**Solution:** Add variables to `.env` file

---

## 3. Usage Instructions

### 3.1 Basic Usage

**Run with default configuration:**
```bash
python main.py
```

**Process a specific number of emails:**
```bash
python main.py --limit 5
```

**Enable debug mode:**
```bash
python main.py --debug
```

**Run continuously (not single batch):**
```bash
python main.py --continuous
```

**Use custom configuration:**
```bash
python main.py --config custom-config.yaml --env .env.production
```

### 3.2 Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--config PATH` | Path to YAML config file | `--config config/prod.yaml` |
| `--env PATH` | Path to .env file | `--env .env.prod` |
| `--debug` | Enable debug logging | `--debug` |
| `--log-level LEVEL` | Set log level | `--log-level DEBUG` |
| `--limit N` | Override max emails per run | `--limit 10` |
| `--continuous` | Run continuously | `--continuous` |
| `--version` | Show version | `--version` |
| `--help` | Show help | `--help` |

### 3.3 Daily Workflow

**Morning Routine:**
```bash
# Process new emails (single batch)
python main.py --limit 20

# Check results
tail -20 logs/agent.log
cat logs/email_changelog.md | tail -20
```

**Continuous Monitoring:**
```bash
# Run continuously (processes in batches)
python main.py --continuous

# Monitor in another terminal
tail -f logs/agent.log
```

**Weekly Review:**
```bash
# Process all unread emails
python main.py

# Review analytics
cat logs/analytics.jsonl | tail -10

# Check changelog
cat logs/email_changelog.md
```

### 3.4 Advanced Usage

**Process Historical Emails:**
```yaml
# In config.yaml, change imap_query:
imap_query: 'SENTSINCE 01-Jan-2026'  # Process all emails since date
```

**Target Specific Senders:**
```yaml
imap_query: 'FROM "important@client.com"'
```

**Process and Summarize Only Urgent:**
```yaml
summarization_tags:
  - 'Urgent'  # Only urgent emails get summaries
```

**Custom Processing Limits:**
```bash
# Process 50 emails with debug output
python main.py --limit 50 --debug
```

### 3.5 Output and Results

**Console Output:**
- Progress bar showing email processing
- Summary table with metrics:
  - Total processed
  - Successfully processed
  - Failed
  - Notes created (V2)
  - Summaries generated (V2)
  - Note creation failures (V2)

**Log Files:**
- `logs/agent.log` - Detailed operation log
- `logs/analytics.jsonl` - JSONL analytics data
- `logs/email_changelog.md` - Human-readable audit log (V2)

**Obsidian Notes:**
- Created in `obsidian_vault_path` directory
- Named: `YYYY-MM-DD-HHMMSS - <Subject>.md`
- Contains YAML frontmatter and email content

---

## 4. Obsidian Note Format

### 4.1 Note Structure

Each email note follows this structure:

```markdown
---
subject: Project Alpha - Weekly Update & Action Items
from: client@example.com
to: marc@myteam.com
cc: team@myteam.com
date: 2026-01-07T10:00:00Z
source_message_id: <CAKdfgkj34s...@mail.gmail.com>
tags: [urgent, project-alpha]
---

>[!info]+ Summary
> The client provided a weekly update for Project Alpha. Key action items include updating the deployment script by Monday and sending them the revised mockups.

## Original Content

Hi Marc,

Just wanted to send over the weekly update...
*(...rest of the sanitized email body converted to Markdown...)*
```

### 4.2 YAML Frontmatter Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `subject` | string | Email subject line | `"Project Update"` |
| `from` | string | Sender email address | `"client@example.com"` |
| `to` | list | Recipient email addresses | `["marc@team.com"]` |
| `cc` | list | CC recipients | `["team@team.com"]` |
| `date` | string | ISO 8601 date | `"2026-01-07T10:00:00Z"` |
| `source_message_id` | string | Original Message-ID | `"<abc123@mail.com>"` |
| `tags` | list | IMAP tags applied | `["urgent", "project-alpha"]` |

### 4.3 Summary Section

**When Summaries Are Generated:**
- Only for emails with tags listed in `summarization_tags` config
- Default: Only `Urgent` emails get summaries
- Saves API costs by not summarizing every email

**Summary Format:**
- Uses Obsidian callout syntax: `>[!info]+ Summary`
- Contains AI-generated summary of key points
- May include action items if extracted

**Example:**
```markdown
>[!info]+ Summary
> This email contains a project update with three action items:
> 1. Review the deployment script by Monday
> 2. Send revised mockups to the client
> 3. Schedule follow-up meeting
```

### 4.4 Email Body Content

- HTML emails are converted to clean Markdown
- Images are stripped (not included in notes)
- Attachments are not processed (links may be preserved)
- Original formatting is preserved where possible

### 4.5 Using Notes in Obsidian

**Searching:**
- Use Obsidian's search: `Ctrl+Shift+F` (Windows/Linux) or `Cmd+Shift+F` (macOS)
- Search by sender: `from: client@example.com`
- Search by date: `date: 2026-01-07`
- Search by tag: `tags: urgent`

**Linking:**
- Link to notes from other notes: `[[2026-01-07-100000 - Project Update]]`
- Use YAML frontmatter for filtering in Dataview queries

**Dataview Queries:**
```markdown
```dataview
TABLE subject, from, date
FROM "emails"
WHERE contains(tags, "urgent")
SORT date DESC
```
```

**Organizing:**
- Notes are created in the configured `obsidian_vault_path` directory
- Use Obsidian's folder structure or tags for organization
- Consider creating MOCs (Maps of Content) for project-related emails

### 4.6 Note File Naming

**Format:** `YYYY-MM-DD-HHMMSS - <Sanitized-Subject>.md`

**Examples:**
- `2026-01-07-100000 - Project Update.md`
- `2026-01-07-143022 - Re- Meeting Tomorrow.md`
- `2026-01-07-091500 - Urgent Action Required.md`

**Sanitization:**
- Special characters are removed or replaced
- Long subjects are truncated
- Invalid filename characters are replaced with hyphens

---

## 5. Troubleshooting

For comprehensive troubleshooting information, see the **[Troubleshooting Guide](TROUBLESHOOTING.md)**.

The troubleshooting guide covers:
- **Configuration Issues** - Config file errors, missing environment variables, YAML syntax problems
- **IMAP Connection Problems** - Authentication failures, connection timeouts, SSL/TLS errors, UID vs sequence number issues
- **AI Processing Errors** - API authentication, rate limiting, invalid models
- **Tagging Issues** - Flags not visible in Thunderbird, invalid flag names
- **Performance Issues** - Slow processing, memory usage
- **Logging and Debugging** - How to enable debug mode and interpret logs

### Quick Reference

**Common Issues:**

1. **Config file not found:**
   ```bash
   cp config/config.yaml.example config/config.yaml
   ```

2. **Missing environment variables:**
   - Create `.env` file with `IMAP_PASSWORD` and `OPENROUTER_API_KEY`

3. **IMAP authentication failed:**
   - Use app-specific password if 2FA is enabled
   - Enable IMAP access in your email account settings

4. **API errors:**
   - Verify API key in `.env` file
   - Check rate limits and model availability

For detailed solutions and additional troubleshooting steps, see the [Troubleshooting Guide](TROUBLESHOOTING.md).

### 5.6 Performance Issues

**Problem: Slow processing**
**Solutions:**
1. Reduce `max_body_chars` (smaller = faster)
2. Use `--limit N` to process fewer emails
3. Check network speed to OpenRouter API
4. Use faster model: `google/gemini-2.5-flash-lite-preview-09-2025`

**Problem: High API costs**
**Solutions:**
1. Use cheaper models (gemini-2.5-flash-lite is very cost-effective)
2. Reduce `max_body_chars` to lower token usage
3. Limit `summarization_tags` to only essential emails
4. Monitor usage in OpenRouter dashboard

### 5.7 Debugging Tips

> **See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for comprehensive debugging guidance and solutions.**

**Enable Debug Mode:**
```bash
python main.py --debug
```

**Check Logs:**
```bash
# View recent logs
tail -f logs/agent.log

# Search for errors
grep ERROR logs/agent.log

# View analytics
cat logs/analytics.jsonl | tail -10
```

**Test Components:**
```bash
# Test IMAP connection
python scripts/test_imap_live.py

# Test flag operations
python scripts/test_imap_flags.py

# Run test suite
pytest -v
```

**Common Log Messages:**
- `"No unprocessed emails found"` - Normal, all emails processed
- `"Reached max_emails limit"` - Normal, limit reached
- `"AI processing failed for UID X"` - Check logs for specific error

---

## 6. Phased Rollout Plan

### 6.1 Overview

The V2 rollout follows a phased approach to ensure stability, validate functionality, and manage costs before full deployment.

### 6.2 Phase 1: Alpha Test

**Duration:** 1-2 weeks  
**Scope:** Primary User's personal email account only

**Objectives:**
- Validate core functionality (note creation, summarization)
- Monitor API costs and processing time
- Identify and fix critical bugs
- Validate Obsidian integration

**Success Criteria:**
- >99% note creation success rate
- No critical bugs or data corruption
- API costs within expected range
- Obsidian notes are usable and searchable

**Activities:**
1. Configure agent for personal email account
2. Process small batches (5-10 emails per run)
3. Review generated notes in Obsidian
4. Monitor logs and analytics daily
5. Document any issues or improvements needed

**Rollback Plan:**
- Disable V2 features by removing `obsidian_vault_path` from config
- Agent falls back to V1 behavior (tagging only)

### 6.3 Phase 2: Team Briefing

**Duration:** 1 week  
**Scope:** Team demonstration and training

**Objectives:**
- Set expectations about the tool's purpose
- Demonstrate Obsidian note format and usage
- Train team on searching and linking notes
- Gather feedback and questions

**Key Messages:**
- **This is an additional information source**, not a replacement for email
- **Primary source of truth remains the email server**
- Notes are for quick reference and searchability
- Always verify important information in original emails

**Activities:**
1. Formal team demonstration
2. Show example notes and search capabilities
3. Explain YAML frontmatter and Dataview queries
4. Q&A session
5. Document feedback for future improvements

**Deliverables:**
- Team training materials
- FAQ document
- Best practices guide

### 6.4 Phase 3: Staged Rollout

**Duration:** 2-4 weeks (one inbox per week)  
**Scope:** Shared inboxes, one at a time

**Objectives:**
- Gradually expand to team inboxes
- Monitor performance at scale
- Validate multi-user scenarios
- Ensure no conflicts or data issues

**Rollout Schedule:**
- **Week 1:** First shared inbox (e.g., support@team.com)
- **Week 2:** Second shared inbox (e.g., projects@team.com)
- **Week 3:** Third shared inbox (if applicable)
- **Week 4:** Final shared inboxes

**For Each Inbox:**
1. Configure agent with inbox credentials
2. Process small initial batch (10-20 emails)
3. Review notes and verify accuracy
4. Monitor for 2-3 days
5. Increase batch size if stable
6. Document any issues

**Success Criteria:**
- All inboxes processing successfully
- No performance degradation
- Team using notes effectively
- No critical issues reported

### 6.5 Monitoring and Metrics

**Key Metrics to Track:**
- Note creation success rate (target: >99%)
- Summarization quality (qualitative feedback)
- API costs per email processed
- Processing time per email
- Error rates by category

**Tools:**
- `logs/analytics.jsonl` - Automated metrics
- `logs/email_changelog.md` - Audit trail
- OpenRouter dashboard - API usage
- Team feedback - Qualitative assessment

**Review Schedule:**
- **Daily:** During Phase 1 (Alpha)
- **Weekly:** During Phase 2 (Briefing)
- **Bi-weekly:** During Phase 3 (Staged Rollout)
- **Monthly:** After full rollout

### 6.6 Risk Mitigation

**Risk: Vault Pollution**
- **Mitigation:** Monitor note volume, consider filtering improvements
- **Accepted:** For V2, we accept creating notes for all non-spam emails

**Risk: High API Costs**
- **Mitigation:** Use cost-effective models, limit summarization tags
- **Monitoring:** Track costs in OpenRouter dashboard

**Risk: Data Corruption**
- **Mitigation:** Comprehensive error handling, idempotency tags
- **Recovery:** Original emails remain untouched on server

**Risk: Team Adoption**
- **Mitigation:** Training, clear documentation, gradual rollout
- **Support:** Regular check-ins and Q&A sessions

---

## 7. Deployment Instructions

### 7.1 Production Deployment Checklist

**Pre-Deployment:**
- [ ] All tests passing: `pytest`
- [ ] Configuration validated
- [ ] Environment variables set
- [ ] Obsidian vault path created and accessible
- [ ] Log directories created
- [ ] Backup of existing configuration

**Deployment:**
- [ ] Copy code to production location
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure `config/config.yaml`
- [ ] Set up `.env` with production credentials
- [ ] Test IMAP connection
- [ ] Test OpenRouter API connection
- [ ] Run dry run: `python main.py --limit 1 --debug`

**Post-Deployment:**
- [ ] Monitor first run closely
- [ ] Verify notes are created correctly
- [ ] Check logs for errors
- [ ] Verify changelog is updating
- [ ] Confirm analytics are being recorded

### 7.2 Automated Deployment (Optional)

**Using Cron (Linux/macOS):**
```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/email-agent && /usr/bin/python3 main.py >> logs/cron.log 2>&1

# Run daily at 9 AM
0 9 * * * cd /path/to/email-agent && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

**Using Task Scheduler (Windows):**
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (daily, weekly, etc.)
4. Action: Start a program
5. Program: `python`
6. Arguments: `C:\path\to\email-agent\main.py`
7. Start in: `C:\path\to\email-agent`

**Using systemd (Linux):**
```ini
[Unit]
Description=Email Agent
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/email-agent
ExecStart=/usr/bin/python3 /path/to/email-agent/main.py
StandardOutput=append:/path/to/email-agent/logs/systemd.log
StandardError=append:/path/to/email-agent/logs/systemd.log

[Install]
WantedBy=multi-user.target
```

### 7.3 Continuous Mode

**For 24/7 Processing:**
```bash
# Run continuously (processes in batches)
python main.py --continuous

# Or use a process manager (PM2, supervisor, etc.)
pm2 start main.py --name email-agent --interpreter python3 -- --continuous
```

**Considerations:**
- Monitor resource usage
- Set up log rotation
- Configure alerts for failures
- Regular health checks

### 7.4 Backup and Recovery

**What to Backup:**
- Configuration files (`config/config.yaml`)
- Environment file (`.env`) - store securely
- Log files (optional, for audit)
- Analytics data (optional)

**Recovery:**
- Restore configuration files
- Recreate `.env` with credentials
- Verify paths and permissions
- Test with `--limit 1` before full run

### 7.5 Security Considerations

**Credentials:**
- Never commit `.env` to version control
- Use app-specific passwords for email
- Rotate API keys regularly
- Store credentials securely (password manager)

**File Permissions:**
- Restrict `.env` file: `chmod 600 .env`
- Protect config directory
- Limit log file access

**Network:**
- Use secure IMAP (port 993 with SSL)
- Verify OpenRouter API uses HTTPS
- Consider VPN for sensitive environments

---

## Appendix

### A. Quick Reference

**Common Commands:**
```bash
# Run agent
python main.py

# Process 5 emails with debug
python main.py --limit 5 --debug

# Check logs
tail -f logs/agent.log

# View changelog
cat logs/email_changelog.md

# Run tests
pytest -v
```

**Important Paths:**
- Config: `config/config.yaml`
- Environment: `.env`
- Logs: `logs/agent.log`
- Analytics: `logs/analytics.jsonl`
- Changelog: `logs/email_changelog.md`
- Notes: `{obsidian_vault_path}/`

### B. Support Resources

- **Documentation:** `docs/` directory
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`
- **Main README:** `README.md`
- **Product Design:** `pdd_v2.md`

### C. Version History

- **V2.0** (January 2026): Obsidian integration, conditional summarization, changelog
- **V1.0** (2024): Initial release with email tagging

---

**End of Complete Guide**

For questions or issues, refer to the troubleshooting section or check the logs for detailed error messages.
