"""Authentication interfaces and base classes.

This module defines the core interfaces and base classes for authentication
in the email agent, supporting both password-based and OAuth 2.0 authentication
methods via the Strategy pattern.
"""
import base64
import secrets
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol, TypedDict, Optional, Callable

import imaplib


# Type definitions for OAuth token management
class TokenInfo(TypedDict):
    """OAuth 2.0 token information structure.
    
    Attributes:
        access_token: The OAuth 2.0 access token string
        expires_at: Optional expiration timestamp (datetime object)
        refresh_token: Optional refresh token for obtaining new access tokens
    """
    access_token: str
    expires_at: Optional[datetime]
    refresh_token: Optional[str]


class OAuthConfig(TypedDict):
    """OAuth 2.0 configuration structure.
    
    Attributes:
        client_id: OAuth 2.0 client identifier
        client_secret: OAuth 2.0 client secret
        redirect_uri: OAuth 2.0 redirect URI for authorization callback
        scopes: List of OAuth 2.0 scopes to request
        auth_url: OAuth 2.0 authorization endpoint URL
        token_url: OAuth 2.0 token endpoint URL
    """
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    auth_url: str
    token_url: str


class AuthenticatorProtocol(Protocol):
    """Protocol for IMAP authentication strategies.
    
    This protocol defines the interface that all authentication strategies
    must implement. It supports both traditional password-based authentication
    and OAuth 2.0 XOAUTH2 SASL authentication.
    
    The authenticate method should:
    - For password auth: Call imap_connection.login(email, password)
    - For OAuth: Generate XOAUTH2 SASL string and call 
      imap_connection.authenticate('XOAUTH2', sasl_string)
    
    References:
        - RFC 3501: IMAP4 Protocol
        - RFC 7628: OAuth 2.0 SASL Mechanism (XOAUTH2)
        - RFC 6749: OAuth 2.0 Authorization Framework
    
    Example:
        >>> authenticator = PasswordAuthenticator(email, password)
        >>> authenticator.authenticate(imap_conn)
        True
    """
    
    def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
        """Authenticate with the IMAP server.
        
        Args:
            imap_connection: The IMAP4_SSL connection object to authenticate
            
        Returns:
            True if authentication succeeds, False otherwise
            
        Raises:
            AuthenticationError: If authentication fails
            TokenError: If token retrieval/refresh fails (OAuth only)
        """
        ...


# Custom exceptions for authentication errors
class TokenError(Exception):
    """Base exception for token-related errors."""
    pass


class OAuthError(TokenError):
    """Exception raised for OAuth 2.0 flow errors."""
    pass


class AuthExpiredError(TokenError):
    """Exception raised when authentication token has expired."""
    pass


class AuthenticationError(Exception):
    """Exception raised when IMAP authentication fails."""
    pass


class OAuthProvider(ABC):
    """Abstract base class for OAuth 2.0 providers.
    
    This class implements the Strategy pattern for OAuth 2.0 providers,
    supporting the Authorization Code Flow with optional PKCE (Proof Key
    for Code Exchange) for enhanced security.
    
    References:
        - RFC 6749: OAuth 2.0 Authorization Framework
        - RFC 7636: Proof Key for Code Exchange (PKCE)
        - RFC 6819: OAuth 2.0 Security Best Current Practice
    
    Security Best Practices:
        - Always validate state parameter to prevent CSRF attacks
        - Use PKCE for public clients when supported
        - Implement secure token storage and refresh mechanisms
        - Use HTTPS for all OAuth endpoints
    """
    
    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """Generate OAuth 2.0 authorization URL.
        
        Args:
            state: Cryptographically secure state parameter for CSRF protection.
                   Should be generated using generate_state() utility.
        
        Returns:
            Complete authorization URL with all required parameters
            
        Raises:
            OAuthError: If URL generation fails due to configuration issues
        """
        pass
    
    @abstractmethod
    def handle_callback(self, code: str, state: str) -> TokenInfo:
        """Handle OAuth 2.0 authorization callback and exchange code for tokens.
        
        Args:
            code: Authorization code received from OAuth provider
            state: State parameter that must match the one used in get_auth_url()
        
        Returns:
            TokenInfo dictionary containing access_token, refresh_token, and expires_at
        
        Raises:
            OAuthError: If code exchange fails
            ValueError: If state parameter doesn't match (CSRF protection)
        """
        pass
    
    @abstractmethod
    def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
        """Refresh an expired access token using refresh token.
        
        Args:
            token_info: Current token information containing refresh_token
        
        Returns:
            Updated TokenInfo with new access_token and updated expires_at
        
        Raises:
            AuthExpiredError: If refresh token is invalid or expired
            OAuthError: If token refresh fails
        """
        pass
    
    def validate_token(self, token_info: TokenInfo) -> bool:
        """Check if token is valid (not expired) with 5-minute buffer.
        
        This method checks token expiration with a 5-minute buffer to account
        for clock skew and ensure tokens are refreshed before they expire.
        
        Args:
            token_info: Token information to validate
        
        Returns:
            True if token is valid (not expired or expiring within 5 minutes),
            False otherwise
        """
        return is_token_valid(token_info, clock_skew=300)


