"""
Data models for email processing pipeline.

This module contains data classes that track email state through the processing pipeline.

Integration Pattern:
    EmailContext is designed to be passed through the V4 processing pipeline:
    
    1. Construction: Create EmailContext from IMAP data using from_imap_dict()
    2. Parsing: Content parser sets parsed_body and is_html_fallback
    3. LLM Classification: LLM client sets llm_score and llm_tags
    4. Whitelist Rules: Rules engine sets whitelist_boost and whitelist_tags
    5. Action Selection: Final stage sets result_action
    
    Example:
        # At IMAP fetch point:
        email_dict = imap_client.get_email_by_uid(uid)
        context = from_imap_dict(email_dict)
        
        # Through pipeline stages:
        context = content_parser.parse(context)  # Sets parsed_body
        context = llm_client.classify(context)   # Sets llm_score, llm_tags
        context = rules_engine.apply_whitelist(context)  # Sets whitelist_boost
        context.result_action = "PROCESSED"      # Final action
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class EmailContext:
    """
    Tracks email metadata and processing state through the pipeline.
    
    This class maintains all information about an email as it moves through
    the processing stages: parsing, LLM classification, whitelist/blacklist
    rules, and final action determination.
    
    Fields:
        uid: Email UID from IMAP server
        sender: Email sender address
        subject: Email subject line
        date: Email date from headers (RFC 2822 format)
        to: List of recipient email addresses
        cc: List of carbon copy recipient email addresses
        message_id: Message-ID header value
        raw_html: Raw HTML content of the email (if available)
        raw_text: Raw plain text content of the email (if available)
        parsed_body: Parsed/converted body content (Markdown after HTML conversion)
        is_html_fallback: Flag indicating if HTML parsing failed and plain text was used
        llm_score: LLM classification score (0-10 scale)
        llm_tags: List of tags assigned by LLM classification
        whitelist_boost: Score boost applied by whitelist rules
        whitelist_tags: List of tags added by whitelist rules
        result_action: Final action taken (e.g., "PROCESSED", "DROPPED", "RECORDED")
    """
    # Required fields (no defaults - must be provided at construction)
    uid: str
    sender: str
    subject: str
    
    # Email metadata (extracted from IMAP headers)
    date: Optional[str] = None
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    message_id: Optional[str] = None
    
    # Optional raw content (may not be available at instantiation)
    raw_html: Optional[str] = field(default=None, repr=False)  # Exclude from repr for readability
    raw_text: Optional[str] = field(default=None, repr=False)  # Exclude from repr for readability
    
    # State flags (pipeline-populated)
    parsed_body: Optional[str] = None
    is_html_fallback: bool = False
    
    # Classification (pipeline-populated)
    llm_score: Optional[float] = None
    llm_tags: List[str] = field(default_factory=list)
    
    # Rules (pipeline-populated)
    whitelist_boost: float = 0.0
    whitelist_tags: List[str] = field(default_factory=list)
    result_action: Optional[str] = None
    
    # Summarization (pipeline-populated, optional)
    summary: Optional[Dict[str, Any]] = None
    
    def add_llm_tag(self, tag: str) -> None:
        """
        Add a tag to the LLM tags list, preventing duplicates.
        
        Args:
            tag: Tag string to add
        """
        if tag and tag not in self.llm_tags:
            self.llm_tags.append(tag)
    
    def add_whitelist_tag(self, tag: str, boost: float = 0.0) -> None:
        """
        Add a whitelist tag and optionally adjust the whitelist boost.
        
        Args:
            tag: Tag string to add
            boost: Score boost to add (default: 0.0)
        """
        if tag and tag not in self.whitelist_tags:
            self.whitelist_tags.append(tag)
        if boost != 0.0:
            self.whitelist_boost += boost
    
    def is_scored(self) -> bool:
        """
        Check if the email has been scored by the LLM.
        
        Returns:
            True if llm_score is not None, False otherwise
        """
        return self.llm_score is not None
    
    def has_result(self) -> bool:
        """
        Check if a final action has been determined.
        
        Returns:
            True if result_action is not None, False otherwise
        """
        return self.result_action is not None


def from_imap_dict(email_dict: Dict[str, Any]) -> EmailContext:
    """
    Create an EmailContext instance from an IMAP email dictionary.
    
    This function converts the dictionary format returned by IMAP client methods
    (get_unprocessed_emails, get_email_by_uid) into an EmailContext instance.
    
    Extracts all available metadata including date, recipients (to/cc), and message_id.
    
    Args:
        email_dict: Dictionary with email data from IMAP client.
                   Expected keys: uid, subject, from/sender, body, html_body, date, to, cc, headers
    
    Returns:
        EmailContext instance with required fields populated
    
    Example:
        >>> email_dict = {
        ...     'uid': '12345',
        ...     'subject': 'Test Email',
        ...     'from': 'sender@example.com',
        ...     'date': 'Wed, 13 Sep 2023 14:34:53 +0200',
        ...     'to': ['recipient@example.com'],
        ...     'body': 'Plain text body',
        ...     'html_body': '<p>HTML body</p>'
        ... }
        >>> context = from_imap_dict(email_dict)
        >>> context.uid
        '12345'
        >>> context.date
        'Wed, 13 Sep 2023 14:34:53 +0200'
    """
    # Extract required fields
    uid = str(email_dict.get('uid', ''))
    subject = email_dict.get('subject', '[No Subject]')
    
    # Handle sender field (can be 'from' or 'sender')
    sender = email_dict.get('sender') or email_dict.get('from', '[Unknown Sender]')
    
    # Extract metadata fields
    date = email_dict.get('date') or None
    
    # Extract recipients (to field)
    to_value = email_dict.get('to', [])
    if isinstance(to_value, str):
        # Parse comma-separated addresses
        to_list = [addr.strip() for addr in to_value.split(',') if addr.strip()]
    elif isinstance(to_value, list):
        to_list = [str(addr).strip() for addr in to_value if addr]
    else:
        to_list = []
    
    # Extract CC recipients
    cc_value = email_dict.get('cc', [])
    if isinstance(cc_value, str):
        cc_list = [addr.strip() for addr in cc_value.split(',') if addr.strip()]
    elif isinstance(cc_value, list):
        cc_list = [str(addr).strip() for addr in cc_value if addr]
    else:
        cc_list = []
    
    # Extract Message-ID from headers if available
    message_id = None
    headers = email_dict.get('headers', {})
    if isinstance(headers, dict):
        message_id = headers.get('Message-ID') or headers.get('Message-Id') or None
        if message_id:
            message_id = str(message_id).strip()
    # Also check direct message_id field
    if not message_id:
        message_id = email_dict.get('message_id') or email_dict.get('source_message_id') or None
        if message_id:
            message_id = str(message_id).strip()
    
    # Extract raw content (use get with None default to distinguish empty strings from missing keys)
    raw_html = email_dict.get('html_body') if 'html_body' in email_dict else email_dict.get('raw_html')
    raw_text = email_dict.get('body') if 'body' in email_dict else email_dict.get('raw_text')
    
    return EmailContext(
        uid=uid,
        sender=str(sender),
        subject=str(subject),
        date=date,
        to=to_list,
        cc=cc_list,
        message_id=message_id,
        raw_html=raw_html,
        raw_text=raw_text
    )


__all__ = ['EmailContext', 'from_imap_dict']
