"""
YAML frontmatter generation for Obsidian notes.

This module provides functions to extract email metadata and format it
as YAML frontmatter for Obsidian notes.
"""

import logging
import yaml
from datetime import datetime
from email.utils import parsedate_to_datetime, parseaddr
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def extract_email_metadata(email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract required metadata fields from email object with null defaults for missing fields.
    
    Args:
        email: Email dictionary with keys like 'subject', 'sender', 'date', etc.
               May also contain raw email message object in 'raw_message' key.
    
    Returns:
        Dictionary with keys: subject, from, to, cc, date, source_message_id
        Missing fields will be None.
    """
    metadata = {
        'subject': None,
        'from': None,
        'to': None,
        'cc': None,
        'date': None,
        'source_message_id': None
    }
    
    if not email:
        logger.warning("Empty email object provided to extract_email_metadata")
        return metadata
    
    # Extract subject
    metadata['subject'] = email.get('subject') or None
    
    # Extract from (sender)
    metadata['from'] = email.get('sender') or email.get('from') or None
    
    # Extract to (recipients)
    # Can be string or list
    to_value = email.get('to') or email.get('recipients')
    if to_value:
        if isinstance(to_value, str):
            # Parse comma-separated addresses
            metadata['to'] = [addr.strip() for addr in to_value.split(',') if addr.strip()]
        elif isinstance(to_value, list):
            metadata['to'] = [str(addr).strip() for addr in to_value if addr]
        else:
            metadata['to'] = [str(to_value)]
    else:
        metadata['to'] = []
    
    # Extract cc
    cc_value = email.get('cc')
    if cc_value:
        if isinstance(cc_value, str):
            metadata['cc'] = [addr.strip() for addr in cc_value.split(',') if addr.strip()]
        elif isinstance(cc_value, list):
            metadata['cc'] = [str(addr).strip() for addr in cc_value if addr]
        else:
            metadata['cc'] = [str(cc_value)]
    else:
        metadata['cc'] = []
    
    # Extract date (will be normalized in normalize_date)
    metadata['date'] = email.get('date') or None
    
    # Extract source_message_id (Message-ID header)
    metadata['source_message_id'] = email.get('message_id') or email.get('source_message_id') or None
    
    # If raw_message is available, extract additional fields
    raw_msg = email.get('raw_message')
    if raw_msg:
        try:
            # Extract To if not already present
            if not metadata['to']:
                to_header = raw_msg.get('To')
                if to_header:
                    if isinstance(to_header, str):
                        metadata['to'] = [addr.strip() for addr in to_header.split(',') if addr.strip()]
                    elif isinstance(to_header, list):
                        metadata['to'] = [str(addr).strip() for addr in to_header if addr]
            
            # Extract CC if not already present
            if not metadata['cc']:
                cc_header = raw_msg.get('CC') or raw_msg.get('Cc')
                if cc_header:
                    if isinstance(cc_header, str):
                        metadata['cc'] = [addr.strip() for addr in cc_header.split(',') if addr.strip()]
                    elif isinstance(cc_header, list):
                        metadata['cc'] = [str(addr).strip() for addr in cc_header if addr]
            
            # Extract Message-ID if not already present
            if not metadata['source_message_id']:
                msg_id = raw_msg.get('Message-ID') or raw_msg.get('Message-Id')
                if msg_id:
                    metadata['source_message_id'] = str(msg_id).strip()
            
            # Extract From if not already present
            if not metadata['from']:
                from_header = raw_msg.get('From')
                if from_header:
                    metadata['from'] = str(from_header).strip()
            
            # Extract Date if not already present
            if not metadata['date']:
                date_header = raw_msg.get('Date')
                if date_header:
                    metadata['date'] = str(date_header).strip()
        except Exception as e:
            logger.warning(f"Error extracting metadata from raw_message: {e}")
    
    return metadata


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parse various email date formats and normalize to ISO 8601 format.
    
    Handles common email date formats like RFC 2822 and converts them
    to ISO 8601 format (YYYY-MM-DDTHH:mm:ssZ) for YAML compatibility.
    
    Args:
        date_str: Date string in various formats (RFC 2822, ISO, etc.)
    
    Returns:
        ISO 8601 formatted date string, or None if parsing fails
    
    Examples:
        >>> normalize_date("Mon, 27 Oct 2023 10:00:00 +0000")
        '2023-10-27T10:00:00+00:00'
        >>> normalize_date("2023-10-27T10:00:00Z")
        '2023-10-27T10:00:00+00:00'
    """
    if not date_str:
        return None
    
    try:
        # Try parsing with email.utils.parsedate_to_datetime (handles RFC 2822)
        dt = parsedate_to_datetime(date_str)
        # Convert to ISO 8601 format with timezone
        return dt.isoformat()
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to parse date '{date_str}': {e}")
        # Try alternative parsing
        try:
            # Try parsing as ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.isoformat()
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date string: {date_str}")
            return None


def yaml_safe_string(value: Optional[str]) -> str:
    """
    Make a string safe for YAML by escaping special characters.
    
    Wraps strings containing colons, quotes, or other special characters
    in double quotes with proper escaping.
    
    Args:
        value: String value to make YAML-safe
    
    Returns:
        YAML-safe string representation
    
    Examples:
        >>> yaml_safe_string("Normal text")
        'Normal text'
        >>> yaml_safe_string("Text with: colon")
        '"Text with: colon"'
        >>> yaml_safe_string('Text with "quotes"')
        '"Text with \\"quotes\\""'
    """
    if value is None:
        return 'null'
    
    value_str = str(value)
    
    # Check if string needs quoting
    needs_quotes = False
    
    # Check for colon followed by non-space (YAML key-value separator)
    if ':' in value_str and not value_str.strip().startswith('http'):
        # Check if colon is in a context that needs quoting
        for i, char in enumerate(value_str):
            if char == ':' and i < len(value_str) - 1 and value_str[i + 1] != ' ':
                needs_quotes = True
                break
    
    # Check for quotes
    if '"' in value_str or "'" in value_str:
        needs_quotes = True
    
    # Check for special YAML characters
    if any(char in value_str for char in ['#', '@', '`', '|', '>', '&', '*', '!', '%', '?', '{', '}', '[', ']']):
        # Only quote if these appear in problematic contexts
        if ':' in value_str or '"' in value_str:
            needs_quotes = True
    
    # Check for leading/trailing whitespace
    if value_str != value_str.strip():
        needs_quotes = True
    
    if needs_quotes:
        # Escape double quotes and wrap in double quotes
        escaped = value_str.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    
    return value_str


def generate_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """
    Convert metadata dictionary into valid YAML frontmatter string.
    
    Produces YAML frontmatter with proper delimiters (---) and formatting.
    Handles null values, arrays, and special characters correctly.
    
    Args:
        metadata: Dictionary with keys: subject, from, to, cc, date, source_message_id
    
    Returns:
        YAML frontmatter string with --- delimiters
    
    Examples:
        >>> metadata = {'subject': 'Test', 'from': 'test@example.com', 'to': [], 'cc': [], 'date': None, 'source_message_id': None}
        >>> frontmatter = generate_yaml_frontmatter(metadata)
        >>> print(frontmatter)
        ---
        subject: Test
        from: test@example.com
        to: []
        cc: []
        date: null
        source_message_id: null
        ---
    """
    # Prepare data for YAML serialization
    yaml_data = {}
    
    # Normalize date
    if metadata.get('date'):
        normalized_date = normalize_date(metadata['date'])
        yaml_data['date'] = normalized_date
    else:
        yaml_data['date'] = None
    
    # Add other fields
    yaml_data['subject'] = metadata.get('subject')
    yaml_data['from'] = metadata.get('from')
    yaml_data['to'] = metadata.get('to', [])
    yaml_data['cc'] = metadata.get('cc', [])
    yaml_data['source_message_id'] = metadata.get('source_message_id')
    
    # Generate YAML using PyYAML
    # Use default_flow_style=False for block style (lists as - item)
    # Use allow_unicode=True to handle unicode characters
    yaml_str = yaml.dump(
        yaml_data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,  # Preserve order
        width=1000,  # Prevent line wrapping
        default_style=None  # Use default YAML style (quotes only when needed)
    )
    
    # Ensure proper delimiters
    # Remove any existing delimiters
    yaml_str = yaml_str.strip()
    if yaml_str.startswith('---'):
        yaml_str = yaml_str[3:].strip()
    if yaml_str.endswith('---'):
        yaml_str = yaml_str[:-3].strip()
    
    # Add delimiters with proper spacing
    frontmatter = f"---\n{yaml_str}\n---"
    
    return frontmatter


def generate_email_yaml_frontmatter(email: Dict[str, Any]) -> str:
    """
    Complete function to extract email metadata and generate YAML frontmatter.
    
    This is the main function to use for generating YAML frontmatter from email objects.
    
    Args:
        email: Email dictionary with subject, sender, date, etc.
    
    Returns:
        YAML frontmatter string ready to be inserted into Obsidian note
    
    Examples:
        >>> email = {'subject': 'Test Email', 'sender': 'test@example.com', 'date': 'Mon, 27 Oct 2023 10:00:00 +0000'}
        >>> frontmatter = generate_email_yaml_frontmatter(email)
        >>> print(frontmatter)
        ---
        subject: Test Email
        from: test@example.com
        ...
        ---
    """
    metadata = extract_email_metadata(email)
    # Normalize date in metadata
    if metadata.get('date'):
        metadata['date'] = normalize_date(metadata['date'])
    return generate_yaml_frontmatter(metadata)
