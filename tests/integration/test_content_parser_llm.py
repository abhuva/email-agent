"""
Integration tests for Content Parser ↔ LLM processing interaction.

This module tests the integration between the Content Parser and LLM processing,
verifying that:
- Parsed content is correctly transformed into LLM prompts
- LLM outputs are handled correctly
- Error handling works for partial/invalid responses
- HTML to Markdown conversion works correctly
"""

import pytest
from unittest.mock import Mock

from src.content_parser import parse_html_content
from src.llm_client import LLMResponse
from tests.integration.mock_services import MockLLMClient


class TestContentParserLLMIntegration:
    """Integration tests for Content Parser and LLM processing."""
    
    def test_html_content_parsed_before_llm(
        self,
        mock_llm_client
    ):
        """
        Test that HTML content is parsed to Markdown before LLM processing.
        
        Scenario:
        - Email has HTML content
        - Content parser converts HTML to Markdown
        - LLM receives parsed Markdown content
        """
        # HTML email content
        html_body = "<p>This is <strong>important</strong> content</p>"
        plain_text = "This is important content"
        
        # Parse content
        parsed_content, is_fallback = parse_html_content(html_body, plain_text)
        
        # Verify parsing worked
        assert not is_fallback
        assert "important" in parsed_content.lower()
        
        # Simulate LLM processing with parsed content
        response = mock_llm_client.classify_email(parsed_content)
        
        # Verify LLM received parsed content
        assert isinstance(response, LLMResponse)
        assert response.spam_score is not None
        assert response.importance_score is not None
        
    def test_plain_text_fallback_used(
        self,
        mock_llm_client
    ):
        """
        Test that plain text fallback is used when HTML parsing fails.
        
        Scenario:
        - Email has empty/invalid HTML
        - Content parser falls back to plain text
        - LLM receives plain text content
        """
        # Empty HTML, valid plain text
        html_body = ""
        plain_text = "This is plain text content"
        
        # Parse content
        parsed_content, is_fallback = parse_html_content(html_body, plain_text)
        
        # Verify fallback was used
        assert is_fallback
        assert parsed_content == plain_text
        
        # Simulate LLM processing
        response = mock_llm_client.classify_email(parsed_content)
        
        # Verify LLM received plain text
        assert isinstance(response, LLMResponse)
        
    def test_llm_response_handled_correctly(
        self,
        mock_llm_client
    ):
        """
        Test that LLM responses are correctly parsed and handled.
        
        Scenario:
        - LLM returns valid JSON response
        - Response is parsed into LLMResponse object
        - Scores are accessible
        """
        # Configure mock LLM
        mock_llm_client.set_default_response(spam_score=2, importance_score=9)
        
        # Process email content
        email_content = "This is an important email"
        response = mock_llm_client.classify_email(email_content)
        
        # Verify response structure
        assert isinstance(response, LLMResponse)
        assert response.spam_score == 2
        assert response.importance_score == 9
        assert response.raw_response is not None
        
    def test_llm_invalid_json_handled(
        self,
        mock_llm_client
    ):
        """
        Test that invalid JSON from LLM is handled gracefully.
        
        Scenario:
        - LLM returns invalid JSON
        - System handles error gracefully
        """
        # Configure mock LLM to return invalid JSON
        mock_llm_client.set_invalid_json(True)
        
        # Process email content
        email_content = "Test email"
        response = mock_llm_client.classify_email(email_content)
        
        # Verify response still has structure (even if invalid)
        assert isinstance(response, LLMResponse)
        # Invalid JSON may result in default scores
        assert response.spam_score is not None
        assert response.importance_score is not None
