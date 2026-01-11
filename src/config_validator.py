"""
V4 Configuration Schema Validator

This module provides a reusable validation engine that can take a loaded config
object and the schema definition and return structured validation results
(success, warnings, and errors).

The validator performs:
- Per-field validation: existence of required fields, type checks, default value
  filling (if supported), and basic constraints (min/max, enum, regex, etc.)
- Schema-level validation hooks for cross-field rules if needed
- Structured error and warning reporting with path/key, error code, message, and value
"""
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from src.config_schema import SchemaDefinition, get_v4_config_schema

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """
    Represents a single validation issue (error or warning).
    
    Attributes:
        path: Dot-separated path to the configuration key (e.g., 'imap.port')
        error_code: Short error code identifier (e.g., 'MISSING_REQUIRED', 'INVALID_TYPE')
        message: Human-readable error message
        value: The actual value that caused the issue (if available)
        severity: 'error' or 'warning'
    """
    path: str
    error_code: str
    message: str
    value: Any = None
    severity: str = 'error'  # 'error' or 'warning'
    
    def __str__(self) -> str:
        """Return a human-readable representation of the issue."""
        value_str = f" (value: {repr(self.value)})" if self.value is not None else ""
        return f"{self.severity.upper()}[{self.error_code}] {self.path}: {self.message}{value_str}"


