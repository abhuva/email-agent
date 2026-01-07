"""
Integration tests for complete V2 email processing workflow.

Tests the end-to-end workflow from email selection to note creation,
including summarization, tagging, changelog, and analytics.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict, Any
import json
import os

from src.main_loop import run_email_processing_loop
from src.config import ConfigManager


class MockIMAPConnection:
    """Mock IMAP connection for integration testing"""
    def __init__(self, emails: List[Dict[str, Any]] = None, simulate_failures: bool = False):
        self.emails = emails or []
        self.simulate_failures = simulate_failures
        self.uid_calls = []
        self.selected_mailbox = 'INBOX'
        self.flags_by_uid = {}  # Track flags per UID
        
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        return False
        
    def select(self, mailbox):
        self.selected_mailbox = mailbox
        return ('OK', [b'1'])
    
    def uid(self, operation, *args):
        self.uid_calls.append((operation, args))
        
        if operation == 'SEARCH':
            # Return UIDs of all emails
            uids = [str(email.get('id', i)).encode() if isinstance(email.get('id'), (int, str)) else email.get('id', bytes(str(i), 'utf-8'))
                   for i, email in enumerate(self.emails, 1)]
            return ('OK', [b' '.join(uids)])
        
        elif operation == 'FETCH':
            uid = args[0]
            # Find email by UID
            email = next((e for e in self.emails if str(e.get('id', '')) == str(uid)), None)
            if not email:
                return ('OK', [b''])
            
            # Return flags
            flags = self.flags_by_uid.get(str(uid), ['\\Seen'])
            flags_str = ' '.join(flags)
            return ('OK', [f'{uid} (FLAGS ({flags_str}))'.encode()])
        
        elif operation == 'STORE':
            uid = str(args[0])
            flags_silent = args[1]
            tagset = args[2] if len(args) > 2 else ''
            
            # Parse tagset to get tags
            if tagset:
                # Extract tags from tagset (e.g., "+FLAGS (Tag1 Tag2)")
                import re
                tags = re.findall(r'\(([^)]+)\)', tagset)
                if tags:
                    new_tags = tags[0].split()
                    current_flags = self.flags_by_uid.get(uid, ['\\Seen'])
                    self.flags_by_uid[uid] = list(set(current_flags + new_tags))
            
            if self.simulate_failures:
                return ('NO', [b'STORE failed'])
            return ('OK', [b'1 STORED'])
        
        return ('OK', [b''])
    
    def logout(self):
        return ('OK', [b'Bye'])


@pytest.fixture
def temp_vault_dir(tmp_path):
    """Create a temporary Obsidian vault directory"""
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir()
    return str(vault_dir)


@pytest.fixture
def temp_changelog_file(tmp_path):
    """Create a temporary changelog file path"""
    changelog_file = tmp_path / "changelog.md"
    return str(changelog_file)


@pytest.fixture
def temp_analytics_file(tmp_path):
    """Create a temporary analytics file path"""
    analytics_file = tmp_path / "analytics.jsonl"
    return str(analytics_file)


@pytest.fixture
def v2_config_with_obsidian(tmp_path, temp_vault_dir, temp_changelog_file, temp_analytics_file):
    """Create a V2 config with Obsidian integration enabled"""
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    
    # Create config file
    config_content = f"""
imap:
  server: 'test.imap.com'
  port: 993
  username: 'test@example.com'
  password_env: 'IMAP_PASSWORD'
prompt_file: 'config/prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'
processed_tag: 'AIProcessed'
max_body_chars: 4000
max_emails_per_run: 10
log_file: '{tmp_path / "test.log"}'
log_level: 'INFO'
analytics_file: '{temp_analytics_file}'
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://test.api'
  model: 'test-model'
obsidian_vault_path: '{temp_vault_dir}'
summarization_tags:
  - 'Urgent'
