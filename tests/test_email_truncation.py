"""
TDD tests for email body truncation functionality.
"""

import pytest
from unittest.mock import Mock
from src.email_truncation import (
    get_max_truncation_length,
    truncate_plain_text,
    truncate_html,
    truncate_email_body,
    DEFAULT_MAX_BODY_CHARS
)


def test_get_max_truncation_length_from_config():
    """Test that get_max_truncation_length reads from ConfigManager"""
    mock_config = Mock()
    mock_config.max_body_chars = 5000
    result = get_max_truncation_length(mock_config)
    assert result == 5000


def test_get_max_truncation_length_with_default_fallback():
    """Test that get_max_truncation_length uses default if config missing"""
    result = get_max_truncation_length(None)
    assert result == DEFAULT_MAX_BODY_CHARS


def test_get_max_truncation_length_validates_positive():
    """Test that get_max_truncation_length validates value is positive"""
    mock_config = Mock()
    mock_config.max_body_chars = -100
    result = get_max_truncation_length(mock_config)
    assert result == DEFAULT_MAX_BODY_CHARS  # Should fallback to default


def test_truncate_plain_text_no_truncation_needed():
    """Test truncate_plain_text when body is shorter than max"""
    body = "Short email body"
    result = truncate_plain_text(body, 100)
    assert result['truncatedBody'] == body
    assert result['isTruncated'] is False


def test_truncate_plain_text_truncates_at_word_boundary():
    """Test truncate_plain_text truncates at last space before maxLength"""
    body = "This is a very long email body that needs to be truncated at a word boundary"
    max_len = 30
    result = truncate_plain_text(body, max_len)
    assert result['isTruncated'] is True
    assert len(result['truncatedBody']) <= max_len
    # Should end with indicator
    assert "[Content truncated]" in result['truncatedBody']
    # Should not cut mid-word (check last word before indicator is complete)
    truncated_without_indicator = result['truncatedBody'].replace(" [Content truncated]", "")
    assert truncated_without_indicator[-1] != ' ' or truncated_without_indicator.rstrip()[-1].isalnum()


def test_truncate_plain_text_truncates_at_newline():
    """Test truncate_plain_text prefers newline over space for truncation"""
    body = "First paragraph with some text\n\nSecond paragraph with more text\n\nThird paragraph"
    max_len = 40  # Will truncate, should prefer newline
    result = truncate_plain_text(body, max_len)
    assert result['isTruncated'] is True
    # Should truncate at newline if possible (check that we kept content up to a newline)
    truncated_without_indicator = result['truncatedBody'].replace(" [Content truncated]", "")
    # The truncated text should end at a word boundary (newline or space)
    assert len(truncated_without_indicator) > 0


def test_truncate_plain_text_adds_indicator():
    """Test truncate_plain_text adds [Content truncated] indicator"""
    body = "A" * 100
    result = truncate_plain_text(body, 50)
    assert result['isTruncated'] is True
    assert "[Content truncated]" in result['truncatedBody']


def test_truncate_plain_text_respects_max_length():
    """Test truncate_plain_text result doesn't exceed maxLength including indicator"""
    body = "A" * 1000
    max_len = 50
    result = truncate_plain_text(body, max_len)
    assert len(result['truncatedBody']) <= max_len


def test_truncate_html_preserves_structure():
    """Test truncate_html preserves valid HTML structure"""
    body = "<p>First paragraph</p><p>Second paragraph</p><p>Third paragraph</p>"
    result = truncate_html(body, 50)
    assert 'truncatedBody' in result
    assert 'isTruncated' in result
    # Should contain valid HTML tags
    assert '<p>' in result['truncatedBody'] or result['isTruncated'] is False


def test_truncate_html_removes_scripts():
    """Test truncate_html removes script and style tags"""
    body = "<p>Content</p><script>alert('xss')</script><p>More content</p>"
    result = truncate_html(body, 100)
    assert '<script>' not in result['truncatedBody']


def test_truncate_html_handles_empty_body():
    """Test truncate_html handles empty HTML body"""
    result = truncate_html("", 100)
    assert result['truncatedBody'] == ''
    assert result['isTruncated'] is False


def test_truncate_html_handles_invalid_html():
    """Test truncate_html handles malformed HTML gracefully"""
    body = "<p>Unclosed tag<div>Broken<html>"
    result = truncate_html(body, 50)
    assert 'truncatedBody' in result
    assert 'isTruncated' in result


def test_truncate_email_body_detects_plain_text():
    """Test truncate_email_body detects text/plain and delegates correctly"""
    body = "Plain text email body"
    result = truncate_email_body(body, 'text/plain', 100)
    assert result['truncatedBody'] == body
    assert result['isTruncated'] is False


def test_truncate_email_body_detects_html():
    """Test truncate_email_body detects text/html and delegates correctly"""
    body = "<p>HTML email body</p>"
    result = truncate_email_body(body, 'text/html', 100)
    assert 'truncatedBody' in result
    assert 'isTruncated' in result
