"""
Verification tests for test infrastructure fixtures.

This module tests that all fixtures in conftest.py work correctly.
This is a temporary test file to verify the infrastructure.
"""
import pytest
from pathlib import Path


def test_v3_config_dict_fixture(v3_config_dict):
    """Test that v3_config_dict fixture returns proper structure."""
    assert 'imap' in v3_config_dict
    assert 'paths' in v3_config_dict
    assert 'openrouter' in v3_config_dict
    assert 'processing' in v3_config_dict
    assert v3_config_dict['imap']['server'] == 'test.imap.com'


# V3 config_file fixture test removed - V4 uses v4_config_file instead


def test_sample_email_data_fixture(sample_email_data):
    """Test that sample_email_data fixture returns proper structure."""
    assert 'uid' in sample_email_data
    assert 'subject' in sample_email_data
    assert 'from' in sample_email_data
    assert 'to' in sample_email_data
    assert 'body' in sample_email_data


def test_mock_imap_connection_fixture(mock_imap_connection):
    """Test that mock_imap_connection fixture works."""
    assert mock_imap_connection is not None
    assert hasattr(mock_imap_connection, 'select')
    assert hasattr(mock_imap_connection, 'search')


def test_mock_llm_client_fixture(mock_llm_client):
    """Test that mock_llm_client fixture works."""
    assert mock_llm_client is not None
    assert hasattr(mock_llm_client, 'classify_email')
    result = mock_llm_client.classify_email("test")
    assert result.spam_score == 2
    assert result.importance_score == 9


def test_dry_run_helper_fixture(dry_run_helper):
    """Test that dry_run_helper fixture works."""
    assert dry_run_helper is not None
    dry_run_helper.disable()
    dry_run_helper.assert_not_dry_run()
    dry_run_helper.enable()
    dry_run_helper.assert_dry_run()


def test_email_variants_fixtures(
    sample_email_data,
    sample_email_data_important,
    sample_email_data_spam,
    sample_email_data_html,
    sample_email_data_large
):
    """Test that all email variant fixtures work."""
    assert sample_email_data['uid'] != sample_email_data_important['uid']
    assert sample_email_data_spam['subject'].lower().find('won') != -1
    assert sample_email_data_html['content_type'] == 'text/html'
    assert len(sample_email_data_large['body']) > 1000