summarization_prompt_path: 'config/summarization_prompt.md'
changelog_path: '{temp_changelog_file}'
imap_query: 'UNSEEN'
"""
    config_path.write_text(config_content)
    
    # Create env file
    env_content = "IMAP_PASSWORD=testpass\nOPENROUTER_API_KEY=testkey\n"
    env_path.write_text(env_content)
    
    # Create required prompt files
    prompt_dir = tmp_path / "config"
    prompt_dir.mkdir()
    (prompt_dir / "prompt.md").write_text("# Test Prompt")
    (prompt_dir / "summarization_prompt.md").write_text("# Test Summarization Prompt")
    
    return ConfigManager(str(config_path), str(env_path))


@pytest.fixture
def sample_email_urgent():
    """Sample email that should trigger summarization"""
    return {
        'id': b'100',
        'subject': 'Urgent: Action Required',
        'sender': 'boss@company.com',
        'body': 'This is an urgent email that requires immediate attention.',
        'content_type': 'text/plain',
        'date': '2026-01-07T12:00:00Z',
        'to': ['me@example.com'],
        'cc': []
    }


@pytest.fixture
def sample_email_neutral():
    """Sample email that should NOT trigger summarization"""
    return {
        'id': b'200',
        'subject': 'Regular Update',
        'sender': 'newsletter@example.com',
        'body': 'This is a regular email update.',
        'content_type': 'text/plain',
        'date': '2026-01-07T11:00:00Z',
        'to': ['me@example.com'],
        'cc': []
    }


def test_complete_workflow_with_summarization(
    v2_config_with_obsidian,
    temp_vault_dir,
    temp_changelog_file,
    temp_analytics_file,
    sample_email_urgent
):
    """Test complete workflow for email that triggers summarization"""
    # Setup mock IMAP
    mock_imap = MockIMAPConnection(emails=[sample_email_urgent])
    
    # Mock AI responses
    ai_classification_response = {
        'choices': [{'message': {'content': 'urgent'}}]
    }
    summarization_response = {
        'choices': [{
            'message': {
                'content': 'Summary: This is an urgent email requiring immediate action. Action items: Review and respond.'
            }
        }]
    }
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=[sample_email_urgent]), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient') as mock_client_class, \
         patch('src.main_loop.send_email_prompt_for_keywords', return_value=ai_classification_response), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', return_value=['urgent']), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={
             'success': True,
             'keyword': 'urgent',
             'applied_tags': ['Urgent', 'AIProcessed']
         }), \
         patch('src.main_loop.check_summarization_required', return_value={
             'summarize': True,
             'prompt': 'Test prompt'
         }), \
         patch('src.main_loop.generate_email_summary', return_value={
             'success': True,
             'summary': 'This is an urgent email requiring immediate action.',
             'action_items': ['Review and respond'],
             'priority': 'high'
         }), \
         patch('src.main_loop.create_obsidian_note_for_email', return_value={
             'success': True,
             'note_path': f'{temp_vault_dir}/test-note.md'
         }), \
         patch('src.main_loop.tag_email_note_created', return_value=True), \
         patch('src.main_loop.update_changelog', return_value=True):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=1)
        
        # Verify results
        assert result['total_fetched'] == 1
        assert result['successfully_processed'] == 1
        assert result['notes_created'] == 1
        assert result['summaries_generated'] == 1
        assert result['note_creation_failures'] == 0
        assert result['tag_breakdown'].get('urgent', 0) == 1


def test_complete_workflow_without_summarization(
    v2_config_with_obsidian,
    temp_vault_dir,
    sample_email_neutral
):
    """Test complete workflow for email that does NOT trigger summarization"""
    mock_imap = MockIMAPConnection(emails=[sample_email_neutral])
    
    ai_classification_response = {
        'choices': [{'message': {'content': 'neutral'}}]
    }
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=[sample_email_neutral]), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.main_loop.send_email_prompt_for_keywords', return_value=ai_classification_response), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', return_value=['neutral']), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={
             'success': True,
             'keyword': 'neutral',
             'applied_tags': ['Neutral', 'AIProcessed']
         }), \
         patch('src.main_loop.check_summarization_required', return_value={
             'summarize': False,
             'reason': 'no_matching_tags'
         }), \
         patch('src.main_loop.create_obsidian_note_for_email', return_value={
             'success': True,
             'note_path': f'{temp_vault_dir}/test-note.md'
         }), \
         patch('src.main_loop.tag_email_note_created', return_value=True), \
         patch('src.main_loop.update_changelog', return_value=True):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=1)
        
        # Verify results
        assert result['total_fetched'] == 1
        assert result['successfully_processed'] == 1
        assert result['notes_created'] == 1
        assert result['summaries_generated'] == 0  # No summarization
        assert result['note_creation_failures'] == 0
        assert result['tag_breakdown'].get('neutral', 0) == 1


def test_workflow_with_note_creation_failure(
    v2_config_with_obsidian,
    sample_email_urgent
):
    """Test workflow when note creation fails"""
    mock_imap = MockIMAPConnection(emails=[sample_email_urgent])
    
    ai_classification_response = {
        'choices': [{'message': {'content': 'urgent'}}]
    }
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=[sample_email_urgent]), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.main_loop.send_email_prompt_for_keywords', return_value=ai_classification_response), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', return_value=['urgent']), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={
             'success': True,
             'keyword': 'urgent',
             'applied_tags': ['Urgent', 'AIProcessed']
         }), \
         patch('src.main_loop.check_summarization_required', return_value={
             'summarize': False,
             'reason': 'no_matching_tags'
         }), \
         patch('src.main_loop.create_obsidian_note_for_email', return_value={
             'success': False,
             'error': 'Permission denied'
         }), \
         patch('src.main_loop.tag_email_note_failed', return_value=True), \
         patch('src.main_loop.update_changelog', return_value=True):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=1)
        
        # Verify failure is tracked
        assert result['total_fetched'] == 1
        assert result['successfully_processed'] == 1  # AI processing succeeded
        assert result['notes_created'] == 0  # Note creation failed
        assert result['note_creation_failures'] == 1  # Failure tracked


def test_workflow_with_changelog_update(
    v2_config_with_obsidian,
    temp_vault_dir,
    temp_changelog_file,
    sample_email_urgent
):
    """Test that changelog is updated correctly"""
    mock_imap = MockIMAPConnection(emails=[sample_email_urgent])
    
    ai_classification_response = {
        'choices': [{'message': {'content': 'urgent'}}]
    }
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=[sample_email_urgent]), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.main_loop.send_email_prompt_for_keywords', return_value=ai_classification_response), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', return_value=['urgent']), \
         patch('src.main_loop.process_email_with_ai_tags', return_value={
             'success': True,
             'keyword': 'urgent',
             'applied_tags': ['Urgent', 'AIProcessed']
         }), \
         patch('src.main_loop.check_summarization_required', return_value={
             'summarize': False
         }), \
         patch('src.main_loop.create_obsidian_note_for_email', return_value={
             'success': True,
             'note_path': f'{temp_vault_dir}/test-note.md'
         }), \
         patch('src.main_loop.tag_email_note_created', return_value=True):
        
        # Mock changelog update to verify it's called
        with patch('src.main_loop.update_changelog', return_value=True) as mock_changelog_update:
            result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=1)
            
            # Verify changelog was called
            assert mock_changelog_update.called
            call_args = mock_changelog_update.call_args
            assert call_args[1]['path'] == temp_changelog_file
            assert len(call_args[1]['email_list']) == 1


def test_workflow_with_analytics_tracking(
    v2_config_with_obsidian,
    temp_analytics_file,
    sample_email_urgent,
    sample_email_neutral
):
    """Test that analytics are tracked correctly"""
    mock_imap = MockIMAPConnection(emails=[sample_email_urgent, sample_email_neutral])
    
    def mock_ai_response(body, client, max_chars=None, model=None, max_tokens=None):
        # Determine response based on body content or use default
        if 'urgent' in body.lower():
            return {'choices': [{'message': {'content': 'urgent'}}]}
        return {'choices': [{'message': {'content': 'neutral'}}]}
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=[sample_email_urgent, sample_email_neutral]), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.main_loop.send_email_prompt_for_keywords', side_effect=mock_ai_response), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', side_effect=lambda r: ['urgent'] if 'urgent' in str(r) else ['neutral']), \
         patch('src.main_loop.process_email_with_ai_tags', side_effect=lambda *args, **kwargs: {
             'success': True,
             'keyword': 'urgent' if args[2] == 'urgent' else 'neutral',
             'applied_tags': ['Urgent', 'AIProcessed'] if args[2] == 'urgent' else ['Neutral', 'AIProcessed']
         }), \
         patch('src.main_loop.check_summarization_required', side_effect=lambda email, config: {
             'summarize': email.get('id') == sample_email_urgent['id'] and 'Urgent' in email.get('tags', [])
         }), \
         patch('src.main_loop.generate_email_summary', return_value={
             'success': True,
             'summary': 'Test summary'
         }), \
         patch('src.main_loop.create_obsidian_note_for_email', return_value={
             'success': True,
             'note_path': 'test-note.md'
         }), \
         patch('src.main_loop.tag_email_note_created', return_value=True), \
         patch('src.main_loop.update_changelog', return_value=True):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=2)
        
        # Verify analytics
        assert result['total_fetched'] == 2
        assert result['successfully_processed'] == 2
        assert result['notes_created'] == 2
        assert result['summaries_generated'] == 1  # Only urgent email
        assert result['note_creation_failures'] == 0
        assert result['tag_breakdown'].get('urgent', 0) == 1
        assert result['tag_breakdown'].get('neutral', 0) == 1


def test_workflow_handles_imap_failure_gracefully(
    v2_config_with_obsidian,
    sample_email_urgent
):
    """Test that IMAP failures don't crash the workflow"""
    from src.imap_connection import IMAPFetchError
    
    with patch('src.main_loop.fetch_emails', side_effect=IMAPFetchError("IMAP connection failed")), \
         patch('src.main_loop.OpenRouterClient'):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True)
        
        # Should handle gracefully
        assert 'errors' in result
        assert len(result['errors']) > 0
        assert result['total_fetched'] == 0


