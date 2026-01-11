# V4 Rule Syntax Guide

**Status:** Complete  
**Task:** 20.3  
**Audience:** Developers, Rule Writers  
**PDD Reference:** [pdd_V4.md](../pdd_V4.md) Section 3.2

---

## Overview

Complete reference for V4 rule syntax, including blacklist and whitelist rules, pattern matching, and rule examples. For technical implementation details, see [V4 Rules Engine](v4-rules-engine.md).

V4 rules provide fine-grained control over email processing:
- **Blacklist Rules:** Pre-processing rules applied BEFORE AI classification (drop or record emails)
- **Whitelist Rules:** Post-processing rules applied AFTER AI classification (boost scores, add tags)

---

## Rule Syntax Overview

### Rule Files

- **Blacklist Rules:** `config/blacklist.yaml`
- **Whitelist Rules:** `config/whitelist.yaml`

### Rule Structure

Rules are defined as YAML lists. Each rule is an object with specific fields:

```yaml
# Direct list format (recommended)
- trigger: "sender"  # or "subject", "domain"
  value: "pattern"
  action: "drop"      # or "record", "pass" (blacklist) / "boost" (whitelist)
  # ... additional fields depending on rule type
```

### Rule Triggers

All rules support three trigger types:

- **`sender`**: Match against email sender address
- **`subject`**: Match against email subject line
- **`domain`**: Match against sender domain (extracted from sender address)

---

## Blacklist Rules

**Purpose:** Pre-processing rules applied BEFORE AI classification  
**File:** `config/blacklist.yaml`  
**When Applied:** Before expensive AI processing (saves costs)

### Blacklist Rule Syntax

```yaml
# Direct list format
- trigger: "sender" | "subject" | "domain"
  value: "<pattern>"
  action: "drop" | "record" | "pass"
```

**Required Fields:**
- `trigger`: One of `"sender"`, `"subject"`, or `"domain"` (case-insensitive)
- `value`: Pattern to match against (string)
- `action`: One of `"drop"`, `"record"`, or `"pass"` (case-insensitive)

**Alternative Format:**
```yaml
# Using blocked_items key
blocked_items:
  - trigger: "sender"
    value: "spam@example.com"
    action: "drop"
```

### Blacklist Actions

| Action | Description | Behavior |
|--------|-------------|----------|
| `drop` | Skip email entirely | Email is ignored, no processing, no file generation |
| `record` | Generate raw markdown only | Email is converted to markdown, but no AI classification |
| `pass` | Continue normal processing | Email proceeds to normal AI processing pipeline |

**Action Priority:**
- Rules are evaluated in order
- First matching rule determines the action
- If no rules match, email proceeds to normal processing

### Blacklist Examples

**Drop Spam Senders:**
```yaml
- trigger: "sender"
  value: "no-reply@spam.com"
  action: "drop"

- trigger: "sender"
  value: "noreply@newsletter.com"
  action: "drop"
```

**Record Unsubscribe Emails:**
```yaml
- trigger: "subject"
  value: "Unsubscribe"
  action: "record"

- trigger: "subject"
  value: "Manage Preferences"
  action: "record"
```

**Block Entire Domains:**
```yaml
- trigger: "domain"
  value: "spam-domain.com"
  action: "drop"

- trigger: "domain"
  value: "newsletter-spam.com"
  action: "drop"
```

**Pass Through (Explicit):**
```yaml
# Allow specific sender even if domain is blocked
- trigger: "sender"
  value: "important@spam-domain.com"
  action: "pass"
```

---

## Whitelist Rules

**Purpose:** Post-processing rules applied AFTER AI classification  
**File:** `config/whitelist.yaml`  
**When Applied:** After AI classification, before note generation

### Whitelist Rule Syntax

```yaml
# Direct list format
- trigger: "sender" | "subject" | "domain"
  value: "<pattern>"
  action: "boost"
  score_boost: <number>  # Required: >= 0
  add_tags: ["tag1", "tag2"]  # Optional: List of tags
```

**Required Fields:**
- `trigger`: One of `"sender"`, `"subject"`, or `"domain"` (case-insensitive)
- `value`: Pattern to match against (string)
- `action`: Must be `"boost"` (case-insensitive)
- `score_boost`: Numeric value (integer or float) >= 0 to add to importance_score

