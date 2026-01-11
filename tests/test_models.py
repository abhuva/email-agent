"""
Tests for models module (Task 4).

Tests EmailContext dataclass structure, defaults, helper methods, and pipeline usage.
"""
import pytest
from src.models import EmailContext, from_imap_dict


class TestEmailContextStructure:
    """Tests for EmailContext dataclass structure and initialization."""
    
    def test_required_fields_must_be_provided(self):
        """Test that required fields (uid, sender, subject) must be provided."""
        # Should work with all required fields
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test Subject"
        )
        assert context.uid == "12345"
        assert context.sender == "test@example.com"
        assert context.subject == "Test Subject"
    
    def test_required_fields_cannot_be_omitted(self):
        """Test that omitting required fields raises TypeError."""
        with pytest.raises(TypeError):
            EmailContext(uid="12345", sender="test@example.com")
            # Missing subject
    
    def test_optional_fields_have_defaults(self):
        """Test that optional fields have sensible defaults."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test Subject"
        )
        # Optional raw content
        assert context.raw_html is None
        assert context.raw_text is None
        # State flags
        assert context.parsed_body is None
        assert context.is_html_fallback is False
        # Classification
        assert context.llm_score is None
        assert context.llm_tags == []
        # Rules
        assert context.whitelist_boost == 0.0
        assert context.whitelist_tags == []
        assert context.result_action is None
    
    def test_list_fields_use_default_factory(self):
        """Test that list fields use default_factory to avoid shared mutable defaults."""
        context1 = EmailContext(
            uid="1",
            sender="test@example.com",
            subject="Test 1"
        )
        context2 = EmailContext(
            uid="2",
            sender="test@example.com",
            subject="Test 2"
        )
        
        # Modifying one should not affect the other
        context1.llm_tags.append("tag1")
        context2.llm_tags.append("tag2")
        
        assert context1.llm_tags == ["tag1"]
        assert context2.llm_tags == ["tag2"]
        assert context1.whitelist_tags == []
        assert context2.whitelist_tags == []
    
    def test_all_fields_can_be_set_at_construction(self):
        """Test that all fields can be set during construction."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test Subject",
            raw_html="<p>HTML</p>",
            raw_text="Plain text",
            parsed_body="Parsed markdown",
            is_html_fallback=True,
            llm_score=8.5,
            llm_tags=["important", "work"],
            whitelist_boost=2.0,
            whitelist_tags=["vip"],
            result_action="PROCESSED"
        )
        assert context.raw_html == "<p>HTML</p>"
        assert context.raw_text == "Plain text"
        assert context.parsed_body == "Parsed markdown"
        assert context.is_html_fallback is True
        assert context.llm_score == 8.5
        assert context.llm_tags == ["important", "work"]
        assert context.whitelist_boost == 2.0
        assert context.whitelist_tags == ["vip"]
        assert context.result_action == "PROCESSED"
    
    def test_repr_excludes_large_fields(self):
        """Test that repr excludes large fields (raw_html, raw_text) for readability."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test Subject",
            raw_html="<p>" + "x" * 1000 + "</p>",  # Large HTML
            raw_text="y" * 1000  # Large text
        )
        repr_str = repr(context)
        # Should not include the large content in repr
        assert "x" * 100 not in repr_str
        assert "y" * 100 not in repr_str
        # But should include key fields
        assert "12345" in repr_str
        assert "test@example.com" in repr_str
        assert "Test Subject" in repr_str


class TestEmailContextHelperMethods:
    """Tests for EmailContext helper methods."""
    
    def test_add_llm_tag(self):
        """Test adding LLM tags without duplicates."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test"
        )
        assert context.llm_tags == []
        
        context.add_llm_tag("important")
        assert context.llm_tags == ["important"]
        
        context.add_llm_tag("work")
        assert context.llm_tags == ["important", "work"]
        
        # Adding duplicate should not add again
        context.add_llm_tag("important")
        assert context.llm_tags == ["important", "work"]
    
    def test_add_llm_tag_ignores_empty_strings(self):
        """Test that empty strings are not added as tags."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test"
        )
        context.add_llm_tag("")
        context.add_llm_tag(None)  # Should handle None gracefully
        assert context.llm_tags == []
    
    def test_add_whitelist_tag(self):
        """Test adding whitelist tags and boost."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test"
        )
        assert context.whitelist_tags == []
        assert context.whitelist_boost == 0.0
        
        context.add_whitelist_tag("vip")
        assert context.whitelist_tags == ["vip"]
        assert context.whitelist_boost == 0.0  # No boost specified
        
        context.add_whitelist_tag("client", boost=5.0)
        assert context.whitelist_tags == ["vip", "client"]
        assert context.whitelist_boost == 5.0
        
        # Adding another tag with boost should accumulate
        context.add_whitelist_tag("important", boost=3.0)
        assert context.whitelist_tags == ["vip", "client", "important"]
        assert context.whitelist_boost == 8.0
    
    def test_add_whitelist_tag_prevents_duplicates(self):
        """Test that duplicate whitelist tags are not added."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test"
        )
        context.add_whitelist_tag("vip")
        context.add_whitelist_tag("vip")  # Duplicate
        assert context.whitelist_tags == ["vip"]
    
    def test_is_scored(self):
        """Test is_scored helper method."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test"
        )
        assert context.is_scored() is False
        
        context.llm_score = 8.5
        assert context.is_scored() is True
        
        context.llm_score = 0.0
        assert context.is_scored() is True  # 0.0 is still a score
    
    def test_has_result(self):
        """Test has_result helper method."""
        context = EmailContext(
            uid="12345",
            sender="test@example.com",
            subject="Test"
        )
        assert context.has_result() is False
        
        context.result_action = "PROCESSED"
        assert context.has_result() is True
        
        context.result_action = "DROPPED"
        assert context.has_result() is True


