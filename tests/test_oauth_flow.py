"""
Tests for OAuth flow implementation.

Tests verify OAuth flow orchestration, local HTTP server, port conflict handling,
authorization URL generation, callback handling, token exchange, and error scenarios.
"""
import pytest
import socket
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from urllib.parse import urlparse, parse_qs

from src.auth.oauth_flow import (
    OAuthFlow,
    OAuthCallbackHandler,
    OAuthPortError,
    OAuthCallbackError,
    OAuthTimeoutError,
)
from src.auth.interfaces import OAuthProvider, TokenInfo, OAuthError
from src.auth.token_manager import TokenManager


@pytest.fixture
def mock_provider():
    """Create a mock OAuth provider."""
    provider = MagicMock(spec=OAuthProvider)
    provider.get_auth_url.return_value = 'https://example.com/auth?state=test_state'
    provider.handle_callback.return_value = {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_at': datetime.now() + timedelta(hours=1),
    }
    provider.redirect_uri = 'http://localhost:8080/callback'
    return provider


@pytest.fixture
def mock_token_manager(tmp_path):
    """Create a mock TokenManager."""
    return TokenManager(credentials_dir=tmp_path / 'credentials')


@pytest.fixture
def oauth_flow(mock_provider, mock_token_manager):
    """Create an OAuthFlow instance for testing."""
    return OAuthFlow(
        provider=mock_provider,
        token_manager=mock_token_manager,
        account_name='test_account',
    )


class TestOAuthFlowInitialization:
    """Test OAuthFlow initialization."""
    
    def test_init_success(self, mock_provider, mock_token_manager):
        """Test successful initialization."""
        flow = OAuthFlow(
            provider=mock_provider,
            token_manager=mock_token_manager,
            account_name='test_account',
        )
        assert flow.provider == mock_provider
        assert flow.token_manager == mock_token_manager
        assert flow.account_name == 'test_account'
        assert flow.callback_port == 8080
        assert flow.server is None
        assert flow._state is None
    
    def test_init_invalid_provider(self, mock_token_manager):
        """Test initialization with invalid provider raises error."""
        invalid_provider = Mock()  # Doesn't implement OAuthProvider
        
        with pytest.raises(OAuthError, match="must implement OAuthProvider"):
            OAuthFlow(
                provider=invalid_provider,
                token_manager=mock_token_manager,
                account_name='test_account',
            )
    
    def test_init_custom_port(self, mock_provider, mock_token_manager):
        """Test initialization with custom callback port."""
        flow = OAuthFlow(
            provider=mock_provider,
            token_manager=mock_token_manager,
            account_name='test_account',
            callback_port=9000,
        )
        assert flow.callback_port == 9000


class TestFindAvailablePort:
    """Test port finding functionality."""
    
    def test_find_available_port_success(self, oauth_flow):
        """Test finding an available port."""
        port = oauth_flow.find_available_port(start_port=8080, max_attempts=5)
        assert 8080 <= port < 8085
        assert isinstance(port, int)
    
    @patch('socket.socket')
    def test_find_available_port_all_busy(self, mock_socket, oauth_flow):
        """Test that OAuthPortError is raised when all ports are busy."""
        # Mock all ports as busy
        mock_socket.return_value.__enter__.return_value.bind.side_effect = OSError()
        
        with pytest.raises(OAuthPortError, match="No available ports"):
            oauth_flow.find_available_port(start_port=8080, max_attempts=3)
    
    @patch('src.auth.oauth_flow.socket.socket')
    def test_find_available_port_skips_busy(self, mock_socket_class, oauth_flow):
        """Test that busy ports are skipped and next available is found."""
        call_count = [0]  # Use list to allow modification in nested function
        
        def create_mock_socket(*args, **kwargs):
            mock_sock = MagicMock()
            mock_sock.__enter__ = Mock(return_value=mock_sock)
            mock_sock.__exit__ = Mock(return_value=None)
            
            # First call (port 8080) raises OSError (busy)
            # Subsequent calls succeed
            if call_count[0] == 0:
                mock_sock.bind.side_effect = OSError("Port busy")
            else:
                mock_sock.bind.return_value = None
            call_count[0] += 1
            return mock_sock
        
        mock_socket_class.side_effect = create_mock_socket
        
        # Should find next available port (skip 8080)
        port = oauth_flow.find_available_port(start_port=8080, max_attempts=5)
        # Port should be different from 8080 (which is busy)
        assert port != 8080, f"Expected port != 8080, got {port}"
        assert 8080 < port < 8085, f"Expected port in range (8080, 8085), got {port}"


