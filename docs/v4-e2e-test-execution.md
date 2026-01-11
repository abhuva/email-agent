# V4 End-to-End Test Execution Guide

**Task:** 19.5  
**Status:** ✅ Complete  
**PDD Reference:** Task 19 - Perform End-to-End Testing

## Overview

This guide covers executing, analyzing, and iterating on V4 end-to-end test runs. E2E tests validate the complete email processing pipeline using real email accounts and services.

## Running E2E Tests

### Prerequisites

Before running E2E tests, ensure:

- [ ] Test accounts configured (see `docs/v4-e2e-test-setup.md`)
- [ ] Test account credentials in environment variables
- [ ] Test account configs in `config/accounts/`
- [ ] Test accounts documented in `config/test-accounts.yaml`
- [ ] Test environment set up (see `docs/v4-e2e-test-environment.md`)

### Running All E2E Tests

```bash
# Run all V4 E2E tests
pytest tests/test_e2e_v4_pipeline.py -v -m e2e_v4

# Run with more verbose output
pytest tests/test_e2e_v4_pipeline.py -vv -s -m e2e_v4

# Run specific test class
pytest tests/test_e2e_v4_pipeline.py::TestE2ESingleAccountBasicFlow -v -m e2e_v4

# Run specific test
pytest tests/test_e2e_v4_pipeline.py::TestE2ESingleAccountBasicFlow::test_process_single_plain_text_email -v -m e2e_v4
```

### Skipping E2E Tests

If credentials are not available:

```bash
# Skip E2E tests
pytest tests/test_e2e_v4_pipeline.py -v -m "not e2e_v4"

# Or exclude the file entirely
pytest tests/ -v --ignore=tests/test_e2e_v4_pipeline.py
```

### Running Specific Test Scenarios

```bash
# Single-account basic flow
pytest tests/test_e2e_v4_pipeline.py::TestE2ESingleAccountBasicFlow -v -m e2e_v4

# Multi-account processing
pytest tests/test_e2e_v4_pipeline.py::TestE2EMultiAccountProcessing -v -m e2e_v4

# Rules engine
pytest tests/test_e2e_v4_pipeline.py::TestE2ERulesEngine -v -m e2e_v4

# Content parsing
pytest tests/test_e2e_v4_pipeline.py::TestE2EContentParsing -v -m e2e_v4

# Edge cases
pytest tests/test_e2e_v4_pipeline.py::TestE2EEdgeCases -v -m e2e_v4

# Provider-specific
pytest tests/test_e2e_v4_pipeline.py::TestE2EProviderSpecific -v -m e2e_v4
```

## Analyzing Test Results

### Test Output Analysis

After running tests, analyze the output:

1. **Test Pass/Fail Status**
   - Check which tests passed/failed
   - Identify patterns in failures

2. **Processing Results**
   - Check account processing success/failure
   - Review email processing counts
   - Verify note generation

3. **Log Analysis**
   - Review logs for errors/warnings
   - Check correlation IDs for tracing
   - Analyze performance metrics

### Log Analysis

```bash
# View recent logs
tail -n 100 logs/agent.log

# Search for errors
grep "ERROR" logs/agent.log

# Search for specific account
grep "test-gmail-1" logs/agent.log

# Search for correlation IDs
grep "correlation_id" logs/agent.log
```

### Test Vault Analysis

Check generated notes:

```bash
# List notes in test vault
ls -lt /tmp/test-vault-gmail-1/*.md

# View note content
cat /tmp/test-vault-gmail-1/*.md | head -50

# Check note count
ls /tmp/test-vault-gmail-1/*.md | wc -l
```

### Analytics Analysis

Review structured analytics:

```bash
# View analytics entries
tail -n 50 logs/analytics.jsonl

# Parse JSONL for analysis
cat logs/analytics.jsonl | jq '.account_id, .email_uid, .status'
```

## Common Issues and Solutions

### Issue: No Test Accounts Available

**Symptoms:**
- Tests skipped with "No test accounts available"
- `available_test_accounts` fixture returns empty list

**Solutions:**
1. Verify test accounts configured in `config/test-accounts.yaml`
2. Check credentials in environment variables
3. Verify account configs exist in `config/accounts/`
4. Run environment verification: `pytest tests/test_e2e_v4_pipeline.py::TestE2EEnvironmentVerification -v`

### Issue: IMAP Connection Fails

**Symptoms:**
- Tests fail with IMAP connection errors
- "IMAP connection failed" in logs

**Solutions:**
1. Verify credentials are correct (app password, not regular password)
2. Check IMAP server settings (server, port)
3. Verify IMAP is enabled in account settings
4. Test IMAP connection manually: `python scripts/test_imap_live.py`

### Issue: No Emails Processed

**Symptoms:**
- Tests pass but no notes generated
- "No emails found" in logs

**Solutions:**
1. Send test emails to test accounts
2. Verify emails are unprocessed (no AIProcessed flag)
3. Check IMAP query matches test emails
4. Verify emails are in INBOX (not other folders)

### Issue: Rules Not Applied

