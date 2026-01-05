"""
TDD tests for complete email tagging workflow with validation and verification.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.email_tagging import process_email_with_ai_tags


class MockIMAPConnection:
    """Mock IMAP connection for testing"""
    def __init__(self, before_flags=None, after_flags=None):
        self.before_flags = before_flags or ['\\Seen']
        self.after_flags = after_flags or ['\\Seen', 'Urgent', '[AI-Processed]']
        self.uid_calls = []
    
    def uid(self, operation, uid, *args):
        self.uid_calls.append((operation, uid, args))
        if operation == 'FETCH':
            if len(self.uid_calls) == 1:
                # First call: before flags
                flags_str = ' '.join(self.before_flags)
                return ('OK', [f'1 (FLAGS ({flags_str}))'.encode()])
            else:
                # Second call: after flags
                flags_str = ' '.join(self.after_flags)
                return ('OK', [f'1 (FLAGS ({flags_str}))'.encode()])
        elif operation == 'STORE':
            return ('OK', [b'1 STORED'])
        return ('OK', [b''])


def test_process_email_with_ai_tags_validates_empty_uid():
    """Test that process_email_with_ai_tags rejects empty/invalid UID"""
    imap = MockIMAPConnection()
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral'}}
    
    result = process_email_with_ai_tags(imap, None, "urgent", config)
    assert result['success'] is False
    assert result['applied_tags'] == []
    
    result = process_email_with_ai_tags(imap, "", "urgent", config)
    assert result['success'] is False


def test_process_email_with_ai_tags_validates_ai_response():
    """Test that process_email_with_ai_tags validates AI response is not empty"""
    imap = MockIMAPConnection()
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral'}}
    
    result = process_email_with_ai_tags(imap, 123, None, config)
    assert result['success'] is False
    
    result = process_email_with_ai_tags(imap, 123, "", config)
    assert result['success'] is False


def test_process_email_with_ai_tags_fetches_before_tags():
    """Test that process_email_with_ai_tags fetches flags before tagging"""
    imap = MockIMAPConnection(before_flags=['\\Seen', '\\Flagged'])
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral'}}
    
    result = process_email_with_ai_tags(imap, 123, "urgent", config)
    
    # Should have called UID FETCH for before flags
    fetch_calls = [call for call in imap.uid_calls if call[0] == 'FETCH']
    assert len(fetch_calls) >= 1
    assert '\\Seen' in result['before_tags'] or 'Seen' in result['before_tags']


def test_process_email_with_ai_tags_verifies_after_tags():
    """Test that process_email_with_ai_tags verifies tags were applied by fetching after"""
    imap = MockIMAPConnection(
        before_flags=['\\Seen'],
        after_flags=['\\Seen', 'Urgent', '[AI-Processed]']
    )
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral'}}
    
    result = process_email_with_ai_tags(imap, 123, "urgent", config)
    
    # Should have called UID FETCH twice (before and after)
    fetch_calls = [call for call in imap.uid_calls if call[0] == 'FETCH']
    assert len(fetch_calls) >= 2
    assert '[AI-Processed]' in result['after_tags']


def test_process_email_with_ai_tags_returns_complete_dict():
    """Test that process_email_with_ai_tags returns dict with success/applied_tags/before_tags/after_tags"""
    imap = MockIMAPConnection()
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral'}}
    
    result = process_email_with_ai_tags(imap, 123, "urgent", config)
    
    assert 'success' in result
    assert 'applied_tags' in result
    assert 'before_tags' in result
    assert 'after_tags' in result
    assert 'keyword' in result
    assert 'timestamp' in result
    assert isinstance(result['applied_tags'], list)
    assert isinstance(result['before_tags'], list)
    assert isinstance(result['after_tags'], list)


def test_process_email_with_ai_tags_logs_audit_trail(caplog):
    """Test that process_email_with_ai_tags logs full audit trail with timestamps"""
    import logging
    caplog.set_level(logging.INFO)
    
    imap = MockIMAPConnection()
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral'}}
    metadata = {'subject': 'Test Email', 'sender': 'test@example.com'}
    
    result = process_email_with_ai_tags(imap, 123, "urgent", config, email_metadata=metadata)
    
    # Check that logging occurred
    log_messages = caplog.text
    assert 'Processing email UID 123' in log_messages
    assert 'tagged successfully' in log_messages or 'Failed to tag' in log_messages
    assert result['timestamp']  # Timestamp should be set


def test_process_email_with_ai_tags_handles_neutral_fallback():
    """Test that process_email_with_ai_tags handles neutral fallback correctly"""
    imap = MockIMAPConnection()
    config = {'tag_mapping': {'urgent': 'Urgent', 'neutral': 'Neutral', 'spam': 'Spam'}}
    
    # Test with neutral keyword
    result = process_email_with_ai_tags(imap, 123, "neutral", config)
    assert result['keyword'] == 'neutral'
    assert 'Neutral' in result['applied_tags']
    assert '[AI-Processed]' in result['applied_tags']


def test_process_email_with_ai_tags_handles_missing_config():
    """Test that process_email_with_ai_tags handles missing tag_mapping in config"""
    imap = MockIMAPConnection()
    config = {}  # Missing tag_mapping
    
    result = process_email_with_ai_tags(imap, 123, "urgent", config)
    assert result['success'] is False