class TestFromImapDict:
    """Tests for from_imap_dict conversion function."""
    
    def test_converts_basic_imap_dict(self):
        """Test conversion from basic IMAP dictionary."""
        email_dict = {
            'uid': '12345',
            'subject': 'Test Email',
            'from': 'sender@example.com',
            'body': 'Plain text body',
            'html_body': '<p>HTML body</p>'
        }
        context = from_imap_dict(email_dict)
        
        assert context.uid == '12345'
        assert context.subject == 'Test Email'
        assert context.sender == 'sender@example.com'
        assert context.raw_text == 'Plain text body'
        assert context.raw_html == '<p>HTML body</p>'
    
    def test_handles_sender_field_variations(self):
        """Test that it handles both 'from' and 'sender' fields."""
        # Test with 'from' field
        email_dict1 = {
            'uid': '1',
            'subject': 'Test',
            'from': 'from@example.com'
        }
        context1 = from_imap_dict(email_dict1)
        assert context1.sender == 'from@example.com'
        
        # Test with 'sender' field (preferred)
        email_dict2 = {
            'uid': '2',
            'subject': 'Test',
            'sender': 'sender@example.com'
        }
        context2 = from_imap_dict(email_dict2)
        assert context2.sender == 'sender@example.com'
        
        # Test with both (sender should take precedence)
        email_dict3 = {
            'uid': '3',
            'subject': 'Test',
            'from': 'from@example.com',
            'sender': 'sender@example.com'
        }
        context3 = from_imap_dict(email_dict3)
        assert context3.sender == 'sender@example.com'
    
    def test_handles_missing_optional_fields(self):
        """Test conversion when optional fields are missing."""
        email_dict = {
            'uid': '12345',
            'subject': 'Test Email',
            'from': 'sender@example.com'
            # No body, html_body, etc.
        }
        context = from_imap_dict(email_dict)
        
        assert context.uid == '12345'
        assert context.subject == 'Test Email'
        assert context.sender == 'sender@example.com'
        assert context.raw_html is None
        assert context.raw_text is None
    
    def test_handles_empty_strings(self):
        """Test conversion with empty string values."""
        email_dict = {
            'uid': '12345',
            'subject': '',
            'from': '',
            'body': '',
            'html_body': ''
        }
        context = from_imap_dict(email_dict)
        
        assert context.uid == '12345'
        assert context.subject == ''
        assert context.sender == ''
        assert context.raw_text == ''
        assert context.raw_html == ''
    
    def test_handles_alternative_field_names(self):
        """Test that it handles alternative field names (raw_html, raw_text)."""
        email_dict = {
            'uid': '12345',
            'subject': 'Test',
            'from': 'sender@example.com',
            'raw_html': '<p>HTML</p>',
            'raw_text': 'Plain text'
        }
        context = from_imap_dict(email_dict)
        
        assert context.raw_html == '<p>HTML</p>'
        assert context.raw_text == 'Plain text'
    
    def test_provides_defaults_for_missing_required_fields(self):
        """Test that missing required fields get default values."""
        email_dict = {
            'uid': '',  # Empty but present
            # Missing subject and from
        }
        context = from_imap_dict(email_dict)
        
        assert context.uid == ''
        assert context.subject == '[No Subject]'
        assert context.sender == '[Unknown Sender]'


