"""
V4 Decision Logic Module

This module implements threshold-based decision logic for email classification
using numerical scores from the LLM.

It processes LLM scores, applies configurable thresholds, handles edge cases,
and provides a standardized classification result format.

Architecture:
    - Uses account-specific configuration passed as dictionary
    - Processes LLMResponse objects from llm_client.py
    - Returns ClassificationResult objects for downstream modules
    - Handles edge cases and provides confidence scoring

Usage:
    >>> from src.decision_logic import DecisionLogic
    >>> from src.llm_client import LLMResponse
    >>> 
    >>> config = {'processing': {'importance_threshold': 7, 'spam_threshold': 5}}
    >>> logic = DecisionLogic(config)
    >>> llm_response = LLMResponse(spam_score=2, importance_score=9)
    >>> result = logic.classify(llm_response)
    >>> print(result.is_important)
    True
    >>> print(result.is_spam)
    False
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

from src.llm_client import LLMResponse

logger = logging.getLogger(__name__)


class ClassificationStatus(Enum):
    """Status of email classification."""
    SUCCESS = "success"
    ERROR = "error"
    INVALID_SCORES = "invalid_scores"


@dataclass
class ClassificationResult:
    """
    Standardized classification result for downstream modules.
    
    This format is designed to be consumed by:
    - Note generation module (for frontmatter and tags)
    - IMAP flag setting module (for applying tags)
    - Logging/analytics modules (for tracking)
    
    Attributes:
        is_important: Whether email meets importance threshold
        is_spam: Whether email meets spam threshold
        importance_score: Processed importance score (0-10)
        spam_score: Processed spam score (0-10)
        confidence: Confidence level (0.0-1.0) in classification
        status: Classification status (success, error, invalid_scores)
        raw_scores: Original scores from LLM (for debugging)
        metadata: Additional metadata for downstream processing
    """
    is_important: bool
    is_spam: bool
    importance_score: int
    spam_score: int
    confidence: float
    status: ClassificationStatus
    raw_scores: Dict[str, int]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for serialization."""
        return {
            "is_important": self.is_important,
            "is_spam": self.is_spam,
            "importance_score": self.importance_score,
            "spam_score": self.spam_score,
            "confidence": self.confidence,
            "status": self.status.value,
            "raw_scores": self.raw_scores,
            "metadata": self.metadata
        }
    
    def to_frontmatter_dict(self) -> Dict[str, Any]:
        """
        Convert to format suitable for YAML frontmatter in notes.
        
        This format aligns with PDD Section 3.2 specification.
        """
        return {
            "llm_output": {
                "importance_score": self.importance_score,
                "spam_score": self.spam_score,
                "model_used": self.metadata.get("model_used", "unknown")
            },
            "processing_meta": {
                "script_version": "3.0",
                "processed_at": self.metadata.get("processed_at"),
                "status": self.status.value
            },
            "tags": self._generate_tags()
        }
    
    def _generate_tags(self) -> list:
        """Generate tags based on classification results."""
        tags = ["email"]
        if self.is_important:
            tags.append("important")
        if self.is_spam:
            tags.append("spam")
        # Add #process_error tag for error status (Task 10)
        if self.status == ClassificationStatus.ERROR:
            tags.append("#process_error")
        return tags
    
    def to_imap_tags(self) -> list:
        """
        Convert to IMAP tag list for flag setting.
        
        Returns list of tag names to apply to email.
        """
        tags = []
        if self.is_important:
            tags.append("Important")
        if self.is_spam:
            tags.append("Spam")
        return tags


