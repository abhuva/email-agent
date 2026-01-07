"""
Tests for Obsidian note assembly and formatting.
"""

import pytest
from src.obsidian_note_assembly import (
    format_yaml_frontmatter,
    format_summary_callout,
    format_original_content,
    assemble_obsidian_note
)


class TestFormatYamlFrontmatter:
    """Tests for format_yaml_frontmatter function."""
    
    def test_formats_valid_yaml_data(self):
        """Test formatting of valid YAML data."""
        data = {'subject': 'Test Email', 'from': 'test@example.com'}
        frontmatter = format_yaml_frontmatter(data)
        
        assert frontmatter.startswith('---')
        assert frontmatter.endswith('---\n')
        assert 'subject' in frontmatter
        assert 'Test Email' in frontmatter
    
    def test_handles_empty_dict(self):
        """Test handling of empty dictionary."""
        frontmatter = format_yaml_frontmatter({})
        
        assert frontmatter == "---\n---\n"
    
    def test_handles_none(self):
        """Test handling of None input."""
        frontmatter = format_yaml_frontmatter(None)
        
        assert frontmatter == "---\n---\n"
    
    def test_handles_non_dict_input(self):
        """Test handling of non-dict input."""
        frontmatter = format_yaml_frontmatter("not a dict")
        
        assert frontmatter == "---\n---\n"
    
    def test_preserves_yaml_structure(self):
        """Test that YAML structure is preserved."""
        data = {
            'subject': 'Test',
            'from': 'test@example.com',
            'to': ['user1@example.com', 'user2@example.com'],
            'date': '2024-01-01'
        }
        frontmatter = format_yaml_frontmatter(data)
        
        assert 'subject' in frontmatter
        assert 'from' in frontmatter
        assert 'to' in frontmatter
        assert '2024-01-01' in frontmatter


class TestFormatSummaryCallout:
    """Tests for format_summary_callout function."""
    
    def test_formats_summary_text(self):
        """Test formatting of summary text."""
        summary = "This is a summary of the email."
        callout = format_summary_callout(summary)
        
        assert '[!summary]' in callout
        assert 'Summary' in callout
        assert 'This is a summary' in callout
        assert callout.startswith('>')
    
    def test_returns_empty_for_none(self):
        """Test that None returns empty string."""
        callout = format_summary_callout(None)
        
        assert callout == ''
    
    def test_returns_empty_for_empty_string(self):
        """Test that empty string returns empty string."""
        callout = format_summary_callout("")
        
        assert callout == ''
    
    def test_returns_empty_for_whitespace_only(self):
        """Test that whitespace-only string returns empty string."""
        callout = format_summary_callout("   \n\t  ")
        
        assert callout == ''
    
    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        summary = "  Summary text  "
        callout = format_summary_callout(summary)
        
        assert 'Summary text' in callout
        assert not callout.startswith('> [!summary] Summary\n>   Summary text')
    
    def test_includes_proper_newlines(self):
        """Test that callout has proper newline formatting."""
        summary = "Test summary"
        callout = format_summary_callout(summary)
        
        # Should end with \n\n (blank line after callout)
        assert callout.endswith('\n\n')
        # Should have newline after title
        assert 'Summary\n>' in callout


class TestFormatOriginalContent:
    """Tests for format_original_content function."""
    
    def test_formats_content_with_heading(self):
        """Test formatting of content with heading."""
        content = "Email body content here"
        formatted = format_original_content(content)
        
        assert '# Original Content' in formatted
        assert 'Email body content here' in formatted
    
    def test_handles_empty_content(self):
        """Test handling of empty content."""
        formatted = format_original_content("")
        
        assert '# Original Content' in formatted
        assert formatted == "# Original Content\n\n"
    
    def test_preserves_multiline_content(self):
        """Test that multiline content is preserved."""
        content = "Line 1\nLine 2\nLine 3"
        formatted = format_original_content(content)
        
        assert 'Line 1' in formatted
        assert 'Line 2' in formatted
        assert 'Line 3' in formatted
    
    def test_removes_trailing_newlines(self):
        """Test that trailing newlines are normalized."""
        content = "Content\n\n\n"
        formatted = format_original_content(content)
        
        # Should end with single newline after content
        assert formatted.endswith('\n')
        assert not formatted.endswith('\n\n\n')
    
    def test_includes_proper_spacing(self):
        """Test that proper spacing is included."""
        content = "Test content"
        formatted = format_original_content(content)
        
        # Should have blank line after heading
        assert '# Original Content\n\n' in formatted


