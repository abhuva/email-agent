"""Token management for OAuth tokens."""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import requests

from src.auth.interfaces import TokenInfo, TokenError

logger = logging.getLogger(__name__)


class TokenRefreshError(TokenError):
    """Exception raised when token refresh fails."""
    pass


class TokenManager:
    """Manages OAuth token storage, loading, and refreshing.
    
    This class handles secure storage of OAuth tokens in JSON files within
    the credentials directory. Tokens are stored with restricted file permissions
    (0600) to prevent unauthorized access.
    
    Attributes:
        credentials_dir: Path to the credentials directory where tokens are stored
    """
    
    def __init__(self, credentials_dir: Optional[Path] = None):
        """Initialize TokenManager with credentials directory.
        
        Args:
            credentials_dir: Path to credentials directory. Defaults to 'credentials/'
                            in the project root if not specified.
        """
        if credentials_dir is None:
            # Default to 'credentials/' in project root
            # Assume project root is parent of src/
            project_root = Path(__file__).parent.parent.parent
            credentials_dir = project_root / 'credentials'
        
        self.credentials_dir = Path(credentials_dir)
        logger.debug(f"TokenManager initialized with credentials_dir: {self.credentials_dir}")
    
    def _get_token_path(self, account_name: str) -> Path:
        """Get the file path for an account's token file.
        
        Args:
            account_name: Name of the account
            
        Returns:
            Path to the token file (credentials/{account_name}.json)
        """
        # Sanitize account_name to prevent directory traversal
        safe_name = account_name.replace('/', '_').replace('\\', '_').replace('..', '_')
        return self.credentials_dir / f"{safe_name}.json"
    
    def save_tokens(self, account_name: str, tokens: Dict[str, Any]) -> None:
        """Save OAuth tokens to a JSON file.
        
        Creates the credentials directory if it doesn't exist and sets
        file permissions to 0600 (read/write for owner only).
        Uses atomic file writes (temp file + rename) for safety.
        
        Args:
            account_name: Name of the account
            tokens: Dictionary containing token information (access_token, 
                   refresh_token, expires_at, etc.)
        
        Raises:
            OSError: If directory creation or file write fails
            PermissionError: If file permissions cannot be set
            ValueError: If token structure is invalid
        """
        try:
            # Validate token structure before saving
            self._validate_token_structure(tokens)
            
            # Create credentials directory if it doesn't exist
            self.credentials_dir.mkdir(parents=True, exist_ok=True)
            
            # Set directory permissions to 0700 (owner only)
            # Note: On Windows, chmod may not fully work, but we try anyway
            try:
                os.chmod(self.credentials_dir, 0o700)
            except (OSError, AttributeError):
                # Windows may not support chmod fully, log but continue
                logger.debug(f"Could not set directory permissions on {self.credentials_dir}")
            
            token_path = self._get_token_path(account_name)
            
            # Convert datetime objects to ISO format strings for JSON serialization
            serializable_tokens = self._serialize_tokens(tokens)
            
            # Atomic file write: write to temp file, then rename
            import tempfile
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.credentials_dir,
                prefix=f".{account_name}.tmp.",
                suffix='.json'
            )
            
            try:
                # Write to temp file
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(serializable_tokens, f, indent=2, ensure_ascii=False)
                
                # Set temp file permissions to 0600
                try:
                    os.chmod(temp_path, 0o600)
                except (OSError, AttributeError):
                    logger.warning(f"Could not set temp file permissions on {temp_path}")
                
                # Atomic rename (replaces existing file atomically)
                os.replace(temp_path, token_path)
                
            except Exception:
                # Clean up temp file on error
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass
                raise
            
            # Set final file permissions to 0600 (read/write for owner only)
            try:
                os.chmod(token_path, 0o600)
            except (OSError, AttributeError):
                # Windows may not support chmod fully, log but continue
                logger.warning(f"Could not set file permissions on {token_path}")
            
            logger.info(f"Saved tokens for account '{account_name}' to {token_path}")
            
        except OSError as e:
            logger.error(f"Failed to save tokens for account '{account_name}': {e}")
            raise
        except PermissionError as e:
            logger.error(f"Permission denied saving tokens for account '{account_name}': {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid token structure for account '{account_name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving tokens for account '{account_name}': {e}")
            raise
    
    def load_tokens(self, account_name: str) -> Optional[Dict[str, Any]]:
        """Load OAuth tokens from a JSON file.
        
        Args:
            account_name: Name of the account
            
        Returns:
            Dictionary containing token information, or None if file doesn't exist
        
        Raises:
            PermissionError: If file cannot be read due to permissions
            json.JSONDecodeError: If file contains invalid JSON
            ValueError: If token structure is invalid
        """
        token_path = self._get_token_path(account_name)
        
        try:
            if not token_path.exists():
                logger.debug(f"Token file not found for account '{account_name}': {token_path}")
                return None
            
            with open(token_path, 'r', encoding='utf-8') as f:
                tokens = json.load(f)
            
            # Validate token structure
            try:
                self._validate_token_structure(tokens, strict=False)  # Allow V4 formats
            except ValueError as e:
                logger.warning(f"Token structure validation warning for account '{account_name}': {e}")
                # Continue anyway for backward compatibility
            
            # Deserialize datetime strings back to datetime objects
            deserialized_tokens = self._deserialize_tokens(tokens)
            
            logger.debug(f"Loaded tokens for account '{account_name}' from {token_path}")
            return deserialized_tokens
            
        except FileNotFoundError:
            logger.debug(f"Token file not found for account '{account_name}': {token_path}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied loading tokens for account '{account_name}': {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in token file for account '{account_name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading tokens for account '{account_name}': {e}")
            raise
    
    def _serialize_tokens(self, tokens: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tokens dictionary to JSON-serializable format.
        
        Converts datetime objects to ISO format strings.
        
        Args:
            tokens: Token dictionary that may contain datetime objects
            
        Returns:
            Dictionary with datetime objects converted to ISO strings
        """
        serializable = {}
        for key, value in tokens.items():
            if isinstance(value, datetime):
                serializable[key] = value.isoformat()
            else:
                serializable[key] = value
        return serializable
    
    def _deserialize_tokens(self, tokens: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tokens dictionary from JSON format back to Python types.
        
        Converts ISO format strings back to datetime objects for 'expires_at'.
        
        Args:
            tokens: Token dictionary from JSON (may contain ISO datetime strings)
            
        Returns:
            Dictionary with ISO strings converted back to datetime objects
        """
        deserialized = {}
        for key, value in tokens.items():
            if key == 'expires_at' and isinstance(value, str):
                try:
                    deserialized[key] = datetime.fromisoformat(value)
                except (ValueError, AttributeError):
                    # If parsing fails, keep as string
                    logger.warning(f"Could not parse expires_at as datetime: {value}")
                    deserialized[key] = value
            else:
                deserialized[key] = value
        return deserialized
    
    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if token is expired or will expire within 5 minutes.
        
        Applies a 5-minute buffer to account for clock skew and ensure tokens
        are refreshed before they expire. Handles multiple expiry formats:
        - expires_at: datetime object or ISO string
        - expires_in: seconds until expiry (calculated from current time)
        
        Args:
            tokens: Token dictionary containing expiry information
            
        Returns:
            True if token is expired or will expire within 5 minutes, False otherwise.
            Returns True (expired) if expiry information is missing or invalid.
        """
        # 5-minute buffer in seconds
        BUFFER_SECONDS = 300
        
        # Try to get expires_at (datetime object or ISO string)
        expires_at = tokens.get('expires_at')
        
        if expires_at is not None:
            try:
                # Handle datetime object
                if isinstance(expires_at, datetime):
                    expiry_time = expires_at
                # Handle ISO string
                elif isinstance(expires_at, str):
                    try:
                        expiry_time = datetime.fromisoformat(expires_at)
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid expires_at format: {expires_at}")
                        return True  # Treat as expired if we can't parse
                # Handle timestamp (float/int)
                elif isinstance(expires_at, (int, float)):
                    expiry_time = datetime.fromtimestamp(expires_at)
                else:
                    logger.warning(f"Unexpected expires_at type: {type(expires_at)}")
                    return True  # Treat as expired for unknown types
                
                # Check if token expires within buffer time
                now = datetime.now()
                time_until_expiry = (expiry_time - now).total_seconds()
                
                is_expired = time_until_expiry <= BUFFER_SECONDS
                
                if is_expired:
                    logger.debug(f"Token expired or expiring soon: {time_until_expiry:.0f}s until expiry")
                else:
                    logger.debug(f"Token valid: {time_until_expiry:.0f}s until expiry")
                
                return is_expired
                
            except Exception as e:
                logger.warning(f"Error checking token expiry: {e}")
                return True  # Treat as expired on error
        
        # Try to get expires_in (seconds until expiry from now)
        expires_in = tokens.get('expires_in')
        if expires_in is not None:
            try:
                expires_in_seconds = float(expires_in)
                # Calculate expiry time: current time + expires_in
                expiry_timestamp = time.time() + expires_in_seconds
                # Check if expires within buffer
                is_expired = expiry_timestamp <= (time.time() + BUFFER_SECONDS)
                
                if is_expired:
                    logger.debug(f"Token expired or expiring soon (expires_in={expires_in_seconds}s)")
                else:
                    logger.debug(f"Token valid (expires_in={expires_in_seconds}s)")
                
                return is_expired
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid expires_in value: {expires_in} ({e})")
                return True  # Treat as expired if we can't parse
        
        # No expiry information available - treat as expired (conservative approach)
        logger.warning("Token missing expiry information (expires_at and expires_in both missing)")
        return True
    
    def refresh_token(self, account_name: str, provider: str) -> Dict[str, Any]:
        """Refresh OAuth access token using refresh token.
        
        Implements OAuth 2.0 refresh token flow per RFC 6749. Loads existing
        tokens, constructs refresh request, and saves refreshed tokens.
        
        Args:
            account_name: Name of the account
            provider: OAuth provider name ('google' or 'microsoft')
        
        Returns:
            Dictionary containing refreshed token information
        
        Raises:
            TokenRefreshError: If refresh fails (invalid refresh token, network error, etc.)
            FileNotFoundError: If token file doesn't exist
        """
        # Load existing tokens
        tokens = self.load_tokens(account_name)
        if tokens is None:
            raise TokenRefreshError(f"No tokens found for account '{account_name}'")
        
        refresh_token = tokens.get('refresh_token')
        if not refresh_token:
            raise TokenRefreshError(f"No refresh token available for account '{account_name}'")
        
        # Get provider-specific configuration
        token_endpoint, client_id, client_secret = self._get_provider_config(provider)
        
        # Construct refresh request per OAuth 2.0 spec
        refresh_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
        }
        
        # Make refresh request
        try:
            logger.info(f"Refreshing token for account '{account_name}' (provider: {provider})")
            response = requests.post(
                token_endpoint,
                data=refresh_data,
                timeout=30,
                verify=True,  # SSL verification
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse response
            token_response = response.json()
            
            # Check for OAuth errors in response
            if 'error' in token_response:
                error_desc = token_response.get('error_description', token_response['error'])
                raise TokenRefreshError(f"OAuth token refresh error: {error_desc}")
            
            # Extract new token information
            new_access_token = token_response.get('access_token')
            if not new_access_token:
                raise TokenRefreshError("Missing access_token in refresh response")
            
            # Build updated token dictionary
            refreshed_tokens = {
                'access_token': new_access_token,
                'refresh_token': token_response.get('refresh_token', refresh_token),  # Use new if provided, else keep old
            }
            
            # Handle expires_in
            expires_in = token_response.get('expires_in')
            if expires_in:
                expires_in_seconds = int(expires_in)
                expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
                refreshed_tokens['expires_at'] = expires_at
                refreshed_tokens['expires_in'] = expires_in_seconds
            else:
                # If no expires_in, try to preserve existing expires_at
                if 'expires_at' in tokens:
                    refreshed_tokens['expires_at'] = tokens['expires_at']
            
            # Save refreshed tokens
            self.save_tokens(account_name, refreshed_tokens)
            
            logger.info(f"Successfully refreshed token for account '{account_name}'")
            return refreshed_tokens
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error refreshing token for account '{account_name}': {e}"
            logger.error(error_msg)
            raise TokenRefreshError(error_msg) from e
        except requests.exceptions.HTTPError as e:
            # 4xx or 5xx response
            status_code = e.response.status_code if hasattr(e, 'response') else None
            try:
                error_detail = e.response.json() if hasattr(e, 'response') and e.response else {}
                error_desc = error_detail.get('error_description', error_detail.get('error', str(e)))
            except:
                error_desc = str(e)
            
            error_msg = f"Token refresh failed for account '{account_name}' (HTTP {status_code}): {error_desc}"
            logger.error(error_msg)
            raise TokenRefreshError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error refreshing token for account '{account_name}': {e}"
            logger.error(error_msg)
            raise TokenRefreshError(error_msg) from e
    
    def _get_provider_config(self, provider: str) -> tuple[str, str, str]:
        """Get provider-specific OAuth configuration.
        
        Args:
            provider: Provider name ('google' or 'microsoft')
        
        Returns:
            Tuple of (token_endpoint, client_id, client_secret)
        
        Raises:
            TokenRefreshError: If provider is unknown or credentials are missing
        """
        provider_lower = provider.lower()
        
        if provider_lower == 'google':
            token_endpoint = 'https://oauth2.googleapis.com/token'
            client_id = os.getenv('GOOGLE_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        elif provider_lower == 'microsoft':
            token_endpoint = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
            client_id = os.getenv('MS_CLIENT_ID')
            client_secret = os.getenv('MS_CLIENT_SECRET')
        else:
            raise TokenRefreshError(f"Unknown provider: {provider} (supported: 'google', 'microsoft')")
        
        if not client_id:
            raise TokenRefreshError(f"Missing {provider.upper()}_CLIENT_ID environment variable")
        if not client_secret:
            raise TokenRefreshError(f"Missing {provider.upper()}_CLIENT_SECRET environment variable")
        
        return token_endpoint, client_id, client_secret
    
    def get_valid_token(self, account_name: str, provider: str) -> Optional[str]:
        """Get a valid access token, automatically refreshing if needed.
        
        This is the main public method for obtaining access tokens. It:
        1. Loads tokens from storage
        2. Checks if token is expired (with 5-minute buffer)
        3. Automatically refreshes if expired or missing
        4. Returns the access token string
        
        Includes retry logic for race conditions and brief caching of valid tokens.
        
        Args:
            account_name: Name of the account
            provider: OAuth provider name ('google' or 'microsoft')
        
        Returns:
            Access token string if available, None if refresh fails after retry
        """
        # Check cache first (brief TTL to avoid unnecessary file I/O)
        cache_key = f"{account_name}:{provider}"
        if hasattr(self, '_token_cache'):
            cached_entry = self._token_cache.get(cache_key)
            if cached_entry:
                token, expiry_time = cached_entry
                if time.time() < expiry_time:
                    logger.debug(f"Using cached token for account '{account_name}'")
                    return token
        else:
            self._token_cache = {}
        
        # Load tokens
        tokens = self.load_tokens(account_name)
        
        # If no tokens, try to refresh (will fail, but gives proper error)
        if tokens is None:
            logger.info(f"No tokens found for account '{account_name}', attempting refresh")
            try:
                tokens = self.refresh_token(account_name, provider)
            except TokenRefreshError as e:
                logger.error(f"Cannot get valid token for account '{account_name}': {e}")
                return None
        
        # Check if token is expired
        if self._is_token_expired(tokens):
            logger.info(f"Token expired for account '{account_name}', refreshing...")
            try:
                tokens = self.refresh_token(account_name, provider)
            except TokenRefreshError as e:
                logger.error(f"Token refresh failed for account '{account_name}': {e}")
                # Retry once for race conditions
                try:
                    logger.debug(f"Retrying token refresh for account '{account_name}'")
                    tokens = self.refresh_token(account_name, provider)
                except TokenRefreshError as retry_error:
                    logger.error(f"Token refresh retry failed for account '{account_name}': {retry_error}")
                    return None
        
        # Extract access token
        access_token = tokens.get('access_token')
        if not access_token:
            logger.error(f"No access_token in tokens for account '{account_name}'")
            return None
        
        # Cache token briefly (5 minutes TTL)
        cache_expiry = time.time() + 300
        self._token_cache[cache_key] = (access_token, cache_expiry)
        
        return access_token
    
    def _validate_token_structure(self, tokens: Dict[str, Any], strict: bool = True) -> None:
        """Validate token dictionary structure.
        
        Ensures required fields are present and have correct types.
        Handles both V5 (OAuth) and V4 (legacy) token formats for backward compatibility.
        
        Args:
            tokens: Token dictionary to validate
            strict: If True, require access_token. If False, allow V4 formats.
        
        Raises:
            ValueError: If token structure is invalid
        """
        if not isinstance(tokens, dict):
            raise ValueError("Tokens must be a dictionary")
        
        # V5 OAuth format: requires access_token
        if strict:
            if 'access_token' not in tokens:
                raise ValueError("Missing required field: access_token")
            if not isinstance(tokens['access_token'], str) or not tokens['access_token']:
                raise ValueError("access_token must be a non-empty string")
        
        # Optional fields validation
        if 'refresh_token' in tokens and tokens['refresh_token'] is not None:
            if not isinstance(tokens['refresh_token'], str) or not tokens['refresh_token']:
                raise ValueError("refresh_token must be a non-empty string if provided")
        
        if 'expires_at' in tokens and tokens['expires_at'] is not None:
            if not isinstance(tokens['expires_at'], (datetime, str, int, float)):
                raise ValueError("expires_at must be datetime, ISO string, or timestamp")
        
        if 'expires_in' in tokens and tokens['expires_in'] is not None:
            try:
                expires_in = float(tokens['expires_in'])
                # Allow negative expires_in for expired tokens (backward compatibility)
                # Only validate that it's a number
            except (ValueError, TypeError):
                raise ValueError("expires_in must be a number")
        
        # V4 backward compatibility: allow tokens without access_token if not strict
        # (V4 might have different structure)
        if not strict and 'access_token' not in tokens:
            logger.debug("Token structure appears to be V4 format (no access_token field)")
