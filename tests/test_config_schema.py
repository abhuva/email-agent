"""
Tests for configuration schema definition.

Tests verify that the schema object/schema file contains expected keys
and constraints and can be loaded/instantiated without errors.
"""
import pytest
from src.config_schema import (
    get_v4_config_schema,
    validate_schema_structure,
    SchemaDefinition
)


class TestSchemaDefinition:
    """Test that the schema definition is valid and can be loaded."""
    
    def test_schema_can_be_loaded(self):
        """Test that get_v4_config_schema() returns a valid schema."""
        schema = get_v4_config_schema()
        assert isinstance(schema, dict)
        assert len(schema) > 0
    
    def test_schema_has_required_sections(self):
        """Test that schema contains all required sections."""
        schema = get_v4_config_schema()
        required_sections = ['imap', 'paths', 'openrouter', 'classification', 'summarization', 'processing']
        for section in required_sections:
            assert section in schema, f"Missing required section: {section}"
    
    def test_schema_structure_is_valid(self):
        """Test that schema structure validation passes."""
        schema = get_v4_config_schema()
        # Should not raise
        assert validate_schema_structure(schema) is True
    
    def test_schema_sections_have_required_fields(self):
        """Test that each section has 'required' and 'fields' keys."""
        schema = get_v4_config_schema()
        for section_name, section_def in schema.items():
            assert 'required' in section_def, f"Section '{section_name}' missing 'required'"
            assert 'fields' in section_def, f"Section '{section_name}' missing 'fields'"
            assert isinstance(section_def['required'], bool)
            assert isinstance(section_def['fields'], dict)
    
    def test_schema_fields_have_type_and_required(self):
        """Test that each field has 'type' and 'required' keys."""
        schema = get_v4_config_schema()
        for section_name, section_def in schema.items():
            for field_name, field_def in section_def['fields'].items():
                assert 'type' in field_def, f"Field '{section_name}.{field_name}' missing 'type'"
                assert 'required' in field_def, f"Field '{section_name}.{field_name}' missing 'required'"
                assert isinstance(field_def['required'], bool)
    
    def test_validate_schema_structure_rejects_invalid_schema(self):
        """Test that validate_schema_structure raises errors for invalid schemas."""
        # Empty schema
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_schema_structure({})
        
        # Non-dict schema
        with pytest.raises(ValueError, match="must be a dictionary"):
            validate_schema_structure("not a dict")
        
        # Missing 'required' field
        with pytest.raises(ValueError, match="missing 'required' field"):
            validate_schema_structure({'section': {'fields': {}}})
        
        # Missing 'fields' field
        with pytest.raises(ValueError, match="missing 'fields' field"):
            validate_schema_structure({'section': {'required': True}})
        
        # Field missing 'type'
        with pytest.raises(ValueError, match="missing 'type' field"):
            validate_schema_structure({
                'section': {
                    'required': True,
                    'fields': {
                        'field': {'required': True}
                    }
                }
            })
        
        # Field missing 'required'
        with pytest.raises(ValueError, match="missing 'required' field"):
            validate_schema_structure({
                'section': {
                    'required': True,
                    'fields': {
                        'field': {'type': str}
                    }
                }
            })
    
    def test_schema_contains_expected_imap_fields(self):
        """Test that imap section contains expected fields."""
        schema = get_v4_config_schema()
        imap_fields = schema['imap']['fields']
        expected_fields = ['server', 'port', 'username', 'password_env', 'query', 
                          'processed_tag', 'application_flags']
        for field in expected_fields:
            assert field in imap_fields, f"Missing imap field: {field}"
    
    def test_schema_contains_expected_paths_fields(self):
        """Test that paths section contains expected fields."""
        schema = get_v4_config_schema()
        paths_fields = schema['paths']['fields']
        expected_fields = ['template_file', 'obsidian_vault', 'log_file', 
                          'analytics_file', 'changelog_path', 'prompt_file',
                          'summarization_prompt_path']
        for field in expected_fields:
            assert field in paths_fields, f"Missing paths field: {field}"
    
    def test_schema_contains_expected_processing_fields(self):
        """Test that processing section contains expected fields."""
        schema = get_v4_config_schema()
        processing_fields = schema['processing']['fields']
        expected_fields = ['importance_threshold', 'spam_threshold', 
                          'max_body_chars', 'max_emails_per_run', 'summarization_tags']
        for field in expected_fields:
            assert field in processing_fields, f"Missing processing field: {field}"
