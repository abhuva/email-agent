"""
Tests for Google OAuth provider implementation.

Tests verify authorization URL generation, token exchange, refresh flows,
error handling, and integration with google-auth-oauthlib library.
"""
import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.auth.providers.google import GoogleOAuthProvider, GoogleOAuthError
from src.auth.interfaces import TokenInfo, OAuthError, AuthExpiredError


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for Google OAuth."""
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id_123')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret_456')


@pytest.fixture
def google_provider(mock_env_vars):
    """Create a GoogleOAuthProvider instance with mocked credentials."""
    return GoogleOAuthProvider()


@pytest.fixture
def valid_token_info():
    """Sample valid token information."""
    return {
        'access_token': 'test_access_token_123',
        'refresh_token': 'test_refresh_token_456',
        'expires_at': datetime.now() + timedelta(hours=1),
    }


class TestGoogleOAuthProviderInitialization:
    """Test GoogleOAuthProvider initialization."""
    
    def test_init_loads_env_vars(self, mock_env_vars):
        """Test that provider loads credentials from environment variables."""
        provider = GoogleOAuthProvider()
        assert provider.client_id == 'test_client_id_123'
        assert provider.client_secret == 'test_client_secret_456'
    
    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials."""
        provider = GoogleOAuthProvider(
            client_id='explicit_id',
            client_secret='explicit_secret',
        )
        assert provider.client_id == 'explicit_id'
        assert provider.client_secret == 'explicit_secret'
    
    def test_init_missing_client_id(self, monkeypatch):
        """Test that missing GOOGLE_CLIENT_ID raises error."""
        monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
        monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'secret')
        
        with pytest.raises(GoogleOAuthError, match="GOOGLE_CLIENT_ID"):
            GoogleOAuthProvider()
    
    def test_init_missing_client_secret(self, monkeypatch):
        """Test that missing GOOGLE_CLIENT_SECRET raises error."""
        monkeypatch.setenv('GOOGLE_CLIENT_ID', 'id')
        monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)
        
        with pytest.raises(GoogleOAuthError, match="GOOGLE_CLIENT_SECRET"):
            GoogleOAuthProvider()
    
    def test_init_default_scopes(self, google_provider):
        """Test that default scopes include Gmail IMAP scope."""
        assert 'https://mail.google.com/' in google_provider.scopes
        assert 'openid' in google_provider.scopes
        assert 'email' in google_provider.scopes
        assert 'profile' in google_provider.scopes
    
    def test_init_custom_scopes(self, mock_env_vars):
        """Test initialization with custom scopes."""
        custom_scopes = ['https://mail.google.com/', 'custom_scope']
        provider = GoogleOAuthProvider(scopes=custom_scopes)
        assert provider.scopes == custom_scopes
    
    def test_init_default_redirect_uri(self, google_provider):
        """Test that default redirect URI is set correctly."""
        assert google_provider.redirect_uri == 'http://localhost:8080/callback'
    
    def test_init_custom_redirect_uri(self, mock_env_vars):
        """Test initialization with custom redirect URI."""
        provider = GoogleOAuthProvider(redirect_uri='http://localhost:9000/callback')
        assert provider.redirect_uri == 'http://localhost:9000/callback'


