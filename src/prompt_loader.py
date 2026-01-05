import os
from typing import List, Tuple, Dict, Any
import logging
import re
import yaml

def find_markdown_files(prompt_dir: str) -> List[str]:
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

FRONTMATTER_REGEX = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)$', re.DOTALL)

def parse_markdown_frontmatter(md: str) -> Dict[str, Any]:
    """
    Extract YAML frontmatter (as dict) and main content (as string) from Markdown string.
    Returns a dict with 'metadata' and 'content'.
    If no frontmatter detected, 'metadata' is empty and all content is in 'content'.
    """
    m = FRONTMATTER_REGEX.match(md)
    if m:
        front = m.group(1)
        content = m.group(2)
        try:
            metadata = yaml.safe_load(front) or {}
        except Exception as e:
            logging.warning(f"Error parsing frontmatter: {e}")
            metadata = {}
        return {'metadata': metadata, 'content': content}
    else:
        return {'metadata': {}, 'content': md}
