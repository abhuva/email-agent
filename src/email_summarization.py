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
    Parse LLM response into structured summary object.
    
    Args:
        raw_response: Raw API response dict from LLM
    
    Returns:
        Dict with keys:
            - summary: str - Main summary text
            - action_items: List[str] - List of action items
            - priority: str - Priority level (low/medium/high)
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
        'action_items': [],
        'priority': 'medium',
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
        
        # Strip markdown formatting if present
        content_clean = content.strip()
        
        # Remove markdown code blocks if present
        if content_clean.startswith("```"):
            # Extract content between code blocks
            match = re.search(r'```(?:markdown)?\s*(.*?)\s*```', content_clean, re.DOTALL)
            if match:
                content_clean = match.group(1).strip()
        
        # Validate minimum length
        if len(content_clean) < 20:
            logger.warning(f"Summary too short ({len(content_clean)} chars), minimum 20 required")
            return result
        
        # Validate maximum length
        if len(content_clean) > 500:
            logger.warning(f"Summary too long ({len(content_clean)} chars), truncating to 500")
            content_clean = content_clean[:500].rstrip()
        
        # Try to extract structured information
        # Look for action items (bullet points, numbered lists)
        action_items = []
        priority = 'medium'
        
        # Extract bullet points or numbered items that look like action items
        action_patterns = [
            r'(?:^|\n)[-*•]\s*(.+?)(?=\n|$)',
            r'(?:^|\n)\d+\.\s*(.+?)(?=\n|$)',
            r'(?:^|\n)Action[:\s]+(.+?)(?=\n|$)',
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, content_clean, re.MULTILINE | re.IGNORECASE)
            if matches:
                action_items.extend([m.strip() for m in matches if len(m.strip()) > 5])
        
        # Extract priority (look for "priority: high/medium/low" or similar)
        priority_patterns = [
            r'priority[:\s]+(low|medium|high)',
            r'priority[:\s]+(urgent|normal|low)',
        ]
        
        for pattern in priority_patterns:
            match = re.search(pattern, content_clean, re.IGNORECASE)
            if match:
                priority_raw = match.group(1).lower()
                if 'urgent' in priority_raw or 'high' in priority_raw:
                    priority = 'high'
                elif 'low' in priority_raw:
                    priority = 'low'
                else:
                    priority = 'medium'
                break
        
        # The main summary is the cleaned content (or first paragraph if structured)
        summary = content_clean
        
        # If we found action items, try to separate them from summary
        if action_items:
            # Remove action items section from summary if present
            for item in action_items:
                summary = summary.replace(f"- {item}", "").replace(f"* {item}", "").replace(f"• {item}", "")
            summary = re.sub(r'\n{3,}', '\n\n', summary).strip()
        
        result['summary'] = summary
        result['action_items'] = action_items[:5]  # Limit to 5 action items
        result['priority'] = priority
        result['success'] = True
        
        logger.debug(f"Parsed summary: {len(summary)} chars, {len(action_items)} action items, priority: {priority}")
        
    except Exception as e:
        logger.error(f"Error parsing summary response: {e}", exc_info=True)
        # Return partial result if we got some content
        if result.get('raw_content'):
            result['summary'] = result['raw_content'][:500]
            result['success'] = True  # Partial success
    
    return result


def generate_email_summary(
    email: Dict[str, Any],
    client: OpenRouterClient,
    config,
    summarization_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main function to generate email summary using LLM.
    
    This function orchestrates prompt formatting, API calls, error handling,
    and response parsing to generate a structured summary.
    
    Args:
        email: Email dict with 'subject', 'sender', 'body', 'date', etc.
        client: OpenRouterClient instance
        config: ConfigManager instance
        summarization_result: Optional result from check_summarization_required()
                             If None, will check if summarization is needed
    
    Returns:
        Dict with keys:
            - success: bool - Whether summary was generated successfully
            - summary: str - Main summary text
            - action_items: List[str] - List of action items
            - priority: str - Priority level
            - error: Optional[str] - Error message if failed
    
    Examples:
        >>> email = {'subject': 'Test', 'sender': 'test@example.com', 'body': 'Content'}
        >>> result = generate_email_summary(email, client, config)
        >>> 'success' in result
        True
    """
    # Check if summarization is required
    if summarization_result is None:
        from src.summarization import check_summarization_required
        summarization_result = check_summarization_required(email, config)
    
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
        
        # Get model from config
        model = config.openrouter_model
        
        # Call LLM API
        logger.info(f"Calling LLM API for email {email_uid} summarization")
        start_time = time.time()
        
        raw_response = call_llm_for_summarization(
            client,
            formatted_prompt,
            model,
            max_tokens=300,
            temperature=0.3
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
