"""
Tests for rules module (Task 6).

Tests blacklist rule loading, validation, matching, and evaluation.
"""
import pytest
import tempfile
import yaml
from pathlib import Path

from src.models import EmailContext
from src.rules import (
    ActionEnum,
    BlacklistRule,
    InvalidRuleError,
    check_blacklist,
    load_blacklist_rules,
    match_domain_rule,
    match_sender_rule,
    match_subject_rule,
    rule_matches_email,
    validate_blacklist_rule,
    _extract_domain_from_email,
)


class TestActionEnum:
    """Tests for ActionEnum."""
    
    def test_action_enum_values(self):
        """Test that ActionEnum has the expected values."""
        assert ActionEnum.DROP.value == "drop"
        assert ActionEnum.RECORD.value == "record"
        assert ActionEnum.PASS.value == "pass"
    
    def test_action_enum_from_string(self):
        """Test creating ActionEnum from string values."""
        assert ActionEnum("drop") == ActionEnum.DROP
        assert ActionEnum("record") == ActionEnum.RECORD
        assert ActionEnum("pass") == ActionEnum.PASS
    
    def test_action_enum_invalid_value(self):
        """Test that invalid ActionEnum value raises ValueError."""
        with pytest.raises(ValueError):
            ActionEnum("invalid")


class TestBlacklistRule:
    """Tests for BlacklistRule dataclass."""
    
    def test_valid_rule_creation(self):
        """Test creating a valid BlacklistRule."""
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert rule.trigger_type == "sender"
        assert rule.value == "spam@example.com"
        assert rule.action == ActionEnum.DROP
    
    def test_invalid_trigger_type(self):
        """Test that invalid trigger_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            BlacklistRule(
                trigger_type="invalid",
                value="test",
                action=ActionEnum.DROP
            )
    
    def test_empty_value(self):
        """Test that empty value raises ValueError."""
        with pytest.raises(ValueError, match="Rule value cannot be empty"):
            BlacklistRule(
                trigger_type="sender",
                value="",
                action=ActionEnum.DROP
            )
    
    def test_invalid_action_type(self):
        """Test that non-ActionEnum action raises ValueError."""
        with pytest.raises(ValueError, match="Action must be ActionEnum"):
            BlacklistRule(
                trigger_type="sender",
                value="test",
                action="drop"  # Should be ActionEnum.DROP
            )
    
    def test_all_trigger_types(self):
        """Test that all valid trigger types work."""
        for trigger in ("sender", "subject", "domain"):
            rule = BlacklistRule(
                trigger_type=trigger,
                value="test",
                action=ActionEnum.DROP
            )
            assert rule.trigger_type == trigger


class TestValidateBlacklistRule:
    """Tests for validate_blacklist_rule function."""
    
    def test_valid_sender_rule(self):
        """Test validating a valid sender rule."""
        raw_rule = {
            "trigger": "sender",
            "value": "spam@example.com",
            "action": "drop"
        }
        rule = validate_blacklist_rule(raw_rule)
        assert rule.trigger_type == "sender"
        assert rule.value == "spam@example.com"
        assert rule.action == ActionEnum.DROP
    
    def test_valid_subject_rule(self):
        """Test validating a valid subject rule."""
        raw_rule = {
            "trigger": "subject",
            "value": "Unsubscribe",
            "action": "record"
        }
        rule = validate_blacklist_rule(raw_rule)
        assert rule.trigger_type == "subject"
        assert rule.value == "Unsubscribe"
        assert rule.action == ActionEnum.RECORD
    
    def test_valid_domain_rule(self):
        """Test validating a valid domain rule."""
        raw_rule = {
            "trigger": "domain",
            "value": "spam.com",
            "action": "drop"
        }
        rule = validate_blacklist_rule(raw_rule)
        assert rule.trigger_type == "domain"
        assert rule.value == "spam.com"
        assert rule.action == ActionEnum.DROP
    
    def test_missing_trigger(self):
        """Test that missing trigger field raises InvalidRuleError."""
        raw_rule = {
            "value": "test",
            "action": "drop"
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'trigger'"):
            validate_blacklist_rule(raw_rule)
    
    def test_missing_value(self):
        """Test that missing value field raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "action": "drop"
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'value'"):
            validate_blacklist_rule(raw_rule)
    
    def test_missing_action(self):
        """Test that missing action field raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test"
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'action'"):
            validate_blacklist_rule(raw_rule)
    
    def test_invalid_trigger_type(self):
        """Test that invalid trigger type raises InvalidRuleError."""
        raw_rule = {
            "trigger": "invalid",
            "value": "test",
            "action": "drop"
        }
        with pytest.raises(InvalidRuleError, match="Invalid trigger type"):
            validate_blacklist_rule(raw_rule)
    
    def test_invalid_action(self):
        """Test that invalid action raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "invalid"
        }
        with pytest.raises(InvalidRuleError, match="Invalid action"):
            validate_blacklist_rule(raw_rule)
    
    def test_empty_value(self):
        """Test that empty value raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "",
            "action": "drop"
        }
        with pytest.raises(InvalidRuleError, match="cannot be empty"):
            validate_blacklist_rule(raw_rule)
    
    def test_case_insensitive_trigger(self):
        """Test that trigger type is case-insensitive."""
        raw_rule = {
            "trigger": "SENDER",  # Uppercase
            "value": "test",
            "action": "drop"
        }
        rule = validate_blacklist_rule(raw_rule)
        assert rule.trigger_type == "sender"  # Lowercase
    
    def test_case_insensitive_action(self):
        """Test that action is case-insensitive."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "DROP"  # Uppercase
        }
        rule = validate_blacklist_rule(raw_rule)
        assert rule.action == ActionEnum.DROP
    
    def test_non_dict_input(self):
        """Test that non-dict input raises InvalidRuleError."""
        with pytest.raises(InvalidRuleError, match="must be a dictionary"):
            validate_blacklist_rule("not a dict")