**Optional Fields:**
- `add_tags`: List of tag strings (defaults to empty list if not specified)

**Alternative Format:**
```yaml
# Using allowed_items key
allowed_items:
  - trigger: "domain"
    value: "important-client.com"
    action: "boost"
    score_boost: 20
    add_tags: ["#vip", "#work"]
```

### Whitelist Actions

Whitelist rules only support the `boost` action:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `score_boost` | `number` | Amount to add to importance_score | `20` (adds 20 to score) |
| `add_tags` | `list[str]` | Tags to add to email | `["#vip", "#work"]` |

**Behavior:**
- `score_boost` is added to the AI-generated `importance_score`
- Tags are appended to the email's tag list
- Multiple whitelist rules can match (effects are cumulative)

### Whitelist Examples

**Boost Important Clients:**
```yaml
- trigger: "domain"
  value: "important-client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip", "#work"]

- trigger: "domain"
  value: "partner-company.com"
  action: "boost"
  score_boost: 15
  add_tags: ["#partner"]
```

**Boost Specific Senders:**
```yaml
- trigger: "sender"
  value: "boss@company.com"
  action: "boost"
  score_boost: 25
  add_tags: ["#priority", "#boss"]

- trigger: "sender"
  value: "team-lead@company.com"
  action: "boost"
  score_boost: 15
  add_tags: ["#team"]
```

**Boost Urgent Subjects:**
```yaml
- trigger: "subject"
  value: "URGENT"
  action: "boost"
  score_boost: 10
  add_tags: ["#urgent"]

- trigger: "subject"
  value: "Action Required"
  action: "boost"
  score_boost: 5
  add_tags: ["#action"]
```

---

## Pattern Matching

V4 rules support different pattern matching strategies:

### Exact Matching

**For Sender and Subject:**
- Case-insensitive substring matching (contains)
- Matches if the pattern appears anywhere in the field

**Examples:**
```yaml
# Matches: "no-reply@spam.com", "NO-REPLY@SPAM.COM", "test@no-reply@spam.com"
- trigger: "sender"
  value: "no-reply@spam.com"
  action: "drop"

# Matches: "Unsubscribe", "UNSUBSCRIBE", "Please unsubscribe", "unsubscribe now"
- trigger: "subject"
  value: "Unsubscribe"
  action: "record"
```

### Regex Matching

**Automatic Regex Detection:**
- If the value contains regex special characters, it's automatically compiled as a regex pattern
- Supports full Python regex syntax

**Examples:**
```yaml
# Regex: Match any sender from spam domain
- trigger: "sender"
  value: ".*@spam\\.com"  # Escaped dot for literal period
  action: "drop"

# Regex: Match subject starting with "URGENT"
- trigger: "subject"
  value: "^URGENT"  # ^ = start of string
  action: "boost"
  score_boost: 10

# Regex: Match multiple domains
- trigger: "domain"
  value: "(spam|newsletter|marketing)\\.com"
  action: "drop"
```

**Regex Tips:**
- Escape special characters with backslash (e.g., `\\.` for literal dot)
- Use `.*` for "any characters"
- Use `^` for start of string, `$` for end of string
- Test regex patterns before using in production

### Domain Matching

**For Domain Trigger:**
- Case-insensitive exact domain matching
- Extracts domain from sender address (e.g., "user@example.com" → "example.com")
- Matches only the domain part, not subdomains by default

**Examples:**
```yaml
# Matches: "user@example.com", "admin@example.com", "test@example.com"
# Does NOT match: "user@subdomain.example.com"
- trigger: "domain"
  value: "example.com"
  action: "boost"
  score_boost: 10

# To match subdomains, use regex:
- trigger: "domain"
  value: ".*\\.example\\.com"  # Matches any subdomain of example.com
  action: "boost"
  score_boost: 10
```

---

## Rule Best Practices

### Organization

1. **Group Related Rules:** Keep similar rules together
2. **Order Matters:** Place more specific rules before general ones
3. **Comment Rules:** Add comments explaining why rules exist

**Example:**
```yaml
# Block spam domains
- trigger: "domain"
  value: "spam-domain.com"
  action: "drop"

# Block newsletter spam
- trigger: "subject"
  value: "Unsubscribe"
  action: "record"

# Boost important clients
- trigger: "domain"
  value: "important-client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip"]
```

### Performance

