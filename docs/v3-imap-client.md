# V3 IMAP Client Module

**Status:** ✅ Complete (Task 3)  
**Module:** `src/imap_client.py`  
**Tests:** `tests/test_imap_connection.py` (may need V3-specific tests)

## Overview

The V3 IMAP client module provides a clean, modular interface for IMAP operations. It replaces direct IMAP connection code with a V3-compliant implementation that uses the settings.py facade for all configuration access.

This module handles:
- IMAP server connection and authentication
- Email retrieval by UID
- Batch email retrieval for unprocessed messages
- IMAP flag management
- Processed email tracking

## Architecture

```
ImapClient
  ├── connect() → IMAP connection
  ├── get_email_by_uid(uid) → Single email
  ├── get_unprocessed_emails() → Batch emails
  ├── set_flag(uid, flag) → Flag management
  ├── has_flag(uid, flag) → Flag checking
  └── disconnect() → Cleanup
```

## Configuration

IMAP settings are configured in `config.yaml`:

```yaml
imap:
  server: 'imap.example.com'
  port: 143
  username: 'your-email@example.com'
  password_env: 'IMAP_PASSWORD'  # Environment variable name
  query: 'ALL'
  processed_tag: 'AIProcessed'
```

Access via settings facade:
```python
from src.settings import settings

server = settings.get_imap_server()
port = settings.get_imap_port()
username = settings.get_imap_username()
password = settings.get_imap_password()  # Loads from env var
query = settings.get_imap_query()
processed_tag = settings.get_imap_processed_tag()
```

## Usage

### Basic Usage

```python
from src.imap_client import ImapClient

# Create client
client = ImapClient()

# Connect to server
client.connect()

# Get unprocessed emails
emails = client.get_unprocessed_emails()
for email in emails:
    print(f"UID: {email['uid']}, Subject: {email['subject']}")

# Disconnect
client.disconnect()
```

### Get Email by UID

```python
client = ImapClient()
client.connect()

# Fetch specific email
email = client.get_email_by_uid('12345')
print(f"Subject: {email['subject']}")
print(f"From: {email['from']}")
print(f"Body: {email['body']}")

client.disconnect()
```

### Flag Management

```python
client = ImapClient()
client.connect()

# Check if email is processed
if client.has_flag('12345', 'AIProcessed'):
    print("Email already processed")

# Set processed flag
client.set_flag('12345', 'AIProcessed')

# Check processed status
is_processed = client.is_processed('12345')

client.disconnect()
```

### Context Manager Usage

```python
from src.imap_client import ImapClient

# Use as context manager (auto-disconnect)
with ImapClient() as client:
    client.connect()
    emails = client.get_unprocessed_emails()
    # Process emails...
    # Auto-disconnects on exit
```

## Key Methods

### Connection Management

- `connect()`: Establish IMAP connection
- `disconnect()`: Close IMAP connection
- `__enter__()` / `__exit__()`: Context manager support

### Email Retrieval

- `get_email_by_uid(uid: str)`: Fetch specific email by UID
- `get_unprocessed_emails()`: Get all unprocessed emails (excludes processed_tag)
- `search_emails(query: str)`: Search emails with custom query

### Flag Management

- `set_flag(uid: str, flag: str)`: Set IMAP flag on email
- `clear_flag(uid: str, flag: str)`: Clear IMAP flag from email
- `has_flag(uid: str, flag: str)`: Check if email has flag
- `is_processed(uid: str)`: Check if email has processed_tag

## Email Format

Emails are returned as dictionaries with the following structure:

```python
{
    'uid': '12345',
    'subject': 'Email Subject',
    'from': 'sender@example.com',
    'to': ['recipient@example.com'],
    'date': '2024-01-15T14:30:22Z',
    'body': 'Email body text...',
    'html_body': '<html>...</html>',  # If available
    'attachments': []  # List of attachment info
}
```

## Error Handling

The module defines custom exceptions:

- `IMAPClientError`: Base exception for IMAP client errors
- `IMAPConnectionError`: Connection or authentication failures
- `IMAPFetchError`: Email fetching or operation failures

**Example:**
```python
from src.imap_client import ImapClient, IMAPConnectionError

try:
    client = ImapClient()
    client.connect()
except IMAPConnectionError as e:
    print(f"Connection failed: {e}")
```

## Processed Email Tracking

The module tracks processed emails using IMAP flags:

1. **Check if processed**: `client.is_processed(uid)`
   - Checks for `processed_tag` flag (default: 'AIProcessed')

2. **Get unprocessed emails**: `client.get_unprocessed_emails()`
   - Automatically excludes emails with `processed_tag`
   - Uses IMAP search query: `NOT FLAG processed_tag`

3. **Mark as processed**: `client.set_flag(uid, processed_tag)`
   - Sets the processed flag after successful processing

## Integration with Settings Facade

All configuration is accessed through the settings facade:

```python
from src.settings import settings

class ImapClient:
    def __init__(self):
        # Load configuration via facade
        self._server = settings.get_imap_server()
        self._port = settings.get_imap_port()
        self._username = settings.get_imap_username()
        self._password = settings.get_imap_password()
        self._query = settings.get_imap_query()
        self._processed_tag = settings.get_imap_processed_tag()
```

**No direct YAML access** - all configuration comes through the facade.

## Differences from V2

### V2 (Old)
- Direct `ConfigManager` access
- Mixed connection and processing logic
- Less structured error handling

### V3 (New)
- Settings facade for configuration
- Clean separation of concerns
- Structured error handling
- Context manager support

## Testing

Run IMAP tests:
```bash
pytest tests/test_imap_connection.py -v
```

For live testing:
```bash
python scripts/test_imap_live.py
```

## PDD Alignment

This module implements:
- **PDD Section 3.1**: IMAP configuration structure
- **PDD Section 5.4**: Modular structure (`src/imap_client.py`)
- **PDD Section 2**: Settings facade pattern

## Reference

- **PDD Specification**: `pdd.md` Sections 3.1, 5.4
- **Module Code**: `src/imap_client.py`
- **Tests**: `tests/test_imap_connection.py`
- **Configuration**: `docs/v3-configuration.md`
- **Settings Facade**: `src/settings.py`
- **Related**: `docs/imap-fetching.md` (general IMAP documentation)
