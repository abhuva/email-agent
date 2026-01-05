import os
import shutil
import pytest
from src.prompt_loader import find_markdown_files

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
    # No such directory
    no_dir = tmp_path / 'nonexistent'
    result = find_markdown_files(str(no_dir))
    assert result == []
