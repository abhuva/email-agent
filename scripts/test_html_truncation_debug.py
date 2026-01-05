"""Quick debug script for HTML truncation"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email_truncation import truncate_html, HAS_BS4
from bs4 import BeautifulSoup

print(f"HAS_BS4: {HAS_BS4}")

# Test decompose directly
soup = BeautifulSoup("<p>Content</p><script>alert('xss')</script><p>More</p>", 'html.parser')
print(f"Before decompose: <script> in str(soup) = {'<script>' in str(soup)}")
for tag in soup(['script']):
    tag.decompose()
print(f"After decompose: <script> in str(soup) = {'<script>' in str(soup)}")
print(f"After decompose str: {str(soup)}")

# Test truncate_html
body = "<p>Content</p><script>alert('xss')</script><p>More content</p>"
result = truncate_html(body, 100)

print(f"\nTruncate result: {result}")
print(f"Has <script>: {'<script>' in result['truncatedBody']}")
print(f"Body: {result['truncatedBody']}")
