# V4 End-to-End Test Scenarios

**Task:** 19.3  
**Status:** ✅ Complete  
**PDD Reference:** Task 19 - Perform End-to-End Testing

## Overview

This document defines comprehensive end-to-end test scenarios for the V4 email processing pipeline. These scenarios cover the complete pipeline from email fetching to note generation, including multi-account processing, rule application, HTML parsing, and all other features.

## Test Scenario Categories

### 1. Single-Account Basic Flow

#### Scenario 1.1: Process Single Plain Text Email

**Description:** Process a single plain text email through the complete pipeline.

**Test Data:**
- **Email Type:** Plain text
- **Subject:** "E2E Test - Plain Text Email"
- **Body:** Simple text content
- **Sender:** test-sender@example.com
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched from IMAP
2. Blacklist check passes (no match)
3. Content parsed (plain text, no HTML conversion needed)
4. LLM classification returns scores
5. Whitelist check applied (no match)
6. Note generated with correct content
7. Note saved to vault
8. Email tagged with AIProcessed

**Assertions:**
- Note file exists in vault
- Note contains correct subject, sender, date
- Note contains email body
- Note contains LLM scores
- Email has AIProcessed flag set
- Logs show successful processing

#### Scenario 1.2: Process Single HTML Email

**Description:** Process a single HTML email with HTML-to-Markdown conversion.

**Test Data:**
- **Email Type:** HTML
- **Subject:** "E2E Test - HTML Email"
- **Body:** HTML content with formatting
- **Sender:** test-sender@example.com
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched from IMAP
2. Blacklist check passes
3. HTML content parsed to Markdown
4. LLM classification returns scores
5. Whitelist check applied
6. Note generated with Markdown content
7. Note saved to vault
8. Email tagged with AIProcessed

**Assertions:**
- Note file exists in vault
- Note contains converted Markdown (not raw HTML)
- HTML formatting preserved in Markdown
- Note contains LLM scores
- Email has AIProcessed flag set

#### Scenario 1.3: Process Email with Attachments

**Description:** Process an email with attachments (attachments are not processed, but email is).

**Test Data:**
- **Email Type:** Multipart with attachments
- **Subject:** "E2E Test - Email with Attachments"
- **Body:** Text content
- **Attachments:** PDF, image files
- **Sender:** test-sender@example.com
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched from IMAP
2. Email processed normally (attachments noted but not processed)
3. Note generated
4. Note saved to vault
5. Email tagged with AIProcessed

**Assertions:**
- Note file exists
- Note mentions attachments (if template includes)
- Email has AIProcessed flag set

### 2. Multi-Account Processing

#### Scenario 2.1: Process Multiple Accounts Sequentially

**Description:** Process multiple accounts in sequence, verifying state isolation.

**Test Data:**
- **Accounts:** test-gmail-1, test-gmail-2
- **Emails:** One email per account
- **Account Configs:** Different vaults, different settings

**Expected Behavior:**
1. Account 1 processed (email fetched, processed, note created)
2. Account 2 processed (email fetched, processed, note created)
3. Complete isolation between accounts

**Assertions:**
- Account 1 note in account 1 vault
- Account 2 note in account 2 vault
- No cross-contamination between accounts
- Separate logs per account
- Both accounts processed successfully

#### Scenario 2.2: Process All Accounts

**Description:** Process all configured accounts using --all-accounts flag.

**Test Data:**
- **Accounts:** All available test accounts
- **Emails:** One email per account

**Expected Behavior:**
1. All accounts discovered
2. Each account processed in sequence
3. Summary shows all accounts processed

**Assertions:**
- All accounts processed
- Notes created in correct vaults
- Summary shows correct counts
- No failures in any account

#### Scenario 2.3: Account Failure Isolation

**Description:** Verify that failure in one account doesn't affect others.

**Test Data:**
- **Account 1:** Valid account with email
- **Account 2:** Invalid credentials (will fail)
- **Account 3:** Valid account with email

**Expected Behavior:**
1. Account 1 processed successfully
2. Account 2 fails (invalid credentials)
3. Account 3 processed successfully
4. Error logged for account 2
5. Summary shows 2 successful, 1 failed

**Assertions:**
- Account 1 and 3 processed successfully
- Account 2 failure logged
- No cross-contamination
- Summary shows correct failure count

### 3. Rules Engine Testing

#### Scenario 3.1: Blacklist Drop Rule

**Description:** Email matches blacklist rule and is dropped (not processed).

