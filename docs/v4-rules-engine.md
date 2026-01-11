# V4 Rules Engine - Blacklist and Whitelist Rules

**Task:** 6 (Blacklist), 7 (Whitelist)  
**Status:** ✅ Complete  
**PDD Reference:** Section 2.2, 3.2, 4.2.2

## Overview

The Rules Engine provides blacklist and whitelist rule processing functionality for the V4 email processing pipeline. 

- **Blacklist rules** are applied **BEFORE** AI processing (pre-processing) to filter out unwanted emails, either by dropping them entirely or recording them without AI classification.
- **Whitelist rules** are applied **AFTER** AI processing (post-processing) to boost importance scores and add tags to emails that match.

## Purpose

The blacklist rules component provides:
- **Pre-processing Filtering:** Filter emails before expensive AI processing
- **Flexible Matching:** Support for sender, subject, and domain-based rules
- **Action-Based Processing:** DROP (skip entirely), RECORD (raw markdown only), or PASS (normal processing)
- **Robust Error Handling:** Graceful handling of malformed rules without breaking the pipeline
- **YAML Configuration:** Simple YAML-based rule definition

## Module Location

- **File:** `src/rules.py`
- **Test File:** `tests/test_rules.py`
- **Configuration:** 
  - `config/blacklist.yaml` (blacklist rules)
  - `config/whitelist.yaml` (whitelist rules)

## Architecture

### Core Components

**Blacklist Components:**
1. **ActionEnum:** Enumeration of possible actions (DROP, RECORD, PASS)
2. **BlacklistRule:** Dataclass representing a single blacklist rule
3. **Rule Loading:** Functions to load and validate blacklist rules from YAML
4. **Rule Matching:** Helper functions for matching emails against blacklist rules
5. **Rule Evaluation:** Main function to check emails against all blacklist rules

**Whitelist Components:**
1. **WhitelistRule:** Dataclass representing a single whitelist rule
2. **Rule Loading:** Functions to load and validate whitelist rules from YAML
3. **Rule Matching:** Helper functions for matching emails against whitelist rules
4. **Score Application:** Main function to apply whitelist rules and adjust scores/tags

### Data Structures

#### ActionEnum

```python
class ActionEnum(Enum):
    DROP = "drop"      # Skip email processing entirely
    RECORD = "record"  # Generate raw markdown without AI
    PASS = "pass"      # Continue with normal processing
```

#### BlacklistRule

```python
@dataclass
class BlacklistRule:
    trigger_type: str          # "sender", "subject", or "domain"
    value: str                 # Pattern/value to match
    action: ActionEnum         # Action when matched
    pattern: Optional[Pattern] # Compiled regex (if applicable)
    raw_value: Optional[str]   # Original value for reference
```

#### WhitelistRule

```python
@dataclass
class WhitelistRule:
    trigger_type: str          # "sender", "subject", or "domain"
    value: str                 # Pattern/value to match
    score_boost: float         # Score boost to apply (>= 0)
    tags: List[str]            # Tags to add when matched
    pattern: Optional[Pattern]  # Compiled regex (if applicable)
    raw_value: Optional[str]   # Original value for reference
```

## Configuration

### Blacklist YAML Format

Blacklist rules are defined in `config/blacklist.yaml`:

```yaml
# Direct list format
- trigger: "sender"
  value: "no-reply@spam.com"
  action: "drop"

- trigger: "subject"
  value: "Unsubscribe"
  action: "record"

- trigger: "domain"
  value: "spam-domain.com"
  action: "drop"
```

Or using the `blocked_items` key:

```yaml
blocked_items:
  - trigger: "sender"
    value: "spam@example.com"
    action: "drop"
```

### Blacklist Rule Schema

Each blacklist rule must have:
- **trigger:** One of `"sender"`, `"subject"`, or `"domain"` (case-insensitive)
- **value:** The pattern to match against (string)
- **action:** One of `"drop"`, `"record"`, or `"pass"` (case-insensitive)

### Whitelist YAML Format

Whitelist rules are defined in `config/whitelist.yaml`:

```yaml
# Direct list format
- trigger: "domain"
  value: "important-client.com"
  action: "boost"
  score_boost: 20
  add_tags: ["#vip", "#work"]

- trigger: "sender"
  value: "boss@company.com"
  action: "boost"
  score_boost: 15
  add_tags: ["#priority"]

- trigger: "subject"
  value: "URGENT"
  action: "boost"
  score_boost: 10
  add_tags: ["#urgent"]
```

Or using the `allowed_items` key:

```yaml
allowed_items:
  - trigger: "domain"
    value: "important-client.com"
    action: "boost"
    score_boost: 20
    add_tags: ["#vip", "#work"]
```

### Whitelist Rule Schema

