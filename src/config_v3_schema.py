"""
V3 Configuration Schema

This module defines the Pydantic schema for V3 configuration structure
as specified in pdd.md Section 3.1.

All configuration parameters must match the PDD specification exactly.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import os


class ImapConfig(BaseModel):
    """IMAP server configuration section."""
    server: str = Field(..., description="IMAP server hostname")
    port: int = Field(default=143, description="IMAP port (143 for STARTTLS, 993 for SSL)")
    username: str = Field(..., description="Email account username")
    password_env: str = Field(default="IMAP_PASSWORD", description="Environment variable name for IMAP password")
    query: str = Field(default="ALL", description="IMAP search query")
    processed_tag: str = Field(default="AIProcessed", description="IMAP flag name for processed emails")
    # Application-specific flags for cleanup command (Task 13)
    application_flags: list[str] = Field(
        default=["AIProcessed", "ObsidianNoteCreated", "NoteCreationFailed"],
        description="List of application-specific IMAP flags that can be cleaned up. These flags are managed by this application and safe to remove."
    )

    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator('password_env')
    @classmethod
    def validate_password_env(cls, v: str) -> str:
        """Validate password environment variable name is provided."""
        if not v or not v.strip():
            raise ValueError("password_env must be specified (security requirement)")
        # Note: Actual env var value is validated when accessed via settings.get_imap_password()
        return v

    @field_validator('application_flags')
    @classmethod
    def validate_application_flags(cls, v: list[str]) -> list[str]:
        """Validate application flags list is not empty and contains valid flag names."""
        if not v:
            raise ValueError("application_flags cannot be empty (must specify at least one flag)")
        # Validate flag names (IMAP flags should not contain spaces or special chars)
        for flag in v:
            if not flag or not flag.strip():
                raise ValueError(f"Application flag cannot be empty: {v}")
            if ' ' in flag or '\t' in flag:
                raise ValueError(f"Application flag cannot contain spaces: {flag}")
        return v


class PathsConfig(BaseModel):
    """File and directory paths configuration section."""
    template_file: str = Field(default="config/note_template.md.j2", description="Jinja2 template for generating Markdown notes")
    obsidian_vault: str = Field(..., description="Obsidian vault directory (must exist)")
    log_file: str = Field(default="logs/agent.log", description="Unstructured operational log file")
    analytics_file: str = Field(default="logs/analytics.jsonl", description="Structured analytics log (JSONL format)")
    changelog_path: str = Field(default="logs/email_changelog.md", description="Changelog/audit log file")
    prompt_file: str = Field(default="config/prompt.md", description="LLM prompt file for email classification")

    @field_validator('obsidian_vault')
    @classmethod
    def validate_obsidian_vault(cls, v: str) -> str:
        """Validate obsidian vault directory exists."""
        if not os.path.isdir(v):
            raise ValueError(f"Obsidian vault path must be an existing directory: {v}")
        return v

    @field_validator('template_file', 'prompt_file')
    @classmethod
    def validate_file_paths(cls, v: str) -> str:
        """Validate that file paths are non-empty."""
        if not v or not v.strip():
            raise ValueError(f"File path cannot be empty: {v}")
        return v


class OpenRouterConfig(BaseModel):
    """OpenRouter API configuration section."""
    api_key_env: str = Field(default="OPENROUTER_API_KEY", description="Environment variable name for API key")
    api_url: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter API endpoint")
    model: str = Field(..., description="LLM model to use")
    temperature: float = Field(default=0.2, description="LLM temperature (0.0-2.0)")
    retry_attempts: int = Field(default=3, description="Number of retry attempts for failed API calls")
    retry_delay_seconds: int = Field(default=5, description="Initial delay between retries (exponential backoff)")

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not (0.0 <= v <= 2.0):
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator('retry_attempts')
    @classmethod
    def validate_retry_attempts(cls, v: int) -> int:
        """Validate retry attempts is positive."""
        if v < 1:
            raise ValueError(f"Retry attempts must be at least 1, got {v}")
        return v

    @field_validator('retry_delay_seconds')
    @classmethod
    def validate_retry_delay(cls, v: int) -> int:
        """Validate retry delay is positive."""
        if v < 1:
            raise ValueError(f"Retry delay must be at least 1 second, got {v}")
        return v

    @field_validator('api_key_env')
    @classmethod
    def validate_api_key_env(cls, v: str) -> str:
        """Validate API key environment variable name is provided."""
        if not v or not v.strip():
            raise ValueError("api_key_env must be specified (security requirement)")
        # Note: Actual env var value is validated when accessed via settings.get_openrouter_api_key()
        return v


class ProcessingConfig(BaseModel):
    """Processing configuration section."""
    importance_threshold: int = Field(default=8, description="Minimum importance score (0-10) to mark email as important")
    spam_threshold: int = Field(default=5, description="Maximum spam score (0-10) to consider email as spam")
    max_body_chars: int = Field(default=4000, description="Maximum characters to send to LLM")
    max_emails_per_run: int = Field(default=15, description="Maximum number of emails to process per execution")

    @field_validator('importance_threshold', 'spam_threshold')
    @classmethod
    def validate_score_threshold(cls, v: int) -> int:
        """Validate score thresholds are in valid range."""
        if not (0 <= v <= 10):
            raise ValueError(f"Score threshold must be between 0 and 10, got {v}")
        return v

    @field_validator('max_body_chars', 'max_emails_per_run')
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate positive integers."""
        if v < 1:
            raise ValueError(f"Value must be at least 1, got {v}")
        return v


class V3ConfigSchema(BaseModel):
    """
    V3 Configuration Schema
    
    This schema matches the PDD Section 3.1 specification exactly.
    All configuration must conform to this structure.
    """
    imap: ImapConfig
    paths: PathsConfig
    openrouter: OpenRouterConfig
    processing: ProcessingConfig

    model_config = ConfigDict(
        extra="forbid",  # Reject any extra fields not in schema
        validate_assignment=True  # Validate on assignment
    )

    @model_validator(mode='after')
    def validate_paths_exist(self) -> 'V3ConfigSchema':
        """Validate that required files exist (after model creation)."""
        # Check that prompt_file exists
        if not os.path.isfile(self.paths.prompt_file):
            raise ValueError(f"Prompt file does not exist: {self.paths.prompt_file}")
        
        # Check that template_file exists (if specified)
        if self.paths.template_file and not os.path.isfile(self.paths.template_file):
            raise ValueError(f"Template file does not exist: {self.paths.template_file}")
        
        return self