**Test Data:**
- **Email:** From spam@example.com (matches blacklist)
- **Blacklist Rule:**
  ```yaml
  - trigger: "sender"
    value: "spam@example.com"
    action: "drop"
  ```
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched from IMAP
2. Blacklist check matches
3. Email dropped (no processing)
4. Email NOT tagged with AIProcessed
5. Log shows email dropped

**Assertions:**
- No note file created
- Email does NOT have AIProcessed flag
- Log shows blacklist drop
- Email remains unprocessed

#### Scenario 3.2: Blacklist Record Rule

**Description:** Email matches blacklist rule and is recorded (raw markdown, no AI).

**Test Data:**
- **Email:** From automated@example.com (matches blacklist)
- **Blacklist Rule:**
  ```yaml
  - trigger: "sender"
    value: "automated@example.com"
    action: "record"
  ```
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched from IMAP
2. Blacklist check matches
3. Raw markdown file generated (no AI processing)
4. Email tagged with AIProcessed
5. Log shows email recorded

**Assertions:**
- Note file created (raw markdown)
- Note does NOT contain LLM scores
- Email has AIProcessed flag set
- Log shows blacklist record

#### Scenario 3.3: Whitelist Boost Rule

**Description:** Email matches whitelist rule and gets score boost and tags.

