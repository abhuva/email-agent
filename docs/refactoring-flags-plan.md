# Refactoring Plan: KEYWORDS → FLAGS

## Overview

Refactor the codebase to use IMAP FLAGS instead of KEYWORDS extension, since the target IMAP server doesn't support KEYWORDS capability.

## Current State Analysis

### Files Using KEYWORDS:
1. **`src/imap_connection.py`**:
   - `IMAPKeywordsNotSupportedError` exception
   - `safe_imap_operation()` - checks for KEYWORDS capability
   - `search_emails_excluding_processed()` - uses `KEYWORD` in search (actually searches FLAGS!)

2. **`src/email_tagging.py`**:
   - Uses `add_tags_to_email()` which already uses FLAGS correctly
   - `process_email_with_ai_tags()` - fetches FLAGS correctly

3. **`tests/test_imap_safe_operations.py`**:
   - Tests KEYWORDS capability validation

4. **Documentation**:
   - References to KEYWORDS in docs

### What's Already Correct:
- ✅ `add_tags_to_email()` uses `+FLAGS` (correct!)
- ✅ `_fetch_email_flags()` uses `FETCH ... (FLAGS)` (correct!)
- ✅ Search uses `KEYWORD "tag"` which searches FLAGS (correct, just confusing name!)

### What Needs Changing:
- ❌ Remove KEYWORDS capability check
- ❌ Rename terminology from "keywords" to "flags"
- ❌ Update error messages
- ❌ Update documentation

## Refactoring Steps

### Phase 1: Test FLAGS Support (PREREQUISITE)
**Goal:** Verify FLAGS work on the target server

**Tasks:**
1. ✅ Create `scripts/test_imap_flags.py` (DONE)
2. Run test script: `python scripts/test_imap_flags.py`
3. Verify all tests pass
4. Document results

**Success Criteria:**
- Can add custom flags
- Can fetch flags
- Can search by flags
- Can exclude by flags

### Phase 2: Remove KEYWORDS Capability Check
**Goal:** Remove unnecessary KEYWORDS capability validation

**Files to Modify:**
- `src/imap_connection.py`

**Changes:**
1. Remove `IMAPKeywordsNotSupportedError` exception (or keep for backward compatibility)
2. Remove KEYWORDS capability check from `safe_imap_operation()`
3. Update docstrings to mention FLAGS instead of KEYWORDS
4. Keep the function logic the same (it already uses FLAGS!)

**Code Changes:**
```python
# BEFORE:
if 'KEYWORDS' not in capabilities_str:
    raise IMAPKeywordsNotSupportedError(...)

# AFTER:
# Remove this check entirely - FLAGS are always supported
```

### Phase 3: Update Search Function
**Goal:** Clarify that we're using FLAGS (even though search uses "KEYWORD" keyword)

**Files to Modify:**
- `src/imap_connection.py`

**Changes:**
1. Update `search_emails_excluding_processed()` docstring
2. Add comment explaining that `KEYWORD` in search actually searches FLAGS
3. Keep the search syntax the same (it's correct!)

**Code Changes:**
```python
# Add comment:
# Note: IMAP uses "KEYWORD" keyword in SEARCH to search FLAGS
# This is confusing naming in the IMAP spec, but it's correct
status, data = imap.search(None, f'{q} NOT KEYWORD "{processed_tag}"')
```

### Phase 4: Update Terminology
**Goal:** Use "flags" terminology consistently

**Files to Modify:**
- `src/imap_connection.py`
- `src/email_tagging.py`
- `src/tag_mapping.py` (variable names)
- All documentation

**Changes:**
1. Update function docstrings
2. Update variable names where appropriate
3. Update error messages
4. Update log messages

**Note:** Keep `ALLOWED_KEYWORDS` in `tag_mapping.py` as-is (it's about AI response keywords, not IMAP)

### Phase 5: Update Tests
**Goal:** Remove KEYWORDS capability tests, add FLAGS tests

**Files to Modify:**
- `tests/test_imap_safe_operations.py`
- Create `tests/test_imap_flags.py` (unit tests)

**Changes:**
1. Remove `test_safe_imap_operation_raises_on_no_keywords_support`
2. Remove `test_safe_imap_operation_validates_keywords_support`
3. Add tests for FLAGS operations
4. Update remaining tests to not check for KEYWORDS

### Phase 6: Update Documentation
**Goal:** Document FLAGS usage clearly

**Files to Modify:**
- `docs/imap-fetching.md`
- `docs/imap-keywords-vs-flags.md` (already created)
- `README.md` (if it mentions KEYWORDS)

**Changes:**
1. Update all references to KEYWORDS → FLAGS
2. Explain the confusing IMAP naming (KEYWORD searches FLAGS)
3. Add examples of FLAGS usage
4. Document server compatibility

### Phase 7: Update Live Test Script
**Goal:** Remove KEYWORDS check from live test

**Files to Modify:**
- `scripts/test_imap_live.py`

**Changes:**
1. Remove KEYWORDS capability check
2. Update test to verify FLAGS work instead
3. Update success messages

## Implementation Order

1. **Run FLAGS test** (`scripts/test_imap_flags.py`) - VERIFY IT WORKS FIRST
2. **Phase 2**: Remove KEYWORDS check from `safe_imap_operation()`
3. **Phase 3**: Update search function comments
4. **Phase 4**: Update terminology (docstrings, logs)
5. **Phase 5**: Update tests
6. **Phase 6**: Update documentation
7. **Phase 7**: Update live test script
8. **Final**: Run all tests, verify live test works

## Testing Strategy

### Unit Tests:
- All existing tests should still pass
- New FLAGS-specific tests
- Remove KEYWORDS capability tests

### Integration Tests:
- Run `scripts/test_imap_flags.py` - must pass
- Run `scripts/test_imap_live.py` - should now pass all tests
- Verify email tagging works end-to-end

### Manual Testing:
1. Connect to real IMAP server
2. Tag an email
3. Verify tag appears
4. Search for tagged email
5. Verify exclusion works

## Risk Assessment

**Low Risk:**
- We're already using FLAGS in STORE commands
- Search syntax is already correct
- Only removing capability check

**Medium Risk:**
- Need to verify FLAGS work on target server (Phase 1)
- Terminology changes might confuse users initially

**Mitigation:**
- Test thoroughly with `scripts/test_imap_flags.py` first
- Keep backward compatibility where possible
- Update documentation clearly

## Rollback Plan

If issues arise:
1. Keep `IMAPKeywordsNotSupportedError` for backward compatibility
2. Add feature flag to enable/disable KEYWORDS check
3. Revert changes file-by-file if needed

## Success Criteria

✅ All tests pass
✅ Live test script passes all tests
✅ Can tag emails on target server
✅ Can search/exclude by tags
✅ Documentation is clear and accurate
✅ No breaking changes to API

## Estimated Effort

- Phase 1 (Testing): 30 min
- Phase 2-4 (Code changes): 1-2 hours
- Phase 5 (Tests): 1 hour
- Phase 6 (Docs): 30 min
- Phase 7 (Live test): 30 min
- **Total: 3-4 hours**

## Next Steps

1. **IMMEDIATE**: Run `python scripts/test_imap_flags.py` to verify FLAGS work
2. If tests pass, proceed with Phase 2
3. If tests fail, investigate server-specific issues