@dataclass
class ValidationResult:
    """
    Result object containing validation status, errors, and warnings.
    
    Attributes:
        is_valid: True if validation passed (no errors, warnings may exist)
        errors: List of validation errors (fatal issues)
        warnings: List of validation warnings (non-fatal issues)
        normalized_config: Optional normalized config with defaults applied
    """
    is_valid: bool = True
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    normalized_config: Optional[Dict] = None
    
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are any validation warnings."""
        return len(self.warnings) > 0
    
    def get_all_issues(self) -> List[ValidationIssue]:
        """Get all issues (errors and warnings) combined."""
        return self.errors + self.warnings
    
    def __str__(self) -> str:
        """Return a human-readable summary of the validation result."""
        status = "VALID" if self.is_valid else "INVALID"
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        return f"ValidationResult({status}, {error_count} errors, {warning_count} warnings)"


class ConfigSchemaValidator:
    """
    Validator component that validates configuration dictionaries against a schema.
    
    This validator:
    - Checks for required fields
    - Validates field types
    - Applies constraints (min/max, enum, regex, etc.)
    - Returns structured validation results with errors and warnings
    """
    
    def __init__(self, schema: Optional[SchemaDefinition] = None):
        """
        Initialize the validator with a schema.
        
        Args:
            schema: Schema definition to use for validation.
                   If None, uses the default V4 schema from get_v4_config_schema()
        """
        self.schema = schema if schema is not None else get_v4_config_schema()
    
    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate a configuration dictionary against the schema.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            ValidationResult containing validation status, errors, and warnings
        """
        result = ValidationResult()
        normalized = {}
        
        # Validate each section in the schema
        for section_name, section_def in self.schema.items():
            section_path = section_name
            section_config = config.get(section_name)
            
            # Check if required section is missing
            if section_def.get('required', False) and section_config is None:
                result.errors.append(ValidationIssue(
                    path=section_path,
                    error_code='MISSING_REQUIRED_SECTION',
                    message=f"Required section '{section_name}' is missing",
                    severity='error'
                ))
                continue
            
            # If section is not present and not required, skip it
            if section_config is None:
                continue
            
            # Validate section is a dictionary
            if not isinstance(section_config, dict):
                result.errors.append(ValidationIssue(
                    path=section_path,
                    error_code='INVALID_SECTION_TYPE',
                    message=f"Section '{section_name}' must be a dictionary, got {type(section_config).__name__}",
                    value=section_config,
                    severity='error'
                ))
                continue
            
            # Validate fields in the section
            normalized_section = {}
            for field_name, field_def in section_def.get('fields', {}).items():
                field_path = f"{section_path}.{field_name}"
                field_value = section_config.get(field_name)
                
                # Check if required field is missing
                if field_def.get('required', False) and field_value is None:
                    result.errors.append(ValidationIssue(
                        path=field_path,
                        error_code='MISSING_REQUIRED_FIELD',
                        message=f"Required field '{field_name}' is missing",
                        severity='error'
                    ))
                    continue
                
                # If field is not present and not required, use default if available
                if field_value is None:
                    if 'default' in field_def:
                        field_value = field_def['default']
                        normalized_section[field_name] = field_value
                    continue
                
                # Validate field type
                expected_type = field_def.get('type')
                type_valid, type_issue = self._validate_type(
                    field_path, field_value, expected_type
                )
                if not type_valid:
                    result.errors.append(type_issue)
                    continue
                
                # Validate field constraints
                constraints = field_def.get('constraints', {})
                constraint_issues = self._validate_constraints(
                    field_path, field_value, constraints
                )
                for issue in constraint_issues:
                    if issue.severity == 'error':
                        result.errors.append(issue)
                    else:
                        result.warnings.append(issue)
                
                # Add validated field to normalized config
                normalized_section[field_name] = field_value
            
            # Add normalized section to normalized config
            if normalized_section or section_config:
                normalized[section_name] = normalized_section if normalized_section else section_config
        
        # Determine overall validity (valid if no errors)
        result.is_valid = not result.has_errors()
        
        # Set normalized config (merge validated fields with original config)
        if normalized:
            # Merge normalized with original to preserve fields not in schema
            result.normalized_config = {**config, **normalized}
        else:
            result.normalized_config = config.copy() if config else {}
        
        return result
    
    def _validate_type(
        self, 
        path: str, 
        value: Any, 
        expected_type: Union[type, Tuple[type, ...]]
    ) -> Tuple[bool, Optional[ValidationIssue]]:
        """
        Validate that a value matches the expected type.
        
        Args:
            path: Path to the field being validated
            value: Value to validate
            expected_type: Expected type or tuple of allowed types
            
        Returns:
            Tuple of (is_valid, ValidationIssue or None)
        """
        if expected_type is None:
            return True, None
        
        # Handle tuple of types (union types)
        if isinstance(expected_type, tuple):
            if any(isinstance(value, t) for t in expected_type):
                return True, None
            type_names = [t.__name__ if t is not type(None) else 'None' for t in expected_type]
            type_str = ' | '.join(type_names)
        else:
            if isinstance(value, expected_type):
                return True, None
            type_str = expected_type.__name__
        
        return False, ValidationIssue(
            path=path,
            error_code='INVALID_TYPE',
            message=f"Expected type {type_str}, got {type(value).__name__}",
            value=value,
            severity='error'
        )
    
    def _validate_constraints(
        self, 
        path: str, 
        value: Any, 
        constraints: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """
        Validate field constraints (min, max, enum, regex, etc.).
        
        Args:
            path: Path to the field being validated
            value: Value to validate
            constraints: Dictionary of constraint definitions
            
        Returns:
            List of ValidationIssue objects (empty if all constraints pass)
        """
        issues = []
        
        # Min/Max for numeric values
        if isinstance(value, (int, float)):
            if 'min' in constraints:
                min_val = constraints['min']
                if value < min_val:
                    issues.append(ValidationIssue(
                        path=path,
                        error_code='VALUE_BELOW_MIN',
                        message=f"Value {value} is below minimum {min_val}",
                        value=value,
                        severity='error'
                    ))
            
            if 'max' in constraints:
                max_val = constraints['max']
                if value > max_val:
                    issues.append(ValidationIssue(
                        path=path,
                        error_code='VALUE_ABOVE_MAX',
                        message=f"Value {value} is above maximum {max_val}",
                        value=value,
                        severity='error'
                    ))
        
        # Min/Max length for strings and lists
        if isinstance(value, (str, list)):
            if 'min_length' in constraints:
                min_len = constraints['min_length']
                if len(value) < min_len:
                    issues.append(ValidationIssue(
                        path=path,
                        error_code='LENGTH_BELOW_MIN',
                        message=f"Length {len(value)} is below minimum {min_len}",
                        value=value,
                        severity='error'
                    ))
            
            if 'max_length' in constraints:
                max_len = constraints['max_length']
                if len(value) > max_len:
                    issues.append(ValidationIssue(
                        path=path,
                        error_code='LENGTH_ABOVE_MAX',
                        message=f"Length {len(value)} is above maximum {max_len}",
                        value=value,
                        severity='error'
                    ))
        
        # Enum validation
        if 'enum' in constraints:
            allowed_values = constraints['enum']
            if value not in allowed_values:
                issues.append(ValidationIssue(
                    path=path,
                    error_code='VALUE_NOT_IN_ENUM',
                    message=f"Value {repr(value)} is not in allowed values: {allowed_values}",
                    value=value,
                    severity='error'
                ))
        
        # Regex validation for strings
        if isinstance(value, str) and 'regex' in constraints:
            import re
            pattern = constraints['regex']
            if not re.match(pattern, value):
                issues.append(ValidationIssue(
                    path=path,
                    error_code='VALUE_DOES_NOT_MATCH_REGEX',
                    message=f"Value does not match required pattern: {pattern}",
                    value=value,
                    severity='error'
                ))
        
        # Item type validation for lists
        if isinstance(value, list) and 'item_type' in constraints:
            expected_item_type = constraints['item_type']
            for i, item in enumerate(value):
                if not isinstance(item, expected_item_type):
                    issues.append(ValidationIssue(
                        path=f"{path}[{i}]",
                        error_code='INVALID_ITEM_TYPE',
                        message=f"List item must be {expected_item_type.__name__}, got {type(item).__name__}",
                        value=item,
                        severity='error'
                    ))
        
        # Custom validator function
        if 'validator' in constraints:
            validator_func = constraints['validator']
            if callable(validator_func):
                try:
                    if not validator_func(value):
                        issues.append(ValidationIssue(
                            path=path,
                            error_code='CUSTOM_VALIDATION_FAILED',
                            message="Value failed custom validation",
                            value=value,
                            severity='error'
                        ))
                except Exception as e:
                    issues.append(ValidationIssue(
                        path=path,
                        error_code='VALIDATOR_EXCEPTION',
                        message=f"Validator raised exception: {e}",
                        value=value,
                        severity='error'
                    ))
        
        return issues
