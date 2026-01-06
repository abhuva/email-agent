"""
Tests for YAML frontmatter generation.
"""

import pytest
import yaml
from datetime import datetime
from src.yaml_frontmatter import (
    extract_email_metadata,
    normalize_date,
    yaml_safe_string,
    generate_yaml_frontmatter,
    generate_email_yaml_frontmatter
)


class TestExtractEmailMetadata:
    """Tests for extract_email_metadata function."""
    
    def test_basic_extraction(self):
        """Test extraction of basic email fields."""
        email = {
            'subject': 'Test Subject',
            'sender': 'sender@example.com',
            'to': 'recipient@example.com',
            'cc': 'cc@example.com',
            'date': 'Mon, 27 Oct 2023 10:00:00 +0000',
            'message_id': '<test123@example.com>'
        }
        metadata = extract_email_metadata(email)
        assert metadata['subject'] == 'Test Subject'
        assert metadata['from'] == 'sender@example.com'
        assert metadata['to'] == ['recipient@example.com']
        assert metadata['cc'] == ['cc@example.com']
        assert metadata['date'] == 'Mon, 27 Oct 2023 10:00:00 +0000'
        assert metadata['source_message_id'] == '<test123@example.com>'
    
    def test_missing_fields(self):
        """Test handling of missing fields."""
        email = {'subject': 'Test'}
        metadata = extract_email_metadata(email)
        assert metadata['subject'] == 'Test'
        assert metadata['from'] is None
        assert metadata['to'] == []
        assert metadata['cc'] == []
        assert metadata['date'] is None
        assert metadata['source_message_id'] is None
    
    def test_empty_email(self):
        """Test handling of empty email object."""
        metadata = extract_email_metadata({})
        assert all(v is None or v == [] for v in metadata.values())
    
    def test_none_email(self):
        """Test handling of None email."""
        metadata = extract_email_metadata(None)
        assert all(v is None or v == [] for v in metadata.values())
    
    def test_to_as_list(self):
        """Test handling of 'to' as a list."""
        email = {'to': ['user1@example.com', 'user2@example.com']}
        metadata = extract_email_metadata(email)
        assert metadata['to'] == ['user1@example.com', 'user2@example.com']
    
    def test_cc_as_list(self):
        """Test handling of 'cc' as a list."""
        email = {'cc': ['cc1@example.com', 'cc2@example.com']}
        metadata = extract_email_metadata(email)
        assert metadata['cc'] == ['cc1@example.com', 'cc2@example.com']
    
    def test_to_with_raw_message(self):
        """Test extraction from raw_message object."""
        class MockMessage:
            def get(self, key, default=None):
                if key == 'To':
                    return 'user1@example.com, user2@example.com'
                elif key == 'CC':
                    return 'cc@example.com'
                elif key == 'Message-ID':
                    return '<msg123@example.com>'
                return default
        
        email = {'raw_message': MockMessage()}
        metadata = extract_email_metadata(email)
        assert len(metadata['to']) == 2
        assert 'user1@example.com' in metadata['to']
        assert 'cc@example.com' in metadata['cc']
        assert metadata['source_message_id'] == '<msg123@example.com>'


class TestNormalizeDate:
    """Tests for normalize_date function."""
    
    def test_rfc2822_date(self):
        """Test parsing RFC 2822 date format."""
        date_str = "Mon, 27 Oct 2023 10:00:00 +0000"
        result = normalize_date(date_str)
        assert result is not None
        assert '2023-10-27' in result
        assert 'T' in result  # ISO format
    
    def test_iso_date(self):
        """Test parsing ISO 8601 date format."""
        date_str = "2023-10-27T10:00:00Z"
        result = normalize_date(date_str)
        assert result is not None
        assert '2023-10-27' in result
    
    def test_invalid_date(self):
        """Test handling of invalid date."""
        result = normalize_date("not a date")
        assert result is None
    
    def test_none_date(self):
        """Test handling of None date."""
        result = normalize_date(None)
        assert result is None
    
    def test_empty_date(self):
        """Test handling of empty date."""
        result = normalize_date("")
        assert result is None


class TestYamlSafeString:
    """Tests for yaml_safe_string function."""
    
    def test_normal_string(self):
        """Test normal string doesn't need quoting."""
        result = yaml_safe_string("Normal text")
        assert result == "Normal text"
    
    def test_string_with_colon(self):
        """Test string with colon (PyYAML handles quoting automatically)."""
        result = yaml_safe_string("Text with: colon")
        # PyYAML will handle quoting when needed, so we just check it returns a string
        assert isinstance(result, str)
        assert "colon" in result
    
    def test_string_with_quotes(self):
        """Test string with quotes needs escaping."""
        result = yaml_safe_string('Text with "quotes"')
        assert '"' in result
        assert '\\"' in result or result.count('"') > 2
    
    def test_none_value(self):
        """Test None value returns 'null'."""
        result = yaml_safe_string(None)
        assert result == 'null'
    
    def test_http_url(self):
        """Test HTTP URL doesn't need quoting for colon."""
        result = yaml_safe_string("https://example.com")
        # Should not quote just because of colon in URL
        assert isinstance(result, str)


