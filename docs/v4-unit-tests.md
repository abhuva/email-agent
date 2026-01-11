# V4 Unit Tests Documentation

**Task:** 16 - Create Unit Tests for Core Components  
**Status:** ✅ Complete

## Overview

This document describes the comprehensive unit test suite for V4 core components. The test suite ensures high code coverage and validates critical functionality through isolated unit tests using mocks.

## Test Structure

### Test Utilities (`tests/conftest_v4.py`)

V4-specific test fixtures and utilities for:
- **Configuration Fixtures:** V4 global and account-specific config dictionaries
- **Rules Engine Fixtures:** Sample blacklist and whitelist rules
- **EmailContext Builders:** Builder pattern for creating test EmailContext objects
- **Mock Service Fixtures:** Mock implementations for IMAP, LLM, note generator, and decision logic
- **MasterOrchestrator Fixtures:** Test fixtures for orchestrator testing

### Core Component Tests

#### 1. ConfigLoader Tests (`tests/test_config_loader.py`)

Comprehensive tests for the V4 configuration loader:
- **Initialization:** Default and custom parameter initialization
- **Path Resolution:** Global and account config path resolution
- **Account Name Validation:** Security checks for path traversal prevention
- **YAML Loading:** File loading, parsing, and error handling
- **Deep Merge Logic:** Dictionary, list, and primitive merge rules
- **Merged Config Loading:** Global-only and account-specific config loading
- **Edge Cases:** Empty configs, missing files, invalid formats
- **Convenience Functions:** Module-level helper functions
- **Schema Validation Integration:** Validation result handling

**Coverage:** 640+ lines, 9 test classes, 50+ test methods

#### 2. Rules Engine Tests (`tests/test_rules.py`)

Comprehensive tests for blacklist and whitelist rules:
- **ActionEnum:** Enum value validation
- **BlacklistRule:** Rule creation and validation
- **WhitelistRule:** Rule creation and validation
- **Rule Matching:** Sender, subject, and domain matching logic
- **Rule Loading:** YAML file loading and parsing
- **Blacklist Evaluation:** DROP, RECORD, and PASS actions
- **Whitelist Application:** Score boosting and tag addition
- **Edge Cases:** Malformed rules, empty rules, regex patterns

**Coverage:** 1300+ lines, 15+ test classes, 100+ test methods

#### 3. ContentParser Tests (`tests/test_content_parser.py`)

Tests for HTML to Markdown conversion:
- **HTML Conversion:** Successful HTML to Markdown conversion
- **Fallback Mechanism:** Plain text fallback on conversion failure
- **Character Limits:** 20,000 character limit enforcement
- **Complex HTML:** Various HTML formatting scenarios
- **Edge Cases:** Empty HTML, missing HTML, encoding issues
- **Logging:** Fallback logging behavior

**Coverage:** 270+ lines, 5+ test classes, 20+ test methods

#### 4. AccountProcessor Tests (`tests/test_account_processor.py`)

Tests for isolated per-account processing:
- **Initialization:** State isolation between instances
- **Setup/Teardown:** Lifecycle management
- **Pipeline Execution:** Blacklist → Parse → LLM → Whitelist → Note generation
- **Error Handling:** Setup failures, processing failures, cleanup
- **Safety Interlock:** Cost estimation and user confirmation
- **State Isolation:** Multiple account processor instances

**Coverage:** 700+ lines, 10+ test classes, 30+ test methods

#### 5. MasterOrchestrator Tests (`tests/test_master_orchestrator.py`)

Comprehensive tests for multi-account orchestration:
- **Initialization:** Default and custom initialization
- **CLI Argument Parsing:** All argument combinations
- **Account Discovery:** Account file discovery and filtering
- **Account Selection:** Single, multiple, and all account selection
- **AccountProcessor Creation:** Isolated processor creation
- **Shared Services:** LLM client, note generator, decision logic initialization
- **Orchestration Run:** Single and multiple account processing
- **Error Handling:** Setup failures, processing failures, partial failures
- **Result Aggregation:** Success/failure tracking and timing

**Coverage:** 650+ lines, 8 test classes, 38 test methods

## Test Coverage

### Overall Statistics
- **Total Tests:** 234+ tests for core V4 components
- **Test Files:** 5 dedicated test files
- **Test Utilities:** 1 comprehensive conftest file
- **Coverage:** High coverage of critical paths and edge cases

### Component Coverage
- **ConfigLoader:** ✅ Comprehensive (50+ tests)
- **Rules Engine:** ✅ Comprehensive (100+ tests)
- **ContentParser:** ✅ Comprehensive (20+ tests)
- **AccountProcessor:** ✅ Comprehensive (30+ tests)
- **MasterOrchestrator:** ✅ Comprehensive (38 tests)

## Test Execution

### Run All Core Component Tests
```bash
pytest tests/test_config_loader.py tests/test_rules.py tests/test_content_parser.py tests/test_account_processor.py tests/test_master_orchestrator.py -v
```

### Run Specific Component Tests
```bash
# ConfigLoader
pytest tests/test_config_loader.py -v

# Rules Engine
pytest tests/test_rules.py -v

# ContentParser
pytest tests/test_content_parser.py -v

# AccountProcessor
pytest tests/test_account_processor.py -v

# MasterOrchestrator
pytest tests/test_master_orchestrator.py -v
```

### Run with Coverage
```bash
pytest tests/test_config_loader.py tests/test_rules.py tests/test_content_parser.py tests/test_account_processor.py tests/test_master_orchestrator.py --cov=src --cov-report=html
```

## Test Patterns

### Mocking Strategy
- **Isolation:** All tests use mocks to isolate components
- **File System:** Use `tmp_path` fixture for temporary files
- **External Services:** Mock IMAP, LLM, and file operations
- **Context Managers:** Mock logging and context managers

### Test Data Builders
- **EmailContext Builder:** Fluent builder for EmailContext objects
- **Config Generators:** Helper functions for test configurations
- **Email Data Generators:** Helper functions for test email data

### Error Testing
- **Exception Handling:** Test all error paths
- **Validation Errors:** Test schema validation failures
- **Network Errors:** Test IMAP and LLM failures
- **File System Errors:** Test missing files and permissions

## Best Practices

1. **Isolation:** Each test is completely isolated using mocks
2. **Clarity:** Test names clearly describe what is being tested
3. **Coverage:** Critical paths and edge cases are thoroughly tested
4. **Maintainability:** Tests use fixtures and builders for reusability
5. **Performance:** Tests run quickly without external dependencies

## Integration with CI/CD

All unit tests are integrated into the CI/CD pipeline:
- Tests run on every commit
- Failures block merges
- Coverage reports are generated
- Test results are reported in PRs

## Future Enhancements

Potential improvements:
- **Property-Based Testing:** Use Hypothesis for property-based tests
- **Performance Tests:** Add performance benchmarks
- **Mutation Testing:** Use mutmut for mutation testing
- **Coverage Goals:** Set and enforce coverage thresholds

## Related Documentation

- [V4 Configuration System](v4-configuration.md) - Configuration loading and merging
- [V4 Rules Engine](v4-rules-engine.md) - Blacklist and whitelist rules
- [V4 Content Parser](v4-content-parser.md) - HTML to Markdown conversion
- [V4 Account Processor](v4-account-processor.md) - Per-account processing
- [V4 Master Orchestrator](v4-orchestrator.md) - Multi-account orchestration
