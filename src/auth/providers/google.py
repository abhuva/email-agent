"""Google OAuth provider implementation.

This module implements the Google OAuth 2.0 provider using the google-auth-oauthlib
library. It supports the Authorization Code Flow with offline access for refresh tokens.
"""
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.auth.interfaces import (
    OAuthProvider,
    TokenInfo,
    OAuthError,
    AuthExpiredError,
    parse_token_response,
)

logger = logging.getLogger(__name__)


class GoogleOAuthError(OAuthError):
    """Exception raised for Google OAuth-specific errors."""
    pass


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth 2.0 provider implementation.
    
    This provider implements the OAuth 2.0 Authorization Code Flow for Google,
    specifically configured for Gmail IMAP access. It uses the google-auth-oauthlib
    library to handle the OAuth flow.
    
    Required environment variables:
        GOOGLE_CLIENT_ID: OAuth 2.0 client ID from Google Cloud Console
        GOOGLE_CLIENT_SECRET: OAuth 2.0 client secret from Google Cloud Console
    
    Scopes:
        https://mail.google.com/ - Required for Gmail IMAP access
        openid, email, profile - For user identification
    
    References:
        - Google OAuth 2.0: https://developers.google.com/identity/protocols/oauth2
        - Gmail API Scopes: https://developers.google.com/gmail/api/auth/scopes
    """
    
    # Google OAuth 2.0 endpoints
    AUTHORIZATION_BASE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
    
    # Required scopes for Gmail IMAP access
    DEFAULT_SCOPES = [
        'https://mail.google.com/',  # Gmail IMAP access
        'openid',  # OpenID Connect
        'email',   # User email
        'profile', # User profile
    ]
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[list[str]] = None,
    ):
        """Initialize Google OAuth provider.
        
        Args:
            client_id: OAuth 2.0 client ID. If None, loaded from GOOGLE_CLIENT_ID env var.
            client_secret: OAuth 2.0 client secret. If None, loaded from GOOGLE_CLIENT_SECRET env var.
            redirect_uri: OAuth redirect URI. Defaults to http://localhost:8080/callback
            scopes: List of OAuth scopes. Defaults to Gmail IMAP scopes.
        
        Raises:
            GoogleOAuthError: If required credentials are missing
        """
        # Load credentials from environment if not provided
        self.client_id = client_id or os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('GOOGLE_CLIENT_SECRET')
        
        # Validate configuration
        self._validate_configuration()
        
        # Set redirect URI
        self.redirect_uri = redirect_uri or 'http://localhost:8080/callback'
        
        # Set scopes
        self.scopes = scopes or self.DEFAULT_SCOPES
        
        # Store Flow object (will be created when needed)
        self._flow: Optional[Flow] = None
        self._state: Optional[str] = None
        
        logger.debug(f"GoogleOAuthProvider initialized with client_id: {self.client_id[:10]}...")
    
    def _validate_configuration(self) -> None:
        """Validate that all required credentials are available.
        
        Raises:
            GoogleOAuthError: If credentials are missing
        """
        if not self.client_id:
            raise GoogleOAuthError(
                "GOOGLE_CLIENT_ID environment variable is required. "
                "Set it in your .env file or environment."
            )
        
        if not self.client_secret:
            raise GoogleOAuthError(
                "GOOGLE_CLIENT_SECRET environment variable is required. "
                "Set it in your .env file or environment."
            )
    
    def _create_flow(self) -> Flow:
        """Create or return existing OAuth Flow object.
        
        Returns:
            Configured Flow object for OAuth 2.0 flow
        """
        if self._flow is None:
            # Create client config dict for Flow
            client_config = {
                'web': {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'auth_uri': self.AUTHORIZATION_BASE_URL,
                    'token_uri': self.TOKEN_ENDPOINT,
                    'redirect_uris': [self.redirect_uri],
                }
            }
            
            # Create Flow with offline access (for refresh tokens)
            self._flow = Flow.from_client_config(
                client_config,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri,
            )
            # Enable offline access to get refresh tokens
            self._flow.redirect_uri = self.redirect_uri
        
        return self._flow
    
    def get_auth_url(self, state: str) -> str:
        """Generate Google OAuth 2.0 authorization URL.
        
        Args:
            state: Cryptographically secure state parameter for CSRF protection
        
        Returns:
            Complete authorization URL with all required parameters
        
        Raises:
            GoogleOAuthError: If URL generation fails
        """
        try:
            flow = self._create_flow()
            self._state = state  # Store state for validation
            
            # Generate authorization URL
            auth_url, _ = flow.authorization_url(
                access_type='offline',  # Required for refresh tokens
                include_granted_scopes='true',
                state=state,
                prompt='consent',  # Force consent to ensure refresh token
            )
            
            logger.info(f"Generated Google OAuth authorization URL with state: {state[:16]}...")
            return auth_url
            
        except Exception as e:
            error_msg = f"Failed to generate Google OAuth authorization URL: {e}"
            logger.error(error_msg)
            raise GoogleOAuthError(error_msg) from e
    
    def handle_callback(self, code: str, state: str) -> TokenInfo:
        """Handle OAuth 2.0 authorization callback and exchange code for tokens.
        
        Args:
            code: Authorization code received from Google
            state: State parameter that must match the one used in get_auth_url()
        
        Returns:
            TokenInfo dictionary containing access_token, refresh_token, and expires_at
        
        Raises:
            GoogleOAuthError: If code exchange fails
            ValueError: If state parameter doesn't match (CSRF protection)
        """
        # Validate state parameter
        if self._state is None or state != self._state:
            error_msg = "State parameter mismatch - possible CSRF attack"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            flow = self._create_flow()
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=code)
            
            # Get credentials from flow
            credentials: Credentials = flow.credentials
            
            # Extract token information
            token_info: TokenInfo = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'expires_at': credentials.expiry,  # datetime object
            }
            
            # Validate token response
            if not token_info['access_token']:
                raise GoogleOAuthError("Missing access_token in token response")
            
            logger.info("Successfully exchanged authorization code for tokens")
            return token_info
            
        except ValueError as e:
            # Re-raise ValueError (state mismatch) as-is
            raise
        except Exception as e:
            error_msg = f"Failed to exchange authorization code for tokens: {e}"
            logger.error(error_msg)
            raise GoogleOAuthError(error_msg) from e
    
    def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
        """Refresh an expired access token using refresh token.
        
        Args:
            token_info: Current token information containing refresh_token
        
        Returns:
            Updated TokenInfo with new access_token and updated expires_at
        
        Raises:
            AuthExpiredError: If refresh token is invalid or expired
            GoogleOAuthError: If token refresh fails
        """
        refresh_token = token_info.get('refresh_token')
        if not refresh_token:
            error_msg = "No refresh token available for token refresh"
            logger.error(error_msg)
            raise AuthExpiredError(error_msg)
        
        try:
            # Create credentials object from existing tokens
            credentials = Credentials(
                token=token_info.get('access_token'),
                refresh_token=refresh_token,
                token_uri=self.TOKEN_ENDPOINT,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            
            # Refresh the token
            credentials.refresh(Request())
            
            # Build updated token info
            refreshed_token_info: TokenInfo = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token or refresh_token,  # Keep old if not provided
                'expires_at': credentials.expiry,  # datetime object
            }
            
            logger.info("Successfully refreshed Google OAuth token")
            return refreshed_token_info
            
        except Exception as e:
            error_msg = f"Failed to refresh Google OAuth token: {e}"
            logger.error(error_msg)
            
            # Check if it's an auth error (invalid/expired refresh token)
            if 'invalid_grant' in str(e).lower() or 'invalid_token' in str(e).lower():
                raise AuthExpiredError(f"Refresh token is invalid or expired: {e}") from e
            
            raise GoogleOAuthError(error_msg) from e
    
    def exchange_code_for_tokens(self, code: str, state: str) -> TokenInfo:
        """Exchange authorization code for tokens (alias for handle_callback).
        
        This method is provided for backward compatibility and clarity.
        
        Args:
            code: Authorization code received from Google
            state: State parameter that must match the one used in get_auth_url()
        
        Returns:
            TokenInfo dictionary containing access_token, refresh_token, and expires_at
        """
        return self.handle_callback(code, state)
