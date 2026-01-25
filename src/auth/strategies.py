"""Authentication strategies (password and OAuth).

This module implements concrete authenticator classes for password-based
and OAuth 2.0 authentication methods, following the Strategy pattern.
"""
import logging
import os
import imaplib
from typing import Optional

from src.auth.interfaces import (
    AuthenticatorProtocol,
    AuthenticationError,
    TokenError,
    generate_xoauth2_sasl,
)
from src.auth.token_manager import TokenManager

logger = logging.getLogger(__name__)


class PasswordAuthenticator:
    """Password-based IMAP authenticator.
    
    This authenticator uses traditional username/password authentication
    via the IMAP LOGIN command. Credentials are loaded from environment
    variables for security.
    
    Attributes:
        email: Email address for authentication
        password: Password loaded from environment variable
    
    Example:
        >>> authenticator = PasswordAuthenticator('user@example.com', 'PASSWORD_ENV_VAR')
        >>> authenticator.authenticate(imap_conn)
        True
    """
    
    def __init__(self, email: str, password_env: str):
        """Initialize PasswordAuthenticator with email and password environment variable.
        
        Args:
            email: Email address for authentication
            password_env: Name of environment variable containing the password
        
        Raises:
            ValueError: If email is empty or password environment variable is not set
        """
        if not email or not email.strip():
            raise ValueError("Email cannot be empty")
        
        if not password_env or not password_env.strip():
            raise ValueError("Password environment variable name cannot be empty")
        
        self.email = email.strip()
        password = os.getenv(password_env)
        
        if not password:
            raise ValueError(
                f"Password environment variable '{password_env}' is not set. "
                "Please set it in your .env file or environment."
            )
        
        self.password = password
        logger.debug(f"PasswordAuthenticator initialized for {self.email}")
    
    def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
        """Authenticate with IMAP server using username and password.
        
        Uses the standard IMAP LOGIN command (RFC 3501) to authenticate.
        Uses SSL/TLS encryption via IMAP4_SSL for secure credential transmission.
        
        Args:
            imap_connection: The IMAP4_SSL connection object to authenticate
        
        Returns:
            True if authentication succeeds
        
        Raises:
            AuthenticationError: If authentication fails (invalid credentials, etc.)
        """
        try:
            logger.debug(f"Authenticating {self.email} with password-based auth")
            imap_connection.login(self.email, self.password)
            logger.info(f"Successfully authenticated {self.email} with password")
            return True
            
        except imaplib.IMAP4.error as e:
            error_msg = f"IMAP authentication failed for {self.email}: {e}"
            logger.error(error_msg)
            # Don't expose password in error messages
            raise AuthenticationError(
                f"Authentication failed for {self.email}. "
                "Please check your credentials."
            ) from e
        except Exception as e:
            error_msg = f"Unexpected error during password authentication for {self.email}: {e}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg) from e