def test_workflow_handles_llm_api_failure_gracefully(
    v2_config_with_obsidian,
    sample_email_urgent
):
    """Test that LLM API failures are handled gracefully"""
    from src.openrouter_client import OpenRouterAPIError
    
    mock_imap = MockIMAPConnection(emails=[sample_email_urgent])
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=[sample_email_urgent]), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.main_loop.send_email_prompt_for_keywords', side_effect=OpenRouterAPIError("API Error")), \
         patch('src.main_loop.truncate_email_body', return_value={'truncatedBody': 'test', 'isTruncated': False}), \
         patch('src.main_loop.get_max_truncation_length', return_value=4000), \
         patch('src.imap_connection.add_tags_to_email', return_value=True), \
         patch('time.sleep'):  # Speed up test
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=1)
        
        # Should handle gracefully - email marked as failed
        assert result['total_fetched'] == 1
        assert result['failed'] == 1
        assert result['successfully_processed'] == 0


def test_workflow_skips_already_processed_emails(
    v2_config_with_obsidian
):
    """Test that emails with ObsidianNoteCreated tag are skipped"""
    # fetch_emails should return empty list when all emails are already processed
    with patch('src.main_loop.fetch_emails', return_value=[]), \
         patch('src.main_loop.OpenRouterClient'):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True)
        
        # Should find no emails (they're filtered by IMAP query)
        assert result['total_fetched'] == 0


