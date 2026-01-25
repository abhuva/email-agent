# V4 Content Parser - HTML to Markdown Conversion

**Task:** 5  
**Status:** ✅ Complete  
**PDD Reference:** Section 2.3

## Overview

The content parser module converts HTML email bodies to Markdown format using the `html2text` library. It provides robust error handling with automatic fallback to plain text when HTML conversion fails, and enforces a 20,000 character limit on parsed content.

## Purpose

The content parser provides:
- **HTML to Markdown Conversion:** Converts HTML email content to clean Markdown format
- **Automatic Fallback:** Falls back to plain text when HTML is missing, empty, or conversion fails
- **Character Limit Enforcement:** Truncates content to 20,000 characters to manage token usage
- **State Tracking:** Returns a fallback flag to indicate whether HTML conversion was successful

## Module Location

- **File:** `src/content_parser.py`
- **Main Function:** `parse_html_content(html_body: str, plain_text_body: str) -> Tuple[str, bool]`
- **Helper Function:** `_html_to_markdown(html_body: str) -> str` (private)

## API Reference

### `parse_html_content(html_body: str, plain_text_body: str) -> Tuple[str, bool]`

Parse HTML email content to Markdown, with fallback to plain text.

**Parameters:**
- `html_body: str` - HTML content of the email (may be None, empty, or whitespace)
- `plain_text_body: str` - Plain text content of the email (fallback option)

**Returns:**
- `Tuple[str, bool]` - A tuple containing:
  - `parsed_content: str` - The converted Markdown content (or plain text if fallback)
  - `is_fallback: bool` - `True` if plain text was used (HTML conversion failed/skipped), `False` if HTML was successfully converted

**Behavior:**
1. If `html_body` is missing, empty, or whitespace-only → returns `plain_text_body` with `is_fallback=True`
2. Attempts HTML to Markdown conversion using `html2text`
3. If conversion produces empty/whitespace result → falls back to `plain_text_body` with `is_fallback=True`
4. If conversion raises exception → catches error, logs warning, returns `plain_text_body` with `is_fallback=True`
5. If conversion succeeds → returns Markdown content with `is_fallback=False`
6. Enforces 20,000 character limit on final content (truncation does not change `is_fallback` flag)

**Example:**
```python
from src.content_parser import parse_html_content

# Successful HTML conversion
html = "<p>Hello <strong>world</strong></p>"
text = "Hello world"
content, is_fallback = parse_html_content(html, text)
# content: "Hello **world**" (or similar Markdown)
# is_fallback: False

# Fallback to plain text
content, is_fallback = parse_html_content("", "Plain text only")
# content: "Plain text only"
# is_fallback: True
```

### `_html_to_markdown(html_body: str) -> str` (Private)

Convert HTML content to Markdown format using html2text.

**Configuration:**
- `ignore_links = False` - Keep links in Markdown
- `ignore_images = True` - Ignore images to save tokens
- `body_width = 0` - Don't wrap lines (preserve original formatting)
- `unicode_snob = True` - Use unicode characters
- `mark_code = True` - Mark code blocks

**Raises:**
- `ImportError` - If html2text library is not available
- `Exception` - If HTML conversion fails

## Integration with EmailContext

The content parser is designed to work with the `EmailContext` data class:

```python
from src.models import EmailContext
from src.content_parser import parse_html_content

# Create EmailContext from IMAP data
context = EmailContext(
    uid="12345",
    sender="sender@example.com",
    subject="Test Email",
    raw_html="<p>HTML content</p>",
    raw_text="Plain text content"
)

# Parse content
parsed_content, is_fallback = parse_html_content(
    context.raw_html or "",
    context.raw_text or ""
)

# Update EmailContext
context.parsed_body = parsed_content
context.is_html_fallback = is_fallback
```

## Character Limit Enforcement

The parser enforces a hard limit of 20,000 characters on the returned content:

- **Truncation Behavior:** Content exceeding 20,000 characters is truncated to exactly 20,000 characters
- **Flag Preservation:** The `is_fallback` flag is not changed by truncation:
  - If content came from HTML and was truncated → `is_fallback` remains `False`
  - If content came from plain text and was truncated → `is_fallback` remains `True`
- **Logging:** A warning is logged when truncation occurs, including original and truncated lengths

**Example:**
```python
# Long HTML content
long_html = "<p>" + "A" * 25000 + "</p>"
text = "Short text"
content, is_fallback = parse_html_content(long_html, text)

# Result: len(content) == 20000, is_fallback == False
```

## Error Handling

The parser handles various error conditions gracefully:

1. **Missing/Empty HTML:** Returns plain text with `is_fallback=True`
2. **Conversion Exceptions:** Catches all exceptions, logs warning, returns plain text with `is_fallback=True`
3. **Empty Conversion Result:** If HTML conversion produces empty/whitespace string, falls back to plain text
4. **Malformed HTML:** html2text handles malformed HTML gracefully, but if it fails, falls back to plain text

## Logging

The module uses Python's standard `logging` module with a module-level logger:

- **DEBUG:** Logs when HTML conversion is attempted and whether it succeeded
- **WARNING:** Logs when HTML conversion fails, produces empty result, or content is truncated

**Example Log Messages:**
```
DEBUG: Attempting HTML to Markdown conversion
DEBUG: HTML to Markdown conversion successful
WARNING: HTML to Markdown conversion failed: <error>, falling back to plain text
WARNING: HTML conversion produced empty result, falling back to plain text
WARNING: Content truncated from 25000 to 20,000 characters (is_fallback=False)
```

## Testing

Comprehensive test coverage is provided in `tests/test_content_parser.py`:

- **HTML Conversion Tests:** Successful conversion, complex formatting, links
- **Fallback Tests:** Missing HTML, empty HTML, whitespace-only HTML, conversion exceptions, empty results
- **Character Limit Tests:** HTML truncation, plain text truncation, exact limit, below limit
- **Logging Tests:** Debug logs, warning logs for failures and truncation
- **Edge Cases:** Malformed HTML, special characters, None values, empty inputs

Run tests with:
```bash
pytest tests/test_content_parser.py -v
```

## Dependencies

- **html2text:** Required library for HTML to Markdown conversion
  - Already included in `requirements.txt`
  - If not available, the module will raise `ImportError` when attempting conversion

## PDD Alignment

This implementation follows the PDD V4 Section 2.3 specifications:

- ✅ Uses `html2text` library for conversion
- ✅ Falls back to plain text on error
- ✅ Sets `is_html_fallback` flag (returned as `is_fallback` in function)
- ✅ Logs warnings on conversion failure
- ✅ Integrates with `EmailContext` data class

## Related Documentation

- [PDD V4](pdd_V4.md) - Section 2.3 for content parser specifications
- [V4 Models](v4-models.md) - EmailContext data class integration
- [V4 Configuration System](v4-configuration.md) - Configuration structure
- [V4 Pipeline Architecture](pdd_V4.md) - Overall pipeline design

## Future Enhancements

Potential future enhancements:
- Configurable character limit (currently hardcoded to 20,000)
- HTML sanitization before conversion (currently relies on html2text)
- Custom html2text configuration options
- Support for preserving specific HTML elements
- Performance optimizations for very large HTML content
