print('[DEBUG] Top-level print from openrouter_client.py -- should always show!')
import sys
import os
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import ConfigManager

class OpenRouterAPIError(Exception):
    """
    Raised when OpenRouter API calls fail.
    
    This exception is raised for:
    - HTTP errors (4xx, 5xx status codes)
    - Invalid JSON responses
    - Network/connection errors
    - Rate limiting (429 status code)
    """
    pass

def get_openrouter_headers(api_key: str) -> Dict[str, str]:
    '''
    Returns authentication and content-type headers for OpenRouter API (OpenAI-compatible).
    '''
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

class OpenRouterClient:
    '''
    Simple OpenAI-compatible client for OpenRouter API.
    Usage:
        client = OpenRouterClient(api_key, api_url)
        response = client.chat_completion({...})
    '''
    def __init__(self, api_key: str, api_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")

    def chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        '''
        Calls /chat/completions endpoint with the provided payload dict (OpenAI-compatible).
        Raises OpenRouterAPIError on HTTP/API errors.
        '''
        url = self.api_url + "/chat/completions"
        headers = get_openrouter_headers(self.api_key)
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise OpenRouterAPIError(f"HTTP {response.status_code}: {response.text}") from e
        try:
            return response.json()
        except Exception as je:
            raise OpenRouterAPIError(f"Invalid JSON response: {response.text}") from je

def create_prompt(email_content: str, max_chars: int = 4000) -> str:
    '''
    Generates the prompt text for keyword extraction.
    - Truncates email_content to max_chars, appends truncation marker if needed.
    - Instructions ensure response will be comma-separated keywords, AI-friendly.
    '''
    trunc_notice = "\n[Content truncated]"
    truncated = email_content
    if len(email_content) > max_chars:
        truncated = email_content[:max_chars]
        end_idx = truncated.rfind("\n", 0, max_chars)
        if end_idx > 30:
            truncated = truncated[:end_idx]
        truncated = truncated.rstrip() + trunc_notice

    prompt = (
        "Analyze the following email and extract the 3 most relevant tag keywords for categorization. "
        "Reply with keywords only, comma-separated:\n\n---\n"
        f"{truncated}\n---"
    )
    return prompt

def send_email_prompt_for_keywords(
    email_content: str,
    client: OpenRouterClient,
    max_chars: int = 4000,
    model: str = None,
    max_tokens: int = 32
) -> Dict[str, Any]:
    '''
    Calls OpenRouter AI API and returns the raw response dict. Uses the provided model or falls back to GPT-3.5-turbo.
    '''
    if not model:
        model = 'openai/gpt-3.5-turbo'
    prompt = create_prompt(email_content, max_chars)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise email tag extractor."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens
    }
    try:
        result = client.chat_completion(payload)
    except OpenRouterAPIError as err:
        raise
    return result

def extract_keywords_from_openrouter_response(response: Dict[str, Any]) -> List[str]:
    '''
    Given a response from OpenRouter/Chat API, extract keywords as a list of strings.
    '''
    content = None
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return []
    if "[" in content or "]" in content:
        try:
            import json
            arr = json.loads(content)
            if isinstance(arr, list):
                return [str(k).strip() for k in arr]
        except Exception:
            pass
    return [k.strip() for k in content.split(",") if k.strip()]

# Direct integration demo for dev/test (runs on every python execution)
print("[DEBUG] __name__ value is:", __name__)
print("[DEBUG] Loading .env/config ...")

conf = ConfigManager('config/config.yaml', '.env')
params = conf.openrouter_params()
print("[DEBUG] config.openrouter_params():", params)
api_key = params['api_key']
api_url = params['api_url']
model = params.get('model', 'openai/gpt-3.5-turbo')
print("[DEBUG] OPENROUTER_API_KEY:", repr(api_key))
print("[DEBUG] OPENROUTER_API_URL:", repr(api_url))
print("[DEBUG] MODEL:", repr(model))
if not api_key:
    print("Set OPENROUTER_API_KEY in your environment.")
    exit(1)
client = OpenRouterClient(api_key, api_url)
email_content = "This is a message about travel, invoices, and urgent delivery."
prompt = create_prompt(email_content, 100)
print("[DEBUG] Prompt:\n", prompt)
try:
    print("[DEBUG] Sending prompt with model:", model)
    api_result = send_email_prompt_for_keywords(email_content, client, 100, model=model)
    print("[DEBUG] API result:\n", api_result)
    keywords = extract_keywords_from_openrouter_response(api_result)
    print("[DEBUG] Extracted keywords:", keywords)
except Exception as e:
    print("[DEBUG] Error:", e)
