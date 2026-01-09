"""
Tests for V3 note generator module.

These tests verify template loading, rendering, and error handling functionality.
"""
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.note_generator import (
    NoteGenerator,
    TemplateLoader,
    TemplateRenderer,
    TemplateLoaderError,
    TemplateRenderError
)
from src.decision_logic import ClassificationResult, ClassificationStatus
from src.config import ConfigError


@pytest.fixture
def temp_template_dir(tmp_path):
    """Create a temporary directory with a template file."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_file = template_dir / "note_template.md.j2"
    template_file.write_text("""---
uid: {{ uid }}
subject: "{{ subject }}"
tags: {{ tags | tojson }}
---
# {{ subject }}

{{ body }}
""")
    return template_dir, template_file


@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return {
        'uid': '12345',
        'subject': 'Test Email',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'date': '2024-01-01T12:00:00Z',
        'body': 'This is a test email body.',
        'html_body': '<p>This is a test email body.</p>',
        'headers': {}
    }


@pytest.fixture
def sample_classification_result():
    """Sample classification result for testing."""
    return ClassificationResult(
        is_important=True,
        is_spam=False,
        importance_score=9,
        spam_score=2,
        confidence=0.85,
        status=ClassificationStatus.SUCCESS,
        raw_scores={'importance_score': 9, 'spam_score': 2},
        metadata={
            'model_used': 'test-model',
            'processed_at': '2024-01-01T12:00:00Z'
        }
    )


@pytest.fixture
def mock_settings():
    """Mock settings facade for testing."""
    with patch('src.note_generator.settings') as mock:
        mock.get_template_file.return_value = 'config/note_template.md.j2'
        mock.get_importance_threshold.return_value = 8
        mock.get_spam_threshold.return_value = 5
        yield mock


class TestTemplateLoader:
    """Tests for TemplateLoader class."""
    
    def test_template_loader_initialization(self, mock_settings, temp_template_dir):
        """Test template loader initialization."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        assert loader.get_template_path() == str(template_file)
        assert loader.get_template_directory() == str(template_dir)
    
    def test_template_exists(self, mock_settings, temp_template_dir):
        """Test template existence check."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        assert loader.template_exists() is True
    
    def test_template_not_exists(self, mock_settings, tmp_path):
        """Test template existence check when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.md.j2"
        mock_settings.get_template_file.return_value = str(non_existent)
        
        loader = TemplateLoader()
        assert loader.template_exists() is False
    
    def test_load_template_content(self, mock_settings, temp_template_dir):
        """Test loading template content."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        content = loader.load_template_content()
        assert 'uid: {{ uid }}' in content
        assert 'subject: "{{ subject }}"' in content
    
    def test_load_template_content_not_found(self, mock_settings, tmp_path):
        """Test loading template when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.md.j2"
        mock_settings.get_template_file.return_value = str(non_existent)
        
        loader = TemplateLoader()
        with pytest.raises(TemplateLoaderError, match="Template file not found"):
            loader.load_template_content()


