# V3 Logging Integration Guide

**Status:** ✅ Complete (Task 9)  
**Module:** `src/v3_logger.py`  
**Tests:** `tests/test_v3_logger.py`

## Overview

The V3 logging system provides dual logging functionality as specified in PDD Section 7:
1. **Unstructured operational logs** → `agent.log` (via Python logging)
2. **Structured analytics** → `analytics.jsonl` (per-email records with uid, timestamp, status, scores)

**Critical Requirement:** Both logging systems must write for **every processed email**, regardless of success or failure.

## Quick Start

```python
from src.v3_logger import EmailLogger, get_email_logger

# Get logger instance
email_logger = get_email_logger()

# Log email processing
email_logger.log_email_processed(
    uid='12345',
    status='success',
    importance_score=9,
    spam_score=2,
    subject='Important Email'
)
```

## Integration Points

### 1. Email Processing Start

Log when email processing begins:

```python
email_logger.log_email_start(uid='12345', subject='Test Email')
```

### 2. Classification Result

Log classification results:

```python
email_logger.log_classification_result(
    uid='12345',
    importance_score=9,
    spam_score=2,
    is_important=True,
    is_spam=False
)
```

### 3. Email Processing Complete

**MUST be called for every email** (success or failure):

```python
# Success case
email_logger.log_email_processed(
    uid='12345',
    status='success',
    importance_score=9,
    spam_score=2,
    subject='Test Email'
)

# Error case
email_logger.log_email_processed(
    uid='12345',
    status='error',
    importance_score=-1,
    spam_score=-1,
    subject='Test Email',
    error_message='LLM API failed'
)
```

## Integration with Email Processing Workflow

### Example: Integration with V3 Orchestrator (Task 14)

When the V3 orchestrator is implemented, integrate logging as follows:

```python
from src.v3_logger import get_email_logger
from src.decision_logic import ClassificationResult

# Initialize logger once
email_logger = get_email_logger()

# In email processing loop:
for email in emails:
    uid = email['uid']
    subject = email.get('subject', '')
    
    # Log start
    email_logger.log_email_start(uid, subject)
    
    try:
        # ... classification logic ...
        classification_result = decision_logic.classify(llm_response)
        
        # Log classification
        email_logger.log_classification_result(
            uid=uid,
            importance_score=classification_result.importance_score,
            spam_score=classification_result.spam_score,
            is_important=classification_result.is_important,
            is_spam=classification_result.is_spam
        )
        
        # ... note generation, file writing, etc. ...
        
        # Log success (REQUIRED for every email)
        email_logger.log_email_processed(
            uid=uid,
            status='success',
            importance_score=classification_result.importance_score,
            spam_score=classification_result.spam_score,
            subject=subject
        )
        
    except Exception as e:
        # Log error (REQUIRED for every email, even on failure)
        email_logger.log_email_processed(
            uid=uid,
            status='error',
            importance_score=-1,
            spam_score=-1,
            subject=subject,
            error_message=str(e)
        )
```

## Querying Logs

### Query by UID

```python
from src.v3_logger import LogQuery

query = LogQuery()
results = query.query_by_uid('12345')
for entry in results:
    print(f"Status: {entry.status}, Scores: {entry.importance_score}/{entry.spam_score}")
```

### Query by Status

```python
# Get all successful processing
success_results = query.query_by_status('success')

# Get all errors
error_results = query.query_by_status('error')
```

### Query by Date Range

```python
from datetime import datetime, timezone

start = datetime(2024, 1, 1, tzinfo=timezone.utc)
end = datetime(2024, 1, 31, tzinfo=timezone.utc)
results = query.query_by_date_range(start, end)
```

### Get Statistics

```python
stats = query.get_statistics()
print(f"Total: {stats['total']}")
print(f"Success: {stats['success_count']}")
print(f"Errors: {stats['error_count']}")
print(f"Avg Importance: {stats['avg_importance_score']:.1f}")
```

## Configuration

The logging system uses the `settings.py` facade:

- `settings.get_log_file()` → Operational log file path (default: `logs/agent.log`)
- `settings.get_analytics_file()` → Analytics JSONL file path (default: `logs/analytics.jsonl`)

Both paths are configured in `config.yaml`:

```yaml
paths:
  log_file: 'logs/agent.log'
  analytics_file: 'logs/analytics.jsonl'
```

## Log File Management

The `LogFileManager` class handles:
- Automatic directory creation
- Log file rotation (when files exceed 10MB)
- Thread-safe operations

Log rotation creates backup files:
- `analytics.jsonl.1` (most recent backup)
- `analytics.jsonl.2` (older backup)
- ... up to 5 backups

## Structured Analytics Format

Each line in `analytics.jsonl` is a JSON object:

```json
{"uid": "12345", "timestamp": "2024-01-01T12:00:00Z", "status": "success", "importance_score": 9, "spam_score": 2}
{"uid": "12346", "timestamp": "2024-01-01T12:01:00Z", "status": "error", "importance_score": -1, "spam_score": -1}
```

**Fields:**
- `uid`: Email UID (string)
- `timestamp`: ISO 8601 timestamp (string)
- `status`: "success" or "error" (string)
- `importance_score`: 0-10 or -1 for errors (integer)
- `spam_score`: 0-10 or -1 for errors (integer)

## Operational Logs Format

Operational logs use standard Python logging format:

```
2024-01-01T12:00:00 INFO [msg-id] Email processed: UID 12345 'Test Email' | Importance: 9/10, Spam: 2/10
2024-01-01T12:01:00 ERROR [msg-id] Email processing failed: UID 12346 'Failed Email': LLM API error
```

## Error Handling

The logging system is designed to be resilient:

- **Analytics write failures** are logged but don't stop processing
- **Operational log failures** are logged but don't stop processing
- **File system errors** are caught and logged
- **Thread-safe operations** prevent race conditions

## Testing

Run the test suite:

```bash
pytest tests/test_v3_logger.py -v
```

**19 tests** covering:
- EmailLogEntry serialization
- AnalyticsWriter operations
- EmailLogger functionality
- LogQuery operations
- Integration workflows

## PDD Alignment

This module implements:

- **PDD Section 7**: Non-Functional Requirements (Observability)
  - ✅ Unstructured operational logs to `agent.log`
  - ✅ Structured analytics to `analytics.jsonl` with fields: uid, timestamp, status, scores
  - ✅ Both systems write for every processed email
  - ✅ Log entries created regardless of processing success or failure

## Related Documentation

- [PDD Section 7](../pdd.md#7-non-functional-requirements-nfrs--security) - Observability requirements
- [V3 Configuration Guide](v3-configuration.md) - Configuration system
- [V3 Decision Logic](v3-decision-logic.md) - Classification results format
