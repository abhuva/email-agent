"""
Tests for configurable IMAP query builder (Task 16).
"""

import pytest
from src.imap_connection import build_imap_query_with_exclusions


def test_build_imap_query_with_exclusions_basic():
    """Test basic query building with exclude tags"""
    result = build_imap_query_with_exclusions('UNSEEN', ['AIProcessed', 'ObsidianNoteCreated'])
    expected = '(UNSEEN NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated")'
    assert result == expected


def test_build_imap_query_with_exclusions_single_tag():
    """Test query building with single exclude tag"""
    result = build_imap_query_with_exclusions('UNSEEN', ['AIProcessed'])
    expected = '(UNSEEN NOT KEYWORD "AIProcessed")'
    assert result == expected


def test_build_imap_query_with_exclusions_three_tags():
    """Test query building with three exclude tags (default behavior)"""
    result = build_imap_query_with_exclusions(
        'UNSEEN',
        ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed']
    )
    expected = '(UNSEEN NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated" NOT KEYWORD "NoteCreationFailed")'
    assert result == expected


def test_build_imap_query_with_exclusions_empty_tags():
    """Test query building with empty exclude tags list"""
    result = build_imap_query_with_exclusions('UNSEEN', [])
    assert result == 'UNSEEN'


def test_build_imap_query_with_exclusions_disable_idempotency():
    """Test query building when idempotency is disabled"""
    result = build_imap_query_with_exclusions(
        'UNSEEN',
        ['AIProcessed', 'ObsidianNoteCreated'],
        disable_idempotency=True
    )
    assert result == 'UNSEEN'


def test_build_imap_query_with_exclusions_complex_query():
    """Test query building with complex user query"""
    user_query = 'UNSEEN SENTSINCE 01-Jan-2026'
    result = build_imap_query_with_exclusions(
        user_query,
        ['AIProcessed', 'ObsidianNoteCreated']
    )
    expected = f'({user_query} NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated")'
    assert result == expected


def test_build_imap_query_with_exclusions_custom_tags():
    """Test query building with custom exclusion tags"""
    result = build_imap_query_with_exclusions(
        'UNSEEN',
        ['AIProcessed', 'CustomTag', 'Archived']
    )
    expected = '(UNSEEN NOT KEYWORD "AIProcessed" NOT KEYWORD "CustomTag" NOT KEYWORD "Archived")'
    assert result == expected


def test_build_imap_query_with_exclusions_many_tags():
    """Test query building with many exclusion tags (performance test)"""
    tags = [f'Tag{i}' for i in range(10)]
    result = build_imap_query_with_exclusions('UNSEEN', tags)
    
    # Verify all tags are included
    for tag in tags:
        assert f'NOT KEYWORD "{tag}"' in result
    
    # Verify query structure
    assert result.startswith('(UNSEEN')
    assert result.endswith(')')
    assert result.count('NOT KEYWORD') == len(tags)


def test_build_imap_query_with_exclusions_all_flag():
    """Test query building with ALL query"""
    result = build_imap_query_with_exclusions('ALL', ['AIProcessed'])
    expected = '(ALL NOT KEYWORD "AIProcessed")'
    assert result == expected


def test_build_imap_query_with_exclusions_from_query():
    """Test query building with FROM query"""
    result = build_imap_query_with_exclusions(
        'FROM "sender@example.com"',
        ['AIProcessed', 'ObsidianNoteCreated']
    )
    expected = '(FROM "sender@example.com" NOT KEYWORD "AIProcessed" NOT KEYWORD "ObsidianNoteCreated")'
    assert result == expected