**Symptoms:**
- Blacklist/whitelist rules not working
- Emails not dropped/boosted as expected

**Solutions:**
1. Verify rules files exist (`config/blacklist.yaml`, `config/whitelist.yaml`)
2. Check rule syntax (valid YAML)
3. Verify rule triggers match test email senders/subjects/domains
4. Review rule evaluation logs

### Issue: HTML Parsing Fails

**Symptoms:**
- HTML emails not converted to Markdown
- Parsing errors in logs

**Solutions:**
1. Check HTML content (may be malformed)
2. Verify html2text library is installed
3. Review parsing error logs
4. Test parsing manually with test HTML

### Issue: Note Generation Fails

**Symptoms:**
- Notes not created
- "Note generation failed" in logs

**Solutions:**
1. Verify vault directory exists and is writable
2. Check vault path in account config
3. Review file permissions
4. Check disk space

## Iterating on Test Runs

### Test Iteration Process

1. **Run Tests** - Execute E2E test suite
2. **Analyze Results** - Review test output, logs, notes
3. **Identify Issues** - Find failures, errors, unexpected behavior
4. **Fix Issues** - Update code, config, or test data
5. **Re-run Tests** - Verify fixes work
6. **Repeat** - Continue until all tests pass

### Test Data Iteration

If tests fail due to missing test data:

1. **Send Test Emails** to test accounts
2. **Configure Test Rules** for specific scenarios
3. **Verify Email State** (unprocessed, correct senders, etc.)
4. **Re-run Tests** with new test data

### Configuration Iteration

If tests fail due to configuration issues:

1. **Review Config Files** - Check YAML syntax, structure
2. **Verify Environment Variables** - Check credentials, API keys
3. **Update Configs** - Fix configuration issues
4. **Re-run Tests** with updated configs

### Code Iteration

If tests reveal code bugs:

1. **Reproduce Issue** - Run failing test to reproduce bug
2. **Debug** - Use logs, debugger to find root cause
3. **Fix Code** - Implement fix
4. **Test Fix** - Re-run test to verify fix
5. **Run Full Suite** - Ensure no regressions

## Test Coverage Analysis

### Coverage Metrics

Track test coverage:

- **Scenario Coverage** - Which test scenarios are covered
- **Account Coverage** - Which test accounts are tested
- **Provider Coverage** - Which email providers are tested
- **Rule Coverage** - Which rules are tested
- **Edge Case Coverage** - Which edge cases are tested

### Coverage Gaps

Identify and fill coverage gaps:

1. **Missing Scenarios** - Add tests for uncovered scenarios
2. **Missing Accounts** - Add tests for untested accounts
3. **Missing Providers** - Add tests for untested providers
4. **Missing Rules** - Add tests for untested rule combinations
5. **Missing Edge Cases** - Add tests for untested edge cases

## Performance Analysis

### Processing Time

Monitor processing performance:

- **Email Processing Time** - Time per email
- **Account Processing Time** - Time per account
- **Total Test Time** - Time for full test suite

### Resource Usage

Monitor resource usage:

- **API Calls** - Number of LLM API calls
- **Cost** - Estimated API costs
- **Memory** - Memory usage during tests
- **Network** - Network usage (IMAP, API calls)

## CI/CD Integration

### Continuous Integration

Integrate E2E tests into CI/CD:

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  schedule:
    - cron: '0 0 * * *'  # Daily
  workflow_dispatch:

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Configure test accounts
        env:
          IMAP_PASSWORD_TEST_GMAIL_1: ${{ secrets.IMAP_PASSWORD_TEST_GMAIL_1 }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          # Setup test accounts
      - name: Run E2E tests
        run: pytest tests/test_e2e_v4_pipeline.py -v -m e2e_v4
```

### Test Scheduling

Schedule E2E tests:

- **Daily** - Run full suite daily
- **Pre-release** - Run before releases
- **On-demand** - Run manually when needed

## Success Criteria

E2E tests are successful when:

1. ✅ **All Tests Pass** - All test scenarios pass
2. ✅ **No Errors** - No unexpected errors in logs
3. ✅ **Notes Generated** - Notes created correctly
4. ✅ **Rules Applied** - Rules work as expected
5. ✅ **State Isolation** - No cross-contamination
6. ✅ **Performance Acceptable** - Processing times reasonable
7. ✅ **Costs Controlled** - API costs within budget

## Next Steps

After executing and iterating on E2E tests:

1. **Proceed to Subtask 19.6:** Final stage (validate tests, update docs, mark done)
2. **Document Findings** - Document any issues found
3. **Update Tests** - Add new tests for discovered edge cases
4. **Monitor in Production** - Use E2E tests to monitor production health

## Related Documentation

- `docs/v4-e2e-test-setup.md` - Test account setup
- `docs/v4-e2e-test-environment.md` - Test environment setup
- `docs/v4-e2e-test-scenarios.md` - Test scenarios
- `tests/test_e2e_v4_pipeline.py` - E2E test suite
- `tests/e2e_helpers.py` - E2E test utilities
