"""
Tests for V4 Configuration Loader with Deep Merge Logic.

These tests verify the ConfigLoader class that handles loading and merging
global and account-specific configuration files according to V4 merge rules.
"""
import pytest
import tempfile
import yaml
from pathlib import Path

from src.config_loader import ConfigLoader, ConfigurationError, load_merged_config


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory structure for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    accounts_dir = config_dir / "accounts"
    accounts_dir.mkdir()
    
    return config_dir


@pytest.fixture
def global_config_data():
    """Sample global configuration data."""
    return {
        'imap': {
            'server': 'global.imap.com',
            'port': 143,
            'username': 'global@example.com',
            'query': 'ALL'
        },
        'paths': {
            'obsidian_vault': '/global/vault',
            'log_file': 'logs/global.log'
        },
        'processing': {
            'importance_threshold': 7,
            'spam_threshold': 5,
            'max_emails_per_run': 10
        },
        'items': [1, 2, 3],
        'simple_value': 'global'
    }


@pytest.fixture
def account_config_data():
    """Sample account-specific configuration data."""
    return {
        'imap': {
            'server': 'account.imap.com',
            'username': 'account@example.com',
            'port': 993  # Override port
        },
        'paths': {
            'obsidian_vault': '/account/vault'  # Override vault
        },
        'processing': {
            'importance_threshold': 8  # Override threshold
        },
        'items': [4, 5],  # Replace list
        'simple_value': 'account',  # Override primitive
        'new_key': 'new_value'  # Add new key
    }


@pytest.fixture
def global_config_file(temp_config_dir, global_config_data):
    """Create a global config.yaml file."""
    config_file = temp_config_dir / "config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(global_config_data, f)
    return config_file


class TestConfigLoaderInitialization:
    """Tests for ConfigLoader initialization."""
    
    def test_init_with_defaults(self, temp_config_dir):
        """Test ConfigLoader initialization with default parameters."""
        loader = ConfigLoader(str(temp_config_dir))
        assert loader.base_dir == Path(temp_config_dir).resolve()
        assert loader.global_filename == "config.yaml"
        assert loader.accounts_dirname == "accounts"
    
    def test_init_with_custom_paths(self, temp_config_dir):
        """Test ConfigLoader initialization with custom paths."""
        loader = ConfigLoader(
            base_dir=str(temp_config_dir),
            global_filename="custom.yaml",
            accounts_dirname="custom_accounts"
        )
        assert loader.global_filename == "custom.yaml"
        assert loader.accounts_dirname == "custom_accounts"
    
    def test_init_with_path_object(self, temp_config_dir):
        """Test ConfigLoader initialization with Path object."""
        loader = ConfigLoader(Path(temp_config_dir))
        assert loader.base_dir == Path(temp_config_dir).resolve()


class TestPathResolution:
    """Tests for path resolution methods."""
    
    def test_get_global_config_path_exists(self, temp_config_dir, global_config_file):
        """Test getting global config path when file exists."""
        loader = ConfigLoader(str(temp_config_dir))
        path = loader._get_global_config_path()
        assert path == global_config_file
        assert path.exists()
    
    def test_get_global_config_path_missing(self, temp_config_dir):
        """Test getting global config path when file is missing."""
        loader = ConfigLoader(str(temp_config_dir))
        with pytest.raises(FileNotFoundError) as exc_info:
            loader._get_global_config_path()
        assert "not found" in str(exc_info.value).lower()
    
    def test_get_account_config_path_exists(self, temp_config_dir, account_config_data):
        """Test getting account config path when file exists."""
        account_file = temp_config_dir / "accounts" / "test.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(account_config_data, f)
        
        loader = ConfigLoader(str(temp_config_dir))
        path = loader._get_account_config_path("test")
        assert path == account_file
        assert path.exists()
    
    def test_get_account_config_path_missing(self, temp_config_dir):
        """Test getting account config path when file is missing."""
        loader = ConfigLoader(str(temp_config_dir))
        with pytest.raises(FileNotFoundError) as exc_info:
            loader._get_account_config_path("nonexistent")
        assert "not found" in str(exc_info.value).lower()


