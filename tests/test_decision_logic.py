"""
Tests for decision logic module (Task 6).

Tests threshold-based classification, score processing, edge case handling,
and classification result output format.
"""
import pytest
from unittest.mock import Mock, patch

from src.decision_logic import (
    DecisionLogic,
    ClassificationResult,
    ClassificationStatus,
    ScoreProcessor
)
from src.llm_client import LLMResponse


@pytest.fixture
def default_test_config():
    """Default test configuration for DecisionLogic."""
    return {
        'processing': {
            'importance_threshold': 8,
            'spam_threshold': 5
        }
    }


@pytest.fixture
def custom_test_config():
    """Custom test configuration for DecisionLogic."""
    return {
        'processing': {
            'importance_threshold': 7,
            'spam_threshold': 6
        }
    }


class TestScoreProcessor:
    """Tests for score processing and validation."""
    
    def test_validate_score_valid_range(self):
        """Test validation of scores in valid range."""
        assert ScoreProcessor.validate_score(0, "test_score") == 0
        assert ScoreProcessor.validate_score(5, "test_score") == 5
        assert ScoreProcessor.validate_score(10, "test_score") == 10
    
    def test_validate_score_below_minimum(self):
        """Test validation fails for scores below minimum."""
        with pytest.raises(ValueError, match="must be between 0 and 10"):
            ScoreProcessor.validate_score(-1, "test_score")
    
    def test_validate_score_above_maximum(self):
        """Test validation fails for scores above maximum."""
        with pytest.raises(ValueError, match="must be between 0 and 10"):
            ScoreProcessor.validate_score(11, "test_score")
    
    def test_validate_score_wrong_type(self):
        """Test validation fails for non-integer scores."""
        with pytest.raises(ValueError, match="must be an integer"):
            ScoreProcessor.validate_score(5.5, "test_score")
        with pytest.raises(ValueError, match="must be an integer"):
            ScoreProcessor.validate_score("5", "test_score")
    
    def test_process_scores_valid(self):
        """Test processing of valid scores."""
        llm_response = LLMResponse(spam_score=2, importance_score=9)
        result = ScoreProcessor.process_scores(llm_response)
        assert result["spam_score"] == 2
        assert result["importance_score"] == 9
    
    def test_process_scores_invalid(self):
        """Test processing fails for invalid scores."""
        llm_response = LLMResponse(spam_score=15, importance_score=9)
        with pytest.raises(ValueError):
            ScoreProcessor.process_scores(llm_response)
    
    def test_handle_invalid_scores(self):
        """Test handling of invalid scores returns error values."""
        llm_response = LLMResponse(spam_score=15, importance_score=-5)
        result = ScoreProcessor.handle_invalid_scores(llm_response)
        assert result["spam_score"] == -1
        assert result["importance_score"] == -1


