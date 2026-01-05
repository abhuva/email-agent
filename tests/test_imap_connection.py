import pytest
import os
from src.imap_connection import connect_imap, IMAPConnectionError, load_imap_queries, search_emails_excluding_processed, fetch_and_parse_emails

@pytest.fixture
def dummy_creds():
    return {'host': 'imap.example.com','user': 'no-such-user','password': 'wrong-password','port': 993}

@pytest.fixture
def config_queries_file(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text('imap_queries:\n  - UNSEEN\n  - FROM \"alice@example.com\"\n')
    return str(cfg)

@pytest.fixture
def config_query_file(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text('imap_query: UNSEEN')
    return str(cfg)

def test_connect_imap_failure(dummy_creds):
    with pytest.raises(IMAPConnectionError):
        connect_imap(**dummy_creds)

def test_load_imap_queries(config_queries_file):
    queries = load_imap_queries(config_queries_file)
    assert queries == ['UNSEEN', 'FROM "alice@example.com"']

def test_load_imap_queries_single(config_query_file):
    queries = load_imap_queries(config_query_file)
    assert queries == ['UNSEEN']

def test_load_imap_queries_invalid(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text('imap_queries: 123')
    with pytest.raises(ValueError):
        load_imap_queries(str(cfg))

def test_search_emails_excluding_processed_mock(monkeypatch):
    class FakeIMAP:
        def select(self, mailbox):
            assert mailbox == 'INBOX'
            return ('OK', [b''])
        def search(self, charset, query):
            queries = ["UNSEEN NOT KEYWORD \"[AI-Processed]\"", "FROM alice@example.com NOT KEYWORD \"[AI-Processed]\""]
            assert query in queries
            if "UNSEEN" in query:
                return ('OK', [b'1 2'])
            elif "FROM" in query:
                return ('OK', [b'3'])
            return ('NO', [])
    fake_imap = FakeIMAP()
    uids = search_emails_excluding_processed(fake_imap, ['UNSEEN', 'FROM alice@example.com'])
    assert set(uids) == {b'1', b'2', b'3'}

def test_fetch_and_parse_emails_mock(monkeypatch):
    class FakeIMAP:
        def fetch(self, msg_id, _):
            assert msg_id in [b'42']
            from email.message import EmailMessage
            em = EmailMessage()
            em['Subject'] = 'Test Subject'
            em['From'] = 'test@sender.com'
            em['Date'] = 'Wed, 21 Jun 2023 09:00:00 +0000'
            em.set_content("Hello World\nLine2")
            return ('OK', [(None, em.as_bytes())])
    fake_imap = FakeIMAP()
    results = fetch_and_parse_emails(fake_imap, [b'42'])
    assert results[0]['subject'] == 'Test Subject'
    assert results[0]['sender'] == 'test@sender.com'
    assert 'Hello World' in results[0]['body']
