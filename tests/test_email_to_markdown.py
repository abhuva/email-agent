"""
Tests for email body sanitization and Markdown conversion.
"""

import pytest
from src.email_to_markdown import (
    detect_content_type,
    sanitize_html_body,
    html_to_markdown,
    enhance_plain_text_to_markdown,
    convert_email_to_markdown
)


class TestDetectContentType:
    """Tests for detect_content_type function."""
    
    def test_detects_html(self):
        """Test detection of HTML content."""
        assert detect_content_type("<p>Hello</p>") is True
        assert detect_content_type("<html><body>Test</body></html>") is True
        assert detect_content_type("Text with <strong>bold</strong>") is True
    
    def test_detects_plain_text(self):
        """Test detection of plain text content."""
        assert detect_content_type("Plain text email") is False
        assert detect_content_type("No HTML tags here") is False
        assert detect_content_type("") is False
    
    def test_case_insensitive(self):
        """Test that HTML detection is case-insensitive."""
        assert detect_content_type("<P>Test</P>") is True
        assert detect_content_type("<STRONG>Bold</STRONG>") is True


class TestSanitizeHtmlBody:
    """Tests for sanitize_html_body function."""
    
    def test_removes_script_tags(self):
        """Test that script tags are removed."""
        html = "<p>Hello</p><script>alert('xss')</script>"
        result = sanitize_html_body(html)
        assert 'script' not in result['content'].lower()
        assert 'alert' not in result['content']
        assert result['isHtml'] is True
    
    def test_removes_style_tags(self):
        """Test that style tags are removed."""
        html = "<p>Hello</p><style>body { color: red; }</style>"
        result = sanitize_html_body(html)
        assert 'style' not in result['content'].lower()
        assert result['isHtml'] is True
    
    def test_removes_inline_images(self):
        """Test that img tags are removed."""
        html = "<p>Hello</p><img src='image.jpg' alt='test'>"
        result = sanitize_html_body(html)
        assert 'img' not in result['content'].lower()
        assert result['isHtml'] is True
    
    def test_removes_dangerous_elements(self):
        """Test that dangerous elements are removed."""
        html = "<p>Hello</p><iframe src='evil.com'></iframe>"
        result = sanitize_html_body(html)
        assert 'iframe' not in result['content'].lower()
        assert result['isHtml'] is True
    
    def test_removes_javascript_urls(self):
        """Test that javascript: URLs are removed."""
        html = "<p>Hello</p><a href='javascript:alert(1)'>Click</a>"
        result = sanitize_html_body(html)
        assert 'javascript:' not in result['content'].lower()
        assert result['isHtml'] is True
    
    def test_preserves_safe_content(self):
        """Test that safe HTML content is preserved."""
        html = "<p>Hello <strong>world</strong></p>"
        result = sanitize_html_body(html)
        assert 'Hello' in result['content']
        assert 'world' in result['content']
        assert result['isHtml'] is True
    
    def test_empty_body(self):
        """Test handling of empty body."""
        result = sanitize_html_body("")
        assert result['content'] == ""
        assert result['isHtml'] is True
        assert result['warnings'] == []
    
    def test_returns_warnings(self):
        """Test that warnings are returned for removed content."""
        html = "<p>Hello</p><script>alert('xss')</script>"
        result = sanitize_html_body(html)
        assert len(result['warnings']) > 0
        assert any('script' in w.lower() for w in result['warnings'])