class TestDecisionLogic:
    """Tests for threshold-based decision logic."""
    
    def test_classify_important_email(self, default_test_config):
        """Test classification of important email."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=1, importance_score=9)
        result = logic.classify(llm_response)
        
        assert result.is_important is True
        assert result.is_spam is False
        assert result.importance_score == 9
        assert result.spam_score == 1
        assert result.status == ClassificationStatus.SUCCESS
        assert result.confidence > 0.0
    
    def test_classify_spam_email(self, default_test_config):
        """Test classification of spam email."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=7, importance_score=2)
        result = logic.classify(llm_response)
        
        assert result.is_important is False
        assert result.is_spam is True
        assert result.importance_score == 2
        assert result.spam_score == 7
        assert result.status == ClassificationStatus.SUCCESS
    
    def test_classify_neutral_email(self, default_test_config):
        """Test classification of neutral email."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=2, importance_score=4)
        result = logic.classify(llm_response)
        
        assert result.is_important is False
        assert result.is_spam is False
        assert result.status == ClassificationStatus.SUCCESS
    
    def test_classify_at_threshold_boundary(self, default_test_config):
        """Test classification when score is exactly at threshold."""
        logic = DecisionLogic(default_test_config)
        # Exactly at importance threshold (should be important)
        llm_response = LLMResponse(spam_score=2, importance_score=8)
        result = logic.classify(llm_response)
        
        assert result.is_important is True
        assert result.is_spam is False
        assert "threshold_boundary" in result.metadata or "edge_cases" in result.metadata
    
    def test_classify_conflicting_scores(self, default_test_config):
        """Test classification with conflicting scores (important spam)."""
        logic = DecisionLogic(default_test_config)
        # High importance but also high spam (conflict)
        llm_response = LLMResponse(spam_score=7, importance_score=9)
        result = logic.classify(llm_response)
        
        # Spam should take precedence (not important)
        assert result.is_important is False
        assert result.is_spam is True
        assert "conflicting_classification" in result.metadata.get("edge_cases", [])
    
    def test_classify_error_scores(self, default_test_config):
        """Test classification with error scores (-1)."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=-1, importance_score=-1)
        result = logic.classify(llm_response)
        
        assert result.is_important is False
        assert result.is_spam is False
        assert result.importance_score == -1
        assert result.spam_score == -1
        assert result.status == ClassificationStatus.ERROR
        assert result.confidence == 0.0
    
    def test_classify_invalid_scores(self, default_test_config):
        """Test classification with invalid scores (out of range)."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=15, importance_score=9)
        result = logic.classify(llm_response)
        
        assert result.status == ClassificationStatus.INVALID_SCORES
        assert result.importance_score == -1
        assert result.spam_score == -1
    
    def test_classify_custom_thresholds(self, custom_test_config):
        """Test classification with custom threshold values."""
        logic = DecisionLogic(custom_test_config)
        llm_response = LLMResponse(spam_score=4, importance_score=7)
        result = logic.classify(llm_response)
        
        assert result.is_important is True  # 7 >= 7
        assert result.is_spam is False  # 4 < 6


class TestClassificationResult:
    """Tests for classification result output format."""
    
    def test_to_dict(self):
        """Test conversion to dictionary format."""
        result = ClassificationResult(
            is_important=True,
            is_spam=False,
            importance_score=9,
            spam_score=2,
            confidence=0.85,
            status=ClassificationStatus.SUCCESS,
            raw_scores={"spam_score": 2, "importance_score": 9},
            metadata={"test": "value"}
        )
        
        result_dict = result.to_dict()
        assert result_dict["is_important"] is True
        assert result_dict["is_spam"] is False
        assert result_dict["importance_score"] == 9
        assert result_dict["spam_score"] == 2
        assert result_dict["confidence"] == 0.85
        assert result_dict["status"] == "success"
        assert result_dict["metadata"]["test"] == "value"
    
    def test_to_frontmatter_dict(self):
        """Test conversion to frontmatter format (PDD Section 3.2)."""
        result = ClassificationResult(
            is_important=True,
            is_spam=False,
            importance_score=9,
            spam_score=2,
            confidence=0.85,
            status=ClassificationStatus.SUCCESS,
            raw_scores={"spam_score": 2, "importance_score": 9},
            metadata={
                "model_used": "test-model",
                "processed_at": "2024-01-01T00:00:00Z"
            }
        )
        
        frontmatter = result.to_frontmatter_dict()
        
        # Check llm_output section
        assert frontmatter["llm_output"]["importance_score"] == 9
        assert frontmatter["llm_output"]["spam_score"] == 2
        assert frontmatter["llm_output"]["model_used"] == "test-model"
        
        # Check processing_meta section
        assert frontmatter["processing_meta"]["script_version"] == "3.0"
        assert frontmatter["processing_meta"]["status"] == "success"
        assert "processed_at" in frontmatter["processing_meta"]
        
        # Check tags
        assert "email" in frontmatter["tags"]
        assert "important" in frontmatter["tags"]
        assert "spam" not in frontmatter["tags"]
    
    def test_to_imap_tags(self):
        """Test conversion to IMAP tag list."""
        result = ClassificationResult(
            is_important=True,
            is_spam=True,
            importance_score=9,
            spam_score=7,
            confidence=0.85,
            status=ClassificationStatus.SUCCESS,
            raw_scores={"spam_score": 7, "importance_score": 9},
            metadata={}
        )
        
        tags = result.to_imap_tags()
        assert "Important" in tags
        assert "Spam" in tags
    
    def test_generate_tags(self):
        """Test tag generation based on classification."""
        # Important email
        result_important = ClassificationResult(
            is_important=True,
            is_spam=False,
            importance_score=9,
            spam_score=2,
            confidence=0.85,
            status=ClassificationStatus.SUCCESS,
            raw_scores={},
            metadata={}
        )
        tags = result_important._generate_tags()
        assert "email" in tags
        assert "important" in tags
        assert "spam" not in tags
        
        # Spam email
        result_spam = ClassificationResult(
            is_important=False,
            is_spam=True,
            importance_score=2,
            spam_score=7,
            confidence=0.85,
            status=ClassificationStatus.SUCCESS,
            raw_scores={},
            metadata={}
        )
        tags = result_spam._generate_tags()
        assert "email" in tags
        assert "spam" in tags
        assert "important" not in tags


class TestEdgeCases:
    """Tests for edge case handling."""
    
    def test_score_exactly_at_threshold(self, default_test_config):
        """Test handling of scores exactly at threshold."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=5, importance_score=8)
        result = logic.classify(llm_response)
        
        # Both scores at threshold - spam takes precedence in conflict resolution
        assert result.is_important is False  # Spam takes precedence
        assert result.is_spam is True
        # Should have edge case metadata
        assert len(result.metadata.get("edge_cases", [])) > 0
        assert "threshold_boundary" in result.metadata or result.metadata.get("threshold_boundary") is True
    
    def test_unusual_high_both_scores(self, default_test_config):
        """Test handling of unusual score combinations."""
        logic = DecisionLogic(default_test_config)
        llm_response = LLMResponse(spam_score=8, importance_score=9)
        result = logic.classify(llm_response)
        
        # Should handle conflict (spam takes precedence)
        assert result.is_important is False
        assert result.is_spam is True
        # Should have edge case metadata
        edge_cases = result.metadata.get("edge_cases", [])
        assert "unusual_high_both_scores" in edge_cases or "conflicting_classification" in edge_cases


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""
    
    def test_confidence_high_distance_from_threshold(self, default_test_config):
        """Test confidence is higher when scores are far from threshold."""
        logic = DecisionLogic(default_test_config)
        # Score far above threshold
        llm_response_far = LLMResponse(spam_score=1, importance_score=10)
        result_far = logic.classify(llm_response_far)
        
        # Score just above threshold
        llm_response_close = LLMResponse(spam_score=1, importance_score=8)
        result_close = logic.classify(llm_response_close)
        
        # Far score should have higher confidence
        assert result_far.confidence >= result_close.confidence
    
    def test_confidence_range(self, default_test_config):
        """Test confidence is always in valid range (0.0-1.0)."""
        logic = DecisionLogic(default_test_config)
        
        test_cases = [
            LLMResponse(spam_score=1, importance_score=10),
            LLMResponse(spam_score=5, importance_score=8),
            LLMResponse(spam_score=2, importance_score=4),
        ]
        
        for llm_response in test_cases:
            result = logic.classify(llm_response)
            assert 0.0 <= result.confidence <= 1.0
