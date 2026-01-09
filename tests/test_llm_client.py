"""
Tests for V3 LLM client module.

These tests verify LLM API interactions, retry logic, and response parsing.
Uses mocking to avoid requiring actual API access.
"""
import pytest
import json
import time
from unittest.mock import Mock, MagicMock, patch, call
from requests.exceptions import HTTPError, RequestException, Timeout

from src.llm_client import (
    LLMClient,
    LLMResponse,
    LLMAPIError,
    LLMResponseParseError,
    LLMClientError
)
from src.settings import Settings


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings facade for testing."""
    settings_mock = Mock(spec=Settings)
    settings_mock.get_openrouter_api_key.return_value = 'test_api_key'
    settings_mock.get_openrouter_api_url.return_value = 'https://openrouter.ai/api/v1'
    settings_mock.get_openrouter_model.return_value = 'test-model'
    settings_mock.get_openrouter_temperature.return_value = 0.2
    settings_mock.get_openrouter_retry_attempts.return_value = 3
    settings_mock.get_openrouter_retry_delay_seconds.return_value = 1  # Short delay for tests
    settings_mock.get_max_body_chars.return_value = 4000
    
    # Patch the settings singleton
    import src.llm_client
    monkeypatch.setattr(src.llm_client, 'settings', settings_mock)
    return settings_mock


def test_llm_response_dataclass():
    """Test LLMResponse dataclass."""
    response = LLMResponse(spam_score=2, importance_score=8)
    assert response.spam_score == 2
    assert response.importance_score == 8
    assert response.to_dict() == {"spam_score": 2, "importance_score": 8}


def test_llm_client_initialization():
    """Test that LLMClient initializes correctly."""
    client = LLMClient()
    assert client._api_key is None
    assert client._api_url is None


@patch('src.llm_client.requests.post')
def test_llm_client_classify_email_success(mock_post, mock_settings):
    """Test successful email classification."""
    # Mock API response - return dict directly from json() method
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 2, "importance_score": 8}'
            }
        }]
    }
    mock_response = MagicMock()
    # Ensure json() is a callable that returns the actual dict
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    result = client.classify_email("Test email content")
    
    assert isinstance(result, LLMResponse)
    assert result.spam_score == 2
    assert result.importance_score == 8
    
    # Verify API call was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert 'https://openrouter.ai/api/v1/chat/completions' in str(call_args[0])
    assert call_args[1]['headers']['Authorization'] == 'Bearer test_api_key'
    assert call_args[1]['json']['model'] == 'test-model'
    assert call_args[1]['json']['temperature'] == 0.2


@patch('src.llm_client.requests.post')
def test_llm_client_classify_email_with_user_prompt(mock_post, mock_settings):
    """Test email classification with custom user prompt."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 1, "importance_score": 9}'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    result = client.classify_email(
        "Test email",
        user_prompt="Custom classification prompt"
    )
    
    assert result.spam_score == 1
    assert result.importance_score == 9
    
    # Verify custom prompt was used
    call_args = mock_post.call_args
    messages = call_args[1]['json']['messages']
    assert "Custom classification prompt" in messages[1]['content']


@patch('src.llm_client.requests.post')
def test_llm_client_classify_email_truncation(mock_post, mock_settings):
    """Test that email content is truncated if too long."""
    mock_settings.get_max_body_chars.return_value = 100
    
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 3, "importance_score": 7}'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    long_content = "x" * 200
    result = client.classify_email(long_content)
    
    # Verify truncation marker was added
    call_args = mock_post.call_args
    messages = call_args[1]['json']['messages']
    assert "[Content truncated]" in messages[1]['content']


@patch('src.llm_client.requests.post')
def test_llm_client_parse_json_response(mock_post, mock_settings):
    """Test parsing of valid JSON response."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 5, "importance_score": 6}'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    result = client.classify_email("Test")
    
    assert result.spam_score == 5
    assert result.importance_score == 6


@patch('src.llm_client.requests.post')
def test_llm_client_parse_markdown_wrapped_json(mock_post, mock_settings):
    """Test parsing JSON wrapped in markdown code blocks."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '```json\n{"spam_score": 4, "importance_score": 7}\n```'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    result = client.classify_email("Test")
    
    assert result.spam_score == 4
    assert result.importance_score == 7


@patch('src.llm_client.requests.post')
@patch('src.llm_client.time.sleep')
def test_llm_client_parse_invalid_json(mock_sleep, mock_post, mock_settings):
    """Test handling of invalid JSON response (triggers retries, then raises LLMAPIError)."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": "This is not valid JSON"
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    # Parse errors trigger retries, then raise LLMAPIError after all retries exhausted
    with pytest.raises(LLMAPIError, match="Failed after 3 attempts"):
        client.classify_email("Test")
    
    # Should have retried 3 times
    assert mock_post.call_count == 3


@patch('src.llm_client.requests.post')
@patch('src.llm_client.time.sleep')
def test_llm_client_parse_missing_fields(mock_sleep, mock_post, mock_settings):
    """Test handling of response with missing required fields (triggers retries)."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 3}'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    # Missing fields trigger retries, then raise LLMAPIError after all retries exhausted
    with pytest.raises(LLMAPIError, match="Failed after 3 attempts"):
        client.classify_email("Test")
    
    # Should have retried 3 times
    assert mock_post.call_count == 3