class TestStartLocalServer:
    """Test local HTTP server startup."""
    
    def test_start_local_server_success(self, oauth_flow):
        """Test successful server startup."""
        port = oauth_flow.start_local_server()
        
        assert isinstance(port, int)
        assert 8080 <= port < 8100
        assert oauth_flow.server is not None
        assert oauth_flow.server_thread is not None
        assert oauth_flow.server_thread.is_alive()
        
        # Cleanup
        oauth_flow.stop_local_server()
    
    def test_start_local_server_auto_find_port(self, oauth_flow):
        """Test server startup with auto port detection."""
        # Make default port busy by actually binding and listening
        busy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        busy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            busy_socket.bind(('localhost', 8080))
            busy_socket.listen(1)  # Actually listen to make port truly busy
            time.sleep(0.1)  # Give socket time to fully bind (especially on Windows)
            
            # Verify port is actually busy by trying to bind again
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                test_socket.bind(('localhost', 8080))
                # If we get here, port isn't actually busy - skip test
                test_socket.close()
                pytest.skip("Port 8080 is not actually busy - may be a timing issue")
            except OSError:
                # Port is busy as expected
                test_socket.close()
                pass
            
            # Should find alternative port (starts from 8080, so should find 8081 or higher)
            port = oauth_flow.start_local_server()
            assert port != 8080
            assert port >= 8081  # Should be at least 8081 since 8080 is busy
        finally:
            busy_socket.close()
            oauth_flow.stop_local_server()
            time.sleep(0.1)  # Give socket time to release
    
    def test_stop_local_server(self, oauth_flow):
        """Test server shutdown."""
        oauth_flow.start_local_server()
        assert oauth_flow.server is not None
        
        oauth_flow.stop_local_server()
        # Server should be cleaned up
        assert oauth_flow.server is None


class TestGetAuthorizationUrl:
    """Test authorization URL generation."""
    
    @patch('src.auth.oauth_flow.generate_state')
    def test_get_authorization_url_success(self, mock_generate_state, oauth_flow):
        """Test successful authorization URL generation."""
        mock_generate_state.return_value = 'test_state_123'
        oauth_flow.callback_port = 8080
        
        # Make mock provider return URL with the state that was passed to it
        def get_auth_url_side_effect(state):
            return f'https://example.com/auth?state={state}'
        oauth_flow.provider.get_auth_url.side_effect = get_auth_url_side_effect
        
        url = oauth_flow.get_authorization_url()
        
        assert url == 'https://example.com/auth?state=test_state_123'
        assert oauth_flow._state == 'test_state_123'
        oauth_flow.provider.get_auth_url.assert_called_once_with('test_state_123')
    
    def test_get_authorization_url_updates_redirect_uri(self, oauth_flow):
        """Test that redirect URI is updated with callback port."""
        oauth_flow.callback_port = 9000
        oauth_flow.get_authorization_url()
        
        assert oauth_flow.provider.redirect_uri == 'http://localhost:9000/callback'
    
    def test_get_authorization_url_provider_error(self, oauth_flow):
        """Test that provider errors are propagated."""
        oauth_flow.provider.get_auth_url.side_effect = OAuthError("Provider error")
        
        with pytest.raises(OAuthError, match="Provider error"):
            oauth_flow.get_authorization_url()


