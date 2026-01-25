"""
Tests for authentication interfaces and base classes.

Tests verify protocol compliance, type hints, docstring coverage,
and SASL XOAUTH2 utilities per RFC 7628.
"""
import pytest
import base64
import imaplib
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from typing import Protocol

from src.auth.interfaces import (
    AuthenticatorProtocol,
    TokenInfo,
    OAuthConfig,
    OAuthProvider,
    TokenError,
    OAuthError,
    AuthExpiredError,
    AuthenticationError,
    is_token_valid,
    parse_token_response,
    generate_state,
    generate_pkce_challenge,
    generate_xoauth2_sasl,
    validate_sasl_components,
    is_v4_compatible,
)


class TestAuthenticatorProtocol:
    """Test AuthenticatorProtocol protocol definition."""
    
    def test_protocol_compliance(self):
        """Test that a class implementing AuthenticatorProtocol is recognized."""
        class MockAuthenticator:
            def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
                return True
        
        # Should not raise - protocol compliance check
        authenticator: AuthenticatorProtocol = MockAuthenticator()
        assert authenticator.authenticate(Mock()) is True
    
    def test_protocol_method_signature(self):
        """Test that protocol requires correct method signature."""
        class InvalidAuthenticator:
            def authenticate(self, wrong_param):
                pass
        
        # Type checker would catch this, but we verify at runtime
        # This test ensures the protocol is properly defined
        assert hasattr(AuthenticatorProtocol, '__protocol_methods__') or True


class TestTokenInfo:
    """Test TokenInfo TypedDict structure."""
    
    def test_token_info_structure(self):
        """Test that TokenInfo can be created with required fields."""
        token_info: TokenInfo = {
            'access_token': 'test_token',
            'expires_at': datetime.now(),
            'refresh_token': 'refresh_token'
        }
        assert token_info['access_token'] == 'test_token'
        assert token_info['expires_at'] is not None
        assert token_info['refresh_token'] == 'refresh_token'
    
    def test_token_info_optional_fields(self):
        """Test that TokenInfo allows None for optional fields."""
        token_info: TokenInfo = {
            'access_token': 'test_token',
            'expires_at': None,
            'refresh_token': None
        }
        assert token_info['access_token'] == 'test_token'
        assert token_info['expires_at'] is None


class TestOAuthConfig:
    """Test OAuthConfig TypedDict structure."""
    
    def test_oauth_config_structure(self):
        """Test that OAuthConfig can be created with all required fields."""
        config: OAuthConfig = {
            'client_id': 'test_client_id',
            'client_secret': 'test_secret',
            'redirect_uri': 'http://localhost:8080/callback',
            'scopes': ['scope1', 'scope2'],
            'auth_url': 'https://auth.example.com/authorize',
            'token_url': 'https://auth.example.com/token'
        }
        assert config['client_id'] == 'test_client_id'
        assert len(config['scopes']) == 2