**Test Data:**
- **Email:** From important-client@example.com (matches whitelist)
- **Whitelist Rule:**
  ```yaml
  - trigger: "domain"
    value: "important-client.com"
    action: "boost"
    score_boost: 20
    add_tags: ["#vip", "#work"]
  ```
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched from IMAP
2. Blacklist check passes
3. Content parsed
4. LLM classification returns scores
5. Whitelist check matches
6. Score boosted (+20)
7. Tags added (#vip, #work)
8. Note generated with boosted score and tags
9. Email tagged with AIProcessed

**Assertions:**
- Note file exists
- Note contains boosted importance_score
- Note contains tags (#vip, #work)
- Email has AIProcessed flag set
- Log shows whitelist boost applied

#### Scenario 3.4: Multiple Whitelist Rules Match

**Description:** Email matches multiple whitelist rules (all boosts/tags applied).

**Test Data:**
- **Email:** From client@important-client.com (matches multiple rules)
- **Whitelist Rules:**
  ```yaml
  - trigger: "domain"
    value: "important-client.com"
    action: "boost"
    score_boost: 20
    add_tags: ["#vip"]
  - trigger: "sender"
    value: "client@important-client.com"
    action: "boost"
    score_boost: 10
    add_tags: ["#client"]
  ```
- **Account:** test-gmail-1

**Expected Behavior:**
1. Both whitelist rules match
2. Score boosted by sum (20 + 10 = 30)
3. All tags added (#vip, #client)
4. Note generated with combined boosts/tags

**Assertions:**
- Note contains boosted score (base + 30)
- Note contains all tags (#vip, #client)
- Log shows both rules applied

#### Scenario 3.5: Whitelist Before Blacklist

**Description:** Verify whitelist rules are checked before blacklist rules.

**Test Data:**
- **Email:** From important-client@example.com
- **Whitelist Rule:** Matches domain (boost)
- **Blacklist Rule:** Matches sender (drop)
- **Account:** test-gmail-1

**Expected Behavior:**
1. Whitelist check first (matches, boost applied)
2. Blacklist check second (matches, but whitelist takes precedence)
3. Email processed normally (not dropped)

**Assertions:**
- Email processed (not dropped)
- Whitelist boost applied
- Note contains boosted score

### 4. Content Parsing Testing

#### Scenario 4.1: Complex HTML Parsing

**Description:** Parse complex HTML with tables, images, links.

**Test Data:**
- **Email Type:** Complex HTML
- **Subject:** "E2E Test - Complex HTML"
- **Body:** HTML with tables, images, links, formatting
- **Account:** test-gmail-1

**Expected Behavior:**
1. HTML content parsed to Markdown
2. Tables converted to Markdown tables
3. Images converted to Markdown image syntax
4. Links converted to Markdown links
5. Formatting preserved

**Assertions:**
- Note contains Markdown (not HTML)
- Tables rendered correctly
- Images referenced correctly
- Links work correctly
- Formatting preserved

#### Scenario 4.2: HTML Parsing Fallback

**Description:** HTML parsing fails, fallback to plain text.

**Test Data:**
- **Email Type:** Malformed HTML
- **Subject:** "E2E Test - HTML Fallback"
- **Body:** Malformed HTML that causes parsing error
- **Account:** test-gmail-1

**Expected Behavior:**
1. HTML parsing attempted
2. Parsing fails (error logged)
3. Fallback to plain text body
4. Processing continues with plain text
5. Note generated with plain text

**Assertions:**
- Note contains plain text (not HTML)
- Log shows HTML parsing error
- Processing_error flag set in note
- Note still generated successfully

#### Scenario 4.3: Plain Text Only Email

**Description:** Process email with only plain text (no HTML).

**Test Data:**
- **Email Type:** Plain text only
- **Subject:** "E2E Test - Plain Text Only"
- **Body:** Plain text content
- **Account:** test-gmail-1

**Expected Behavior:**
1. No HTML parsing needed
2. Plain text used directly
3. Note generated with plain text

**Assertions:**
- Note contains plain text
- No HTML parsing errors
- Note generated successfully

### 5. Edge Cases and Error Handling

#### Scenario 5.1: Empty Email Body

**Description:** Process email with empty body.

**Test Data:**
- **Email Type:** Plain text
- **Subject:** "E2E Test - Empty Body"
- **Body:** (empty)
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email fetched
2. Empty body handled gracefully
3. Note generated with empty body
4. Processing continues

**Assertions:**
- Note file created
- Note contains empty body section
- No errors in processing
- Email tagged with AIProcessed

#### Scenario 5.2: Very Long Email

**Description:** Process email that exceeds max_body_chars limit.

**Test Data:**
- **Email Type:** Plain text
- **Subject:** "E2E Test - Very Long Email"
- **Body:** Very long content (> max_body_chars)
- **Account:** test-gmail-1

**Expected Behavior:**
1. Email body truncated to max_body_chars
2. Truncated body sent to LLM
3. Note generated with truncated body
4. Log shows truncation

**Assertions:**
- Note contains truncated body
- Body length <= max_body_chars
- Log shows truncation
- Processing continues

#### Scenario 5.3: IMAP Connection Failure

**Description:** Handle IMAP connection failure gracefully.

**Test Data:**
- **Account:** Invalid credentials (connection fails)
- **Account:** test-gmail-1

**Expected Behavior:**
1. IMAP connection attempted
2. Connection fails
3. Error logged
4. Account processing skipped
5. Other accounts continue processing

**Assertions:**
- Error logged clearly
- Account skipped (not processed)
- Other accounts unaffected
- Summary shows failure

#### Scenario 5.4: LLM API Failure

**Description:** Handle LLM API failure with retry logic.

**Test Data:**
- **Email:** Normal email
- **LLM API:** Simulated failure (or actual failure)
- **Account:** test-gmail-1

**Expected Behavior:**
1. LLM API call attempted
2. API call fails
3. Retry logic activated
4. Retries up to retry_attempts
5. If all retries fail, error logged, email skipped

**Assertions:**
- Retry attempts logged
- Error handled gracefully
- Email skipped if all retries fail
- Other emails continue processing

#### Scenario 5.5: Note Generation Failure

**Description:** Handle note generation failure gracefully.

**Test Data:**
- **Email:** Normal email
- **Vault:** Read-only or invalid path
- **Account:** test-gmail-1

**Expected Behavior:**
1. Note generation attempted
2. File write fails
3. Error logged
4. Email tagged with NoteCreationFailed
5. Processing continues

**Assertions:**
- Error logged clearly
- Email tagged with NoteCreationFailed
- Processing continues
- Other emails unaffected

### 6. Provider-Specific Testing

#### Scenario 6.1: Gmail Provider

**Description:** Test with Gmail IMAP server.

**Test Data:**
- **Account:** test-gmail-1 (Gmail)
- **Email:** Normal email
- **IMAP Server:** imap.gmail.com:993

**Expected Behavior:**
1. Gmail IMAP connection successful
2. Email fetched from Gmail
3. Processing completes successfully

**Assertions:**
- Gmail connection works
- Email fetched successfully
- Note generated
- Email tagged

#### Scenario 6.2: Outlook Provider

**Description:** Test with Outlook IMAP server.

**Test Data:**
- **Account:** test-outlook-1 (Outlook)
- **Email:** Normal email
- **IMAP Server:** outlook.office365.com:993

**Expected Behavior:**
1. Outlook IMAP connection successful
2. Email fetched from Outlook
3. Processing completes successfully

**Assertions:**
- Outlook connection works
- Email fetched successfully
- Note generated
- Email tagged

#### Scenario 6.3: Custom IMAP Provider

**Description:** Test with custom IMAP server.

**Test Data:**
- **Account:** test-custom-1 (Custom IMAP)
- **Email:** Normal email
- **IMAP Server:** mail.custom-domain.com:993

**Expected Behavior:**
1. Custom IMAP connection successful
2. Email fetched from custom server
3. Processing completes successfully

**Assertions:**
- Custom IMAP connection works
- Email fetched successfully
- Note generated
- Email tagged

### 7. Safety Interlock Testing

#### Scenario 7.1: Cost Estimation

**Description:** Verify cost estimation for email processing.

**Test Data:**
- **Account:** test-gmail-1
- **Emails:** 10 emails
- **Cost Config:** cost_per_1k_tokens: 0.0001

**Expected Behavior:**
1. Cost estimated before processing
2. Cost displayed to user
3. User confirmation requested
4. Processing proceeds after confirmation

**Assertions:**
- Cost estimate calculated correctly
- Cost displayed clearly
- Confirmation requested
- Processing proceeds after confirmation

#### Scenario 7.2: Cost Threshold Skip

**Description:** Skip confirmation for low-cost operations.

**Test Data:**
- **Account:** test-gmail-1
- **Emails:** 1 email (low cost)
- **Config:** skip_confirmation_below_threshold: true, cost_threshold: 0.10

**Expected Behavior:**
1. Cost estimated
2. Cost below threshold
3. Confirmation skipped
4. Processing proceeds automatically

**Assertions:**
- Cost below threshold
- Confirmation skipped
- Processing proceeds automatically

## Test Data Requirements

### Test Email Templates

Test email templates are defined in `tests/e2e_helpers.py`:

1. **Plain Text Email**
   - Subject: "E2E Test - Plain Text Email"
   - Body: Simple text content
   - Sender: test-sender@example.com

2. **HTML Email**
   - Subject: "E2E Test - HTML Email"
   - Body: HTML content with formatting
   - Sender: test-sender@example.com

3. **Blacklist Match Email**
   - Subject: "E2E Test - Blacklist Match"
   - Body: Normal content
   - Sender: spam@example.com (matches blacklist)

4. **Whitelist Match Email**
   - Subject: "E2E Test - Whitelist Match"
   - Body: Normal content
   - Sender: important-client@example.com (matches whitelist)

5. **Complex HTML Email**
   - Subject: "E2E Test - Complex HTML"
   - Body: HTML with tables, images, links
   - Sender: test-sender@example.com

### Test Rules Configuration

Test rules are configured in `config/blacklist.yaml` and `config/whitelist.yaml`:

**Blacklist Rules:**
- Drop spam@example.com
- Record automated@example.com
- Drop unwanted-domain.com

**Whitelist Rules:**
- Boost important-client.com (+20, #vip, #work)
- Boost client@important-client.com (+10, #client)

## Test Execution Strategy

### Test Execution Order

1. **Basic Flow Tests** - Verify core functionality
2. **Multi-Account Tests** - Verify state isolation
3. **Rules Engine Tests** - Verify rule application
4. **Content Parsing Tests** - Verify HTML parsing
5. **Edge Case Tests** - Verify error handling
6. **Provider Tests** - Verify provider compatibility
7. **Safety Interlock Tests** - Verify cost estimation

### Test Data Preparation

Before running E2E tests:

1. **Send Test Emails** to test accounts
2. **Configure Test Rules** in blacklist/whitelist files
3. **Verify Email Availability** in test accounts
4. **Prepare Test Vaults** (created automatically by fixtures)

### Test Assertions

Each test scenario includes:

- **File Assertions** - Note files exist, content correct
- **Flag Assertions** - Email flags set correctly
- **Log Assertions** - Logs show expected behavior
- **State Assertions** - No cross-contamination
- **Error Assertions** - Errors handled gracefully

## Success Criteria

A test scenario passes if:

1. ✅ All expected behaviors occur
2. ✅ All assertions pass
3. ✅ No unexpected errors
4. ✅ Logs show correct behavior
5. ✅ State isolation maintained

## Next Steps

After designing test scenarios:

1. **Proceed to Subtask 19.4:** Implement automated E2E test suite
2. **Proceed to Subtask 19.5:** Execute and iterate on test runs

## Related Documentation

- `docs/v4-e2e-test-setup.md` - Test account setup
- `docs/v4-e2e-test-environment.md` - Test environment setup
- `tests/e2e_helpers.py` - Test utilities
- `tests/conftest_e2e_v4.py` - Test fixtures
