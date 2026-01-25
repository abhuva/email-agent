"""
Utility functions for building IMAP date-based queries.

This module provides functions to:
- Parse date strings in various formats
- Build IMAP SENTSINCE/SINCE queries with date filters
- Support dynamic date calculations (e.g., "last 7 days")
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


def parse_date_string(date_str: str) -> datetime:
    """
    Parse a date string in various formats to a datetime object.
    
    Supports formats like:
    - "02.02.2022" (DD.MM.YYYY)
    - "2022-02-02" (YYYY-MM-DD)
    - "02/02/2022" (DD/MM/YYYY or MM/DD/YYYY)
    - "2 Feb 2022" (natural language)
    - ISO format strings
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        datetime object
        
    Raises:
        ValueError: If date string cannot be parsed
        
    Examples:
        >>> parse_date_string("02.02.2022")
        datetime.datetime(2022, 2, 2, 0, 0)
        >>> parse_date_string("2022-02-02")
        datetime.datetime(2022, 2, 2, 0, 0)
    """
    # Try common formats first
    formats = [
        '%d.%m.%Y',      # 02.02.2022
        '%d-%m-%Y',      # 02-02-2022
        '%d/%m/%Y',      # 02/02/2022
        '%Y-%m-%d',      # 2022-02-02
        '%Y/%m/%d',      # 2022/02/02
        '%m/%d/%Y',      # 02/02/2022 (US format)
        '%d.%m.%y',      # 02.02.22
        '%d-%m-%y',      # 02-02-22
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    # Fallback to dateutil parser (handles natural language)
    try:
        return date_parser.parse(date_str.strip())
    except (ValueError, TypeError) as e:
        raise ValueError(f"Could not parse date string '{date_str}': {e}")


def format_imap_date(date: datetime) -> str:
    """
    Format a datetime object as IMAP date string (DD-MMM-YYYY).
    
    IMAP requires dates in format: DD-MMM-YYYY (e.g., "02-Feb-2022")
    
    Args:
        date: datetime object
        
    Returns:
        Formatted date string for IMAP queries
        
    Examples:
        >>> format_imap_date(datetime(2022, 2, 2))
        '02-Feb-2022'
    """
    return date.strftime('%d-%b-%Y')


def build_imap_date_query(
    base_query: str = 'ALL',
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    use_sentsince: bool = True
) -> str:
    """
    Build an IMAP query with date filters.
    
    This function combines a base query with SENTSINCE/SINCE and/or SENTBEFORE/SENTON
    date filters. The date filters are combined using AND logic.
    
    Args:
        base_query: Base IMAP query (default: 'ALL')
        after: Optional datetime - only emails sent/received after this date
        before: Optional datetime - only emails sent/received before this date
        use_sentsince: If True, use SENTSINCE (sent date), else use SINCE (received date)
        
    Returns:
        Combined IMAP query string
        
    Examples:
        >>> build_imap_date_query(after=datetime(2022, 2, 2))
        '(ALL SENTSINCE 02-Feb-2022)'
        >>> build_imap_date_query(after=datetime(2022, 2, 2), before=datetime(2022, 2, 10))
        '(ALL SENTSINCE 02-Feb-2022 SENTBEFORE 10-Feb-2022)'
    """
    query_parts = [base_query]
    
    if after:
        date_keyword = 'SENTSINCE' if use_sentsince else 'SINCE'
        date_str = format_imap_date(after)
        query_parts.append(f"{date_keyword} {date_str}")
    
    if before:
        # IMAP uses SENTBEFORE for sent date, but there's no standard BEFORE for received date
        # For consistency, we'll use SENTBEFORE when use_sentsince=True
        if use_sentsince:
            date_str = format_imap_date(before)
            query_parts.append(f"SENTBEFORE {date_str}")
        else:
            # For received date, we can use SENTBEFORE as a workaround or use ON with date range
            # Most IMAP servers support SENTBEFORE even for received date filtering
            date_str = format_imap_date(before)
            query_parts.append(f"SENTBEFORE {date_str}")
    
    # Combine parts with spaces and wrap in parentheses if multiple parts
    if len(query_parts) > 1:
        return f"({' '.join(query_parts)})"
    else:
        return query_parts[0]


def build_dynamic_date_query(
    days: int,
    base_query: str = 'ALL',
    use_sentsince: bool = True
) -> str:
    """
    Build an IMAP query for emails from the last N days.
    
    This is a convenience function that calculates the date N days ago
    and builds a query using that date.
    
    Args:
        days: Number of days to look back (e.g., 7 for last 7 days)
        base_query: Base IMAP query (default: 'ALL')
        use_sentsince: If True, use SENTSINCE (sent date), else use SINCE (received date)
        
    Returns:
        IMAP query string with date filter
        
    Examples:
        >>> build_dynamic_date_query(7)
        '(ALL SENTSINCE 15-Jan-2026)'  # Assuming today is 22-Jan-2026
    """
    date_n_days_ago = datetime.now() - timedelta(days=days)
    return build_imap_date_query(
        base_query=base_query,
        after=date_n_days_ago,
        use_sentsince=use_sentsince
    )
