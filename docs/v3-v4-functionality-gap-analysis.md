# V3 to V4 Functionality Gap Analysis

**Date:** 2026-01-18  
**Purpose:** Identify all V3 functionality that exists but is not yet implemented in V4, to prevent accidental removal of needed features.

---

## Executive Summary

This document identifies **all V3 functionality** that is **not yet implemented in V4**. Before removing any V3 code, we must:
1. ✅ Identify the gap
2. ✅ Decide if the functionality is needed in V4
3. ✅ Either implement it in V4 OR document why it's not needed
4. ✅ Only then remove V3 code

---

## 1. CLI Command Options

### 1.1 `process` Command

#### ✅ Implemented in V4
- `--account` - Process specific account
- `--all` - Process all accounts
- `--dry-run` - Preview mode
- `--uid` - Target specific email (⚠️ **PARTIALLY** - see below)
- `--force-reprocess` - Reprocess emails (⚠️ **PARTIALLY** - see below)
- `--max-emails` - Limit number of emails (⚠️ **PARTIALLY** - see below)

#### ❌ Missing in V4
- **`--debug-prompt`** - Write formatted classification prompt to debug file
  - **V3 Location:** `src/cli_v3.py:129-132`
  - **V3 Usage:** `python main.py process --uid 400 --debug-prompt`
  - **V3 Implementation:** Passes `debug_prompt=True` to `Pipeline.process_emails()`
  - **V4 Status:** Not implemented - CLI accepts it but warns it's not supported
  - **Impact:** Users cannot debug prompt construction in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

#### ⚠️ Partially Implemented (Warnings Shown)
- **`--uid`** - Currently shows warning: "not yet fully supported in V4"
  - **V3:** Fully functional, processes single email by UID
  - **V4:** CLI accepts it but `MasterOrchestrator` doesn't pass it through
  - **Impact:** Users cannot process specific emails by UID in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

- **`--force-reprocess`** - Currently shows warning: "not yet fully supported in V4"
  - **V3:** Fully functional, ignores processed_tag
  - **V4:** CLI accepts it but `MasterOrchestrator` doesn't pass it through
  - **Impact:** Users cannot force reprocessing in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

- **`--max-emails`** - Currently shows warning: "not yet fully supported in V4"
  - **V3:** Fully functional, limits number of emails processed
  - **V4:** CLI accepts it but `MasterOrchestrator` doesn't pass it through
  - **Impact:** Users cannot limit email count for testing in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

### 1.2 `cleanup-flags` Command

#### ✅ Implemented in V4
- `--dry-run` - Preview mode
- `--account` - Account selection (⚠️ **PARTIALLY** - see below)

#### ❌ Missing in V4
- **Full implementation** - V4 CLI shows error message and exits
  - **V3 Location:** `src/cli_v3.py:292-433`
  - **V3 Features:**
    - Confirmation prompt (mandatory, security requirement)
    - Flag scanning with detailed results
    - Flag removal with summary statistics
    - Error handling and reporting
  - **V4 Status:** Placeholder only - shows error and exits
  - **Impact:** Users cannot clean up IMAP flags in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

#### ⚠️ Partially Implemented
- **`--account`** - CLI accepts it but command doesn't work
  - **V3:** Single-account only (uses global config)
  - **V4:** Should support per-account cleanup
  - **Impact:** Multi-account cleanup not possible
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

### 1.3 `backfill` Command

#### ✅ Implemented in V4
- `--account` - Account selection (required)
- `--start-date` - Date range start
- `--end-date` - Date range end
- `--force-reprocess` - Reprocess emails
- `--dry-run` - Preview mode
- `--max-emails` - Limit number of emails

#### ❌ Missing in V4
- **Full implementation** - V4 CLI shows error message and exits
  - **V3 Location:** `src/cli_v3.py:436-509`
  - **V3 Features:**
    - Date range filtering
    - Folder selection (`--folder` option)
    - Progress tracking with progress bars
    - API throttling
    - Cost estimation and safety interlock
    - Detailed summary statistics
  - **V4 Status:** Placeholder only - shows error and exits
  - **Impact:** Users cannot backfill historical emails in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

- **`--folder`** option - V3 has it, V4 doesn't
  - **V3 Location:** `src/cli_v3.py:448-451`
  - **V3 Usage:** `python main.py backfill --folder INBOX`
  - **V3 Implementation:** Allows selecting specific IMAP folder
  - **V4 Status:** Not in CLI options
  - **Impact:** Users cannot backfill specific folders in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