def test_workflow_with_multiple_emails_mixed_results(
    v2_config_with_obsidian,
    temp_vault_dir,
    sample_email_urgent,
    sample_email_neutral
):
    """Test workflow with multiple emails, some succeed, some fail"""
    emails = [sample_email_urgent, sample_email_neutral]
    mock_imap = MockIMAPConnection(emails=emails)
    
    def mock_note_creation(email, config, summary):
        # First email succeeds, second fails
        if email.get('id') == sample_email_urgent['id']:
            return {'success': True, 'note_path': f'{temp_vault_dir}/note1.md'}
        return {'success': False, 'error': 'Write failed'}
    
    ai_responses = [
        {'choices': [{'message': {'content': 'urgent'}}]},
        {'choices': [{'message': {'content': 'neutral'}}]}
    ]
    
    # Create a proper context manager mock
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_imap)
    mock_context.__exit__ = Mock(return_value=False)
    
    with patch('src.main_loop.fetch_emails', return_value=emails), \
         patch('src.main_loop.safe_imap_operation', return_value=mock_context), \
         patch('src.main_loop.OpenRouterClient'), \
         patch('src.main_loop.send_email_prompt_for_keywords', side_effect=ai_responses), \
         patch('src.main_loop.extract_keywords_from_openrouter_response', side_effect=[['urgent'], ['neutral']]), \
         patch('src.main_loop.process_email_with_ai_tags', side_effect=[
             {'success': True, 'keyword': 'urgent', 'applied_tags': ['Urgent', 'AIProcessed']},
             {'success': True, 'keyword': 'neutral', 'applied_tags': ['Neutral', 'AIProcessed']}
         ]), \
         patch('src.main_loop.check_summarization_required', return_value={'summarize': False}), \
         patch('src.main_loop.create_obsidian_note_for_email', side_effect=mock_note_creation), \
         patch('src.main_loop.tag_email_note_created', return_value=True), \
         patch('src.main_loop.tag_email_note_failed', return_value=True), \
         patch('src.main_loop.update_changelog', return_value=True):
        
        result = run_email_processing_loop(v2_config_with_obsidian, single_run=True, max_emails=2)
        
        # Verify mixed results
        assert result['total_fetched'] == 2
        assert result['successfully_processed'] == 2  # Both AI processed successfully
        assert result['notes_created'] == 1  # Only first note created
        assert result['note_creation_failures'] == 1  # Second failed
        assert result['tag_breakdown'].get('urgent', 0) == 1
        assert result['tag_breakdown'].get('neutral', 0) == 1
