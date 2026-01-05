# Prompt Loading & Parsing Module

## Overview
Handles discovering, reading, and parsing prompt Markdown files (with YAML frontmatter) for customizable and dynamic AI prompting.

## Components
- **find_markdown_files**: Finds all *.md files in a directory specified by config.
- **parse_markdown_frontmatter**: Splits prompt file content into YAML frontmatter as metadata (dict) and Markdown body (string). Handles invalid or missing frontmatter gracefully.

## Test Strategy
- File finding and parsing are tested with temp directories/files (pytest fixes isolation).
- Frontmatter parser is tested for valid, invalid, and absent frontmatter edge cases.

## Usage Example
```python
from src.prompt_loader import find_markdown_files, parse_markdown_frontmatter
prompts = []
for fname in find_markdown_files('prompts/'):
    with open(fname) as f:
        doc = parse_markdown_frontmatter(f.read())
    prompts.append(doc)
```

---
This file is updated after every major change to prompt file code or tests.