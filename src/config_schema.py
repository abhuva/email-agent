"""
V4 Configuration Schema Definition

This module defines the schema for V4 configuration validation.
V4 configuration supports account-specific overrides via deep merge.

The schema is defined as a dictionary structure that can express:
- Required fields
- Allowed types
- Default values (if any)
- Allowed value ranges/enums
- Cross-field constraints

This schema is used by the ConfigSchemaValidator to validate merged
configuration dictionaries before they are used by the application.

PDD Reference: pdd_V4.md Section 3.1
"""
from typing import Any, Dict, List, Optional, Union

# Type aliases for schema definition
SchemaField = Dict[str, Any]
SchemaDefinition = Dict[str, Any]


def get_v4_config_schema() -> SchemaDefinition:
    """
    Get the V4 configuration schema definition.
    
    The schema is defined as a nested dictionary structure where:
    - Each top-level key represents a configuration section (e.g., 'imap', 'paths')
    - Each section contains field definitions with validation rules
    - Field definitions include: type, required, default, constraints
    
    Returns:
        Dictionary containing the complete schema definition
        
    Schema Structure:
        {
            'section_name': {
                'required': bool,
                'fields': {
                    'field_name': {
                        'type': type or tuple of types,
                        'required': bool,
                        'default': default_value (optional),
                        'constraints': {
                            'min': min_value (optional),
                            'max': max_value (optional),
                            'enum': [allowed_values] (optional),
                            'regex': pattern (optional),
                            'validator': callable (optional)
                        }
                    }
                }
            }
        }
    """
    return {
        'imap': {
            'required': True,
            'fields': {
                'server': {
                    'type': str,
                    'required': True,
                    'constraints': {
                        'min_length': 1
                    }
                },
                'port': {
                    'type': int,
                    'required': False,
                    'default': 143,
                    'constraints': {
                        'min': 1,
                        'max': 65535
                    }
                },
                'username': {
                    'type': str,
                    'required': True,
                    'constraints': {
                        'min_length': 1
                    }
                },
                'password_env': {
                    'type': str,
                    'required': False,
                    'default': 'IMAP_PASSWORD',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'query': {
                    'type': str,
                    'required': False,
                    'default': 'ALL',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'processed_tag': {
                    'type': str,
                    'required': False,
                    'default': 'AIProcessed',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'application_flags': {
                    'type': list,
                    'required': False,
                    'default': ['AIProcessed', 'ObsidianNoteCreated', 'NoteCreationFailed'],
                    'constraints': {
                        'item_type': str,
                        'min_length': 1  # At least one flag required
                    }
                }
            }
        },
        'paths': {
            'required': True,
            'fields': {
                'template_file': {
                    'type': str,
                    'required': False,
                    'default': 'config/note_template.md.j2',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'obsidian_vault': {
                    'type': str,
                    'required': True,
                    'constraints': {
                        'min_length': 1
                    }
                },
                'log_file': {
                    'type': str,
                    'required': False,
                    'default': 'logs/agent.log',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'analytics_file': {
                    'type': str,
                    'required': False,
                    'default': 'logs/analytics.jsonl',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'changelog_path': {
                    'type': str,
                    'required': False,
                    'default': 'logs/email_changelog.md',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'prompt_file': {
                    'type': str,
                    'required': False,
                    'default': 'config/prompt.md',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'summarization_prompt_path': {
                    'type': (str, type(None)),
                    'required': False,
                    'default': None,
                    'constraints': {}
                }
            }
        },
        'openrouter': {
            'required': True,
            'fields': {
                'api_key_env': {
                    'type': str,
                    'required': False,
                    'default': 'OPENROUTER_API_KEY',
                    'constraints': {
                        'min_length': 1
                    }
                },
                'api_url': {
                    'type': str,
                    'required': False,
                    'default': 'https://openrouter.ai/api/v1',
                    'constraints': {
                        'min_length': 1
                    }
                }
            }
        },
        'classification': {
            'required': True,
            'fields': {
                'model': {
                    'type': str,
                    'required': True,
                    'constraints': {
                        'min_length': 1
                    }
                },
                'temperature': {
                    'type': (int, float),
                    'required': False,
                    'default': 0.2,
                    'constraints': {
                        'min': 0.0,
                        'max': 2.0
                    }
                },
                'retry_attempts': {
                    'type': int,
                    'required': False,
                    'default': 3,
                    'constraints': {
                        'min': 1
                    }
                },
                'retry_delay_seconds': {
                    'type': int,
                    'required': False,
                    'default': 5,
                    'constraints': {
                        'min': 1
                    }
                }
            }
        },
        'summarization': {
            'required': True,
            'fields': {
                'model': {
                    'type': str,
                    'required': True,
                    'constraints': {
                        'min_length': 1
                    }
                },
                'temperature': {
                    'type': (int, float),
                    'required': False,
                    'default': 0.3,
                    'constraints': {
                        'min': 0.0,
                        'max': 2.0
                    }
                },
                'retry_attempts': {
                    'type': int,
                    'required': False,
                    'default': 3,
                    'constraints': {
                        'min': 1
                    }
                },
                'retry_delay_seconds': {
                    'type': int,
                    'required': False,
                    'default': 5,
                    'constraints': {
                        'min': 1
                    }
                }
            }
        },
        'processing': {
            'required': True,
            'fields': {
                'importance_threshold': {
                    'type': int,
                    'required': False,
                    'default': 8,
                    'constraints': {
                        'min': 0,
                        'max': 10
                    }
                },
                'spam_threshold': {
                    'type': int,
                    'required': False,
                    'default': 5,
                    'constraints': {
                        'min': 0,
                        'max': 10
                    }
                },
                'max_body_chars': {
                    'type': int,
                    'required': False,
                    'default': 4000,
                    'constraints': {
                        'min': 1
                    }
                },
                'max_emails_per_run': {
                    'type': int,
                    'required': False,
                    'default': 15,
                    'constraints': {
                        'min': 1
                    }
                },
                'summarization_tags': {
                    'type': (list, type(None)),
                    'required': False,
                    'default': None,
                    'constraints': {
                        'item_type': str  # If list, items must be strings
                    }
                }
            }
        },
        'auth': {
            'required': False,  # Optional - account-specific, defaults to password if missing
            'fields': {
                'method': {
                    'type': str,
                    'required': False,
                    'default': 'password',
                    'constraints': {
                        'enum': ['password', 'oauth']
                    }
                },
                'provider': {
                    'type': (str, type(None)),
                    'required': False,
                    'default': None,
                    'constraints': {
                        'enum': ['google', 'microsoft']  # Only valid when method='oauth'
                    }
                },
                'password_env': {
                    'type': (str, type(None)),
                    'required': False,
                    'default': None,
                    'constraints': {
                        'min_length': 1  # Required when method='password'
                    }
                },
                'oauth': {
                    'type': (dict, type(None)),
                    'required': False,
                    'default': None,
                    'constraints': {
                        # OAuth-specific fields validated via custom validator
                    }
                }
            }
        }
    }


def validate_schema_structure(schema: SchemaDefinition) -> bool:
    """
    Validate that a schema definition has the correct structure.
    
    This function checks that the schema object contains expected keys
    and constraints and can be loaded/instantiated without errors.
    
    Args:
        schema: Schema definition to validate
        
    Returns:
        True if schema structure is valid
        
    Raises:
        ValueError: If schema structure is invalid
    """
    if not isinstance(schema, dict):
        raise ValueError(f"Schema must be a dictionary, got {type(schema).__name__}")
    
    # Check that schema has at least one section
    if not schema:
        raise ValueError("Schema cannot be empty")
    
    # Validate each section
    for section_name, section_def in schema.items():
        if not isinstance(section_name, str):
            raise ValueError(f"Section name must be a string, got {type(section_name).__name__}")
        
        if not isinstance(section_def, dict):
            raise ValueError(f"Section definition for '{section_name}' must be a dictionary")
        
        # Check required fields in section definition
        if 'required' not in section_def:
            raise ValueError(f"Section '{section_name}' missing 'required' field")
        
        if 'fields' not in section_def:
            raise ValueError(f"Section '{section_name}' missing 'fields' field")
        
        if not isinstance(section_def['required'], bool):
            raise ValueError(f"Section '{section_name}' 'required' must be a boolean")
        
        if not isinstance(section_def['fields'], dict):
            raise ValueError(f"Section '{section_name}' 'fields' must be a dictionary")
        
        # Validate each field in the section
        for field_name, field_def in section_def['fields'].items():
            if not isinstance(field_name, str):
                raise ValueError(f"Field name in section '{section_name}' must be a string")
            
            if not isinstance(field_def, dict):
                raise ValueError(
                    f"Field definition for '{section_name}.{field_name}' must be a dictionary"
                )
            
            # Check required fields in field definition
            if 'type' not in field_def:
                raise ValueError(
                    f"Field '{section_name}.{field_name}' missing 'type' field"
                )
            
            if 'required' not in field_def:
                raise ValueError(
                    f"Field '{section_name}.{field_name}' missing 'required' field"
                )
            
            if not isinstance(field_def['required'], bool):
                raise ValueError(
                    f"Field '{section_name}.{field_name}' 'required' must be a boolean"
                )
            
            # Validate constraints if present
            if 'constraints' in field_def:
                if not isinstance(field_def['constraints'], dict):
                    raise ValueError(
                        f"Field '{section_name}.{field_name}' 'constraints' must be a dictionary"
                    )
    
    return True
