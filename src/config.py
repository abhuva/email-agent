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

class ConfigFormatError(ConfigError):
    """
    Raised when configuration parameters have invalid formats or data types.
    
    This exception is raised for:
    - Invalid parameter types (e.g., string expected but got list)
    - Invalid parameter formats (e.g., empty strings where non-empty required)
    - Invalid parameter values (e.g., malformed IMAP query syntax)
    """
    pass

class ConfigPathError(ConfigError):
    """
    Raised when required file or directory paths don't exist.
    
    This exception is raised for:
    - Missing directories (e.g., obsidian_vault_path)
    - Missing files (e.g., summarization_prompt_path, changelog_path)
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

def validate_v2_config_paths(config: Dict[str, Any]) -> bool:
    """
    Validate that all required V2 file and directory paths exist.
    
    This function checks that:
    - obsidian_vault_path exists and is a directory
    - summarization_prompt_path exists and is a file (if specified)
    - changelog_path's parent directory exists (file itself can be created)
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if all required paths exist
        
    Raises:
        ConfigPathError: If any required paths don't exist or have wrong type
        
    Example:
        >>> config = {'obsidian_vault_path': '/path/to/vault', ...}
        >>> validate_v2_config_paths(config)
        True
    """
    errors = []
    
    # Validate obsidian_vault_path (required for V2)
    if 'obsidian_vault_path' in config:
        vault_path = config['obsidian_vault_path']
        if not os.path.exists(vault_path):
            errors.append(f"obsidian_vault_path does not exist: {vault_path} (expected: directory)")
        elif not os.path.isdir(vault_path):
            errors.append(f"obsidian_vault_path is not a directory: {vault_path}")
    
    # Validate summarization_prompt_path (required if summarization_tags is specified)
    if 'summarization_prompt_path' in config:
        prompt_path = config['summarization_prompt_path']
        if not os.path.exists(prompt_path):
            errors.append(f"summarization_prompt_path does not exist: {prompt_path} (expected: file)")
        elif not os.path.isfile(prompt_path):
            errors.append(f"summarization_prompt_path is not a file: {prompt_path}")
    
    # Validate changelog_path parent directory exists (file can be created)
    if 'changelog_path' in config:
        changelog = config['changelog_path']
        changelog_dir = os.path.dirname(os.path.abspath(changelog))
        if changelog_dir and not os.path.exists(changelog_dir):
            errors.append(f"changelog_path parent directory does not exist: {changelog_dir}")
        elif changelog_dir and not os.path.isdir(changelog_dir):
            errors.append(f"changelog_path parent is not a directory: {changelog_dir}")
    
    if errors:
        error_msg = "V2 configuration path errors:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigPathError(error_msg)
    
    return True

def validate_v2_config_format(config: Dict[str, Any]) -> bool:
    """
    Validate that V2 configuration parameters have correct data types and formats.
    
    This function validates the format of V2 parameters (obsidian_vault_path,
    summarization_tags, summarization_prompt_path, changelog_path, imap_query).
    It does NOT check if paths exist (that's done in validate_v2_config_paths).
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if all V2 parameters have valid formats
        
    Raises:
        ConfigFormatError: If any V2 parameter has an invalid format
        
    Example:
        >>> config = {'obsidian_vault_path': '/path/to/vault', ...}
        >>> validate_v2_config_format(config)
        True
    """
    errors = []
    
    # Validate obsidian_vault_path (if present)
    if 'obsidian_vault_path' in config:
        vault_path = config['obsidian_vault_path']
        if not isinstance(vault_path, str):
            errors.append("obsidian_vault_path must be a string")
        elif not vault_path.strip():
            errors.append("obsidian_vault_path cannot be empty")
    
    # Validate summarization_tags (if present)
    if 'summarization_tags' in config:
        tags = config['summarization_tags']
        if not isinstance(tags, list):
            errors.append("summarization_tags must be a list")
        else:
            for i, tag in enumerate(tags):
                if not isinstance(tag, str):
                    errors.append(f"summarization_tags[{i}] must be a string")
                elif not tag.strip():
                    errors.append(f"summarization_tags[{i}] cannot be empty")
    
    # Validate summarization_prompt_path (if present)
    if 'summarization_prompt_path' in config:
        prompt_path = config['summarization_prompt_path']
        if not isinstance(prompt_path, str):
            errors.append("summarization_prompt_path must be a string")
        elif not prompt_path.strip():
            errors.append("summarization_prompt_path cannot be empty")
    
    # Validate changelog_path (if present)
    if 'changelog_path' in config:
        changelog = config['changelog_path']
        if not isinstance(changelog, str):
            errors.append("changelog_path must be a string")
        elif not changelog.strip():
            errors.append("changelog_path cannot be empty")
    
    # Validate imap_query (if present)
    if 'imap_query' in config:
        query = config['imap_query']
        if not isinstance(query, str):
            errors.append("imap_query must be a string")
        elif not query.strip():
            errors.append("imap_query cannot be empty")
        # Basic IMAP query syntax check (should not contain newlines, should be reasonable length)
        if len(query.strip()) > 1000:
            errors.append("imap_query is too long (max 1000 characters)")
    
    if errors:
        error_msg = "V2 configuration format errors:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigFormatError(error_msg)
    
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
        imap_queries: List of IMAP queries (V1, for backward compatibility)
        imap_query: Primary IMAP query string (V2, takes precedence if set)
        obsidian_vault_path: Path to Obsidian vault directory (V2, optional)
        summarization_tags: List of IMAP tags that trigger summarization (V2, optional)
        summarization_prompt_path: Path to summarization prompt file (V2, optional)
        changelog_path: Path to changelog/audit log file (V2, optional)
        
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
        # Validate V2 config format if any V2 parameters are present
        validate_v2_config_format(self.yaml)
        # Validate V2 config paths if any V2 parameters are present
        validate_v2_config_paths(self.yaml)
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

        # V1 backward compatibility: imap_queries (list)
        self.imap_queries = self.yaml.get('imap_queries', ['UNSEEN'])
        
        # V2: New Obsidian integration parameters (optional for backward compatibility)
        self.obsidian_vault_path = self.yaml.get('obsidian_vault_path')
        self.summarization_tags = self.yaml.get('summarization_tags', [])
        self.summarization_prompt_path = self.yaml.get('summarization_prompt_path')
        self.changelog_path = self.yaml.get('changelog_path')
        # V2: Primary IMAP query (takes precedence over imap_queries if set)
        self.imap_query = self.yaml.get('imap_query')

        # Env secrets
        self.imap_password = os.environ[self.imap['password_env']]
        self.openrouter_api_key = os.environ[self.openrouter['api_key_env']]
        self.openrouter_api_url = self.openrouter['api_url']
        # Model extraction: config, then fallback to gpt-3.5-turbo
        self.openrouter_model = self.openrouter.get('model') or 'openai/gpt-3.5-turbo'
    
    def get_imap_query(self) -> str:
        """
        Get the IMAP query to use for email selection.
        
        V2: Returns imap_query if set, otherwise falls back to first item in imap_queries.
        This maintains backward compatibility with V1 while supporting V2's single query approach.
        
        Returns:
            IMAP query string
            
        Example:
            >>> query = config.get_imap_query()
            >>> print(query)
            'UNSEEN'
        """
        if self.imap_query:
            return self.imap_query
        # V1 backward compatibility
        if self.imap_queries and len(self.imap_queries) > 0:
            return self.imap_queries[0]
        # Default fallback
        return 'UNSEEN'

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