### 1.4 `show-config` Command

#### ✅ Fully Implemented in V4
- All options work correctly
- Better than V3 (supports account-specific config)

---

## 2. Processing Features

### 2.1 Pipeline Class Features

#### ✅ Implemented in AccountProcessor
- Email fetching
- LLM classification
- Decision logic
- Note generation
- IMAP flag setting
- Error handling per email
- Blacklist/whitelist rules
- Content parsing

#### ❌ Missing in AccountProcessor
- **`debug_prompt` option** - Write prompts to debug files
  - **V3 Location:** `src/orchestrator.py::Pipeline.process_emails()`
  - **V3 Implementation:** `LLMClient.classify_email(debug_prompt=True, debug_uid=uid)`
  - **V3 Usage:** Writes formatted prompt to `logs/debug_prompt_<timestamp>_uid_<uid>.txt`
  - **V4 Status:** Not implemented
  - **Impact:** Cannot debug prompt construction in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

- **`uid` processing** - Process single email by UID
  - **V3 Location:** `src/orchestrator.py::Pipeline.process_emails()`
  - **V3 Implementation:** `ImapClient.fetch_email_by_uid(uid)`
  - **V4 Status:** `AccountProcessor.run()` doesn't accept UID parameter
  - **Impact:** Cannot process specific emails in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

- **`force_reprocess` option** - Ignore processed_tag
  - **V3 Location:** `src/orchestrator.py::Pipeline.process_emails()`
  - **V3 Implementation:** Skips processed_tag check in IMAP query
  - **V4 Status:** `AccountProcessor.run()` has `force_reprocess` parameter but may not be fully implemented
  - **Impact:** May not be able to force reprocessing in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION** (verify implementation)

- **`max_emails` option** - Limit number of emails
  - **V3 Location:** `src/orchestrator.py::Pipeline.process_emails()`
  - **V3 Implementation:** Limits emails fetched from IMAP
  - **V4 Status:** `AccountProcessor.run()` doesn't accept max_emails parameter
  - **Impact:** Cannot limit email count for testing in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

- **Single-account mode (no --account flag)** - V3 default behavior
  - **V3:** `python main.py process` works without --account
  - **V4:** Requires `--account` or `--all`
  - **Impact:** Breaking change - V3 users need to adapt
  - **Decision Needed:** ⚠️ **REQUIRES DECISION** (is this intentional?)

### 2.2 Backfill Features

#### ❌ Not Implemented in V4
- **Full backfill functionality**
  - **V3 Location:** `src/backfill.py`
  - **V3 Features:**
    - Date range filtering
    - Folder selection
    - Progress bars (rich library)
    - API throttling
    - Cost estimation
    - Safety interlock (confirmation for large batches)
    - Detailed statistics
  - **V4 Status:** Module exists but not integrated with V4 CLI
  - **Impact:** Cannot backfill historical emails in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

### 2.3 Cleanup Flags Features

#### ❌ Not Implemented in V4
- **Full cleanup functionality**
  - **V3 Location:** `src/cleanup_flags.py`
  - **V3 Features:**
    - Flag scanning
    - Confirmation prompt (security requirement)
    - Flag removal
    - Summary statistics
    - Error handling
  - **V4 Status:** Module exists but not integrated with V4 CLI
  - **Impact:** Cannot clean up IMAP flags in V4
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

---

## 3. Configuration Features

### 3.1 Configuration Access

#### ✅ Implemented in V4
- Per-account configuration
- Config merging (global + account-specific)
- Config validation
- Config display with highlighting

#### ❌ Missing in V4
- **Single-account default mode** - V3 works without account config files
  - **V3:** Uses `config/config.yaml` directly
  - **V4:** Requires account config structure
  - **Impact:** V3 users need to restructure config
  - **Decision Needed:** ⚠️ **REQUIRES DECISION** (is this intentional?)

---

## 4. Logging Features

### 4.1 Logging Systems

#### ✅ Implemented in V4
- Standard Python logging
- Account-specific loggers
- Log file management

#### ❌ Missing in V4
- **V3 Logger features** - `src/v3_logger.py`
  - **V3 Features:**
    - `EmailLogger` - Structured email logging
    - `AnalyticsWriter` - JSONL analytics file
    - `LogFileManager` - Log file rotation/management
    - Structured logging format
  - **V4 Status:** V3 logger still used in some places, not fully migrated
  - **Impact:** May lose structured logging features
  - **Decision Needed:** ⚠️ **REQUIRES DECISION**