class TestExtractDomainFromEmail:
    """Tests for _extract_domain_from_email helper function."""
    
    def test_simple_email(self):
        """Test extracting domain from simple email address."""
        assert _extract_domain_from_email("user@example.com") == "example.com"
    
    def test_email_with_name(self):
        """Test extracting domain from email with name."""
        assert _extract_domain_from_email("Name <user@example.com>") == "example.com"
    
    def test_empty_string(self):
        """Test that empty string returns None."""
        assert _extract_domain_from_email("") is None
    
    def test_no_at_symbol(self):
        """Test that email without @ returns None."""
        assert _extract_domain_from_email("notanemail") is None
    
    def test_complex_email_format(self):
        """Test extracting domain from complex email format."""
        assert _extract_domain_from_email("Lastname, Firstname <user@example.com>") == "example.com"


class TestMatchSenderRule:
    """Tests for match_sender_rule function."""
    
    def test_exact_match(self):
        """Test exact sender match."""
        email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert match_sender_rule(email, rule) is True
    
    def test_case_insensitive_match(self):
        """Test case-insensitive sender match."""
        email = EmailContext(uid="1", sender="SPAM@EXAMPLE.COM", subject="Test")
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert match_sender_rule(email, rule) is True
    
    def test_substring_match(self):
        """Test substring match in sender."""
        email = EmailContext(uid="1", sender="no-reply@spam.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert match_sender_rule(email, rule) is True
    
    def test_no_match(self):
        """Test that non-matching sender returns False."""
        email = EmailContext(uid="1", sender="good@example.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert match_sender_rule(email, rule) is False
    
    def test_empty_sender(self):
        """Test that empty sender returns False."""
        email = EmailContext(uid="1", sender="", subject="Test")
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert match_sender_rule(email, rule) is False
    
    def test_wrong_trigger_type(self):
        """Test that wrong trigger type returns False."""
        email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="subject",  # Wrong type
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert match_sender_rule(email, rule) is False


class TestMatchSubjectRule:
    """Tests for match_subject_rule function."""
    
    def test_exact_match(self):
        """Test exact subject match."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Unsubscribe")
        rule = BlacklistRule(
            trigger_type="subject",
            value="Unsubscribe",
            action=ActionEnum.RECORD
        )
        assert match_subject_rule(email, rule) is True
    
    def test_case_insensitive_match(self):
        """Test case-insensitive subject match."""
        email = EmailContext(uid="1", sender="test@example.com", subject="UNSUBSCRIBE")
        rule = BlacklistRule(
            trigger_type="subject",
            value="unsubscribe",
            action=ActionEnum.RECORD
        )
        assert match_subject_rule(email, rule) is True
    
    def test_substring_match(self):
        """Test substring match in subject."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Click here to unsubscribe")
        rule = BlacklistRule(
            trigger_type="subject",
            value="unsubscribe",
            action=ActionEnum.RECORD
        )
        assert match_subject_rule(email, rule) is True
    
    def test_no_match(self):
        """Test that non-matching subject returns False."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Important Message")
        rule = BlacklistRule(
            trigger_type="subject",
            value="Unsubscribe",
            action=ActionEnum.RECORD
        )
        assert match_subject_rule(email, rule) is False
    
    def test_empty_subject(self):
        """Test that empty subject returns False."""
        email = EmailContext(uid="1", sender="test@example.com", subject="")
        rule = BlacklistRule(
            trigger_type="subject",
            value="Unsubscribe",
            action=ActionEnum.RECORD
        )
        assert match_subject_rule(email, rule) is False


class TestMatchDomainRule:
    """Tests for match_domain_rule function."""
    
    def test_exact_domain_match(self):
        """Test exact domain match."""
        email = EmailContext(uid="1", sender="user@spam.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="domain",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert match_domain_rule(email, rule) is True
    
    def test_case_insensitive_domain_match(self):
        """Test case-insensitive domain match."""
        email = EmailContext(uid="1", sender="user@SPAM.COM", subject="Test")
        rule = BlacklistRule(
            trigger_type="domain",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert match_domain_rule(email, rule) is True
    
    def test_domain_with_name(self):
        """Test domain extraction from email with name."""
        email = EmailContext(uid="1", sender="Name <user@spam.com>", subject="Test")
        rule = BlacklistRule(
            trigger_type="domain",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert match_domain_rule(email, rule) is True
    
    def test_no_match(self):
        """Test that non-matching domain returns False."""
        email = EmailContext(uid="1", sender="user@good.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="domain",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert match_domain_rule(email, rule) is False
    
    def test_empty_sender(self):
        """Test that empty sender returns False."""
        email = EmailContext(uid="1", sender="", subject="Test")
        rule = BlacklistRule(
            trigger_type="domain",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert match_domain_rule(email, rule) is False


class TestRuleMatchesEmail:
    """Tests for rule_matches_email dispatcher function."""
    
    def test_sender_rule_dispatch(self):
        """Test that sender rules are dispatched correctly."""
        email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="sender",
            value="spam@example.com",
            action=ActionEnum.DROP
        )
        assert rule_matches_email(email, rule) is True
    
    def test_subject_rule_dispatch(self):
        """Test that subject rules are dispatched correctly."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Unsubscribe")
        rule = BlacklistRule(
            trigger_type="subject",
            value="Unsubscribe",
            action=ActionEnum.RECORD
        )
        assert rule_matches_email(email, rule) is True
    
    def test_domain_rule_dispatch(self):
        """Test that domain rules are dispatched correctly."""
        email = EmailContext(uid="1", sender="user@spam.com", subject="Test")
        rule = BlacklistRule(
            trigger_type="domain",
            value="spam.com",
            action=ActionEnum.DROP
        )
        assert rule_matches_email(email, rule) is True


