# V3 Note Generator Module

**Status:** ✅ Complete (Tasks 7-8)  
**Module:** `src/note_generator.py`  
**Template:** `config/note_template.md.j2`  
**Tests:** `tests/test_note_generator.py`

## Overview

The V3 Note Generator module provides templating functionality for generating Markdown notes from email content and classification results using Jinja2. It implements a flexible template system that allows users to customize the format of generated notes while maintaining compliance with PDD Section 3.2 frontmatter specifications.

## Architecture

The module consists of three main components:

1. **TemplateLoader** - Handles template file loading and validation
2. **TemplateRenderer** - Renders templates with email data and classification results
3. **NoteGenerator** - High-level interface coordinating template loading and rendering

```
┌─────────────────┐
│ NoteGenerator   │
│  (Main Entry)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────────┐
│Loader │ │  Renderer   │
└───────┘ └─────────────┘
    │         │
    │    ┌────▼────┐
    │    │ Jinja2  │
    │    │ Engine  │
    │    └─────────┘
    │
┌───▼──────────────┐
│ Template File    │
│ (.md.j2)         │
└──────────────────┘
```

## Configuration

The note generator uses the `settings.py` facade for all configuration access:

```python
from src.settings import settings

# Get template file path
template_path = settings.get_template_file()  # Default: 'config/note_template.md.j2'
```

**Configuration Path:**
- `paths.template_file` in `config.yaml` (default: `'config/note_template.md.j2'`)

## Usage

### Basic Usage

```python
from src.note_generator import NoteGenerator
from src.decision_logic import ClassificationResult

# Initialize generator
generator = NoteGenerator()

# Generate note from email data and classification
email_data = {
    'uid': '12345',
    'subject': 'Test Email',
    'from': 'sender@example.com',
    'to': ['recipient@example.com'],
    'date': '2024-01-01T12:00:00Z',
    'body': 'Email content here...',
    'html_body': '<p>Email content here...</p>',
    'headers': {}
}

classification_result = ClassificationResult(...)

# Generate Markdown note
note_content = generator.generate_note(email_data, classification_result)
```

### Without Classification Result

The generator can create notes even when classification fails:

```python
# Generate note without classification (uses error values)
note_content = generator.generate_note(email_data, None)
```

## Template System

### Template Location

Templates are Jinja2 files (`.md.j2` extension) located at the path specified in `config.yaml`:

```yaml
paths:
  template_file: 'config/note_template.md.j2'
```

### Template Variables

The following variables are available in templates:

#### Email Data
- `uid`: Email UID from IMAP server
- `subject`: Email subject line
- `from`: Sender email address
- `to`: List of recipient addresses
- `date`: Email date (various formats)
- `body`: Plain text email body
- `html_body`: HTML email body (if available)
- `headers`: All email headers (dict)

#### Classification Results
- `is_important`: Boolean (true if importance_score >= threshold)
- `is_spam`: Boolean (true if spam_score >= threshold)
- `importance_score`: Integer (0-10, or -1 for errors)
- `spam_score`: Integer (0-10, or -1 for errors)
- `confidence`: Float (0.0-1.0)
- `status`: String ("success" or "error")
- `tags`: List of tags (includes "email", "important" if applicable)

#### LLM Output (Nested)
- `llm_output.importance_score`: Integer
- `llm_output.spam_score`: Integer
- `llm_output.model_used`: String

#### Processing Metadata (Nested)
- `processing_meta.script_version`: String (always "3.0")
- `processing_meta.processed_at`: String (ISO timestamp)
- `processing_meta.status`: String

#### Configuration
- `importance_threshold`: Integer (default: 8)
- `spam_threshold`: Integer (default: 5)

### Custom Jinja2 Filters

The module provides custom filters for common formatting tasks:

#### `format_date(value, format_str='%Y-%m-%d')`
Format a date string to a specific format.

```jinja2
{{ date | format_date('%Y-%m-%d') }}
```

#### `format_datetime(value)`
Format a date string to ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).

```jinja2
{{ date | format_datetime }}
```

#### `truncate(value, length=100)`
Truncate a string with ellipsis.

```jinja2
{{ body | truncate(200) }}
```

### Template Example

See `config/note_template.md.j2` for a complete example template with:
- YAML frontmatter (PDD Section 3.2 compliant)
- Email metadata display
- Conditional classification indicators
- Classification details section
- Email body content
- Processing metadata footer

## Frontmatter Structure (PDD Section 3.2)

The generated notes include YAML frontmatter that matches the PDD specification:

```yaml
---
uid: 12345
subject: "Email Subject"
from: "sender@example.com"
to: ["recipient@example.com"]
date: "2024-01-01T12:00:00Z"
tags: ["email", "important"]
llm_output:
  importance_score: 9
  spam_score: 2
  model_used: "claude-3-opus"
processing_meta:
  script_version: "3.0"
  processed_at: "2024-01-01T12:00:00Z"
  status: "success"
---
```

**Key Features:**
- All fields from PDD Section 3.2 are included
- Tags automatically include "email" and "important" if score >= threshold
- Status is "success" for successful classification, "error" for failures
- ISO 8601 datetime format for dates

## Error Handling

The module includes comprehensive error handling:

