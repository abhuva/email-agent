"""
Email summarization module using LLM API.

This module provides functions to:
- Format prompts for email summarization
- Call LLM API for generating summaries
- Parse and validate summary responses
- Handle errors gracefully
"""

import logging
import time
import re
from typing import Dict, Any, Optional, List
from src.openrouter_client import OpenRouterClient, OpenRouterAPIError

logger = logging.getLogger(__name__)


def format_summarization_prompt(
    base_prompt: str,
    email_subject: str,
    email_sender: str,
    email_body: str,
    email_date: Optional[str] = None
) -> str:
    """
    Format the summarization prompt by combining base prompt with email content.
    
    Args:
        base_prompt: The loaded summarization prompt template
        email_subject: Email subject line
        email_sender: Email sender address
        email_body: Email body content (already sanitized/converted to Markdown)
        email_date: Optional email date string
    
    Returns:
        Formatted prompt string ready for LLM
    
    Examples:
        >>> prompt = format_summarization_prompt(
        ...     "Summarize this email.",
        ...     "Meeting Tomorrow",
        ...     "sender@example.com",
        ...     "We need to meet at 3pm."
        ... )
        >>> 'Meeting Tomorrow' in prompt
        True
    """
    # Build email context section
    context_parts = [
        f"**Subject:** {email_subject}",
        f"**From:** {email_sender}"
    ]
    
    if email_date:
        context_parts.append(f"**Date:** {email_date}")
    
    context_section = "\n".join(context_parts)
    
    # Combine base prompt with email context and body
    formatted_prompt = f"""{base_prompt}

## Email Details
{context_section}

## Email Content
{email_body}

Please provide a concise summary focusing on:
- 2-3 sentence summary of main content
- Bullet-point list of action items (if any)
- Priority level (low/medium/high)
"""
    
    return formatted_prompt.strip()


def call_llm_for_summarization(
    client: OpenRouterClient,
    prompt: str,
    model: str,
    max_tokens: int = 300,
    temperature: float = 0.3,
    timeout: int = 30,
    max_retries: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Call LLM API for email summarization with retry logic.
    
    Args:
        client: OpenRouterClient instance
        prompt: Formatted prompt string
        model: Model name to use
        max_tokens: Maximum tokens for response (default: 300)
        temperature: Temperature for response (default: 0.3 for more focused output)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum retry attempts (default: 3)
    
    Returns:
        Raw API response dict, or None if all retries failed
    
    Examples:
        >>> client = OpenRouterClient(api_key, api_url)
        >>> response = call_llm_for_summarization(client, "Summarize...", "gpt-3.5-turbo")
        >>> response is not None
        True
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that provides concise, accurate email summaries."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    
    attempt = 0
    last_error = None
    
    while attempt < max_retries:
        attempt += 1
        try:
            logger.debug(f"Calling LLM API for summarization (attempt {attempt}/{max_retries})")
            
            # Use the existing chat_completion method
            result = client.chat_completion(payload)
            
            logger.info(f"LLM API call successful (attempt {attempt})")
            return result
            
        except OpenRouterAPIError as e:
            last_error = e
            error_msg = str(e)
            
            # Check if it's a rate limit (429) or server error (5xx) - retry these
            # Don't retry 4xx errors (except 429) as they're client errors
            is_retryable = False
            if "429" in error_msg or "Rate limit" in error_msg:
                is_retryable = True
                logger.warning(f"Rate limit hit, will retry (attempt {attempt}/{max_retries})")
            elif "HTTP 5" in error_msg or " 5" in error_msg[:10]:  # 5xx errors (HTTP 500, HTTP 502, etc.)
                is_retryable = True
                logger.warning(f"Server error, will retry (attempt {attempt}/{max_retries})")
            else:
                # 4xx errors (except 429) are not retryable - break immediately
                logger.error(f"Client error (not retryable): {e}")
                break  # Don't retry non-retryable errors
            
            if is_retryable and attempt < max_retries:
                # Exponential backoff: 1s, 2s, 4s
                sleep_time = 2 ** (attempt - 1)
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"LLM API call failed (attempt {attempt}): {e}")
                if attempt >= max_retries:
                    break
                    
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error in LLM API call (attempt {attempt}): {e}", exc_info=True)
            if attempt >= max_retries:
                break
    
    logger.error(f"All {max_retries} retry attempts failed. Last error: {last_error}")
    return None


