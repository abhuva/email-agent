# Complete V4 Migration Plan

**Task:** 22 - Complete V4 Migration  
**Subtask:** 22.1 - Analysis and Migration Plan  
**Date:** 2026-01-17  
**Status:** In Progress

---

## Executive Summary

This document provides a comprehensive analysis of V3 components that need to be migrated to V4, and a detailed plan for completing the migration. The goal is to achieve a clean V4-only codebase with no V3 remnants, backward compatibility layers, or dual-mode routing.

---

## 1. V3 Modules to Remove

### Core V3 Modules (To Be Deleted)

1. **`src/cli_v3.py`** - V3 Click CLI (900 lines)
   - **Replacement:** V4 CLI using MasterOrchestrator
   - **Commands to migrate:**
     - `process` - Main processing command
     - `cleanup-flags` - IMAP flag cleanup
     - `backfill` - Historical email processing
     - `show-config` - Configuration display (already has V4 support)

2. **`src/config_v3_loader.py`** - V3 configuration loader
   - **Replacement:** `src/config_loader.py` (V4 ConfigLoader)

3. **`src/config_v3_schema.py`** - V3 configuration schema
   - **Replacement:** `src/config_schema.py` (V4 schema)

4. **`src/settings.py`** - V3 settings facade (singleton pattern)
   - **Replacement:** V4 ConfigLoader (per-account configuration)

5. **`src/v3_logger.py`** - V3 logging system
   - **Replacement:** `src/logging_config.py` + `src/logging_context.py` (V4 logging)

6. **`src/error_handling_v3.py`** - V3 error handling
   - **Replacement:** V4 error handling (integrated into modules)

### V3 Classes/Functions to Remove

1. **`Pipeline` class** in `src/orchestrator.py`
   - **Replacement:** `MasterOrchestrator` + `AccountProcessor` (V4)
   - **Location:** Lines 158-1200+ in `orchestrator.py`
   - **Dependencies:** Used by `cli_v3.py`, `backfill.py`, tests

2. **V3-specific functions** in various modules
   - Backward compatibility shims
   - V3-specific configuration access patterns

---

## 2. V3 Dependencies Analysis

### Files Using `cli_v3.py`

- `main.py` - Main entry point (line 29, 246)
- `tests/test_cli_v3.py` - Test file (entire file)

### Files Using `Pipeline` Class

**Source Files:**
- `src/cli_v3.py` - Line 246, 258
- `src/backfill.py` - Line 37, 323

**Test Files:**
- `tests/test_e2e_imap.py` - Lines 38, 384, 444, 583
- `tests/test_integration_v3_workflow.py` - Lines 17, 53, 114, 168, 239, 287, 336, 369, 411, 473, 514, 557, 608, 657, 712, 775, 843, 889, 942, 990, 1036, 1059
- `tests/test_orchestrator.py` - Lines 142, 156, 172, 191, 213, 252, 290, 363, 408, 430, 449, 527, 572, 617
- `tests/test_e2e_llm.py` - Line 443
- `tests/test_backfill.py` - Line 22

### Files Using `settings.py` (V3 Facade)

**Source Files (17 files):**
- `src/orchestrator.py` - Pipeline class initialization
- `src/cli_v3.py` - Configuration initialization
- `src/logging_config.py` - Configuration access
- `src/imap_client.py` - IMAP configuration
- `src/note_generator.py` - Path configuration
- `src/email_summarization.py` - Summarization config
- `src/llm_client.py` - LLM configuration
- `src/config_v3_schema.py` - Schema validation
- `src/settings.py` - Self (facade implementation)
- `src/summarization.py` - Summarization config
- `src/backfill.py` - Configuration access
- `src/cleanup_flags.py` - Configuration access
- `src/v3_logger.py` - Logging configuration
- `src/dry_run_processor.py` - Configuration access
- `src/error_handling_v3.py` - Error handling config
- `src/decision_logic.py` - Decision thresholds
- `src/prompt_renderer.py` - Prompt configuration

### Files Using `v3_logger.py`

**Source Files (4 files):**
- `src/orchestrator.py` - Pipeline class uses EmailLogger
- `src/account_processor.py` - Line 1478-1479 (tries to use V3 logger)
- `src/v3_logger.py` - Self
- `src/error_handling_v3.py` - Error logging

---

## 3. Migration Mapping

### CLI Commands Migration

| V3 Command | V3 Implementation | V4 Implementation | Status |
|------------|-------------------|-------------------|--------|
| `process` | `cli_v3.py::process()` | `MasterOrchestrator.run()` | ✅ Exists |
| `process --account <name>` | `cli_v3.py::_process_v4_accounts()` | `main.py::main_v4()` | ✅ Exists |
| `cleanup-flags` | `cli_v3.py::cleanup_flags()` | **TODO:** Add to V4 CLI | ❌ Missing |
| `backfill` | `cli_v3.py::backfill()` | **TODO:** Add to V4 CLI | ❌ Missing |
| `show-config` | `cli_v3.py::show_config()` | **TODO:** Add to V4 CLI | ⚠️ Partial |

