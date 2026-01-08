# V3 End-to-End Tests

This document covers end-to-end tests for V3 modules that require live external services.

## E2E Tests Overview

- **IMAP E2E Tests** (Task 18.9) - ✅ Complete
- **LLM E2E Tests** (Task 18.10) - ✅ Complete
- **Edge Case E2E Tests** (Task 18.11) - ✅ Complete

---

# V3 End-to-End Tests with Live IMAP Connections

**Status:** ✅ Complete (Task 18.9)  
**Test File:** `tests/test_e2e_imap.py`  
**Pytest Marker:** `@pytest.mark.e2e_imap`

## Overview

End-to-end tests that verify the complete V3 email processing workflow using real IMAP servers. These tests validate:

- IMAP connection and authentication
- Email retrieval from live servers
- Flag management (setting/removing flags)
- Complete processing workflow
- Various email types (plain text, HTML, multipart)
- Error handling and isolation

## Requirements

To run these tests, you need:

1. **Valid IMAP credentials** in `config/config.yaml`:
   ```yaml
   imap:
     server: 'your.imap.server.com'
     port: 993
     username: 'your-email@example.com'
     password_env: 'IMAP_PASSWORD'
   ```

2. **IMAP_PASSWORD environment variable** in `.env`:
   ```
   IMAP_PASSWORD=your_password
   ```

3. **Test email account** with at least one unprocessed email in INBOX

4. **Test environment** - Use a test account, not production email (tests may modify flags)

## Running Tests

### Run All E2E IMAP Tests

```bash
# Run all E2E IMAP tests
pytest tests/test_e2e_imap.py -v

# Run with more verbose output
pytest tests/test_e2e_imap.py -vv -s
```

### Skip E2E Tests (if credentials not available)

```bash
# Skip E2E tests
pytest tests/test_e2e_imap.py -v -m "not e2e_imap"

# Or exclude the file entirely
pytest tests/ -v --ignore=tests/test_e2e_imap.py
```

### Run Specific Test Classes

```bash
# Test IMAP connection only
pytest tests/test_e2e_imap.py::TestE2EIMAPConnection -v

# Test email retrieval only
pytest tests/test_e2e_imap.py::TestE2EEmailRetrieval -v

# Test flag management only
pytest tests/test_e2e_imap.py::TestE2EFlagManagement -v
```

## Test Structure

### Test Classes

1. **TestE2EIMAPConnection** - IMAP connection tests
   - `test_imap_connection_success` - Verify successful connection
   - `test_imap_connection_selects_inbox` - Verify INBOX selection
   - `test_imap_connection_reconnect` - Test reconnection after disconnect

2. **TestE2EEmailRetrieval** - Email retrieval tests
   - `test_get_unprocessed_emails_returns_list` - Verify email list retrieval
   - `test_get_unprocessed_emails_structure` - Verify email data structure
   - `test_get_unprocessed_emails_respects_limit` - Test limit parameter
   - `test_get_email_by_uid` - Test retrieving specific email by UID
   - `test_get_email_by_uid_invalid` - Test error handling for invalid UID
   - `test_is_processed_flag_check` - Test processed flag checking

3. **TestE2EFlagManagement** - Flag management tests
   - `test_set_flag` - Test setting flags on emails
   - `test_remove_flag` - Test removing flags from emails
   - `test_set_processed_flag` - Test setting AIProcessed flag

4. **TestE2EEmailProcessingWorkflow** - Complete workflow tests
   - `test_pipeline_retrieves_emails` - Test pipeline email retrieval
   - `test_pipeline_with_specific_uid` - Test processing specific email by UID

5. **TestE2EEmailTypes** - Email type tests
   - `test_plain_text_email` - Test plain text email processing
   - `test_html_email` - Test HTML email processing
   - `test_email_with_attachments` - Test emails with attachments

6. **TestE2EErrorHandling** - Error handling tests
   - `test_connection_error_handling` - Test connection error handling
   - `test_fetch_error_handling` - Test fetch error handling
   - `test_pipeline_error_isolation` - Test error isolation per email

## Test Fixtures

### Module-Level Fixtures

