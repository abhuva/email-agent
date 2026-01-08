"""
V3 Prompt Renderer

This module handles loading and rendering the score-based classification prompt
with configuration integration and template variable substitution.

All configuration access is through the settings.py facade.
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader, select_autoescape

from src.settings import settings
from src.config import ConfigError

logger = logging.getLogger(__name__)


class PromptRendererError(Exception):
    """Base exception for prompt renderer errors."""
    pass


class PromptConfigError(PromptRendererError):
    """Raised when prompt configuration is invalid."""
    pass


class PromptTemplateError(PromptRendererError):
    """Raised when prompt template cannot be loaded or rendered."""
    pass


class PromptRenderer:
    """
    Renders email classification prompts using templates and configuration.
    
    This class:
    1. Loads prompt configuration from YAML
    2. Loads prompt template from markdown file
    3. Substitutes template variables with email data
    4. Returns fully rendered prompt ready for LLM submission
    
    Example:
        renderer = PromptRenderer()
        prompt = renderer.render_prompt(
            subject="Test Email",
            from_addr="sender@example.com",
            to_addr="recipient@example.com",
            date="2026-01-15T10:00:00Z",
            email_content="Email body content..."
        )
    """
    
    def __init__(self, config_path: Optional[str] = None, template_path: Optional[str] = None):
        """
        Initialize prompt renderer.
        
        Args:
            config_path: Path to prompt_config.yaml (defaults to config/prompt_config.yaml)
            template_path: Path to prompt template (defaults to settings.get_prompt_file())
        """
        self._config: Optional[Dict[str, Any]] = None
        self._template: Optional[Template] = None
        self._config_path = config_path or "config/prompt_config.yaml"
        self._template_path = template_path
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load prompt configuration from YAML file.
        
        Returns:
            Configuration dictionary
            
        Raises:
            PromptConfigError: If configuration cannot be loaded or is invalid
        """
        if self._config is not None:
            return self._config
        
        # Try to load config file, but don't require it (use defaults if missing)
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
                logger.info(f"Loaded prompt configuration from {self._config_path}")
            except yaml.YAMLError as e:
                raise PromptConfigError(f"Invalid YAML in prompt config: {e}")
            except Exception as e:
                raise PromptConfigError(f"Failed to load prompt config: {e}")
        else:
            logger.warning(f"Prompt config file not found: {self._config_path}, using defaults")
            self._config = {}
        
        # Validate and set defaults
        self._config.setdefault('scoring_criteria', {})
        self._config.setdefault('prompt_options', {})
        self._config.setdefault('template_variables', {})
        self._config.setdefault('output_format', {})
        
        return self._config
    
    def _load_template(self) -> Template:
        """
        Load prompt template from markdown file.
        
        Returns:
            Jinja2 Template object
            
        Raises:
            PromptTemplateError: If template cannot be loaded
        """
        if self._template is not None:
            return self._template
        
        # Determine template path
        config = self._load_config()
        template_path = self._template_path
        
        if not template_path:
            # Try config first, then fall back to settings
            template_path = config.get('prompt_template_path')
            if not template_path:
                template_path = settings.get_prompt_file()
        
        if not template_path or not os.path.exists(template_path):
            raise PromptTemplateError(f"Prompt template file not found: {template_path}")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Parse frontmatter if present (markdown files may have YAML frontmatter)
            if template_content.startswith('---'):
                parts = template_content.split('---', 2)
                if len(parts) >= 3:
                    # Skip frontmatter, use content
                    template_content = parts[2].strip()
            
            # Create Jinja2 template
            self._template = Template(template_content)
            logger.info(f"Loaded prompt template from {template_path}")
            return self._template
            
        except Exception as e:
            raise PromptTemplateError(f"Failed to load prompt template: {e}")
    
    def _get_template_variables(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare template variables from email data and configuration.
        
        Args:
            email_data: Email data dictionary with subject, from, to, date, email_content
            
        Returns:
            Dictionary of template variables ready for substitution
        """
        config = self._load_config()
        defaults = config.get('template_variables', {}).get('defaults', {})
        
        # Extract email data with defaults
        variables = {
            'subject': email_data.get('subject', defaults.get('subject', '[No Subject]')),
            'from': email_data.get('from', defaults.get('from', '[Unknown Sender]')),
            'to': email_data.get('to', defaults.get('to', '[Unknown Recipient]')),
            'date': email_data.get('date', defaults.get('date', '[Unknown Date]')),
            'email_content': email_data.get('email_content', defaults.get('email_content', '[No Content]'))
        }
        
        # Add threshold information if configured
        if config.get('prompt_options', {}).get('include_thresholds', True):
            try:
                variables['importance_threshold'] = settings.get_importance_threshold()
                variables['spam_threshold'] = settings.get_spam_threshold()
            except (ConfigError, AttributeError):
                # Settings not initialized or config missing, use defaults from config
                thresholds = config.get('scoring_criteria', {}).get('thresholds', {})
                variables['importance_threshold'] = thresholds.get('importance_threshold', 8)
                variables['spam_threshold'] = thresholds.get('spam_threshold', 5)
        
        return variables
    
    def render_prompt(
        self,
        email_data: Dict[str, Any],
        subject: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        date: Optional[str] = None,
        email_content: Optional[str] = None
    ) -> str:
        """
        Render the prompt template with email data.
        
        This method combines the prompt template with email data and configuration
        to generate the final prompt ready for LLM submission.
        
        Args:
            email_data: Dictionary with email data (can contain subject, from, to, date, email_content)
            subject: Email subject (overrides email_data['subject'])
            from_addr: Sender address (overrides email_data['from'])
            to_addr: Recipient address (overrides email_data['to'])
            date: Email date (overrides email_data['date'])
            email_content: Email body content (overrides email_data['email_content'])
            
        Returns:
            Fully rendered prompt string
            
        Raises:
            PromptTemplateError: If template cannot be rendered
        """
        # Prepare email data dictionary
        data = dict(email_data) if email_data else {}
        if subject is not None:
            data['subject'] = subject
        if from_addr is not None:
            data['from'] = from_addr
        if to_addr is not None:
            data['to'] = to_addr
        if date is not None:
            data['date'] = date
        if email_content is not None:
            data['email_content'] = email_content
        
        # Get template variables
        template_vars = self._get_template_variables(data)
        
        # Load and render template
        template = self._load_template()
        
        try:
            rendered = template.render(**template_vars)
            logger.debug("Successfully rendered prompt template")
            return rendered
        except Exception as e:
            raise PromptTemplateError(f"Failed to render prompt template: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the loaded prompt configuration.
        
        Returns:
            Configuration dictionary
        """
        return self._load_config()
    
    def reload_config(self) -> None:
        """Force reload of configuration on next access."""
        self._config = None
    
    def reload_template(self) -> None:
        """Force reload of template on next access."""
        self._template = None


# Singleton instance for convenience
_default_renderer: Optional[PromptRenderer] = None


def get_prompt_renderer() -> PromptRenderer:
    """
    Get the default prompt renderer instance (singleton).
    
    Returns:
        PromptRenderer instance
    """
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = PromptRenderer()
    return _default_renderer


def render_email_prompt(
    email_data: Dict[str, Any],
    **kwargs
) -> str:
    """
    Convenience function to render email prompt using default renderer.
    
    Args:
        email_data: Email data dictionary
        **kwargs: Additional email data fields (subject, from_addr, etc.)
        
    Returns:
        Rendered prompt string
    """
    renderer = get_prompt_renderer()
    return renderer.render_prompt(email_data, **kwargs)