@patch('src.llm_client.requests.post')
def test_llm_client_parse_out_of_range_scores(mock_post, mock_settings):
    """Test that out-of-range scores are clamped."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 15, "importance_score": -5}'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    result = client.classify_email("Test")
    
    # Scores should be clamped to 0-10
    assert result.spam_score == 10
    assert result.importance_score == 0


@patch('src.llm_client.requests.post')
def test_llm_client_http_error(mock_post, mock_settings):
    """Test handling of HTTP errors."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"
    http_error = HTTPError(response=mock_response)
    mock_response.raise_for_status.side_effect = http_error
    mock_post.return_value = mock_response
    
    client = LLMClient()
    with pytest.raises(LLMAPIError, match="HTTP 429"):
        client.classify_email("Test")


@patch('src.llm_client.requests.post')
@patch('src.llm_client.time.sleep')
def test_llm_client_retry_logic(mock_sleep, mock_post, mock_settings):
    """Test that retry logic works correctly."""
    # First two attempts fail, third succeeds
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_response_fail.text = "Server error"
    http_error = HTTPError(response=mock_response_fail)
    mock_response_fail.raise_for_status.side_effect = http_error
    
    mock_response_success = MagicMock()
    api_response_dict_success = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 2, "importance_score": 8}'
            }
        }]
    }
    mock_response_success.json = lambda: api_response_dict_success
    mock_response_success.raise_for_status = lambda: None
    
    mock_post.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]
    
    client = LLMClient()
    result = client.classify_email("Test")
    
    # Should have retried 3 times (2 failures + 1 success)
    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2  # Sleep between retries
    assert result.spam_score == 2
    assert result.importance_score == 8


@patch('src.llm_client.requests.post')
@patch('src.llm_client.time.sleep')
def test_llm_client_retry_exhaustion(mock_sleep, mock_post, mock_settings):
    """Test that all retries are exhausted before raising error."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server error"
    http_error = HTTPError(response=mock_response)
    mock_response.raise_for_status.side_effect = http_error
    mock_post.return_value = mock_response
    
    client = LLMClient()
    with pytest.raises(LLMAPIError, match="Failed after 3 attempts"):
        client.classify_email("Test")
    
    # Should have tried 3 times (as configured)
    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2  # Sleep between attempts


@patch('src.llm_client.requests.post')
def test_llm_client_network_error(mock_post, mock_settings):
    """Test handling of network errors."""
    mock_post.side_effect = RequestException("Network connection failed")
    
    client = LLMClient()
    with pytest.raises(LLMAPIError, match="Network error"):
        client.classify_email("Test")


@patch('src.llm_client.requests.post')
def test_llm_client_timeout_error(mock_post, mock_settings):
    """Test handling of timeout errors."""
    mock_post.side_effect = Timeout("Request timed out")
    
    client = LLMClient()
    with pytest.raises(LLMAPIError, match="Network error"):
        client.classify_email("Test")


@patch('src.llm_client.requests.post')
def test_llm_client_invalid_json_response(mock_post, mock_settings):
    """Test handling of invalid JSON in API response."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    def raise_json_error():
        raise json.JSONDecodeError("Invalid JSON", "", 0)
    mock_response.json = raise_json_error
    mock_post.return_value = mock_response
    
    client = LLMClient()
    with pytest.raises(LLMAPIError, match="Invalid JSON in API response"):
        client.classify_email("Test")


@patch('src.llm_client.requests.post')
@patch('src.llm_client.time.sleep')
def test_llm_client_empty_response(mock_sleep, mock_post, mock_settings):
    """Test handling of empty response content (triggers retries)."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": ""
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    # Empty response triggers retries, then raises LLMAPIError after all retries exhausted
    with pytest.raises(LLMAPIError, match="Failed after 3 attempts"):
        client.classify_email("Test")
    
    # Should have retried 3 times
    assert mock_post.call_count == 3


@patch('src.llm_client.requests.post')
def test_llm_client_response_format_instructions(mock_post, mock_settings):
    """Test that prompt includes JSON format instructions."""
    api_response_dict = {
        "choices": [{
            "message": {
                "content": '{"spam_score": 3, "importance_score": 7}'
            }
        }]
    }
    mock_response = MagicMock()
    mock_response.json = lambda: api_response_dict
    mock_response.raise_for_status = lambda: None
    mock_post.return_value = mock_response
    
    client = LLMClient()
    client.classify_email("Test email")
    
    # Verify prompt includes JSON format instructions
    call_args = mock_post.call_args
    messages = call_args[1]['json']['messages']
    user_message = messages[1]['content']
    assert "spam_score" in user_message
    assert "importance_score" in user_message
    assert "JSON" in user_message or "json" in user_message
