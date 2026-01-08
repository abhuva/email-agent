"""
V3 Note Generator Module

This module provides templating functionality for generating Markdown notes
from email content and classification results using Jinja2.

All configuration access is through the settings.py facade, not direct YAML access.

Architecture:
    - TemplateLoader: Handles template file loading and validation
    - TemplateRenderer: Renders templates with email data and classification results
    - Jinja2 environment configured for Markdown generation
    - Error handling with fallback templates
    - Comprehensive logging for debugging

Usage:
    >>> from src.note_generator import NoteGenerator
    >>> from src.settings import settings
    >>> 
    >>> generator = NoteGenerator()
    >>> note_content = generator.generate_note(
    ...     email_data={'uid': '123', 'subject': 'Test', ...},
    ...     classification_result=result
    ... )
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateError, select_autoescape

from src.settings import settings
from src.config import ConfigError

logger = logging.getLogger(__name__)


class TemplateLoaderError(Exception):
    """Base exception for template loading errors."""
    pass


class TemplateRenderError(Exception):
    """Base exception for template rendering errors."""
    pass


class TemplateLoader:
    """
    Handles locating and loading template files from configured directory.
    
    Supports template inheritance and includes. Handles file system errors
    gracefully with appropriate exception handling.
    
    All configuration access is through the settings.py facade.
    """
    
    def __init__(self):
        """Initialize template loader with configuration from settings facade."""
        self._template_file = settings.get_template_file()
        self._template_path = Path(self._template_file)
        self._template_dir = self._template_path.parent
        self._template_name = self._template_path.name
        
        logger.debug(f"Template loader initialized: {self._template_file}")
        logger.debug(f"Template directory: {self._template_dir}")
        logger.debug(f"Template name: {self._template_name}")
    
    def template_exists(self) -> bool:
        """
        Check if the configured template file exists.
        
        Returns:
            True if template file exists, False otherwise
        """
        return self._template_path.exists()
    
    def load_template_content(self) -> str:
        """
        Load template content from the configured template file.
        
        Returns:
            Template content as string
            
        Raises:
            TemplateLoaderError: If template file doesn't exist or can't be read
        """
        if not self.template_exists():
            error_msg = f"Template file not found: {self._template_file}"
            logger.error(error_msg)
            raise TemplateLoaderError(error_msg)
        
        try:
            with open(self._template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"Successfully loaded template from {self._template_file}")
            return content
        except IOError as e:
            error_msg = f"Error reading template file {self._template_file}: {e}"
            logger.error(error_msg)
            raise TemplateLoaderError(error_msg) from e
    
    def get_template_path(self) -> str:
        """Get the configured template file path."""
        return str(self._template_file)
    
    def get_template_directory(self) -> str:
        """Get the template directory path."""
        return str(self._template_dir)


class TemplateRenderer:
    """
    Renders templates with email data and classification results.
    
    Provides context preparation functions that transform raw email data
    into a format suitable for template rendering. Includes helper functions
    for common formatting tasks (date formatting, URL handling, etc.).
    
    All configuration access is through the settings.py facade.
    """
    
    def __init__(self, template_loader: TemplateLoader):
        """
        Initialize template renderer with template loader.
        
        Args:
            template_loader: TemplateLoader instance for loading templates
        """
        self._loader = template_loader
        self._env = self._create_jinja2_environment()
        self._template = None
        self._load_template()
    
    def _create_jinja2_environment(self) -> Environment:
        """
        Create and configure Jinja2 environment.
        
        Returns:
            Configured Jinja2 Environment instance
        """
        template_dir = self._loader.get_template_directory()
        
        # Create environment with autoescape for HTML safety
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        env.filters['format_date'] = self._format_date_filter
        env.filters['format_datetime'] = self._format_datetime_filter
        env.filters['truncate'] = self._truncate_filter
        
        logger.debug(f"Jinja2 environment created with template directory: {template_dir}")
        return env
    
    def _load_template(self) -> None:
        """
        Load the template from the configured file.
        
        Raises:
            TemplateRenderError: If template loading fails
        """
        try:
            template_name = Path(self._loader.get_template_path()).name
            self._template = self._env.get_template(template_name)
            logger.debug(f"Template loaded successfully: {template_name}")
        except TemplateNotFound as e:
            error_msg = f"Template not found: {e}"
            logger.error(error_msg)
            raise TemplateRenderError(error_msg) from e
        except TemplateError as e:
            error_msg = f"Template syntax error: {e}"
            logger.error(error_msg)
            raise TemplateRenderError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error loading template: {e}"
            logger.error(error_msg)
            raise TemplateRenderError(error_msg) from e
    
    def _format_date_filter(self, value: str, format_str: str = '%Y-%m-%d') -> str:
        """
        Jinja2 filter for formatting dates.
        
        Args:
            value: Date string to format
            format_str: Format string (default: '%Y-%m-%d')
            
        Returns:
            Formatted date string
        """
        try:
            # Try to parse common date formats
            for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %z']:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime(format_str)
                except ValueError:
                    continue
            # If no format matches, return original
            return value
        except Exception:
            return value
    
    def _format_datetime_filter(self, value: str) -> str:
        """
        Jinja2 filter for formatting datetimes to ISO format.
        
        Args:
            value: Date string to format
            
        Returns:
            ISO formatted datetime string (YYYY-MM-DDTHH:MM:SSZ)
        """
        try:
            # Try to parse common date formats
            for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %z']:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                    continue
            # If no format matches, return original
            return value
        except Exception:
            return value
    
    def _truncate_filter(self, value: str, length: int = 100) -> str:
        """
        Jinja2 filter for truncating strings.
        
        Args:
            value: String to truncate
            length: Maximum length (default: 100)
            
        Returns:
            Truncated string with ellipsis if needed
        """
        if not value:
            return ''
        if len(value) <= length:
            return value
        return value[:length] + '...'
    
    def _prepare_context(
        self,
        email_data: Dict[str, Any],
        classification_result: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Prepare template context from email data and classification results.
        
        Transforms raw email data and classification results into a format
        suitable for template rendering. Includes all fields from PDD Section 3.2.
        
        Args:
            email_data: Email data dictionary with uid, subject, from, to, date, body, etc.
            classification_result: ClassificationResult object (optional)
            
        Returns:
            Dictionary of template variables
        """
        context = {
            'uid': email_data.get('uid', ''),
            'subject': email_data.get('subject', '[No Subject]'),
            'from': email_data.get('from', '[Unknown Sender]'),
            'to': email_data.get('to', []),
            'date': email_data.get('date', ''),
            'body': email_data.get('body', ''),
            'html_body': email_data.get('html_body', ''),
            'headers': email_data.get('headers', {}),
        }
        
        # Add classification results if provided
        if classification_result:
            # Use the to_frontmatter_dict() method to get PDD-compliant format
            frontmatter = classification_result.to_frontmatter_dict()
            context.update({
                'llm_output': frontmatter.get('llm_output', {}),
                'processing_meta': frontmatter.get('processing_meta', {}),
                'tags': frontmatter.get('tags', ['email']),
                'is_important': classification_result.is_important,
                'is_spam': classification_result.is_spam,
                'importance_score': classification_result.importance_score,
                'spam_score': classification_result.spam_score,
                'confidence': classification_result.confidence,
                'status': classification_result.status.value if hasattr(classification_result.status, 'value') else str(classification_result.status),
            })
        else:
            # Default values if no classification result
            context.update({
                'llm_output': {
                    'importance_score': -1,
                    'spam_score': -1,
                    'model_used': 'unknown'
                },
                'processing_meta': {
                    'script_version': '3.0',
                    'processed_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'status': 'error'
                },
                'tags': ['email'],
                'is_important': False,
                'is_spam': False,
                'importance_score': -1,
                'spam_score': -1,
                'confidence': 0.0,
                'status': 'error',
            })
        
        # Add configuration values for template use
        try:
            context['importance_threshold'] = settings.get_importance_threshold()
            context['spam_threshold'] = settings.get_spam_threshold()
        except (ConfigError, AttributeError):
            # Settings not initialized, use defaults
            context['importance_threshold'] = 8
            context['spam_threshold'] = 5
            logger.warning("Settings not initialized, using default thresholds")
        
        return context
    
    def render(
        self,
        email_data: Dict[str, Any],
        classification_result: Optional[Any] = None
    ) -> str:
        """
        Render template with email data and classification results.
        
        Args:
            email_data: Email data dictionary
            classification_result: ClassificationResult object (optional)
            
        Returns:
            Rendered Markdown content
            
        Raises:
            TemplateRenderError: If rendering fails
        """
        try:
            context = self._prepare_context(email_data, classification_result)
            rendered = self._template.render(**context)
            logger.debug(f"Template rendered successfully for email UID: {email_data.get('uid', 'unknown')}")
            return rendered
        except TemplateError as e:
            error_msg = f"Template rendering error: {e}"
            logger.error(error_msg)
            raise TemplateRenderError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error rendering template: {e}"
            logger.error(error_msg)
            raise TemplateRenderError(error_msg) from e


