import pytest
import logging
from src.email_tagging import tag_email_safely
from src.imap_connection import add_tags_to_email

class MockIMAP:
    def __init__(self):
        self.calls = []
        self.should_fail = False
    
    def uid(self, operation, uid, flags_silent, tagset):
        self.calls.append((operation, uid, flags_silent, tagset))
        if self.should_fail:
            return ('NO', [b'error'])
        return ('OK', [b'success'])

@pytest.fixture
def mock_imap():
    return MockIMAP()

@pytest.fixture
def tag_mapping():
    return {
        'urgent': 'Urgent',
        'neutral': 'Neutral',
        'spam': 'Spam'
    }

def test_tag_email_safely_urgent(mock_imap, tag_mapping):
    """Test that 'urgent' AI response maps to 'Urgent' tag + [AI-Processed]"""
    result = tag_email_safely(mock_imap, b'42', 'urgent', tag_mapping)
    assert result is True
    assert len(mock_imap.calls) == 1
    call = mock_imap.calls[0]
    assert call[0] == 'STORE'
    assert 'Urgent' in call[3]
    assert '[AI-Processed]' in call[3]

def test_tag_email_safely_neutral(mock_imap, tag_mapping):
    """Test that 'neutral' AI response maps to 'Neutral' tag + [AI-Processed]"""
    result = tag_email_safely(mock_imap, '99', 'neutral', tag_mapping)
    assert result is True
    assert 'Neutral' in mock_imap.calls[0][3]
    assert '[AI-Processed]' in mock_imap.calls[0][3]

def test_tag_email_safely_spam(mock_imap, tag_mapping):
    """Test that 'spam' AI response maps to 'Spam' tag + [AI-Processed]"""
    result = tag_email_safely(mock_imap, 123, 'spam', tag_mapping)
    assert result is True
    assert 'Spam' in mock_imap.calls[0][3]
    assert '[AI-Processed]' in mock_imap.calls[0][3]

def test_tag_email_safely_always_adds_processed_tag(mock_imap, tag_mapping):
    """Test that [AI-Processed] is always added regardless of AI response"""
    for ai_resp in ['urgent', 'neutral', 'spam', 'invalid', '', None]:
        mock_imap.calls = []
        tag_email_safely(mock_imap, '1', ai_resp, tag_mapping)
        assert len(mock_imap.calls) == 1
        assert '[AI-Processed]' in mock_imap.calls[0][3]

def test_tag_email_safely_fallback_to_neutral(mock_imap, tag_mapping):
    """Test that invalid AI response falls back to Neutral + [AI-Processed]"""
    result = tag_email_safely(mock_imap, '1', 'gibberish response', tag_mapping)
    assert result is True
    assert 'Neutral' in mock_imap.calls[0][3]
    assert '[AI-Processed]' in mock_imap.calls[0][3]

def test_tag_email_safely_handles_imap_failure(mock_imap, tag_mapping):
    """Test that IMAP failures are handled gracefully"""
    mock_imap.should_fail = True
    result = tag_email_safely(mock_imap, '1', 'urgent', tag_mapping)
    assert result is False

def test_tag_email_safely_handles_exceptions(mock_imap, tag_mapping, monkeypatch):
    """Test that exceptions in tag_email_safely are caught and logged"""
    def broken_add_tags(*args, **kwargs):
        raise Exception("Simulated error")
    
    monkeypatch.setattr('src.email_tagging.add_tags_to_email', broken_add_tags)
    result = tag_email_safely(mock_imap, '1', 'urgent', tag_mapping)
    assert result is False
