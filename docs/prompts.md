# Prompt Loading & Parsing Module

## Overview
Handles discovering, reading, parsing, and converting prompt Markdown files (with YAML frontmatter) for customizable and dynamic AI prompting.

*Return to main doc: [README.md](../README.md) for context and documentation overview.*

## Components
- **find_markdown_files**: Finds all *.md files in a directory specified by config.
- **parse_markdown_frontmatter**: Splits prompt file content into YAML frontmatter as metadata (dict) and Markdown body (string). Handles invalid or missing frontmatter gracefully.
- **markdown_to_plain_text**: Converts Markdown prompt body to plain text, stripping/flattening unnecessary markdown formatting for LLM-friendly prompts while retaining important structure.
- **process_prompt_content**: Combines metadata and processed prompt text for AI-ready consumption.
- **load_prompts**: Loads all prompt files, parses and processes them, skipping or logging errors but returning all successful prompt objects with filename references.

## Test Strategy
- File finding and parsing are tested with temp directories/files (pytest fixes isolation).
- Frontmatter parser is tested for valid, invalid, and absent frontmatter edge cases.
- Content processor verifies output correctness from rich Markdown body to flattened prompt text for LLMs.
- End-to-end loader tests return correct structure and handle files with partial or broken metadata without crash.

## Usage Example
```python
from src.prompt_loader import load_prompts
prompt_objs = load_prompts('prompts/')
for p in prompt_objs:
    print(p['prompt_text'], p['metadata'])
```

---
This file is updated after every major change to prompt pipeline or tests.