### Configuration Migration

| V3 Pattern | V4 Pattern | Example |
|------------|------------|---------|
| `settings.get_imap_server()` | `config.imap.server` | Direct config access |
| `settings.initialize(path, env)` | `ConfigLoader(base_dir).load_merged_config(account)` | Per-account config |
| Singleton `settings` | Per-account `config` objects | No global state |

### Logging Migration

| V3 Pattern | V4 Pattern | Example |
|------------|------------|---------|
| `EmailLogger()` | `logging.getLogger('email_agent')` | Standard logging |
| `get_email_logger()` | `logging.getLogger(__name__)` | Module-level logger |
| Dual logging system | Centralized logging | Single logging system |

### Orchestration Migration

| V3 Pattern | V4 Pattern | Example |
|------------|------------|---------|
| `Pipeline().process_emails()` | `MasterOrchestrator.run()` → `AccountProcessor.run()` | Multi-account support |
| Single-account processing | Multi-account processing | Account isolation |

---

## 4. Test Files to Update

### Test Files Requiring Major Updates

1. **`tests/test_cli_v3.py`** (entire file)
   - **Action:** Delete or rewrite for V4 CLI
   - **Dependencies:** Tests `cli_v3.py` commands

2. **`tests/test_integration_v3_workflow.py`** (entire file)
   - **Action:** Rewrite to use V4 components
   - **Dependencies:** Tests `Pipeline` class extensively

3. **`tests/test_orchestrator.py`**
   - **Action:** Update to test `MasterOrchestrator` instead of `Pipeline`
   - **Dependencies:** Tests `Pipeline` class

4. **`tests/test_backfill.py`**
   - **Action:** Update to use V4 components
   - **Dependencies:** Uses `Pipeline` class

5. **`tests/test_e2e_imap.py`**
   - **Action:** Update to use V4 components
   - **Dependencies:** Uses `Pipeline` class

6. **`tests/test_e2e_llm.py`**
   - **Action:** Update to use V4 components
   - **Dependencies:** Uses `Pipeline` class

### Test Files Requiring Minor Updates

- Any test that imports or mocks `settings` facade
- Any test that uses `v3_logger` or `EmailLogger`
- Any test that references V3 configuration patterns

---

## 5. Documentation to Update

### Documentation Files Requiring Updates

1. **`README.md`** - Update CLI examples, remove V3 references
2. **`README-AI.md`** - Update architecture diagrams, remove V3 references
3. **`docs/v3-*.md`** - Mark as deprecated or archive
4. **`docs/v4-*.md`** - Update to reflect V4-only architecture
5. **`docs/MAIN_DOCS.md`** - Update index, remove V3 sections
6. **`docs/ui-approach-comparison.md`** - Already created, reference in migration

### New Documentation Needed

1. **V4 Migration Guide** - For users migrating from V3
2. **V4 Architecture Overview** - Complete V4 architecture documentation
3. **V4 CLI Reference** - Complete CLI command reference

---

## 6. Migration Strategy

### Phase 1: Analysis and Planning ✅ (Current)

- [x] Identify all V3 components
- [x] Map dependencies
- [x] Create migration plan
- [ ] Validate migration plan with stakeholders

### Phase 2: CLI Migration

1. **Create V4 CLI Structure**
   - Create new CLI module (or update existing)
   - Implement base command structure
   - Integrate with MasterOrchestrator

2. **Migrate Commands**
   - Migrate `process` command
   - Migrate `cleanup-flags` command
   - Migrate `backfill` command
   - Migrate `show-config` command

3. **Update Main Entry Point**
   - Remove V3/V4 routing logic
   - Make V4 the only mode
   - Remove `cli_v3` import

### Phase 3: Configuration Migration

1. **Update All Modules**
   - Replace `settings` facade with `ConfigLoader`
   - Update all configuration access patterns
   - Ensure per-account configuration support

2. **Remove V3 Config Modules**
   - Delete `config_v3_loader.py`
   - Delete `config_v3_schema.py`
   - Delete `settings.py`

### Phase 4: Logging Migration

1. **Update All Modules**
   - Replace `v3_logger` with V4 logging
   - Update all logging calls
   - Ensure account context in logs

2. **Remove V3 Logger**
   - Delete `v3_logger.py`
   - Remove all `EmailLogger` usage

### Phase 5: Orchestrator Cleanup

1. **Remove Pipeline Class**
   - Identify all Pipeline usage
   - Replace with MasterOrchestrator/AccountProcessor
   - Update all references

2. **Clean Up Orchestrator Module**
   - Remove Pipeline class definition
   - Keep only MasterOrchestrator and AccountProcessor
   - Update module documentation

### Phase 6: Error Handling Migration

1. **Update Error Handling**
   - Replace `error_handling_v3` with V4 patterns
   - Update all error handling code
   - Ensure consistent error reporting