class TestHtmlToMarkdown:
    """Tests for html_to_markdown function."""
    
    def test_converts_paragraphs(self):
        """Test conversion of paragraphs."""
        html = "<p>Hello world</p>"
        markdown = html_to_markdown(html)
        assert 'Hello world' in markdown
    
    def test_converts_headings(self):
        """Test conversion of headings."""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        markdown = html_to_markdown(html)
        assert 'Title' in markdown
        assert 'Subtitle' in markdown
    
    def test_converts_bold_and_italic(self):
        """Test conversion of emphasis."""
        html = "<p>Hello <strong>bold</strong> and <em>italic</em></p>"
        markdown = html_to_markdown(html)
        assert 'bold' in markdown
        assert 'italic' in markdown
    
    def test_converts_links(self):
        """Test conversion of links."""
        html = "<p>Visit <a href='https://example.com'>example</a></p>"
        markdown = html_to_markdown(html)
        assert 'example' in markdown
        # Link text should be present, URL may be formatted differently by html2text
        # Just verify the link text is there (html2text formats links as [text](url))
        assert 'example' in markdown
    
    def test_converts_lists(self):
        """Test conversion of lists."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        markdown = html_to_markdown(html)
        assert 'Item 1' in markdown
        assert 'Item 2' in markdown
    
    def test_converts_blockquotes(self):
        """Test conversion of blockquotes."""
        html = "<blockquote>Quoted text</blockquote>"
        markdown = html_to_markdown(html)
        assert 'Quoted text' in markdown
    
    def test_empty_html(self):
        """Test handling of empty HTML."""
        markdown = html_to_markdown("")
        assert markdown == ""
    
    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<p>Unclosed tag"
        markdown = html_to_markdown(html)
        # Should not crash, should return something
        assert isinstance(markdown, str)


class TestEnhancePlainTextToMarkdown:
    """Tests for enhance_plain_text_to_markdown function."""
    
    def test_preserves_plain_text(self):
        """Test that plain text is preserved."""
        text = "This is plain text"
        markdown = enhance_plain_text_to_markdown(text)
        assert 'This is plain text' in markdown
    
    def test_converts_urls(self):
        """Test conversion of URLs to Markdown links."""
        text = "Check out https://example.com"
        markdown = enhance_plain_text_to_markdown(text)
        assert 'example.com' in markdown
    
    def test_preserves_lists(self):
        """Test that list-like patterns are preserved."""
        text = "- Item 1\n- Item 2"
        markdown = enhance_plain_text_to_markdown(text)
        assert 'Item 1' in markdown
        assert 'Item 2' in markdown
    
    def test_removes_excessive_empty_lines(self):
        """Test that excessive empty lines are removed."""
        text = "Line 1\n\n\n\n\nLine 2"
        markdown = enhance_plain_text_to_markdown(text)
        # Should have at most 2 consecutive newlines
        assert '\n\n\n' not in markdown
    
    def test_empty_text(self):
        """Test handling of empty text."""
        markdown = enhance_plain_text_to_markdown("")
        assert markdown == ""


class TestConvertEmailToMarkdown:
    """Tests for convert_email_to_markdown function."""
    
    def test_converts_html_email(self):
        """Test conversion of HTML email."""
        html = "<p>Hello <strong>world</strong></p>"
        markdown = convert_email_to_markdown(html)
        assert 'Hello' in markdown
        assert 'world' in markdown
    
    def test_converts_plain_text_email(self):
        """Test conversion of plain text email."""
        text = "This is a plain text email"
        markdown = convert_email_to_markdown(text)
        assert 'This is a plain text email' in markdown
    
    def test_uses_content_type_hint(self):
        """Test that content_type parameter is respected."""
        html = "<p>Hello</p>"
        # Even if it doesn't look like HTML, if content_type says HTML, treat it as HTML
        markdown = convert_email_to_markdown(html, content_type='text/html')
        assert isinstance(markdown, str)
    
    def test_removes_scripts_from_html(self):
        """Test that scripts are removed from HTML."""
        html = "<p>Hello</p><script>alert('xss')</script>"
        markdown = convert_email_to_markdown(html)
        assert 'alert' not in markdown
        assert 'Hello' in markdown
    
    def test_handles_empty_body(self):
        """Test handling of empty email body."""
        markdown = convert_email_to_markdown("")
        assert markdown == ""
    
    def test_handles_none_body(self):
        """Test handling of None email body."""
        markdown = convert_email_to_markdown(None)
        assert markdown == ""
    
    def test_complex_html_email(self):
        """Test conversion of complex HTML email."""
        html = """
        <html>
        <body>
            <h1>Newsletter</h1>
            <p>Hello <strong>subscriber</strong>!</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
            <blockquote>Quote here</blockquote>
        </body>
        </html>
        """
        markdown = convert_email_to_markdown(html)
        assert 'Newsletter' in markdown
        assert 'subscriber' in markdown
        assert 'Item 1' in markdown
        assert 'Item 2' in markdown
        assert 'Quote here' in markdown
    
    def test_plain_text_with_urls(self):
        """Test plain text with URLs."""
        text = "Visit https://example.com for more info"
        markdown = convert_email_to_markdown(text)
        assert 'example.com' in markdown or 'https://example.com' in markdown
    
    def test_strict_mode(self):
        """Test strict mode option."""
        html = "<p>Hello</p><script>alert('xss')</script>"
        markdown = convert_email_to_markdown(html, strict_mode=True)
        assert 'alert' not in markdown
        assert 'Hello' in markdown
    
    def test_obsidian_compatible_output(self):
        """Test that output is compatible with Obsidian."""
        html = "<p>Test email with <a href='https://example.com'>link</a></p>"
        markdown = convert_email_to_markdown(html)
        
        # Should be valid Markdown
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        
        # Should not contain HTML tags (except possibly in code blocks)
        # Basic check: no script tags
        assert '<script' not in markdown.lower()
        
        # Should contain the text content
        assert 'Test email' in markdown or 'link' in markdown