class TestEmailContextPipelineUsage:
    """Integration-style tests for EmailContext through pipeline stages."""
    
    def test_pipeline_state_transitions(self):
        """Test that EmailContext correctly tracks state through pipeline stages."""
        # Stage 1: Initial construction from IMAP
        email_dict = {
            'uid': '12345',
            'subject': 'Important Meeting',
            'from': 'boss@company.com',
            'html_body': '<p>Meeting at 3pm</p>',
            'body': 'Meeting at 3pm'
        }
        context = from_imap_dict(email_dict)
        
        assert context.uid == '12345'
        assert context.parsed_body is None
        assert not context.is_scored()
        assert not context.has_result()
        
        # Stage 2: Content parsing (simulated)
        context.parsed_body = "Meeting at 3pm"
        context.is_html_fallback = False
        assert context.parsed_body is not None
        
        # Stage 3: LLM classification (simulated)
        context.llm_score = 9.0
        context.add_llm_tag("important")
        context.add_llm_tag("work")
        assert context.is_scored()
        assert context.llm_score == 9.0
        assert context.llm_tags == ["important", "work"]
        
        # Stage 4: Whitelist rules (simulated)
        context.add_whitelist_tag("vip", boost=2.0)
        assert context.whitelist_tags == ["vip"]
        assert context.whitelist_boost == 2.0
        
        # Stage 5: Final action
        context.result_action = "PROCESSED"
        assert context.has_result()
        assert context.result_action == "PROCESSED"
    
    def test_pipeline_with_html_fallback(self):
        """Test pipeline flow when HTML parsing fails and fallback is used."""
        email_dict = {
            'uid': '12345',
            'subject': 'Test',
            'from': 'test@example.com',
            'html_body': '<p>Broken HTML',
            'body': 'Plain text fallback'
        }
        context = from_imap_dict(email_dict)
        
        # Simulate HTML parsing failure
        context.parsed_body = "Plain text fallback"
        context.is_html_fallback = True
        
        assert context.is_html_fallback is True
        assert context.parsed_body == "Plain text fallback"
    
    def test_pipeline_with_blacklist_drop(self):
        """Test pipeline flow when email is dropped by blacklist."""
        email_dict = {
            'uid': '12345',
            'subject': 'Spam',
            'from': 'spam@spam.com'
        }
        context = from_imap_dict(email_dict)
        
        # Simulate blacklist check - email dropped before processing
        context.result_action = "DROPPED"
        
        assert context.has_result()
        assert context.result_action == "DROPPED"
        # Should not have been processed further
        assert not context.is_scored()
        assert context.parsed_body is None