- **`live_imap_config`** - Loads live IMAP configuration (skips if credentials unavailable)
- **`live_imap_client`** - Creates and manages live IMAP client connection
- **`live_settings`** - Initializes settings facade for E2E tests

### Function-Level Fixtures

- **`test_email_uid`** - Gets a test email UID for testing (first unprocessed email)

## Test Behavior

### Automatic Skipping

Tests automatically skip if:
- `config/config.yaml` doesn't exist
- `.env` file doesn't exist
- `IMAP_PASSWORD` environment variable is not set
- IMAP server configuration is missing

### Dry-Run Mode

Most workflow tests use `dry_run=True` to avoid:
- Actually writing files to disk
- Setting IMAP flags permanently
- Making unnecessary API calls

### Flag Management

Flag management tests:
- Use test flags (`TestFlagE2E`) that are cleaned up after tests
- Restore original state after testing
- Handle cleanup errors gracefully

## Safety Considerations

1. **Use Test Account**: These tests connect to real IMAP servers and may modify flags
2. **Flag Cleanup**: Tests attempt to clean up test flags, but manual cleanup may be needed
3. **Email Selection**: Tests use the first unprocessed email found - ensure test account has suitable emails
4. **Dry-Run**: Workflow tests use dry-run mode to avoid permanent changes

## Integration with CI/CD

These tests are designed to be skipped in CI environments where IMAP credentials are not available:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pytest tests/ -v -m "not e2e_imap"
```

For CI environments with test IMAP accounts:

```yaml
- name: Run all tests including E2E
  env:
    IMAP_PASSWORD: ${{ secrets.TEST_IMAP_PASSWORD }}
  run: |
    pytest tests/ -v
```

## Troubleshooting

### Issue: Tests Skip Unexpectedly

**Check:**
1. `config/config.yaml` exists and has valid IMAP configuration
2. `.env` file exists and contains `IMAP_PASSWORD`
3. IMAP credentials are correct

### Issue: Connection Errors

**Check:**
1. IMAP server is accessible from test environment
2. Port (993 for SSL, 143 for STARTTLS) is correct
3. Firewall/network allows IMAP connections
4. Credentials are valid

### Issue: No Test Emails Found

**Solution:**
1. Ensure test account has unprocessed emails
2. Check `imap_query` in config matches test emails
3. Remove `AIProcessed` flag from test emails if needed

## PDD Alignment

This test suite implements:
- **PDD Section 5**: Testing requirements for V3 modules
- **Task 18.9**: E2E tests with live IMAP connections

## Related Documentation

- **[V3 IMAP Client](v3-imap-client.md)** - IMAP client implementation
- **[V3 Orchestrator](v3-orchestrator.md)** - Pipeline orchestration
- **[Live Test Guide](live-test-guide.md)** - Manual live testing guide
- **[IMAP Fetching](imap-fetching.md)** - IMAP implementation details

## Reference

- **Test File**: `tests/test_e2e_imap.py`
- **Pytest Config**: `pytest.ini`
- **IMAP Client**: `src/imap_client.py`
- **Orchestrator**: `src/orchestrator.py`
- **Settings**: `src/settings.py`

---

# V3 End-to-End Tests for Edge Cases

**Status:** ✅ Complete (Task 18.11)  
**Test Files:** `tests/test_e2e_imap.py`, `tests/test_e2e_llm.py`  
**Pytest Marker:** `@pytest.mark.e2e_imap`, `@pytest.mark.e2e_llm`

## Overview

End-to-end tests that verify the system's behavior under edge case conditions using real external services. These tests validate:

- Very large email processing and truncation
- Rate limiting scenarios and handling
- Connection interruption recovery
- Malformed response handling
- Concurrent operations
- Special character and unicode handling
- Timeout scenarios

## Requirements

Same as the base E2E tests:
- Valid IMAP credentials for IMAP edge case tests
- Valid LLM API credentials for LLM edge case tests
- Test accounts/environments (not production)

## Running Tests

### Run All Edge Case Tests

```bash
# Run IMAP edge case tests
pytest tests/test_e2e_imap.py::TestE2EEdgeCases -v

