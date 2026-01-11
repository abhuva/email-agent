#!/usr/bin/env python3
"""
Validate Configuration Templates

This script validates that all configuration templates can be loaded
and merged correctly by the ConfigLoader.

Usage:
    python scripts/validate_config_templates.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from src.config_loader import ConfigLoader, ConfigurationError
from src.config_validator import ConfigSchemaValidator


def validate_yaml_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate YAML syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        return True, "OK"
    except yaml.YAMLError as e:
        return False, f"YAML syntax error: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_global_config_template() -> tuple[bool, str]:
    """Validate global config.yaml.example template."""
    template_path = project_root / "config" / "config.yaml.example"
    
    if not template_path.exists():
        return False, f"Template not found: {template_path}"
    
    # Check YAML syntax
    valid, msg = validate_yaml_syntax(template_path)
    if not valid:
        return False, msg
    
    # Try to load with ConfigLoader (but disable validation since it's a template)
    try:
        loader = ConfigLoader('config', global_filename='config.yaml.example', enable_validation=False)
        config = loader.load_global_config()
        
        # Check that it's a dictionary
        if not isinstance(config, dict):
            return False, "Config is not a dictionary"
        
        # Check for required sections (basic check)
        required_sections = ['imap', 'paths', 'openrouter', 'classification', 'summarization', 'processing']
        missing = [s for s in required_sections if s not in config]
        if missing:
            return False, f"Missing required sections: {missing}"
        
        return True, "OK"
    except Exception as e:
        return False, f"ConfigLoader error: {e}"


def validate_account_config_template() -> tuple[bool, str]:
    """Validate account config template."""
    template_path = project_root / "config" / "accounts" / "example-account.yaml"
    
    if not template_path.exists():
        return False, f"Template not found: {template_path}"
    
    # Check YAML syntax
    valid, msg = validate_yaml_syntax(template_path)
    if not valid:
        return False, msg
    
    # Try to load with ConfigLoader
    try:
        loader = ConfigLoader('config', enable_validation=False)
        account_config = loader.load_account_config('example-account')
        
        # Check that it's a dictionary (or empty dict if all commented out)
        if not isinstance(account_config, dict):
            return False, "Account config is not a dictionary"
        
        return True, "OK"
    except Exception as e:
        return False, f"ConfigLoader error: {e}"


def validate_blacklist_template() -> tuple[bool, str]:
    """Validate blacklist.yaml template."""
    template_path = project_root / "config" / "blacklist.yaml"
    
    if not template_path.exists():
        return False, f"Template not found: {template_path}"
    
    # Check YAML syntax
    valid, msg = validate_yaml_syntax(template_path)
    if not valid:
        return False, msg
    
    # Try to load and validate structure
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        # Should be a list (even if empty)
        if not isinstance(rules, list):
            return False, "Blacklist rules must be a list"
        
        # If there are rules, validate structure
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                return False, f"Rule {i} is not a dictionary"
            
            required_fields = ['trigger', 'value', 'action']
            missing = [f for f in required_fields if f not in rule]
            if missing:
                return False, f"Rule {i} missing required fields: {missing}"
            
            # Validate trigger
            if rule['trigger'] not in ['sender', 'subject', 'domain']:
                return False, f"Rule {i} has invalid trigger: {rule['trigger']}"
            
            # Validate action
            if rule['action'] not in ['drop', 'record']:
                return False, f"Rule {i} has invalid action: {rule['action']}"
        
        return True, "OK"
    except Exception as e:
        return False, f"Error validating blacklist: {e}"


def validate_whitelist_template() -> tuple[bool, str]:
    """Validate whitelist.yaml template."""
    template_path = project_root / "config" / "whitelist.yaml"
    
    if not template_path.exists():
        return False, f"Template not found: {template_path}"
    
    # Check YAML syntax
    valid, msg = validate_yaml_syntax(template_path)
    if not valid:
        return False, msg
    
    # Try to load and validate structure
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        
        # Should be a list (even if empty)
        if not isinstance(rules, list):
            return False, "Whitelist rules must be a list"
        
        # If there are rules, validate structure
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                return False, f"Rule {i} is not a dictionary"
            
            required_fields = ['trigger', 'value', 'action', 'score_boost', 'add_tags']
            missing = [f for f in required_fields if f not in rule]
            if missing:
                return False, f"Rule {i} missing required fields: {missing}"
            
            # Validate trigger
            if rule['trigger'] not in ['sender', 'subject', 'domain']:
                return False, f"Rule {i} has invalid trigger: {rule['trigger']}"
            
            # Validate action
            if rule['action'] != 'boost':
                return False, f"Rule {i} has invalid action: {rule['action']} (must be 'boost')"
            
            # Validate score_boost
            if not isinstance(rule['score_boost'], int):
                return False, f"Rule {i} score_boost must be an integer"
            
            # Validate add_tags
            if not isinstance(rule['add_tags'], list):
                return False, f"Rule {i} add_tags must be a list"
        
        return True, "OK"
    except Exception as e:
        return False, f"Error validating whitelist: {e}"


def validate_merged_config() -> tuple[bool, str]:
    """Validate that global and account configs can be merged."""
    try:
        loader = ConfigLoader('config', global_filename='config.yaml.example', enable_validation=False)
        
        # Try to merge (even if account config doesn't exist, should work)
        merged = loader.load_merged_config('example-account')
        
        if not isinstance(merged, dict):
            return False, "Merged config is not a dictionary"
        
        return True, "OK"
    except Exception as e:
        return False, f"Merge error: {e}"


def main():
    """Run all validation checks."""
    print("Validating configuration templates...")
    print("=" * 60)
    
    checks = [
        ("Global config template (config.yaml.example)", validate_global_config_template),
        ("Account config template (example-account.yaml)", validate_account_config_template),
        ("Blacklist template (blacklist.yaml)", validate_blacklist_template),
        ("Whitelist template (whitelist.yaml)", validate_whitelist_template),
        ("Merged config (global + account)", validate_merged_config),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\nChecking {name}...")
        valid, msg = check_func()
        status = "PASS" if valid else "FAIL"
        print(f"  {status}: {msg}")
        results.append((name, valid, msg))
    
    print("\n" + "=" * 60)
    print("Summary:")
    
    passed = sum(1 for _, valid, _ in results if valid)
    total = len(results)
    
    for name, valid, msg in results:
        status = "[OK]" if valid else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print("All templates are valid!")
        return 0
    else:
        print("Some templates have issues. Please fix them.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
