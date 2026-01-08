"""
Tests for V3 prompt renderer module.
"""
import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.prompt_renderer import (
    PromptRenderer,
    PromptRendererError,
    PromptConfigError,
    PromptTemplateError,
    get_prompt_renderer,
    render_email_prompt
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config(temp_dir):
    """Create a sample prompt configuration file."""
    config = {
        'prompt_template_path': 'config/prompt_v3.md',
        'scoring_criteria': {
            'thresholds': {
                'importance_threshold': 8,
                'spam_threshold': 5
            }
        },
        'prompt_options': {
            'include_thresholds': True
        },
        'template_variables': {
            'defaults': {
                'subject': '[No Subject]',
                'from': '[Unknown Sender]',
                'to': '[Unknown Recipient]',
                'date': '[Unknown Date]',
                'email_content': '[No Content]'
            }
        }
    }
    config_path = os.path.join(temp_dir, 'prompt_config.yaml')
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    return config_path


@pytest.fixture
def sample_template(temp_dir):
    """Create a sample prompt template file."""
    template_content = """# Email Scoring

Analyze this email:

**Subject:** {{subject}}
**From:** {{from}}
**To:** {{to}}
**Date:** {{date}}

**Content:**
{{email_content}}

Return JSON: {"importance_score": <0-10>, "spam_score": <0-10>}
"""
    template_path = os.path.join(temp_dir, 'prompt_v3.md')
    with open(template_path, 'w') as f:
        f.write(template_content)
    return template_path


@pytest.fixture
def sample_template_with_frontmatter(temp_dir):
    """Create a sample prompt template with YAML frontmatter."""
    template_content = """---
title: Test Prompt
version: 3.0
---

# Email Scoring

Analyze this email:

**Subject:** {{subject}}
**From:** {{from}}

**Content:**
{{email_content}}
"""
    template_path = os.path.join(temp_dir, 'prompt_with_frontmatter.md')
    with open(template_path, 'w') as f:
        f.write(template_content)
    return template_path


class TestPromptRenderer:
    """Test cases for PromptRenderer class."""
    
    def test_init_defaults(self):
        """Test renderer initialization with defaults."""
        renderer = PromptRenderer()
        assert renderer._config_path == "config/prompt_config.yaml"
        assert renderer._template_path is None
    
    def test_init_custom_paths(self, temp_dir):
        """Test renderer initialization with custom paths."""
        config_path = os.path.join(temp_dir, 'custom_config.yaml')
        template_path = os.path.join(temp_dir, 'custom_template.md')
        renderer = PromptRenderer(config_path=config_path, template_path=template_path)
        assert renderer._config_path == config_path
        assert renderer._template_path == template_path
    
    def test_load_config_missing_file(self, temp_dir):
        """Test loading config when file doesn't exist (should use defaults)."""
        config_path = os.path.join(temp_dir, 'nonexistent.yaml')
        renderer = PromptRenderer(config_path=config_path)
        config = renderer._load_config()
        assert config is not None
        assert 'scoring_criteria' in config
    
    def test_load_config_invalid_yaml(self, temp_dir):
        """Test loading config with invalid YAML."""
        config_path = os.path.join(temp_dir, 'invalid.yaml')
        with open(config_path, 'w') as f:
            f.write('invalid: yaml: content: [')
        renderer = PromptRenderer(config_path=config_path)
        with pytest.raises(PromptConfigError):
            renderer._load_config()
    
    def test_load_config_valid(self, sample_config):
        """Test loading valid configuration."""
        renderer = PromptRenderer(config_path=sample_config)
        config = renderer._load_config()
        assert config is not None
        assert 'scoring_criteria' in config
        assert 'prompt_options' in config
    
    def test_load_template_missing_file(self):
        """Test loading template when file doesn't exist."""
        renderer = PromptRenderer(template_path='nonexistent.md')
        with pytest.raises(PromptTemplateError):
            renderer._load_template()
    
    def test_load_template_valid(self, sample_template):
        """Test loading valid template."""
        renderer = PromptRenderer(template_path=sample_template)
        template = renderer._load_template()
        assert template is not None
    
    def test_load_template_with_frontmatter(self, sample_template_with_frontmatter):
        """Test loading template with YAML frontmatter (should skip frontmatter)."""
        renderer = PromptRenderer(template_path=sample_template_with_frontmatter)
        template = renderer._load_template()
        assert template is not None
        # Template should not contain frontmatter markers
        rendered = template.render(subject="Test", from_addr="test@example.com", 
                                  email_content="Test content")
        assert '---' not in rendered or rendered.count('---') < 2
    
    @patch('src.prompt_renderer.settings')
    def test_get_template_variables(self, mock_settings, sample_config):
        """Test template variable preparation."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        renderer = PromptRenderer(config_path=sample_config)
        email_data = {
            'subject': 'Test Subject',
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'date': '2026-01-15T10:00:00Z',
            'email_content': 'Test email content'
        }
        vars = renderer._get_template_variables(email_data)
        assert vars['subject'] == 'Test Subject'
        assert vars['from'] == 'sender@example.com'
        assert vars['to'] == 'recipient@example.com'
        assert vars['date'] == '2026-01-15T10:00:00Z'
        assert vars['email_content'] == 'Test email content'
    
    @patch('src.prompt_renderer.settings')
    def test_get_template_variables_with_defaults(self, mock_settings, sample_config):
        """Test template variables with missing data (should use defaults)."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        renderer = PromptRenderer(config_path=sample_config)
        email_data = {}  # Empty data
        vars = renderer._get_template_variables(email_data)
        assert vars['subject'] == '[No Subject]'
        assert vars['from'] == '[Unknown Sender]'
        assert vars['to'] == '[Unknown Recipient]'
        assert vars['date'] == '[Unknown Date]'
        assert vars['email_content'] == '[No Content]'
    
    @patch('src.prompt_renderer.settings')
    def test_render_prompt(self, mock_settings, sample_template):
        """Test rendering prompt with email data."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        renderer = PromptRenderer(template_path=sample_template)
        email_data = {
            'subject': 'Test Email',
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'date': '2026-01-15T10:00:00Z',
            'email_content': 'This is a test email.'
        }
        prompt = renderer.render_prompt(email_data)
        assert 'Test Email' in prompt
        assert 'sender@example.com' in prompt
        assert 'recipient@example.com' in prompt
        assert 'This is a test email.' in prompt
        assert 'importance_score' in prompt
        assert 'spam_score' in prompt
    
    @patch('src.prompt_renderer.settings')
    def test_render_prompt_with_kwargs(self, mock_settings, sample_template):
        """Test rendering prompt with keyword arguments."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        renderer = PromptRenderer(template_path=sample_template)
        prompt = renderer.render_prompt(
            email_data={},
            subject='Test Subject',
            from_addr='sender@example.com',
            email_content='Test content'
        )
        assert 'Test Subject' in prompt
        assert 'sender@example.com' in prompt
        assert 'Test content' in prompt
    
    @patch('src.prompt_renderer.settings')
    def test_render_prompt_kwargs_override(self, mock_settings, sample_template):
        """Test that kwargs override email_data values."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        renderer = PromptRenderer(template_path=sample_template)
        email_data = {'subject': 'Original Subject'}
        prompt = renderer.render_prompt(email_data, subject='Override Subject')
        assert 'Override Subject' in prompt
        assert 'Original Subject' not in prompt
    
    def test_get_config(self, sample_config):
        """Test getting configuration."""
        renderer = PromptRenderer(config_path=sample_config)
        config = renderer.get_config()
        assert config is not None
        assert 'scoring_criteria' in config
    
    def test_reload_config(self, sample_config):
        """Test reloading configuration."""
        renderer = PromptRenderer(config_path=sample_config)
        config1 = renderer.get_config()
        renderer.reload_config()
        config2 = renderer.get_config()
        # Should reload (config objects may be different)
        assert config1 is not None
        assert config2 is not None
    
    def test_reload_template(self, sample_template):
        """Test reloading template."""
        renderer = PromptRenderer(template_path=sample_template)
        template1 = renderer._load_template()
        renderer.reload_template()
        template2 = renderer._load_template()
        # Should reload (template objects may be different)
        assert template1 is not None
        assert template2 is not None


class TestPromptRendererConvenience:
    """Test convenience functions."""
    
    def test_get_prompt_renderer_singleton(self):
        """Test that get_prompt_renderer returns singleton."""
        renderer1 = get_prompt_renderer()
        renderer2 = get_prompt_renderer()
        assert renderer1 is renderer2
    
    @patch('src.prompt_renderer.settings')
    def test_render_email_prompt(self, mock_settings, sample_template, monkeypatch):
        """Test render_email_prompt convenience function."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        # Mock the default renderer to use our test template
        def mock_get_renderer():
            return PromptRenderer(template_path=sample_template)
        monkeypatch.setattr('src.prompt_renderer.get_prompt_renderer', mock_get_renderer)
        
        email_data = {
            'subject': 'Test',
            'from': 'test@example.com',
            'email_content': 'Test content'
        }
        prompt = render_email_prompt(email_data)
        assert 'Test' in prompt
        assert 'test@example.com' in prompt
        assert 'Test content' in prompt


class TestPromptRendererIntegration:
    """Integration tests for prompt renderer."""
    
    @patch('src.prompt_renderer.settings')
    def test_full_workflow(self, mock_settings, temp_dir, sample_config, sample_template):
        """Test complete workflow: load config, load template, render prompt."""
        # Mock settings to avoid loading main config
        mock_settings.get_importance_threshold.return_value = 8
        mock_settings.get_spam_threshold.return_value = 5
        
        # Update config to point to template
        config = yaml.safe_load(open(sample_config))
        config['prompt_template_path'] = sample_template
        with open(sample_config, 'w') as f:
            yaml.dump(config, f)
        
        renderer = PromptRenderer(config_path=sample_config)
        email_data = {
            'subject': 'Integration Test',
            'from': 'integration@test.com',
            'to': 'recipient@test.com',
            'date': '2026-01-15T12:00:00Z',
            'email_content': 'This is an integration test email.'
        }
        prompt = renderer.render_prompt(email_data)
        
        # Verify all components are present
        assert 'Integration Test' in prompt
        assert 'integration@test.com' in prompt
        assert 'recipient@test.com' in prompt
        assert 'This is an integration test email.' in prompt
        assert 'importance_score' in prompt
        assert 'spam_score' in prompt