# Run LLM edge case tests
pytest tests/test_e2e_llm.py::TestE2EEdgeCases -v

# Run all edge case tests
pytest tests/test_e2e_imap.py::TestE2EEdgeCases tests/test_e2e_llm.py::TestE2EEdgeCases -v
```

### Skip Edge Case Tests

```bash
# Skip edge case tests (run other E2E tests)
pytest tests/test_e2e_imap.py -v -k "not EdgeCases"
pytest tests/test_e2e_llm.py -v -k "not EdgeCases"
```

## Test Structure

### IMAP Edge Case Tests (`TestE2EEdgeCases`)

1. **Very Large Email Processing**
   - `test_very_large_email_processing` - Test processing of very large emails with automatic truncation

2. **Connection Interruption**
   - `test_connection_interruption_recovery` - Test recovery from connection interruptions
   - `test_connection_interruption_during_fetch` - Test handling of interruptions during email fetch

3. **Malformed Email Handling**
   - `test_malformed_email_handling` - Test handling of emails with malformed headers or content

4. **Rate Limiting**
   - `test_rate_limiting_scenario` - Test behavior under rate limiting conditions

5. **Concurrent Operations**
   - `test_concurrent_operations` - Test concurrent IMAP operations

6. **Special Cases**
   - `test_empty_inbox_handling` - Test handling when inbox is empty
   - `test_very_long_subject_line` - Test handling of very long subject lines
   - `test_special_characters_in_subject` - Test handling of special characters in subjects

### LLM Edge Case Tests (`TestE2EEdgeCases`)

1. **Very Large Email Classification**
   - `test_very_large_email_classification` - Test classification of very large emails with truncation
   - `test_extremely_long_email` - Test classification of extremely long emails

2. **Rate Limiting**
   - `test_rate_limiting_scenario` - Test behavior under API rate limiting
   - `test_rapid_successive_requests` - Test making rapid successive API requests

3. **Connection Interruption**
   - `test_connection_interruption_recovery` - Test recovery from connection interruptions

4. **Malformed Response Handling**
   - `test_malformed_response_handling` - Test handling of malformed API responses
   - `test_malformed_json_response` - Test handling when API returns malformed JSON

5. **Timeout Scenarios**
   - `test_timeout_scenario` - Test handling of API timeout scenarios

6. **Concurrent Operations**
   - `test_concurrent_classifications` - Test concurrent LLM API calls

7. **Special Character Handling**
   - `test_special_characters_and_unicode` - Test classification with special characters and unicode
   - `test_empty_and_minimal_emails` - Test classification of empty and minimal emails

## Test Behavior

### Automatic Skipping

Edge case tests automatically skip if:
- Base E2E test credentials are not available
- Required test data is not available (e.g., no test emails)

### Error Handling

Edge case tests are designed to:
- Verify graceful error handling
- Ensure system doesn't crash under edge conditions
- Validate recovery mechanisms
- Test error isolation

### Performance Considerations

Some edge case tests may:
- Make multiple API calls (rate limiting tests)
- Take longer to execute (timeout tests)
- Consume more API credits (concurrent tests)

## Safety Considerations

1. **Use Test Environment**: Edge case tests may make many API calls or connections
2. **Rate Limiting**: Tests may hit rate limits - this is expected behavior
3. **API Credits**: Some tests consume more API credits than normal tests
4. **Timeouts**: Some tests may take longer to execute

## Integration with CI/CD

Edge case tests are designed to be skipped in CI environments where credentials are not available:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pytest tests/ -v -k "not EdgeCases"
```

For CI environments with test credentials:

```yaml
- name: Run all tests including edge cases
  env:
    IMAP_PASSWORD: ${{ secrets.TEST_IMAP_PASSWORD }}
    OPENROUTER_API_KEY: ${{ secrets.TEST_OPENROUTER_API_KEY }}
  run: |
    pytest tests/ -v
```

## Troubleshooting

### Issue: Rate Limiting Tests Fail

**Solution:**
- Reduce number of requests in test
- Add longer delays between requests
- Use test API key with higher rate limits

### Issue: Timeout Tests Take Too Long

