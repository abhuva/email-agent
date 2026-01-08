# CI Integration Guide

**Status:** ✅ Complete (Task 18.12)  
**CI Workflow:** `.github/workflows/ci.yml`

## Overview

The CI integration provides automated testing for the email-agent project using GitHub Actions. The workflow is designed to:

- Run unit and integration tests automatically on every push and pull request
- Exclude E2E tests by default (they require external credentials)
- Support optional E2E test execution with proper credentials
- Generate test coverage reports
- Provide clear test result reporting

## CI Workflow Structure

### Main Test Job (`test`)

Runs on multiple operating systems and Python versions:
- **OS:** Ubuntu Latest, Windows Latest
- **Python Versions:** 3.9, 3.10, 3.11

**Test Execution:**
1. **Unit Tests** - Fast, isolated tests with mocks
2. **Integration Tests** - Tests module interactions with `--dry-run` mode
3. **All Non-E2E Tests** - Complete test suite excluding E2E tests

**Features:**
- Automatic dependency installation
- Test coverage reporting (Codecov integration)
- JUnit XML test result reporting
- HTML coverage reports as artifacts

### E2E Test Job (`test-e2e`)

**Conditional Execution:**
- Only runs on pull requests with the `run-e2e-tests` label
- Requires GitHub secrets for test credentials

**Required Secrets:**
- `TEST_IMAP_SERVER` - IMAP server hostname
- `TEST_IMAP_USERNAME` - IMAP test account username
- `TEST_IMAP_PASSWORD` - IMAP test account password
- `TEST_OPENROUTER_API_KEY` - OpenRouter API key for testing

**Note:** E2E tests are marked as `continue-on-error: true` to prevent blocking PRs if external services are unavailable.

### Lint Job (`lint`)

Runs code quality checks:
- **Black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting

All lint checks are non-blocking (`continue-on-error: true`) to provide feedback without blocking merges.

## Running Tests Locally

### Run All Non-E2E Tests

```bash
# Run unit and integration tests (excludes E2E)
pytest tests/ -v -m "not e2e_imap and not e2e_llm"

# With coverage
pytest tests/ -v -m "not e2e_imap and not e2e_llm" --cov=src --cov-report=term-missing
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/ -v -m "unit"

# Integration tests only
pytest tests/ -v -m "integration"

# E2E IMAP tests (requires credentials)
pytest tests/test_e2e_imap.py -v

# E2E LLM tests (requires API key)
pytest tests/test_e2e_llm.py -v
```

### Run Tests with Coverage

```bash
# Generate coverage report
pytest tests/ -v -m "not e2e_imap and not e2e_llm" --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html  # Windows
```

## Test Markers

Tests are categorized using pytest markers:

- **`@pytest.mark.unit`** - Unit tests (isolated, no external dependencies)
- **`@pytest.mark.integration`** - Integration tests (may use mocks)
- **`@pytest.mark.e2e_imap`** - E2E tests requiring live IMAP connections
- **`@pytest.mark.e2e_llm`** - E2E tests requiring live LLM API calls
- **`@pytest.mark.slow`** - Tests that take a long time to run

## CI Configuration

### GitHub Secrets Setup

To enable E2E tests in CI, configure the following secrets in your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add the following secrets:
   - `TEST_IMAP_SERVER` - Your test IMAP server hostname
   - `TEST_IMAP_USERNAME` - Test account username
   - `TEST_IMAP_PASSWORD` - Test account password
   - `TEST_OPENROUTER_API_KEY` - OpenRouter API key for testing

### Triggering E2E Tests

E2E tests run automatically when:
- A pull request has the `run-e2e-tests` label
- All required secrets are configured

To add the label:
```bash
# Using GitHub CLI
gh pr edit <PR_NUMBER> --add-label run-e2e-tests

# Or via GitHub web interface
# Add label "run-e2e-tests" to the pull request
```

## Test Reporting

### Coverage Reports

- **Codecov Integration:** Automatic upload to Codecov (if configured)
- **HTML Reports:** Available as workflow artifacts
- **Terminal Output:** Coverage summary in CI logs

### Test Results

- **JUnit XML:** Generated for all test runs
- **GitHub Actions:** Test results published to PR checks
- **Artifacts:** Test results and coverage reports available for download

## Mocking Strategy

### Unit Tests

Unit tests use mocks for all external dependencies:
- **IMAP Operations:** Mocked using `unittest.mock`
- **LLM API Calls:** Mocked HTTP responses
- **File System:** Temporary directories and files
- **Configuration:** Test fixtures with V3 config structure

### Integration Tests

Integration tests use:
- **Dry-Run Mode:** `--dry-run` flag to avoid external calls
- **Mock Services:** Mocked IMAP and LLM clients where appropriate
- **Test Fixtures:** Real configuration loading with test data

### E2E Tests

E2E tests use:
- **Real Services:** Actual IMAP servers and LLM APIs
- **Test Accounts:** Dedicated test accounts (not production)
- **Automatic Skipping:** Skip if credentials unavailable

## CI Best Practices

### For Developers

1. **Run Tests Locally First:**
   ```bash
   pytest tests/ -v -m "not e2e_imap and not e2e_llm"
   ```

2. **Check Coverage:**
   ```bash
   pytest tests/ -v --cov=src --cov-report=term-missing
   ```

3. **Verify Linting:**
   ```bash
   black --check src/ tests/
   isort --check-only src/ tests/
   flake8 src/ tests/
   ```

### For Maintainers

1. **Monitor Test Results:** Check CI status on all PRs
2. **Review Coverage:** Ensure coverage doesn't decrease
3. **E2E Test Usage:** Use sparingly, only when needed
4. **Update Secrets:** Keep test credentials secure and rotated

## Troubleshooting

### Issue: Tests Fail in CI but Pass Locally

**Check:**
1. Python version matches (CI uses 3.9, 3.10, 3.11)
2. Dependencies are up to date (`pip install -r requirements.txt`)
3. Test markers are correctly applied
4. Environment variables are set correctly

### Issue: E2E Tests Don't Run

**Check:**
1. PR has `run-e2e-tests` label
2. Required secrets are configured in GitHub
3. Secrets are correctly named
4. Test account credentials are valid

### Issue: Coverage Reports Missing

**Check:**
1. `pytest-cov` is installed
2. Coverage files are generated (`coverage.xml`)
3. Codecov integration is configured (optional)

### Issue: Lint Checks Fail

**Solution:**
- Run formatting tools locally:
  ```bash
  black src/ tests/
  isort src/ tests/
  ```
- Fix flake8 issues manually
- Note: Lint failures don't block merges (non-blocking)

## PDD Alignment

This CI integration implements:
- **PDD Section 5**: Testing requirements for V3 modules
- **Task 18.12**: CI integration for test suite

## Related Documentation

- **[V3 E2E Tests](v3-e2e-tests.md)** - E2E test documentation
- **[V3 Test Suite](tasks/task_018.txt)** - Complete test suite overview
- **[Test Coverage Analysis](tests/TEST_COVERAGE_ANALYSIS.md)** - Coverage details
- **[Pytest Configuration](pytest.ini)** - Pytest settings

## Reference

- **CI Workflow:** `.github/workflows/ci.yml`
- **Pytest Config:** `pytest.ini`
- **Test Directory:** `tests/`
- **Coverage Config:** `pyproject.toml` (if present)
