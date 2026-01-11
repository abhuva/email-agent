# V4 Integration Tests

**Task:** 17  
**Status:** ✅ Complete  
**PDD Reference:** Section 4.2

## Overview

Integration tests for V4 email processing pipeline verify component interactions without requiring real external dependencies. All tests use mock IMAP and LLM services to enable fast, deterministic testing.

## Test Structure

Integration tests are located in `tests/integration/`:

- **`mock_services.py`** - Mock IMAP and LLM clients
- **`test_utils.py`** - Test utilities and factories
- **`conftest.py`** - Pytest fixtures for integration tests
- **`test_config_loader_account_processor.py`** - ConfigLoader ↔ AccountProcessor integration
- **`test_rules_pipeline.py`** - Rules Engine ↔ processing pipeline integration
- **`test_content_parser_llm.py`** - Content Parser ↔ LLM processing integration
- **`test_e2e_scenarios.py`** - End-to-end integration scenarios

## Test Categories

### 1. ConfigLoader ↔ AccountProcessor Integration

Tests verify that:
- ConfigLoader correctly provides configuration to AccountProcessor
- Configuration defaults and overrides are honored
- Invalid configurations are handled gracefully
- Multiple accounts have isolated configurations
- MasterOrchestrator integration works correctly

**Test File:** `tests/integration/test_config_loader_account_processor.py`

**Key Tests:**
- Valid config creates AccountProcessor correctly
- Config defaults are honored
- Config overrides are applied
- Invalid config handled gracefully
- Multiple accounts isolated configs
- MasterOrchestrator integration

### 2. Rules Engine ↔ Processing Pipeline Integration

Tests verify that:
- Blacklist DROP action skips processing
- Blacklist RECORD action generates raw markdown
- Whitelist rules boost importance scores
- Rule ordering (first match wins)
- No matching rules follow default path

**Test File:** `tests/integration/test_rules_pipeline.py`

**Key Tests:**
- Blacklist drop skips processing
- Blacklist record generates raw markdown
- Whitelist boosts scores
- Rule ordering precedence
- Default processing path

### 3. Content Parser ↔ LLM Processing Integration

Tests verify that:
- HTML content is parsed to Markdown before LLM
- Plain text fallback is used when HTML parsing fails
- LLM responses are correctly parsed
- Invalid JSON from LLM is handled gracefully

**Test File:** `tests/integration/test_content_parser_llm.py`

**Key Tests:**
- HTML parsed before LLM
- Plain text fallback
- LLM response handling
- Invalid JSON handling

### 4. End-to-End Integration Scenarios

Tests verify complete pipeline flows:
- Complete pipeline: config → accounts → fetch → rules → parse → LLM → notes
- Multi-account processing with isolated configurations

**Test File:** `tests/integration/test_e2e_scenarios.py`

## Mock Services

### MockImapClient

In-memory IMAP client that:
- Stores emails in memory
- Supports configurable error conditions
- Implements all required IMAP methods
- Allows testing edge cases (empty inbox, connection errors, malformed messages)

### MockLLMClient

Deterministic LLM client that:
- Returns configurable responses based on scenarios
- Supports timeout simulation
- Supports invalid JSON responses
- Supports truncated responses

## Running Integration Tests

### Run All Integration Tests

```bash
pytest tests/integration/ -v
```

### Run Specific Test Category

```bash
# ConfigLoader ↔ AccountProcessor
pytest tests/integration/test_config_loader_account_processor.py -v

# Rules Engine ↔ Pipeline
pytest tests/integration/test_rules_pipeline.py -v

# Content Parser ↔ LLM
pytest tests/integration/test_content_parser_llm.py -v

# E2E Scenarios
pytest tests/integration/test_e2e_scenarios.py -v
```

### Run with Integration Marker

```bash
pytest -m integration -v
```

## CI Integration

Integration tests are automatically run in CI as part of the test suite. They are included in the standard test run (excluding E2E tests that require live credentials).

**CI Configuration:** `.github/workflows/ci.yml`

The CI workflow runs:
```bash
pytest tests/ -v -m "not e2e_imap and not e2e_llm"
```

This includes all integration tests (marked with `@pytest.mark.integration`).

## Test Coverage

Integration tests cover:
- ✅ ConfigLoader ↔ AccountProcessor integration (8 tests)
- ✅ Rules Engine ↔ processing pipeline integration (5 tests)
- ✅ Content Parser ↔ LLM processing integration (4 tests)
- ✅ End-to-end scenarios (2 tests)

**Total:** 19 integration tests

## Best Practices

1. **Use Mock Services:** Always use `MockImapClient` and `MockLLMClient` for integration tests
2. **Isolate Tests:** Each test should be independent and not rely on external state
3. **Test Integration Points:** Focus on component interactions, not internal implementation
4. **Verify Observable Behavior:** Assert on final outcomes, not internal state
5. **Use Fixtures:** Leverage `conftest.py` fixtures for common setup

## Future Enhancements

- Add more edge case scenarios
- Add performance benchmarks
- Add stress testing scenarios
- Add concurrent processing tests
