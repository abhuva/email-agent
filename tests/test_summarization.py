"""
Tests for conditional summarization logic.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import os
from src.summarization import (
    get_summarization_tags,
    should_summarize_email,
    load_summarization_prompt,
    check_summarization_required
)


class TestGetSummarizationTags:
    """Tests for get_summarization_tags function."""
    
    def test_returns_valid_tags(self):
        """Test that valid tags are returned."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing.summarization_tags = ['Urgent', 'Important']
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == ['Urgent', 'Important']
    
    def test_returns_empty_list_when_not_configured(self):
        """Test that empty list is returned when not configured."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing = Mock()
            del mock_config.processing.summarization_tags  # Attribute doesn't exist
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == []
    
    def test_handles_none_value(self):
        """Test handling of None value."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing.summarization_tags = None
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == []
    
    def test_handles_non_list_value(self):
        """Test handling of non-list value."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing.summarization_tags = 'Urgent'  # String instead of list
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == []
    
    def test_filters_invalid_tags(self):
        """Test that invalid tags are filtered out."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing.summarization_tags = ['Urgent', '', 'Important', None, 123]
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == ['Urgent', 'Important']
    
    def test_handles_empty_list(self):
        """Test handling of empty list."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing.summarization_tags = []
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == []
    
    def test_strips_whitespace(self):
        """Test that whitespace is stripped from tags."""
        with patch('src.summarization.settings') as mock_settings:
            mock_config = Mock()
            mock_config.processing.summarization_tags = [' Urgent ', '  Important  ']
            mock_settings._config = mock_config
            
            tags = get_summarization_tags()
            assert tags == ['Urgent', 'Important']


class TestShouldSummarizeEmail:
    """Tests for should_summarize_email function."""
    
    def test_returns_true_when_tags_match(self):
        """Test that True is returned when tags match."""
        assert should_summarize_email(['Urgent'], ['Urgent']) is True
        assert should_summarize_email(['Urgent', 'Important'], ['Urgent']) is True
        assert should_summarize_email(['Urgent'], ['Urgent', 'Important']) is True
    
    def test_returns_false_when_tags_dont_match(self):
        """Test that False is returned when tags don't match."""
        assert should_summarize_email(['Neutral'], ['Urgent']) is False
        assert should_summarize_email(['Spam'], ['Urgent', 'Important']) is False
    
    def test_returns_false_when_email_has_no_tags(self):
        """Test that False is returned when email has no tags."""
        assert should_summarize_email([], ['Urgent']) is False
    
    def test_returns_false_when_no_summarization_tags(self):
        """Test that False is returned when no summarization tags."""
        assert should_summarize_email(['Urgent'], []) is False
    
    def test_handles_case_sensitivity(self):
        """Test that matching is case-sensitive."""
        assert should_summarize_email(['urgent'], ['Urgent']) is False
        assert should_summarize_email(['Urgent'], ['urgent']) is False
    
    def test_handles_whitespace(self):
        """Test that whitespace is handled correctly."""
        assert should_summarize_email([' Urgent '], ['Urgent']) is True
        assert should_summarize_email(['Urgent'], [' Urgent ']) is True