class TestOpenBrowser:
    """Test browser opening functionality."""
    
    @patch('src.auth.oauth_flow.webbrowser.open')
    def test_open_browser_success(self, mock_open, oauth_flow):
        """Test successful browser opening."""
        auth_url = 'https://example.com/auth'
        oauth_flow.open_browser(auth_url)
        
        mock_open.assert_called_once_with(auth_url)
    
    @patch('src.auth.oauth_flow.webbrowser.open')
    def test_open_browser_error_handled(self, mock_open, oauth_flow):
        """Test that browser opening errors are handled gracefully."""
        mock_open.side_effect = Exception("Browser error")
        
        # Should not raise, just log warning
        oauth_flow.open_browser('https://example.com/auth')
        mock_open.assert_called_once()


class TestWaitForCallback:
    """Test callback waiting functionality."""
    
    def test_wait_for_callback_success(self, oauth_flow):
        """Test successful callback reception."""
        oauth_flow._state = 'test_state'
        oauth_flow.callback_state = 'test_state'
        oauth_flow.auth_code = 'test_code'
        oauth_flow.callback_received = True
        
        code, state = oauth_flow.wait_for_callback(timeout=1)
        
        assert code == 'test_code'
        assert state == 'test_state'
    
    def test_wait_for_callback_state_mismatch(self, oauth_flow):
        """Test that state mismatch raises ValueError."""
        oauth_flow._state = 'original_state'
        oauth_flow.callback_state = 'different_state'
        oauth_flow.auth_code = 'test_code'
        oauth_flow.callback_received = True
        
        with pytest.raises(ValueError, match="State parameter mismatch"):
            oauth_flow.wait_for_callback(timeout=1)
    
    def test_wait_for_callback_timeout(self, oauth_flow):
        """Test that timeout raises OAuthTimeoutError."""
        oauth_flow.callback_received = False
        
        with pytest.raises(OAuthTimeoutError, match="timeout"):
            oauth_flow.wait_for_callback(timeout=0.1)
    
    def test_wait_for_callback_error(self, oauth_flow):
        """Test that callback errors are raised."""
        oauth_flow.callback_received = False
        oauth_flow.callback_error = OAuthCallbackError("Callback error")
        
        with pytest.raises(OAuthCallbackError, match="Callback error"):
            oauth_flow.wait_for_callback(timeout=0.1)


class TestExchangeTokens:
    """Test token exchange functionality."""
    
    def test_exchange_tokens_success(self, oauth_flow):
        """Test successful token exchange."""
        token_info = oauth_flow.exchange_tokens('test_code', 'test_state')
        
        assert token_info['access_token'] == 'test_access_token'
        assert token_info['refresh_token'] == 'test_refresh_token'
        oauth_flow.provider.handle_callback.assert_called_once_with('test_code', 'test_state')
    
    def test_exchange_tokens_missing_access_token(self, oauth_flow):
        """Test that missing access_token raises error."""
        oauth_flow.provider.handle_callback.return_value = {
            'refresh_token': 'test_refresh_token',
        }
        
        with pytest.raises(OAuthError, match="Missing access_token"):
            oauth_flow.exchange_tokens('test_code', 'test_state')
    
    def test_exchange_tokens_provider_error(self, oauth_flow):
        """Test that provider errors are propagated."""
        oauth_flow.provider.handle_callback.side_effect = OAuthError("Provider error")
        
        with pytest.raises(OAuthError, match="Provider error"):
            oauth_flow.exchange_tokens('test_code', 'test_state')
    
    def test_exchange_tokens_state_mismatch(self, oauth_flow):
        """Test that state mismatch from provider raises ValueError."""
        oauth_flow.provider.handle_callback.side_effect = ValueError("State mismatch")
        
        with pytest.raises(ValueError, match="State mismatch"):
            oauth_flow.exchange_tokens('test_code', 'test_state')