class NoteGenerator:
    """
    Main note generator class that coordinates template loading and rendering.
    
    Provides a high-level interface for generating Markdown notes from email
    data and classification results. Includes comprehensive error handling
    with fallback templates.
    
    All configuration access is through the settings.py facade.
    """
    
    def __init__(self):
        """Initialize note generator with template loader and renderer."""
        self._loader = TemplateLoader()
        self._renderer = None
        self._fallback_template = self._create_fallback_template()
        
        # Initialize renderer (will raise error if template doesn't exist)
        try:
            self._renderer = TemplateRenderer(self._loader)
            logger.info("Note generator initialized successfully")
        except TemplateRenderError as e:
            logger.warning(f"Primary template failed to load: {e}")
            logger.info("Note generator initialized with fallback template only")
    
    def _create_fallback_template(self) -> str:
        """
        Create a simple fallback template for use when primary template fails.
        
        Returns:
            Fallback template content as string
        """
        return """---
uid: {{ uid }}
subject: "{{ subject }}"
from: "{{ from }}"
to: {{ to | tojson }}
date: "{{ date }}"
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

**From:** {{ from }}  
**To:** {{ to | join(', ') }}  
**Date:** {{ date }}

{% if is_important %}
> ⚠️ **Important Email**
{% endif %}

{% if is_spam %}
> 🚨 **Spam Email**
{% endif %}

## Content

{{ body }}
"""
    
    def _render_fallback(
        self,
        email_data: Dict[str, Any],
        classification_result: Optional[Any] = None
    ) -> str:
        """
        Render using fallback template.
        
        Args:
            email_data: Email data dictionary
            classification_result: ClassificationResult object (optional)
            
        Returns:
            Rendered Markdown content using fallback template
        """
        try:
            from jinja2 import Template
            template = Template(self._fallback_template)
            
            # Prepare minimal context
            context = {
                'uid': email_data.get('uid', ''),
                'subject': email_data.get('subject', '[No Subject]'),
                'from': email_data.get('from', '[Unknown Sender]'),
                'to': email_data.get('to', []),
                'date': email_data.get('date', ''),
                'body': email_data.get('body', ''),
                'tags': ['email'],
                'importance_score': -1,
                'spam_score': -1,
                'is_important': False,
                'is_spam': False,
                'status': 'error',
            }
            
            if classification_result:
                frontmatter = classification_result.to_frontmatter_dict()
                context.update({
                    'llm_output': frontmatter.get('llm_output', {}),
                    'processing_meta': frontmatter.get('processing_meta', {}),
                    'tags': frontmatter.get('tags', ['email']),
                    'is_important': classification_result.is_important,
                    'is_spam': classification_result.is_spam,
                    'importance_score': classification_result.importance_score,
                    'spam_score': classification_result.spam_score,
                    'status': classification_result.status.value if hasattr(classification_result.status, 'value') else str(classification_result.status),
                })
            else:
                context.update({
                    'llm_output': {'model_used': 'unknown'},
                    'processing_meta': {'processed_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')},
                })
            
            rendered = template.render(**context)
            logger.info("Fallback template rendered successfully")
            return rendered
        except Exception as e:
            error_msg = f"Fallback template rendering failed: {e}"
            logger.error(error_msg)
            # Last resort: return minimal markdown
            return f"# {email_data.get('subject', '[No Subject]')}\n\n{email_data.get('body', '')}"
    
    def generate_note(
        self,
        email_data: Dict[str, Any],
        classification_result: Optional[Any] = None
    ) -> str:
        """
        Generate Markdown note from email data and classification results.
        
        This is the main entry point for note generation. It attempts to use
        the primary template, falling back to a simple template if rendering fails.
        
        Args:
            email_data: Email data dictionary with uid, subject, from, to, date, body, etc.
            classification_result: ClassificationResult object (optional)
            
        Returns:
            Rendered Markdown content
            
        Raises:
            TemplateRenderError: If both primary and fallback templates fail
        """
        # Try primary template first
        if self._renderer:
            try:
                return self._renderer.render(email_data, classification_result)
            except TemplateRenderError as e:
                logger.warning(f"Primary template rendering failed: {e}")
                logger.info("Attempting fallback template")
        
        # Use fallback template
        try:
            return self._render_fallback(email_data, classification_result)
        except Exception as e:
            error_msg = f"Both primary and fallback template rendering failed: {e}"
            logger.error(error_msg)
            raise TemplateRenderError(error_msg) from e
