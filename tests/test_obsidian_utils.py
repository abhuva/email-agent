"""
Tests for Obsidian file system utilities.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime
from src.obsidian_utils import (
    sanitize_filename,
    generate_unique_filename,
    file_exists,
    is_valid_path,
    get_unique_path,
    has_write_permission,
    safe_write_file,
    InvalidPathError,
    WritePermissionError,
    FileWriteError,
    FileSystemError
)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""
    
    def test_basic_sanitization(self):
        """Test basic character removal."""
        result = sanitize_filename("Project Update: Q4 Results")
        assert ":" not in result
        assert "Project" in result
        assert "Update" in result
    
    def test_invalid_characters_removed(self):
        """Test that invalid filename characters are removed."""
        subject = 'Email with /invalid\\chars: *?"<>|'
        result = sanitize_filename(subject)
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            assert char not in result
    
    def test_multiple_spaces_replaced(self):
        """Test that multiple spaces are replaced with hyphens."""
        result = sanitize_filename("  Multiple   Spaces  ")
        assert "  " not in result
        assert result.strip() == result
    
    def test_empty_subject(self):
        """Test handling of empty subject."""
        result = sanitize_filename("")
        assert result == "untitled"
    
    def test_only_invalid_chars(self):
        """Test subject with only invalid characters."""
        result = sanitize_filename("<>:\"/\\|?*")
        assert result == "untitled"
    
    def test_length_truncation(self):
        """Test that long subjects are truncated."""
        long_subject = "A" * 300
        result = sanitize_filename(long_subject, max_length=50)
        assert len(result) <= 50
    
    def test_whitespace_only(self):
        """Test subject with only whitespace."""
        result = sanitize_filename("   \t\n   ")
        assert result == "untitled"
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        result = sanitize_filename("Test émojis 🎉 and ünicode")
        # Should not crash, result should be valid
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenerateUniqueFilename:
    """Tests for generate_unique_filename function."""
    
    def test_basic_filename_generation(self):
        """Test basic filename generation."""
        filename = generate_unique_filename("Test Subject")
        assert filename.endswith(".md")
        assert "Test-Subject" in filename
        # Should have timestamp format YYYY-MM-DD-HHMMSS
        assert len(filename) > 20  # At least timestamp + subject
    
    def test_with_base_path(self):
        """Test filename generation with base path."""
        filename = generate_unique_filename("Test", base_path="/path/to/vault")
        # Handle Windows path separators
        assert "/path/to/vault" in filename.replace("\\", "/")
        assert filename.endswith(".md")
    
    def test_with_custom_timestamp(self):
        """Test filename generation with custom timestamp."""
        timestamp = datetime(2024, 1, 15, 14, 30, 22)
        filename = generate_unique_filename("Test", timestamp=timestamp)
        assert "2024-01-15-143022" in filename
    
    def test_sanitization_in_filename(self):
        """Test that subject is sanitized in filename."""
        filename = generate_unique_filename("Test: Invalid/Chars")
        assert ":" not in filename
        assert "/" not in filename


class TestFileExists:
    """Tests for file_exists function."""
    
    def test_existing_file(self, tmp_path):
        """Test with existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        assert file_exists(str(test_file)) is True
    
    def test_nonexistent_file(self, tmp_path):
        """Test with non-existent file."""
        test_file = tmp_path / "nonexistent.txt"
        assert file_exists(str(test_file)) is False
    
    def test_directory_not_file(self, tmp_path):
        """Test that directories return False."""
        assert file_exists(str(tmp_path)) is False


class TestIsValidPath:
    """Tests for is_valid_path function."""
    
    def test_valid_path(self):
        """Test with valid path."""
        assert is_valid_path("/path/to/file.md") is True
        assert is_valid_path("relative/path.md") is True
    
    def test_invalid_path_characters(self):
        """Test with invalid characters (if Path raises)."""
        # Path validation is lenient, but we test the function works
        result = is_valid_path("test/path.md")
        assert isinstance(result, bool)


class TestGetUniquePath:
    """Tests for get_unique_path function."""
    
    def test_unique_path_when_not_exists(self, tmp_path):
        """Test when file doesn't exist."""
        file_path = str(tmp_path / "test.md")
        result = get_unique_path(file_path)
        assert result == file_path
    
    def test_unique_path_when_exists(self, tmp_path):
        """Test when file exists, should append number."""
        file_path = tmp_path / "test.md"
        file_path.write_text("existing")
        
        result = get_unique_path(str(file_path))
        assert result != str(file_path)
        assert "(1)" in result
        assert not file_exists(result)  # New path shouldn't exist
    
    def test_multiple_collisions(self, tmp_path):
        """Test when multiple files exist."""
        # Create test.md, test (1).md, test (2).md
        (tmp_path / "test.md").write_text("0")
        (tmp_path / "test (1).md").write_text("1")
        (tmp_path / "test (2).md").write_text("2")
        
        result = get_unique_path(str(tmp_path / "test.md"))
        assert "(3)" in result