class TestSaveTokens:
    """Test token saving functionality."""
    
    def test_save_tokens_success(self, oauth_flow):
        """Test successful token saving."""
        token_info: TokenInfo = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_at': datetime.now() + timedelta(hours=1),
        }
        
        oauth_flow.save_tokens(token_info)
        
        # Verify tokens were saved
        saved_tokens = oauth_flow.token_manager.load_tokens('test_account')
        assert saved_tokens is not None
        assert saved_tokens['access_token'] == 'test_access_token'
    
    def test_save_tokens_error(self, oauth_flow):
        """Test that token saving errors are handled."""
        token_info: TokenInfo = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_at': datetime.now() + timedelta(hours=1),
        }
        
        # Mock token manager to raise error
        oauth_flow.token_manager.save_tokens = Mock(side_effect=Exception("Save error"))
        
        with pytest.raises(OAuthError, match="Failed to save tokens"):
            oauth_flow.save_tokens(token_info)


class TestOAuthCallbackHandler:
    """Test OAuth callback HTTP handler."""
    
    def test_handler_success(self, oauth_flow):
        """Test successful callback handling."""
        # Create a mock connection
        mock_connection = Mock()
        mock_connection.makefile.return_value = Mock()
        mock_address = ('127.0.0.1', 12345)
        mock_server = Mock()
        
        # Patch handle() to skip BaseHTTPRequestHandler's request handling
        # which tries to read raw_requestline and causes len() errors
        with patch.object(OAuthCallbackHandler, 'handle', lambda self: None):
            # Create handler with mocked connection
            handler = OAuthCallbackHandler(oauth_flow, mock_connection, mock_address, mock_server)
            handler.path = '/callback?code=test_code&state=test_state'
            handler.oauth_flow._state = 'test_state'
            
            # Mock the response methods
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            handler.wfile = Mock()
            handler.wfile.write = Mock()
            
            # Simulate GET request
            handler.do_GET()
        
        assert oauth_flow.auth_code == 'test_code'
        assert oauth_flow.callback_state == 'test_state'
        assert oauth_flow.callback_received is True
    
    def test_handler_missing_code(self, oauth_flow):
        """Test callback with missing code parameter."""
        # Create a mock connection
        mock_connection = Mock()
        mock_connection.makefile.return_value = Mock()
        mock_address = ('127.0.0.1', 12345)
        mock_server = Mock()
        
        # Patch handle() to skip BaseHTTPRequestHandler's request handling
        # which tries to read raw_requestline and causes len() errors
        with patch.object(OAuthCallbackHandler, 'handle', lambda self: None):
            handler = OAuthCallbackHandler(oauth_flow, mock_connection, mock_address, mock_server)
            handler.path = '/callback?state=test_state'
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            handler.wfile = Mock()
            handler.wfile.write = Mock()
            
            handler.do_GET()
        
        assert oauth_flow.callback_error is not None
        assert isinstance(oauth_flow.callback_error, OAuthCallbackError)
    
    def test_handler_oauth_error(self, oauth_flow):
        """Test callback with OAuth error parameter."""
        # Create a mock connection
        mock_connection = Mock()
        mock_connection.makefile.return_value = Mock()
        mock_address = ('127.0.0.1', 12345)
        mock_server = Mock()
        
        # Patch handle() to skip BaseHTTPRequestHandler's request handling
        # which tries to read raw_requestline and causes len() errors
        with patch.object(OAuthCallbackHandler, 'handle', lambda self: None):
            handler = OAuthCallbackHandler(oauth_flow, mock_connection, mock_address, mock_server)
            handler.path = '/callback?error=access_denied&error_description=User%20denied'
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            handler.wfile = Mock()
            handler.wfile.write = Mock()
            
            handler.do_GET()
        
        assert oauth_flow.callback_error is not None
        assert isinstance(oauth_flow.callback_error, OAuthCallbackError)


