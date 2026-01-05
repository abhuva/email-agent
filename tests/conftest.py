import pytest
from pathlib import Path

@pytest.fixture
def valid_config_path(tmp_path):
    # Write a valid sample config.yaml for testing
    content = '''
imap:
  server: 'mail.example.com'
  port: 993
  username: 'testuser'
  password_env: 'IMAP_PASSWORD'
prompt_file: 'config/prompt.md'
tag_mapping:
  urgent: 'Urgent'
  neutral: 'Neutral'
  spam: 'Spam'
processed_tag: '[AI-Processed]'
max_body_chars: 4000
max_emails_per_run: 15
log_file: 'logs/agent.log'
log_level: 'INFO'
analytics_file: 'logs/analytics.jsonl'
openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1/ai-task'
'''
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)

@pytest.fixture
def invalid_config_path(tmp_path):
    # Write an invalid sample config.yaml (missing required fields)
    content = "openrouter: {}"
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)

@pytest.fixture
def valid_env_file(tmp_path):
    content = """IMAP_PASSWORD=validpassword\nOPENROUTER_API_KEY=validapikey\n"""
    p = tmp_path / ".env"
    p.write_text(content)
    return str(p)

@pytest.fixture
def invalid_env_file(tmp_path):
    content = """IMAP_PASSWORD=\n"""
    p = tmp_path / ".env"
    p.write_text(content)
    return str(p)