---

## 5. Error Handling Features

### 5.1 Error Handling Patterns

#### ✅ Implemented in V4
- Per-email error isolation
- Graceful degradation
- Error logging

#### ❌ Missing in V4
- **V3 Error Handling** - `src/error_handling_v3.py`
  - **V3 Features:**
    - `log_error_with_context()` - Contextual error logging
    - Error categorization
    - Error recovery strategies
  - **V4 Status:** May use different error handling patterns
  - **Impact:** May lose error handling features
  - **Decision Needed:** ⚠️ **REQUIRES DECISION** (verify V4 has equivalent)

---

## 6. Summary Statistics

### 6.1 Processing Summary

#### ✅ Implemented in V4
- Account-level summary
- Success/failure counts
- Total time

#### ❌ Missing in V4
- **Detailed statistics** - V3 PipelineSummary
  - **V3 Features:**
    - Average time per email
    - Per-email timing breakdown
    - Memory usage tracking
    - Detailed error breakdown
  - **V4 Status:** May have less detailed statistics
  - **Impact:** Less visibility into processing performance
  - **Decision Needed:** ⚠️ **REQUIRES DECISION** (verify V4 has equivalent)

---

## 7. Decision Matrix

| Feature | V3 Status | V4 Status | Priority | Decision Needed |
|---------|-----------|-----------|----------|-----------------|
| `--debug-prompt` | ✅ Working | ❌ Missing | Medium | ⚠️ **YES** |
| `--uid` processing | ✅ Working | ⚠️ Partial | High | ⚠️ **YES** |
| `--force-reprocess` | ✅ Working | ⚠️ Partial | High | ⚠️ **YES** |
| `--max-emails` | ✅ Working | ⚠️ Partial | Medium | ⚠️ **YES** |
| `cleanup-flags` command | ✅ Working | ❌ Missing | Medium | ⚠️ **YES** |
| `backfill` command | ✅ Working | ❌ Missing | High | ⚠️ **YES** |
| `--folder` in backfill | ✅ Working | ❌ Missing | Low | ⚠️ **YES** |
| Single-account mode | ✅ Working | ❌ Missing | High | ⚠️ **YES** |
| V3 Logger features | ✅ Working | ⚠️ Partial | Medium | ⚠️ **YES** |
| V3 Error handling | ✅ Working | ⚠️ Unknown | Medium | ⚠️ **YES** |
| Detailed statistics | ✅ Working | ⚠️ Unknown | Low | ⚠️ **YES** |

---

## 8. Recommendations

### High Priority (Must Implement Before Removing V3)
1. **`--uid` processing** - Core functionality for debugging/testing
2. **`--force-reprocess`** - Important for reprocessing emails
3. **`backfill` command** - Critical for historical email processing
4. **Single-account mode** - Breaking change, need migration path

### Medium Priority (Should Implement)
1. **`--debug-prompt`** - Useful for debugging
2. **`--max-emails`** - Useful for testing
3. **`cleanup-flags` command** - Maintenance functionality
4. **V3 Logger migration** - Ensure no feature loss

### Low Priority (Nice to Have)
1. **`--folder` in backfill** - Less commonly used
2. **Detailed statistics** - Enhancement, not critical

---

## 9. Action Items

### Before Removing V3 Code:
1. ✅ **Document all gaps** (this document)
2. ⏳ **Get user decisions** on each feature
3. ⏳ **Implement high-priority features** in V4
4. ⏳ **Verify medium-priority features** are not needed
5. ⏳ **Create migration guide** for breaking changes
6. ⏳ **Only then remove V3 code**

---

## 10. Questions for User

1. **Do you need `--debug-prompt` in V4?** (Useful for debugging prompt construction)
2. **Do you need `--uid` processing in V4?** (Process specific emails)
3. **Do you need `--force-reprocess` in V4?** (Reprocess already-processed emails)
4. **Do you need `--max-emails` in V4?** (Limit emails for testing)
5. **Do you need `cleanup-flags` command in V4?** (Maintenance operation)
6. **Do you need `backfill` command in V4?** (Historical email processing)
7. **Do you need `--folder` option in backfill?** (Backfill specific folders)
8. **Do you need single-account mode (no --account flag)?** (Breaking change)
9. **Do you need V3 logger features in V4?** (Structured logging)
10. **Do you need detailed statistics in V4?** (Performance monitoring)

---

**End of Gap Analysis Document**
