"""
Tests for Microsoft OAuth provider implementation.

Tests verify authorization URL generation, token exchange, refresh flows,
error handling, and integration with MSAL library.
"""
import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.auth.providers.microsoft import MicrosoftOAuthProvider, MicrosoftOAuthError
from src.auth.interfaces import TokenInfo, OAuthError, AuthExpiredError


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for Microsoft OAuth."""
    monkeypatch.setenv('MS_CLIENT_ID', 'test_client_id_123')
    monkeypatch.setenv('MS_CLIENT_SECRET', 'test_client_secret_456')


@pytest.fixture
def microsoft_provider(mock_env_vars):
    """Create a MicrosoftOAuthProvider instance with mocked credentials."""
    return MicrosoftOAuthProvider()


@pytest.fixture
def valid_token_info():
    """Sample valid token information."""
    return {
        'access_token': 'test_access_token_123',
        'refresh_token': 'test_refresh_token_456',
        'expires_at': datetime.now() + timedelta(hours=1),
    }


class TestMicrosoftOAuthProviderInitialization:
    """Test MicrosoftOAuthProvider initialization."""
    
    def test_init_loads_env_vars(self, mock_env_vars):
        """Test that provider loads credentials from environment variables."""
        provider = MicrosoftOAuthProvider()
        assert provider.client_id == 'test_client_id_123'
        assert provider.client_secret == 'test_client_secret_456'
    
    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials."""
        provider = MicrosoftOAuthProvider(
            client_id='explicit_id',
            client_secret='explicit_secret',
        )
        assert provider.client_id == 'explicit_id'
        assert provider.client_secret == 'explicit_secret'
    
    def test_init_missing_client_id(self, monkeypatch):
        """Test that missing MS_CLIENT_ID raises error."""
        monkeypatch.delenv('MS_CLIENT_ID', raising=False)
        monkeypatch.setenv('MS_CLIENT_SECRET', 'secret')
        
        with pytest.raises(MicrosoftOAuthError, match="MS_CLIENT_ID"):
            MicrosoftOAuthProvider()
    
    def test_init_missing_client_secret_warning(self, monkeypatch):
        """Test that missing MS_CLIENT_SECRET logs warning but doesn't fail."""
        monkeypatch.setenv('MS_CLIENT_ID', 'id')
        monkeypatch.delenv('MS_CLIENT_SECRET', raising=False)
        
        # Should not raise error, but use PublicClientApplication
        provider = MicrosoftOAuthProvider()
        assert provider.client_id == 'id'
        assert provider.client_secret is None
    
    def test_init_default_scopes(self, microsoft_provider):
        """Test that default scopes include Outlook IMAP scopes."""
        assert 'https://outlook.office.com/IMAP.AccessAsUser.All' in microsoft_provider.scopes
        assert 'https://outlook.office.com/User.Read' in microsoft_provider.scopes
        assert 'offline_access' in microsoft_provider.scopes
    
    def test_init_adds_offline_access_if_missing(self, mock_env_vars):
        """Test that offline_access scope is automatically added if missing."""
        custom_scopes = ['https://outlook.office.com/IMAP.AccessAsUser.All']
        provider = MicrosoftOAuthProvider(scopes=custom_scopes)
        assert 'offline_access' in provider.scopes
    
    def test_init_custom_scopes(self, mock_env_vars):
        """Test initialization with custom scopes."""
        custom_scopes = ['https://outlook.office.com/IMAP.AccessAsUser.All', 'custom_scope']
        provider = MicrosoftOAuthProvider(scopes=custom_scopes)
        # Should include custom scopes plus offline_access
        assert 'https://outlook.office.com/IMAP.AccessAsUser.All' in provider.scopes
        assert 'custom_scope' in provider.scopes
        assert 'offline_access' in provider.scopes
    
    def test_init_default_redirect_uri(self, microsoft_provider):
        """Test that default redirect URI is set correctly."""
        assert microsoft_provider.redirect_uri == 'http://localhost:8080/callback'
    
    def test_init_custom_redirect_uri(self, mock_env_vars):
        """Test initialization with custom redirect URI."""
        provider = MicrosoftOAuthProvider(redirect_uri='http://localhost:9000/callback')
        assert provider.redirect_uri == 'http://localhost:9000/callback'
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_init_uses_confidential_client_with_secret(self, mock_confidential_class, mock_env_vars):
        """Test that ConfidentialClientApplication is used when client_secret is provided."""
        provider = MicrosoftOAuthProvider()
        mock_confidential_class.assert_called_once()
        call_kwargs = mock_confidential_class.call_args[1]
        assert call_kwargs['client_id'] == 'test_client_id_123'
        assert call_kwargs['client_credential'] == 'test_client_secret_456'
        assert call_kwargs['authority'] == MicrosoftOAuthProvider.AUTHORITY
    
    @patch('src.auth.providers.microsoft.msal.PublicClientApplication')
    def test_init_uses_public_client_without_secret(self, mock_public_class, monkeypatch):
        """Test that PublicClientApplication is used when client_secret is not provided."""
        monkeypatch.setenv('MS_CLIENT_ID', 'id')
        monkeypatch.delenv('MS_CLIENT_SECRET', raising=False)
        
        provider = MicrosoftOAuthProvider()
        mock_public_class.assert_called_once()
        call_kwargs = mock_public_class.call_args[1]
        assert call_kwargs['client_id'] == 'id'
        assert call_kwargs['authority'] == MicrosoftOAuthProvider.AUTHORITY


