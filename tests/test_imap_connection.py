import pytest
import os
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

def test_add_tags_to_email_success():
    imap = DummyIMAP()
    assert add_tags_to_email(imap, b'42', ['Important', 'AIProcessed']) is True
    assert imap.calls[-1][0] == 'STORE'
    assert 'Important' in imap.calls[-1][3]
    assert 'AIProcessed' in imap.calls[-1][3]

def test_add_tags_to_email_failure():
    imap = DummyIMAP()
    imap.simulate_fail = True
    assert add_tags_to_email(imap, '99', ['Spam']) is False
