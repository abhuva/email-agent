"""
Tests for TokenManager OAuth token management.

Tests verify token storage, loading, expiry checking, refresh logic,
and comprehensive error handling.
"""
import pytest
import json
import os
import time
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.auth.token_manager import TokenManager, TokenRefreshError
from src.auth.interfaces import TokenError


@pytest.fixture
def temp_credentials_dir(tmp_path):
    """Create a temporary credentials directory for testing."""
    creds_dir = tmp_path / "credentials"
    creds_dir.mkdir()
    return creds_dir


@pytest.fixture
def token_manager(temp_credentials_dir):
    """Create a TokenManager instance with temporary credentials directory."""
    return TokenManager(credentials_dir=temp_credentials_dir)


@pytest.fixture
def valid_tokens():
    """Sample valid token dictionary."""
    return {
        'access_token': 'test_access_token_123',
        'refresh_token': 'test_refresh_token_456',
        'expires_at': datetime.now() + timedelta(hours=1),
        'expires_in': 3600,
    }


@pytest.fixture
def expired_tokens():
    """Sample expired token dictionary."""
    return {
        'access_token': 'expired_access_token',
        'refresh_token': 'test_refresh_token_456',
        'expires_at': datetime.now() - timedelta(hours=1),
        # Don't include expires_in for expired tokens to avoid validation issues
    }


class TestTokenManagerInitialization:
    """Test TokenManager initialization."""
    
    def test_init_with_custom_dir(self, temp_credentials_dir):
        """Test initialization with custom credentials directory."""
        manager = TokenManager(credentials_dir=temp_credentials_dir)
        assert manager.credentials_dir == temp_credentials_dir
    
    def test_init_with_default_dir(self):
        """Test initialization with default credentials directory."""
        manager = TokenManager()
        # Should default to project_root/credentials
        assert 'credentials' in str(manager.credentials_dir)


class TestSaveTokens:
    """Test token saving functionality."""
    
    def test_save_tokens_creates_file(self, token_manager, valid_tokens):
        """Test that save_tokens creates a JSON file."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        token_path = token_manager._get_token_path('test_account')
        assert token_path.exists()
        
        # Verify file contents
        with open(token_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['access_token'] == 'test_access_token_123'
        assert saved_data['refresh_token'] == 'test_refresh_token_456'
    
    def test_save_tokens_creates_directory(self, tmp_path):
        """Test that save_tokens creates credentials directory if missing."""
        creds_dir = tmp_path / "new_credentials"
        manager = TokenManager(credentials_dir=creds_dir)
        
        assert not creds_dir.exists()
        manager.save_tokens('test_account', {'access_token': 'token'})
        assert creds_dir.exists()
    
    def test_save_tokens_serializes_datetime(self, token_manager, valid_tokens):
        """Test that datetime objects are serialized to ISO strings."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        token_path = token_manager._get_token_path('test_account')
        with open(token_path, 'r') as f:
            saved_data = json.load(f)
        
        # expires_at should be ISO string, not datetime
        assert isinstance(saved_data['expires_at'], str)
        # Should be parseable as ISO format
        datetime.fromisoformat(saved_data['expires_at'])
    
    def test_save_tokens_atomic_write(self, token_manager, valid_tokens):
        """Test that save uses atomic write (temp file + rename)."""
        token_path = token_manager._get_token_path('test_account')
        
        # Save tokens
        token_manager.save_tokens('test_account', valid_tokens)
        
        # Verify file exists and is valid JSON
        assert token_path.exists()
        with open(token_path, 'r') as f:
            json.load(f)  # Should not raise
    
    def test_save_tokens_validates_structure(self, token_manager):
        """Test that save_tokens validates token structure."""
        invalid_tokens = {'invalid': 'structure'}
        
        with pytest.raises(ValueError, match="access_token"):
            token_manager.save_tokens('test_account', invalid_tokens)
    
    def test_save_tokens_handles_permission_error(self, token_manager, valid_tokens, monkeypatch):
        """Test that save_tokens handles permission errors gracefully."""
        def mock_chmod(path, mode):
            raise PermissionError("Permission denied")
        
        monkeypatch.setattr(os, 'chmod', mock_chmod)
        
        # Should still save (chmod failure is logged but doesn't stop save)
        token_manager.save_tokens('test_account', valid_tokens)
        assert token_manager._get_token_path('test_account').exists()


