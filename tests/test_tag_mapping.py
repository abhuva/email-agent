import pytest
from src.tag_mapping import extract_keyword, map_keyword_to_tags, ALLOWED_KEYWORDS

tag_map = {
    "urgent": "Important",
    "neutral": "General",
    "spam": "Junk"
}

@pytest.mark.parametrize("ai_response,expected", [
    ("Urgent", "urgent"),
    ("urgent", "urgent"),
    ("URGENT", "urgent"),
    (" Urgent \n", "urgent"),
    ("urgent. ", "urgent"),
    ("neutral", "neutral"),
    ("Spam", "spam"),
    ("Spam indeed", "spam"),  # Should pick 'spam' if it's the first word
    ("randomtext", "neutral"),
    (None, "neutral"),
    ("", "neutral"),
    ("not-matching", "neutral"),
    ("neutral, please", "neutral"),
    ("Urgent!!!", "urgent"),
])
def test_extract_keyword(ai_response, expected):
    assert extract_keyword(ai_response) == expected

@pytest.mark.parametrize("keyword,expected", [
    ("urgent", ["Important"]),
    ("neutral", ["General"]),
    ("spam", ["Junk"]),
    ("unknown", ["General"]),
    ("", ["General"]),
])
def test_map_keyword_to_tags(keyword, expected):
    assert map_keyword_to_tags(keyword, tag_map) == expected

# Confirm ALLOWED_KEYWORDS is correct

def test_allowed_keywords():
    assert set(ALLOWED_KEYWORDS) == {"urgent","neutral","spam"}
