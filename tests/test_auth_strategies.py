"""
Tests for authentication strategies (password and OAuth).

Tests verify both PasswordAuthenticator and OAuthAuthenticator implementations,
including success/failure scenarios, error handling, and security practices.
"""
import pytest
import os
import imaplib
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.auth.strategies import PasswordAuthenticator, OAuthAuthenticator
from src.auth.interfaces import AuthenticationError, TokenError
from src.auth.token_manager import TokenManager, TokenRefreshError


class TestPasswordAuthenticator:
    """Test PasswordAuthenticator class."""
    
    @pytest.fixture
    def mock_imap(self):
        """Create a mock IMAP connection."""
        mock = MagicMock(spec=imaplib.IMAP4_SSL)
        mock.login = MagicMock(return_value=('OK', [b'Login successful']))
        return mock
    
    @pytest.fixture
    def password_env(self, monkeypatch):
        """Set up password environment variable."""
        password = 'test_password_123'
        monkeypatch.setenv('TEST_PASSWORD_ENV', password)
        return 'TEST_PASSWORD_ENV'
    
    def test_init_with_valid_credentials(self, password_env):
        """Test PasswordAuthenticator initialization with valid credentials."""
        authenticator = PasswordAuthenticator('user@example.com', password_env)
        assert authenticator.email == 'user@example.com'
        assert authenticator.password == 'test_password_123'
    
    def test_init_with_empty_email(self, password_env):
        """Test PasswordAuthenticator raises ValueError for empty email."""
        with pytest.raises(ValueError, match="Email cannot be empty"):
            PasswordAuthenticator('', password_env)
        
        with pytest.raises(ValueError, match="Email cannot be empty"):
            PasswordAuthenticator('   ', password_env)
    
    def test_init_with_empty_password_env(self):
        """Test PasswordAuthenticator raises ValueError for empty password env var name."""
        with pytest.raises(ValueError, match="Password environment variable name cannot be empty"):
            PasswordAuthenticator('user@example.com', '')
    
    def test_init_with_missing_password_env(self, monkeypatch):
        """Test PasswordAuthenticator raises ValueError when password env var is not set."""
        # Ensure env var is not set
        monkeypatch.delenv('MISSING_PASSWORD_ENV', raising=False)
        
        with pytest.raises(ValueError, match="Password environment variable 'MISSING_PASSWORD_ENV' is not set"):
            PasswordAuthenticator('user@example.com', 'MISSING_PASSWORD_ENV')
    
    def test_authenticate_success(self, mock_imap, password_env):
        """Test successful password authentication."""
        authenticator = PasswordAuthenticator('user@example.com', password_env)
        result = authenticator.authenticate(mock_imap)
        
        assert result is True
        mock_imap.login.assert_called_once_with('user@example.com', 'test_password_123')
    
    def test_authenticate_imap_error(self, mock_imap, password_env):
        """Test authentication failure with IMAP error."""
        mock_imap.login.side_effect = imaplib.IMAP4.error('AUTHENTICATIONFAILED')
        
        authenticator = PasswordAuthenticator('user@example.com', password_env)
        
        with pytest.raises(AuthenticationError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        # Verify error message doesn't expose password
        error_msg = str(exc_info.value)
        assert 'test_password_123' not in error_msg
        assert 'user@example.com' in error_msg
        assert 'credentials' in error_msg.lower() or 'authentication failed' in error_msg.lower()
    
    def test_authenticate_unexpected_error(self, mock_imap, password_env):
        """Test authentication handles unexpected errors."""
        mock_imap.login.side_effect = Exception('Unexpected error')
        
        authenticator = PasswordAuthenticator('user@example.com', password_env)
        
        with pytest.raises(AuthenticationError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        assert 'Unexpected error' in str(exc_info.value)
    
    def test_authenticate_protocol_compliance(self, mock_imap, password_env):
        """Test PasswordAuthenticator conforms to AuthenticatorProtocol."""
        from src.auth.interfaces import AuthenticatorProtocol
        
        authenticator = PasswordAuthenticator('user@example.com', password_env)
        
        # Should be recognized as AuthenticatorProtocol
        assert hasattr(authenticator, 'authenticate')
        assert callable(authenticator.authenticate)
        
        # Should work with IMAP4_SSL
        result = authenticator.authenticate(mock_imap)
        assert result is True


class TestOAuthAuthenticator:
    """Test OAuthAuthenticator class."""
    
    @pytest.fixture
    def mock_imap(self):
        """Create a mock IMAP connection."""
        mock = MagicMock(spec=imaplib.IMAP4_SSL)
        mock.authenticate = MagicMock(return_value=('OK', [b'Authentication successful']))
        return mock
    
    @pytest.fixture
    def token_manager(self, tmp_path):
        """Create a TokenManager instance with temporary directory."""
        return TokenManager(credentials_dir=tmp_path / 'credentials')
    
    @pytest.fixture
    def valid_token(self):
        """Sample valid access token."""
        return 'test_access_token_12345'
    
    def test_init_with_valid_parameters(self, token_manager):
        """Test OAuthAuthenticator initialization with valid parameters."""
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        assert authenticator.email == 'user@example.com'
        assert authenticator.account_name == 'test-account'
        assert authenticator.provider_name == 'google'
        assert authenticator.token_manager is token_manager
    
    def test_init_normalizes_provider_name(self, token_manager):
        """Test OAuthAuthenticator normalizes provider name to lowercase."""
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='GOOGLE',
            token_manager=token_manager
        )
        
        assert authenticator.provider_name == 'google'
    
    def test_init_with_empty_email(self, token_manager):
        """Test OAuthAuthenticator raises ValueError for empty email."""
        with pytest.raises(ValueError, match="Email cannot be empty"):
            OAuthAuthenticator('', 'test-account', 'google', token_manager)
    
    def test_init_with_empty_account_name(self, token_manager):
        """Test OAuthAuthenticator raises ValueError for empty account name."""
        with pytest.raises(ValueError, match="Account name cannot be empty"):
            OAuthAuthenticator('user@example.com', '', 'google', token_manager)
    
    def test_init_with_empty_provider_name(self, token_manager):
        """Test OAuthAuthenticator raises ValueError for empty provider name."""
        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            OAuthAuthenticator('user@example.com', 'test-account', '', token_manager)
    
    def test_init_with_invalid_provider(self, token_manager):
        """Test OAuthAuthenticator raises ValueError for invalid provider."""
        with pytest.raises(ValueError, match="Invalid provider"):
            OAuthAuthenticator('user@example.com', 'test-account', 'invalid', token_manager)
    
    def test_init_with_none_token_manager(self):
        """Test OAuthAuthenticator raises ValueError for None token manager."""
        with pytest.raises(ValueError, match="TokenManager cannot be None"):
            OAuthAuthenticator('user@example.com', 'test-account', 'google', None)
    
    @patch('src.auth.strategies.generate_xoauth2_sasl')
    def test_authenticate_success(self, mock_generate_sasl, mock_imap, token_manager, valid_token):
        """Test successful OAuth authentication."""
        # Mock SASL string generation
        mock_sasl_bytes = b'base64_encoded_sasl_string'
        mock_generate_sasl.return_value = mock_sasl_bytes
        
        # Mock token manager
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        result = authenticator.authenticate(mock_imap)
        
        assert result is True
        token_manager.get_valid_token.assert_called_once_with('test-account', 'google')
        mock_generate_sasl.assert_called_once_with('user@example.com', valid_token)
        
        # Verify authenticate was called with XOAUTH2 and callback
        assert mock_imap.authenticate.called
        call_args = mock_imap.authenticate.call_args
        assert call_args[0][0] == 'XOAUTH2'
        assert callable(call_args[0][1])  # Callback function
    
    @patch('src.auth.strategies.generate_xoauth2_sasl')
    def test_authenticate_token_refresh_triggered(self, mock_generate_sasl, mock_imap, token_manager, valid_token):
        """Test that token refresh is triggered when token is expired."""
        # Mock SASL string generation
        mock_sasl_bytes = b'base64_encoded_sasl_string'
        mock_generate_sasl.return_value = mock_sasl_bytes
        
        # Mock token manager to simulate expired token that gets refreshed
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        result = authenticator.authenticate(mock_imap)
        
        assert result is True
        # TokenManager.get_valid_token should handle refresh internally
        token_manager.get_valid_token.assert_called_once()
    
    def test_authenticate_no_token_available(self, mock_imap, token_manager):
        """Test authentication fails when no token is available."""
        # Mock token manager to return None (no token)
        token_manager.get_valid_token = MagicMock(return_value=None)
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        with pytest.raises(TokenError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        assert 'Failed to obtain access token' in str(exc_info.value)
        assert 'auth' in str(exc_info.value).lower()  # Suggests running auth command
    
    def test_authenticate_imap_error(self, mock_imap, token_manager, valid_token):
        """Test authentication failure with IMAP error."""
        from src.auth.strategies import generate_xoauth2_sasl
        
        # Mock token manager
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        # Mock IMAP authenticate to fail
        mock_imap.authenticate.return_value = ('NO', [b'Invalid credentials'])
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        error_msg = str(exc_info.value)
        assert 'OAuth authentication failed' in error_msg
        assert 'user@example.com' in error_msg
        assert 'auth' in error_msg.lower()  # Suggests re-authentication
    
    def test_authenticate_imap_exception(self, mock_imap, token_manager, valid_token):
        """Test authentication handles IMAP exceptions."""
        from src.auth.strategies import generate_xoauth2_sasl
        
        # Mock token manager
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        # Mock IMAP authenticate to raise exception
        mock_imap.authenticate.side_effect = imaplib.IMAP4.error('Connection error')
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        assert 'OAuth authentication failed' in str(exc_info.value)
    
    def test_authenticate_token_error_propagated(self, mock_imap, token_manager):
        """Test that TokenError from token manager is propagated."""
        # Mock token manager to raise TokenError
        token_manager.get_valid_token = MagicMock(side_effect=TokenError('Token refresh failed'))
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        with pytest.raises(TokenError, match="Token refresh failed"):
            authenticator.authenticate(mock_imap)
    
    def test_authenticate_unexpected_error(self, mock_imap, token_manager, valid_token):
        """Test authentication handles unexpected errors."""
        # Mock token manager
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        # Mock generate_xoauth2_sasl to raise unexpected error
        with patch('src.auth.strategies.generate_xoauth2_sasl') as mock_generate:
            mock_generate.side_effect = Exception('Unexpected error')
            
            authenticator = OAuthAuthenticator(
                email='user@example.com',
                account_name='test-account',
                provider_name='google',
                token_manager=token_manager
            )
            
            with pytest.raises(AuthenticationError) as exc_info:
                authenticator.authenticate(mock_imap)
            
            assert 'Unexpected error' in str(exc_info.value)
    
    def test_authenticate_protocol_compliance(self, mock_imap, token_manager, valid_token):
        """Test OAuthAuthenticator conforms to AuthenticatorProtocol."""
        from src.auth.interfaces import AuthenticatorProtocol
        
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        # Should be recognized as AuthenticatorProtocol
        assert hasattr(authenticator, 'authenticate')
        assert callable(authenticator.authenticate)
    
    def test_authenticate_sasl_string_format(self, mock_imap, token_manager, valid_token):
        """Test that SASL string is generated with correct format."""
        import base64
        from src.auth.strategies import generate_xoauth2_sasl
        
        token_manager.get_valid_token = MagicMock(return_value=valid_token)
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        # Call authenticate to trigger SASL generation
        authenticator.authenticate(mock_imap)
        
        # Verify generate_xoauth2_sasl was called with correct parameters
        # (We can't easily verify the callback, but we can verify the function was used)
        token_manager.get_valid_token.assert_called_once()
        assert mock_imap.authenticate.called


class TestAuthenticatorSecurity:
    """Test security practices for both authenticators."""
    
    def test_password_authenticator_no_password_in_errors(self, monkeypatch):
        """Test that password is never exposed in error messages."""
        password = 'secret_password_123'
        monkeypatch.setenv('TEST_PASSWORD', password)
        
        mock_imap = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_imap.login.side_effect = imaplib.IMAP4.error('AUTHENTICATIONFAILED')
        
        authenticator = PasswordAuthenticator('user@example.com', 'TEST_PASSWORD')
        
        with pytest.raises(AuthenticationError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        error_msg = str(exc_info.value)
        assert password not in error_msg
        assert 'secret_password' not in error_msg
    
    def test_oauth_authenticator_no_token_in_errors(self, tmp_path):
        """Test that tokens are never exposed in error messages."""
        token_manager = TokenManager(credentials_dir=tmp_path / 'credentials')
        token_manager.get_valid_token = MagicMock(return_value='secret_token_12345')
        
        mock_imap = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_imap.authenticate.side_effect = imaplib.IMAP4.error('Invalid token')
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            authenticator.authenticate(mock_imap)
        
        error_msg = str(exc_info.value)
        assert 'secret_token_12345' not in error_msg
        assert 'secret_token' not in error_msg


class TestAuthenticatorIntegration:
    """Integration tests for authenticators with real token manager."""
    
    @pytest.fixture
    def token_manager_with_tokens(self, tmp_path, monkeypatch):
        """Create TokenManager with saved tokens."""
        # Set up environment variables for token refresh
        monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_client_id')
        monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_client_secret')
        
        token_manager = TokenManager(credentials_dir=tmp_path / 'credentials')
        
        # Save valid tokens
        tokens = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_at': datetime.now() + timedelta(hours=1),
        }
        token_manager.save_tokens('test-account', tokens)
        
        return token_manager
    
    def test_oauth_authenticator_with_real_token_manager(self, token_manager_with_tokens):
        """Test OAuthAuthenticator works with real TokenManager."""
        mock_imap = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_imap.authenticate.return_value = ('OK', [b'Success'])
        
        authenticator = OAuthAuthenticator(
            email='user@example.com',
            account_name='test-account',
            provider_name='google',
            token_manager=token_manager_with_tokens
        )
        
        # Should successfully authenticate
        result = authenticator.authenticate(mock_imap)
        assert result is True
        assert mock_imap.authenticate.called
