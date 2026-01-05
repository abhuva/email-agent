import pytest
import os
from src.imap_connection import connect_imap, IMAPConnectionError

@pytest.fixture
def dummy_creds():
    # These credentials should NOT work. Safe for failure by design.
    return {
        'host': 'imap.example.com',
        'user': 'no-such-user',
        'password': 'wrong-password',
        'port': 993
    }

# You may want to set IMAP test host/user via environment variables for real integration tests.

def test_connect_imap_failure(dummy_creds):
    with pytest.raises(IMAPConnectionError):
        connect_imap(**dummy_creds)