class TestTemplateRenderer:
    """Tests for TemplateRenderer class."""
    
    def test_renderer_initialization(self, mock_settings, temp_template_dir):
        """Test template renderer initialization."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        assert renderer._loader == loader
        assert renderer._template is not None
    
    def test_renderer_template_not_found(self, mock_settings, tmp_path):
        """Test renderer initialization when template doesn't exist."""
        non_existent = tmp_path / "nonexistent.md.j2"
        mock_settings.get_template_file.return_value = str(non_existent)
        
        loader = TemplateLoader()
        with pytest.raises(TemplateRenderError, match="Template not found"):
            TemplateRenderer(loader)
    
    def test_prepare_context(self, mock_settings, temp_template_dir, sample_email_data, sample_classification_result):
        """Test context preparation."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        
        context = renderer._prepare_context(sample_email_data, sample_classification_result)
        
        assert context['uid'] == '12345'
        assert context['subject'] == 'Test Email'
        assert context['from'] == 'sender@example.com'
        assert context['importance_score'] == 9
        assert context['spam_score'] == 2
        assert context['is_important'] is True
        assert context['is_spam'] is False
        assert 'llm_output' in context
        assert 'processing_meta' in context
        assert 'tags' in context
    
    def test_prepare_context_no_classification(self, mock_settings, temp_template_dir, sample_email_data):
        """Test context preparation without classification result."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        
        context = renderer._prepare_context(sample_email_data, None)
        
        assert context['uid'] == '12345'
        assert context['importance_score'] == -1
        assert context['spam_score'] == -1
        assert context['status'] == 'error'
        assert context['is_important'] is False
        assert context['is_spam'] is False
    
    def test_render(self, mock_settings, temp_template_dir, sample_email_data, sample_classification_result):
        """Test template rendering."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        
        rendered = renderer.render(sample_email_data, sample_classification_result)
        
        assert '12345' in rendered
        assert 'Test Email' in rendered
        assert 'This is a test email body.' in rendered
    
    def test_render_with_invalid_template(self, mock_settings, tmp_path, sample_email_data):
        """Test rendering with invalid template syntax."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "invalid.md.j2"
        template_file.write_text("{{ invalid syntax }")
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        with pytest.raises(TemplateRenderError):
            TemplateRenderer(loader)


class TestNoteGenerator:
    """Tests for NoteGenerator class."""
    
    def test_generator_initialization(self, mock_settings, temp_template_dir):
        """Test note generator initialization."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        generator = NoteGenerator()
        assert generator._loader is not None
        assert generator._renderer is not None
    
    def test_generator_initialization_template_not_found(self, mock_settings, tmp_path):
        """Test generator initialization when template doesn't exist."""
        non_existent = tmp_path / "nonexistent.md.j2"
        mock_settings.get_template_file.return_value = str(non_existent)
        
        generator = NoteGenerator()
        assert generator._loader is not None
        assert generator._renderer is None  # Renderer failed to initialize
    
    def test_generate_note(self, mock_settings, temp_template_dir, sample_email_data, sample_classification_result):
        """Test note generation."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        generator = NoteGenerator()
        note = generator.generate_note(sample_email_data, sample_classification_result)
        
        assert '12345' in note
        assert 'Test Email' in note
        assert 'This is a test email body.' in note
    
    def test_generate_note_no_classification(self, mock_settings, temp_template_dir, sample_email_data):
        """Test note generation without classification result."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        generator = NoteGenerator()
        note = generator.generate_note(sample_email_data, None)
        
        assert '12345' in note
        assert 'Test Email' in note
    
    def test_generate_note_fallback(self, mock_settings, tmp_path, sample_email_data, sample_classification_result):
        """Test note generation with fallback template."""
        # Create generator without valid template
        non_existent = tmp_path / "nonexistent.md.j2"
        mock_settings.get_template_file.return_value = str(non_existent)
        
        generator = NoteGenerator()
        note = generator.generate_note(sample_email_data, sample_classification_result)
        
        # Should use fallback template which includes UID in frontmatter
        # The fallback template includes frontmatter with uid, subject, etc.
        # Check that the note contains the UID (in frontmatter) and subject
        assert '12345' in note, f"UID not found in note: {note[:200]}"
        assert 'Test Email' in note or sample_email_data['subject'] in note
    
    def test_generate_note_error_handling(self, mock_settings, temp_template_dir, sample_email_data):
        """Test error handling in note generation."""
        template_dir, template_file = temp_template_dir
        # Create template with syntax error
        template_file.write_text("{{ invalid syntax }")
        mock_settings.get_template_file.return_value = str(template_file)
        
        generator = NoteGenerator()
        # Should use fallback template when primary fails
        note = generator.generate_note(sample_email_data, None)
        assert 'Test Email' in note  # Fallback should still work