class TestGetAuthUrl:
    """Test authorization URL generation."""
    
    @patch('src.auth.providers.google.Flow')
    def test_get_auth_url_success(self, mock_flow_class, google_provider):
        """Test successful authorization URL generation."""
        # Mock Flow object
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            'https://accounts.google.com/o/oauth2/v2/auth?state=test_state',
            'test_state'
        )
        mock_flow_class.from_client_config.return_value = mock_flow
        
        state = 'test_state_123'
        auth_url = google_provider.get_auth_url(state)
        
        assert 'accounts.google.com' in auth_url
        assert google_provider._state == state
        mock_flow.authorization_url.assert_called_once()
        # Verify offline access is requested
        call_kwargs = mock_flow.authorization_url.call_args[1]
        assert call_kwargs['access_type'] == 'offline'
        assert call_kwargs['prompt'] == 'consent'
    
    @patch('src.auth.providers.google.Flow')
    def test_get_auth_url_creates_flow(self, mock_flow_class, google_provider):
        """Test that Flow is created with correct configuration."""
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ('https://auth.url', 'state')
        mock_flow_class.from_client_config.return_value = mock_flow
        
        google_provider.get_auth_url('state')
        
        # Verify Flow.from_client_config was called
        mock_flow_class.from_client_config.assert_called_once()
        call_kwargs = mock_flow_class.from_client_config.call_args
        
        # Check client config structure
        client_config = call_kwargs[0][0]
        assert 'web' in client_config
        assert client_config['web']['client_id'] == 'test_client_id_123'
        assert client_config['web']['client_secret'] == 'test_client_secret_456'
        
        # Check scopes and redirect_uri
        assert call_kwargs[1]['scopes'] == google_provider.scopes
        assert call_kwargs[1]['redirect_uri'] == google_provider.redirect_uri
    
    @patch('src.auth.providers.google.Flow')
    def test_get_auth_url_error_handling(self, mock_flow_class, google_provider):
        """Test error handling in authorization URL generation."""
        mock_flow_class.from_client_config.side_effect = Exception("Flow creation failed")
        
        with pytest.raises(GoogleOAuthError, match="Failed to generate"):
            google_provider.get_auth_url('state')


class TestHandleCallback:
    """Test authorization callback handling and token exchange."""
    
    @patch('src.auth.providers.google.Flow')
    def test_handle_callback_success(self, mock_flow_class, google_provider, valid_token_info):
        """Test successful callback handling and token exchange."""
        # Mock Flow and credentials
        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.token = valid_token_info['access_token']
        mock_credentials.refresh_token = valid_token_info['refresh_token']
        mock_credentials.expiry = valid_token_info['expires_at']
        mock_flow.credentials = mock_credentials
        mock_flow_class.from_client_config.return_value = mock_flow
        
        # Set state for validation
        state = 'test_state_123'
        google_provider._state = state
        
        code = 'authorization_code_123'
        token_info = google_provider.handle_callback(code, state)
        
        assert token_info['access_token'] == valid_token_info['access_token']
        assert token_info['refresh_token'] == valid_token_info['refresh_token']
        assert token_info['expires_at'] == valid_token_info['expires_at']
        
        # Verify fetch_token was called with code
        mock_flow.fetch_token.assert_called_once_with(code=code)
    
    @patch('src.auth.providers.google.Flow')
    def test_handle_callback_state_mismatch(self, mock_flow_class, google_provider):
        """Test that state mismatch raises ValueError."""
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        
        google_provider._state = 'stored_state'
        
        with pytest.raises(ValueError, match="State parameter mismatch"):
            google_provider.handle_callback('code', 'different_state')
    
    @patch('src.auth.providers.google.Flow')
    def test_handle_callback_no_state(self, mock_flow_class, google_provider):
        """Test that missing stored state raises ValueError."""
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        
        google_provider._state = None
        
        with pytest.raises(ValueError, match="State parameter mismatch"):
            google_provider.handle_callback('code', 'any_state')
    
    @patch('src.auth.providers.google.Flow')
    def test_handle_callback_missing_access_token(self, mock_flow_class, google_provider):
        """Test error when access token is missing in response."""
        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.token = None  # Missing token
        mock_credentials.refresh_token = 'refresh'
        mock_credentials.expiry = datetime.now()
        mock_flow.credentials = mock_credentials
        mock_flow_class.from_client_config.return_value = mock_flow
        
        google_provider._state = 'state'
        
        with pytest.raises(GoogleOAuthError, match="Missing access_token"):
            google_provider.handle_callback('code', 'state')
    
    @patch('src.auth.providers.google.Flow')
    def test_handle_callback_fetch_token_error(self, mock_flow_class, google_provider):
        """Test error handling when fetch_token fails."""
        mock_flow = MagicMock()
        mock_flow.fetch_token.side_effect = Exception("Token exchange failed")
        mock_flow_class.from_client_config.return_value = mock_flow
        
        google_provider._state = 'state'
        
        with pytest.raises(GoogleOAuthError, match="Failed to exchange"):
            google_provider.handle_callback('code', 'state')
    
    def test_exchange_code_for_tokens_alias(self, google_provider):
        """Test that exchange_code_for_tokens is an alias for handle_callback."""
        with patch.object(google_provider, 'handle_callback') as mock_handle:
            mock_handle.return_value = {'access_token': 'token', 'expires_at': None, 'refresh_token': None}
            google_provider._state = 'state'
            
            google_provider.exchange_code_for_tokens('code', 'state')
            mock_handle.assert_called_once_with('code', 'state')


