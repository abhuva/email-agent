# V3 Decision Logic Module

**Status:** ✅ Complete (Task 6)  
**Module:** `src/decision_logic.py`  
**Tests:** `tests/test_decision_logic.py` (23 tests, all passing)

## Overview

The decision logic module implements threshold-based classification for email processing. It takes numerical scores from the LLM (importance_score and spam_score) and applies configurable thresholds to determine email categorization.

This module replaces the rigid classification system with a flexible, threshold-based approach as specified in PDD Section 3.

## Architecture

```
LLMResponse (scores) → ScoreProcessor → DecisionLogic → ClassificationResult
                                                          ↓
                                    Frontmatter Dict / IMAP Tags / Dict
```

### Key Components

1. **ScoreProcessor**: Validates and normalizes scores from LLM
2. **DecisionLogic**: Applies thresholds and makes classification decisions
3. **ClassificationResult**: Standardized output format for downstream modules

## Configuration

Thresholds are configured in `config.yaml` under the `processing` section:

```yaml
processing:
  importance_threshold: 8  # Minimum score (0-10) to mark as important
  spam_threshold: 5        # Maximum score (0-10) to consider as spam
```

Access via settings facade:
```python
from src.settings import settings

importance_threshold = settings.get_importance_threshold()  # Default: 8
spam_threshold = settings.get_spam_threshold()              # Default: 5
```

## Usage

### Basic Usage

```python
from src.decision_logic import DecisionLogic
from src.llm_client import LLMResponse

# Initialize decision logic
logic = DecisionLogic()

# Get scores from LLM
llm_response = LLMResponse(spam_score=2, importance_score=9)

# Classify email
result = logic.classify(llm_response)

# Check classification
print(f"Important: {result.is_important}")  # True
print(f"Spam: {result.is_spam}")           # False
print(f"Confidence: {result.confidence}")   # 0.85
```

### Output Formats

#### Dictionary Format
```python
result_dict = result.to_dict()
# {
#   "is_important": True,
#   "is_spam": False,
#   "importance_score": 9,
#   "spam_score": 2,
#   "confidence": 0.85,
#   "status": "success",
#   "raw_scores": {...},
#   "metadata": {...}
# }
```

#### Frontmatter Format (PDD Section 3.2)
```python
frontmatter = result.to_frontmatter_dict()
# {
#   "llm_output": {
#     "importance_score": 9,
#     "spam_score": 2,
#     "model_used": "test-model"
#   },
#   "processing_meta": {
#     "script_version": "3.0",
#     "processed_at": "2024-01-01T00:00:00Z",
#     "status": "success"
#   },
#   "tags": ["email", "important"]
# }
```

#### IMAP Tags Format
```python
tags = result.to_imap_tags()
# ["Important"]  # or ["Spam"] or ["Important", "Spam"]
```

## Classification Logic

### Threshold Application

- **Importance**: `importance_score >= importance_threshold` → `is_important = True`
- **Spam**: `spam_score >= spam_threshold` → `is_spam = True`

### Edge Case Handling

1. **Scores at Threshold Boundary**
   - When score equals threshold, classification is applied (meets threshold)
   - Edge case metadata is added for tracking

2. **Conflicting Classifications**
   - If email is both important AND spam, spam takes precedence
   - Resolution: `is_important = False`, `is_spam = True`
   - Metadata includes `conflicting_classification: True`

3. **Invalid Scores**
   - Scores outside 0-10 range → Error status
   - Error scores (-1) from failed LLM calls → Error status
   - Returns error values: `importance_score: -1`, `spam_score: -1`

4. **Unusual Score Combinations**
   - High importance (≥8) AND high spam (≥7) → Flagged in metadata
   - Helps identify potential prompt or scoring issues

### Confidence Calculation

Confidence is calculated based on distance from thresholds:
- Higher distance from threshold = higher confidence
- Range: 0.0 to 1.0
- Boosted if classification is clear (score ≥ threshold + 2)

## Score Processing

### Validation

Scores must be:
- Integer type
- In range 0-10 (inclusive)
- Both scores present (not missing)

### Error Handling

Invalid scores trigger:
1. Error logging
2. Error status in result
3. Error values (-1) for both scores
4. Metadata with error details

## ClassificationResult Structure

```python
@dataclass
class ClassificationResult:
    is_important: bool                    # Meets importance threshold
    is_spam: bool                         # Meets spam threshold
    importance_score: int                 # Processed score (0-10 or -1)
    spam_score: int                       # Processed score (0-10 or -1)
    confidence: float                     # Confidence level (0.0-1.0)
    status: ClassificationStatus          # success, error, invalid_scores
    raw_scores: Dict[str, int]            # Original LLM scores
    metadata: Dict[str, Any]              # Additional metadata
```

### Metadata Fields

- `edge_cases`: List of detected edge cases
- `threshold_boundary`: True if score at threshold
- `conflicting_classification`: True if conflict detected
- `resolution`: How conflict was resolved
- `importance_threshold`: Threshold value used
- `spam_threshold`: Threshold value used
- `error`: Error message (if error occurred)

## Integration Points

### Consumes
- **LLMResponse** from `src/llm_client.py`
  - Provides `spam_score` and `importance_score`

### Uses
- **settings.py** facade
  - `settings.get_importance_threshold()`
  - `settings.get_spam_threshold()`

### Produces
- **ClassificationResult** for:
  - Note generation (via `to_frontmatter_dict()`)
  - IMAP flag setting (via `to_imap_tags()`)
  - Logging/analytics (via `to_dict()`)

## Testing

Comprehensive test suite covers:
- Score validation (valid, invalid, out of range)
- Threshold application (at boundary, above, below)
- Edge case handling (conflicts, boundaries, unusual combinations)
- Confidence calculation
- Output format conversion (dict, frontmatter, IMAP tags)

Run tests:
```bash
pytest tests/test_decision_logic.py -v
```

## Examples

### Example 1: Important Email
```python
llm_response = LLMResponse(spam_score=1, importance_score=9)
result = logic.classify(llm_response)

assert result.is_important is True
assert result.is_spam is False
assert result.confidence > 0.5
```

### Example 2: Spam Email
```python
llm_response = LLMResponse(spam_score=7, importance_score=2)
result = logic.classify(llm_response)

assert result.is_important is False
assert result.is_spam is True
```

### Example 3: Neutral Email
```python
llm_response = LLMResponse(spam_score=2, importance_score=4)
result = logic.classify(llm_response)

assert result.is_important is False
assert result.is_spam is False
```

### Example 4: Error Handling
```python
llm_response = LLMResponse(spam_score=-1, importance_score=-1)
result = logic.classify(llm_response)

assert result.status == ClassificationStatus.ERROR
assert result.importance_score == -1
assert result.spam_score == -1
```

## PDD Alignment

This module implements:
- **PDD Section 3.1**: Processing configuration with thresholds
- **PDD Section 3.2**: Frontmatter format for notes
- **PDD Section 4**: API contract (scores 0-10, error values -1)

## Future Enhancements

Potential improvements:
- Custom threshold per email type
- Confidence-based filtering
- Historical threshold tuning
- Multi-class classification support

## Reference

- **PDD Specification**: `pdd.md` Sections 3.1, 3.2, 4
- **Module Code**: `src/decision_logic.py`
- **Tests**: `tests/test_decision_logic.py`
- **Configuration**: `docs/v3-configuration.md`
- **Settings Facade**: `src/settings.py`