**Solution:**
- Reduce timeout values in test configuration
- Skip timeout tests in local development
- Run timeout tests separately

### Issue: Concurrent Tests Fail

**Solution:**
- Reduce number of concurrent threads
- Add delays between thread starts
- Verify API supports concurrent requests

## PDD Alignment

This test suite implements:
- **PDD Section 5**: Testing requirements for V3 modules
- **Task 18.11**: E2E tests for edge cases

## Related Documentation

- **[V3 IMAP Client](v3-imap-client.md)** - IMAP client implementation
- **[V3 LLM Client](v3-llm-client.md)** - LLM client implementation
- **[V3 Orchestrator](v3-orchestrator.md)** - Pipeline orchestration
- **[Live Test Guide](live-test-guide.md)** - Manual live testing guide

## Reference

- **Test Files**: `tests/test_e2e_imap.py`, `tests/test_e2e_llm.py`
- **Test Class**: `TestE2EEdgeCases`
- **Pytest Config**: `pytest.ini`

---

# V3 End-to-End Tests with Live LLM API

**Status:** ✅ Complete (Task 18.10)  
**Test File:** `tests/test_e2e_llm.py`  
**Pytest Marker:** `@pytest.mark.e2e_llm`

## Overview

End-to-end tests that verify the complete V3 LLM client functionality using real LLM API calls. These tests validate:

- LLM API connection and authentication
- Email classification with live API
- Prompt construction and formatting
- Response parsing and validation
- Error handling and retry logic
- Various email types and edge cases
- Integration with decision logic

## Requirements

To run these tests, you need:

1. **Valid OpenRouter configuration** in `config/config.yaml`:
   ```yaml
   openrouter:
     api_key_env: 'OPENROUTER_API_KEY'
     api_url: 'https://openrouter.ai/api/v1'
     model: 'google/gemini-2.5-flash-lite-preview-09-2025'
     temperature: 0.2
     retry_attempts: 3
     retry_delay_seconds: 5
   ```

2. **OPENROUTER_API_KEY environment variable** in `.env`:
   ```
   OPENROUTER_API_KEY=your_api_key
   ```

3. **Valid API key** with sufficient credits/quota

4. **Network access** to OpenRouter API

5. **Test environment** - Use a test/staging API key if possible (tests consume API credits)

## Running Tests

### Run All E2E LLM Tests

```bash
# Run all E2E LLM tests
pytest tests/test_e2e_llm.py -v

# Run with more verbose output
pytest tests/test_e2e_llm.py -vv -s
```

### Skip E2E Tests (if credentials not available)

```bash
# Skip E2E tests
pytest tests/test_e2e_llm.py -v -m "not e2e_llm"

# Or exclude the file entirely
pytest tests/ -v --ignore=tests/test_e2e_llm.py
```

### Run Specific Test Classes

```bash
# Test LLM connection only
pytest tests/test_e2e_llm.py::TestE2ELLMConnection -v

# Test classification only
pytest tests/test_e2e_llm.py::TestE2ELLMClassification -v

# Test error handling only
pytest tests/test_e2e_llm.py::TestE2ELLMErrorHandling -v
```

## Test Structure

### Test Classes

1. **TestE2ELLMConnection** - LLM client initialization tests
   - `test_llm_client_initializes` - Verify client initialization
   - `test_llm_client_loads_config` - Verify configuration loading

2. **TestE2ELLMClassification** - Email classification tests
   - `test_classify_simple_email` - Test basic email classification
   - `test_classify_important_email` - Test important email classification
   - `test_classify_spam_email` - Test spam email classification
   - `test_classify_with_custom_prompt` - Test custom prompt integration
   - `test_classify_with_max_chars` - Test content truncation

3. **TestE2ELLMResponseParsing** - Response parsing tests
   - `test_response_has_valid_scores` - Verify score ranges
   - `test_response_has_raw_content` - Verify raw response content
   - `test_response_to_dict` - Test response serialization

4. **TestE2ELLMErrorHandling** - Error handling tests
   - `test_invalid_api_key_handling` - Test invalid API key handling
   - `test_network_error_handling` - Test network error handling
   - `test_retry_logic_on_transient_error` - Test retry logic