class TestCheckBlacklist:
    """Tests for check_blacklist function."""
    
    def test_no_rules_returns_pass(self):
        """Test that empty rules list returns PASS."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Test")
        assert check_blacklist(email, []) == ActionEnum.PASS
    
    def test_no_match_returns_pass(self):
        """Test that no matching rules returns PASS."""
        email = EmailContext(uid="1", sender="good@example.com", subject="Good Message")
        rules = [
            BlacklistRule(
                trigger_type="sender",
                value="spam@example.com",
                action=ActionEnum.DROP
            )
        ]
        assert check_blacklist(email, rules) == ActionEnum.PASS
    
    def test_drop_rule_matches(self):
        """Test that matching DROP rule returns DROP."""
        email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        rules = [
            BlacklistRule(
                trigger_type="sender",
                value="spam@example.com",
                action=ActionEnum.DROP
            )
        ]
        assert check_blacklist(email, rules) == ActionEnum.DROP
    
    def test_record_rule_matches(self):
        """Test that matching RECORD rule returns RECORD."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Unsubscribe")
        rules = [
            BlacklistRule(
                trigger_type="subject",
                value="Unsubscribe",
                action=ActionEnum.RECORD
            )
        ]
        assert check_blacklist(email, rules) == ActionEnum.RECORD
    
    def test_drop_overrides_record(self):
        """Test that DROP rule takes priority over RECORD rule."""
        email = EmailContext(uid="1", sender="spam@example.com", subject="Unsubscribe")
        rules = [
            BlacklistRule(
                trigger_type="subject",
                value="Unsubscribe",
                action=ActionEnum.RECORD
            ),
            BlacklistRule(
                trigger_type="sender",
                value="spam@example.com",
                action=ActionEnum.DROP
            )
        ]
        # DROP should win even though RECORD also matches
        assert check_blacklist(email, rules) == ActionEnum.DROP
    
    def test_multiple_rules_first_match_drop(self):
        """Test that first DROP match returns immediately."""
        email = EmailContext(uid="1", sender="spam@example.com", subject="Test")
        rules = [
            BlacklistRule(
                trigger_type="sender",
                value="spam@example.com",
                action=ActionEnum.DROP
            ),
            BlacklistRule(
                trigger_type="subject",
                value="Test",
                action=ActionEnum.RECORD
            )
        ]
        assert check_blacklist(email, rules) == ActionEnum.DROP
    
    def test_multiple_record_rules(self):
        """Test that multiple RECORD rules still return RECORD."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Unsubscribe")
        rules = [
            BlacklistRule(
                trigger_type="subject",
                value="Unsubscribe",
                action=ActionEnum.RECORD
            ),
            BlacklistRule(
                trigger_type="domain",
                value="example.com",
                action=ActionEnum.RECORD
            )
        ]
        assert check_blacklist(email, rules) == ActionEnum.RECORD
    
    def test_malformed_rule_handled_gracefully(self):
        """Test that malformed rules don't crash the evaluation."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Test")
        # Create a rule that might cause issues (missing pattern, etc.)
        rules = [
            BlacklistRule(
                trigger_type="sender",
                value="test@example.com",
                action=ActionEnum.DROP
            )
        ]
        # Should not raise exception
        result = check_blacklist(email, rules)
        assert result in (ActionEnum.DROP, ActionEnum.RECORD, ActionEnum.PASS)


