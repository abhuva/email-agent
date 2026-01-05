import os
import yaml
from dotenv import load_dotenv
from typing import Any, Dict

class ConfigError(Exception):
    """
    Raised when configuration loading or validation fails.
    
    This exception is raised for:
    - Missing config files
    - Invalid YAML syntax
    - Missing required configuration keys
    - Missing required environment variables
    """
    pass

def load_yaml_config(path: str) -> Dict[str, Any]:
    """
    Load and parse a YAML configuration file.
    
    Args:
        path: Path to the YAML configuration file
        
    Returns:
        Dictionary containing the parsed configuration
        
    Raises:
        ConfigError: If the file doesn't exist or contains invalid YAML
        
    Example:
        >>> config = load_yaml_config('config/config.yaml')
        >>> print(config['imap']['server'])
        'imap.example.com'
    """
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    with open(path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error: {e}")
    return config

def validate_yaml_config(config: Dict[str, Any]) -> bool:
    """
    Validate that a configuration dictionary contains all required keys.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if validation passes
        
    Raises:
        ConfigError: If any required configuration keys are missing
        
    Example:
        >>> config = {'imap': {...}, 'prompt_file': '...'}
        >>> validate_yaml_config(config)
        True
    """
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
    """
    Load environment variables from a .env file.
    
    Args:
        env_path: Path to the .env file
        
    Raises:
        ConfigError: If the .env file doesn't exist
        
    Note:
        This function modifies os.environ by loading variables from the file.
        Variables are available via os.environ after this call.
        
    Example:
        >>> load_env_vars('.env')
        >>> api_key = os.environ.get('OPENROUTER_API_KEY')
    """
    if not os.path.exists(env_path):
        raise ConfigError(f"Env file not found: {env_path}")
    load_dotenv(env_path)

def validate_env_vars(config: Dict[str, Any]) -> bool:
    """
    Validate that all required environment variables are set.
    
    Args:
        config: Configuration dictionary containing env var names
        
    Returns:
        True if all required environment variables are present
        
    Raises:
        ConfigError: If any required environment variables are missing
        
    Example:
        >>> config = {'imap': {'password_env': 'IMAP_PASSWORD'}, ...}
        >>> validate_env_vars(config)
        True
    """
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
    Configuration manager that combines YAML and environment variable configuration.
    
    This class loads and validates configuration from both YAML files and .env files,
    providing convenient property access to configuration values.
    
    Args:
        yaml_path: Path to the YAML configuration file
        env_path: Path to the .env file containing secrets
        
    Raises:
        ConfigError: If configuration files are missing or invalid
        
    Attributes:
        imap: IMAP configuration dictionary
        prompt_file: Path to the prompt file
        tag_mapping: Dictionary mapping AI keywords to IMAP tags
        processed_tag: Tag name for processed emails
        max_body_chars: Maximum characters for email body truncation
        max_emails_per_run: Maximum emails to process per run
        log_file: Path to log file
        log_level: Logging level (INFO, DEBUG, etc.)
        analytics_file: Path to analytics JSONL file
        openrouter: OpenRouter configuration dictionary
        
    Example:
        >>> config = ConfigManager('config/config.yaml', '.env')
        >>> print(config.imap['server'])
        'imap.example.com'
        >>> print(config.max_emails_per_run)
        15
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

    def imap_connection_params(self) -> Dict[str, Any]:
        """
        Get IMAP connection parameters as a dictionary.
        
        Returns:
            Dictionary with keys: host, port, username, password
            
        Example:
            >>> params = config.imap_connection_params()
            >>> print(params['host'])
            'imap.example.com'
        """
        return {
            'host': self.imap['server'],
            'port': self.imap['port'],
            'username': self.imap['username'],
            'password': self.imap_password,
        }
    
    def openrouter_params(self) -> Dict[str, Any]:
        """
        Get OpenRouter API parameters as a dictionary.
        
        Returns:
            Dictionary with keys: api_key, api_url, model
            
        Example:
            >>> params = config.openrouter_params()
            >>> print(params['model'])
            'openai/gpt-3.5-turbo'
        """
        return {
            'api_key': self.openrouter_api_key,
            'api_url': self.openrouter_api_url,
            'model': self.openrouter_model,
        }