5. **TestE2ELLMPromptConstruction** - Prompt construction tests
   - `test_default_prompt_format` - Test default prompt formatting
   - `test_custom_prompt_integration` - Test custom prompt integration

6. **TestE2ELLMEmailTypes** - Email type tests
   - `test_plain_text_email` - Test plain text email classification
   - `test_html_email` - Test HTML email classification
   - `test_email_with_special_characters` - Test special character handling
   - `test_empty_email` - Test empty email edge case

7. **TestE2ELLMIntegration** - Integration tests
   - `test_llm_client_with_decision_logic` - Test decision logic integration
   - `test_llm_client_with_orchestrator` - Test orchestrator integration

8. **TestE2ELLMPerformance** - Performance tests
   - `test_classification_response_time` - Test response time
   - `test_multiple_classifications` - Test sequential classifications

## Test Fixtures

### Module-Level Fixtures

- **`live_llm_config`** - Loads live LLM configuration (skips if credentials unavailable)
- **`live_llm_client`** - Creates and manages live LLM client

### Function-Level Fixtures

- **`sample_email_content`** - Sample email for testing
- **`important_email_content`** - Important email sample
- **`spam_email_content`** - Spam email sample
- **`long_email_content`** - Long email for truncation testing

## Test Behavior

### Automatic Skipping

Tests automatically skip if:
- `config/config.yaml` doesn't exist
- `.env` file doesn't exist
- `OPENROUTER_API_KEY` environment variable is not set
- OpenRouter configuration is missing

### API Usage

- Tests make actual API calls and consume API credits
- Each test makes at least one API call
- Performance tests make multiple sequential calls
- Use test/staging API keys when possible

### Error Handling

Error handling tests use mocks to simulate failures:
- Invalid API keys
- Network errors
- Transient errors (for retry testing)

## Safety Considerations

1. **Use Test API Key**: These tests make real API calls and consume credits
2. **API Quota**: Ensure sufficient API quota/credits before running tests
3. **Rate Limiting**: Tests may be rate-limited by API provider
4. **Cost Awareness**: Each test consumes API credits - run selectively if needed

## Integration with CI/CD

These tests are designed to be skipped in CI environments where LLM API credentials are not available:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pytest tests/ -v -m "not e2e_llm"
```

For CI environments with test API keys:

```yaml
- name: Run all tests including E2E
  env:
    OPENROUTER_API_KEY: ${{ secrets.TEST_OPENROUTER_API_KEY }}
  run: |
    pytest tests/ -v
```

## Troubleshooting

### Issue: Tests Skip Unexpectedly

**Check:**
1. `config/config.yaml` exists and has valid OpenRouter configuration
2. `.env` file exists and contains `OPENROUTER_API_KEY`
3. API key is valid and has sufficient credits

### Issue: API Errors

**Check:**
1. API key is valid and not expired
2. API quota/credits are available
3. Network connectivity to OpenRouter API
4. Model name in config is valid and available

### Issue: Rate Limiting

**Solution:**
1. Reduce number of tests run at once
2. Add delays between test runs
3. Use test API key with higher rate limits
4. Run tests during off-peak hours

### Issue: Slow Response Times

**Check:**
1. Network latency to API endpoint
2. Model being used (some models are slower)
3. API server load
4. Request payload size

## PDD Alignment

This test suite implements:
- **PDD Section 5**: Testing requirements for V3 modules
- **Task 18.10**: E2E tests with live LLM API

## Related Documentation

- **[V3 LLM Client](v3-llm-client.md)** - LLM client implementation
- **[V3 Decision Logic](v3-decision-logic.md)** - Classification decision logic
- **[V3 Orchestrator](v3-orchestrator.md)** - Pipeline orchestration
- **[Live Test Guide](live-test-guide.md)** - Manual live testing guide

## Reference

- **Test File**: `tests/test_e2e_llm.py`
- **Pytest Config**: `pytest.ini`
- **LLM Client**: `src/llm_client.py`
- **Decision Logic**: `src/decision_logic.py`
- **Settings**: `src/settings.py`
