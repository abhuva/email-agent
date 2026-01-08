"""
V3 LLM client module for email classification.

This module provides a clean interface for LLM API interactions using the settings.py facade.
Implements retry logic, structured JSON response parsing, and error handling as specified in the PDD.

All configuration access is through the settings.py facade, not direct YAML access.
"""
import json
import logging
import random
import time
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass

from src.settings import settings
from src.config import ConfigError

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class LLMAPIError(LLMClientError):
    """Raised when LLM API calls fail."""
    pass


class LLMResponseParseError(LLMClientError):
    """Raised when LLM response cannot be parsed or validated."""
    pass


@dataclass
class LLMResponse:
    """Structured response from LLM API."""
    spam_score: int
    importance_score: int
    raw_response: Optional[str] = None
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format."""
        return {
            "spam_score": self.spam_score,
            "importance_score": self.importance_score
        }


class LLMClient:
    """
    V3 LLM client for email classification.
    
    This class provides a clean interface for LLM API interactions, using the
    settings.py facade for all configuration access.
    
    Example:
        client = LLMClient()
        response = client.classify_email(email_content)
        print(f"Spam: {response.spam_score}, Importance: {response.importance_score}")
    """
    
    def __init__(self):
        """Initialize LLM client (loads configuration from settings facade)."""
        self._api_key: Optional[str] = None
        self._api_url: Optional[str] = None
        self._model: Optional[str] = None
        self._temperature: Optional[float] = None
        self._retry_attempts: Optional[int] = None
        self._retry_delay_seconds: Optional[int] = None
    
    def _load_config(self) -> None:
        """Load configuration from settings facade (lazy loading)."""
        if self._api_key is None:
            self._api_key = settings.get_openrouter_api_key()
            self._api_url = settings.get_openrouter_api_url()
            self._model = settings.get_openrouter_model()
            self._temperature = settings.get_openrouter_temperature()
            self._retry_attempts = settings.get_openrouter_retry_attempts()
            self._retry_delay_seconds = settings.get_openrouter_retry_delay_seconds()
    
    def _format_prompt_for_json(self, email_content: str, user_prompt: Optional[str] = None) -> str:
        """
        Format prompt to request structured JSON response.
        
        Args:
            email_content: The email content to analyze
            user_prompt: Optional user-provided prompt (from prompt file)
            
        Returns:
            Formatted prompt string requesting JSON response
        """
        # Use user prompt if provided, otherwise use default
        if user_prompt:
            base_prompt = user_prompt
        else:
            base_prompt = (
                "Analyze the following email and provide a classification score. "
                "Consider factors such as sender reputation, content relevance, urgency indicators, "
                "and spam characteristics."
            )
        
        # Append JSON format instructions
        json_instructions = (
            "\n\n"
            "IMPORTANT: You must respond with ONLY a valid JSON object containing exactly these two fields:\n"
            "- spam_score: An integer from 0-10 where 0 is definitely not spam and 10 is definitely spam\n"
            "- importance_score: An integer from 0-10 where 0 is not important and 10 is very important\n\n"
            "Example response format:\n"
            '{"spam_score": 2, "importance_score": 8}\n\n'
            "Do not include any explanation, markdown formatting, or additional text. Only the JSON object."
        )
        
        full_prompt = f"{base_prompt}\n\n---\n{email_content}\n---{json_instructions}"
        return full_prompt
    
    def _make_api_request(self, prompt: str) -> Dict[str, Any]:
        """
        Make a single API request to the LLM.
        
        Args:
            prompt: The formatted prompt to send
            
        Returns:
            Raw API response dictionary
            
        Raises:
            LLMAPIError: If API call fails
        """
        self._load_config()
        
        url = f"{self._api_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an email classification assistant. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self._temperature,
            "response_format": {"type": "json_object"}  # Request JSON mode if supported
        }
        
        logger.debug(f"Making API request to {url}")
        logger.debug(f"Model: {self._model}, Temperature: {self._temperature}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            error_msg = f"HTTP {status_code} error: {e.response.text if e.response else str(e)}"
            logger.error(f"API request failed: {error_msg}")
            raise LLMAPIError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during API request: {e}"
            logger.error(error_msg)
            raise LLMAPIError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in API response: {e}"
            logger.error(error_msg)
            raise LLMAPIError(error_msg) from e
    
    def _parse_response(self, api_response: Dict[str, Any]) -> LLMResponse:
        """
        Parse and validate LLM API response.
        
        Args:
            api_response: Raw API response dictionary
            
        Returns:
            LLMResponse object with parsed scores
            
        Raises:
            LLMResponseParseError: If response cannot be parsed or validated
        """
        try:
            # Extract content from OpenAI-compatible response format
            content = api_response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                raise LLMResponseParseError("Empty response content from LLM")
            
            logger.debug(f"Raw LLM response content: {content[:200]}...")
            
            # Try to parse JSON from response
            # Sometimes LLM wraps JSON in markdown code blocks
            content_clean = content.strip()
            if content_clean.startswith("```"):
                # Remove markdown code block markers
                lines = content_clean.split("\n")
                content_clean = "\n".join(lines[1:-1]) if len(lines) > 2 else content_clean
            
            # Parse JSON
            try:
                parsed_json = json.loads(content_clean)
            except json.JSONDecodeError as e:
                # Try to extract JSON from text if wrapped
                import re
                json_match = re.search(r'\{[^{}]*"spam_score"[^{}]*"importance_score"[^{}]*\}', content_clean)
                if json_match:
                    parsed_json = json.loads(json_match.group())
                else:
                    raise LLMResponseParseError(f"Could not parse JSON from response: {e}")
            
            # Validate required fields
            if not isinstance(parsed_json, dict):
                raise LLMResponseParseError(f"Response is not a JSON object: {type(parsed_json)}")
            
            spam_score = parsed_json.get("spam_score")
            importance_score = parsed_json.get("importance_score")
            
            if spam_score is None or importance_score is None:
                raise LLMResponseParseError(
                    f"Missing required fields. Got: {list(parsed_json.keys())}"
                )
            
            # Validate score types and ranges
            try:
                spam_score = int(spam_score)
                importance_score = int(importance_score)
            except (ValueError, TypeError) as e:
                raise LLMResponseParseError(
                    f"Scores must be integers. Got spam_score={spam_score}, importance_score={importance_score}"
                )
            
            if not (0 <= spam_score <= 10):
                logger.warning(f"spam_score out of range (0-10): {spam_score}, clamping to valid range")
                spam_score = max(0, min(10, spam_score))
            
            if not (0 <= importance_score <= 10):
                logger.warning(f"importance_score out of range (0-10): {importance_score}, clamping to valid range")
                importance_score = max(0, min(10, importance_score))
            
            return LLMResponse(
                spam_score=spam_score,
                importance_score=importance_score,
                raw_response=content
            )
            
        except LLMResponseParseError:
            raise
        except Exception as e:
            raise LLMResponseParseError(f"Unexpected error parsing response: {e}") from e
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        base_delay = self._retry_delay_seconds
        exponential_delay = base_delay * (2 ** (attempt - 1))
        # Add jitter (random 0-25% of delay)
        jitter = exponential_delay * 0.25 * random.random()
        return exponential_delay + jitter
    
    def classify_email(
        self,
        email_content: str,
        user_prompt: Optional[str] = None,
        max_chars: Optional[int] = None
    ) -> LLMResponse:
        """
        Classify an email using LLM API with retry logic.
        
        This method implements the full API contract from the PDD:
        - POST to URL from settings.get_openrouter_api_url()
        - Bearer token auth via settings.get_openrouter_api_key()
        - JSON response with {"spam_score": <int>, "importance_score": <int>}
        - Retry logic with exponential backoff
        
        Args:
            email_content: The email content to classify
            user_prompt: Optional user-provided prompt (from prompt file)
            max_chars: Maximum characters to send (truncates if needed)
            
        Returns:
            LLMResponse object with spam_score and importance_score
            
        Raises:
            LLMAPIError: If all retry attempts fail
            LLMResponseParseError: If response cannot be parsed
        """
        self._load_config()
        
        # Truncate email content if needed
        if max_chars:
            max_body_chars = settings.get_max_body_chars()
            effective_max = min(max_chars, max_body_chars) if max_chars else max_body_chars
        else:
            effective_max = settings.get_max_body_chars()
        
        if len(email_content) > effective_max:
            logger.info(f"Truncating email content from {len(email_content)} to {effective_max} characters")
            email_content = email_content[:effective_max] + "\n[Content truncated]"
        
        # Format prompt
        prompt = self._format_prompt_for_json(email_content, user_prompt)
        
        # Retry logic
        last_error = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                logger.info(f"LLM API call attempt {attempt}/{self._retry_attempts}")
                
                # Make API request
                api_response = self._make_api_request(prompt)
                
                # Parse response
                result = self._parse_response(api_response)
                
                logger.info(
                    f"LLM classification successful: spam_score={result.spam_score}, "
                    f"importance_score={result.importance_score}"
                )
                return result
                
            except (LLMAPIError, LLMResponseParseError) as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed: {e}")
                
                if attempt < self._retry_attempts:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self._retry_attempts} attempts failed")
        
        # All retries exhausted - raise error
        raise LLMAPIError(
            f"Failed after {self._retry_attempts} attempts. Last error: {last_error}"
        ) from last_error
