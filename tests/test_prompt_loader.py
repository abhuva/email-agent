import os
import shutil
import pytest
from src.prompt_loader import find_markdown_files, parse_markdown_frontmatter

@pytest.fixture
def prompt_dir_with_files(tmp_path):
    md1 = tmp_path / 'prompt1.md'
    md2 = tmp_path / 'prompt2.md'
    other = tmp_path / 'not-a-prompt.txt'
    md1.write_text('Prompt 1')
    md2.write_text('Prompt 2')
    other.write_text('not a prompt')
    return str(tmp_path)

def test_finds_md_files(prompt_dir_with_files):
    files = find_markdown_files(prompt_dir_with_files)
    assert len(files) == 2
    assert any(f.endswith('prompt1.md') for f in files)
    assert any(f.endswith('prompt2.md') for f in files)

def test_returns_empty_if_dir_missing(tmp_path):
    no_dir = tmp_path / 'nonexistent'
    result = find_markdown_files(str(no_dir))
    assert result == []

def test_parse_markdown_frontmatter():
    md = """---
title: Test Prompt
tag: example
---
Actual prompt body."""
    parsed = parse_markdown_frontmatter(md)
    assert parsed['metadata']['title'] == 'Test Prompt'
    assert parsed['metadata']['tag'] == 'example'
    assert 'Actual prompt body.' in parsed['content']

def test_parse_markdown_no_frontmatter():
    md = "Only body content here."
    parsed = parse_markdown_frontmatter(md)
    assert parsed['metadata'] == {}
    assert 'Only body content here.' in parsed['content']

def test_parse_markdown_invalid_frontmatter():
    md = """---
this: : [is: : bad\n---\nRest of body."""
    parsed = parse_markdown_frontmatter(md)
    # gracefully fails
    assert parsed['metadata'] == {}