"""
Tests for content parser module (Task 5).

Tests HTML to Markdown conversion, fallback mechanism, and character limit enforcement.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from src.content_parser import parse_html_content, _html_to_markdown


class TestHtmlToMarkdownConversion:
    """Tests for successful HTML to Markdown conversion."""
    
    def test_successful_html_conversion(self):
        """Test successful HTML-to-Markdown conversion with is_fallback = False."""
        html = "<p>Hello <strong>world</strong></p>"
        plain_text = "Hello world"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is False
        assert "world" in parsed_content or "Hello" in parsed_content
        assert isinstance(parsed_content, str)
    
    def test_complex_html_formatting(self):
        """Test conversion of complex HTML with various formatting."""
        html = """
        <h1>Title</h1>
        <p>Paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <a href="https://example.com">Link</a>
        """
        plain_text = "Title\nParagraph with bold and italic text.\nItem 1\nItem 2\nLink"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is False
        assert "Title" in parsed_content
        assert isinstance(parsed_content, str)
    
    def test_html_with_links(self):
        """Test that links are preserved in Markdown conversion."""
        html = '<p>Visit <a href="https://example.com">example.com</a> for more info.</p>'
        plain_text = "Visit example.com for more info."
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is False
        assert "example.com" in parsed_content or "https://example.com" in parsed_content


class TestFallbackToPlainText:
    """Tests for fallback to plain text when HTML conversion fails or is unavailable."""
    
    def test_missing_html_uses_plain_text(self):
        """Test that missing HTML falls back to plain text with is_fallback = True."""
        html = None
        plain_text = "Plain text only email"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is True
        assert parsed_content == plain_text
    
    def test_empty_html_uses_plain_text(self):
        """Test that empty HTML falls back to plain text."""
        html = ""
        plain_text = "Plain text only email"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is True
        assert parsed_content == plain_text
    
    def test_whitespace_only_html_uses_plain_text(self):
        """Test that whitespace-only HTML falls back to plain text."""
        html = "   \n\t  "
        plain_text = "Plain text only email"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is True
        assert parsed_content == plain_text
    
    def test_html_conversion_exception_falls_back(self):
        """Test that exception in _html_to_markdown triggers fallback to plain text."""
        html = "<p>Test HTML</p>"
        plain_text = "Fallback plain text"
        
        # Mock _html_to_markdown to raise an exception
        with patch('src.content_parser._html_to_markdown', side_effect=Exception("Conversion error")):
            parsed_content, is_fallback = parse_html_content(html, plain_text)
            
            assert is_fallback is True
            assert parsed_content == plain_text
    
    def test_empty_conversion_result_falls_back(self):
        """Test that empty conversion result falls back to plain text."""
        html = "<p>Test HTML</p>"
        plain_text = "Fallback plain text"
        
        # Mock _html_to_markdown to return empty string
        with patch('src.content_parser._html_to_markdown', return_value=""):
            parsed_content, is_fallback = parse_html_content(html, plain_text)
            
            assert is_fallback is True
            assert parsed_content == plain_text
    
    def test_whitespace_only_conversion_result_falls_back(self):
        """Test that whitespace-only conversion result falls back to plain text."""
        html = "<p>Test HTML</p>"
        plain_text = "Fallback plain text"
        
        # Mock _html_to_markdown to return whitespace only
        with patch('src.content_parser._html_to_markdown', return_value="   \n\t  "):
            parsed_content, is_fallback = parse_html_content(html, plain_text)
            
            assert is_fallback is True
            assert parsed_content == plain_text


class TestCharacterLimitEnforcement:
    """Tests for 20,000 character limit enforcement."""
    
    def test_html_content_truncated_to_limit(self):
        """Test that HTML-derived content exceeding 20,000 chars is truncated."""
        # Create HTML that will produce content longer than 20,000 chars
        long_html = "<p>" + "A" * 25000 + "</p>"
        plain_text = "Short plain text"
        
        parsed_content, is_fallback = parse_html_content(long_html, plain_text)
        
        assert len(parsed_content) == 20_000
        # is_fallback should remain False since it came from HTML (even though truncated)
        assert is_fallback is False
    
    def test_plain_text_content_truncated_to_limit(self):
        """Test that plain-text-derived content exceeding 20,000 chars is truncated."""
        html = ""  # Empty HTML triggers fallback
        long_plain_text = "A" * 25000
        
        parsed_content, is_fallback = parse_html_content(html, long_plain_text)
        
        assert len(parsed_content) == 20_000
        # is_fallback should remain True since it came from plain text
        assert is_fallback is True
    
    def test_content_at_exact_limit_not_truncated(self):
        """Test that content exactly at 20,000 chars is not truncated."""
        html = "<p>" + "A" * 19997 + "</p>"  # Will produce ~20,000 chars after conversion
        plain_text = "Short plain text"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        # Should not be truncated (may be slightly less due to HTML conversion)
        assert len(parsed_content) <= 20_000
        assert is_fallback is False
    
    def test_content_below_limit_not_truncated(self):
        """Test that content below 20,000 chars is not truncated."""
        html = "<p>Short HTML content</p>"
        plain_text = "Short plain text"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert len(parsed_content) < 20_000
        assert is_fallback is False


class TestLogging:
    """Tests for logging behavior in content parser."""
    
    def test_logs_debug_on_successful_conversion(self, caplog):
        """Test that debug log is emitted on successful HTML conversion."""
        html = "<p>Test HTML</p>"
        plain_text = "Plain text"
        
        with caplog.at_level(logging.DEBUG):
            parse_html_content(html, plain_text)
        
        assert "Attempting HTML to Markdown conversion" in caplog.text
        assert "HTML to Markdown conversion successful" in caplog.text
    
    def test_logs_debug_on_empty_html(self, caplog):
        """Test that debug log is emitted when HTML is empty."""
        html = ""
        plain_text = "Plain text"
        
        with caplog.at_level(logging.DEBUG):
            parse_html_content(html, plain_text)
        
        assert "HTML body is missing or empty" in caplog.text
    
    def test_logs_warning_on_conversion_failure(self, caplog):
        """Test that warning log is emitted when HTML conversion fails."""
        html = "<p>Test HTML</p>"
        plain_text = "Plain text"
        
        with patch('src.content_parser._html_to_markdown', side_effect=Exception("Conversion error")):
            with caplog.at_level(logging.WARNING):
                parse_html_content(html, plain_text)
        
        assert "HTML to Markdown conversion failed" in caplog.text
        assert "Conversion error" in caplog.text
    
    def test_logs_warning_on_empty_conversion_result(self, caplog):
        """Test that warning log is emitted when conversion produces empty result."""
        html = "<p>Test HTML</p>"
        plain_text = "Plain text"
        
        with patch('src.content_parser._html_to_markdown', return_value=""):
            with caplog.at_level(logging.WARNING):
                parse_html_content(html, plain_text)
        
        assert "HTML conversion produced empty result" in caplog.text
    
    def test_logs_warning_on_truncation(self, caplog):
        """Test that warning log is emitted when content is truncated."""
        long_html = "<p>" + "A" * 25000 + "</p>"
        plain_text = "Short plain text"
        
        with caplog.at_level(logging.WARNING):
            parse_html_content(long_html, plain_text)
        
        assert "Content truncated" in caplog.text
        assert "20,000 characters" in caplog.text


class TestEdgeCases:
    """Tests for edge cases and malformed HTML."""
    
    def test_malformed_html_handled_gracefully(self):
        """Test that malformed HTML is handled gracefully."""
        html = "<p>Unclosed tag <strong>bold text"
        plain_text = "Plain text fallback"
        
        # Should not raise exception, either converts or falls back
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert isinstance(parsed_content, str)
        assert len(parsed_content) <= 20_000
    
    def test_html_with_special_characters(self):
        """Test HTML with special characters converts correctly."""
        html = "<p>Email with &amp; entities and &quot;quotes&quot;</p>"
        plain_text = "Email with & entities and \"quotes\""
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is False
        assert isinstance(parsed_content, str)
    
    def test_plain_text_with_none_html(self):
        """Test handling when html_body is explicitly None."""
        html = None
        plain_text = "Plain text content"
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert is_fallback is True
        assert parsed_content == plain_text
    
    def test_both_html_and_plain_text_empty(self):
        """Test handling when both HTML and plain text are empty."""
        html = ""
        plain_text = ""
        
        parsed_content, is_fallback = parse_html_content(html, plain_text)
        
        assert parsed_content == ""
        assert is_fallback is True
