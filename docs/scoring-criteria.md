# Email Scoring Criteria

This document defines the detailed criteria for scoring email importance (0-10) and spam likelihood (0-10) as part of the V3 score-based classification system.

## Importance Score (0-10)

The importance score measures how critical or actionable an email is to the recipient.

### Scoring Factors

#### High Importance Indicators (Score 7-10)

**Score 10 - Critical/Urgent:**
- Direct action required with explicit deadlines (e.g., "Please respond by 5 PM today")
- Time-sensitive business decisions or approvals needed
- Security alerts, account access issues, or critical system notifications
- Personal emergencies or urgent family matters
- Legal or financial deadlines (e.g., tax filing, contract signing)
- From known important contacts (boss, client, family) with urgent content

**Score 9 - Very Important:**
- Action required within 24-48 hours
- Important project updates or status changes
- Meeting invitations for important events
- Financial transactions requiring confirmation
- Important notifications from services you actively use
- From important contacts with actionable content

**Score 8 - Important:**
- Action required within a week
- Work-related tasks or assignments
- Important updates from subscribed services
- Personal correspondence requiring response
- Meeting confirmations or schedule changes
- From known contacts with relevant content

**Score 7 - Moderately Important:**
- Action required but not urgent
- Informational updates from important sources
- Newsletters or updates from services you use regularly
- Personal correspondence that may need a response

#### Medium Importance Indicators (Score 4-6)

**Score 6 - Somewhat Important:**
- Informational content from known sources
- Updates from services you occasionally use
- Personal correspondence that's nice to read but not urgent
- Social notifications (LinkedIn, etc.) that may be relevant

**Score 5 - Neutral/Standard:**
- Standard transactional emails (receipts, confirmations)
- Routine notifications from services
- General newsletters from subscribed sources
- Personal correspondence with no action required

**Score 4 - Low Importance:**
- Automated notifications that are informational only
- Marketing emails from brands you've interacted with
- Social media notifications
- General updates that don't require action

#### Low Importance Indicators (Score 0-3)

**Score 3 - Very Low Importance:**
- Marketing emails from unknown or rarely-used services
- Automated system notifications
- Social media updates
- General informational content

**Score 2 - Minimal Importance:**
- Bulk marketing emails
- Automated notifications you rarely check
- Low-priority social updates

**Score 1 - Negligible:**
- Automated system messages
- Bulk informational emails
- Low-value notifications

**Score 0 - No Importance:**
- Completely irrelevant content
- Automated system messages with no user value
- Test emails or system diagnostics

### Edge Cases

- **Empty or near-empty emails:** Score 0-1 (no content = no importance)
- **Emails with only attachments:** Score based on sender relationship and subject line
- **Forwarded emails:** Score based on forwarder's relationship and their added context
- **Reply chains:** Score based on latest message content and sender
- **Calendar invites:** Score 7-9 depending on sender and event importance

## Spam Score (0-10)

The spam score measures the likelihood that an email is unsolicited, malicious, or unwanted.

### Scoring Factors

#### High Spam Indicators (Score 7-10)

**Score 10 - Definite Spam:**
- Obvious phishing attempts (fake login pages, suspicious links)
- "Nigerian prince" style scams
- Emails with malicious attachments
- Suspicious sender domains that don't match claimed identity
- Excessive use of spam trigger words ("FREE", "URGENT", "CLICK NOW", "LIMITED TIME")
- Poor grammar and spelling errors typical of spam
- Requests for personal information or passwords

**Score 9 - Very Likely Spam:**
- Aggressive marketing with multiple spam indicators
- Suspicious links to unknown domains
- Unusual sender addresses (random characters, suspicious domains)
- Excessive capitalization and exclamation marks
- Promises that seem too good to be true
- Requests to click links or download files from unknown sources

**Score 8 - Likely Spam:**
- Marketing emails with multiple red flags
- Sender doesn't match expected identity
- Suspicious subject lines with spam keywords
- Unusual formatting or HTML structure
- Links to shortened URLs or suspicious domains
- Generic greetings ("Dear Customer" instead of your name)

**Score 7 - Probably Spam:**
- Marketing emails with some suspicious characteristics
- Sender from unknown or rarely-used service
- Subject line with spam-like characteristics
- Generic content that doesn't reference your account

#### Medium Spam Indicators (Score 4-6)

**Score 6 - Possibly Spam:**
- Marketing emails from services you may have signed up for
- Generic promotional content
- Sender from unknown brand
- Some spam-like characteristics but not definitive