1. **Template Loading Errors**
   - If primary template fails to load, generator initializes without renderer
   - Fallback template is used when primary template rendering fails

2. **Template Rendering Errors**
   - Syntax errors are caught and logged
   - Missing variables use defaults or empty values
   - Fallback template ensures notes are always generated

3. **Fallback Template**
   - Simple template embedded in code
   - Used when primary template is unavailable or fails
   - Ensures system continues functioning even with template issues

## Customization

### Creating Custom Templates

1. Copy the default template:
   ```bash
   cp config/note_template.md.j2 config/my_custom_template.md.j2
   ```

2. Modify the template structure and formatting as needed

3. Update `config.yaml`:
   ```yaml
   paths:
     template_file: 'config/my_custom_template.md.j2'
   ```

4. Test with dry-run:
   ```bash
   python main.py process --uid <email_uid> --dry-run
   ```

### Template Best Practices

- Always quote string values in YAML frontmatter to handle special characters
- Use conditional blocks (`{% if %}`) to show/hide sections based on data
- Test templates with various email types (important, spam, error cases)
- Keep frontmatter structure aligned with PDD Section 3.2 specification
- Use Jinja2 comments (`{# ... #}`) for documentation (they're stripped in output)
- Use filters for data transformation (format_date, truncate, etc.)

## Integration Points

### Consumes
- **Email Data** from `src/imap_client.py` (via `ImapClient.get_email_by_uid()`)
- **Classification Results** from `src/decision_logic.py` (via `ClassificationResult`)
- **Configuration** from `src/settings.py` facade

### Uses
- **Jinja2** templating engine
- **settings.py** facade for configuration access

### Produces
- **Markdown Notes** with YAML frontmatter (ready for Obsidian vault)

## Testing

Run the test suite:

```bash
pytest tests/test_note_generator.py -v
```

**Test Coverage:**
- Template loading and validation
- Template rendering with various inputs
- Error handling and fallback behavior
- Custom filter functionality
- Integration tests verifying PDD compliance

**22 tests total** covering all functionality.

## PDD Alignment

This module implements:

- **PDD Section 3.2**: Output Data Schema (Markdown Frontmatter)
- **PDD Section 5**: Backend Implementation Plan (note generation)
- **PDD Section 6**: Frontend Implementation Plan (template system)

**Key Compliance Points:**
- ✅ YAML frontmatter structure matches PDD Section 3.2 exactly
- ✅ Template file location configurable via `paths.template_file`
- ✅ All configuration access through `settings.py` facade
- ✅ Error handling with fallback templates
- ✅ Comprehensive logging for debugging

## Examples

### Example 1: Basic Note Generation

```python
from src.note_generator import NoteGenerator
from src.decision_logic import ClassificationResult, ClassificationStatus

generator = NoteGenerator()

email_data = {
    'uid': '12345',
    'subject': 'Important Meeting',
    'from': 'boss@company.com',
    'to': ['me@company.com'],
    'date': '2024-01-15T10:00:00Z',
    'body': 'We need to discuss the project...',
    'headers': {}
}

classification = ClassificationResult(
    is_important=True,
    is_spam=False,
    importance_score=9,
    spam_score=1,
    confidence=0.9,
    status=ClassificationStatus.SUCCESS,
    raw_scores={'importance_score': 9, 'spam_score': 1},
    metadata={'model_used': 'claude-3-opus', 'processed_at': '2024-01-15T10:05:00Z'}
)

note = generator.generate_note(email_data, classification)
# Returns Markdown with frontmatter and formatted content
```

### Example 2: Custom Template with Conditional Sections

```jinja2
---
uid: {{ uid }}
subject: "{{ subject }}"
tags: {{ tags | tojson }}
---

# {{ subject }}

{% if is_important %}
> 🚨 URGENT: This email requires immediate attention!
{% endif %}

**From:** {{ from }}  
**Date:** {{ date | format_date }}

{{ body }}
```

## Troubleshooting

### Template Not Found

**Error:** `TemplateLoaderError: Template file not found`

**Solution:**
1. Verify template file exists at path in `config.yaml`
2. Check file permissions
3. Ensure path is relative to project root or absolute

### Template Syntax Errors

**Error:** `TemplateRenderError: Template syntax error`

**Solution:**
1. Validate Jinja2 syntax in template file
2. Check for unclosed tags or filters
3. Use fallback template temporarily while fixing syntax

### Missing Variables

**Symptom:** Template renders with empty values

**Solution:**
1. Check that email data includes all required fields
2. Verify classification result is properly formatted
3. Use default values in template: `{{ variable | default('N/A') }}`

## Related Documentation

- [PDD Section 3.2](../pdd.md#32-output-data-schema-markdown-frontmatter) - Frontmatter specification
- [V3 Configuration Guide](v3-configuration.md) - Configuration system
- [V3 Decision Logic](v3-decision-logic.md) - Classification results format
- [Jinja2 Documentation](https://jinja.palletsprojects.com/) - Template syntax

## Future Enhancements

Potential future improvements:
- Template inheritance and includes
- Multiple template support (different templates for different email types)
- HTML to Markdown conversion in templates
- Attachment metadata in templates
- Template caching for performance