2. **Remove V3 Error Handling**
   - Delete `error_handling_v3.py`
   - Remove all references

### Phase 7: Backward Compatibility Removal

1. **Remove Compatibility Code**
   - Remove all adapters and shims
   - Remove version checks
   - Remove conditional V3/V4 code
   - Clean up comments and docstrings

### Phase 8: UI/Output Formatting

1. **Integrate DryRunOutput**
   - Add DryRunOutput to MasterOrchestrator
   - Update all output formatting
   - Ensure consistent UX

### Phase 9: Test Migration

1. **Update Tests**
   - Rewrite V3-specific tests
   - Update all test imports
   - Update test fixtures and mocks
   - Ensure all tests pass

2. **Remove V3 Test Files**
   - Delete or rewrite `test_cli_v3.py`
   - Update integration tests

### Phase 10: Documentation

1. **Update Documentation**
   - Update all user-facing docs
   - Update developer docs
   - Archive V3 documentation
   - Create V4 migration guide

### Phase 11: Final Verification

1. **Code Verification**
   - Search for all V3 references
   - Verify no V3 imports remain
   - Verify no V3 modules exist
   - Run full test suite

2. **Documentation Verification**
   - Verify all docs updated
   - Verify no V3 references in docs
   - Verify migration guide complete

---

## 7. Risk Assessment

### High Risk Areas

1. **Configuration Migration**
   - **Risk:** Many modules depend on `settings` facade
   - **Mitigation:** Systematic replacement, thorough testing

2. **Pipeline Class Removal**
   - **Risk:** Core functionality, many dependencies
   - **Mitigation:** Ensure MasterOrchestrator has all features

3. **Test Migration**
   - **Risk:** Large number of tests need updating
   - **Mitigation:** Update incrementally, maintain test coverage

### Medium Risk Areas

1. **CLI Migration**
   - **Risk:** User-facing changes
   - **Mitigation:** Maintain command compatibility where possible

2. **Logging Migration**
   - **Risk:** Log format changes
   - **Mitigation:** Ensure log compatibility or migration path

### Low Risk Areas

1. **Documentation Updates**
   - **Risk:** Outdated documentation
   - **Mitigation:** Systematic review and update

---

## 8. Success Criteria

### Code Quality

- [ ] No V3 modules exist in `src/` directory
- [ ] No V3 imports in any source file
- [ ] No backward compatibility code
- [ ] No V3/V4 routing logic
- [ ] Single code path (V4 only)

### Functionality

- [ ] All V3 commands work in V4
- [ ] All tests pass
- [ ] No regression in functionality
- [ ] Multi-account support working
- [ ] UI/Output formatting consistent

### Documentation

- [ ] All documentation updated
- [ ] No V3 references in user docs
- [ ] V4 migration guide complete
- [ ] Architecture docs reflect V4-only

### Testing

- [ ] All tests updated for V4
- [ ] Test coverage maintained or improved
- [ ] Integration tests pass
- [ ] E2E tests pass

---

## 9. Implementation Notes

### Key Decisions

1. **CLI Framework:** Keep Click or switch to argparse?
   - **Decision:** Keep Click (already used in V4, familiar)

2. **Configuration Access:** How to handle per-account config?
   - **Decision:** Use ConfigLoader per account (already implemented)

3. **Logging:** How to maintain log compatibility?
   - **Decision:** Use V4 logging system, update log format

4. **Pipeline Functionality:** How to ensure feature parity?
   - **Decision:** Verify MasterOrchestrator + AccountProcessor have all features

### Dependencies

- **Click** - CLI framework (keep)
- **colorama** - Color output (keep for DryRunOutput)
- **Pydantic** - Configuration validation (keep)
- **Standard logging** - Replace v3_logger

---

## 10. Next Steps

1. **Review and Approve Plan** - Get stakeholder approval
2. **Start Phase 2** - Begin CLI migration
3. **Incremental Migration** - Migrate one component at a time
4. **Continuous Testing** - Test after each phase
5. **Documentation Updates** - Update docs as we go

---

## Appendix: File Inventory

### V3 Files to Delete

```
src/cli_v3.py
src/config_v3_loader.py
src/config_v3_schema.py
src/settings.py
src/v3_logger.py
src/error_handling_v3.py
```

### V3 Classes to Remove

```
src/orchestrator.py::Pipeline
src/orchestrator.py::ProcessOptions (V3 version)
src/orchestrator.py::ProcessingResult (V3 version)
src/orchestrator.py::PipelineSummary (V3 version)
```

### Test Files to Update/Delete

```
tests/test_cli_v3.py (delete or rewrite)
tests/test_integration_v3_workflow.py (rewrite)
tests/test_orchestrator.py (update)
tests/test_backfill.py (update)
tests/test_e2e_imap.py (update)
tests/test_e2e_llm.py (update)
```

---

**End of Migration Plan**
