import os
from typing import List, Dict, Any
import logging
import re
import yaml
import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension
from io import StringIO


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
            metadata = yaml.safe_load(front) or {}
        except Exception as e:
            logging.warning(f"Error parsing frontmatter: {e}")
            metadata = {}
        return {'metadata': metadata, 'content': content}
    else:
        return {'metadata': {}, 'content': md}

class MarkdownPlainTextExtractor(Treeprocessor):
    def run(self, root):
        text = StringIO()
        self._extract_text(root, text)
        return text.getvalue()

    def _extract_text(self, node, text):
        if node.text:
            text.write(node.text)
        for child in node:
            self._extract_text(child, text)
            if child.tail:
                text.write(child.tail)

class PlainTextExtension(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(MarkdownPlainTextExtractor(md), 'plaintext', 15)

def markdown_to_plain_text(md_content: str) -> str:
    md = markdown.Markdown(extensions=[PlainTextExtension()])
    return md.convert(md_content)

def process_prompt_content(doc: Dict[str, Any]) -> Dict[str, Any]:
    prompt_text = markdown_to_plain_text(doc['content'])
    result = dict(doc)
    result['prompt_text'] = prompt_text
    return result

def load_prompts(prompt_dir: str) -> List[Dict[str, Any]]:
    """
    Orchestrated pipeline: loads all prompts from a directory, parses frontmatter, processes content.
    Returns a list of dicts with keys: 'metadata', 'content', 'prompt_text'.
    Logs and skips files with failures but continues loading others.
    """
    prompt_files = find_markdown_files(prompt_dir)
    loaded = []
    for file in prompt_files:
        try:
            with open(file, encoding='utf-8') as f:
                raw = f.read()
            doc = parse_markdown_frontmatter(raw)
            doc_proc = process_prompt_content(doc)
            doc_proc['filename'] = file
            loaded.append(doc_proc)
            logging.info(f"Loaded prompt: {file}")
        except Exception as e:
            logging.warning(f"Failed to load prompt file {file}: {e}")
    return loaded
