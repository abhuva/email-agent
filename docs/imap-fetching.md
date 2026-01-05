# IMAP Email Fetching Module

## Overview
This module handles connecting to an IMAP server, searching and fetching emails according to user configuration, excluding already processed emails, and parsing their content for downstream AI processing.

## Components
- **connect_imap**: Securely connects with credentials (from .env/config) using SSL; robust error and logging.
- **load_imap_queries**: Loads list or single-string IMAP search queries from config.yaml.
- **search_emails_excluding_processed**: Executes queries and ensures [AI-Processed]-tagged messages are excluded.
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

---
This file updated after every major change to IMAP code or tests.