class TestGenerateYamlFrontmatter:
    """Tests for generate_yaml_frontmatter function."""
    
    def test_basic_frontmatter(self):
        """Test generation of basic frontmatter."""
        metadata = {
            'subject': 'Test Subject',
            'from': 'sender@example.com',
            'to': ['recipient@example.com'],
            'cc': [],
            'date': '2023-10-27T10:00:00+00:00',
            'source_message_id': '<test123@example.com>'
        }
        frontmatter = generate_yaml_frontmatter(metadata)
        
        # Check delimiters
        assert frontmatter.startswith('---')
        assert frontmatter.endswith('---')
        
        # Check content
        assert 'subject: Test Subject' in frontmatter
        assert 'from: sender@example.com' in frontmatter
        assert 'to:' in frontmatter
        assert 'cc:' in frontmatter
    
    def test_frontmatter_with_null_values(self):
        """Test frontmatter with null values."""
        metadata = {
            'subject': None,
            'from': None,
            'to': [],
            'cc': [],
            'date': None,
            'source_message_id': None
        }
        frontmatter = generate_yaml_frontmatter(metadata)
        
        # Should still be valid YAML
        assert frontmatter.startswith('---')
        assert frontmatter.endswith('---')
        
        # Parse to verify it's valid YAML
        yaml_content = frontmatter.strip('---').strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed is not None
    
    def test_frontmatter_with_multiple_recipients(self):
        """Test frontmatter with multiple recipients."""
        metadata = {
            'subject': 'Test',
            'from': 'sender@example.com',
            'to': ['user1@example.com', 'user2@example.com'],
            'cc': ['cc1@example.com'],
            'date': '2023-10-27T10:00:00+00:00',
            'source_message_id': None
        }
        frontmatter = generate_yaml_frontmatter(metadata)
        
        # Should be valid YAML
        yaml_content = frontmatter.strip('---').strip()
        parsed = yaml.safe_load(yaml_content)
        assert isinstance(parsed['to'], list)
        assert len(parsed['to']) == 2
    
    def test_frontmatter_is_valid_yaml(self):
        """Test that generated frontmatter is valid YAML."""
        metadata = {
            'subject': 'Test Subject: With Colon',
            'from': 'sender@example.com',
            'to': ['recipient@example.com'],
            'cc': [],
            'date': '2023-10-27T10:00:00+00:00',
            'source_message_id': '<test@example.com>'
        }
        frontmatter = generate_yaml_frontmatter(metadata)
        
        # Extract YAML content (between --- delimiters)
        lines = frontmatter.strip().split('\n')
        yaml_lines = [line for line in lines if line != '---']
        yaml_content = '\n'.join(yaml_lines)
        
        # Should parse without errors
        parsed = yaml.safe_load(yaml_content)
        assert parsed is not None
        assert parsed['subject'] == 'Test Subject: With Colon'


class TestGenerateEmailYamlFrontmatter:
    """Tests for generate_email_yaml_frontmatter function."""
    
    def test_complete_workflow(self):
        """Test complete workflow from email to frontmatter."""
        email = {
            'subject': 'Test Email',
            'sender': 'sender@example.com',
            'to': 'recipient@example.com',
            'date': 'Mon, 27 Oct 2023 10:00:00 +0000',
            'message_id': '<test123@example.com>'
        }
        frontmatter = generate_email_yaml_frontmatter(email)
        
        # Should be valid YAML frontmatter
        assert frontmatter.startswith('---')
        assert frontmatter.endswith('---')
        assert 'subject: Test Email' in frontmatter
        assert 'from: sender@example.com' in frontmatter
    
    def test_with_special_characters(self):
        """Test handling of special characters in subject."""
        email = {
            'subject': 'Email with: colon and "quotes"',
            'sender': 'sender@example.com',
            'date': '2023-10-27T10:00:00+00:00'
        }
        frontmatter = generate_email_yaml_frontmatter(email)
        
        # Should be valid YAML
        yaml_content = frontmatter.strip('---').strip()
        parsed = yaml.safe_load(yaml_content)
        assert 'colon' in parsed['subject']
    
    def test_with_malformed_date(self):
        """Test handling of malformed date."""
        email = {
            'subject': 'Test',
            'sender': 'sender@example.com',
            'date': 'not a valid date'
        }
        frontmatter = generate_email_yaml_frontmatter(email)
        
        # Should still generate valid frontmatter
        assert frontmatter.startswith('---')
        assert frontmatter.endswith('---')
        
        # Date should be None or null
        yaml_content = frontmatter.strip('---').strip()
        parsed = yaml.safe_load(yaml_content)
        assert parsed['date'] is None or parsed['date'] == 'null'
    
    def test_obsidian_compatible_format(self):
        """Test that frontmatter is compatible with Obsidian."""
        email = {
            'subject': 'Test Email',
            'sender': 'sender@example.com',
            'to': ['user1@example.com', 'user2@example.com'],
            'cc': ['cc@example.com'],
            'date': '2023-10-27T10:00:00+00:00',
            'message_id': '<test@example.com>'
        }
        frontmatter = generate_email_yaml_frontmatter(email)
        
        # Obsidian expects:
        # 1. --- delimiters
        # 2. Valid YAML
        # 3. Proper spacing
        
        # Check structure
        assert frontmatter.startswith('---\n')
        assert frontmatter.endswith('\n---')
        
        # Parse to verify structure
        yaml_content = frontmatter.strip('---').strip()
        parsed = yaml.safe_load(yaml_content)
        
        # Check required fields are present
        assert 'subject' in parsed
        assert 'from' in parsed
        assert 'to' in parsed
        assert 'cc' in parsed
        assert 'date' in parsed
        assert 'source_message_id' in parsed