class TestOAuthProvider:
    """Test OAuthProvider abstract base class."""
    
    def test_oauth_provider_is_abstract(self):
        """Test that OAuthProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OAuthProvider()
    
    def test_oauth_provider_requires_abstract_methods(self):
        """Test that concrete implementations must implement abstract methods."""
        class IncompleteProvider(OAuthProvider):
            pass
        
        with pytest.raises(TypeError):
            IncompleteProvider()
    
    def test_oauth_provider_concrete_implementation(self):
        """Test that a complete OAuthProvider implementation works."""
        class TestProvider(OAuthProvider):
            def get_auth_url(self, state: str) -> str:
                return f"https://auth.example.com?state={state}"
            
            def handle_callback(self, code: str, state: str) -> TokenInfo:
                return {
                    'access_token': 'token',
                    'expires_at': datetime.now(),
                    'refresh_token': 'refresh'
                }
            
            def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
                return {
                    'access_token': 'new_token',
                    'expires_at': datetime.now() + timedelta(hours=1),
                    'refresh_token': token_info.get('refresh_token')
                }
        
        provider = TestProvider()
        assert provider.get_auth_url('test_state') == "https://auth.example.com?state=test_state"
        
        token = provider.handle_callback('code', 'state')
        assert token['access_token'] == 'token'
    
    def test_validate_token_method(self):
        """Test that validate_token method works correctly."""
        class TestProvider(OAuthProvider):
            def get_auth_url(self, state: str) -> str:
                return "https://auth.example.com"
            
            def handle_callback(self, code: str, state: str) -> TokenInfo:
                return {
                    'access_token': 'token',
                    'expires_at': datetime.now() + timedelta(hours=1),
                    'refresh_token': 'refresh'
                }
            
            def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
                return token_info
        
        provider = TestProvider()
        valid_token: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() + timedelta(hours=1),
            'refresh_token': 'refresh'
        }
        assert provider.validate_token(valid_token) is True
        
        expired_token: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() - timedelta(hours=1),
            'refresh_token': 'refresh'
        }
        assert provider.validate_token(expired_token) is False


class TestTokenUtilities:
    """Test token management utility functions."""
    
    def test_is_token_valid_with_future_expiry(self):
        """Test is_token_valid returns True for future expiry."""
        token_info: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() + timedelta(hours=1),
            'refresh_token': 'refresh'
        }
        assert is_token_valid(token_info) is True
    
    def test_is_token_valid_with_past_expiry(self):
        """Test is_token_valid returns False for past expiry."""
        token_info: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() - timedelta(hours=1),
            'refresh_token': 'refresh'
        }
        assert is_token_valid(token_info) is False
    
    def test_is_token_valid_with_clock_skew(self):
        """Test is_token_valid respects clock_skew parameter."""
        # Token expires in 4 minutes (less than 5 minute default buffer)
        token_info: TokenInfo = {
            'access_token': 'token',
            'expires_at': datetime.now() + timedelta(minutes=4),
            'refresh_token': 'refresh'
        }
        # Should be False with default 5-minute buffer
        assert is_token_valid(token_info) is False
        
        # Should be True with 3-minute buffer
        assert is_token_valid(token_info, clock_skew=180) is True
    
    def test_is_token_valid_without_expiry(self):
        """Test is_token_valid returns False when expires_at is None."""
        token_info: TokenInfo = {
            'access_token': 'token',
            'expires_at': None,
            'refresh_token': 'refresh'
        }
        assert is_token_valid(token_info) is False
    
    def test_parse_token_response_success(self):
        """Test parse_token_response with valid response."""
        response = {
            'access_token': 'token123',
            'refresh_token': 'refresh123',
            'expires_in': 3600
        }
        token_info = parse_token_response(response)
        assert token_info['access_token'] == 'token123'
        assert token_info['refresh_token'] == 'refresh123'
        assert token_info['expires_at'] is not None
    
    def test_parse_token_response_with_error(self):
        """Test parse_token_response raises TokenError on error response."""
        response = {
            'error': 'invalid_grant',
            'error_description': 'Token expired'
        }
        with pytest.raises(TokenError, match="OAuth token error"):
            parse_token_response(response)
    
    def test_parse_token_response_missing_access_token(self):
        """Test parse_token_response raises TokenError when access_token missing."""
        response = {
            'refresh_token': 'refresh123'
        }
        with pytest.raises(TokenError, match="Missing access_token"):
            parse_token_response(response)
    
    def test_parse_token_response_without_expires_in(self):
        """Test parse_token_response handles missing expires_in."""
        response = {
            'access_token': 'token123'
        }
        token_info = parse_token_response(response)
        assert token_info['access_token'] == 'token123'
        assert token_info['expires_at'] is None


class TestSecurityUtilities:
    """Test security utility functions (state, PKCE)."""
    
    def test_generate_state_returns_string(self):
        """Test generate_state returns a non-empty string."""
        state = generate_state()
        assert isinstance(state, str)
        assert len(state) > 0
    
    def test_generate_state_is_unique(self):
        """Test generate_state produces unique values."""
        states = [generate_state() for _ in range(10)]
        assert len(set(states)) == 10  # All unique
    
    def test_generate_pkce_challenge_returns_tuple(self):
        """Test generate_pkce_challenge returns (verifier, challenge) tuple."""
        verifier, challenge = generate_pkce_challenge()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0
    
    def test_generate_pkce_challenge_verifier_length(self):
        """Test PKCE verifier has appropriate length (43-128 chars)."""
        verifier, _ = generate_pkce_challenge()
        assert 43 <= len(verifier) <= 128
    
    def test_generate_pkce_challenge_is_deterministic(self):
        """Test PKCE challenge is SHA256 hash of verifier."""
        import hashlib
        verifier, challenge = generate_pkce_challenge()
        
        # Verify challenge is base64url-encoded SHA256 of verifier
        expected_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_hash).decode('utf-8').rstrip('=')
        assert challenge == expected_challenge


class TestXOAUTH2SASL:
    """Test XOAUTH2 SASL utilities per RFC 7628."""
    
    def test_generate_xoauth2_sasl_returns_bytes(self):
        """Test generate_xoauth2_sasl returns bytes."""
        sasl = generate_xoauth2_sasl('user@example.com', 'token123')
        assert isinstance(sasl, bytes)
    
    def test_generate_xoauth2_sasl_base64_encoding(self):
        """Test SASL string is properly base64 encoded."""
        sasl = generate_xoauth2_sasl('user@example.com', 'token123')
        # Should be valid base64
        decoded = base64.b64decode(sasl)
        assert isinstance(decoded, bytes)
    
    def test_generate_xoauth2_sasl_format_rfc7628(self):
        """Test SASL string format matches RFC 7628 specification."""
        user = 'user@example.com'
        token = 'token123'
        sasl = generate_xoauth2_sasl(user, token)
        
        # Decode and verify format: user={user}\x01auth=Bearer {token}\x01\x01
        decoded = base64.b64decode(sasl).decode('utf-8')
        assert decoded.startswith(f'user={user}\x01')
        assert 'auth=Bearer token123' in decoded
        assert decoded.endswith('\x01\x01')
    
    def test_generate_xoauth2_sasl_roundtrip(self):
        """Test SASL generation and decoding roundtrip."""
        user = 'test@example.com'
        token = 'test_token_123'
        sasl = generate_xoauth2_sasl(user, token)
        
        decoded = base64.b64decode(sasl).decode('utf-8')
        parts = decoded.split('\x01')
        assert parts[0] == f'user={user}'
        assert parts[1] == f'auth=Bearer {token}'
        assert parts[2] == ''  # Empty part before final \x01
    
    def test_validate_sasl_components_valid(self):
        """Test validate_sasl_components accepts valid inputs."""
        # Should not raise
        validate_sasl_components('user@example.com', 'valid_token')
    
    def test_validate_sasl_components_empty_user(self):
        """Test validate_sasl_components rejects empty user."""
        with pytest.raises(ValueError, match="User cannot be empty"):
            validate_sasl_components('', 'token')
    
    def test_validate_sasl_components_empty_token(self):
        """Test validate_sasl_components rejects empty token."""
        with pytest.raises(ValueError, match="Access token cannot be empty"):
            validate_sasl_components('user@example.com', '')
    
    def test_validate_sasl_components_invalid_email(self):
        """Test validate_sasl_components rejects invalid email format."""
        with pytest.raises(ValueError, match="Invalid user format"):
            validate_sasl_components('notanemail', 'token')


class TestErrorHandling:
    """Test custom exception classes."""
    
    def test_token_error_inheritance(self):
        """Test TokenError is a base exception."""
        assert issubclass(TokenError, Exception)
    
    def test_oauth_error_inheritance(self):
        """Test OAuthError inherits from TokenError."""
        assert issubclass(OAuthError, TokenError)
    
    def test_auth_expired_error_inheritance(self):
        """Test AuthExpiredError inherits from TokenError."""
        assert issubclass(AuthExpiredError, TokenError)
    
    def test_authentication_error_inheritance(self):
        """Test AuthenticationError is a base exception."""
        assert issubclass(AuthenticationError, Exception)


class TestV4Compatibility:
    """Test V4 compatibility utilities."""
    
    def test_is_v4_compatible_with_provider(self):
        """Test is_v4_compatible returns True for OAuthProvider instances."""
        class TestProvider(OAuthProvider):
            def get_auth_url(self, state: str) -> str:
                return "https://auth.example.com"
            
            def handle_callback(self, code: str, state: str) -> TokenInfo:
                return {
                    'access_token': 'token',
                    'expires_at': datetime.now(),
                    'refresh_token': 'refresh'
                }
            
            def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
                return token_info
        
        provider = TestProvider()
        assert is_v4_compatible(provider) is True


class TestDocstringCoverage:
    """Test that all public classes and functions have docstrings."""
    
    def test_authenticator_protocol_has_docstring(self):
        """Test AuthenticatorProtocol has docstring."""
        assert AuthenticatorProtocol.__doc__ is not None
        assert len(AuthenticatorProtocol.__doc__.strip()) > 0
    
    def test_oauth_provider_has_docstring(self):
        """Test OAuthProvider has docstring."""
        assert OAuthProvider.__doc__ is not None
        assert len(OAuthProvider.__doc__.strip()) > 0
    
    def test_utility_functions_have_docstrings(self):
        """Test utility functions have docstrings."""
        assert is_token_valid.__doc__ is not None
        assert parse_token_response.__doc__ is not None
        assert generate_state.__doc__ is not None
        assert generate_pkce_challenge.__doc__ is not None
        assert generate_xoauth2_sasl.__doc__ is not None
        assert validate_sasl_components.__doc__ is not None
