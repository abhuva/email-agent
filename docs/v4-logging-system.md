# V4 Enhanced Logging System

**Status:** Complete  
**Task:** 12 - Implement Enhanced Logging System  
**Date:** 2025-01-05

---

## Overview

The V4 Enhanced Logging System provides comprehensive, contextual logging for multi-account email processing. It includes centralized configuration, context propagation, structured logging for account lifecycle events, and configuration override tracking.

---

## Architecture

The logging system consists of four main modules:

1. **`src/logging_config.py`** - Centralized logging configuration and initialization
2. **`src/logging_context.py`** - Context management for account_id, correlation_id, etc.
3. **`src/logging_helpers.py`** - Helper functions for structured logging (account lifecycle, config overrides)
4. **`docs/v4-logging-design.md`** - Complete design documentation

---

## Key Features

### 1. Centralized Configuration

All logging is configured through a single initialization point:

```python
from src.logging_config import init_logging

# Initialize with defaults
init_logging()

# Initialize with config file
init_logging(config_path='config/logging.yaml')

# Initialize with runtime overrides
init_logging(overrides={'level': 'DEBUG', 'format': 'json'})
```

### 2. Context-Aware Logging

All log messages automatically include contextual information:
- `correlation_id`: Unique ID for a processing run
- `account_id`: Account identifier being processed
- `job_id`: Job/batch identifier
- `component`: Module/component name
- `environment`: Environment name (production, development, etc.)

### 3. Account Lifecycle Logging

Structured logging for account processing start/end:

```python
from src.logging_helpers import log_account_start, log_account_end
from src.logging_context import with_account_context

with with_account_context(account_id='work', correlation_id='abc-123'):
    log_account_start('work')
    # ... process account ...
    log_account_end('work', success=True, processing_time=10.5)
```

### 4. Configuration Override Logging

Automatic logging of configuration overrides when account-specific configs differ from global:

```python
from src.logging_helpers import log_config_overrides

log_config_overrides(
    overrides={'imap.username': 'work@example.com'},
    account_id='work',
    source='account_config',
    scope='account'
)
```

---

## Configuration

### Configuration File (Optional)

Create `config/logging.yaml`:

```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: plain  # plain or json
  handlers:
    console:
      enabled: true
      level: INFO
    file:
      enabled: true
      path: logs/email_agent.log
      level: INFO
      max_bytes: 10485760  # 10MB
      backup_count: 5
    json_file:
      enabled: false
      path: logs/email_agent.jsonl
      level: INFO
  context:
    include_component: true
    include_environment: true
    default_environment: production
```

### Environment Variables

Override configuration via environment variables:

- `LOG_LEVEL`: Override log level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT`: Override format (plain, json)
- `LOG_FILE`: Override log file path
- `LOG_CONSOLE`: Enable/disable console logging (true/false)
- `LOG_JSON_FILE`: Enable/disable JSON file logging (true/false)
- `LOG_JSON_PATH`: Override JSON log file path

---

## Usage

### Basic Usage

```python
from src.logging_config import init_logging, get_logger

# Initialize logging (first thing in application startup)
init_logging()

# Get a logger (automatically includes context)
logger = get_logger(__name__)
logger.info("This message will include context automatically")
```

### With Account Context

```python
from src.logging_context import with_account_context
from src.logging_helpers import log_account_start, log_account_end

with with_account_context(account_id='work', correlation_id='abc-123'):
    log_account_start('work')
    # ... process account ...
    log_account_end('work', success=True, processing_time=10.5)
```

### Error Logging with Context

```python
from src.logging_helpers import log_error_with_context

try:
    # ... operation ...
except Exception as e:
    log_error_with_context(
        error=e,
        account_id='work',
        correlation_id='abc-123',
        operation='processing'
    )
```

---

## Log Formats

### Plain Text Format

```
2025-01-05 12:34:56 INFO     [abc-123] [work] [orchestrator] Processing account: work
```

### JSON Format

```json
{
  "timestamp": "2025-01-05T12:34:56.789Z",
  "level": "INFO",
  "correlation_id": "abc-123",
  "account_id": "work",
  "component": "orchestrator",
  "message": "Processing account: work"
}
```

---

## Integration Points

### Orchestrator Integration

The `MasterOrchestrator` automatically:
- Generates a correlation ID for each run
- Sets account context for each account being processed
- Logs account processing start/end
- Logs errors with full context

### Configuration Loader Integration

The `ConfigLoader` automatically:
- Logs configuration merge operations
- Logs configuration overrides when account configs differ from global

---

## Security & Privacy

The logging system automatically masks sensitive values:
- Passwords, secrets, tokens, API keys
- Only first and last characters are shown: `p****d`

Sensitive keys are detected by keywords: `password`, `secret`, `token`, `key`, `api_key`, `auth`, `credential`, `passwd`, `pwd`

---

## Testing

Tests are located in:
- `tests/test_logging_config.py` - Configuration and initialization tests
- `tests/test_logging_context.py` - Context management tests

Run tests:
```bash
pytest tests/test_logging_config.py tests/test_logging_context.py -v
```

---

## Design Documentation

For complete design details, see:
- **[v4-logging-design.md](v4-logging-design.md)** - Complete design specification

---

## References

- Python Logging Documentation: https://docs.python.org/3/library/logging.html
- Context Variables (contextvars): https://docs.python.org/3/library/contextvars.html
- PDD V4 Section 3.2: Logging requirements
- Task 12: Enhanced Logging System

---

*This documentation is part of the V4 Enhanced Logging System implementation.*