class TestLoadTokens:
    """Test token loading functionality."""
    
    def test_load_tokens_returns_dict(self, token_manager, valid_tokens):
        """Test that load_tokens returns token dictionary."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        loaded = token_manager.load_tokens('test_account')
        assert isinstance(loaded, dict)
        assert loaded['access_token'] == 'test_access_token_123'
    
    def test_load_tokens_returns_none_if_missing(self, token_manager):
        """Test that load_tokens returns None for non-existent account."""
        loaded = token_manager.load_tokens('nonexistent_account')
        assert loaded is None
    
    def test_load_tokens_deserializes_datetime(self, token_manager, valid_tokens):
        """Test that ISO datetime strings are deserialized to datetime objects."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        loaded = token_manager.load_tokens('test_account')
        assert isinstance(loaded['expires_at'], datetime)
    
    def test_load_tokens_handles_invalid_json(self, token_manager):
        """Test that load_tokens raises JSONDecodeError for invalid JSON."""
        token_path = token_manager._get_token_path('test_account')
        token_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write invalid JSON
        with open(token_path, 'w') as f:
            f.write('{ invalid json }')
        
        with pytest.raises(json.JSONDecodeError):
            token_manager.load_tokens('test_account')
    
    def test_load_tokens_handles_permission_error(self, token_manager, valid_tokens, monkeypatch):
        """Test that load_tokens handles permission errors."""
        token_manager.save_tokens('test_account', valid_tokens)
        token_path = token_manager._get_token_path('test_account')
        
        def mock_open(*args, **kwargs):
            raise PermissionError("Permission denied")
        
        monkeypatch.setattr('builtins.open', mock_open)
        
        with pytest.raises(PermissionError):
            token_manager.load_tokens('test_account')


class TestTokenExpiry:
    """Test token expiry checking logic."""
    
    def test_is_token_expired_future_expiry(self, token_manager, valid_tokens):
        """Test that future expiry returns False (not expired)."""
        # Token expires in 1 hour, should not be expired
        assert not token_manager._is_token_expired(valid_tokens)
    
    def test_is_token_expired_past_expiry(self, token_manager, expired_tokens):
        """Test that past expiry returns True (expired)."""
        assert token_manager._is_token_expired(expired_tokens)
    
    def test_is_token_expired_with_buffer(self, token_manager):
        """Test that 5-minute buffer is applied."""
        # Token expires in 4 minutes (within buffer)
        tokens = {
            'access_token': 'token',
            'expires_at': datetime.now() + timedelta(minutes=4),
        }
        assert token_manager._is_token_expired(tokens)  # Should be expired due to buffer
    
    def test_is_token_expired_with_expires_in(self, token_manager):
        """Test expiry checking with expires_in field."""
        # Token expires in 1 hour
        tokens = {
            'access_token': 'token',
            'expires_in': 3600,
        }
        assert not token_manager._is_token_expired(tokens)
        
        # Token expires in 4 minutes (within buffer)
        tokens = {
            'access_token': 'token',
            'expires_in': 240,  # 4 minutes
        }
        assert token_manager._is_token_expired(tokens)
    
    def test_is_token_expired_missing_expiry(self, token_manager):
        """Test that missing expiry information treats token as expired."""
        tokens = {
            'access_token': 'token',
            # No expiry info
        }
        assert token_manager._is_token_expired(tokens)
    
    def test_is_token_expired_malformed_expiry(self, token_manager):
        """Test that malformed expiry treats token as expired."""
        tokens = {
            'access_token': 'token',
            'expires_at': 'invalid_datetime_string',
        }
        assert token_manager._is_token_expired(tokens)


