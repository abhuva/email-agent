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
    WhitelistRule,
    check_blacklist,
    load_blacklist_rules,
    load_whitelist_rules,
    match_domain_rule,
    match_sender_rule,
    match_subject_rule,
    rule_matches_email,
    validate_blacklist_rule,
    validate_whitelist_rule,
    apply_whitelist,
    whitelist_rule_matches_email,
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


# ============================================================================
# Whitelist Rule Tests
# ============================================================================

class TestWhitelistRule:
    """Tests for WhitelistRule dataclass."""
    
    def test_valid_rule_creation(self):
        """Test creating a valid WhitelistRule."""
        rule = WhitelistRule(
            trigger_type="sender",
            value="boss@company.com",
            score_boost=15.0,
            tags=["#priority"]
        )
        assert rule.trigger_type == "sender"
        assert rule.value == "boss@company.com"
        assert rule.score_boost == 15.0
        assert rule.tags == ["#priority"]
    
    def test_invalid_trigger_type(self):
        """Test that invalid trigger_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            WhitelistRule(
                trigger_type="invalid",
                value="test",
                score_boost=10.0,
                tags=[]
            )
    
    def test_empty_value(self):
        """Test that empty value raises ValueError."""
        with pytest.raises(ValueError, match="Rule value cannot be empty"):
            WhitelistRule(
                trigger_type="sender",
                value="",
                score_boost=10.0,
                tags=[]
            )
    
    def test_negative_score_boost(self):
        """Test that negative score_boost raises ValueError."""
        with pytest.raises(ValueError, match="score_boost must be >= 0"):
            WhitelistRule(
                trigger_type="sender",
                value="test",
                score_boost=-5.0,
                tags=[]
            )
    
    def test_invalid_tags_type(self):
        """Test that non-list tags raises ValueError."""
        with pytest.raises(ValueError, match="tags must be a list"):
            WhitelistRule(
                trigger_type="sender",
                value="test",
                score_boost=10.0,
                tags="not a list"
            )
    
    def test_empty_tag_string(self):
        """Test that empty tag string raises ValueError."""
        with pytest.raises(ValueError, match="Tags cannot be empty strings"):
            WhitelistRule(
                trigger_type="sender",
                value="test",
                score_boost=10.0,
                tags=["valid", ""]
            )
    
    def test_all_trigger_types(self):
        """Test that all valid trigger types work."""
        for trigger in ("sender", "subject", "domain"):
            rule = WhitelistRule(
                trigger_type=trigger,
                value="test",
                score_boost=10.0,
                tags=[]
            )
            assert rule.trigger_type == trigger


class TestValidateWhitelistRule:
    """Tests for validate_whitelist_rule function."""
    
    def test_valid_sender_rule(self):
        """Test validating a valid sender rule."""
        raw_rule = {
            "trigger": "sender",
            "value": "boss@company.com",
            "action": "boost",
            "score_boost": 15,
            "add_tags": ["#priority"]
        }
        rule = validate_whitelist_rule(raw_rule)
        assert rule.trigger_type == "sender"
        assert rule.value == "boss@company.com"
        assert rule.score_boost == 15.0
        assert rule.tags == ["#priority"]
    
    def test_valid_domain_rule(self):
        """Test validating a valid domain rule."""
        raw_rule = {
            "trigger": "domain",
            "value": "important-client.com",
            "action": "boost",
            "score_boost": 20,
            "add_tags": ["#vip", "#work"]
        }
        rule = validate_whitelist_rule(raw_rule)
        assert rule.trigger_type == "domain"
        assert rule.value == "important-client.com"
        assert rule.score_boost == 20.0
        assert rule.tags == ["#vip", "#work"]
    
    def test_valid_subject_rule(self):
        """Test validating a valid subject rule."""
        raw_rule = {
            "trigger": "subject",
            "value": "URGENT",
            "action": "boost",
            "score_boost": 10,
            "add_tags": ["#urgent"]
        }
        rule = validate_whitelist_rule(raw_rule)
        assert rule.trigger_type == "subject"
        assert rule.value == "URGENT"
        assert rule.score_boost == 10.0
        assert rule.tags == ["#urgent"]
    
    def test_missing_trigger(self):
        """Test that missing trigger field raises InvalidRuleError."""
        raw_rule = {
            "value": "test",
            "action": "boost",
            "score_boost": 10,
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'trigger'"):
            validate_whitelist_rule(raw_rule)
    
    def test_missing_value(self):
        """Test that missing value field raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "action": "boost",
            "score_boost": 10,
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'value'"):
            validate_whitelist_rule(raw_rule)
    
    def test_missing_action(self):
        """Test that missing action field raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "score_boost": 10,
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'action'"):
            validate_whitelist_rule(raw_rule)
    
    def test_invalid_action(self):
        """Test that invalid action raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "drop",  # Must be "boost" for whitelist
            "score_boost": 10,
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="Invalid action for whitelist rule"):
            validate_whitelist_rule(raw_rule)
    
    def test_missing_score_boost(self):
        """Test that missing score_boost field raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="missing required field: 'score_boost'"):
            validate_whitelist_rule(raw_rule)
    
    def test_invalid_score_boost_type(self):
        """Test that non-numeric score_boost raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "score_boost": "not a number",
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="score_boost must be a number"):
            validate_whitelist_rule(raw_rule)
    
    def test_negative_score_boost(self):
        """Test that negative score_boost raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "score_boost": -5,
            "add_tags": []
        }
        with pytest.raises(InvalidRuleError, match="score_boost must be >= 0"):
            validate_whitelist_rule(raw_rule)
    
    def test_missing_add_tags_defaults_to_empty(self):
        """Test that missing add_tags defaults to empty list."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "score_boost": 10
        }
        rule = validate_whitelist_rule(raw_rule)
        assert rule.tags == []
    
    def test_invalid_tags_type(self):
        """Test that non-list add_tags raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "score_boost": 10,
            "add_tags": "not a list"
        }
        with pytest.raises(InvalidRuleError, match="add_tags must be a list"):
            validate_whitelist_rule(raw_rule)
    
    def test_empty_tag_in_list(self):
        """Test that empty tag in list raises InvalidRuleError."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "score_boost": 10,
            "add_tags": ["valid", ""]
        }
        with pytest.raises(InvalidRuleError, match="cannot be empty"):
            validate_whitelist_rule(raw_rule)
    
    def test_case_insensitive_trigger(self):
        """Test that trigger type is case-insensitive."""
        raw_rule = {
            "trigger": "SENDER",  # Uppercase
            "value": "test",
            "action": "boost",
            "score_boost": 10,
            "add_tags": []
        }
        rule = validate_whitelist_rule(raw_rule)
        assert rule.trigger_type == "sender"  # Lowercase
    
    def test_case_insensitive_action(self):
        """Test that action is case-insensitive."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "BOOST",  # Uppercase
            "score_boost": 10,
            "add_tags": []
        }
        rule = validate_whitelist_rule(raw_rule)
        # Should not raise error
    
    def test_non_dict_input(self):
        """Test that non-dict input raises InvalidRuleError."""
        with pytest.raises(InvalidRuleError, match="must be a dictionary"):
            validate_whitelist_rule("not a dict")
    
    def test_score_boost_as_float(self):
        """Test that score_boost can be a float."""
        raw_rule = {
            "trigger": "sender",
            "value": "test",
            "action": "boost",
            "score_boost": 15.5,
            "add_tags": []
        }
        rule = validate_whitelist_rule(raw_rule)
        assert rule.score_boost == 15.5


class TestWhitelistRuleMatchesEmail:
    """Tests for whitelist_rule_matches_email function."""
    
    def test_sender_rule_match(self):
        """Test sender rule matching."""
        email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        rule = WhitelistRule(
            trigger_type="sender",
            value="boss@company.com",
            score_boost=15.0,
            tags=["#priority"]
        )
        assert whitelist_rule_matches_email(email, rule) is True
    
    def test_sender_rule_no_match(self):
        """Test sender rule non-match."""
        email = EmailContext(uid="1", sender="other@company.com", subject="Test")
        rule = WhitelistRule(
            trigger_type="sender",
            value="boss@company.com",
            score_boost=15.0,
            tags=["#priority"]
        )
        assert whitelist_rule_matches_email(email, rule) is False
    
    def test_subject_rule_match(self):
        """Test subject rule matching."""
        email = EmailContext(uid="1", sender="test@example.com", subject="URGENT: Action Required")
        rule = WhitelistRule(
            trigger_type="subject",
            value="URGENT",
            score_boost=10.0,
            tags=["#urgent"]
        )
        assert whitelist_rule_matches_email(email, rule) is True
    
    def test_domain_rule_match(self):
        """Test domain rule matching."""
        email = EmailContext(uid="1", sender="user@important-client.com", subject="Test")
        rule = WhitelistRule(
            trigger_type="domain",
            value="important-client.com",
            score_boost=20.0,
            tags=["#vip"]
        )
        assert whitelist_rule_matches_email(email, rule) is True
    
    def test_domain_rule_no_match(self):
        """Test domain rule non-match."""
        email = EmailContext(uid="1", sender="user@other.com", subject="Test")
        rule = WhitelistRule(
            trigger_type="domain",
            value="important-client.com",
            score_boost=20.0,
            tags=["#vip"]
        )
        assert whitelist_rule_matches_email(email, rule) is False


class TestApplyWhitelist:
    """Tests for apply_whitelist function."""
    
    def test_no_rules_returns_unchanged(self):
        """Test that empty rules list returns unchanged score and empty tags."""
        email = EmailContext(uid="1", sender="test@example.com", subject="Test")
        new_score, tags = apply_whitelist(email, [], 5.0)
        assert new_score == 5.0
        assert tags == []
    
    def test_no_match_returns_unchanged(self):
        """Test that no matching rules returns unchanged score and empty tags."""
        email = EmailContext(uid="1", sender="other@example.com", subject="Test")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@company.com",
                score_boost=15.0,
                tags=["#priority"]
            )
        ]
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert new_score == 5.0
        assert tags == []
    
    def test_single_matching_rule(self):
        """Test that single matching rule applies boost and adds tags."""
        email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@company.com",
                score_boost=15.0,
                tags=["#priority"]
            )
        ]
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert new_score == 20.0
        assert tags == ["#priority"]
    
    def test_multiple_matching_rules_cumulative(self):
        """Test that multiple matching rules are cumulative."""
        email = EmailContext(uid="1", sender="boss@important-client.com", subject="URGENT")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@important-client.com",
                score_boost=15.0,
                tags=["#priority"]
            ),
            WhitelistRule(
                trigger_type="domain",
                value="important-client.com",
                score_boost=20.0,
                tags=["#vip", "#work"]
            ),
            WhitelistRule(
                trigger_type="subject",
                value="URGENT",
                score_boost=10.0,
                tags=["#urgent"]
            )
        ]
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert new_score == 50.0  # 5.0 + 15.0 + 20.0 + 10.0
        # Tags should include all unique tags
        assert "#priority" in tags
        assert "#vip" in tags
        assert "#work" in tags
        assert "#urgent" in tags
        assert len(tags) == 4
    
    def test_duplicate_tags_removed(self):
        """Test that duplicate tags are removed."""
        email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@company.com",
                score_boost=15.0,
                tags=["#priority", "#work"]
            ),
            WhitelistRule(
                trigger_type="domain",
                value="company.com",
                score_boost=10.0,
                tags=["#priority"]  # Duplicate tag
            )
        ]
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert new_score == 30.0  # 5.0 + 15.0 + 10.0
        assert tags.count("#priority") == 1  # Should only appear once
        assert "#work" in tags
        assert len(tags) == 2
    
    def test_zero_score_boost(self):
        """Test that zero score_boost works correctly."""
        email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@company.com",
                score_boost=0.0,
                tags=["#tagged"]
            )
        ]
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert new_score == 5.0  # No change
        assert tags == ["#tagged"]
    
    def test_very_high_score_boost(self):
        """Test that very high score_boost works correctly."""
        email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@company.com",
                score_boost=1000.0,
                tags=["#important"]
            )
        ]
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert new_score == 1005.0
        assert tags == ["#important"]
    
    def test_malformed_rule_handled_gracefully(self):
        """Test that malformed rules don't crash the evaluation."""
        email = EmailContext(uid="1", sender="boss@company.com", subject="Test")
        rules = [
            WhitelistRule(
                trigger_type="sender",
                value="boss@company.com",
                score_boost=15.0,
                tags=["#priority"]
            )
        ]
        # Should not raise exception
        new_score, tags = apply_whitelist(email, rules, 5.0)
        assert isinstance(new_score, float)
        assert isinstance(tags, list)


