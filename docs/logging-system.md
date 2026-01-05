# Logging System Design (email-agent)

## Motivation
A robust logging system is required to ensure reliability, traceability, and auditability of agent operations. This system will support both console and file outputs, INFO/DEBUG log levels, clear timestamping, unique Message-IDs, and analytics summaries. The system is developed test-first (TDD) and tightly coupled to the overall configuration strategy.

## Implementation/Subtasks Checklist

1. **Test scaffolding** (✅ done):
    - Dedicated pytest module (`test_logging.py`)
    - Fixtures provide temp files and capture for isolated file/console outputs
    - Confirmed helpers prevent test pollution
2. **Tests for core features** (✅ done):
    - Tests for INFO/DEBUG, console/file, strict output structure, log-level filtering (all currently failing as expected)
    - Every requirement has a concrete failing test for TDD
3. **Logger implementation** (✅ done):
    - logger.py provides LoggerFactory
    - Handlers for console and file
    - Strict FORMAT with timestamp and UUID message IDs
    - Filters ensure every message has required metadata
4. **Analytics summary** (✅ done):
    - analytics.py generates a valid JSONL summary of the log file at run end, including count by log level and edge case handling
    - Tests are passing for analytics file structure, metrics, and edge scenarios
5. **Configuration/integration**: Logging config section, easy integration points in main, shutdown hook for summaries, helpers

## TDD Approach
- Add, then incrementally resolve, failing tests for every new behavior.
- Use temporary files and redirected stdout to prevent polluting real logs or user output.
- Optimize for developer experience: failures are clear and fast.

## Design Principles
- Log output structure is strict and consistent to enable searching and analytics.
- No side effects in tests; all output is isolated and cleaned.
- All log locations, levels, and analytics output paths are derived from config.yaml.

---
This file is to be updated at every step as the logging system evolves, so information and design decisions are always current and complete.