1. **Use Domain Rules First:** Domain matching is faster than sender/subject matching
2. **Order by Frequency:** Place frequently matching rules first
3. **Avoid Complex Regex:** Simple patterns are faster than complex regex

### Maintainability

1. **Use Descriptive Values:** Use clear, descriptive patterns
2. **Document Complex Rules:** Add comments for complex regex patterns
3. **Test Rules:** Test rules with dry-run mode before deploying

### Security

1. **Validate Patterns:** Ensure regex patterns are safe (avoid ReDoS)
2. **Review Rules Regularly:** Periodically review and update rules
3. **Test Changes:** Test rule changes in dry-run mode first

---

## Rule Examples

### Complete Blacklist Example

```yaml
# config/blacklist.yaml

# Drop spam domains
- trigger: "domain"
  value: "spam-domain.com"
  action: "drop"

- trigger: "domain"
  value: "newsletter-spam.com"
  action: "drop"

# Record unsubscribe emails (save without AI processing)
- trigger: "subject"
  value: "Unsubscribe"
  action: "record"

- trigger: "subject"
  value: "Manage Preferences"
  action: "record"

# Drop specific spam senders
- trigger: "sender"
  value: "no-reply@spam.com"
  action: "drop"

# Regex: Drop any sender from spam domain
- trigger: "sender"
  value: ".*@spam\\.com"
  action: "drop"
```

### Complete Whitelist Example

```yaml
# config/whitelist.yaml

# Boost important clients
- trigger: "domain"
  value: "important-client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip", "#work"]

- trigger: "domain"
  value: "partner-company.com"
  action: "boost"
  score_boost: 15
  add_tags: ["#partner"]

# Boost specific senders
- trigger: "sender"
  value: "boss@company.com"
  action: "boost"
  score_boost: 25
  add_tags: ["#priority", "#boss"]

# Boost urgent subjects
- trigger: "subject"
  value: "URGENT"
  action: "boost"
  score_boost: 10
  add_tags: ["#urgent"]

# Regex: Boost any sender from important domain
- trigger: "sender"
  value: ".*@important\\.com"
  action: "boost"
  score_boost: 15
  add_tags: ["#important"]
```

### Combined Example

**Blacklist (pre-processing):**
```yaml
# Drop spam before AI processing
- trigger: "domain"
  value: "spam.com"
  action: "drop"
```

**Whitelist (post-processing):**
```yaml
# Boost important emails after AI processing
- trigger: "domain"
  value: "important.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#important"]
```

**Result:**
- Spam emails are dropped (no AI processing, saves cost)
- Important emails get boosted scores and tags (after AI processing)

---

## Rule Troubleshooting

### Invalid YAML Syntax

**Error:**
```
yaml.scanner.ScannerError: while scanning
```

**Solution:**
- Validate YAML syntax
- Check for missing colons, incorrect indentation
- Use spaces, not tabs

### Invalid Rule Format

**Error:**
```
InvalidRuleError: Missing required field: action
```

**Solution:**
- Ensure all required fields are present
- Check rule syntax matches examples above
- Validate trigger values: `"sender"`, `"subject"`, or `"domain"`

### Rules Not Matching

**Symptoms:**
- Rules defined but not taking effect
- Emails not being dropped/boosted as expected

**Solution:**
- Check pattern matching (case-insensitive, substring matching)
- Verify trigger type matches field being checked
- Test with dry-run mode to see rule evaluation
- Check rule order (first matching rule wins)

### Regex Not Working

**Symptoms:**
- Regex patterns not matching as expected

**Solution:**
- Escape special characters (e.g., `\\.` for literal dot)
- Test regex patterns in Python before using
- Use online regex testers to validate patterns
- Check regex syntax (Python regex, not shell glob)

### Performance Issues

**Symptoms:**
- Slow rule evaluation
- High CPU usage

**Solution:**
- Use domain rules first (faster than sender/subject)
- Simplify complex regex patterns
- Order rules by frequency (most common first)
- Consider caching compiled regex patterns

For more troubleshooting, see [V4 Troubleshooting Guide](v4-troubleshooting.md).

---

## Related Documentation

- [V4 Rules Engine](v4-rules-engine.md) - Technical implementation details
- [V4 Rule Examples](v4-rule-examples.md) - Common rule patterns
- [V4 Configuration Reference](v4-configuration-reference.md) - Configuration context
