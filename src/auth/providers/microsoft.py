"""Microsoft OAuth provider implementation.

This module implements the Microsoft OAuth 2.0 provider using the MSAL (Microsoft
Authentication Library) library. It supports the Authorization Code Flow with offline
access for refresh tokens.
"""
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import msal
import requests

from src.auth.interfaces import (
    OAuthProvider,
    TokenInfo,
    OAuthError,
    AuthExpiredError,
    parse_token_response,
)

logger = logging.getLogger(__name__)


class MicrosoftOAuthError(OAuthError):
    """Exception raised for Microsoft OAuth-specific errors."""
    pass


class MicrosoftOAuthProvider(OAuthProvider):
    """Microsoft OAuth 2.0 provider implementation.
    
    This provider implements the OAuth 2.0 Authorization Code Flow for Microsoft,
    specifically configured for Outlook IMAP access. It uses the MSAL library to
    handle the OAuth flow.
    
    Required environment variables:
        MS_CLIENT_ID: OAuth 2.0 client ID from Azure App Registration
        MS_CLIENT_SECRET: OAuth 2.0 client secret from Azure App Registration
    
    Scopes:
        https://outlook.office.com/IMAP.AccessAsUser.All - Required for Outlook IMAP access
        https://outlook.office.com/User.Read - For user identification
    
    Note: offline_access is a reserved scope in MSAL and should NOT be included in scopes.
    MSAL automatically handles refresh tokens when the app is configured with offline_access
    permission in Azure Portal API permissions.
    
    References:
        - Microsoft Identity Platform: https://learn.microsoft.com/en-us/entra/identity-platform/
        - MSAL Python: https://github.com/AzureAD/microsoft-authentication-library-for-python
        - Outlook IMAP Scopes: https://learn.microsoft.com/en-us/entra/identity-platform/scopes-oidc
    """
    
    # Microsoft OAuth 2.0 endpoints
    AUTHORITY = 'https://login.microsoftonline.com/common'
    TOKEN_ENDPOINT = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    
    # Required scopes for Outlook IMAP access
    # Note: 'offline_access' is a reserved scope in MSAL and should NOT be included here.
    # MSAL automatically handles refresh tokens when the app is configured with offline_access
    # permission in Azure Portal (which is already set up in the API permissions).
    DEFAULT_SCOPES = [
        'https://outlook.office.com/IMAP.AccessAsUser.All',  # Outlook IMAP access
        'https://outlook.office.com/User.Read',  # User profile
    ]
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[list[str]] = None,
    ):
        """Initialize Microsoft OAuth provider.
        
        Args:
            client_id: OAuth 2.0 client ID. If None, loaded from MS_CLIENT_ID env var.
            client_secret: OAuth 2.0 client secret. If None, loaded from MS_CLIENT_SECRET env var.
            redirect_uri: OAuth redirect URI. Defaults to http://localhost:8080/callback
            scopes: List of OAuth scopes. Defaults to Outlook IMAP scopes.
        
        Raises:
            MicrosoftOAuthError: If required credentials are missing
        """
        # Load credentials from environment if not provided
        self.client_id = client_id or os.getenv('MS_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('MS_CLIENT_SECRET')
        
        # Validate configuration
        self._validate_configuration()
        
        # Set redirect URI
        self.redirect_uri = redirect_uri or 'http://localhost:8080/callback'
        
        # Set scopes
        self.scopes = scopes or self.DEFAULT_SCOPES
        
        # Remove offline_access if present (MSAL reserved scope - handled automatically)
        if 'offline_access' in self.scopes:
            self.scopes = [s for s in self.scopes if s != 'offline_access']
            logger.debug("Removed 'offline_access' from scopes (MSAL reserved scope)")
        
        # Initialize MSAL PublicClientApplication
        # Note: For public clients, client_secret is not used in the app initialization
        # but may be needed for token refresh. We'll use ConfidentialClientApplication
        # if client_secret is provided, otherwise PublicClientApplication.
        if self.client_secret:
            # Use ConfidentialClientApplication for web apps with client secret
            self.app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.AUTHORITY,
            )
        else:
            # Use PublicClientApplication for desktop/mobile apps
            self.app = msal.PublicClientApplication(
                client_id=self.client_id,
                authority=self.AUTHORITY,
            )
        
        # Store flow state for callback validation
        self._flow: Optional[Dict[str, Any]] = None
        self._state: Optional[str] = None
        
        logger.debug(f"MicrosoftOAuthProvider initialized with client_id: {self.client_id[:10]}...")
    
    def get_auth_url(self, state: str, login_hint: Optional[str] = None) -> str:
        """Generate Microsoft OAuth 2.0 authorization URL.
        
        Args:
            state: Cryptographically secure state parameter for CSRF protection
            login_hint: Optional email address to pre-fill or guide account selection
        
        Returns:
            Complete authorization URL with all required parameters
        
        Raises:
            MicrosoftOAuthError: If URL generation fails
        """
        try:
            # Prepare additional parameters for account selection
            # Use prompt='select_account' to force account picker (prevents auto-login)
            # Use login_hint to pre-fill the email field if provided
            flow_kwargs = {
                'scopes': self.scopes,
                'redirect_uri': self.redirect_uri,
                'state': state,  # Pass our state to MSAL
                'prompt': 'select_account',  # Force account picker to show
            }
            
            # Add login_hint if provided (pre-fills email field)
            if login_hint:
                flow_kwargs['login_hint'] = login_hint
                logger.debug(f"Using login_hint: {login_hint}")
            
            # Initiate authorization code flow
            # MSAL manages the state parameter internally and includes it in the flow
            # We pass our state to MSAL, but must use the state from the flow for validation
            flow = self.app.initiate_auth_code_flow(**flow_kwargs)
            
            # Store flow for callback validation
            self._flow = flow
            
            # Extract state from flow - this is the state that will be in the callback URL
            # MSAL may encode/transform the state, so we must use what's in the flow
            flow_state = flow.get('state')
            if flow_state:
                # Use MSAL's state from the flow (this matches what will be in the callback)
                self._state = flow_state
                logger.debug(f"Using MSAL flow state: {flow_state[:16]}...")
            else:
                # Fallback to our state if MSAL doesn't provide one (shouldn't happen)
                self._state = state
                logger.warning("MSAL flow did not contain state, using provided state")
            
            # Extract authorization URL from flow
            auth_url = flow.get('auth_uri')
            if not auth_url:
                raise MicrosoftOAuthError("Failed to generate authorization URL: missing auth_uri in flow")
            
            logger.info(f"Generated Microsoft OAuth authorization URL with state: {self._state[:16]}...")
            return auth_url
            
        except Exception as e:
            error_msg = f"Failed to generate Microsoft OAuth authorization URL: {e}"
            logger.error(error_msg)
            raise MicrosoftOAuthError(error_msg) from e
    
    def handle_callback(self, code: str, state: str) -> TokenInfo:
        """Handle OAuth 2.0 authorization callback and exchange code for tokens.
        
        Args:
            code: Authorization code received from Microsoft
            state: State parameter that must match the one used in get_auth_url()
        
        Returns:
            TokenInfo dictionary containing access_token, refresh_token, and expires_at
        
        Raises:
            MicrosoftOAuthError: If code exchange fails
            ValueError: If state parameter doesn't match (CSRF protection)
        """
        # Input validation
        if not code or not code.strip():
            raise ValueError("Authorization code cannot be empty")
        if not state or not state.strip():
            raise ValueError("State parameter cannot be empty")
        
        # Validate state parameter
        if self._state is None or state != self._state:
            error_msg = "State parameter mismatch - possible CSRF attack"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate flow exists
        if not self._flow:
            error_msg = "No active authorization flow. Call get_auth_url() first."
            logger.error(error_msg)
            raise MicrosoftOAuthError(error_msg)
        
        try:
            # Prepare auth response dictionary from callback parameters
            # MSAL expects a dict with query parameters from the callback
            auth_response = {
                'code': code,
                'state': state,
            }
            
            # Exchange authorization code for tokens
            result = self.app.acquire_token_by_auth_code_flow(
                auth_code_flow=self._flow,
                auth_response=auth_response,
            )
            
            # Check for errors in result
            if 'error' in result:
                error_desc = result.get('error_description', result.get('error', 'Unknown error'))
                error_code = result.get('error')
                
                # Map common MSAL error codes to user-friendly messages
                if error_code == 'invalid_grant':
                    error_msg = f"Invalid or expired authorization code: {error_desc}"
                elif error_code == 'interaction_required':
                    error_msg = f"User interaction required: {error_desc}"
                elif error_code == 'consent_required':
                    error_msg = f"User consent required: {error_desc}"
                else:
                    error_msg = f"OAuth error ({error_code}): {error_desc}"
                
                logger.error(error_msg)
                raise MicrosoftOAuthError(error_msg)
            
            # Extract token information from result
            if 'access_token' not in result:
                raise MicrosoftOAuthError("Missing access_token in token response")
            
            # Parse expires_on (Unix timestamp) to datetime
            expires_at = None
            if 'expires_on' in result:
                expires_at = datetime.fromtimestamp(result['expires_on'])
            elif 'expires_in' in result:
                expires_in = result['expires_in']
                if isinstance(expires_in, (int, float)):
                    expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            
            token_info: TokenInfo = {
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token'),
                'expires_at': expires_at,
            }
            
            # Validate token response
            if not token_info['access_token']:
                raise MicrosoftOAuthError("Missing access_token in token response")
            
            logger.info("Successfully exchanged authorization code for tokens")
            return token_info
            
        except ValueError as e:
            # Re-raise ValueError (state mismatch) as-is
            raise
        except MicrosoftOAuthError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            error_msg = f"Failed to exchange authorization code for tokens: {e}"
            logger.error(error_msg)
            raise MicrosoftOAuthError(error_msg) from e
    
    def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
        """Refresh an expired access token using refresh token.
        
        Args:
            token_info: Current token information containing refresh_token
        
        Returns:
            Updated TokenInfo with new access_token and updated expires_at
        
        Raises:
            AuthExpiredError: If refresh token is invalid or expired
            MicrosoftOAuthError: If token refresh fails
        """
        refresh_token = token_info.get('refresh_token')
        if not refresh_token:
            error_msg = "No refresh token available for token refresh"
            logger.error(error_msg)
            raise AuthExpiredError(error_msg)
        
        try:
            # First, try to get accounts from cache (silent refresh)
            accounts = self.app.get_accounts()
            
            result = None
            if accounts:
                # Try silent token acquisition first (uses cached tokens)
                result = self.app.acquire_token_silent(
                    scopes=self.scopes,
                    account=accounts[0],  # Use first account if multiple
                )
            
            # If silent acquisition failed or no accounts, use refresh token
            if not result or 'access_token' not in result:
                # Use refresh token flow
                # Note: MSAL doesn't have a direct refresh_token method,
                # but we can use acquire_token_by_refresh_token if available
                # For ConfidentialClientApplication, we can use the refresh token directly
                # Check if app has acquire_token_by_refresh_token method (ConfidentialClientApplication)
                if hasattr(self.app, 'acquire_token_by_refresh_token'):
                    try:
                        # For confidential clients, we can use the refresh token
                        result = self.app.acquire_token_by_refresh_token(
                            refresh_token=refresh_token,
                            scopes=self.scopes,
                        )
                        # Check for errors immediately
                        if isinstance(result, dict) and 'error' in result:
                            error_desc = result.get('error_description', result.get('error', 'Unknown error'))
                            error_code = result.get('error')
                            
                            # Map common MSAL error codes
                            if error_code in ('invalid_grant', 'invalid_refresh_token', 'expired_token'):
                                error_msg = f"Refresh token is invalid or expired: {error_desc}"
                                logger.error(error_msg)
                                raise AuthExpiredError(error_msg)
                            else:
                                error_msg = f"Token refresh failed ({error_code}): {error_desc}"
                                logger.error(error_msg)
                                raise MicrosoftOAuthError(error_msg)
                    except (AttributeError, TypeError):
                        # Fall through to manual HTTP request
                        result = None
                    except (AuthExpiredError, MicrosoftOAuthError):
                        # Re-raise our custom errors
                        raise
                
                # If still no result, use manual HTTP request (for public clients or fallback)
                if not result or 'access_token' not in result:
                    # For public clients, manually construct the refresh request
                    # MSAL's PublicClientApplication handles refresh tokens via cache,
                    # but we need explicit refresh for our use case
                    token_endpoint = f"{self.AUTHORITY}/oauth2/v2.0/token"
                    data = {
                        'grant_type': 'refresh_token',
                        'refresh_token': refresh_token,
                        'client_id': self.client_id,
                        'scope': ' '.join(self.scopes),
                    }
                    
                    # Add client_secret if available (for confidential clients)
                    if self.client_secret:
                        data['client_secret'] = self.client_secret
                    
                    try:
                        response = requests.post(
                            token_endpoint,
                            data=data,
                            timeout=30,
                        )
                        response.raise_for_status()
                        result = response.json()
                    except requests.exceptions.Timeout:
                        error_msg = "Token refresh request timed out after 30 seconds"
                        logger.error(error_msg)
                        raise MicrosoftOAuthError(error_msg)
                    except requests.exceptions.RequestException as e:
                        error_msg = f"Network error during token refresh: {e}"
                        logger.error(error_msg)
                        raise MicrosoftOAuthError(error_msg) from e
            
            # Check for errors in result
            if isinstance(result, dict) and 'error' in result:
                error_desc = result.get('error_description', result.get('error', 'Unknown error'))
                error_code = result.get('error')
                
                # Map common MSAL error codes
                if error_code in ('invalid_grant', 'invalid_refresh_token', 'expired_token'):
                    error_msg = f"Refresh token is invalid or expired: {error_desc}"
                    logger.error(error_msg)
                    raise AuthExpiredError(error_msg)
                else:
                    error_msg = f"Token refresh failed ({error_code}): {error_desc}"
                    logger.error(error_msg)
                    raise MicrosoftOAuthError(error_msg)
            
            # Extract token information from result
            if 'access_token' not in result:
                raise MicrosoftOAuthError("Missing access_token in refresh response")
            
            # Parse expires_on (Unix timestamp) to datetime
            expires_at = None
            if 'expires_on' in result:
                expires_at = datetime.fromtimestamp(result['expires_on'])
            elif 'expires_in' in result:
                expires_in = result['expires_in']
                if isinstance(expires_in, (int, float)):
                    expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            
            # Build updated token info
            refreshed_token_info: TokenInfo = {
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token') or refresh_token,  # Keep old if not provided
                'expires_at': expires_at,
            }
            
            logger.info("Successfully refreshed Microsoft OAuth token")
            return refreshed_token_info
            
        except AuthExpiredError:
            # Re-raise auth expired errors
            raise
        except MicrosoftOAuthError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            error_msg = f"Failed to refresh Microsoft OAuth token: {e}"
            logger.error(error_msg)
            
            # Check if it's an auth error (invalid/expired refresh token)
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['invalid_grant', 'invalid_refresh_token', 'expired_token', '401', '403']):
                raise AuthExpiredError(f"Refresh token is invalid or expired: {e}") from e
            
            raise MicrosoftOAuthError(error_msg) from e
    
    def _validate_configuration(self) -> None:
        """Validate that all required credentials are available.
        
        Raises:
            MicrosoftOAuthError: If credentials are missing
        """
        if not self.client_id:
            raise MicrosoftOAuthError(
                "MS_CLIENT_ID environment variable is required. "
                "Set it in your .env file or environment."
            )
        
        # Note: client_secret is optional for PublicClientApplication
        # but recommended for ConfidentialClientApplication
        if not self.client_secret:
            logger.warning(
                "MS_CLIENT_SECRET not provided. Using PublicClientApplication. "
                "For production, consider using ConfidentialClientApplication with client_secret."
            )
