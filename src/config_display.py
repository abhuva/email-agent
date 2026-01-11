"""
Configuration Display Module

This module provides functionality to display merged configurations with
highlighting of overridden values. It tracks which values come from global
config vs account-specific overrides and formats the output accordingly.

Usage:
    >>> from src.config_display import AnnotatedConfigMerger, ConfigFormatter
    >>> merger = AnnotatedConfigMerger()
    >>> annotated = merger.merge_with_annotations(global_config, account_config)
    >>> formatter = ConfigFormatter()
    >>> yaml_output = formatter.format_yaml(annotated)
"""
import yaml
import json
from typing import Dict, Any, Literal, Union
from enum import Enum


class ConfigSource(Enum):
    """Source of a configuration value."""
    GLOBAL = "global"
    ACCOUNT = "account"


# Type alias for annotated values
AnnotatedValue = Dict[str, Any]  # {'value': <actual_value>, 'source': ConfigSource}


class AnnotatedConfigMerger:
    """
    Merges global and account configurations while tracking the source of each value.
    
    This class creates an annotated configuration structure where each value
    is tagged with its source (global or account). This enables highlighting
    of overridden values in the output.
    
    Example:
        >>> merger = AnnotatedConfigMerger()
        >>> global_config = {'imap': {'server': 'global.com', 'port': 993}}
        >>> account_config = {'imap': {'server': 'account.com'}}
        >>> annotated = merger.merge_with_annotations(global_config, account_config)
        >>> # annotated['imap']['server'] = {'value': 'account.com', 'source': ConfigSource.ACCOUNT}
        >>> # annotated['imap']['port'] = {'value': 993, 'source': ConfigSource.GLOBAL}
    """
    
    def merge_with_annotations(
        self,
        global_config: Dict[str, Any],
        account_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge global and account configurations with source annotations.
        
        Args:
            global_config: Global/base configuration dictionary
            account_config: Account-specific override configuration dictionary
            
        Returns:
            Annotated configuration dictionary where each value is wrapped with
            {'value': <actual_value>, 'source': ConfigSource}
        """
        # Start with annotated global config
        annotated_base = self._annotate_dict(global_config, ConfigSource.GLOBAL)
        
        # Merge account overrides
        if account_config:
            annotated_override = self._annotate_dict(account_config, ConfigSource.ACCOUNT)
            annotated_result = self._merge_annotated(annotated_base, annotated_override)
        else:
            annotated_result = annotated_base
        
        return annotated_result
    
    def _annotate_dict(
        self,
        config: Dict[str, Any],
        source: ConfigSource
    ) -> Dict[str, Any]:
        """
        Recursively annotate a configuration dictionary with source information.
        
        Args:
            config: Configuration dictionary to annotate
            source: Source of the configuration values
            
        Returns:
            Annotated dictionary where each value is wrapped with source info
        """
        annotated = {}
        for key, value in config.items():
            if isinstance(value, dict):
                # Recursively annotate nested dictionaries
                annotated[key] = self._annotate_dict(value, source)
            elif isinstance(value, list):
                # For lists, annotate each item if it's a dict, otherwise wrap the list
                annotated[key] = {
                    'value': [
                        self._annotate_dict(item, source) if isinstance(item, dict) else item
                        for item in value
                    ],
                    'source': source
                }
            else:
                # Primitive value - wrap with source
                annotated[key] = {
                    'value': value,
                    'source': source
                }
        return annotated
    
    def _merge_annotated(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two annotated configuration dictionaries.
        
        Merge rules:
        - Dictionaries: Recursively merged
        - Lists: Completely replaced (account list replaces global list)
        - Primitives: Overwritten (account value replaces global value)
        
        Args:
            base: Base annotated configuration (from global)
            override: Override annotated configuration (from account)
            
        Returns:
            Merged annotated configuration
        """
        result = base.copy()
        
        for key, override_item in override.items():
            base_item = result.get(key)
            
            # Check if override item is an annotated wrapper
            # An annotated wrapper has exactly 'value' and 'source' keys
            is_override_wrapper = (
                isinstance(override_item, dict) and 
                'value' in override_item and 
                'source' in override_item and
                set(override_item.keys()) == {'value', 'source'}
            )
            
            # Check if base item is an annotated wrapper
            is_base_wrapper = (
                isinstance(base_item, dict) and 
                'value' in base_item and 
                'source' in base_item and
                set(base_item.keys()) == {'value', 'source'}
            )
            
            if is_override_wrapper:
                override_value = override_item['value']
                override_source = override_item['source']
            else:
                # Override item is a dict of annotated values (nested dict) or direct value
                override_value = override_item
                override_source = ConfigSource.ACCOUNT
            
            if is_base_wrapper:
                base_value = base_item['value']
            else:
                # Base item is a dict of annotated values (nested dict) or direct value
                base_value = base_item
            
            # Case 1: Both are dictionaries - recursively merge
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                # Both are dicts - merge them (they may contain annotated values)
                merged_dict = self._merge_annotated(base_value, override_value)
                result[key] = merged_dict
            # Case 2: Both are lists - replace (account list replaces global list)
            elif isinstance(base_value, list) and isinstance(override_value, list):
                # Account list completely replaces global list
                result[key] = {
                    'value': override_value.copy(),
                    'source': override_source
                }
            # Case 3: All other cases - override replaces base
            else:
                result[key] = {
                    'value': override_value.copy() if isinstance(override_value, (dict, list)) else override_value,
                    'source': override_source
                }
        
        return result


class ConfigFormatter:
    """
    Formats annotated configurations for display with override highlighting.
    
    Supports YAML and JSON output formats, with different strategies for
    indicating overridden values in each format.
    """
    
    def format_yaml(
        self,
        annotated_config: Dict[str, Any],
        show_sources: bool = True
    ) -> str:
        """
        Format annotated configuration as YAML with override comments.
        
        Overridden values are marked with inline comments like:
            server: account.com  # overridden from global
        
        Args:
            annotated_config: Annotated configuration dictionary
            show_sources: Whether to show source comments (default: True)
            
        Returns:
            YAML string with override indicators
        """
        if not show_sources:
            # Just extract plain config and format as YAML
            plain_config = self._extract_plain_config(annotated_config)
            return yaml.dump(
                plain_config,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=1000
            )
        
        # Generate YAML with comments directly
        lines = self._generate_yaml_with_comments(annotated_config, indent=0)
        return '\n'.join(lines)
    
    def format_json(
        self,
        annotated_config: Dict[str, Any],
        show_sources: bool = True,
        include_source_fields: bool = False
    ) -> str:
        """
        Format annotated configuration as JSON.
        
        Args:
            annotated_config: Annotated configuration dictionary
            show_sources: Whether to include source information (default: True)
            include_source_fields: If True, adds __source fields to JSON (default: False)
                                  If False, source info is only in a separate note
            
        Returns:
            JSON string (with optional source fields or note about overrides)
        """
        if include_source_fields:
            # Include __source fields in JSON structure
            json_config = self._convert_to_json_with_sources(annotated_config)
        else:
            # Plain JSON with source info in a note
            json_config = self._extract_plain_config(annotated_config)
        
        json_str = json.dumps(json_config, indent=2, default=str, ensure_ascii=False)
        
        if show_sources and not include_source_fields:
            # Add a note about overrides at the top
            override_note = self._generate_override_note(annotated_config)
            if override_note:
                json_str = f"// Overridden values: {override_note}\n{json_str}"
        
        return json_str
    
    def _extract_plain_config(self, annotated_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract plain configuration from annotated structure.
        
        Args:
            annotated_config: Annotated configuration dictionary
            
        Returns:
            Plain configuration dictionary without source annotations
        """
        plain = {}
        for key, item in annotated_config.items():
            if isinstance(item, dict) and 'value' in item and 'source' in item:
                # Annotated value
                value = item['value']
                if isinstance(value, dict):
                    # Recursively extract nested dicts
                    plain[key] = self._extract_plain_config(value)
                elif isinstance(value, list):
                    # Handle lists - check if items are annotated
                    plain_list = []
                    for list_item in value:
                        if isinstance(list_item, dict) and 'value' in list_item:
                            # Annotated list item (shouldn't happen for simple lists)
                            plain_list.append(self._extract_plain_config(list_item) if isinstance(list_item.get('value'), dict) else list_item.get('value'))
                        else:
                            plain_list.append(list_item)
                    plain[key] = plain_list
                else:
                    # Primitive value
                    plain[key] = value
            elif isinstance(item, dict):
                # Nested dict (not annotated wrapper) - recurse
                plain[key] = self._extract_plain_config(item)
            else:
                # Direct value (shouldn't happen in properly annotated config)
                plain[key] = item
        
        return plain
    
    def _generate_yaml_with_comments(
        self,
        annotated_config: Dict[str, Any],
        indent: int = 0
    ) -> list[str]:
        """
        Generate YAML lines with inline comments for overridden values.
        
        Args:
            annotated_config: Annotated configuration dictionary
            indent: Current indentation level (number of spaces)
            
        Returns:
            List of YAML lines with comments
        """
        lines = []
        indent_str = ' ' * indent
        
        for key, item in annotated_config.items():
            if isinstance(item, dict) and 'value' in item and 'source' in item:
                # Annotated value
                value = item['value']
                source = item['source']
                is_overridden = isinstance(source, ConfigSource) and source == ConfigSource.ACCOUNT
                
                if isinstance(value, dict):
                    # Nested dictionary
                    lines.append(f"{indent_str}{key}:")
                    if is_overridden:
                        lines.append(f"{indent_str}  # overridden from global")
                    nested_lines = self._generate_yaml_with_comments(value, indent + 2)
                    lines.extend(nested_lines)
                elif isinstance(value, list):
                    # List value
                    if not value:
                        # Empty list
                        comment = "  # overridden from global" if is_overridden else ""
                        lines.append(f"{indent_str}{key}: []{comment}")
                    else:
                        # Non-empty list - format as YAML list
                        lines.append(f"{indent_str}{key}:")
                        if is_overridden:
                            lines.append(f"{indent_str}  # overridden from global")
                        for list_item in value:
                            if isinstance(list_item, dict):
                                # List of dicts - format each dict
                                item_lines = yaml.dump([list_item], default_flow_style=False, sort_keys=False).strip().split('\n')
                                for item_line in item_lines:
                                    lines.append(f"{indent_str}  {item_line}")
                            else:
                                # Primitive list item
                                item_str = yaml.dump([list_item], default_flow_style=False, sort_keys=False).strip()
                                # Remove the leading dash and space, add our own
                                if item_str.startswith('- '):
                                    item_str = item_str[2:]
                                lines.append(f"{indent_str}  - {item_str}")
                else:
                    # Primitive value
                    # Format value appropriately
                    if value is None:
                        value_str = "null"
                    elif isinstance(value, bool):
                        value_str = str(value).lower()
                    elif isinstance(value, (int, float)):
                        value_str = str(value)
                    elif isinstance(value, str):
                        # Quote strings that need it
                        if ':' in value or '#' in value or value.strip() != value:
                            value_str = yaml.dump(value, default_style='"').strip()
                        else:
                            value_str = value
                    else:
                        value_str = str(value)
                    
                    comment = "  # overridden from global" if is_overridden else ""
                    lines.append(f"{indent_str}{key}: {value_str}{comment}")
            elif isinstance(item, dict):
                # Nested dict (not annotated wrapper) - recurse
                lines.append(f"{indent_str}{key}:")
                nested_lines = self._generate_yaml_with_comments(item, indent + 2)
                lines.extend(nested_lines)
            else:
                # Direct value (shouldn't happen in properly annotated config)
                value_str = yaml.dump({key: item}, default_flow_style=False, sort_keys=False).strip()
                value_part = value_str.split(':', 1)[1].strip() if ':' in value_str else str(item)
                lines.append(f"{indent_str}{key}: {value_part}")
        
        return lines
    
    def _add_yaml_comments(
        self,
        lines: list[str],
        annotated_config: Dict[str, Any],
        path: str = ""
    ) -> list[str]:
        """
        Add inline comments to YAML lines indicating overridden values.
        
        This method regenerates YAML with comments rather than trying to inject
        comments into existing YAML (which is complex and error-prone).
        
        Args:
            lines: YAML lines (unused - kept for compatibility)
            annotated_config: Annotated configuration dictionary
            path: Current path in config (unused - kept for compatibility)
            
        Returns:
            List of YAML lines with comments added
        """
        # Regenerate YAML with comments instead of trying to inject them
        return self._generate_yaml_with_comments(annotated_config, indent=0)
    
    def _convert_to_json_with_sources(
        self,
        annotated_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert annotated config to JSON structure with __source fields.
        
        Args:
            annotated_config: Annotated configuration dictionary
            
        Returns:
            JSON-compatible dictionary with __source fields added
        """
        result = {}
        for key, item in annotated_config.items():
            if isinstance(item, dict) and 'value' in item and 'source' in item:
                value = item['value']
                source = item['source']
                
                if isinstance(value, dict):
                    # Recursively process nested dict
                    nested = self._convert_to_json_with_sources(value)
                    nested['__source'] = source.value if isinstance(source, ConfigSource) else source
                    result[key] = nested
                elif isinstance(value, list):
                    # List with source
                    result[key] = value
                    result[f'{key}__source'] = source.value if isinstance(source, ConfigSource) else source
                else:
                    # Primitive with source
                    result[key] = value
                    result[f'{key}__source'] = source.value if isinstance(source, ConfigSource) else source
            elif isinstance(item, dict):
                # Nested dict - recurse
                result[key] = self._convert_to_json_with_sources(item)
            else:
                result[key] = item
        
        return result
    
    def _generate_override_note(self, annotated_config: Dict[str, Any]) -> str:
        """
        Generate a note listing overridden configuration keys.
        
        Args:
            annotated_config: Annotated configuration dictionary
            
        Returns:
            String listing overridden keys (e.g., "imap.server, imap.port")
        """
        overridden_keys = []
        self._collect_overridden_keys(annotated_config, overridden_keys, "")
        return ", ".join(overridden_keys) if overridden_keys else ""
    
    def _collect_overridden_keys(
        self,
        annotated_config: Dict[str, Any],
        overridden_keys: list[str],
        prefix: str
    ) -> None:
        """
        Recursively collect keys that are overridden (source == ACCOUNT).
        
        Args:
            annotated_config: Annotated configuration dictionary
            overridden_keys: List to append overridden key paths to
            prefix: Current path prefix (e.g., "imap.")
        """
        for key, item in annotated_config.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(item, dict) and 'value' in item and 'source' in item:
                source = item['source']
                if isinstance(source, ConfigSource) and source == ConfigSource.ACCOUNT:
                    overridden_keys.append(current_path)
                
                value = item['value']
                if isinstance(value, dict):
                    # Recursively check nested dict
                    self._collect_overridden_keys(value, overridden_keys, current_path)
            elif isinstance(item, dict):
                # Nested dict (not annotated wrapper) - recurse
                self._collect_overridden_keys(item, overridden_keys, current_path)