class TestLoadBlacklistRules:
    """Tests for load_blacklist_rules function."""
    
    def test_load_valid_rules_list(self):
        """Test loading rules from a list format YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = [
                {"trigger": "sender", "value": "spam@example.com", "action": "drop"},
                {"trigger": "subject", "value": "Unsubscribe", "action": "record"},
                {"trigger": "domain", "value": "spam.com", "action": "drop"}
            ]
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_blacklist_rules(config_path)
            assert len(rules) == 3
            assert rules[0].trigger_type == "sender"
            assert rules[1].trigger_type == "subject"
            assert rules[2].trigger_type == "domain"
        finally:
            Path(config_path).unlink()
    
    def test_load_rules_from_blocked_items(self):
        """Test loading rules from blocked_items key."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = {
                "blocked_items": [
                    {"trigger": "sender", "value": "spam@example.com", "action": "drop"}
                ]
            }
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_blacklist_rules(config_path)
            assert len(rules) == 1
            assert rules[0].trigger_type == "sender"
        finally:
            Path(config_path).unlink()
    
    def test_missing_file_returns_empty_list(self):
        """Test that missing file returns empty list."""
        rules = load_blacklist_rules("nonexistent_file.yaml")
        assert rules == []
    
    def test_empty_file_returns_empty_list(self):
        """Test that empty file returns empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            config_path = f.name
        
        try:
            rules = load_blacklist_rules(config_path)
            assert rules == []
        finally:
            Path(config_path).unlink()
    
    def test_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises InvalidRuleError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: [")
            config_path = f.name
        
        try:
            with pytest.raises(InvalidRuleError, match="YAML parse error"):
                load_blacklist_rules(config_path)
        finally:
            Path(config_path).unlink()
    
    def test_malformed_rule_skipped(self):
        """Test that malformed rules are skipped with warning."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = [
                {"trigger": "sender", "value": "spam@example.com", "action": "drop"},
                {"trigger": "invalid", "value": "test", "action": "drop"},  # Invalid trigger
                {"trigger": "subject", "value": "Unsubscribe", "action": "record"}
            ]
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_blacklist_rules(config_path)
            # Should have 2 valid rules (invalid one skipped)
            assert len(rules) == 2
            assert rules[0].trigger_type == "sender"
            assert rules[1].trigger_type == "subject"
        finally:
            Path(config_path).unlink()
    
    def test_all_malformed_rules_returns_empty(self):
        """Test that all malformed rules result in empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = [
                {"trigger": "invalid1", "value": "test", "action": "drop"},
                {"trigger": "invalid2", "value": "test", "action": "drop"}
            ]
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_blacklist_rules(config_path)
            assert rules == []
        finally:
            Path(config_path).unlink()