class TestGetAuthUrl:
    """Test authorization URL generation."""
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_get_auth_url_success(self, mock_app_class, microsoft_provider):
        """Test successful authorization URL generation."""
        # Mock MSAL app
        mock_app = MagicMock()
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state=test_state',
            'state': 'test_state',
        }
        mock_app.initiate_auth_code_flow.return_value = mock_flow
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        state = 'test_state_123'
        auth_url = microsoft_provider.get_auth_url(state)
        
        assert 'login.microsoftonline.com' in auth_url
        assert microsoft_provider._state == state
        mock_app.initiate_auth_code_flow.assert_called_once_with(
            scopes=microsoft_provider.scopes,
            redirect_uri=microsoft_provider.redirect_uri,
        )
        assert microsoft_provider._flow == mock_flow
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_get_auth_url_missing_auth_uri(self, mock_app_class, microsoft_provider):
        """Test error when auth_uri is missing in flow."""
        mock_app = MagicMock()
        mock_flow = {'state': 'test_state'}  # Missing auth_uri
        mock_app.initiate_auth_code_flow.return_value = mock_flow
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        with pytest.raises(MicrosoftOAuthError, match="missing auth_uri"):
            microsoft_provider.get_auth_url('state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_get_auth_url_error_handling(self, mock_app_class, microsoft_provider):
        """Test error handling in authorization URL generation."""
        mock_app = MagicMock()
        mock_app.initiate_auth_code_flow.side_effect = Exception("Flow creation failed")
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        with pytest.raises(MicrosoftOAuthError, match="Failed to generate"):
            microsoft_provider.get_auth_url('state')


class TestHandleCallback:
    """Test authorization callback handling and token exchange."""
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_success(self, mock_app_class, microsoft_provider, valid_token_info):
        """Test successful callback handling and token exchange."""
        # Mock MSAL app and flow
        mock_app = MagicMock()
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/...',
            'state': 'test_state_123',
        }
        mock_result = {
            'access_token': valid_token_info['access_token'],
            'refresh_token': valid_token_info['refresh_token'],
            'expires_on': int((valid_token_info['expires_at']).timestamp()),
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        # Set state and flow for validation
        state = 'test_state_123'
        microsoft_provider._state = state
        microsoft_provider._flow = mock_flow
        
        code = 'authorization_code_123'
        token_info = microsoft_provider.handle_callback(code, state)
        
        assert token_info['access_token'] == valid_token_info['access_token']
        assert token_info['refresh_token'] == valid_token_info['refresh_token']
        assert token_info['expires_at'] is not None
        
        # Verify acquire_token_by_auth_code_flow was called
        mock_app.acquire_token_by_auth_code_flow.assert_called_once()
        call_kwargs = mock_app.acquire_token_by_auth_code_flow.call_args[1]
        assert call_kwargs['auth_code_flow'] == mock_flow
        assert call_kwargs['auth_response']['code'] == code
        assert call_kwargs['auth_response']['state'] == state
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_state_mismatch(self, mock_app_class, microsoft_provider):
        """Test that state mismatch raises ValueError."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'stored_state'
        microsoft_provider._flow = {'auth_uri': '...'}
        
        with pytest.raises(ValueError, match="State parameter mismatch"):
            microsoft_provider.handle_callback('code', 'different_state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_no_state(self, mock_app_class, microsoft_provider):
        """Test that missing stored state raises ValueError."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = None
        microsoft_provider._flow = {'auth_uri': '...'}
        
        with pytest.raises(ValueError, match="State parameter mismatch"):
            microsoft_provider.handle_callback('code', 'any_state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_no_flow(self, mock_app_class, microsoft_provider):
        """Test that missing flow raises error."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'state'
        microsoft_provider._flow = None
        
        with pytest.raises(MicrosoftOAuthError, match="No active authorization flow"):
            microsoft_provider.handle_callback('code', 'state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_empty_code(self, mock_app_class, microsoft_provider):
        """Test that empty authorization code raises ValueError."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'state'
        microsoft_provider._flow = {'auth_uri': '...'}
        
        with pytest.raises(ValueError, match="Authorization code cannot be empty"):
            microsoft_provider.handle_callback('', 'state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_empty_state(self, mock_app_class, microsoft_provider):
        """Test that empty state parameter raises ValueError."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'state'
        microsoft_provider._flow = {'auth_uri': '...'}
        
        with pytest.raises(ValueError, match="State parameter cannot be empty"):
            microsoft_provider.handle_callback('code', '')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_missing_access_token(self, mock_app_class, microsoft_provider):
        """Test error when access token is missing in response."""
        mock_app = MagicMock()
        mock_result = {
            'refresh_token': 'refresh',
            'expires_on': int((datetime.now() + timedelta(hours=1)).timestamp()),
            # Missing access_token
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'state'
        microsoft_provider._flow = {'auth_uri': '...'}
        
        with pytest.raises(MicrosoftOAuthError, match="Missing access_token"):
            microsoft_provider.handle_callback('code', 'state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_error_response(self, mock_app_class, microsoft_provider):
        """Test error handling when MSAL returns error response."""
        mock_app = MagicMock()
        mock_result = {
            'error': 'invalid_grant',
            'error_description': 'Authorization code expired',
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'state'
        microsoft_provider._flow = {'auth_uri': '...'}
        
        with pytest.raises(MicrosoftOAuthError, match="Invalid or expired authorization code"):
            microsoft_provider.handle_callback('code', 'state')
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_handle_callback_expires_in_fallback(self, mock_app_class, microsoft_provider):
        """Test that expires_in is used when expires_on is not available."""
        mock_app = MagicMock()
        mock_result = {
            'access_token': 'token',
            'refresh_token': 'refresh',
            'expires_in': 3600,  # Use expires_in instead of expires_on
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        microsoft_provider._state = 'state'
        microsoft_provider._flow = {'auth_uri': '...'}
        
        token_info = microsoft_provider.handle_callback('code', 'state')
        assert token_info['expires_at'] is not None
        # Should be approximately 1 hour from now
        expected_expiry = datetime.now() + timedelta(seconds=3600)
        assert abs((token_info['expires_at'] - expected_expiry).total_seconds()) < 5


class TestRefreshToken:
    """Test token refresh functionality."""
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_refresh_token_success_silent(self, mock_app_class, microsoft_provider, valid_token_info):
        """Test successful token refresh using silent acquisition."""
        # Mock MSAL app with cached account
        mock_app = MagicMock()
        mock_account = {'username': 'test@example.com'}
        mock_app.get_accounts.return_value = [mock_account]
        mock_result = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_on': int((datetime.now() + timedelta(hours=1)).timestamp()),
        }
        mock_app.acquire_token_silent.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        refreshed = microsoft_provider.refresh_token(valid_token_info)
        
        assert refreshed['access_token'] == 'new_access_token'
        assert refreshed['refresh_token'] == 'new_refresh_token'
        assert refreshed['expires_at'] is not None
        
        # Verify silent acquisition was attempted
        mock_app.acquire_token_silent.assert_called_once_with(
            scopes=microsoft_provider.scopes,
            account=mock_account,
        )
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_refresh_token_success_by_refresh_token(self, mock_app_class, microsoft_provider, valid_token_info):
        """Test successful token refresh using acquire_token_by_refresh_token."""
        # Mock MSAL app without cached accounts
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []  # No cached accounts
        mock_app.acquire_token_silent.return_value = None  # Silent acquisition fails
        mock_result = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_on': int((datetime.now() + timedelta(hours=1)).timestamp()),
        }
        mock_app.acquire_token_by_refresh_token.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        refreshed = microsoft_provider.refresh_token(valid_token_info)
        
        assert refreshed['access_token'] == 'new_access_token'
        assert refreshed['refresh_token'] == 'new_refresh_token'
        
        # Verify refresh token method was called
        mock_app.acquire_token_by_refresh_token.assert_called_once_with(
            refresh_token=valid_token_info['refresh_token'],
            scopes=microsoft_provider.scopes,
        )
    
    @patch('src.auth.providers.microsoft.msal.PublicClientApplication')
    @patch('src.auth.providers.microsoft.requests.post')
    def test_refresh_token_public_client_manual(self, mock_requests_post, mock_public_class, monkeypatch, valid_token_info):
        """Test token refresh for PublicClientApplication using manual HTTP request."""
        monkeypatch.setenv('MS_CLIENT_ID', 'id')
        monkeypatch.delenv('MS_CLIENT_SECRET', raising=False)
        
        provider = MicrosoftOAuthProvider()
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        refreshed = provider.refresh_token(valid_token_info)
        
        assert refreshed['access_token'] == 'new_access_token'
        assert refreshed['refresh_token'] == 'new_refresh_token'
        
        # Verify HTTP request was made
        mock_requests_post.assert_called_once()
        call_kwargs = mock_requests_post.call_args
        assert 'login.microsoftonline.com' in call_kwargs[0][0]
        assert call_kwargs[1]['data']['grant_type'] == 'refresh_token'
        assert call_kwargs[1]['data']['refresh_token'] == valid_token_info['refresh_token']
        assert call_kwargs[1]['timeout'] == 30
    
    def test_refresh_token_missing_refresh_token(self, microsoft_provider):
        """Test error when refresh token is missing."""
        token_info: TokenInfo = {
            'access_token': 'token',
            'expires_at': None,
            'refresh_token': None,  # Missing
        }
        
        with pytest.raises(AuthExpiredError, match="No refresh token"):
            microsoft_provider.refresh_token(token_info)
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_refresh_token_invalid_grant(self, mock_app_class, microsoft_provider, valid_token_info):
        """Test error handling for invalid_grant (expired refresh token)."""
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []
        mock_app.acquire_token_silent.return_value = None  # Silent acquisition fails
        mock_result = {
            'error': 'invalid_grant',
            'error_description': 'Refresh token expired',
        }
        # Make acquire_token_by_refresh_token return the error dict
        mock_app.acquire_token_by_refresh_token.return_value = mock_result
        # Make sure hasattr returns True so we use this method
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        with pytest.raises(AuthExpiredError, match="Refresh token is invalid"):
            microsoft_provider.refresh_token(valid_token_info)
    
    @patch('src.auth.providers.microsoft.msal.PublicClientApplication')
    @patch('src.auth.providers.microsoft.requests.post')
    def test_refresh_token_network_timeout(self, mock_requests_post, mock_public_class, monkeypatch, valid_token_info):
        """Test error handling for network timeout."""
        import requests
        monkeypatch.setenv('MS_CLIENT_ID', 'id')
        monkeypatch.delenv('MS_CLIENT_SECRET', raising=False)
        
        provider = MicrosoftOAuthProvider()
        mock_requests_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with pytest.raises(MicrosoftOAuthError, match="timed out"):
            provider.refresh_token(valid_token_info)
    
    @patch('src.auth.providers.microsoft.msal.PublicClientApplication')
    @patch('src.auth.providers.microsoft.requests.post')
    def test_refresh_token_network_error(self, mock_requests_post, mock_public_class, monkeypatch, valid_token_info):
        """Test error handling for network errors."""
        import requests
        monkeypatch.setenv('MS_CLIENT_ID', 'id')
        monkeypatch.delenv('MS_CLIENT_SECRET', raising=False)
        
        provider = MicrosoftOAuthProvider()
        mock_requests_post.side_effect = requests.exceptions.RequestException("Network error")
        
        with pytest.raises(MicrosoftOAuthError, match="Network error"):
            provider.refresh_token(valid_token_info)
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_refresh_token_keeps_old_refresh_token(self, mock_app_class, microsoft_provider, valid_token_info):
        """Test that old refresh token is kept if new one not provided."""
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []
        mock_app.acquire_token_silent.return_value = None  # Silent acquisition fails
        mock_result = {
            'access_token': 'new_access_token',
            # No new refresh_token
            'expires_on': int((datetime.now() + timedelta(hours=1)).timestamp()),
        }
        mock_app.acquire_token_by_refresh_token.return_value = mock_result
        mock_app_class.return_value = mock_app
        microsoft_provider.app = mock_app
        
        refreshed = microsoft_provider.refresh_token(valid_token_info)
        
        # Should keep old refresh token
        assert refreshed['refresh_token'] == valid_token_info['refresh_token']


class TestOAuthProviderInterface:
    """Test that MicrosoftOAuthProvider implements OAuthProvider interface."""
    
    def test_implements_oauth_provider(self, microsoft_provider):
        """Test that MicrosoftOAuthProvider is an instance of OAuthProvider."""
        from src.auth.interfaces import OAuthProvider
        assert isinstance(microsoft_provider, OAuthProvider)
    
    def test_has_required_methods(self, microsoft_provider):
        """Test that all required OAuthProvider methods are implemented."""
        assert hasattr(microsoft_provider, 'get_auth_url')
        assert hasattr(microsoft_provider, 'handle_callback')
        assert hasattr(microsoft_provider, 'refresh_token')
        assert hasattr(microsoft_provider, 'validate_token')
    
    def test_validate_token_method(self, microsoft_provider):
        """Test that validate_token method works correctly."""
        valid_token: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() + timedelta(hours=1),
            'refresh_token': 'refresh',
        }
        assert microsoft_provider.validate_token(valid_token) is True
        
        expired_token: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() - timedelta(hours=1),
            'refresh_token': 'refresh',
        }
        assert microsoft_provider.validate_token(expired_token) is False


class TestErrorHandling:
    """Test error handling and exception types."""
    
    def test_microsoft_oauth_error_inheritance(self):
        """Test that MicrosoftOAuthError inherits from OAuthError."""
        assert issubclass(MicrosoftOAuthError, OAuthError)
        assert issubclass(MicrosoftOAuthError, Exception)
    
    def test_error_messages_are_informative(self, monkeypatch):
        """Test that error messages provide helpful information."""
        monkeypatch.delenv('MS_CLIENT_ID', raising=False)
        
        with pytest.raises(MicrosoftOAuthError) as exc_info:
            MicrosoftOAuthProvider()
        
        error_msg = str(exc_info.value)
        assert 'MS_CLIENT_ID' in error_msg
        assert 'environment variable' in error_msg or '.env' in error_msg


class TestIntegration:
    """Integration tests for complete OAuth flow."""
    
    @patch('src.auth.providers.microsoft.msal.ConfidentialClientApplication')
    def test_complete_oauth_flow(self, mock_app_class, microsoft_provider):
        """Test complete OAuth flow from auth URL to token exchange."""
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        
        # Step 1: Generate authorization URL
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state=flow_state',
            'state': 'flow_state',
        }
        mock_app.initiate_auth_code_flow.return_value = mock_flow
        microsoft_provider.app = mock_app
        
        state = 'test_state_123'
        auth_url = microsoft_provider.get_auth_url(state)
        assert 'login.microsoftonline.com' in auth_url
        
        # Step 2: Mock token exchange
        mock_result = {
            'access_token': 'access_token_123',
            'refresh_token': 'refresh_token_456',
            'expires_on': int((datetime.now() + timedelta(hours=1)).timestamp()),
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = mock_result
        
        # Step 3: Handle callback
        code = 'auth_code_789'
        token_info = microsoft_provider.handle_callback(code, state)
        
        assert token_info['access_token'] == 'access_token_123'
        assert token_info['refresh_token'] == 'refresh_token_456'
        assert token_info['expires_at'] is not None
