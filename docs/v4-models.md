# V4 Models - EmailContext Data Class

**Task:** 4  
**Status:** ✅ Complete  
**PDD Reference:** Section 5.1

## Overview

The `EmailContext` data class is a core component of the V4 email processing pipeline. It tracks email metadata and processing state as emails move through the pipeline stages: parsing, LLM classification, whitelist/blacklist rules, and final action determination.

## Purpose

The `EmailContext` class provides:
- **State Tracking:** Maintains all email information and processing state in a single, structured object
- **Type Safety:** Uses Python dataclasses with explicit type hints for better code safety and IDE support
- **Pipeline Integration:** Designed to be passed through pipeline stages, with each stage updating relevant fields
- **Helper Methods:** Convenience methods for common state checks and updates

## Module Location

- **File:** `src/models.py`
- **Class:** `EmailContext`
- **Utility Function:** `from_imap_dict()`

## Data Structure

### Required Fields

These fields must be provided when creating an `EmailContext` instance:

- `uid: str` - Email UID from IMAP server
- `sender: str` - Email sender address
- `subject: str` - Email subject line

### Optional Raw Content

- `raw_html: Optional[str]` - Raw HTML content of the email (if available)
- `raw_text: Optional[str]` - Raw plain text content of the email (if available)

### State Flags (Pipeline-Populated)

- `parsed_body: Optional[str]` - Parsed/converted body content (Markdown after HTML conversion)
- `is_html_fallback: bool` - Flag indicating if HTML parsing failed and plain text was used (default: `False`)

### Classification (Pipeline-Populated)

- `llm_score: Optional[float]` - LLM classification score (0-10 scale, default: `None`)
- `llm_tags: List[str]` - List of tags assigned by LLM classification (default: empty list)

### Rules (Pipeline-Populated)

- `whitelist_boost: float` - Score boost applied by whitelist rules (default: `0.0`)
- `whitelist_tags: List[str]` - List of tags added by whitelist rules (default: empty list)
- `result_action: Optional[str]` - Final action taken (e.g., "PROCESSED", "DROPPED", "RECORDED", default: `None`)

## Usage

### Creating EmailContext from IMAP Data

The `from_imap_dict()` utility function converts IMAP email dictionaries into `EmailContext` instances:

```python
from src.models import EmailContext, from_imap_dict

# From IMAP client
email_dict = imap_client.get_email_by_uid('12345')
context = from_imap_dict(email_dict)

# Direct construction
context = EmailContext(
    uid='12345',
    sender='sender@example.com',
    subject='Test Email',
    raw_html='<p>HTML content</p>',
    raw_text='Plain text content'
)
```

### Pipeline Integration Pattern

```python
# Stage 1: Initial construction from IMAP
email_dict = imap_client.get_email_by_uid(uid)
context = from_imap_dict(email_dict)

# Stage 2: Content parsing
context.parsed_body = content_parser.parse(context.raw_html)
context.is_html_fallback = False  # or True if parsing failed

# Stage 3: LLM classification
llm_result = llm_client.classify(context)
context.llm_score = llm_result.score
context.add_llm_tag("important")
context.add_llm_tag("work")

# Stage 4: Whitelist rules
whitelist_result = rules_engine.apply_whitelist(context)
context.add_whitelist_tag("vip", boost=2.0)

# Stage 5: Final action
context.result_action = "PROCESSED"
```

## Helper Methods

### `add_llm_tag(tag: str) -> None`

Add a tag to the LLM tags list, preventing duplicates.

```python
context.add_llm_tag("important")
context.add_llm_tag("work")
# Duplicate tags are not added
context.add_llm_tag("important")  # No effect
```

### `add_whitelist_tag(tag: str, boost: float = 0.0) -> None`

Add a whitelist tag and optionally adjust the whitelist boost.

```python
context.add_whitelist_tag("vip")
context.add_whitelist_tag("client", boost=5.0)
# Boost accumulates
context.add_whitelist_tag("important", boost=3.0)
# Total boost: 8.0
```

### `is_scored() -> bool`

Check if the email has been scored by the LLM.

```python
if context.is_scored():
    print(f"Score: {context.llm_score}")
```

### `has_result() -> bool`

Check if a final action has been determined.

```python
if context.has_result():
    print(f"Action: {context.result_action}")
```

## Design Decisions

### Mutable Dataclass

The `EmailContext` class is mutable (not frozen) to allow pipeline stages to update fields as the email progresses through processing. This enables a single instance to be passed through all stages.

### Default Factories for Lists

List fields (`llm_tags`, `whitelist_tags`) use `field(default_factory=list)` to avoid shared mutable defaults. Each instance gets its own empty list.

### Repr Optimization

Large fields (`raw_html`, `raw_text`) are excluded from the `repr()` output using `field(repr=False)` to improve logging readability. Only key metadata fields are shown in string representations.

### Optional vs Required Fields

Required fields (`uid`, `sender`, `subject`) have no defaults and must be provided at construction. Pipeline-populated fields use `Optional[...] = None` to indicate they're set during processing.

## Testing

Comprehensive tests are available in `tests/test_models.py`:

- **Structure Tests:** Required fields, defaults, list field isolation
- **Helper Method Tests:** Tag management, state checks
- **Conversion Tests:** `from_imap_dict()` with various input formats
- **Pipeline Integration Tests:** State transitions through pipeline stages

Run tests with:
```bash
pytest tests/test_models.py -v
```

## Integration with V4 Pipeline

The `EmailContext` class is designed for the V4 processing pipeline:

1. **IMAP Fetch:** Create `EmailContext` from IMAP data using `from_imap_dict()`
2. **Blacklist Check:** Set `result_action = "DROPPED"` if email matches blacklist
3. **Content Parsing:** Set `parsed_body` and `is_html_fallback`
4. **LLM Classification:** Set `llm_score` and `llm_tags`
5. **Whitelist Rules:** Set `whitelist_boost` and `whitelist_tags`
6. **Action Selection:** Set final `result_action`

## Related Documentation

- [PDD V4](../pdd_V4.md) - Section 5.1 for API contract specification
- [V4 Configuration System](v4-configuration.md) - Configuration structure
- [V4 Pipeline Architecture](../pdd_V4.md) - Overall pipeline design

## Future Enhancements

Potential future enhancements:
- Immutable variant for specific use cases
- Validation methods for field constraints
- Serialization support for persistence
- Additional helper methods for common operations