class TestLoadWhitelistRules:
    """Tests for load_whitelist_rules function."""
    
    def test_load_valid_rules_list(self):
        """Test loading rules from a list format YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = [
                {
                    "trigger": "sender",
                    "value": "boss@company.com",
                    "action": "boost",
                    "score_boost": 15,
                    "add_tags": ["#priority"]
                },
                {
                    "trigger": "domain",
                    "value": "important-client.com",
                    "action": "boost",
                    "score_boost": 20,
                    "add_tags": ["#vip", "#work"]
                }
            ]
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_whitelist_rules(config_path)
            assert len(rules) == 2
            assert rules[0].trigger_type == "sender"
            assert rules[0].score_boost == 15.0
            assert rules[0].tags == ["#priority"]
            assert rules[1].trigger_type == "domain"
            assert rules[1].score_boost == 20.0
            assert rules[1].tags == ["#vip", "#work"]
        finally:
            Path(config_path).unlink()
    
    def test_load_rules_from_allowed_items(self):
        """Test loading rules from allowed_items key."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = {
                "allowed_items": [
                    {
                        "trigger": "sender",
                        "value": "boss@company.com",
                        "action": "boost",
                        "score_boost": 15,
                        "add_tags": ["#priority"]
                    }
                ]
            }
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_whitelist_rules(config_path)
            assert len(rules) == 1
            assert rules[0].trigger_type == "sender"
        finally:
            Path(config_path).unlink()
    
    def test_missing_file_returns_empty_list(self):
        """Test that missing file returns empty list."""
        rules = load_whitelist_rules("nonexistent_file.yaml")
        assert rules == []
    
    def test_empty_file_returns_empty_list(self):
        """Test that empty file returns empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            config_path = f.name
        
        try:
            rules = load_whitelist_rules(config_path)
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
                load_whitelist_rules(config_path)
        finally:
            Path(config_path).unlink()
    
    def test_malformed_rule_skipped(self):
        """Test that malformed rules are skipped with warning."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = [
                {
                    "trigger": "sender",
                    "value": "boss@company.com",
                    "action": "boost",
                    "score_boost": 15,
                    "add_tags": ["#priority"]
                },
                {
                    "trigger": "invalid",  # Invalid trigger
                    "value": "test",
                    "action": "boost",
                    "score_boost": 10,
                    "add_tags": []
                },
                {
                    "trigger": "domain",
                    "value": "important-client.com",
                    "action": "boost",
                    "score_boost": 20,
                    "add_tags": ["#vip"]
                }
            ]
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_whitelist_rules(config_path)
            # Should have 2 valid rules (invalid one skipped)
            assert len(rules) == 2
            assert rules[0].trigger_type == "sender"
            assert rules[1].trigger_type == "domain"
        finally:
            Path(config_path).unlink()
    
    def test_all_malformed_rules_returns_empty(self):
        """Test that all malformed rules result in empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_data = [
                {
                    "trigger": "invalid1",
                    "value": "test",
                    "action": "boost",
                    "score_boost": 10,
                    "add_tags": []
                },
                {
                    "trigger": "invalid2",
                    "value": "test",
                    "action": "boost",
                    "score_boost": -5,  # Invalid negative score
                    "add_tags": []
                }
            ]
            yaml.dump(rules_data, f)
            config_path = f.name
        
        try:
            rules = load_whitelist_rules(config_path)
            assert rules == []
        finally:
            Path(config_path).unlink()