class TestRefreshToken:
    """Test token refresh functionality."""
    
    @patch('src.auth.providers.google.Credentials')
    @patch('src.auth.providers.google.Request')
    def test_refresh_token_success(self, mock_request_class, mock_credentials_class, google_provider, valid_token_info):
        """Test successful token refresh."""
        # Mock credentials refresh
        mock_credentials = MagicMock()
        mock_credentials.token = 'new_access_token'
        mock_credentials.refresh_token = 'new_refresh_token'
        mock_credentials.expiry = datetime.now() + timedelta(hours=1)
        mock_credentials.refresh.return_value = None  # refresh() doesn't return anything
        
        mock_credentials_class.return_value = mock_credentials
        
        refreshed = google_provider.refresh_token(valid_token_info)
        
        assert refreshed['access_token'] == 'new_access_token'
        assert refreshed['refresh_token'] == 'new_refresh_token'
        assert refreshed['expires_at'] is not None
        
        # Verify Credentials was created with correct parameters
        mock_credentials_class.assert_called_once()
        call_kwargs = mock_credentials_class.call_args[1]
        assert call_kwargs['token'] == valid_token_info['access_token']
        assert call_kwargs['refresh_token'] == valid_token_info['refresh_token']
        assert call_kwargs['token_uri'] == google_provider.TOKEN_ENDPOINT
        assert call_kwargs['client_id'] == google_provider.client_id
        assert call_kwargs['client_secret'] == google_provider.client_secret
        
        # Verify refresh was called
        mock_credentials.refresh.assert_called_once()
        assert isinstance(mock_credentials.refresh.call_args[0][0], type(mock_request_class()))
    
    @patch('src.auth.providers.google.Credentials')
    @patch('src.auth.providers.google.Request')
    def test_refresh_token_keeps_old_refresh_token(self, mock_request_class, mock_credentials_class, google_provider, valid_token_info):
        """Test that old refresh token is kept if new one not provided."""
        mock_credentials = MagicMock()
        mock_credentials.token = 'new_access_token'
        mock_credentials.refresh_token = None  # No new refresh token
        mock_credentials.expiry = datetime.now() + timedelta(hours=1)
        mock_credentials.refresh.return_value = None
        
        mock_credentials_class.return_value = mock_credentials
        
        refreshed = google_provider.refresh_token(valid_token_info)
        
        # Should keep old refresh token
        assert refreshed['refresh_token'] == valid_token_info['refresh_token']
    
    def test_refresh_token_missing_refresh_token(self, google_provider):
        """Test error when refresh token is missing."""
        token_info: TokenInfo = {
            'access_token': 'token',
            'expires_at': None,
            'refresh_token': None,  # Missing
        }
        
        with pytest.raises(AuthExpiredError, match="No refresh token"):
            google_provider.refresh_token(token_info)
    
    @patch('src.auth.providers.google.Credentials')
    @patch('src.auth.providers.google.Request')
    def test_refresh_token_invalid_grant(self, mock_request_class, mock_credentials_class, google_provider, valid_token_info):
        """Test error handling for invalid_grant (expired refresh token)."""
        mock_credentials = MagicMock()
        mock_credentials.refresh.side_effect = Exception("invalid_grant: Token expired")
        mock_credentials_class.return_value = mock_credentials
        
        with pytest.raises(AuthExpiredError, match="Refresh token is invalid"):
            google_provider.refresh_token(valid_token_info)
    
    @patch('src.auth.providers.google.Credentials')
    @patch('src.auth.providers.google.Request')
    def test_refresh_token_network_error(self, mock_request_class, mock_credentials_class, google_provider, valid_token_info):
        """Test error handling for network errors."""
        mock_credentials = MagicMock()
        mock_credentials.refresh.side_effect = Exception("Network error")
        mock_credentials_class.return_value = mock_credentials
        
        with pytest.raises(GoogleOAuthError, match="Failed to refresh"):
            google_provider.refresh_token(valid_token_info)