**Score 5 - Neutral/Uncertain:**
- Marketing emails from known brands
- Newsletters you may have subscribed to
- Transactional emails from legitimate services
- Generic notifications

**Score 4 - Probably Legitimate:**
- Marketing emails from brands you've interacted with
- Newsletters from subscribed sources
- Transactional emails from known services
- Personal correspondence

#### Low Spam Indicators (Score 0-3)

**Score 3 - Likely Legitimate:**
- Emails from known contacts
- Transactional emails from trusted services
- Personal correspondence
- Work-related emails

**Score 2 - Very Likely Legitimate:**
- Emails from close contacts (family, close colleagues)
- Important service notifications
- Personal correspondence with familiar content
- Work emails from known colleagues

**Score 1 - Almost Certainly Legitimate:**
- Emails from trusted contacts
- Important personal or work correspondence
- Verified service notifications
- Emails matching expected patterns

**Score 0 - Definitely Legitimate:**
- Emails from verified contacts in your address book
- Important personal or work correspondence
- Verified transactional emails from trusted services
- Emails you were expecting

### Spam Detection Factors

**Sender Analysis:**
- Domain reputation (known spam domains = higher score)
- Sender address format (random characters = higher score)
- SPF/DKIM/DMARC alignment (misalignment = higher score)
- Relationship to recipient (unknown sender = higher score)

**Content Analysis:**
- Spam trigger words ("FREE", "URGENT", "WINNER", "CLICK NOW")
- Suspicious links (shortened URLs, mismatched domains)
- Poor grammar and spelling
- Excessive capitalization and punctuation
- Generic greetings vs. personalized content
- Requests for personal information or passwords

**Technical Indicators:**
- Missing or suspicious email headers
- Unusual HTML structure
- Embedded tracking pixels from unknown sources
- Suspicious attachment types
- Mismatched "From" and "Reply-To" addresses

### Edge Cases

- **Newsletters from subscribed sources:** Score 1-3 (legitimate but may be unwanted)
- **Marketing from brands you've purchased from:** Score 2-4 (legitimate but promotional)
- **Transactional emails:** Score 0-2 (usually legitimate)
- **Emails with only images:** Score 5-7 (common spam technique, but may be legitimate marketing)
- **Emails in foreign languages:** Score 4-6 (context-dependent)
- **Emails with suspicious links but from known sender:** Score 3-5 (could be compromised account)

## Threshold Alignment

As specified in the PDD:
- **Importance Threshold:** 8 (emails with importance_score >= 8 are considered "important")
- **Spam Threshold:** 5 (emails with spam_score >= 5 are considered likely spam)

These thresholds ensure:
- Only truly important emails (score 8-10) are flagged as important
- Emails with moderate spam likelihood (score 5-10) are flagged for review
- The system maintains a balance between false positives and false negatives

## Scoring Consistency Guidelines

1. **Sender Relationship:** Known contacts should generally have lower spam scores and higher importance scores
2. **Content Relevance:** Emails with actionable content should have higher importance scores
3. **Urgency Indicators:** Time-sensitive language increases importance score
4. **Spam Patterns:** Multiple spam indicators compound to increase spam score
5. **Context Matters:** The same email may score differently based on recipient's relationship with sender
6. **Conservative Approach:** When uncertain, err on the side of lower spam scores to avoid false positives

## Examples

### Example 1: Important Work Email
- **From:** Known colleague
- **Subject:** "Project deadline moved to tomorrow - action needed"
- **Content:** Clear action items with deadline
- **Importance Score:** 9
- **Spam Score:** 0

### Example 2: Newsletter
- **From:** Subscribed newsletter service
- **Subject:** "Weekly Newsletter - Issue #123"
- **Content:** Informational newsletter content
- **Importance Score:** 4
- **Spam Score:** 2

### Example 3: Phishing Attempt
- **From:** "noreply@paypall.com" (typo in domain)
- **Subject:** "URGENT: Verify your account NOW"
- **Content:** Suspicious link, requests password
- **Importance Score:** 1
- **Spam Score:** 10

### Example 4: Marketing Email
- **From:** Known brand you've purchased from
- **Subject:** "Special offer - 20% off today only"
- **Content:** Promotional content with legitimate links
- **Importance Score:** 3
- **Spam Score:** 3

### Example 5: Personal Email
- **From:** Family member
- **Subject:** "Dinner plans for this weekend"
- **Content:** Personal correspondence
- **Importance Score:** 6
- **Spam Score:** 0
