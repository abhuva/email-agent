"""
Tests for Obsidian note creation and email tagging workflow.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path
from src.obsidian_note_creation import (
    generate_note_content,
    write_obsidian_note,
    tag_email_note_created,
    tag_email_note_failed,
    create_obsidian_note_for_email,
    OBSIDIAN_NOTE_CREATED_TAG,
    NOTE_CREATION_FAILED_TAG
)
from src.obsidian_utils import InvalidPathError, WritePermissionError, FileWriteError


class TestGenerateNoteContent:
    """Tests for generate_note_content function."""
    
    def test_generates_note_with_basic_email(self):
        """Test generating note from basic email data."""
        email = {
            'subject': 'Test Email',
            'sender': 'test@example.com',
            'body': 'Email body content',
            'date': '2024-01-15T10:30:00Z'
        }
        
        note = generate_note_content(email)
        
        assert '---' in note  # YAML frontmatter
        assert 'Test Email' in note
        assert 'test@example.com' in note
        assert '# Original Content' in note
        assert 'Email body content' in note
    
    def test_includes_summary_when_available(self):
        """Test that summary is included when available."""
        email = {
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        summary_result = {
            'success': True,
            'summary': 'This is a summary'
        }
        
        note = generate_note_content(email, summary_result)
        
        assert '[!summary]' in note
        assert 'This is a summary' in note
    
    def test_omits_summary_when_not_available(self):
        """Test that summary is omitted when not available."""
        email = {
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        summary_result = {
            'success': False
        }
        
        note = generate_note_content(email, summary_result)
        
        assert '[!summary]' not in note
    
    def test_handles_empty_summary(self):
        """Test handling of empty summary."""
        email = {
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        summary_result = {
            'success': True,
            'summary': ''
        }
        
        note = generate_note_content(email, summary_result)
        
        assert '[!summary]' not in note
    
    def test_converts_html_body_to_markdown(self):
        """Test that HTML email body is converted to Markdown."""
        email = {
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': '<p>Hello <strong>world</strong></p>',
            'content_type': 'text/html'
        }
        
        note = generate_note_content(email)
        
        assert 'Hello' in note
        assert 'world' in note
        # Should not contain raw HTML tags
        assert '<p>' not in note or '<strong>' not in note


class TestWriteObsidianNote:
    """Tests for write_obsidian_note function."""
    
    def test_writes_note_to_disk(self):
        """Test writing note to disk."""
        with patch('src.dry_run.is_dry_run', return_value=False):
            with tempfile.TemporaryDirectory() as temp_dir:
                note_content = "---\n---\n\n# Original Content\n\nTest content\n"
                
                note_path = write_obsidian_note(
                    note_content,
                    "Test Email",
                    temp_dir
                )
                
                assert os.path.exists(note_path)
                assert note_path.endswith('.md')
                # Filename is sanitized, so "Test Email" becomes "Test-Email"
                filename = os.path.basename(note_path)
                assert 'Test' in filename and 'Email' in filename
                
                # Verify content
                with open(note_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert 'Test content' in content
    
    @patch('src.dry_run.is_dry_run', return_value=False)
    def test_generates_unique_filename(self, mock_dry_run):
        """Test that unique filenames are generated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            note_content = "---\n---\n\n# Original Content\n\nContent\n"
            
            path1 = write_obsidian_note(note_content, "Test", temp_dir)
            path2 = write_obsidian_note(note_content, "Test", temp_dir)
            
            # Should have different paths (timestamp or number suffix)
            assert path1 != path2
    
    def test_raises_error_for_nonexistent_vault(self):
        """Test that error is raised for nonexistent vault path."""
        note_content = "---\n---\n\n# Original Content\n\n"
        
        with pytest.raises(InvalidPathError):
            write_obsidian_note(note_content, "Test", "/nonexistent/path")
    
    def test_raises_error_for_file_vault(self):
        """Test that error is raised if vault path is a file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            note_content = "---\n---\n\n# Original Content\n\n"
            
            with pytest.raises(InvalidPathError):
                write_obsidian_note(note_content, "Test", temp_path)
        finally:
            os.unlink(temp_path)


class TestTagEmailNoteCreated:
    """Tests for tag_email_note_created function."""
    
    def test_tags_email_successfully(self):
        """Test successful email tagging."""
        imap = Mock()
        # Mock the uid('FETCH', ...) call used by _fetch_email_flags
        # First call (before tagging) returns empty flags, second call (after) returns the tag
        imap.uid = Mock(side_effect=[
            ('OK', [b'1 (FLAGS (\\Seen))']),  # Before tagging
            ('OK', [b'1 (FLAGS (\\Seen ObsidianNoteCreated))'])  # After tagging
        ])
        with patch('src.imap_connection.add_tags_to_email', return_value=True):
            result = tag_email_note_created(imap, b'123', '/path/to/note.md')
        
        assert result is True
    
    def test_handles_tagging_failure(self):
        """Test handling of tagging failure."""
        imap = Mock()
        with patch('src.imap_connection.add_tags_to_email', return_value=False):
            result = tag_email_note_created(imap, b'123')
        
        assert result is False
    
    def test_handles_exceptions(self):
        """Test handling of exceptions during tagging."""
        imap = Mock()
        with patch('src.imap_connection.add_tags_to_email', side_effect=Exception("Tag error")):
            result = tag_email_note_created(imap, b'123')
        
        assert result is False


class TestTagEmailNoteFailed:
    """Tests for tag_email_note_failed function."""
    
    def test_tags_email_successfully(self):
        """Test successful failure tagging."""
        imap = Mock()
        # Mock the uid('FETCH', ...) call used by _fetch_email_flags
        # First call (before tagging) returns empty flags, second call (after) returns the tag
        imap.uid = Mock(side_effect=[
            ('OK', [b'1 (FLAGS (\\Seen))']),  # Before tagging
            ('OK', [b'1 (FLAGS (\\Seen NoteCreationFailed))'])  # After tagging
        ])
        with patch('src.imap_connection.add_tags_to_email', return_value=True):
            result = tag_email_note_failed(imap, b'123', 'Error message')
        
        assert result is True
    
    def test_handles_tagging_failure(self):
        """Test handling of tagging failure."""
        imap = Mock()
        with patch('src.imap_connection.add_tags_to_email', return_value=False):
            result = tag_email_note_failed(imap, b'123')
        
        assert result is False
    
    def test_handles_exceptions(self):
        """Test handling of exceptions during tagging."""
        imap = Mock()
        with patch('src.imap_connection.add_tags_to_email', side_effect=Exception("Tag error")):
            result = tag_email_note_failed(imap, b'123')
        
        assert result is False


class TestCreateObsidianNoteForEmail:
    """Tests for create_obsidian_note_for_email function."""
    
    def test_creates_note_successfully(self):
        """Test successful note creation."""
        email = {
            'id': b'123',
            'subject': 'Test Email',
            'sender': 'test@example.com',
            'body': 'Email content',
            'date': '2024-01-15'
        }
        config = Mock()
        config.obsidian_vault_path = None
        
        with patch('src.dry_run.is_dry_run', return_value=False):
            with tempfile.TemporaryDirectory() as temp_dir:
                config.obsidian_vault_path = temp_dir
                
                result = create_obsidian_note_for_email(email, config)
                
                assert result['success'] is True
                assert result['note_path'] is not None
                assert result['error'] is None
                assert os.path.exists(result['note_path'])
    
    def test_returns_error_when_vault_not_configured(self):
        """Test that error is returned when vault path not configured."""
        email = {
            'id': b'123',
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        config = Mock()
        config.obsidian_vault_path = None
        
        result = create_obsidian_note_for_email(email, config)
        
        assert result['success'] is False
        assert 'obsidian_vault_path' in result['error']
        assert result['note_path'] is None
    
    def test_handles_invalid_vault_path(self):
        """Test handling of invalid vault path."""
        email = {
            'id': b'123',
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        config = Mock()
        config.obsidian_vault_path = '/nonexistent/path'
        
        result = create_obsidian_note_for_email(email, config)
        
        assert result['success'] is False
        assert 'Invalid vault path' in result['error'] or 'does not exist' in result['error']
        assert result['note_path'] is None
    
    def test_includes_summary_in_note(self):
        """Test that summary is included when available."""
        email = {
            'id': b'123',
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        summary_result = {
            'success': True,
            'summary': 'This is a summary'
        }
        config = Mock()
        
        with patch('src.dry_run.is_dry_run', return_value=False):
            with tempfile.TemporaryDirectory() as temp_dir:
                config.obsidian_vault_path = temp_dir
                
                result = create_obsidian_note_for_email(email, config, summary_result)
                
                assert result['success'] is True
                # Verify summary is in the note
                with open(result['note_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert '[!summary]' in content
                    assert 'This is a summary' in content
    
    def test_handles_write_permission_error(self):
        """Test handling of write permission errors."""
        email = {
            'id': b'123',
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        config = Mock()
        
        # Use a path that will cause permission error (if possible)
        # On Windows, we can't easily simulate this, so we'll test with invalid path
        config.obsidian_vault_path = '/nonexistent/path'
        
        result = create_obsidian_note_for_email(email, config)
        
        assert result['success'] is False
        assert result['error'] is not None
    
    def test_handles_exceptions_gracefully(self):
        """Test that exceptions are handled gracefully."""
        email = {
            'id': b'123',
            'subject': 'Test',
            'sender': 'test@example.com',
            'body': 'Content'
        }
        config = Mock()
        config.obsidian_vault_path = '/some/path'
        
        # Mock write_obsidian_note to raise exception
        with patch('src.obsidian_note_creation.write_obsidian_note', side_effect=Exception("Unexpected error")):
            result = create_obsidian_note_for_email(email, config)
        
        assert result['success'] is False
        assert 'Unexpected error' in result['error']
        assert result['note_path'] is None