class TestAssembleObsidianNote:
    """Tests for assemble_obsidian_note function."""
    
    def test_assembles_note_with_all_sections(self):
        """Test assembling note with frontmatter, summary, and content."""
        yaml_data = {'subject': 'Test', 'from': 'test@example.com'}
        summary = "This is a summary"
        content = "Email body content"
        
        note = assemble_obsidian_note(yaml_data, summary, content)
        
        assert '---' in note  # Frontmatter
        assert '[!summary]' in note  # Summary callout
        assert '# Original Content' in note  # Content heading
        assert 'Email body content' in note
    
    def test_assembles_note_without_summary(self):
        """Test assembling note without summary."""
        yaml_data = {'subject': 'Test', 'from': 'test@example.com'}
        content = "Email body content"
        
        note = assemble_obsidian_note(yaml_data, None, content)
        
        assert '---' in note  # Frontmatter
        assert '[!summary]' not in note  # No summary
        assert '# Original Content' in note  # Content heading
        assert 'Email body content' in note
    
    def test_assembles_note_with_empty_content(self):
        """Test assembling note with empty content."""
        yaml_data = {'subject': 'Test', 'from': 'test@example.com'}
        summary = "Summary here"
        
        note = assemble_obsidian_note(yaml_data, summary, "")
        
        assert '---' in note
        assert '[!summary]' in note
        assert '# Original Content' in note
    
    def test_handles_invalid_yaml_data(self):
        """Test handling of invalid YAML data."""
        note = assemble_obsidian_note("not a dict", "Summary", "Content")
        
        # Should still produce valid note structure
        assert '---' in note
        assert '# Original Content' in note
    
    def test_proper_spacing_between_sections(self):
        """Test that sections have proper spacing."""
        yaml_data = {'subject': 'Test'}
        summary = "Summary"
        content = "Content"
        
        note = assemble_obsidian_note(yaml_data, summary, content)
        
        # Check that there's proper spacing (not too many newlines)
        # Frontmatter should end with ---\n, then one \n before summary
        parts = note.split('---')
        if len(parts) > 1:
            after_frontmatter = parts[1]
            # Should not have excessive newlines
            assert '\n\n\n' not in after_frontmatter[:50]  # Check first part
    
    def test_ends_with_newline(self):
        """Test that note ends with newline."""
        yaml_data = {'subject': 'Test'}
        note = assemble_obsidian_note(yaml_data, None, "Content")
        
        assert note.endswith('\n')
    
    def test_handles_none_content(self):
        """Test handling of None content."""
        yaml_data = {'subject': 'Test'}
        note = assemble_obsidian_note(yaml_data, None, None)
        
        assert '# Original Content' in note
        assert note.endswith('\n')
    
    def test_handles_exceptions_gracefully(self):
        """Test that exceptions are handled gracefully."""
        # This test verifies error handling doesn't crash
        # The function should return a minimal valid note on error
        note = assemble_obsidian_note({}, None, "")
        
        assert isinstance(note, str)
        assert len(note) > 0
        assert '---' in note
    
    def test_complete_note_structure(self):
        """Test complete note structure matches Obsidian requirements."""
        yaml_data = {
            'subject': 'Meeting Tomorrow',
            'from': 'sender@example.com',
            'to': ['recipient@example.com'],
            'cc': [],
            'date': '2024-01-15T10:30:00Z',
            'source_message_id': '<msg123@example.com>'
        }
        summary = "We need to meet at 3pm to discuss the project."
        content = "Hi,\n\nLet's meet tomorrow at 3pm.\n\nBest regards"
        
        note = assemble_obsidian_note(yaml_data, summary, content)
        
        # Verify structure
        assert note.startswith('---')
        assert 'subject: Meeting Tomorrow' in note
        assert '[!summary]' in note
        assert 'We need to meet' in note
        assert '# Original Content' in note
        assert "Let's meet tomorrow" in note
        assert note.endswith('\n')
        
        # Verify sections are in correct order
        frontmatter_end = note.find('---\n', 4)  # Find closing ---
        assert frontmatter_end > 0
        
        # Summary should come after frontmatter
        summary_start = note.find('[!summary]')
        assert summary_start > frontmatter_end
        
        # Content heading should come after summary
        content_start = note.find('# Original Content')
        assert content_start > summary_start
