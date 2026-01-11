"""
Tests for config_display module.

Tests the annotated configuration merging and formatting functionality
for the show-config command.
"""
import pytest
from src.config_display import (
    AnnotatedConfigMerger,
    ConfigFormatter,
    ConfigSource
)


class TestAnnotatedConfigMerger:
    """Tests for AnnotatedConfigMerger."""
    
    def test_merge_simple_override(self):
        """Test merging with a simple override."""
        merger = AnnotatedConfigMerger()
        global_config = {'server': 'global.com', 'port': 993}
        account_config = {'server': 'account.com'}
        
        annotated = merger.merge_with_annotations(global_config, account_config)
        
        # Check server is overridden
        assert annotated['server']['value'] == 'account.com'
        assert annotated['server']['source'] == ConfigSource.ACCOUNT
        
        # Check port is from global
        assert annotated['port']['value'] == 993
        assert annotated['port']['source'] == ConfigSource.GLOBAL
    
    def test_merge_nested_override(self):
        """Test merging with nested dictionary overrides."""
        merger = AnnotatedConfigMerger()
        global_config = {
            'imap': {
                'server': 'global.com',
                'port': 993,
                'ssl': True
            }
        }
        account_config = {
            'imap': {
                'server': 'account.com'
            }
        }
        
        annotated = merger.merge_with_annotations(global_config, account_config)
        
        # Check nested structure
        assert 'imap' in annotated
        imap_config = annotated['imap']
        
        # Server is overridden
        assert imap_config['server']['value'] == 'account.com'
        assert imap_config['server']['source'] == ConfigSource.ACCOUNT
        
        # Port is from global
        assert imap_config['port']['value'] == 993
        assert imap_config['port']['source'] == ConfigSource.GLOBAL
        
        # SSL is from global
        assert imap_config['ssl']['value'] is True
        assert imap_config['ssl']['source'] == ConfigSource.GLOBAL
    
    def test_merge_list_replacement(self):
        """Test that lists are completely replaced, not merged."""
        merger = AnnotatedConfigMerger()
        global_config = {'folders': ['INBOX', 'Sent']}
        account_config = {'folders': ['INBOX', 'Archive']}
        
        annotated = merger.merge_with_annotations(global_config, account_config)
        
        # List should be replaced
        assert annotated['folders']['value'] == ['INBOX', 'Archive']
        assert annotated['folders']['source'] == ConfigSource.ACCOUNT
    
    def test_merge_empty_account_config(self):
        """Test merging when account config is empty."""
        merger = AnnotatedConfigMerger()
        global_config = {'server': 'global.com', 'port': 993}
        account_config = {}
        
        annotated = merger.merge_with_annotations(global_config, account_config)
        
        # All values should be from global
        assert annotated['server']['value'] == 'global.com'
        assert annotated['server']['source'] == ConfigSource.GLOBAL
        assert annotated['port']['value'] == 993
        assert annotated['port']['source'] == ConfigSource.GLOBAL
    
    def test_merge_new_account_key(self):
        """Test merging when account config adds a new key."""
        merger = AnnotatedConfigMerger()
        global_config = {'server': 'global.com'}
        account_config = {'custom_key': 'custom_value'}
        
        annotated = merger.merge_with_annotations(global_config, account_config)
        
        # New key should be from account
        assert annotated['custom_key']['value'] == 'custom_value'
        assert annotated['custom_key']['source'] == ConfigSource.ACCOUNT
        
        # Existing key should be from global
        assert annotated['server']['value'] == 'global.com'
        assert annotated['server']['source'] == ConfigSource.GLOBAL


class TestConfigFormatter:
    """Tests for ConfigFormatter."""
    
    def test_format_yaml_simple(self):
        """Test YAML formatting with simple values."""
        formatter = ConfigFormatter()
        
        # Create annotated config
        annotated = {
            'server': {
                'value': 'example.com',
                'source': ConfigSource.GLOBAL
            },
            'port': {
                'value': 993,
                'source': ConfigSource.ACCOUNT
            }
        }
        
        yaml_output = formatter.format_yaml(annotated, show_sources=True)
        
        # Should contain the values
        assert 'server: example.com' in yaml_output
        assert 'port: 993' in yaml_output
        # Should have override comment for port
        assert 'overridden from global' in yaml_output
    
    def test_format_yaml_no_sources(self):
        """Test YAML formatting without source comments."""
        formatter = ConfigFormatter()
        
        annotated = {
            'server': {
                'value': 'example.com',
                'source': ConfigSource.GLOBAL
            }
        }
        
        yaml_output = formatter.format_yaml(annotated, show_sources=False)
        
        # Should not have override comments
        assert 'overridden from global' not in yaml_output
        assert 'server: example.com' in yaml_output
    
    def test_format_json_plain(self):
        """Test JSON formatting without source fields."""
        formatter = ConfigFormatter()
        
        annotated = {
            'server': {
                'value': 'example.com',
                'source': ConfigSource.GLOBAL
            },
            'port': {
                'value': 993,
                'source': ConfigSource.ACCOUNT
            }
        }
        
        json_output = formatter.format_json(annotated, show_sources=True, include_source_fields=False)
        
        # Should be valid JSON
        import json
        parsed = json.loads(json_output.split('\n', 1)[-1])  # Skip comment line if present
        assert parsed['server'] == 'example.com'
        assert parsed['port'] == 993
        
        # Should have override note if there are overrides
        if 'Overridden values' in json_output:
            assert 'port' in json_output
    
    def test_format_json_with_sources(self):
        """Test JSON formatting with __source fields."""
        formatter = ConfigFormatter()
        
        annotated = {
            'server': {
                'value': 'example.com',
                'source': ConfigSource.GLOBAL
            },
            'port': {
                'value': 993,
                'source': ConfigSource.ACCOUNT
            }
        }
        
        json_output = formatter.format_json(annotated, show_sources=True, include_source_fields=True)
        
        # Should be valid JSON
        import json
        parsed = json.loads(json_output)
        
        # Should have source fields
        assert 'server' in parsed
        assert 'server__source' in parsed
        assert parsed['server__source'] == 'global'
        assert 'port__source' in parsed
        assert parsed['port__source'] == 'account'
    
    def test_extract_plain_config(self):
        """Test extracting plain config from annotated structure."""
        formatter = ConfigFormatter()
        
        annotated = {
            'server': {
                'value': 'example.com',
                'source': ConfigSource.GLOBAL
            },
            'imap': {
                'value': {
                    'port': {
                        'value': 993,
                        'source': ConfigSource.ACCOUNT
                    }
                },
                'source': ConfigSource.GLOBAL
            }
        }
        
        plain = formatter._extract_plain_config(annotated)
        
        assert plain['server'] == 'example.com'
        assert plain['imap']['port'] == 993
        assert 'source' not in plain
        assert 'value' not in plain
    
    def test_generate_override_note(self):
        """Test generating override note."""
        formatter = ConfigFormatter()
        
        annotated = {
            'server': {
                'value': 'example.com',
                'source': ConfigSource.GLOBAL
            },
            'port': {
                'value': 993,
                'source': ConfigSource.ACCOUNT
            },
            'imap': {
                'value': {
                    'ssl': {
                        'value': True,
                        'source': ConfigSource.ACCOUNT
                    }
                },
                'source': ConfigSource.GLOBAL
            }
        }
        
        note = formatter._generate_override_note(annotated)
        
        # Should list overridden keys
        assert 'port' in note
        assert 'imap.ssl' in note
        assert 'server' not in note