Each whitelist rule must have:
- **trigger:** One of `"sender"`, `"subject"`, or `"domain"` (case-insensitive)
- **value:** The pattern to match against (string)
- **action:** Must be `"boost"` (case-insensitive)
- **score_boost:** Numeric value (integer or float) >= 0 to add to importance_score
- **add_tags:** List of tag strings (optional, defaults to empty list)

### Matching Semantics

Both blacklist and whitelist rules use the same matching semantics:
- **Sender/Subject:** Case-insensitive substring matching (contains)
- **Domain:** Case-insensitive exact domain matching
- **Regex Support:** Values containing regex characters are automatically compiled as regex patterns

## API Reference

### Loading Blacklist Rules

```python
from src.rules import load_blacklist_rules

# Load rules from YAML file
rules = load_blacklist_rules("config/blacklist.yaml")
```

**Returns:** `List[BlacklistRule]` - List of validated rules (empty list if file missing or invalid)

**Raises:** `InvalidRuleError` - If YAML cannot be parsed

**Behavior:**
- Missing file: Returns empty list (logs warning)
- Empty file: Returns empty list (logs warning)
- Malformed rules: Skipped with warning, valid rules still loaded
- Invalid YAML: Raises `InvalidRuleError`

### Loading Whitelist Rules

```python
from src.rules import load_whitelist_rules

# Load rules from YAML file
rules = load_whitelist_rules("config/whitelist.yaml")
```

**Returns:** `List[WhitelistRule]` - List of validated rules (empty list if file missing or invalid)

**Raises:** `InvalidRuleError` - If YAML cannot be parsed

**Behavior:**
- Missing file: Returns empty list (logs warning)
- Empty file: Returns empty list (logs warning)
- Malformed rules: Skipped with warning, valid rules still loaded
- Invalid YAML: Raises `InvalidRuleError`

### Checking Blacklist

```python
from src.rules import check_blacklist
from src.models import EmailContext

# Create email context
email = EmailContext(
    uid="12345",
    sender="spam@example.com",
    subject="Test"
)

# Check against rules
action = check_blacklist(email, rules)

# Handle action
if action == ActionEnum.DROP:
    # Skip processing entirely
    pass
elif action == ActionEnum.RECORD:
    # Generate raw markdown without AI
    pass
else:  # PASS
    # Continue with normal processing
    pass
```

**Returns:** `ActionEnum` - Action to take (DROP, RECORD, or PASS)

**Priority Order:**
1. **DROP** (highest) - If any rule matches with DROP action, return DROP immediately
2. **RECORD** (medium) - If any rule matches with RECORD action, return RECORD
3. **PASS** (lowest) - Default if no rules match

### Applying Whitelist

```python
from src.rules import apply_whitelist
from src.models import EmailContext

# Create email context (after LLM classification)
email = EmailContext(
    uid="12345",
    sender="boss@company.com",
    subject="Test"
)
email.llm_score = 5.0  # Initial score from LLM

# Load whitelist rules
whitelist_rules = load_whitelist_rules("config/whitelist.yaml")

# Apply whitelist rules
new_score, tags = apply_whitelist(email, whitelist_rules, email.llm_score)

# Update email context
email.llm_score = new_score
email.whitelist_tags = tags
```

**Returns:** `tuple[float, List[str]]` - (new_score, tags_list) where:
- `new_score`: Current score plus all matching rules' score_boost values
- `tags_list`: List of all unique tags from matching rules (duplicates removed)

**Behavior:**
- Multiple matching rules are cumulative (all boosts and tags are applied)
- Duplicate tags are automatically removed
- Empty rules list returns unchanged score and empty tags list

### Rule Validation

**Blacklist Rule Validation:**

```python
from src.rules import validate_blacklist_rule

raw_rule = {
    "trigger": "sender",
    "value": "spam@example.com",
    "action": "drop"
}

rule = validate_blacklist_rule(raw_rule)
```

**Returns:** `BlacklistRule` - Validated rule object

**Raises:** `InvalidRuleError` - If rule is malformed

**Whitelist Rule Validation:**

```python
from src.rules import validate_whitelist_rule

raw_rule = {
    "trigger": "domain",
    "value": "important-client.com",
    "action": "boost",
    "score_boost": 20,
    "add_tags": ["#vip", "#work"]
}

rule = validate_whitelist_rule(raw_rule)
```

**Returns:** `WhitelistRule` - Validated rule object

**Raises:** `InvalidRuleError` - If rule is malformed

**Validation Rules:**
- `score_boost` must be >= 0 (can be integer or float)
- `add_tags` must be a list of non-empty strings (optional, defaults to empty list)
- `action` must be exactly `"boost"` for whitelist rules

## Usage Examples

### Basic Usage

