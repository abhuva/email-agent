# Conditional Summarization System

## Overview
The conditional summarization system determines whether an email should be summarized based on its tags and loads the appropriate prompt for LLM-based summarization. This is a V2 feature that enables cost-effective summarization by only processing emails with specific tags.

*Return to main doc: [README.md](../README.md) for context and documentation overview.*

## Components

### 1. Configuration Access (`get_summarization_tags`)
Safely accesses and validates the `summarization_tags` configuration from the config manager.

**Function:** `get_summarization_tags(config) -> List[str]`

**Behavior:**
- Returns list of tag strings that trigger summarization
- Validates that config value is a list of non-empty strings
- Returns empty list if config is missing, invalid, or empty
- Logs warnings for invalid configurations but never raises exceptions
- Strips whitespace from tag values

**Example:**
```python
from src.summarization import get_summarization_tags

config.summarization_tags = ['Urgent', 'Important']
tags = get_summarization_tags(config)
# Returns: ['Urgent', 'Important']
```

### 2. Tag Matching (`should_summarize_email`)
Checks if an email's tags intersect with the configured summarization tags.

**Function:** `should_summarize_email(email_tags: List[str], summarization_tags: List[str]) -> bool`

**Behavior:**
- Uses set intersection to find matching tags
- Returns `True` if any email tag matches any summarization tag
- Returns `False` if no tags match, email has no tags, or no summarization tags configured
- Case-sensitive matching
- Handles whitespace by stripping tags before comparison

**Example:**
```python
from src.summarization import should_summarize_email

email_tags = ['Urgent', 'Neutral']
summarization_tags = ['Urgent', 'Important']
should_summarize = should_summarize_email(email_tags, summarization_tags)
# Returns: True (because 'Urgent' matches)
```

### 3. Prompt Loading (`load_summarization_prompt`)
Loads the summarization prompt from the configured file path with comprehensive error handling.

**Function:** `load_summarization_prompt(prompt_path: Optional[str]) -> Optional[str]`

**Behavior:**
- Reads prompt file from filesystem
- Handles `FileNotFoundError`, `PermissionError`, and other IO exceptions
- Validates that loaded content is a non-empty string
- Returns `None` on any error and logs specific error message
- Strips leading/trailing whitespace from loaded content

**Example:**
```python
from src.summarization import load_summarization_prompt

prompt = load_summarization_prompt('config/summarization_prompt.md')
if prompt:
    print(f"Loaded {len(prompt)} characters")
```

### 4. Main Decision Function (`check_summarization_required`)
Orchestrates tag checking and prompt loading to determine if summarization should proceed.

**Function:** `check_summarization_required(email: Dict[str, Any], config) -> Dict[str, Any]`

**Returns:**
```python
{
    'summarize': bool,           # Whether summarization should proceed
    'prompt': Optional[str],      # Loaded prompt if summarize is True, None otherwise
    'reason': Optional[str]       # Reason if summarize is False (for logging)
}
```

**Behavior:**
1. Gets summarization tags from config
2. Checks if email tags match summarization tags
3. If match found, loads prompt from configured path
4. Returns structured result with decision and prompt (if available)
5. Never raises exceptions - always returns a result dict

**Reasons for `summarize=False`:**
- `'no_summarization_tags_configured'` - No tags configured in config
- `'tags_do_not_match'` - Email tags don't match any summarization tags
- `'prompt_load_failed'` - Tags match but prompt file couldn't be loaded
- `'unexpected_error: <error>'` - Unexpected exception occurred

**Example:**
```python
from src.summarization import check_summarization_required

email = {'tags': ['Urgent']}
result = check_summarization_required(email, config)

if result['summarize']:
    prompt = result['prompt']
    # Use prompt for LLM summarization call
else:
    reason = result['reason']
    # Log reason and continue without summarization
```

## Integration

### Main Loop Integration
The summarization check is integrated into the main email processing loop in `src/main_loop.py`:

1. **After successful tagging:** Once an email is successfully tagged, the system checks if summarization is required
2. **Tag extraction:** Applied tags are extracted from the tagging result (excluding `AIProcessed` and `AIProcessingFailed`)
3. **Decision:** `check_summarization_required()` is called with the email and config
4. **Storage:** The result is stored in the email dict under `email['summarization']` for later use
5. **Logging:** Appropriate log levels are used (INFO for required, DEBUG for not required)

**Code Flow:**
```python
# After successful tagging
applied_tags = result.get('applied_tags', [])
content_tags = [tag for tag in applied_tags 
               if tag not in [config.processed_tag, AI_PROCESSING_FAILED_FLAG]]

email_with_tags = {**email, 'tags': content_tags}
summarization_result = check_summarization_required(email_with_tags, config)
email['summarization'] = summarization_result
```

### Usage in Task 7 (LLM Integration)
The stored summarization result is used in Task 7 to:
- Check if `summarization_result['summarize']` is `True`
- Use `summarization_result['prompt']` for the LLM call
- Generate the summary using the loaded prompt

### Usage in Task 8 (Note Creation)
The stored summarization result is used in Task 8 to:
- Include the summary in the Obsidian note if available
- Place the summary after the YAML frontmatter and before the email body

## Configuration

### Config File (`config.yaml`)
```yaml
# List of IMAP tags that trigger AI summarization
# Only emails with these tags will have summaries generated (saves API costs)
summarization_tags:
  - 'Urgent'
  # - 'Important'  # Add more tags as needed

# Path to the Markdown prompt file used for email summarization
# This prompt is separate from the classification prompt and is only used
# when an email has a tag matching one in summarization_tags
summarization_prompt_path: 'config/summarization_prompt.md'
```

### Prompt File Format
The summarization prompt file should be a Markdown file containing instructions for the LLM on how to summarize emails. Example:

```markdown
# Email Summarization Prompt

Please provide a concise summary of the following email. Focus on:
- Key action items
- Important dates or deadlines
- Main topics discussed
- Any urgent information

Email content:
```

## Error Handling

The system is designed for **graceful degradation**:

1. **No exceptions raised:** All functions return safe defaults (empty lists, None, False) instead of raising exceptions
2. **Comprehensive logging:** Errors are logged at appropriate levels (WARNING for config issues, ERROR for file I/O)
3. **Pipeline continuation:** If summarization check fails, the email processing continues without summarization
4. **Structured results:** All decision functions return structured dicts with clear reason fields

## Test Strategy

Comprehensive test suite with 28 tests covering:

- **Config validation:** Valid tags, empty list, None, non-list, invalid items, whitespace
- **Tag matching:** Matches, no matches, empty tags, case sensitivity, whitespace handling
- **Prompt loading:** Existing file, nonexistent, empty, whitespace-only, directory path, permission errors
- **Decision function:** All scenarios including exceptions, multiple matching tags, missing email tags

**Run tests:**
```bash
pytest tests/test_summarization.py -v
```

## Best Practices

1. **Tag naming:** Use consistent, case-sensitive tag names in both `summarization_tags` and email tags
2. **Prompt design:** Keep summarization prompts focused and specific to reduce token usage
3. **Cost control:** Only add tags to `summarization_tags` that truly need summarization
4. **Error monitoring:** Check logs for summarization-related warnings to catch configuration issues early
5. **Testing:** Test summarization logic with various tag combinations before deploying

## Related Modules

- **`src/config.py`:** Configuration management and validation
- **`src/main_loop.py`:** Main processing loop integration
- **`src/openrouter_client.py`:** LLM client for actual summarization (Task 7)
- **`src/email_tagging.py`:** Email tagging that provides tags for summarization check

---

*This file is updated after every major change to the summarization system or tests.*
