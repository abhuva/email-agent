"""
Tests for configuration schema validator.

Tests verify that the validator correctly:
- Validates required fields
- Validates field types
- Validates constraints (min/max, enum, regex, etc.)
- Returns structured validation results
- Handles valid and invalid configurations
"""
import pytest
from src.config_validator import (
    ConfigSchemaValidator,
    ValidationResult,
    ValidationIssue
)
from src.config_schema import get_v4_config_schema


@pytest.fixture
def validator():
    """Create a validator instance for testing."""
    return ConfigSchemaValidator()


@pytest.fixture
def valid_config():
    """A valid configuration dictionary for testing."""
    return {
        'imap': {
            'server': 'imap.example.com',
            'port': 143,
            'username': 'user@example.com',
            'password_env': 'IMAP_PASSWORD',
            'query': 'ALL',
            'processed_tag': 'AIProcessed',
            'application_flags': ['AIProcessed', 'ObsidianNoteCreated']
        },
        'paths': {
            'obsidian_vault': '/path/to/vault',
            'template_file': 'config/template.md.j2',
            'log_file': 'logs/agent.log',
            'analytics_file': 'logs/analytics.jsonl',
            'changelog_path': 'logs/changelog.md',
            'prompt_file': 'config/prompt.md'
        },
        'openrouter': {
            'api_key_env': 'OPENROUTER_API_KEY',
            'api_url': 'https://openrouter.ai/api/v1'
        },
        'classification': {
            'model': 'google/gemini-2.5-flash-lite-preview-09-2025',
            'temperature': 0.2,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
        'summarization': {
            'model': 'google/gemini-2.5-flash-lite-preview-09-2025',
            'temperature': 0.3,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
        'processing': {
            'importance_threshold': 8,
            'spam_threshold': 5,
            'max_body_chars': 4000,
            'max_emails_per_run': 15
        }
    }


class TestConfigSchemaValidator:
    """Test the ConfigSchemaValidator class."""
    
    def test_validator_initializes_with_default_schema(self):
        """Test that validator can be initialized without a schema."""
        validator = ConfigSchemaValidator()
        assert validator.schema is not None
        assert 'imap' in validator.schema
    
    def test_validator_initializes_with_custom_schema(self):
        """Test that validator can be initialized with a custom schema."""
        custom_schema = {'test_section': {'required': True, 'fields': {}}}
        validator = ConfigSchemaValidator(schema=custom_schema)
        assert validator.schema == custom_schema
    
    def test_validate_valid_config_returns_success(self, validator, valid_config):
        """Test that validating a valid config returns success."""
        result = validator.validate(valid_config)
        assert result.is_valid is True
        assert not result.has_errors()
        assert result.normalized_config is not None
    
    def test_validate_missing_required_section(self, validator):
        """Test that missing required section is caught."""
        config = {
            'paths': {'obsidian_vault': '/vault'}
            # Missing 'imap' section
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('MISSING_REQUIRED_SECTION' in issue.error_code for issue in result.errors)
        assert any('imap' in issue.path for issue in result.errors)
    
    def test_validate_missing_required_field(self, validator):
        """Test that missing required field is caught."""
        config = {
            'imap': {
                'port': 143
                # Missing 'server' and 'username' (required)
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('MISSING_REQUIRED_FIELD' in issue.error_code for issue in result.errors)
        assert any('imap.server' in issue.path for issue in result.errors)
    
    def test_validate_invalid_type(self, validator):
        """Test that invalid field type is caught."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'port': 'not-a-number',  # Should be int
                'username': 'user@example.com'
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('INVALID_TYPE' in issue.error_code for issue in result.errors)
        assert any('imap.port' in issue.path for issue in result.errors)
    
    def test_validate_value_below_min(self, validator):
        """Test that value below minimum is caught."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'port': 0,  # Below minimum of 1
                'username': 'user@example.com'
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('VALUE_BELOW_MIN' in issue.error_code for issue in result.errors)
    
    def test_validate_value_above_max(self, validator):
        """Test that value above maximum is caught."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'port': 70000,  # Above maximum of 65535
                'username': 'user@example.com'
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('VALUE_ABOVE_MAX' in issue.error_code for issue in result.errors)
    
    def test_validate_temperature_range(self, validator):
        """Test that temperature values are validated within 0.0-2.0 range."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'user@example.com'
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {
                'model': 'test-model',
                'temperature': 3.0  # Above maximum of 2.0
            },
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('VALUE_ABOVE_MAX' in issue.error_code for issue in result.errors)
        assert any('classification.temperature' in issue.path for issue in result.errors)
    
    def test_validate_list_item_type(self, validator):
        """Test that list item types are validated."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'user@example.com',
                'application_flags': ['flag1', 123, 'flag2']  # Mixed types
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('INVALID_ITEM_TYPE' in issue.error_code for issue in result.errors)
    
    def test_validate_optional_fields_with_defaults(self, validator):
        """Test that optional fields use defaults when missing."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'user@example.com'
                # port, query, processed_tag missing but have defaults
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        # Should be valid because defaults are applied
        assert result.is_valid is True
        assert result.normalized_config is not None
        # Check that defaults are in normalized config
        assert result.normalized_config['imap']['port'] == 143
        assert result.normalized_config['imap']['query'] == 'ALL'
    
    def test_validate_result_has_errors_method(self, validator):
        """Test ValidationResult.has_errors() method."""
        config = {'imap': {}}  # Missing required fields
        result = validator.validate(config)
        assert result.has_errors() is True
        assert result.has_warnings() is False
    
    def test_validate_result_get_all_issues(self, validator):
        """Test ValidationResult.get_all_issues() method."""
        config = {'imap': {}}  # Missing required fields
        result = validator.validate(config)
        all_issues = result.get_all_issues()
        assert len(all_issues) == len(result.errors) + len(result.warnings)
    
    def test_validate_invalid_section_type(self, validator):
        """Test that invalid section type (non-dict) is caught."""
        config = {
            'imap': 'not-a-dict',  # Should be a dictionary
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('INVALID_SECTION_TYPE' in issue.error_code for issue in result.errors)
    
    def test_validate_processing_thresholds(self, validator):
        """Test that processing thresholds are validated (0-10 range)."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'user@example.com'
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {
                'importance_threshold': 15,  # Above maximum of 10
                'spam_threshold': -1  # Below minimum of 0
            }
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        # Should have errors for both thresholds
        importance_errors = [e for e in result.errors if 'importance_threshold' in e.path]
        spam_errors = [e for e in result.errors if 'spam_threshold' in e.path]
        assert len(importance_errors) > 0
        assert len(spam_errors) > 0
    
    def test_validate_optional_summarization_prompt_path(self, validator):
        """Test that optional summarization_prompt_path can be None."""
        config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'user@example.com'
            },
            'paths': {
                'obsidian_vault': '/vault',
                'summarization_prompt_path': None  # Optional, can be None
            },
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is True
    
    def test_validate_string_min_length(self, validator):
        """Test that string min_length constraint is validated."""
        config = {
            'imap': {
                'server': '',  # Empty string, below min_length of 1
                'username': 'user@example.com'
            },
            'paths': {'obsidian_vault': '/vault'},
            'openrouter': {},
            'classification': {'model': 'test-model'},
            'summarization': {'model': 'test-model'},
            'processing': {}
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('LENGTH_BELOW_MIN' in issue.error_code for issue in result.errors)
    
    # Auth schema validation tests
    def test_validate_auth_password_method_valid(self, validator, valid_config):
        """Test that valid password auth config passes validation."""
        valid_config['auth'] = {
            'method': 'password',
            'password_env': 'IMAP_PASSWORD'
        }
        result = validator.validate(valid_config)
        assert result.is_valid is True
        assert not result.has_errors()
    
    def test_validate_auth_password_method_missing_password_env(self, validator, valid_config):
        """Test that password method requires password_env."""
        valid_config['auth'] = {
            'method': 'password'
            # Missing password_env
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.password_env' in issue.path and 'MISSING_REQUIRED_FIELD' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_method_valid_google(self, validator, valid_config):
        """Test that valid OAuth config with Google provider passes validation."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'scopes': ['https://mail.google.com/'],
                'access_type': 'offline',
                'include_granted_scopes': True
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is True
        assert not result.has_errors()
    
    def test_validate_auth_oauth_method_valid_microsoft(self, validator, valid_config):
        """Test that valid OAuth config with Microsoft provider passes validation."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'microsoft',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'MS_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'scopes': ['https://outlook.office.com/IMAP.AccessAsUser.All']
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is True
        assert not result.has_errors()
    
    def test_validate_auth_oauth_method_missing_provider(self, validator, valid_config):
        """Test that OAuth method requires provider."""
        valid_config['auth'] = {
            'method': 'oauth'
            # Missing provider
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.provider' in issue.path and 'MISSING_REQUIRED_FIELD' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_method_invalid_provider(self, validator, valid_config):
        """Test that provider must be 'google' or 'microsoft'."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'invalid-provider'
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.provider' in issue.path and 'INVALID_PROVIDER' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_method_invalid_method(self, validator, valid_config):
        """Test that method must be 'password' or 'oauth'."""
        valid_config['auth'] = {
            'method': 'invalid-method'
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.method' in issue.path and 'INVALID_AUTH_METHOD' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_missing_required_fields(self, validator, valid_config):
        """Test that OAuth config requires client_id, client_secret_env, and redirect_uri."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id'
                # Missing client_secret_env and redirect_uri
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        # Should have errors for missing fields
        oauth_errors = [e for e in result.errors if 'auth.oauth' in e.path]
        assert len(oauth_errors) >= 2  # At least 2 missing fields
    
    def test_validate_auth_oauth_invalid_scopes_type(self, validator, valid_config):
        """Test that OAuth scopes must be a list."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'scopes': 'not-a-list'  # Should be a list
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.oauth.scopes' in issue.path and 'INVALID_TYPE' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_invalid_scope_items(self, validator, valid_config):
        """Test that OAuth scope items must be strings."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'scopes': ['valid-scope', 123, 'another-scope']  # Mixed types
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.oauth.scopes' in issue.path and 'INVALID_ITEM_TYPE' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_invalid_access_type(self, validator, valid_config):
        """Test that OAuth access_type must be a string."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'access_type': 123  # Should be a string
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.oauth.access_type' in issue.path and 'INVALID_TYPE' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_oauth_invalid_include_granted_scopes(self, validator, valid_config):
        """Test that OAuth include_granted_scopes must be a boolean."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'include_granted_scopes': 'not-a-boolean'  # Should be a boolean
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is False
        assert result.has_errors()
        assert any('auth.oauth.include_granted_scopes' in issue.path and 'INVALID_TYPE' in issue.error_code 
                   for issue in result.errors)
    
    def test_validate_auth_default_method_password(self, validator, valid_config):
        """Test that auth block defaults to method='password' when method is missing."""
        valid_config['auth'] = {
            'password_env': 'IMAP_PASSWORD'
            # method not specified, should default to 'password'
        }
        result = validator.validate(valid_config)
        # Should be valid because method defaults to 'password' and password_env is provided
        assert result.is_valid is True
        assert result.normalized_config['auth']['method'] == 'password'
    
    def test_validate_auth_backward_compatibility_warning(self, validator, valid_config):
        """Test that V4 configs without auth block generate deprecation warning."""
        # Remove auth block if present, keep password_env in imap (old style)
        if 'auth' in valid_config:
            del valid_config['auth']
        valid_config['imap']['password_env'] = 'IMAP_PASSWORD'
        
        result = validator.validate(valid_config)
        # Should be valid but with warning
        assert result.is_valid is True
        assert result.has_warnings()
        assert any('DEPRECATED_CONFIG_STYLE' in issue.error_code for issue in result.warnings)
        assert any('auth' in issue.path for issue in result.warnings)
    
    def test_validate_auth_extra_fields_ignored(self, validator, valid_config):
        """Test that extra unknown fields in auth block are ignored (don't cause errors)."""
        valid_config['auth'] = {
            'method': 'password',
            'password_env': 'IMAP_PASSWORD',
            'unknown_field': 'should-be-ignored',
            'another_unknown': 123
        }
        result = validator.validate(valid_config)
        # Should be valid (extra fields ignored, no errors)
        assert result.is_valid is True
        assert not result.has_errors()
        # Normalized config contains only schema-defined fields
        auth_config = result.normalized_config.get('auth', {})
        assert 'method' in auth_config
        assert 'password_env' in auth_config
        # Extra fields are not in normalized config (they're ignored, not preserved)
    
    def test_validate_auth_oauth_empty_scopes_allowed(self, validator, valid_config):
        """Test that OAuth scopes can be an empty list."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback',
                'scopes': []  # Empty list should be valid
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is True
        assert not result.has_errors()
    
    def test_validate_auth_oauth_optional_fields_defaults(self, validator, valid_config):
        """Test that OAuth optional fields (access_type, include_granted_scopes) are optional."""
        valid_config['auth'] = {
            'method': 'oauth',
            'provider': 'google',
            'oauth': {
                'client_id': 'test-client-id',
                'client_secret_env': 'GOOGLE_CLIENT_SECRET',
                'redirect_uri': 'http://localhost:8080/callback'
                # access_type and include_granted_scopes are optional
            }
        }
        result = validator.validate(valid_config)
        assert result.is_valid is True
        assert not result.has_errors()