class TestTemplateFilters:
    """Tests for custom Jinja2 filters."""
    
    def test_format_date_filter(self, mock_settings, temp_template_dir):
        """Test date formatting filter."""
        template_dir, template_file = temp_template_dir
        template_file.write_text("{{ date | format_date('%Y-%m-%d') }}")
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        
        email_data = {'uid': '1', 'subject': 'Test', 'from': 'test@example.com', 
                     'to': [], 'date': '2024-01-01T12:00:00Z', 'body': '', 'headers': {}}
        rendered = renderer.render(email_data, None)
        assert '2024-01-01' in rendered
    
    def test_format_datetime_filter(self, mock_settings, temp_template_dir):
        """Test datetime formatting filter."""
        template_dir, template_file = temp_template_dir
        template_file.write_text("{{ date | format_datetime }}")
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        
        email_data = {'uid': '1', 'subject': 'Test', 'from': 'test@example.com',
                     'to': [], 'date': '2024-01-01 12:00:00', 'body': '', 'headers': {}}
        rendered = renderer.render(email_data, None)
        assert '2024-01-01T12:00:00Z' in rendered
    
    def test_truncate_filter(self, mock_settings, temp_template_dir):
        """Test truncate filter."""
        template_dir, template_file = temp_template_dir
        template_file.write_text("{{ body | truncate(10) }}")
        mock_settings.get_template_file.return_value = str(template_file)
        
        loader = TemplateLoader()
        renderer = TemplateRenderer(loader)
        
        email_data = {'uid': '1', 'subject': 'Test', 'from': 'test@example.com',
                     'to': [], 'date': '2024-01-01', 'body': 'This is a very long text', 'headers': {}}
        rendered = renderer.render(email_data, None)
        assert len(rendered.strip()) <= 13  # "This is..." (10 chars + "...")
        assert '...' in rendered


class TestIntegration:
    """Integration tests for full workflow."""
    
    def test_full_workflow(self, mock_settings, temp_template_dir, sample_email_data, sample_classification_result):
        """Test full note generation workflow."""
        template_dir, template_file = temp_template_dir
        mock_settings.get_template_file.return_value = str(template_file)
        
        generator = NoteGenerator()
        note = generator.generate_note(sample_email_data, sample_classification_result)
        
        # Verify frontmatter structure
        assert '---' in note
        assert 'uid: 12345' in note
        assert 'subject: "Test Email"' in note
        assert 'tags:' in note
        
        # Verify body content
        assert '# Test Email' in note
        assert 'This is a test email body.' in note
    
    def test_frontmatter_structure(self, mock_settings, temp_template_dir, sample_email_data, sample_classification_result):
        """Test that frontmatter matches PDD Section 3.2 specification."""
        template_dir, template_file = temp_template_dir
        # Use a template that matches PDD spec
        template_file.write_text("""---
uid: {{ uid }}
subject: "{{ subject }}"
from: "{{ from }}"
to: {{ to | tojson }}
date: "{{ date | format_datetime }}"
tags: {{ tags | tojson }}
llm_output:
  importance_score: {{ importance_score }}
  spam_score: {{ spam_score }}
  model_used: "{{ llm_output.model_used }}"
processing_meta:
  script_version: "3.0"
  processed_at: "{{ processing_meta.processed_at }}"
  status: "{{ status }}"
---
# {{ subject }}
""")
        mock_settings.get_template_file.return_value = str(template_file)
        
        generator = NoteGenerator()
        note = generator.generate_note(sample_email_data, sample_classification_result)
        
        # Verify PDD Section 3.2 structure
        assert 'uid: 12345' in note
        assert 'subject: "Test Email"' in note
        assert 'from: "sender@example.com"' in note
        assert 'llm_output:' in note
        assert 'importance_score: 9' in note
        assert 'spam_score: 2' in note
        assert 'model_used:' in note
        assert 'processing_meta:' in note
        assert 'script_version: "3.0"' in note
        assert 'status: "success"' in note or 'status: success' in note