class ScoreProcessor:
    """
    Processes and validates numerical scores from LLM.
    
    Handles score normalization, validation, and range checking.
    """
    
    # Expected score range (0-10 as per PDD)
    MIN_SCORE = 0
    MAX_SCORE = 10
    
    @classmethod
    def validate_score(cls, score: int, score_name: str) -> int:
        """
        Validate that a score is within expected range.
        
        Args:
            score: Score value to validate
            score_name: Name of score (for error messages)
            
        Returns:
            Validated score value
            
        Raises:
            ValueError: If score is outside valid range
        """
        if not isinstance(score, int):
            raise ValueError(f"{score_name} must be an integer, got {type(score).__name__}")
        
        if score < cls.MIN_SCORE or score > cls.MAX_SCORE:
            raise ValueError(
                f"{score_name} must be between {cls.MIN_SCORE} and {cls.MAX_SCORE}, "
                f"got {score}"
            )
        
        return score
    
    @classmethod
    def process_scores(cls, llm_response: LLMResponse) -> Dict[str, int]:
        """
        Process and validate scores from LLM response.
        
        Args:
            llm_response: LLMResponse object with scores
            
        Returns:
            Dictionary with validated scores
            
        Raises:
            ValueError: If scores are invalid
        """
        try:
            importance_score = cls.validate_score(
                llm_response.importance_score,
                "importance_score"
            )
            spam_score = cls.validate_score(
                llm_response.spam_score,
                "spam_score"
            )
            
            return {
                "importance_score": importance_score,
                "spam_score": spam_score
            }
        except ValueError as e:
            logger.error(f"Score validation failed: {e}")
            raise
    
    @classmethod
    def handle_invalid_scores(cls, llm_response: LLMResponse) -> Dict[str, int]:
        """
        Handle cases where scores are invalid or missing.
        
        Returns default error scores (-1) as specified in PDD.
        """
        logger.warning(
            f"Invalid scores detected: importance={llm_response.importance_score}, "
            f"spam={llm_response.spam_score}. Using error values."
        )
        return {
            "importance_score": -1,
            "spam_score": -1
        }


