"""
TDD tests for main processing loop functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
from src.main_loop import (
    process_email_with_ai,
    run_email_processing_loop,
    generate_analytics_summary,
    AI_PROCESSING_FAILED_FLAG
)


@pytest.fixture
def mock_config():
    """Create a mock ConfigManager"""
    config = Mock()
    config.openrouter_model = 'test-model'
    config.max_emails_per_run = 10
    config.processed_tag = 'AIProcessed'
    config.tag_mapping = {'urgent': 'Urgent', 'neutral': 'Neutral', 'spam': 'Spam'}
    config.max_body_chars = 4000
    config.get_imap_query.return_value = 'UNSEEN'  # V2: single query string
    config.openrouter_params.return_value = {
        'api_key': 'test-key',
        'api_url': 'https://test.api'
    }
    config.imap_connection_params.return_value = {
        'host': 'test.host',
        'username': 'test@user',
        'password': 'test-pass',
        'port': 993
    }
    return config


@pytest.fixture
def sample_email():
    """Create a sample email dict"""
    return {
        'id': b'123',
        'subject': 'Test Email',
        'sender': 'test@example.com',
        'body': 'This is a test email body',
        'content_type': 'text/plain'
    }


def test_process_email_with_ai_success(mock_config, sample_email):
    """Test successful AI processing of an email"""
    mock_client = Mock()
    mock_response = {
        'choices': [{
            'message': {
                'content': 'urgent, important'
            }
        }]
    }
    
    with patch('src.main_loop.send_email_prompt_for_keywords', return_value=mock_response), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', return_value=['urgent', 'important']), \
         patch('src.main_loop.truncate_email_body', return_value={'truncatedBody': sample_email['body'], 'isTruncated': False}), \
         patch('src.main_loop.get_max_truncation_length', return_value=4000):
        
        result = process_email_with_ai(sample_email, mock_client, mock_config)
        assert result == 'urgent, important'


def test_process_email_with_ai_handles_api_error(mock_config, sample_email):
    """Test process_email_with_ai handles API errors gracefully"""
    mock_client = Mock()
    
    from src.openrouter_client import OpenRouterAPIError
    
    with patch('src.main_loop.send_email_prompt_for_keywords', side_effect=OpenRouterAPIError("API Error")), \
         patch('src.main_loop.truncate_email_body', return_value={'truncatedBody': sample_email['body'], 'isTruncated': False}), \
         patch('src.main_loop.get_max_truncation_length', return_value=4000), \
         patch('time.sleep'):  # Mock sleep to speed up test
        
        result = process_email_with_ai(sample_email, mock_client, mock_config, max_retries=2)
        assert result is None


def test_process_email_with_ai_handles_rate_limit(mock_config, sample_email):
    """Test process_email_with_ai handles rate limiting"""
    mock_client = Mock()
    
    from src.openrouter_client import OpenRouterAPIError
    
    # First call fails with rate limit, second succeeds
    mock_response = {
        'choices': [{
            'message': {
                'content': 'neutral'
            }
        }]
    }
    
    with patch('src.main_loop.send_email_prompt_for_keywords', side_effect=[
        OpenRouterAPIError("Rate limit"),
        mock_response
    ]), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', return_value=['neutral']), \
         patch('src.main_loop.truncate_email_body', return_value={'truncatedBody': sample_email['body'], 'isTruncated': False}), \
         patch('src.main_loop.get_max_truncation_length', return_value=4000), \
         patch('time.sleep'):  # Mock sleep
        
        result = process_email_with_ai(sample_email, mock_client, mock_config, max_retries=3)
        assert result == 'neutral'


def test_run_email_processing_loop_fetches_emails(mock_config):
    """Test main loop fetches emails using config"""
    mock_emails = [
        {'id': b'1', 'subject': 'Test 1', 'body': 'Body 1', 'sender': 'test@example.com'}
    ]
    
    with patch('src.main_loop.fetch_emails', return_value=mock_emails), \
         patch('src.main_loop.OpenRouterClient'), \
         patch.object(mock_config, 'get_imap_query', return_value='UNSEEN'), \
         patch('src.main_loop.process_email_with_ai', return_value='urgent'), \
         patch('src.main_loop.safe_imap_operation'), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={'success': True, 'keyword': 'urgent'}):
        
        result = run_email_processing_loop(mock_config, single_run=True)
        assert result['total_fetched'] == 1


def test_run_email_processing_loop_processes_each_email(mock_config):
    """Test main loop processes each fetched email"""
    mock_emails = [
        {'id': b'1', 'subject': 'Test 1', 'body': 'Body 1', 'sender': 'test@example.com'},
        {'id': b'2', 'subject': 'Test 2', 'body': 'Body 2', 'sender': 'test@example.com'}
    ]
    
    with patch('src.main_loop.fetch_emails', return_value=mock_emails), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.imap_connection.load_imap_queries', return_value=['UNSEEN']), \
         patch('src.main_loop.process_email_with_ai', return_value='urgent') as mock_process, \
         patch('src.main_loop.safe_imap_operation'), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={'success': True, 'keyword': 'urgent'}):
        
        result = run_email_processing_loop(mock_config, single_run=True)
        assert mock_process.call_count == 2
        assert result['successfully_processed'] == 2


def test_run_email_processing_loop_handles_failed_email(mock_config):
    """Test main loop continues when one email fails"""
    mock_emails = [
        {'id': b'1', 'subject': 'Test 1', 'body': 'Body 1', 'sender': 'test@example.com'},
        {'id': b'2', 'subject': 'Test 2', 'body': 'Body 2', 'sender': 'test@example.com'}
    ]
    
    # First email succeeds, second fails
    def mock_process(email, client, config):
        if email['id'] == b'1':
            return 'urgent'
        return None
    
    with patch('src.main_loop.fetch_emails', return_value=mock_emails), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.imap_connection.load_imap_queries', return_value=['UNSEEN']), \
         patch('src.main_loop.process_email_with_ai', side_effect=mock_process), \
         patch('src.main_loop.safe_imap_operation'), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={'success': True, 'keyword': 'urgent'}), \
         patch('src.imap_connection.add_tags_to_email', return_value=True):
        
        result = run_email_processing_loop(mock_config, single_run=True)
        assert result['successfully_processed'] == 1
        assert result['failed'] == 1


def test_run_email_processing_loop_respects_max_emails(mock_config):
    """Test main loop respects max_emails_per_run config"""
    # Create 20 emails but max is 10
    mock_emails = [
        {'id': bytes(str(i), 'utf-8'), 'subject': f'Test {i}', 'body': f'Body {i}', 'sender': 'test@example.com'}
        for i in range(20)
    ]
    
    with patch('src.main_loop.fetch_emails', return_value=mock_emails), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.imap_connection.load_imap_queries', return_value=['UNSEEN']), \
         patch('src.main_loop.process_email_with_ai', return_value='urgent') as mock_process, \
         patch('src.main_loop.safe_imap_operation'), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={'success': True, 'keyword': 'urgent'}):
        
        result = run_email_processing_loop(mock_config, single_run=True, max_emails=10)
        assert mock_process.call_count == 10
        assert result['total_fetched'] == 10  # Processed 10 (limited)
        assert result.get('total_available', result['total_fetched']) == 20  # But 20 were available
        assert result.get('remaining_unprocessed', 0) == 10  # 10 remain unprocessed


def test_generate_analytics_summary_counts_emails():
    """Test analytics summary counts processed emails correctly"""
    analytics = {
        'run_id': '2026-01-05T00:00:00',
        'total_fetched': 10,
        'successfully_processed': 8,
        'failed': 2,
        'tag_breakdown': {},
        'errors': []
    }
    
    summary = generate_analytics_summary(analytics)
    assert summary['total'] == 10
    assert summary['successfully_processed'] == 8
    assert summary['failed'] == 2


def test_generate_analytics_summary_tracks_tags():
    """Test analytics summary tracks tag breakdown"""
    analytics = {
        'run_id': '2026-01-05T00:00:00',
        'total_fetched': 10,
        'successfully_processed': 8,
        'failed': 2,
        'tag_breakdown': {
            'urgent': 3,
            'neutral': 4,
            'spam': 1
        },
        'errors': []
    }
    
    summary = generate_analytics_summary(analytics)
    assert summary['tags']['urgent'] == 3
    assert summary['tags']['neutral'] == 4
    assert summary['tags']['spam'] == 1


def test_run_email_processing_loop_respects_limit_across_batches(mock_config):
    """Test main loop respects max_emails limit across multiple batches in continuous mode"""
    # First batch: 8 emails, second batch: 5 emails, but limit is 10 total
    batch1 = [
        {'id': bytes(str(i), 'utf-8'), 'subject': f'Test {i}', 'body': f'Body {i}', 'sender': 'test@example.com'}
        for i in range(8)
    ]
    batch2 = [
        {'id': bytes(str(i+8), 'utf-8'), 'subject': f'Test {i+8}', 'body': f'Body {i+8}', 'sender': 'test@example.com'}
        for i in range(5)
    ]
    
    fetch_call_count = 0
    def mock_fetch(*args, **kwargs):
        nonlocal fetch_call_count
        fetch_call_count += 1
        if fetch_call_count == 1:
            return batch1
        elif fetch_call_count == 2:
            return batch2
        else:
            return []  # No more emails
    
    with patch('src.main_loop.fetch_emails', side_effect=mock_fetch), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.imap_connection.load_imap_queries', return_value=['UNSEEN']), \
         patch('src.main_loop.process_email_with_ai', return_value='urgent') as mock_process, \
         patch('src.main_loop.safe_imap_operation'), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={'success': True, 'keyword': 'urgent'}):
        
        result = run_email_processing_loop(mock_config, single_run=False, max_emails=10)
        # Should process 8 from first batch + 2 from second batch = 10 total
        assert mock_process.call_count == 10
        assert result['total_fetched'] == 10
        assert result['total_available'] == 13  # 8 + 5
        assert result['remaining_unprocessed'] == 3  # 5 - 2 = 3 remaining in second batch


def test_generate_analytics_summary_calculates_success_rate():
    """Test analytics summary calculates success rate"""
    analytics = {
        'run_id': '2026-01-05T00:00:00',
        'total_fetched': 10,
        'successfully_processed': 8,
        'failed': 2,
        'tag_breakdown': {},
        'errors': []
    }
    
    summary = generate_analytics_summary(analytics)
    assert summary['success_rate'] == 80.0
    
    # Test edge case: no emails
    analytics_empty = {
        'run_id': '2026-01-05T00:00:00',
        'total_fetched': 0,
        'successfully_processed': 0,
        'failed': 0,
        'tag_breakdown': {},
        'errors': []
    }
    summary_empty = generate_analytics_summary(analytics_empty)
    assert summary_empty['success_rate'] == 0.0