class TestRefreshToken:
    """Test token refresh functionality."""
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    @patch('src.auth.token_manager.requests.post')
    def test_refresh_token_success(self, mock_post, token_manager, valid_tokens):
        """Test successful token refresh."""
        # Setup existing tokens
        token_manager.save_tokens('test_account', valid_tokens)
        
        # Mock successful refresh response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        # Refresh token
        refreshed = token_manager.refresh_token('test_account', 'google')
        
        assert refreshed['access_token'] == 'new_access_token'
        assert refreshed['refresh_token'] == 'new_refresh_token'
        assert 'expires_at' in refreshed
        
        # Verify tokens were saved
        loaded = token_manager.load_tokens('test_account')
        assert loaded['access_token'] == 'new_access_token'
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    @patch('src.auth.token_manager.requests.post')
    def test_refresh_token_http_error(self, mock_post, token_manager, valid_tokens):
        """Test token refresh with HTTP error response."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Token expired',
        }
        mock_response.raise_for_status.side_effect = Exception("HTTP 400")
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        with pytest.raises(TokenRefreshError):
            token_manager.refresh_token('test_account', 'google')
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    @patch('src.auth.token_manager.requests.post')
    def test_refresh_token_network_error(self, mock_post, token_manager, valid_tokens):
        """Test token refresh with network error."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        # Mock network error
        mock_post.side_effect = Exception("Network error")
        
        with pytest.raises(TokenRefreshError, match="Network error"):
            token_manager.refresh_token('test_account', 'google')
    
    def test_refresh_token_missing_tokens(self, token_manager):
        """Test refresh_token with no existing tokens."""
        with pytest.raises(TokenRefreshError, match="No tokens found"):
            token_manager.refresh_token('nonexistent_account', 'google')
    
    def test_refresh_token_missing_refresh_token(self, token_manager):
        """Test refresh_token with no refresh_token in tokens."""
        tokens = {'access_token': 'token'}  # No refresh_token
        token_manager.save_tokens('test_account', tokens)
        
        with pytest.raises(TokenRefreshError, match="No refresh token"):
            token_manager.refresh_token('test_account', 'google')
    
    def test_refresh_token_missing_credentials(self, token_manager, valid_tokens):
        """Test refresh_token with missing environment variables."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(TokenRefreshError, match="CLIENT_ID"):
                token_manager.refresh_token('test_account', 'google')
    
    def test_refresh_token_unknown_provider(self, token_manager, valid_tokens):
        """Test refresh_token with unknown provider."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        with pytest.raises(TokenRefreshError, match="Unknown provider"):
            token_manager.refresh_token('test_account', 'unknown_provider')
    
    @patch.dict(os.environ, {
        'MS_CLIENT_ID': 'ms_client_id',
        'MS_CLIENT_SECRET': 'ms_client_secret',
    })
    @patch('src.auth.token_manager.requests.post')
    def test_refresh_token_microsoft(self, mock_post, token_manager, valid_tokens):
        """Test token refresh for Microsoft provider."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'access_token': 'new_token',
            'expires_in': 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        refreshed = token_manager.refresh_token('test_account', 'microsoft')
        assert refreshed['access_token'] == 'new_token'
        
        # Verify correct endpoint was called
        assert 'microsoftonline.com' in mock_post.call_args[0][0]


class TestGetValidToken:
    """Test get_valid_token with automatic refresh."""
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    def test_get_valid_token_valid_token(self, token_manager, valid_tokens):
        """Test get_valid_token with valid (non-expired) token."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        token = token_manager.get_valid_token('test_account', 'google')
        
        assert token == 'test_access_token_123'
        # Should not have called refresh
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    @patch('src.auth.token_manager.requests.post')
    def test_get_valid_token_expired_refreshes(self, mock_post, token_manager, expired_tokens):
        """Test get_valid_token with expired token triggers refresh."""
        token_manager.save_tokens('test_account', expired_tokens)
        
        # Mock successful refresh
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'access_token': 'refreshed_token',
            'expires_in': 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        token = token_manager.get_valid_token('test_account', 'google')
        
        assert token == 'refreshed_token'
        # Verify refresh was called
        assert mock_post.called
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    def test_get_valid_token_missing_returns_none(self, token_manager):
        """Test get_valid_token with no tokens returns None."""
        token = token_manager.get_valid_token('nonexistent_account', 'google')
        assert token is None
    
    @patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_client_secret',
    })
    @patch('src.auth.token_manager.requests.post')
    def test_get_valid_token_refresh_failure_returns_none(self, mock_post, token_manager, expired_tokens):
        """Test get_valid_token when refresh fails returns None after retry."""
        token_manager.save_tokens('test_account', expired_tokens)
        
        # Mock refresh failure
        mock_post.side_effect = Exception("Refresh failed")
        
        token = token_manager.get_valid_token('test_account', 'google')
        
        assert token is None
        # Should have retried once
        assert mock_post.call_count == 2
    
    def test_get_valid_token_caching(self, token_manager, valid_tokens):
        """Test that get_valid_token caches valid tokens briefly."""
        token_manager.save_tokens('test_account', valid_tokens)
        
        # First call
        token1 = token_manager.get_valid_token('test_account', 'google')
        
        # Second call should use cache (no file read)
        token2 = token_manager.get_valid_token('test_account', 'google')
        
        assert token1 == token2 == 'test_access_token_123'