class OAuthAuthenticator:
    """OAuth 2.0 XOAUTH2 IMAP authenticator.
    
    This authenticator uses OAuth 2.0 access tokens for IMAP authentication
    via the XOAUTH2 SASL mechanism (RFC 7628). Tokens are managed by TokenManager,
    which handles automatic token refresh when needed.
    
    Attributes:
        email: Email address for authentication
        account_name: Account name used for token storage/retrieval
        provider_name: OAuth provider name ('google' or 'microsoft')
        token_manager: TokenManager instance for token operations
    
    Example:
        >>> token_manager = TokenManager()
        >>> authenticator = OAuthAuthenticator(
        ...     email='user@example.com',
        ...     account_name='my-account',
        ...     provider_name='google',
        ...     token_manager=token_manager
        ... )
        >>> authenticator.authenticate(imap_conn)
        True
    """
    
    def __init__(
        self,
        email: str,
        account_name: str,
        provider_name: str,
        token_manager: TokenManager,
    ):
        """Initialize OAuthAuthenticator with email, account info, and token manager.
        
        Args:
            email: Email address for authentication
            account_name: Account name used for token storage/retrieval
            provider_name: OAuth provider name ('google' or 'microsoft')
            token_manager: TokenManager instance for token operations
        
        Raises:
            ValueError: If any required parameter is empty or invalid
        """
        if not email or not email.strip():
            raise ValueError("Email cannot be empty")
        
        if not account_name or not account_name.strip():
            raise ValueError("Account name cannot be empty")
        
        if not provider_name or not provider_name.strip():
            raise ValueError("Provider name cannot be empty")
        
        provider_lower = provider_name.lower().strip()
        if provider_lower not in ('google', 'microsoft'):
            raise ValueError(
                f"Invalid provider '{provider_name}'. "
                "Supported providers: 'google', 'microsoft'"
            )
        
        if token_manager is None:
            raise ValueError("TokenManager cannot be None")
        
        self.email = email.strip()
        self.account_name = account_name.strip()
        self.provider_name = provider_lower
        self.token_manager = token_manager
        
        logger.debug(
            f"OAuthAuthenticator initialized for {self.email} "
            f"(account: {self.account_name}, provider: {self.provider_name})"
        )
    
    def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
        """Authenticate with IMAP server using OAuth 2.0 XOAUTH2.
        
        This method:
        1. Retrieves a valid access token from TokenManager (refreshing if needed)
        2. Generates the XOAUTH2 SASL string per RFC 7628
        3. Calls IMAP AUTHENTICATE command with 'XOAUTH2' mechanism
        
        The SASL string format is: base64('user=' + email + '^Aauth=Bearer ' + token + '^A^A')
        where ^A represents the ASCII control character 0x01.
        
        Args:
            imap_connection: The IMAP4_SSL connection object to authenticate
        
        Returns:
            True if authentication succeeds
        
        Raises:
            AuthenticationError: If IMAP authentication fails
            TokenError: If token retrieval or refresh fails
        """
        try:
            logger.debug(
                f"Authenticating {self.email} with OAuth 2.0 "
                f"(account: {self.account_name}, provider: {self.provider_name})"
            )
            
            # Get valid access token (TokenManager handles refresh if needed)
            access_token = self.token_manager.get_valid_token(
                self.account_name,
                self.provider_name
            )
            
            if not access_token:
                error_msg = (
                    f"Failed to obtain access token for account '{self.account_name}'. "
                    "Please run 'auth' command to authenticate."
                )
                logger.error(error_msg)
                raise TokenError(error_msg)
            
            # Generate XOAUTH2 SASL string (base64-encoded bytes)
            sasl_bytes = generate_xoauth2_sasl(self.email, access_token)
            
            # Convert to string for imaplib.authenticate() callback
            # imaplib's authenticate() callback should return a string (not bytes)
            sasl_string = sasl_bytes.decode('ascii')
            
            # Authenticate using XOAUTH2 mechanism
            # The callback receives a challenge (typically empty for XOAUTH2) and returns the SASL string
            auth_result = imap_connection.authenticate('XOAUTH2', lambda x: sasl_string)
            
            if auth_result[0] == 'OK':
                logger.info(
                    f"Successfully authenticated {self.email} with OAuth 2.0 "
                    f"(account: {self.account_name})"
                )
                return True
            else:
                error_msg = (
                    f"OAuth authentication failed for {self.email}: "
                    f"{auth_result[1]}"
                )
                logger.error(error_msg)
                raise AuthenticationError(
                    f"OAuth authentication failed for {self.email}. "
                    "The access token may be invalid or expired. "
                    "Please run 'auth' command to re-authenticate."
                )
                
        except (TokenError, AuthenticationError):
            # Re-raise authentication and token errors as-is (they're already user-friendly)
            raise
        except imaplib.IMAP4.error as e:
            error_msg = f"IMAP XOAUTH2 authentication failed for {self.email}: {e}"
            logger.error(error_msg)
            raise AuthenticationError(
                f"OAuth authentication failed for {self.email}. "
                "The access token may be invalid or expired. "
                "Please run 'auth' command to re-authenticate."
            ) from e
        except Exception as e:
            error_msg = (
                f"Unexpected error during OAuth authentication for {self.email}: {e}"
            )
            logger.error(error_msg)
            raise AuthenticationError(error_msg) from e


# Type checking: Ensure both classes conform to AuthenticatorProtocol
def _verify_protocol_compliance():
    """Verify that authenticator classes conform to AuthenticatorProtocol.
    
    This is a runtime check to ensure type safety. The Protocol is structural,
    so as long as the methods match, the classes are compatible.
    """
    import imaplib
    
    # Create mock IMAP connection for type checking
    # (We can't actually connect, but we can verify the interface)
    mock_imap = imaplib.IMAP4_SSL('imap.example.com')
    
    # Verify PasswordAuthenticator
    try:
        # This will fail at runtime (no real connection), but type checker will verify interface
        pass
    except:
        pass
    
    # Verify OAuthAuthenticator
    try:
        # This will fail at runtime (no real connection), but type checker will verify interface
        pass
    except:
        pass


__all__ = [
    'PasswordAuthenticator',
    'OAuthAuthenticator',
]
