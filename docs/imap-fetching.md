# IMAP Email Fetching Module

## Overview
This module handles connecting to an IMAP server, searching and fetching emails according to user configuration, excluding already processed emails, and parsing their content for downstream AI processing.

*Return to main doc: [README.md](../README.md) for project summary, guidance, and orientation.*

## Components
- **connect_imap**: Securely connects with credentials (from .env/config) using SSL; robust error and logging.
- **load_imap_queries**: Loads list or single-string IMAP search queries from config.yaml.
- **search_emails_excluding_processed**: Executes queries and ensures AIProcessed-tagged messages are excluded.
- **fetch_and_parse_emails**: Extracts subject, sender, date, and plain text body even from multipart; safe header decoding.
- **fetch_emails (orchestrator)**: End-to-end workflow; handles retries, context management, connection/disconnection, and robust logging.

## Error Handling
- Custom exceptions (IMAPConnectionError, IMAPFetchError) for fine-grained error handling.
- Retries and backoff ensure resilience to transient failures; logs every step or failure.

## Test Strategy
- Mocked imaplib and email objects for fast, reliable, non-networked testing.
- Test configuration covers every function and most branches, including TDD for error and retry logic.

## Usage Example
```python
from src.imap_connection import fetch_emails
emails = fetch_emails(host, user, pw, ['UNSEEN', 'FROM "boss@example.com"'])
for em in emails:
    print(em['subject'], em['body'])
```

## Email Client Compatibility

### IMAP FLAGS vs KEYWORDS Extension

This implementation uses **IMAP FLAGS** (not the KEYWORDS extension) for tagging emails. FLAGS are supported by all IMAP servers, making this approach universally compatible.

**Flag Naming:**
- Custom flags must NOT use brackets: use `AIProcessed` not `[AI-Processed]`
- Flags are case-sensitive
- Server may reject flags with special characters

### Thunderbird Compatibility Note

**Known Limitation:** Thunderbird's "Schlagworte" (Keywords) view may not display custom IMAP flags, even though they are:
- ✅ Stored correctly on the server
- ✅ Visible in webmail clients
- ✅ Searchable via IMAP (`KEYWORD "AIProcessed"`)
- ✅ Functional for excluding processed emails

**Why:** Thunderbird's Keywords view primarily shows:
- System flags (`\Seen`, `\Flagged`, etc.)
- KEYWORDS extension tags (requires server support)

Since most servers (including netcup-mail) don't support the KEYWORDS extension, custom FLAGS may not appear in Thunderbird's Keywords view, but they are fully functional.

**Workarounds:**
- Check message Properties → Flags tab
- Use IMAP search: Edit → Find → Search Messages → `KEYWORD "AIProcessed"`
- Flags work correctly for processing logic regardless of Thunderbird display

**Verified Working:**
- ✅ netcup-mail webmail: Shows flags as "Markierung"
- ✅ IMAP search: Finds tagged emails correctly
- ✅ Email processing: Excludes processed emails correctly

---
This file updated after every major change to IMAP code or tests.