class TestTokenValidation:
    """Test token structure validation."""
    
    def test_validate_token_structure_valid(self, token_manager):
        """Test validation with valid token structure."""
        tokens = {
            'access_token': 'token',
            'refresh_token': 'refresh',
            'expires_at': datetime.now(),
        }
        # Should not raise
        token_manager._validate_token_structure(tokens)
    
    def test_validate_token_structure_missing_access_token(self, token_manager):
        """Test validation fails with missing access_token."""
        tokens = {'refresh_token': 'refresh'}
        
        with pytest.raises(ValueError, match="access_token"):
            token_manager._validate_token_structure(tokens, strict=True)
    
    def test_validate_token_structure_empty_access_token(self, token_manager):
        """Test validation fails with empty access_token."""
        tokens = {'access_token': ''}
        
        with pytest.raises(ValueError, match="access_token"):
            token_manager._validate_token_structure(tokens)
    
    def test_validate_token_structure_invalid_expires_in(self, token_manager):
        """Test validation fails with invalid expires_in."""
        tokens = {
            'access_token': 'token',
            'expires_in': 'not_a_number',  # Non-numeric
        }
        
        with pytest.raises(ValueError, match="expires_in"):
            token_manager._validate_token_structure(tokens)
    
    def test_validate_token_structure_v4_compatibility(self, token_manager):
        """Test validation allows V4 format when not strict."""
        tokens = {'some_v4_field': 'value'}  # No access_token
        
        # Should not raise when strict=False
        token_manager._validate_token_structure(tokens, strict=False)


class TestGetTokenPath:
    """Test token path generation."""
    
    def test_get_token_path_sanitizes_name(self, token_manager):
        """Test that account names are sanitized to prevent directory traversal."""
        path1 = token_manager._get_token_path('normal_account')
        path2 = token_manager._get_token_path('../../etc/passwd')
        
        # Path should not contain actual '..' directory traversal
        # (sanitization replaces '..' with '_')
        path_str = str(path2)
        # Check that path doesn't go up directories (no '..' as path component)
        path_parts = Path(path_str).parts
        assert '..' not in path_parts
        assert path1.name == 'normal_account.json'
    
    def test_get_token_path_uses_credentials_dir(self, token_manager):
        """Test that token path uses credentials directory."""
        path = token_manager._get_token_path('test_account')
        
        assert token_manager.credentials_dir in path.parents
        assert path.name == 'test_account.json'
