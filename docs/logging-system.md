# Logging System Design: email-agent

## Overview
This document describes the architecture, design rationale, and implementation details of the logging system for email-agent. The logging system provides robust, configurable logging to file and console, including analytics summary, throughout the agent lifecycle.

---

## 1. Architecture
The system modularizes logging code into `logger.py` (core factory), `analytics.py` (summary generation), and integrates with CLI via configuration. All logging is structured and strict for traceability, search, and analytics.

## 2. Configuration
- Logging is configured via `config.yaml` (`log_file`, `log_level`, etc). 
- Analytics output file/location is also from config.
- All log file/analytics locations are parametrized for test/client use.

## 3. Test Strategy & Scaffolding
- Test files: `test_logging.py`
- Pytest fixtures isolate temporary log and analytics files, ensure tests do not pollute main logs.
- Output capture helpers are used for console log collection.
- TDD: Every core behavior (log to console/file, structure, analytics) covered by initial failing and then passing tests.

### Example Test Fixture Usage
```python
from tests.test_logging import temp_logfile

def test_log_output():
    with temp_logfile() as logfile:
        # ... test with that log file
        pass
```

### Isolation Principle
- Tests must not produce or consume real logs in production locations.
- Each test run is clean and does not overlap outputs.

## 4. Core Implementation
- `LoggerFactory` creates and configures loggers with file/console handlers, formats.
- Each log message includes timestamp (ISO 8601), unique message ID.
- Log levels (INFO, DEBUG, etc.) are enforced; filtering verified by tests.

### Usage Example
```python
from src.logger import LoggerFactory
logger = LoggerFactory.create_logger(level='INFO', log_file='out.log')
logger.info("Test log message")
```

## 5. Analytics Summary
- Metrics (message counts per level, etc) are generated at run end by `analytics.py`.
- Output: single-line JSONL in analytics file from config.
- Edge cases (no logs/large logs) are handled by robust summary logic and tested.
- Example output:
```json
{"timestamp": "2025-07-01T12:34:56", "total_processed": 13, "level_counts": {"INFO": 12, "ERROR": 1}, "tags_applied": {}}
```

### Analytics Summary Implementation
- `generate_analytics(log_file, analytics_file)` parses the configured log file and generates a JSON summary of log events.
- Summary includes processed count, per-level breakdown, and any additional collected data.
- Called on shutdown in CLI to ensure every run produces a summary record.
- The analytics file is appended for each run (JSONL format).

## 6. Configuration and Integration Details
- The YAML config (`config.yaml`) is the single source for logger and analytics file locations (keys: `log_file`, `log_level`, `analytics_file`).
- CLI (`src/cli.py`) loads config and global logger instance at startup. Exit hook triggers analytics summary.
- Example:
```yaml
log_file: "logs/agent.log"
log_level: "INFO"
analytics_file: "logs/analytics.jsonl"
```

### CLI/App Integration Code
```python
# src/cli.py
logger = LoggerFactory.create_logger(...)
logger.info("Started application")
# At exit
generate_analytics(config.log_file, config.analytics_file)
```
- Helper functions support common patterns (`LoggerFactory.create_logger`, `generate_analytics`).
- Global logger access ensures traceability across all modules.

---

*This file is updated in real time as the logging system is developed and integrated, to keep documentation in step with code.*