def parse_summary_response(raw_response: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse LLM response and return raw summary text with minimal processing.
    
    For smaller models like Gemini Flash, we return the raw response directly
    without complex parsing, allowing the model's natural formatting to be preserved.
    
    Args:
        raw_response: Raw API response dict from LLM
    
    Returns:
        Dict with keys:
            - summary: str - Raw summary text (minimal processing)
            - success: bool - Whether parsing succeeded
            - raw_content: str - Raw content from API (for debugging)
    
    Examples:
        >>> response = {'choices': [{'message': {'content': 'Summary here'}}]}
        >>> result = parse_summary_response(response)
        >>> result['success']
        True
    """
    result = {
        'summary': '',
        'success': False,
        'raw_content': ''
    }
    
    if not raw_response:
        logger.warning("Empty response from LLM API")
        return result
    
    try:
        # Extract content from standard LLM response format
        content = raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not content:
            logger.warning("No content in LLM response")
            return result
        
        result['raw_content'] = content.strip()
        
        # Minimal processing: just strip whitespace and remove markdown code blocks if present
        content_clean = content.strip()
        
        # Remove markdown code blocks if present (some models wrap responses in code blocks)
        if content_clean.startswith("```"):
            match = re.search(r'```(?:markdown)?\s*(.*?)\s*```', content_clean, re.DOTALL)
            if match:
                content_clean = match.group(1).strip()
        
        # Basic validation: minimum length
        if len(content_clean) < 10:
            logger.warning(f"Summary too short ({len(content_clean)} chars), minimum 10 required")
            return result
        
        # Store the raw summary text directly (no parsing, no breaking down)
        result['summary'] = content_clean
        result['success'] = True
        
        logger.debug(f"Summary extracted: {len(content_clean)} chars (raw response, no parsing)")
        
    except Exception as e:
        logger.error(f"Error parsing summary response: {e}", exc_info=True)
        # Return partial result if we got some content
        if result.get('raw_content'):
            result['summary'] = result['raw_content']
            result['success'] = True  # Partial success
    
    return result


def generate_email_summary(
    email: Dict[str, Any],
    client: OpenRouterClient,
    summarization_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main function to generate email summary using LLM.
    
    This function orchestrates prompt formatting, API calls, error handling,
    and response parsing to generate a structured summary.
    
    Args:
        email: Email dict with 'subject', 'sender', 'body', 'date', etc.
        client: OpenRouterClient instance
        summarization_result: Optional result from check_summarization_required()
                             If None, will check if summarization is needed
    
    Returns:
        Dict with keys:
            - success: bool - Whether summary was generated successfully
            - summary: str - Raw summary text from LLM (inserted directly, no parsing)
            - error: Optional[str] - Error message if failed
            - action_items: List[str] - (Deprecated, always empty) Kept for backward compatibility
            - priority: str - (Deprecated, always 'medium') Kept for backward compatibility
    
    Examples:
        >>> email = {'subject': 'Test', 'sender': 'test@example.com', 'body': 'Content'}
        >>> result = generate_email_summary(email, client)
        >>> 'success' in result
        True
    """
    from src.settings import settings
    
    # Check if summarization is required
    if summarization_result is None:
        from src.summarization import check_summarization_required
        summarization_result = check_summarization_required(email)
    
    if not summarization_result.get('summarize', False):
        reason = summarization_result.get('reason', 'unknown')
        logger.debug(f"Summarization not required: {reason}")
        return {
            'success': False,
            'summary': '',
            'action_items': [],
            'priority': 'medium',
            'error': f'summarization_not_required: {reason}'
        }
    
    prompt_template = summarization_result.get('prompt')
    if not prompt_template:
        logger.warning("Summarization required but no prompt template available")
        return {
            'success': False,
            'summary': '',
            'action_items': [],
            'priority': 'medium',
            'error': 'prompt_template_missing'
        }
    
    email_uid = email.get('id', 'unknown')
    email_subject = email.get('subject', 'N/A')
    email_sender = email.get('sender', 'N/A')
    email_body = email.get('body', '')
    email_date = email.get('date')
    
    if not email_body:
        logger.warning(f"Email {email_uid} has no body content for summarization")
        return {
            'success': False,
            'summary': '',
            'action_items': [],
            'priority': 'medium',
            'error': 'email_body_empty'
        }
    
    try:
        # Format prompt
        logger.debug(f"Formatting summarization prompt for email {email_uid}")
        formatted_prompt = format_summarization_prompt(
            prompt_template,
            email_subject,
            email_sender,
            email_body,
            email_date
        )
        
        # Get model and settings from summarization config
        model = settings.get_summarization_model()
        temperature = settings.get_summarization_temperature()
        max_tokens = 300  # Can be made configurable later if needed
        
        # Call LLM API
        logger.info(f"Calling LLM API for email {email_uid} summarization (model: {model}, temperature: {temperature})")
        start_time = time.time()
        
        raw_response = call_llm_for_summarization(
            client,
            formatted_prompt,
            model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        api_latency = time.time() - start_time
        logger.info(f"LLM API call completed in {api_latency:.2f}s for email {email_uid}")
        
        if not raw_response:
            logger.warning(f"LLM API call failed for email {email_uid}, using fallback")
            return {
                'success': False,
                'summary': 'Summary unavailable - please read original email',
                'action_items': [],
                'priority': 'medium',
                'error': 'api_call_failed'
            }
        
        # Parse response
        logger.debug(f"Parsing summary response for email {email_uid}")
        parsed_result = parse_summary_response(raw_response)
        
        if parsed_result['success']:
            logger.info(f"Successfully generated summary for email {email_uid} ({len(parsed_result['summary'])} chars)")
        else:
            logger.warning(f"Summary parsing failed for email {email_uid}, using fallback")
            parsed_result['summary'] = 'Summary unavailable - please read original email'
        
        # Add metadata
        parsed_result['api_latency'] = api_latency
        parsed_result['error'] = None
        
        return parsed_result
        
    except Exception as e:
        logger.error(f"Unexpected error generating summary for email {email_uid}: {e}", exc_info=True)
        return {
            'success': False,
            'summary': 'Summary unavailable - please read original email',
            'action_items': [],
            'priority': 'medium',
            'error': f'unexpected_error: {str(e)}'
        }
