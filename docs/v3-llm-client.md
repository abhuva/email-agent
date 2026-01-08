# V3 LLM Client Module

**Status:** ✅ Complete (Task 4)  
**Module:** `src/llm_client.py`  
**Tests:** `tests/test_llm_client.py`

## Overview

The V3 LLM client module provides a clean interface for LLM API interactions via OpenRouter. It implements retry logic, structured JSON response parsing, and comprehensive error handling as specified in PDD Section 4.

This module handles:
- LLM API calls with retry logic
- Structured JSON response parsing
- Score extraction and validation
- Error handling and recovery

## Architecture

```
LLMClient
  ├── classify_email(email_content) → LLMResponse
  ├── _make_api_request(prompt) → API response
  ├── _parse_response(response) → LLMResponse
  └── _calculate_backoff_delay(attempt) → Retry delay
```

## Configuration

OpenRouter settings are configured in `config.yaml`:

```yaml
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'  # Environment variable name
  api_url: 'https://openrouter.ai/api/v1'
  model: 'google/gemini-2.5-flash-lite-preview-09-2025'
  temperature: 0.2
  retry_attempts: 3
  retry_delay_seconds: 5
```

Access via settings facade:
```python
from src.settings import settings

api_key = settings.get_openrouter_api_key()  # Loads from env var
api_url = settings.get_openrouter_api_url()
model = settings.get_openrouter_model()
temperature = settings.get_openrouter_temperature()
retry_attempts = settings.get_openrouter_retry_attempts()
retry_delay = settings.get_openrouter_retry_delay_seconds()
```

## Usage

### Basic Usage

```python
from src.llm_client import LLMClient

# Create client
client = LLMClient()

# Classify email
llm_response = client.classify_email(
    email_content="Subject: Important Meeting\n\nPlease attend..."
)

# Access scores
print(f"Importance: {llm_response.importance_score}")
print(f"Spam: {llm_response.spam_score}")
```

### With Custom Prompt

```python
client = LLMClient()

custom_prompt = "Analyze this email and provide scores..."
llm_response = client.classify_email(
    email_content="...",
    user_prompt=custom_prompt
)
```

### With Custom Max Characters

```python
client = LLMClient()

# Limit email content to 2000 characters
llm_response = client.classify_email(
    email_content="...",
    max_chars=2000
)
```

## LLMResponse Structure

The client returns a structured `LLMResponse` object:

```python
@dataclass
class LLMResponse:
    spam_score: int              # Spam score (0-10)
    importance_score: int        # Importance score (0-10)
    raw_response: Optional[str]  # Raw API response (for debugging)
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format."""
        return {
            "spam_score": self.spam_score,
            "importance_score": self.importance_score
        }
```

## Retry Logic

The client implements configurable retry logic with exponential backoff:

1. **Retry Attempts**: Configurable (default: 3)
2. **Backoff Strategy**: Exponential with jitter
3. **Retry Conditions**: Network errors, API errors, rate limiting

**Backoff Calculation:**
```python
delay = base_delay * (2 ** (attempt - 1)) + random_jitter
```

**Example:**
- Attempt 1: Immediate
- Attempt 2: ~5 seconds + jitter
- Attempt 3: ~10 seconds + jitter
- Attempt 4: ~20 seconds + jitter

## Error Handling

The module defines custom exceptions:

- `LLMClientError`: Base exception for LLM client errors
- `LLMAPIError`: API call failures (network, HTTP errors)
- `LLMResponseParseError`: Response parsing or validation failures

**Error Handling Flow:**
1. API call fails → Retry with backoff
2. All retries exhausted → Raise `LLMAPIError`
3. Response parsing fails → Raise `LLMResponseParseError`
4. Invalid scores → Raise `LLMResponseParseError`

**Example:**
```python
from src.llm_client import LLMClient, LLMAPIError, LLMResponseParseError

client = LLMClient()

try:
    response = client.classify_email("...")
except LLMAPIError as e:
    print(f"API call failed: {e}")
except LLMResponseParseError as e:
    print(f"Response parsing failed: {e}")
```

## Response Parsing

The client expects a JSON response with the following structure:

```json
{
  "spam_score": 2,
  "importance_score": 9
}
```

**Validation:**
- Both scores must be present
- Scores must be integers
- Scores must be in range 0-10

**Error Values:**
- If parsing fails or scores are invalid, the client raises `LLMResponseParseError`
- Downstream modules (decision logic) handle error scores (-1) separately

## API Contract (PDD Section 4)

The client implements the PDD API contract:

- **Endpoint**: POST to URL from `settings.get_openrouter_api_url()`
- **Auth**: Bearer token via `settings.get_openrouter_api_key()`
- **Request**: JSON payload with `model`, `temperature`, and messages
- **Response**: JSON object with `spam_score` and `importance_score` (both 0-10)
- **Retry**: Configurable retry attempts with exponential backoff

## Integration with Settings Facade

All configuration is accessed through the settings facade:

```python
from src.settings import settings

class LLMClient:
    def __init__(self):
        # Load configuration via facade
        self._api_key = settings.get_openrouter_api_key()
        self._api_url = settings.get_openrouter_api_url()
        self._model = settings.get_openrouter_model()
        self._temperature = settings.get_openrouter_temperature()
        self._retry_attempts = settings.get_openrouter_retry_attempts()
        self._retry_delay = settings.get_openrouter_retry_delay_seconds()
```

**No direct YAML access** - all configuration comes through the facade.

## Email Content Truncation

The client automatically truncates email content if it exceeds `max_body_chars`:

```python
# From settings
max_chars = settings.get_max_body_chars()  # Default: 4000

# Truncation happens automatically
if len(email_content) > max_chars:
    email_content = email_content[:max_chars] + "\n[Content truncated]"
```

## Logging

The client logs:
- API call attempts and retries
- Request parameters (with sensitive data redacted)
- Response parsing results
- Errors and failures

**Log Levels:**
- `INFO`: Successful classifications, retry attempts
- `WARNING`: Retry failures, parsing warnings
- `ERROR`: Final failures, exceptions

## Differences from V2

### V2 (Old)
- Direct `ConfigManager` access
- Less structured error handling
- No retry logic
- Mixed prompt and API logic

### V3 (New)
- Settings facade for configuration
- Structured retry logic with exponential backoff
- Comprehensive error handling
- Clean separation of concerns
- Structured response objects

## Testing

Run LLM client tests:
```bash
pytest tests/test_llm_client.py -v
```

Test coverage includes:
- API call success and failure
- Retry logic
- Response parsing
- Error handling
- Score validation

## PDD Alignment

This module implements:
- **PDD Section 3.1**: OpenRouter configuration structure
- **PDD Section 4**: API contract (endpoint, auth, request/response format)
- **PDD Section 4**: Retry mechanism with configurable attempts and delays
- **PDD Section 5.4**: Modular structure (`src/llm_client.py`)

## Reference

- **PDD Specification**: `pdd.md` Sections 3.1, 4, 5.4
- **Module Code**: `src/llm_client.py`
- **Tests**: `tests/test_llm_client.py`
- **Configuration**: `docs/v3-configuration.md`
- **Settings Facade**: `src/settings.py`
- **Decision Logic**: `docs/v3-decision-logic.md` (consumes LLMResponse)
