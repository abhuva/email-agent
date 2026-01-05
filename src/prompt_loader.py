import os
from typing import List
import logging

def find_markdown_files(prompt_dir: str) -> List[str]:
    """
    Find all .md files in directory and return a list of absolute file paths.
    Args:
        prompt_dir (str): Directory path to search for markdown prompt files.
    Returns:
        List[str]: List of prompt markdown file paths (absolute).
    """
    if not os.path.isdir(prompt_dir):
        logging.warning(f"Prompt directory not found: {prompt_dir}")
        return []
    files = [
        os.path.abspath(os.path.join(prompt_dir, fname))
        for fname in os.listdir(prompt_dir)
        if fname.lower().endswith('.md')
    ]
    logging.info(f"Found {len(files)} prompt markdown files in {prompt_dir}")
    return files
