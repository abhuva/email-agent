# V3 Test Coverage Analysis

**Date:** 2026-01-XX  
**Task:** 18.1 - Test Infrastructure Analysis

## Existing Test Coverage

### ✅ Unit Tests (Existing)
- **test_cli_v3.py** - CLI command parsing and execution (16 tests)
- **test_config_v3.py** - Configuration system (9 tests)
- **test_imap_client.py** - IMAP operations (16 tests)
- **test_llm_client.py** - LLM API interactions (18 tests)
- **test_decision_logic.py** - Classification logic (5 test classes)
- **test_note_generator.py** - Note generation (5 test classes)
- **test_error_handling_v3.py** - Error handling (6 test classes)
- **test_v3_logger.py** - Logging system (5 test classes)
- **test_prompt_renderer.py** - Prompt rendering (3 test classes)

### ❌ Missing Unit Tests
- **test_orchestrator.py** - Pipeline orchestration (CRITICAL)
- **test_backfill.py** - Backfill functionality
- **test_cleanup_flags.py** - Cleanup flags command

### ❌ Missing Integration Tests
- **test_integration_v3_workflow.py** - End-to-end V3 workflow with --dry-run
- Integration tests for force-reprocess
- Integration tests for cleanup-flags command
- Integration tests for backfill command

### ❌ Missing E2E Tests
- Live IMAP connection tests
- Live LLM API tests
- Full pipeline execution with real services
- Edge case testing (large emails, rate limiting, etc.)

## Test Infrastructure Status

### Existing Fixtures (conftest.py)
- `valid_config_path` - V2 config format
- `invalid_config_path` - Invalid config
- `valid_env_file` - Environment variables
- `invalid_env_file` - Invalid env file

### Needed Enhancements
- V3 config fixtures (with proper structure)
- Mock IMAP server fixtures
- Mock LLM API fixtures
- Test email data fixtures
- Dry-run test helpers

## Test Coverage Goals

1. **Unit Tests**: 80%+ coverage for all V3 modules
2. **Integration Tests**: All CLI commands and workflows
3. **E2E Tests**: Critical paths with real services
4. **Edge Cases**: Error scenarios, rate limiting, large inputs

## Priority Order

1. **test_orchestrator.py** (HIGH) - Core coordination logic
2. **test_integration_v3_workflow.py** (HIGH) - Full pipeline testing
3. **test_backfill.py** (MEDIUM) - Backfill functionality
4. **test_cleanup_flags.py** (MEDIUM) - Cleanup command
5. **E2E tests** (MEDIUM) - Real service testing
6. **Edge case tests** (LOW) - Resilience testing
