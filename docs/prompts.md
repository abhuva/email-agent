# Prompt Loading & Parsing Module

## Overview
Handles discovering, reading, parsing, and converting prompt Markdown files (with YAML frontmatter) for customizable and dynamic AI prompting.

## Components
- **find_markdown_files**: Finds all *.md files in a directory specified by config.
- **parse_markdown_frontmatter**: Splits prompt file content into YAML frontmatter as metadata (dict) and Markdown body (string). Handles invalid or missing frontmatter gracefully.
- **markdown_to_plain_text**: Converts Markdown prompt body to plain text, stripping/flattening unnecessary markdown formatting for LLM-friendly prompts while retaining important structure.
- **process_prompt_content**: Combines metadata and processed prompt text for AI-ready consumption.

## Test Strategy
- File finding and parsing are tested with temp directories/files (pytest fixes isolation).
- Frontmatter parser is tested for valid, invalid, and absent frontmatter edge cases.
- Content processor verifies output correctness from rich Markdown body to flattened prompt text for LLMs.

## Usage Example
```python
from src.prompt_loader import find_markdown_files, parse_markdown_frontmatter, process_prompt_content
prompts = []
for fname in find_markdown_files('prompts/'):
    with open(fname) as f:
        parsed = parse_markdown_frontmatter(f.read())
        doc = process_prompt_content(parsed)
    prompts.append(doc)
```

---
This file is updated after every major change to prompt pipeline or tests.