class TestOAuthProviderInterface:
    """Test that GoogleOAuthProvider implements OAuthProvider interface."""
    
    def test_implements_oauth_provider(self, google_provider):
        """Test that GoogleOAuthProvider is an instance of OAuthProvider."""
        from src.auth.interfaces import OAuthProvider
        assert isinstance(google_provider, OAuthProvider)
    
    def test_has_required_methods(self, google_provider):
        """Test that all required OAuthProvider methods are implemented."""
        assert hasattr(google_provider, 'get_auth_url')
        assert hasattr(google_provider, 'handle_callback')
        assert hasattr(google_provider, 'refresh_token')
        assert hasattr(google_provider, 'validate_token')
    
    def test_validate_token_method(self, google_provider):
        """Test that validate_token method works correctly."""
        valid_token: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() + timedelta(hours=1),
            'refresh_token': 'refresh',
        }
        assert google_provider.validate_token(valid_token) is True
        
        expired_token: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() - timedelta(hours=1),
            'refresh_token': 'refresh',
        }
        assert google_provider.validate_token(expired_token) is False


class TestErrorHandling:
    """Test error handling and exception types."""
    
    def test_google_oauth_error_inheritance(self):
        """Test that GoogleOAuthError inherits from OAuthError."""
        assert issubclass(GoogleOAuthError, OAuthError)
        assert issubclass(GoogleOAuthError, Exception)
    
    def test_error_messages_are_informative(self, monkeypatch):
        """Test that error messages provide helpful information."""
        monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
        
        with pytest.raises(GoogleOAuthError) as exc_info:
            GoogleOAuthProvider()
        
        error_msg = str(exc_info.value)
        assert 'GOOGLE_CLIENT_ID' in error_msg
        assert 'environment variable' in error_msg or '.env' in error_msg


class TestIntegration:
    """Integration tests for complete OAuth flow."""
    
    @patch('src.auth.providers.google.Flow')
    def test_complete_oauth_flow(self, mock_flow_class, google_provider):
        """Test complete OAuth flow from auth URL to token exchange."""
        # Mock Flow for authorization
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            'https://accounts.google.com/o/oauth2/v2/auth?state=flow_state',
            'flow_state'
        )
        mock_flow_class.from_client_config.return_value = mock_flow
        
        # Step 1: Generate authorization URL
        state = 'test_state_123'
        auth_url = google_provider.get_auth_url(state)
        assert 'accounts.google.com' in auth_url
        
        # Step 2: Mock token exchange
        mock_credentials = MagicMock()
        mock_credentials.token = 'access_token_123'
        mock_credentials.refresh_token = 'refresh_token_456'
        mock_credentials.expiry = datetime.now() + timedelta(hours=1)
        mock_flow.credentials = mock_credentials
        
        # Step 3: Handle callback
        code = 'auth_code_789'
        token_info = google_provider.handle_callback(code, state)
        
        assert token_info['access_token'] == 'access_token_123'
        assert token_info['refresh_token'] == 'refresh_token_456'
        assert token_info['expires_at'] is not None
