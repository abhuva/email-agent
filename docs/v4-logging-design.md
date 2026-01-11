# V4 Enhanced Logging System Design

**Status:** Design Document  
**Task:** 12.1 - Design centralized logging configuration and context schema  
**Date:** 2025-01-05

---

## 1. Overview

This document defines the design for the V4 enhanced logging system that supports multi-account processing with contextual information, configuration override logging, and structured account lifecycle tracking.

---

## 2. Logging Framework

**Framework:** Python's standard `logging` library with structured JSON formatter support

**Rationale:**
- Standard library, no external dependencies
- Well-tested and widely used
- Supports filters, formatters, and handlers
- Can be extended with JSON formatting for structured logs

---

## 3. Log Format

**Format Options:**
1. **Plain Text (Default):** Human-readable format for console and development
2. **JSON (Optional):** Structured format for log aggregation tools (ELK, Splunk, etc.)

**Plain Text Format:**
```
%(timestamp)s %(levelname)-8s [%(correlation_id)s] [%(account_id)s] [%(component)s] %(message)s
```

**JSON Format:**
```json
{
  "timestamp": "2025-01-05T12:34:56.789Z",
  "level": "INFO",
  "correlation_id": "abc-123-def",
  "account_id": "work",
  "job_id": "job-001",
  "component": "orchestrator",
  "message": "Processing account: work",
  "context": {
    "environment": "production",
    "request_id": "req-456"
  }
}
```

---

## 4. Context Schema

**Standard Context Fields:**

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `correlation_id` | string | Unique ID for a processing run/job | Yes |
| `account_id` | string | Account identifier being processed | Conditional* |
| `job_id` | string | Job/batch identifier | No |
| `component` | string | Module/component name (e.g., "orchestrator", "account_processor") | Yes |
| `environment` | string | Environment name (e.g., "production", "development") | No |
| `request_id` | string | Request identifier for API calls | No |

*`account_id` is required when processing account-specific operations, optional for global operations.

**Context Propagation:**
- Context is stored using Python's `contextvars` (for async support) and thread-local storage (for sync code)
- Context automatically propagates to all log records within the same execution context
- Context can be set/cleared using helper functions

---

## 5. Logger Naming Conventions

**Root Logger:** `email_agent`  
**Module Loggers:** `email_agent.<module_name>` (e.g., `email_agent.orchestrator`, `email_agent.account_processor`)

**Child Logger Inheritance:**
- All module loggers inherit from root logger
- Configuration is applied to root logger on startup
- Module loggers automatically inherit handlers, formatters, and log levels

**Example:**
```python
# In src/orchestrator.py
logger = logging.getLogger(__name__)  # Gets 'email_agent.orchestrator'

# In src/account_processor.py
logger = logging.getLogger(__name__)  # Gets 'email_agent.account_processor'
```

---

## 6. Log Levels

**Standard Levels (Python logging):**

| Level | Usage | Examples |
|-------|-------|----------|
| `DEBUG` | Detailed diagnostic information | Function entry/exit, variable values, detailed state |
| `INFO` | General informational messages | Account processing start/end, configuration overrides, normal operations |
| `WARNING` | Warning messages for potentially problematic situations | Configuration defaults used, retry attempts, degraded functionality |
| `ERROR` | Error messages for failures | Processing errors, connection failures, validation errors |
| `CRITICAL` | Critical errors that may cause the application to stop | System failures, unrecoverable errors |

**Usage Guidelines:**
- **DEBUG:** Only enabled during development/debugging, very verbose
- **INFO:** Default level for production, includes all important events
- **WARNING:** Issues that don't prevent operation but should be noted
- **ERROR:** Failures that prevent specific operations but allow continuation
- **CRITICAL:** Failures that may cause application termination

---

## 7. Security & Privacy

**What NOT to Log:**
- Passwords, API keys, tokens, or any secrets
- Full email content (only metadata: UID, sender, subject)
- Personal Identifiable Information (PII) unless necessary and anonymized
- Credit card numbers, SSNs, or other sensitive financial data

**What TO Log:**
- Account identifiers (safe, non-sensitive)
- Email UIDs and metadata (sender, subject, timestamps)
- Processing status and results
- Configuration keys (not values if sensitive)
- Error messages and stack traces (sanitized)

**Sanitization:**
- All log messages should be sanitized before logging
- Use helper functions to mask sensitive data
- Never log full configuration objects that may contain secrets

---

## 8. Configuration Structure

**Configuration File:** `config/logging.yaml` (optional, can use code defaults)

**Example Configuration:**
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

**Environment Variables (Override):**
- `LOG_LEVEL`: Override log level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT`: Override format (plain, json)
- `LOG_FILE`: Override log file path
- `LOG_CONSOLE`: Enable/disable console logging (true/false)

---

## 9. Startup Override Behavior

**Initialization Order:**
1. Application starts
2. Logging initializer is called (first thing in main entrypoint)
3. Existing handlers are cleared
4. New configuration is applied to root logger
5. All subsequent loggers inherit this configuration

**Override Mechanism:**
- `init_logging(config_path=None, overrides=None)` function
- Can override log level, format, handlers at runtime
- Overrides are logged at INFO level for transparency

---

## 10. Account Processing Lifecycle Logging

**Required Log Events:**

1. **Account Processing Start:**
   ```
   INFO: Processing account: {account_id} [correlation_id={correlation_id}]
   ```

2. **Configuration Overrides:**
   ```
   INFO: Configuration override: {key} = {value} (source: {source}) [account_id={account_id}]
   ```

3. **Account Processing End:**
   ```
   INFO: Account '{account_id}' processing complete (success: {success}, time: {time}s) [correlation_id={correlation_id}]
   ```

4. **Account Processing Error:**
   ```
   ERROR: Account '{account_id}' processing failed: {error} [correlation_id={correlation_id}]
   ```

---

## 11. Implementation Plan

1. **Subtask 12.1:** Design (this document) ✅
2. **Subtask 12.2:** Implement startup-time logging override and configuration loader
3. **Subtask 12.3:** Implement contextual logging utilities
4. **Subtask 12.4:** Add structured logging for account lifecycle and configuration overrides
5. **Subtask 12.5:** Refactor existing components to use centralized logging
6. **Subtask 12.6:** Final validation, documentation, and commit

---

## 12. References

- Python Logging Documentation: https://docs.python.org/3/library/logging.html
- Context Variables (contextvars): https://docs.python.org/3/library/contextvars.html
- PDD V4 Section 3.2: Logging requirements
- Existing logging: `src/logger.py`, `src/v3_logger.py`

---

*This design document will be updated as implementation progresses.*