class TestLoadSummarizationPrompt:
    """Tests for load_summarization_prompt function."""
    
    def test_loads_existing_file(self):
        """Test loading an existing prompt file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            f.write("Summarize this email.")
            temp_path = f.name
        
        try:
            prompt = load_summarization_prompt(temp_path)
            assert prompt == "Summarize this email."
        finally:
            os.unlink(temp_path)
    
    def test_returns_none_for_nonexistent_file(self):
        """Test that None is returned for nonexistent file."""
        prompt = load_summarization_prompt('/nonexistent/path/prompt.md')
        assert prompt is None
    
    def test_returns_none_for_none_path(self):
        """Test that None is returned for None path."""
        prompt = load_summarization_prompt(None)
        assert prompt is None
    
    def test_returns_none_for_empty_file(self):
        """Test that None is returned for empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            f.write("")
            temp_path = f.name
        
        try:
            prompt = load_summarization_prompt(temp_path)
            assert prompt is None
        finally:
            os.unlink(temp_path)
    
    def test_returns_none_for_whitespace_only_file(self):
        """Test that None is returned for whitespace-only file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            f.write("   \n\t  \n  ")
            temp_path = f.name
        
        try:
            prompt = load_summarization_prompt(temp_path)
            assert prompt is None
        finally:
            os.unlink(temp_path)
    
    def test_strips_whitespace_from_content(self):
        """Test that whitespace is stripped from loaded content."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            f.write("  Summarize this email.  \n")
            temp_path = f.name
        
        try:
            prompt = load_summarization_prompt(temp_path)
            assert prompt == "Summarize this email."
        finally:
            os.unlink(temp_path)
    
    def test_handles_directory_path(self):
        """Test handling of directory path instead of file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt = load_summarization_prompt(temp_dir)
            assert prompt is None


class TestCheckSummarizationRequired:
    """Tests for check_summarization_required function."""
    
    def test_returns_summarize_true_when_tags_match_and_prompt_loads(self):
        """Test that summarize=True when tags match and prompt loads."""
        email = {'tags': ['Urgent']}
        
        with patch('src.summarization.settings') as mock_settings, \
             patch('src.summarization.load_summarization_prompt', return_value='Summarize this email.'), \
             patch('src.summarization.get_summarization_tags', return_value=['Urgent']):
            mock_config = Mock()
            mock_config.paths.summarization_prompt_path = None
            mock_settings._config = mock_config
            
            result = check_summarization_required(email)
            assert result['summarize'] is True
            assert result['prompt'] == 'Summarize this email.'
            assert result['reason'] is None
    
    def test_returns_summarize_false_when_no_tags_configured(self):
        """Test that summarize=False when no tags configured."""
        email = {'tags': ['Urgent']}
        
        with patch('src.summarization.get_summarization_tags', return_value=[]):
            result = check_summarization_required(email)
            assert result['summarize'] is False
            assert result['prompt'] is None
            assert result['reason'] == 'no_summarization_tags_configured'
    
    def test_returns_summarize_false_when_tags_dont_match(self):
        """Test that summarize=False when tags don't match."""
        email = {'tags': ['Neutral']}
        
        with patch('src.summarization.get_summarization_tags', return_value=['Urgent']):
            result = check_summarization_required(email)
            assert result['summarize'] is False
            assert result['prompt'] is None
            assert result['reason'] == 'tags_do_not_match'
    
    def test_returns_summarize_false_when_prompt_fails_to_load(self):
        """Test that summarize=False when prompt fails to load."""
        email = {'tags': ['Urgent']}
        
        with patch('src.summarization.settings') as mock_settings, \
             patch('src.summarization.get_summarization_tags', return_value=['Urgent']), \
             patch('src.summarization.load_summarization_prompt', return_value=None):
            mock_config = Mock()
            mock_config.paths.summarization_prompt_path = '/nonexistent/path.md'
            mock_settings._config = mock_config
            
            result = check_summarization_required(email)
            assert result['summarize'] is False
            assert result['prompt'] is None
            assert result['reason'] == 'prompt_load_failed'
    
    def test_handles_email_without_tags_key(self):
        """Test handling of email without tags key."""
        email = {}  # No tags key
        
        with patch('src.summarization.get_summarization_tags', return_value=['Urgent']):
            result = check_summarization_required(email)
            assert result['summarize'] is False
            assert result['reason'] == 'tags_do_not_match'
    
    def test_handles_email_with_non_list_tags(self):
        """Test handling of email with non-list tags."""
        email = {'tags': 'Urgent'}  # String instead of list
        
        with patch('src.summarization.get_summarization_tags', return_value=['Urgent']):
            result = check_summarization_required(email)
            assert result['summarize'] is False
            assert result['reason'] == 'tags_do_not_match'
    
    def test_handles_exceptions_gracefully(self):
        """Test that exceptions are handled gracefully."""
        # Make get_summarization_tags raise an exception
        with patch('src.summarization.get_summarization_tags', side_effect=Exception("Test error")):
            email = {'tags': ['Urgent']}
            result = check_summarization_required(email)
            assert result['summarize'] is False
            assert result['prompt'] is None
            assert 'unexpected_error' in result['reason']
    
    def test_multiple_matching_tags(self):
        """Test with multiple matching tags."""
        email = {'tags': ['Urgent', 'Neutral']}
        
        with patch('src.summarization.settings') as mock_settings, \
             patch('src.summarization.load_summarization_prompt', return_value='Summarize this email.'), \
             patch('src.summarization.get_summarization_tags', return_value=['Urgent', 'Important']):
            mock_config = Mock()
            mock_config.paths.summarization_prompt_path = None
            mock_settings._config = mock_config
            
            result = check_summarization_required(email)
            assert result['summarize'] is True
            assert result['prompt'] == 'Summarize this email.'