class DecisionLogic:
    """
    Threshold-based decision logic for email classification.
    
    This class implements the core decision logic that compares processed scores
    against configured thresholds to determine email categorization.
    
    All configuration is accessed through the settings.py facade.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize decision logic with thresholds from account-specific configuration.
        
        Args:
            config: Account-specific merged configuration dictionary
        """
        # Extract thresholds from processing configuration
        processing_config = config.get('processing', {})
        self._importance_threshold = processing_config.get('importance_threshold', 7)
        self._spam_threshold = processing_config.get('spam_threshold', 5)
        
        logger.debug(
            f"Loaded thresholds: importance={self._importance_threshold}, "
            f"spam={self._spam_threshold}"
        )
    
    def _apply_thresholds(
        self,
        importance_score: int,
        spam_score: int
    ) -> tuple[bool, bool]:
        """
        Apply thresholds to determine classification.
        
        Args:
            importance_score: Processed importance score (0-10)
            spam_score: Processed spam score (0-10)
            
        Returns:
            Tuple of (is_important, is_spam) boolean values
        """
        # Importance: score >= threshold means important
        is_important = importance_score >= self._importance_threshold
        
        # Spam: score >= threshold means spam
        is_spam = spam_score >= self._spam_threshold
        
        return is_important, is_spam
    
    def _calculate_confidence(
        self,
        importance_score: int,
        spam_score: int,
        is_important: bool,
        is_spam: bool
    ) -> float:
        """
        Calculate confidence level for classification.
        
        Confidence is based on how far scores are from thresholds.
        Higher distance = higher confidence.
        
        Args:
            importance_score: Processed importance score
            spam_score: Processed spam score
            is_important: Whether email is classified as important
            is_spam: Whether email is classified as spam
            
        Returns:
            Confidence value between 0.0 and 1.0
        """
        # Calculate distance from thresholds
        importance_distance = abs(importance_score - self._importance_threshold)
        spam_distance = abs(spam_score - self._spam_threshold)
        
        # Normalize distances (max distance is 10)
        importance_confidence = min(importance_distance / 10.0, 1.0)
        spam_confidence = min(spam_distance / 10.0, 1.0)
        
        # Average confidence (can be weighted differently if needed)
        confidence = (importance_confidence + spam_confidence) / 2.0
        
        # Boost confidence if classification is clear (far from threshold)
        if is_important and importance_score >= self._importance_threshold + 2:
            confidence = min(confidence + 0.2, 1.0)
        if is_spam and spam_score >= self._spam_threshold + 2:
            confidence = min(confidence + 0.2, 1.0)
        
        return round(confidence, 2)
    
    def _handle_edge_cases(
        self,
        importance_score: int,
        spam_score: int,
        is_important: bool,
        is_spam: bool
    ) -> tuple[bool, bool, Dict[str, Any]]:
        """
        Handle edge cases in classification.
        
        Edge cases include:
        - Scores exactly at threshold
        - Conflicting classifications (important spam)
        - Unusual score combinations
        
        Args:
            importance_score: Processed importance score
            spam_score: Processed spam score
            is_important: Initial importance classification
            is_spam: Initial spam classification
            
        Returns:
            Tuple of (is_important, is_spam, metadata) with edge case handling applied
        """
        metadata = {
            "edge_cases": [],
            "threshold_boundary": False,
            "conflicting_classification": False
        }
        
        # Edge case: Score exactly at threshold
        if importance_score == self._importance_threshold:
            metadata["edge_cases"].append("importance_at_threshold")
            metadata["threshold_boundary"] = True
            logger.debug(f"Importance score exactly at threshold: {importance_score}")
        
        if spam_score == self._spam_threshold:
            metadata["edge_cases"].append("spam_at_threshold")
            metadata["threshold_boundary"] = True
            logger.debug(f"Spam score exactly at threshold: {spam_score}")
        
        # Edge case: Conflicting classification (important spam)
        if is_important and is_spam:
            metadata["edge_cases"].append("conflicting_classification")
            metadata["conflicting_classification"] = True
            logger.warning(
                f"Conflicting classification: important={is_important}, spam={is_spam}. "
                f"Scores: importance={importance_score}, spam={spam_score}"
            )
            # Decision: Spam takes precedence (spam emails are not important)
            is_important = False
            metadata["resolution"] = "spam_takes_precedence"
        
        # Edge case: Unusual score combinations
        if importance_score >= 8 and spam_score >= 7:
            metadata["edge_cases"].append("unusual_high_both_scores")
            logger.debug(
                f"Unusual combination: both scores very high "
                f"(importance={importance_score}, spam={spam_score})"
            )
        
        return is_important, is_spam, metadata
    
    def classify(
        self,
        llm_response: LLMResponse,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        Classify email based on LLM scores and thresholds.
        
        This is the main entry point for classification logic.
        
        Args:
            llm_response: LLMResponse object with scores
            metadata: Optional metadata to include in result
            
        Returns:
            ClassificationResult object with classification decision
        """
        # Initialize metadata
        if metadata is None:
            metadata = {}
        
        # Handle error scores (from failed LLM calls)
        if llm_response.importance_score == -1 or llm_response.spam_score == -1:
            logger.warning("Error scores detected (-1), creating error classification")
            return ClassificationResult(
                is_important=False,
                is_spam=False,
                importance_score=-1,
                spam_score=-1,
                confidence=0.0,
                status=ClassificationStatus.ERROR,
                raw_scores=llm_response.to_dict(),
                metadata={**metadata, "error": "LLM processing failed"}
            )
        
        # Process and validate scores
        try:
            processed_scores = ScoreProcessor.process_scores(llm_response)
            importance_score = processed_scores["importance_score"]
            spam_score = processed_scores["spam_score"]
        except ValueError:
            # Invalid scores - use error handling
            processed_scores = ScoreProcessor.handle_invalid_scores(llm_response)
            return ClassificationResult(
                is_important=False,
                is_spam=False,
                importance_score=-1,
                spam_score=-1,
                confidence=0.0,
                status=ClassificationStatus.INVALID_SCORES,
                raw_scores=llm_response.to_dict(),
                metadata={**metadata, "error": "Invalid score values"}
            )
        
        # Apply thresholds
        is_important, is_spam = self._apply_thresholds(importance_score, spam_score)
        
        # Handle edge cases
        is_important, is_spam, edge_case_metadata = self._handle_edge_cases(
            importance_score, spam_score, is_important, is_spam
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            importance_score, spam_score, is_important, is_spam
        )
        
        # Combine metadata
        final_metadata = {
            **metadata,
            **edge_case_metadata,
            "importance_threshold": self._importance_threshold,
            "spam_threshold": self._spam_threshold
        }
        
        # Create result
        result = ClassificationResult(
            is_important=is_important,
            is_spam=is_spam,
            importance_score=importance_score,
            spam_score=spam_score,
            confidence=confidence,
            status=ClassificationStatus.SUCCESS,
            raw_scores=llm_response.to_dict(),
            metadata=final_metadata
        )
        
        logger.info(
            f"Classification complete: important={is_important}, spam={is_spam}, "
            f"confidence={confidence:.2f}, scores=(imp={importance_score}, spam={spam_score})"
        )
        
        return result