```python
from src.models import EmailContext
from src.rules import load_blacklist_rules, check_blacklist, ActionEnum

# Load rules
rules = load_blacklist_rules("config/blacklist.yaml")

# Process email
email = EmailContext(
    uid="12345",
    sender="spam@example.com",
    subject="Unsubscribe Now"
)

# Check blacklist
action = check_blacklist(email, rules)

if action == ActionEnum.DROP:
    print("Email dropped - skipping processing")
elif action == ActionEnum.RECORD:
    print("Email recorded - generating raw markdown")
else:
    print("Email passed - continuing with normal processing")
```

### Integration with Pipeline

```python
def process_email(email_dict):
    # Create email context
    email = from_imap_dict(email_dict)
    
    # Load blacklist rules
    blacklist_rules = load_blacklist_rules("config/blacklist.yaml")
    
    # Check blacklist (pre-processing)
    action = check_blacklist(email, blacklist_rules)
    
    if action == ActionEnum.DROP:
        logger.info(f"Email {email.uid} dropped by blacklist")
        return None  # Skip processing
    
    if action == ActionEnum.RECORD:
        logger.info(f"Email {email.uid} recorded by blacklist")
        # Generate raw markdown without AI
        generate_raw_note(email)
        return email
    
    # Continue with normal processing
    # ... Content parsing, AI classification, etc.
    email.llm_score = llm_client.classify(email)
    
    # Apply whitelist rules (post-processing)
    whitelist_rules = load_whitelist_rules("config/whitelist.yaml")
    new_score, tags = apply_whitelist(email, whitelist_rules, email.llm_score)
    email.llm_score = new_score
    email.whitelist_tags = tags
    
    # Generate final note with adjusted score and tags
    generate_note(email)
    return email
```

## Error Handling

### Invalid Rules

Malformed rules are handled gracefully:
- **During Loading:** Invalid rules are skipped with a warning log
- **During Evaluation:** Rules causing exceptions are skipped with a warning
- **System Behavior:** Processing continues with valid rules

### Error Types

- **InvalidRuleError:** Raised when:
  - YAML cannot be parsed
  - Rule validation fails
  - Required fields are missing

### Logging

The module uses structured logging:
- **INFO:** Successful rule loading, rule counts
- **WARNING:** Missing files, skipped rules, validation failures
- **ERROR:** Unexpected errors during rule evaluation
- **DEBUG:** Regex compilation, rule matching details

## Testing

Comprehensive test coverage in `tests/test_rules.py`:

**Blacklist Tests:**
- **ActionEnum Tests:** Enum value validation
- **BlacklistRule Tests:** Dataclass validation
- **Rule Validation Tests:** YAML parsing and validation
- **Matching Tests:** Sender, subject, and domain matching
- **Evaluation Tests:** Priority handling, multiple rules
- **Loading Tests:** File handling, error cases

**Whitelist Tests:**
- **WhitelistRule Tests:** Dataclass validation (score_boost, tags)
- **Rule Validation Tests:** YAML parsing and validation (action="boost" requirement)
- **Matching Tests:** Sender, subject, and domain matching
- **Application Tests:** Score boosting, tag accumulation, duplicate handling
- **Loading Tests:** File handling, error cases

Run tests:
```bash
pytest tests/test_rules.py -v
```

**Test Count:** 103 tests total (57 blacklist + 46 whitelist)

## Integration Points

### Pipeline Integration

**Blacklist rules** are applied at the **pre-processing stage**:
**Whitelist rules** are applied at the **post-processing stage** (after LLM classification):

```
IMAP Fetch → Blacklist Check → [DROP/RECORD/PASS] → Content Parser → LLM → Whitelist Check → Final Score/Tags
```

### Dependencies

- **EmailContext:** Uses `sender` and `subject` fields for matching
- **YAML Configuration:** Loads from `config/blacklist.yaml` and `config/whitelist.yaml`
- **Logging:** Uses standard Python logging

### Future Extensions

- **Regex Patterns:** Enhanced regex support for complex matching
- **Rule Priorities:** Explicit priority levels for rules
- **Rule Groups:** Grouping rules for better organization
- **Conditional Rules:** Rules that depend on multiple conditions

## PDD Alignment

This implementation follows PDD V4 specifications:

- **Section 2.2:** Rules Engine component
- **Section 3.2:** Rules schema (YAML format)
- **Section 4.2.2:** Blacklist check in pipeline (pre-processing)
- **Section 4.2.2:** Whitelist application in pipeline (post-processing)

## See Also

- [V4 Configuration System](v4-configuration.md) - Configuration loading
- [V4 Models](v4-models.md) - EmailContext data class
- [V4 Content Parser](v4-content-parser.md) - Content processing
- [PDD V4](../pdd_V4.md) - Complete product design document
