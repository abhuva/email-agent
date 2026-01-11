# V4 Rules Engine - Blacklist Rules

**Task:** 6  
**Status:** ✅ Complete  
**PDD Reference:** Section 2.2, 3.2, 4.2.2

## Overview

The Rules Engine provides blacklist and whitelist rule processing functionality for the V4 email processing pipeline. Blacklist rules are applied **BEFORE** AI processing (pre-processing) to filter out unwanted emails, either by dropping them entirely or recording them without AI classification.

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
- **Configuration:** `config/blacklist.yaml`

## Architecture

### Core Components

1. **ActionEnum:** Enumeration of possible actions (DROP, RECORD, PASS)
2. **BlacklistRule:** Dataclass representing a single blacklist rule
3. **Rule Loading:** Functions to load and validate rules from YAML
4. **Rule Matching:** Helper functions for matching emails against rules
5. **Rule Evaluation:** Main function to check emails against all rules

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

## Configuration

### YAML Format

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

### Rule Schema

Each rule must have:
- **trigger:** One of `"sender"`, `"subject"`, or `"domain"` (case-insensitive)
- **value:** The pattern to match against (string)
- **action:** One of `"drop"`, `"record"`, or `"pass"` (case-insensitive)

### Matching Semantics

- **Sender/Subject:** Case-insensitive substring matching (contains)
- **Domain:** Case-insensitive exact domain matching
- **Regex Support:** Values containing regex characters are automatically compiled as regex patterns

## API Reference

### Loading Rules

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

### Rule Validation

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
    rules = load_blacklist_rules("config/blacklist.yaml")
    
    # Check blacklist (pre-processing)
    action = check_blacklist(email, rules)
    
    if action == ActionEnum.DROP:
        logger.info(f"Email {email.uid} dropped by blacklist")
        return None  # Skip processing
    
    if action == ActionEnum.RECORD:
        logger.info(f"Email {email.uid} recorded by blacklist")
        # Generate raw markdown without AI
        generate_raw_note(email)
        return email
    
    # Continue with normal processing
    # ... AI classification, etc.
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

- **ActionEnum Tests:** Enum value validation
- **BlacklistRule Tests:** Dataclass validation
- **Rule Validation Tests:** YAML parsing and validation
- **Matching Tests:** Sender, subject, and domain matching
- **Evaluation Tests:** Priority handling, multiple rules
- **Loading Tests:** File handling, error cases

Run tests:
```bash
pytest tests/test_rules.py -v
```

## Integration Points

### Pipeline Integration

Blacklist rules are applied at the **pre-processing stage**:

```
IMAP Fetch → Blacklist Check → [DROP/RECORD/PASS] → Content Parser → LLM → ...
```

### Dependencies

- **EmailContext:** Uses `sender` and `subject` fields
- **YAML Configuration:** Loads from `config/blacklist.yaml`
- **Logging:** Uses standard Python logging

### Future Extensions

- **Whitelist Rules:** Similar structure for whitelist processing (Task 7)
- **Regex Patterns:** Enhanced regex support for complex matching
- **Rule Priorities:** Explicit priority levels for rules
- **Rule Groups:** Grouping rules for better organization

## PDD Alignment

This implementation follows PDD V4 specifications:

- **Section 2.2:** Rules Engine component
- **Section 3.2:** Rules schema (YAML format)
- **Section 4.2.2:** Blacklist check in pipeline

## See Also

- [V4 Configuration System](v4-configuration.md) - Configuration loading
- [V4 Models](v4-models.md) - EmailContext data class
- [V4 Content Parser](v4-content-parser.md) - Content processing
- [PDD V4](../pdd_V4.md) - Complete product design document