class TestAccountNameValidation:
    """Tests for account name validation."""
    
    def test_validate_account_name_valid(self):
        """Test validation of valid account names."""
        assert ConfigLoader._validate_account_name("work") == "work"
        assert ConfigLoader._validate_account_name("personal") == "personal"
        assert ConfigLoader._validate_account_name("account-123") == "account-123"
        assert ConfigLoader._validate_account_name("  work  ") == "work"  # Strip whitespace
    
    def test_validate_account_name_empty(self):
        """Test validation rejects empty account names."""
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name("")
        assert "empty" in str(exc_info.value).lower()
        
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name("   ")
        assert "empty" in str(exc_info.value).lower()
    
    def test_validate_account_name_path_traversal(self):
        """Test validation rejects path traversal patterns."""
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name("../work")
        assert "path traversal" in str(exc_info.value).lower()
        
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name("work/../other")
        assert "path traversal" in str(exc_info.value).lower()
        
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name("work\\..\\other")
        assert "path traversal" in str(exc_info.value).lower()
    
    def test_validate_account_name_invalid_type(self):
        """Test validation rejects non-string account names."""
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name(123)
        assert "string" in str(exc_info.value).lower()
        
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader._validate_account_name(None)
        assert "string" in str(exc_info.value).lower()


class TestYAMLLoading:
    """Tests for YAML file loading."""
    
    def test_load_yaml_file_valid(self, temp_config_dir, global_config_data):
        """Test loading a valid YAML file."""
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(global_config_data, f)
        
        loader = ConfigLoader(str(temp_config_dir))
        result = loader._load_yaml_file(config_file)
        assert result == global_config_data
    
    def test_load_yaml_file_empty(self, temp_config_dir):
        """Test loading an empty YAML file returns empty dict."""
        config_file = temp_config_dir / "empty.yaml"
        config_file.write_text("")
        
        loader = ConfigLoader(str(temp_config_dir))
        result = loader._load_yaml_file(config_file)
        assert result == {}
    
    def test_load_yaml_file_none_content(self, temp_config_dir):
        """Test loading YAML file with only comments returns empty dict."""
        config_file = temp_config_dir / "comments.yaml"
        config_file.write_text("# Just a comment\n# Another comment\n")
        
        loader = ConfigLoader(str(temp_config_dir))
        result = loader._load_yaml_file(config_file)
        assert result == {}
    
    def test_load_yaml_file_invalid_syntax(self, temp_config_dir):
        """Test loading YAML file with invalid syntax raises error."""
        config_file = temp_config_dir / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [unclosed")
        
        loader = ConfigLoader(str(temp_config_dir))
        with pytest.raises(ConfigurationError) as exc_info:
            loader._load_yaml_file(config_file)
        assert "YAML parse error" in str(exc_info.value)
    
    def test_load_yaml_file_non_dict_root(self, temp_config_dir):
        """Test loading YAML file with non-dict root raises error."""
        config_file = temp_config_dir / "list.yaml"
        config_file.write_text("- item1\n- item2\n")
        
        loader = ConfigLoader(str(temp_config_dir))
        with pytest.raises(ConfigurationError) as exc_info:
            loader._load_yaml_file(config_file)
        assert "must be a mapping" in str(exc_info.value).lower()
    
    def test_load_global_config(self, temp_config_dir, global_config_data, global_config_file):
        """Test loading global configuration."""
        loader = ConfigLoader(str(temp_config_dir))
        result = loader.load_global_config()
        assert result == global_config_data
    
    def test_load_account_config_exists(self, temp_config_dir, account_config_data):
        """Test loading account configuration when file exists."""
        account_file = temp_config_dir / "accounts" / "test.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(account_config_data, f)
        
        loader = ConfigLoader(str(temp_config_dir))
        result = loader.load_account_config("test")
        assert result == account_config_data
    
    def test_load_account_config_missing(self, temp_config_dir):
        """Test loading account configuration when file is missing returns empty dict."""
        loader = ConfigLoader(str(temp_config_dir))
        result = loader.load_account_config("nonexistent")
        assert result == {}


class TestDeepMerge:
    """Tests for deep merge functionality."""
    
    def test_deep_merge_primitives(self):
        """Test deep merge with primitive values."""
        base = {'a': 1, 'b': 'hello', 'c': True}
        override = {'a': 2, 'b': 'world', 'd': 3.14}
        result = ConfigLoader.deep_merge(base, override)
        
        assert result == {'a': 2, 'b': 'world', 'c': True, 'd': 3.14}
        # Verify base and override are not mutated
        assert base == {'a': 1, 'b': 'hello', 'c': True}
        assert override == {'a': 2, 'b': 'world', 'd': 3.14}
    
    def test_deep_merge_nested_dicts(self):
        """Test deep merge with nested dictionaries."""
        base = {
            'imap': {
                'server': 'base.com',
                'port': 143,
                'settings': {
                    'timeout': 30
                }
            }
        }
        override = {
            'imap': {
                'server': 'override.com',
                'username': 'user@override.com',
                'settings': {
                    'timeout': 60,
                    'retry': 3
                }
            }
        }
        result = ConfigLoader.deep_merge(base, override)
        
        expected = {
            'imap': {
                'server': 'override.com',  # Overridden
                'port': 143,  # Preserved from base
                'username': 'user@override.com',  # Added from override
                'settings': {
                    'timeout': 60,  # Overridden
                    'retry': 3  # Added from override
                }
            }
        }
        assert result == expected
    
    def test_deep_merge_lists_replaced(self):
        """Test deep merge replaces lists instead of concatenating."""
        base = {'items': [1, 2, 3], 'tags': ['a', 'b']}
        override = {'items': [4, 5], 'tags': ['c']}
        result = ConfigLoader.deep_merge(base, override)
        
        assert result == {'items': [4, 5], 'tags': ['c']}
        # Verify lists are replaced, not concatenated
        assert result['items'] == [4, 5]
        assert result['tags'] == ['c']
    
    def test_deep_merge_mismatched_types(self):
        """Test deep merge with mismatched types (override replaces base)."""
        base = {'value': {'nested': 'dict'}}
        override = {'value': [1, 2, 3]}  # Override dict with list
        result = ConfigLoader.deep_merge(base, override)
        
        assert result == {'value': [1, 2, 3]}
        
        base2 = {'value': [1, 2, 3]}
        override2 = {'value': {'nested': 'dict'}}  # Override list with dict
        result2 = ConfigLoader.deep_merge(base2, override2)
        
        assert result2 == {'value': {'nested': 'dict'}}
    
    def test_deep_merge_no_mutation(self):
        """Test that deep merge does not mutate input arguments."""
        base = {'a': {'nested': {'deep': 'value'}}, 'list': [1, 2, 3]}
        override = {'a': {'nested': {'new': 'data'}}, 'list': [4, 5]}
        
        base_copy = {'a': {'nested': {'deep': 'value'}}, 'list': [1, 2, 3]}
        override_copy = {'a': {'nested': {'new': 'data'}}, 'list': [4, 5]}
        
        result = ConfigLoader.deep_merge(base, override)
        
        # Verify inputs are not mutated
        assert base == base_copy
        assert override == override_copy
        
        # Verify result is independent
        result['a']['nested']['modified'] = True
        assert 'modified' not in base['a']['nested']


class TestLoadMergedConfig:
    """Tests for load_merged_config method."""
    
    def test_load_merged_config_global_only(
        self, temp_config_dir, global_config_data, global_config_file
    ):
        """Test loading merged config with only global config."""
        loader = ConfigLoader(str(temp_config_dir))
        result = loader.load_merged_config("nonexistent")
        
        # Should return global config only (account config missing returns {})
        assert result == global_config_data
    
    def test_load_merged_config_with_account(
        self, temp_config_dir, global_config_data, account_config_data,
        global_config_file
    ):
        """Test loading merged config with global and account configs."""
        account_file = temp_config_dir / "accounts" / "test.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(account_config_data, f)
        
        loader = ConfigLoader(str(temp_config_dir))
        result = loader.load_merged_config("test")
        
        # Verify merge results
        assert result['imap']['server'] == 'account.imap.com'  # Overridden
        assert result['imap']['port'] == 993  # Overridden
        assert result['imap']['username'] == 'account@example.com'  # Overridden
        assert result['imap']['query'] == 'ALL'  # Preserved from global
        assert result['paths']['obsidian_vault'] == '/account/vault'  # Overridden
        assert result['paths']['log_file'] == 'logs/global.log'  # Preserved from global
        assert result['processing']['importance_threshold'] == 8  # Overridden
        assert result['processing']['spam_threshold'] == 5  # Preserved from global
        assert result['items'] == [4, 5]  # List replaced
        assert result['simple_value'] == 'account'  # Primitive overridden
        assert result['new_key'] == 'new_value'  # New key added
    
    def test_load_merged_config_invalid_account_name(self, temp_config_dir, global_config_file):
        """Test load_merged_config with invalid account name."""
        loader = ConfigLoader(str(temp_config_dir))
        
        with pytest.raises(ValueError):
            loader.load_merged_config("../invalid")
        
        with pytest.raises(ValueError):
            loader.load_merged_config("")
    
    def test_load_merged_config_missing_global(self, temp_config_dir):
        """Test load_merged_config when global config is missing."""
        loader = ConfigLoader(str(temp_config_dir))
        
        with pytest.raises(FileNotFoundError):
            loader.load_merged_config("test")


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_deep_merge_empty_base(self):
        """Test deep merge with empty base dict."""
        base = {}
        override = {'a': 1, 'b': {'nested': 'value'}}
        result = ConfigLoader.deep_merge(base, override)
        assert result == override
    
    def test_deep_merge_empty_override(self):
        """Test deep merge with empty override dict."""
        base = {'a': 1, 'b': {'nested': 'value'}}
        override = {}
        result = ConfigLoader.deep_merge(base, override)
        assert result == base
    
    def test_deep_merge_both_empty(self):
        """Test deep merge with both dicts empty."""
        result = ConfigLoader.deep_merge({}, {})
        assert result == {}
    
    def test_load_yaml_file_missing(self, temp_config_dir):
        """Test loading non-existent YAML file."""
        loader = ConfigLoader(str(temp_config_dir))
        missing_file = temp_config_dir / "missing.yaml"
        
        with pytest.raises(ConfigurationError) as exc_info:
            loader._load_yaml_file(missing_file)
        assert "Error reading" in str(exc_info.value)


class TestConvenienceFunction:
    """Tests for module-level convenience function."""
    
    def test_load_merged_config_convenience_function(
        self, temp_config_dir, global_config_data, account_config_data,
        global_config_file
    ):
        """Test the module-level load_merged_config convenience function."""
        account_file = temp_config_dir / "accounts" / "test.yaml"
        with open(account_file, 'w') as f:
            yaml.dump(account_config_data, f)
        
        # Use convenience function
        result = load_merged_config("test", base_dir=str(temp_config_dir))
        
        # Verify it works the same as using the class directly
        assert result['imap']['server'] == 'account.imap.com'
        assert result['paths']['obsidian_vault'] == '/account/vault'
    
    def test_load_merged_config_convenience_function_default_dir(
        self, tmp_path, global_config_data
    ):
        """Test convenience function with default base_dir."""
        # Create config structure in a 'config' directory (default)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "accounts").mkdir()
        
        config_file = config_dir / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(global_config_data, f)
        
        # Change to tmp_path so default 'config' directory is found
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            result = load_merged_config("nonexistent")
            assert result == global_config_data
        finally:
            os.chdir(old_cwd)
