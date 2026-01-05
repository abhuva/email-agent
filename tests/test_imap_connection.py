import pytest
import os
from src.imap_connection import connect_imap, IMAPConnectionError, load_imap_queries

@pytest.fixture
def dummy_creds():
    # These credentials should NOT work. Safe for failure by design.
    return {
        'host': 'imap.example.com',
        'user': 'no-such-user',
        'password': 'wrong-password',
        'port': 993
    }

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
