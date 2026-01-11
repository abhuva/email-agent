"""
Tests for V4 Logging Context Module

Tests the context management system for enhanced logging including:
- Context storage and retrieval
- Context propagation
- Context clearing
- Context manager usage
"""
import pytest
import threading
from src.logging_context import (
    get_logging_context,
    set_account_context,
    set_correlation_id,
    set_account_id,
    clear_context,
    with_account_context,
    with_correlation_id
)


def test_get_logging_context_defaults():
    """Test that get_logging_context returns default values when no context is set."""
    clear_context()
    context = get_logging_context()
    
    # Should return empty dict or minimal defaults
    assert isinstance(context, dict)


def test_set_correlation_id():
    """Test setting correlation ID."""
    clear_context()
    set_correlation_id('test-123')
    
    context = get_logging_context()
    assert context.get('correlation_id') == 'test-123'


def test_set_account_id():
    """Test setting account ID."""
    clear_context()
    set_account_id('work')
    
    context = get_logging_context()
    assert context.get('account_id') == 'work'


def test_set_account_context():
    """Test setting multiple context fields at once."""
    clear_context()
    set_account_context(
        account_id='work',
        correlation_id='abc-123',
        job_id='job-001',
        environment='development'
    )
    
    context = get_logging_context()
    assert context.get('account_id') == 'work'
    assert context.get('correlation_id') == 'abc-123'
    assert context.get('job_id') == 'job-001'
    assert context.get('environment') == 'development'


def test_clear_context():
    """Test that clear_context removes all context."""
    set_account_context(account_id='work', correlation_id='abc-123')
    clear_context()
    
    context = get_logging_context()
    # Context should be empty or have minimal defaults
    assert context.get('account_id') is None or context.get('account_id') == 'N/A'


def test_with_account_context():
    """Test context manager for account context."""
    clear_context()
    
    with with_account_context(account_id='work', correlation_id='test-123'):
        context = get_logging_context()
        assert context.get('account_id') == 'work'
        assert context.get('correlation_id') == 'test-123'
    
    # Context should be cleared after context manager exits (since we started with empty context)
    context = get_logging_context()
    # After clearing, context should be empty or have minimal defaults
    assert context.get('account_id') is None or context.get('account_id') not in ['work', 'test-123']


def test_with_account_context_restores_old_context():
    """Test that context manager restores previous context."""
    clear_context()
    set_account_context(account_id='old', correlation_id='old-123')
    
    with with_account_context(account_id='new', correlation_id='new-123'):
        context = get_logging_context()
        assert context.get('account_id') == 'new'
        assert context.get('correlation_id') == 'new-123'
    
    # Should restore old context
    context = get_logging_context()
    assert context.get('account_id') == 'old'
    assert context.get('correlation_id') == 'old-123'


def test_with_correlation_id():
    """Test context manager for correlation ID only."""
    clear_context()
    
    with with_correlation_id('test-456'):
        context = get_logging_context()
        assert context.get('correlation_id') == 'test-456'
    
    # Should be cleared after exit
    context = get_logging_context()
    assert context.get('correlation_id') is None or context.get('correlation_id') == 'N/A'


def test_context_thread_isolation():
    """Test that context is isolated between threads."""
    clear_context()
    set_account_context(account_id='main-thread')
    
    thread_context = {}
    
    def thread_func():
        set_account_context(account_id='thread-1')
        thread_context['account_id'] = get_logging_context().get('account_id')
    
    thread = threading.Thread(target=thread_func)
    thread.start()
    thread.join()
    
    # Thread should have its own context
    assert thread_context.get('account_id') == 'thread-1'
    
    # Main thread context should be unchanged
    context = get_logging_context()
    assert context.get('account_id') == 'main-thread'


def test_context_partial_update():
    """Test that setting partial context doesn't clear other fields."""
    clear_context()
    set_account_context(account_id='work', correlation_id='abc-123')
    
    # Update only account_id
    set_account_id('personal')
    
    context = get_logging_context()
    assert context.get('account_id') == 'personal'
    assert context.get('correlation_id') == 'abc-123'  # Should still be set
