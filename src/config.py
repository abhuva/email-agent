import os
import yaml
from dotenv import load_dotenv
from typing import Any, Dict

class ConfigError(Exception):
    pass

def load_yaml_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    with open(path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error: {e}")
    return config

def validate_yaml_config(config: Dict[str, Any]) -> bool:
    required_top = ['imap', 'prompt_file', 'tag_mapping', 'processed_tag', 'max_body_chars', 'max_emails_per_run', 'log_file', 'log_level', 'analytics_file', 'openrouter']
    for key in required_top:
        if key not in config:
            raise ConfigError(f"Missing required config key: {key}")
    # Validate imap block
    imap_required = ['server', 'port', 'username', 'password_env']
    for k in imap_required:
        if k not in config['imap']:
            raise ConfigError(f"Missing required imap config key: {k}")
    # Validate openrouter block
    if not all(k in config['openrouter'] for k in ['api_key_env', 'api_url']):
        raise ConfigError("Missing openrouter configuration keys")
    return True

def load_env_vars(env_path: str) -> None:
    if not os.path.exists(env_path):
        raise ConfigError(f"Env file not found: {env_path}")
    load_dotenv(env_path)

def validate_env_vars(config: Dict[str, Any]) -> bool:
    imap_pw_var = config['imap']['password_env']
    router_var = config['openrouter']['api_key_env']
    missing = []
    for env_var in [imap_pw_var, router_var]:
        if not os.environ.get(env_var):
            missing.append(env_var)
    if missing:
        raise ConfigError(f"Missing required env vars: {missing}")
    return True

class ConfigManager:
    """
    Combines YAML and environment variable config.
    Provides typed property access and ensures validation at instantiation.
    """
    def __init__(self, yaml_path: str, env_path: str):
        self.yaml = load_yaml_config(yaml_path)
        validate_yaml_config(self.yaml)
        load_env_vars(env_path)
        validate_env_vars(self.yaml)
        self._build()

    def _build(self):
        # Expose each config section as property for convenient access
        self.imap = self.yaml['imap']
        self.prompt_file = self.yaml['prompt_file']
        self.tag_mapping = self.yaml['tag_mapping']
        self.processed_tag = self.yaml['processed_tag']
        self.max_body_chars = int(self.yaml['max_body_chars'])
        self.max_emails_per_run = int(self.yaml['max_emails_per_run'])
        self.log_file = self.yaml['log_file']
        self.log_level = self.yaml['log_level']
        self.analytics_file = self.yaml['analytics_file']
        self.openrouter = self.yaml['openrouter']

        # Env secrets
        self.imap_password = os.environ[self.imap['password_env']]
        self.openrouter_api_key = os.environ[self.openrouter['api_key_env']]
        self.openrouter_api_url = self.openrouter['api_url']
        # Model extraction: config, then fallback to gpt-3.5-turbo
        self.openrouter_model = self.openrouter.get('model') or 'openai/gpt-3.5-turbo'

    def imap_connection_params(self):
        return {
            'host': self.imap['server'],
            'port': self.imap['port'],
            'username': self.imap['username'],
            'password': self.imap_password,
        }
    
    def openrouter_params(self):
        return {
            'api_key': self.openrouter_api_key,
            'api_url': self.openrouter_api_url,
            'model': self.openrouter_model,
        }