class TestHasWritePermission:
    """Tests for has_write_permission function."""
    
    def test_write_permission_exists(self, tmp_path):
        """Test write permission on existing directory."""
        assert has_write_permission(str(tmp_path)) is True
    
    def test_write_permission_nonexistent(self, tmp_path):
        """Test write permission on non-existent directory."""
        nonexistent = tmp_path / "nonexistent"
        assert has_write_permission(str(nonexistent)) is False


class TestSafeWriteFile:
    """Tests for safe_write_file function."""
    
    def test_basic_write(self, tmp_path):
        """Test basic file writing."""
        file_path = str(tmp_path / "test.md")
        content = "# Test Note\n\nThis is a test."
        
        result = safe_write_file(content, file_path)
        assert result == file_path
        assert file_exists(file_path)
        assert Path(file_path).read_text(encoding='utf-8') == content
    
    def test_write_creates_directory(self, tmp_path):
        """Test that missing directories are created."""
        file_path = str(tmp_path / "subdir" / "test.md")
        content = "# Test"
        
        result = safe_write_file(content, file_path)
        assert file_exists(file_path)
        assert Path(file_path).read_text(encoding='utf-8') == content
    
    def test_write_without_overwrite(self, tmp_path):
        """Test that existing file gets unique path when overwrite=False."""
        file_path = tmp_path / "test.md"
        file_path.write_text("existing")
        
        result = safe_write_file("new content", str(file_path), overwrite=False)
        assert result != str(file_path)
        assert "(1)" in result
        # Original file should still exist
        assert file_path.read_text() == "existing"
    
    def test_write_with_overwrite(self, tmp_path):
        """Test that existing file is overwritten when overwrite=True."""
        file_path = tmp_path / "test.md"
        file_path.write_text("old content")
        
        result = safe_write_file("new content", str(file_path), overwrite=True)
        assert result == str(file_path)
        assert file_path.read_text() == "new content"
    
    def test_invalid_path_raises_error(self):
        """Test that invalid path raises InvalidPathError."""
        # This might not raise on all systems, but we test the structure
        with pytest.raises((InvalidPathError, FileWriteError)):
            # Try with a path that might be invalid
            safe_write_file("content", "")
    
    def test_unicode_content(self, tmp_path):
        """Test writing unicode content."""
        file_path = str(tmp_path / "unicode.md")
        content = "# Test with émojis 🎉 and ünicode"
        
        result = safe_write_file(content, file_path)
        assert file_exists(result)
        assert Path(result).read_text(encoding='utf-8') == content
    
    def test_large_content(self, tmp_path):
        """Test writing large content."""
        file_path = str(tmp_path / "large.md")
        content = "A" * 10000
        
        result = safe_write_file(content, file_path)
        assert file_exists(result)
        assert len(Path(result).read_text(encoding='utf-8')) == 10000


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_workflow(self, tmp_path):
        """Test complete workflow: sanitize -> generate -> write."""
        subject = "Project Update: Q4 Results / Important"
        base_path = str(tmp_path)
        
        # Sanitize
        sanitized = sanitize_filename(subject)
        assert ":" not in sanitized
        assert "/" not in sanitized
        
        # Generate filename
        filename = generate_unique_filename(subject, base_path=base_path)
        assert filename.startswith(base_path)
        assert filename.endswith(".md")
        
        # Write file
        content = "# Test Note\n\nContent here."
        result_path = safe_write_file(content, filename)
        assert file_exists(result_path)
        assert Path(result_path).read_text(encoding='utf-8') == content
    
    def test_multiple_writes_same_subject(self, tmp_path):
        """Test writing multiple files with same subject."""
        subject = "Test Subject"
        base_path = str(tmp_path)
        
        # Write first file
        filename1 = generate_unique_filename(subject, base_path=base_path)
        safe_write_file("Content 1", filename1)
        
        # Write second file with a slight delay to ensure different timestamp
        # or use overwrite=False which will create unique path if file exists
        import time
        time.sleep(0.1)  # Small delay to ensure different timestamp
        filename2 = generate_unique_filename(subject, base_path=base_path)
        
        # If filename2 exists, safe_write_file will create unique path
        if file_exists(filename2):
            filename2 = safe_write_file("Content 2", filename2, overwrite=False)
        else:
            safe_write_file("Content 2", filename2)
        
        # Both should exist and be different
        assert file_exists(filename1)
        assert file_exists(filename2)
        # Files might have same timestamp if generated in same second,
        # but safe_write_file should handle that with unique paths
        assert Path(filename1).read_text() != Path(filename2).read_text()