class TestRunCompleteFlow:
    """Test complete OAuth flow orchestration."""
    
    @patch('src.auth.oauth_flow.webbrowser.open')
    @patch('src.auth.oauth_flow.generate_state')
    def test_run_complete_flow_success(self, mock_generate_state, mock_open, oauth_flow):
        """Test successful complete OAuth flow."""
        mock_generate_state.return_value = 'test_state'
        
        # Simulate callback reception
        def simulate_callback():
            time.sleep(0.1)
            oauth_flow._state = 'test_state'
            oauth_flow.callback_state = 'test_state'
            oauth_flow.auth_code = 'test_code'
            oauth_flow.callback_received = True
        
        callback_thread = threading.Thread(target=simulate_callback)
        callback_thread.start()
        
        try:
            token_info = oauth_flow.run(timeout=5)
            
            assert token_info['access_token'] == 'test_access_token'
            assert oauth_flow.provider.get_auth_url.called
            assert oauth_flow.provider.handle_callback.called
            mock_open.assert_called_once()
        finally:
            callback_thread.join(timeout=1)
            oauth_flow.stop_local_server()
    
    def test_run_port_error(self, oauth_flow):
        """Test flow failure when no ports available."""
        # Patch start_local_server to raise OAuthPortError directly
        # This ensures the error is raised before the flow continues
        with patch.object(oauth_flow, 'start_local_server', side_effect=OAuthPortError("No ports available")):
            with pytest.raises(OAuthPortError, match="No ports available"):
                oauth_flow.run(timeout=1)
    
    def test_run_timeout(self, oauth_flow):
        """Test flow timeout when callback not received."""
        with patch.object(oauth_flow, 'start_local_server', return_value=8080):
            with pytest.raises(OAuthTimeoutError):
                oauth_flow.run(timeout=0.1)
    
    def test_run_cleanup_on_error(self, oauth_flow):
        """Test that server is cleaned up even on error."""
        oauth_flow.provider.get_auth_url.side_effect = OAuthError("Provider error")
        
        try:
            oauth_flow.run(timeout=1)
        except OAuthError:
            pass
        
        # Server should be cleaned up
        assert oauth_flow.server is None


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_multiple_ports_busy(self, oauth_flow):
        """Test handling when multiple ports are busy."""
        # Bind to several ports
        sockets = []
        try:
            for port in range(8080, 8083):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('localhost', port))
                sock.listen(1)  # Actually listen to make port truly busy
                sockets.append(sock)
            
            time.sleep(0.1)  # Give sockets time to fully bind (especially on Windows)
            
            # Verify ports are actually busy by trying to bind again
            for test_port in range(8080, 8083):
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    test_socket.bind(('localhost', test_port))
                    # If we get here, port isn't actually busy - skip test
                    test_socket.close()
                    pytest.skip(f"Port {test_port} is not actually busy - may be a timing issue")
                except OSError:
                    # Port is busy as expected
                    test_socket.close()
                    pass
            
            # Should find next available port (since 8080, 8081, 8082 are busy)
            port = oauth_flow.find_available_port(start_port=8080, max_attempts=10)
            assert port >= 8083
        finally:
            for sock in sockets:
                sock.close()
            time.sleep(0.1)  # Give sockets time to release
    
    def test_callback_with_invalid_state(self, oauth_flow):
        """Test callback with invalid state parameter."""
        oauth_flow._state = 'original_state'
        oauth_flow.callback_state = 'invalid_state'
        oauth_flow.auth_code = 'test_code'
        oauth_flow.callback_received = True
        
        with pytest.raises(ValueError, match="State parameter mismatch"):
            oauth_flow.wait_for_callback(timeout=1)
    
    def test_exchange_tokens_with_expired_code(self, oauth_flow):
        """Test token exchange with expired authorization code."""
        oauth_flow.provider.handle_callback.side_effect = OAuthError("Code expired")
        
        with pytest.raises(OAuthError, match="Code expired"):
            oauth_flow.exchange_tokens('expired_code', 'test_state')
