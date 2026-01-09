import pytest
import os
from unittest.mock import patch
from src.imap_connection import connect_imap, IMAPConnectionError, load_imap_queries, search_emails_excluding_processed, fetch_and_parse_emails, fetch_emails, IMAPFetchError, add_tags_to_email

# ...existing fixtures and tests...

class DummyIMAP:
    def __init__(self):
        self.calls = []
        self.uid_results = []
    def uid(self, operation, uid, flags_silent, tagset):
        self.calls.append((operation, uid, flags_silent, tagset))
        if hasattr(self, "simulate_fail") and self.simulate_fail:
            return ('NO', [b'error'])
        self.uid_results.append((uid, tagset))
        return ('OK', [b'success'])

@patch('src.imap_connection.is_dry_run', return_value=False)
def test_add_tags_to_email_success(mock_dry_run):
    imap = DummyIMAP()
    assert add_tags_to_email(imap, b'42', ['Important', 'AIProcessed']) is True
    assert len(imap.calls) > 0
    assert imap.calls[-1][0] == 'STORE'
    # The tagset is the 4th argument (index 3)
    tagset_str = str(imap.calls[-1][3])
    assert 'Important' in tagset_str
    assert 'AIProcessed' in tagset_str

@patch('src.imap_connection.is_dry_run', return_value=False)
def test_add_tags_to_email_failure(mock_dry_run):
    imap = DummyIMAP()
    imap.simulate_fail = True
    assert add_tags_to_email(imap, '99', ['Spam']) is False
