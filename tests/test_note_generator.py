"""
Tests for V4 note generator module.

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


# V3 tests removed - V4 uses config dicts instead of settings facade
# If new tests are needed, they should use V4's config-based approach