# Token management utilities
def is_token_valid(token_info: TokenInfo, clock_skew: int = 300) -> bool:
    """Check if OAuth token is valid (not expired) with configurable clock skew.
    
    Args:
        token_info: Token information to validate
        clock_skew: Buffer time in seconds before expiration (default: 300 = 5 minutes)
    
    Returns:
        True if token is valid, False if expired or missing expiration info
    """
    if not token_info.get('expires_at'):
        # If no expiration info, assume token is invalid (conservative approach)
        return False
    
    expires_at = token_info['expires_at']
    if isinstance(expires_at, datetime):
        now = datetime.now()
        # Check if token expires more than clock_skew seconds in the future
        return (expires_at - now).total_seconds() > clock_skew
    
    return False


def parse_token_response(response: dict) -> TokenInfo:
    """Safely parse OAuth 2.0 token response and convert to TokenInfo.
    
    Args:
        response: Raw token response dictionary from OAuth provider
    
    Returns:
        TokenInfo dictionary with standardized structure
    
    Raises:
        TokenError: If response is missing required fields or malformed
    """
    if 'error' in response:
        error_desc = response.get('error_description', response['error'])
        raise TokenError(f"OAuth token error: {error_desc}")
    
    if 'access_token' not in response:
        raise TokenError("Missing access_token in token response")
    
    token_info: TokenInfo = {
        'access_token': response['access_token'],
        'expires_at': None,
        'refresh_token': response.get('refresh_token'),
    }
    
    # Parse expires_in if provided
    if 'expires_in' in response:
        from datetime import timedelta
        expires_in = response['expires_in']
        if isinstance(expires_in, (int, float)):
            token_info['expires_at'] = datetime.now() + timedelta(seconds=int(expires_in))
    
    return token_info


def generate_state() -> str:
    """Generate cryptographically secure state parameter for OAuth 2.0.
    
    The state parameter is used to prevent CSRF attacks by ensuring the
    authorization callback corresponds to the original authorization request.
    
    Returns:
        URL-safe random string suitable for OAuth state parameter
    """
    return secrets.token_urlsafe(32)


def generate_pkce_challenge() -> tuple[str, str]:
    """Generate PKCE (Proof Key for Code Exchange) challenge and verifier.
    
    PKCE enhances OAuth 2.0 security for public clients by using a dynamic
    challenge instead of a static client secret.
    
    Returns:
        Tuple of (code_verifier, code_challenge) where:
        - code_verifier: Random string (43-128 characters)
        - code_challenge: Base64URL-encoded SHA256 hash of verifier
    
    References:
        RFC 7636: Proof Key for Code Exchange by OAuth Public Clients
    """
    import hashlib
    
    # Generate code verifier (43-128 characters, URL-safe)
    code_verifier = secrets.token_urlsafe(32)
    
    # Generate code challenge (SHA256 hash, base64url encoded)
    code_challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge


# Provider factory type for dependency injection
ProviderFactory = Callable[[OAuthConfig], OAuthProvider]


# XOAUTH2 SASL utilities for IMAP authentication
def generate_xoauth2_sasl(user: str, access_token: str) -> bytes:
    """Generate XOAUTH2 SASL string for IMAP authentication.
    
    Implements the XOAUTH2 SASL mechanism per RFC 7628. The SASL string
    format is: base64('user=' + user + '^Aauth=Bearer ' + token + '^A^A')
    where ^A represents the ASCII control character 0x01.
    
    Args:
        user: Email address or username
        access_token: OAuth 2.0 access token
    
    Returns:
        Base64-encoded SASL string ready for IMAP authenticate() call
    
    Raises:
        ValueError: If user or token is empty or invalid
    
    References:
        RFC 7628: OAuth 2.0 SASL Mechanism
    
    Example:
        >>> sasl = generate_xoauth2_sasl('user@example.com', 'token123')
        >>> imap.authenticate('XOAUTH2', sasl)
    """
    validate_sasl_components(user, access_token)
    
    # Construct SASL string: user={user}\x01auth=Bearer {token}\x01\x01
    sasl_string = f"user={user}\x01auth=Bearer {access_token}\x01\x01"
    
    # Base64 encode
    return base64.b64encode(sasl_string.encode('utf-8'))


def validate_sasl_components(user: str, token: str) -> None:
    """Validate user and token for XOAUTH2 SASL string generation.
    
    Args:
        user: Email address or username to validate
        token: Access token to validate
    
    Raises:
        ValueError: If user or token is empty or contains invalid characters
    """
    if not user or not user.strip():
        raise ValueError("User cannot be empty")
    
    if not token or not token.strip():
        raise ValueError("Access token cannot be empty")
    
    # Basic validation: user should look like an email
    if '@' not in user:
        raise ValueError(f"Invalid user format (expected email): {user}")


# Backward compatibility and version tracking
def is_v4_compatible(provider: OAuthProvider) -> bool:
    """Check if OAuth provider is compatible with V4 configuration system.
    
    Args:
        provider: OAuth provider instance to check
    
    Returns:
        True if provider is compatible with V4, False otherwise
    """
    # All providers implementing OAuthProvider should be V4 compatible
    return isinstance(provider, OAuthProvider)


# Module exports
__all__ = [
    'AuthenticatorProtocol',
    'TokenInfo',
    'OAuthConfig',
    'OAuthProvider',
    'TokenError',
    'OAuthError',
    'AuthExpiredError',
    'AuthenticationError',
    'is_token_valid',
    'parse_token_response',
    'generate_state',
    'generate_pkce_challenge',
    'generate_xoauth2_sasl',
    'validate_sasl_components',
    'is_v4_compatible',
    'ProviderFactory',
]

# Version for backward compatibility tracking
__version__ = '1.0.0'
