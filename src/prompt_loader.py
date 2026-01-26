import os
from typing import List, Dict, Any
import logging
import re
import yaml
import markdown
from html import unescape

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
    m = FRONTMATTER_REGEX.match(md)
    if m:
        front = m.group(1)
        content = m.group(2)
        try:
            # Remove control characters that YAML doesn't allow
            # Control characters (0x00-0x1F, 0x7F-0x9F) are not allowed in YAML
            # Replace them with spaces or remove them
            import re
            # Remove control characters except newlines and tabs
            front_clean = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', front)
            metadata = yaml.safe_load(front_clean) or {}
        except Exception as e:
            logging.warning(f"Error parsing frontmatter: {e}")
            metadata = {}
        return {'metadata': metadata, 'content': content}
    else:
        return {'metadata': {}, 'content': md}

def markdown_to_plain_text(md_content: str) -> str:
    """
    Convert Markdown to plain text by converting to HTML first, then stripping HTML tags.
    This preserves structure (headings, lists) while removing formatting.
    """
    # Convert markdown to HTML
    html_content = markdown.markdown(md_content)
    # Strip HTML tags, keeping text content
    text = re.sub(r'<[^>]+>', '', html_content)
    # Decode HTML entities
    text = unescape(text)
    # Normalize whitespace (multiple spaces/newlines to single space)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def process_prompt_content(doc: Dict[str, Any]) -> Dict[str, Any]:
    prompt_text = markdown_to_plain_text(doc['content'])
    result = dict(doc)
    result['prompt_text'] = prompt_text
    return result

def load_prompts(prompt_dir: str, reload: bool = True) -> List[Dict[str, Any]]:
    """
    Orchestrated pipeline: loads all prompts from a directory, parses frontmatter, processes content.
    Returns a list of dicts with keys: 'metadata', 'content', 'prompt_text'.
    Logs and skips files with failures but continues loading others.
    If reload=True (default), always reloads from disk; parameter included for API clarity.
    """
    prompt_files = find_markdown_files(prompt_dir) if reload else []
    loaded = []
    for file in prompt_files:
        try:
            try:
                with open(file, encoding='utf-8') as f:
                    raw = f.read()
            except FileNotFoundError as fnf:
                logging.warning(f"Prompt file not found: {file} ({fnf})")
                continue
            except Exception as fe:
                logging.error(f"Failed to open prompt file {file}: {fe}")
                continue
            doc = parse_markdown_frontmatter(raw)
            doc_proc = process_prompt_content(doc)
            doc_proc['filename'] = file
            loaded.append(doc_proc)
            logging.info(f"Loaded prompt: {file}")
        except yaml.YAMLError as ye:
            logging.warning(f"Failed YAML parsing in {file}: {ye}")
        except Exception as e:
            logging.warning(f"Failed to process prompt file {file}: {e}")
    return loaded
