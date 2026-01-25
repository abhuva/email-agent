"""OAuth flow implementation for CLI-based authentication.

This module implements the interactive OAuth 2.0 flow for CLI-based authentication,
including local HTTP server for callback handling, browser automation, and token management.
"""
import logging
import secrets
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, urlparse

from src.auth.interfaces import OAuthProvider, TokenInfo, OAuthError, generate_state
from src.auth.token_manager import TokenManager

logger = logging.getLogger(__name__)


class OAuthPortError(OAuthError):
    """Exception raised when no ports are available for OAuth callback."""
    pass


class OAuthCallbackError(OAuthError):
    """Exception raised when OAuth callback handling fails."""
    pass


class OAuthTimeoutError(OAuthError):
    """Exception raised when OAuth flow times out."""
    pass


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback.
    
    This handler processes OAuth authorization callbacks from the OAuth provider,
    extracting the authorization code and state parameter from query parameters.
    """
    
    def __init__(self, oauth_flow, *args, **kwargs):
        """Initialize handler with reference to OAuthFlow instance.
        
        Args:
            oauth_flow: OAuthFlow instance to store callback data
        """
        self.oauth_flow = oauth_flow
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET request from OAuth provider callback."""
        try:
            # Parse URL and query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Extract code and state from query parameters
            code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            error = query_params.get('error', [None])[0]
            error_description = query_params.get('error_description', [None])[0]
            
            # Handle OAuth errors
            if error:
                error_msg = f"OAuth error: {error}"
                if error_description:
                    error_msg += f" - {error_description}"
                logger.error(error_msg)
                self.oauth_flow.callback_error = OAuthCallbackError(error_msg)
                self._send_response(400, "Authentication failed. Please check the console for details.")
                return
            
            # Validate required parameters
            if not code:
                error_msg = "Missing authorization code in callback"
                logger.error(error_msg)
                self.oauth_flow.callback_error = OAuthCallbackError(error_msg)
                self._send_response(400, "Missing authorization code. Please try again.")
                return
            
            if not state:
                error_msg = "Missing state parameter in callback"
                logger.error(error_msg)
                self.oauth_flow.callback_error = OAuthCallbackError(error_msg)
                self._send_response(400, "Missing state parameter. Please try again.")
                return
            
            # Store callback data in OAuthFlow
            self.oauth_flow.auth_code = code
            self.oauth_flow.callback_state = state
            self.oauth_flow.callback_received = True
            
            # Send success response
            self._send_response(200, "Authentication successful! You can close this window.")
            logger.info("OAuth callback received successfully")
            
        except Exception as e:
            error_msg = f"Error processing OAuth callback: {e}"
            logger.error(error_msg, exc_info=True)
            self.oauth_flow.callback_error = OAuthCallbackError(error_msg)
            self._send_response(500, "Internal error processing callback. Please check the console.")
    
    def _send_response(self, status_code: int, message: str):
        """Send HTTP response to client.
        
        Args:
            status_code: HTTP status code
            message: Response message body
        """
        self.send_response(status_code)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        # Send user-friendly HTML response
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Authentication</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    max-width: 500px;
                    margin: 0 auto;
                }}
                h1 {{
                    color: {'#4CAF50' if status_code == 200 else '#f44336'};
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{'✓ Success' if status_code == 200 else '✗ Error'}</h1>
                <p>{message}</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to suppress default HTTP server logging."""
        # Only log at debug level to reduce noise
        logger.debug(f"HTTP {format % args}")


class OAuthFlow:
    """Orchestrates the OAuth 2.0 flow for CLI-based authentication.
    
    This class handles the complete OAuth 2.0 Authorization Code Flow:
    1. Starts a local HTTP server to receive OAuth callbacks
    2. Generates authorization URL with secure state parameter
    3. Opens user's browser to authorization URL
    4. Waits for callback with authorization code
    5. Exchanges code for tokens using the provider
    6. Saves tokens securely using TokenManager
    
    Attributes:
        provider: OAuth provider instance (GoogleOAuthProvider or MicrosoftOAuthProvider)
        token_manager: TokenManager instance for saving tokens
        account_name: Account name for token storage
        callback_port: Port number for OAuth callback (default: 8080, auto-detected)
        server: ThreadingHTTPServer instance for callback handling
        _state: Cryptographically secure state parameter for CSRF protection
        auth_code: Authorization code received from callback
        callback_state: State parameter received from callback
        callback_received: Flag indicating callback was received
        callback_error: Exception raised during callback handling
    """
    
    def __init__(
        self,
        provider: OAuthProvider,
        token_manager: TokenManager,
        account_name: str,
        callback_port: Optional[int] = None,
    ):
        """Initialize OAuth flow.
        
        Args:
            provider: OAuth provider instance (must implement OAuthProvider interface)
            token_manager: TokenManager instance for saving tokens
            account_name: Account name for token storage
            callback_port: Port for callback server (None = auto-detect, default: 8080)
        
        Raises:
            OAuthError: If provider is invalid
        """
        if not isinstance(provider, OAuthProvider):
            raise OAuthError(f"Provider must implement OAuthProvider interface, got {type(provider)}")
        
        self.provider = provider
        self.token_manager = token_manager
        self.account_name = account_name
        self.callback_port = callback_port or 8080
        
        # Server state
        self.server: Optional[ThreadingHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # OAuth flow state
        self._state: Optional[str] = None
        self.auth_code: Optional[str] = None
        self.callback_state: Optional[str] = None
        self.callback_received = False
        self.callback_error: Optional[Exception] = None
        
        logger.debug(f"OAuthFlow initialized for account '{account_name}'")
    
    def find_available_port(self, start_port: int = 8080, max_attempts: int = 20) -> int:
        """Find an available port for OAuth callback server.
        
        Tries ports sequentially from start_port to start_port + max_attempts - 1.
        Uses socket binding to test port availability.
        
        Args:
            start_port: First port to try (default: 8080)
            max_attempts: Maximum number of ports to try (default: 20, ports 8080-8099)
        
        Returns:
            Available port number
        
        Raises:
            OAuthPortError: If no ports are available in the range
        """
        for port in range(start_port, start_port + max_attempts):
            try:
                # Try to bind to the port
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    test_socket.bind(('localhost', port))
                    logger.debug(f"Found available port: {port}")
                    return port
            except OSError:
                # Port is in use, try next
                continue
        
        # No ports available
        error_msg = (
            f"No available ports in range {start_port}-{start_port + max_attempts - 1}. "
            "Please free a port or use manual code entry."
        )
        logger.error(error_msg)
        raise OAuthPortError(error_msg)
    
    def start_local_server(self, port: Optional[int] = None) -> int:
        """Start local HTTP server to receive OAuth callback.
        
        Creates a ThreadingHTTPServer on the specified port (or auto-detected port)
        to handle OAuth authorization callbacks. Server runs in a separate thread
        to avoid blocking the main flow.
        
        Args:
            port: Port number to use (None = use self.callback_port or auto-detect)
        
        Returns:
            Port number the server is listening on
        
        Raises:
            OAuthPortError: If no ports are available
            OAuthError: If server startup fails
        """
        # Find available port if not specified
        if port is None:
            port = self.callback_port
        
        # Try to find available port
        try:
            port = self.find_available_port(start_port=port)
        except OAuthPortError:
            # If default port failed, try from 8080
            if port != 8080:
                try:
                    port = self.find_available_port(start_port=8080)
                except OAuthPortError:
                    raise
        
        self.callback_port = port
        
        # Create handler factory that passes OAuthFlow instance
        def handler_factory(*args, **kwargs):
            return OAuthCallbackHandler(self, *args, **kwargs)
        
        try:
            # Create server
            self.server = ThreadingHTTPServer(('localhost', port), handler_factory)
            self.server.timeout = 1.0  # Allow periodic checks for shutdown
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name=f"OAuthCallbackServer-{port}"
            )
            self.server_thread.start()
            
            logger.info(f"Listening for OAuth callback on http://localhost:{port}")
            return port
            
        except Exception as e:
            error_msg = f"Failed to start OAuth callback server: {e}"
            logger.error(error_msg)
            raise OAuthError(error_msg) from e
    
    def _run_server(self):
        """Run HTTP server in background thread.
        
        Handles requests until shutdown is requested.
        """
        try:
            while not getattr(self, '_shutdown_requested', False):
                self.server.handle_request()
        except Exception as e:
            logger.error(f"Error in OAuth callback server: {e}", exc_info=True)
    
    def stop_local_server(self):
        """Stop the local HTTP server gracefully.
        
        Shuts down the server and waits for the thread to finish.
        """
        if self.server:
            self._shutdown_requested = True
            try:
                # Shutdown server
                self.server.shutdown()
                logger.debug("OAuth callback server shut down")
            except Exception as e:
                logger.warning(f"Error shutting down server: {e}")
            finally:
                self.server = None
                self.server_thread = None
    
    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL with secure state parameter.
        
        Generates a cryptographically secure state parameter and constructs
        the authorization URL using the provider's get_auth_url() method.
        Updates the provider's redirect_uri to match the callback server port.
        
        Returns:
            Complete authorization URL ready for browser
        
        Raises:
            OAuthError: If URL generation fails
        """
        try:
            # Generate secure state parameter
            self._state = generate_state()
            
            # Update provider's redirect URI to match our callback port
            redirect_uri = f"http://localhost:{self.callback_port}/callback"
            if hasattr(self.provider, 'redirect_uri'):
                self.provider.redirect_uri = redirect_uri
            
            # Generate authorization URL
            auth_url = self.provider.get_auth_url(self._state)
            
            logger.info(f"Generated authorization URL with state: {self._state[:16]}...")
            return auth_url
            
        except Exception as e:
            error_msg = f"Failed to generate authorization URL: {e}"
            logger.error(error_msg)
            raise OAuthError(error_msg) from e
    
    def open_browser(self, auth_url: str):
        """Open user's default browser to authorization URL.
        
        Args:
            auth_url: Complete authorization URL to open
        """
        try:
            webbrowser.open(auth_url)
            logger.info("Opened browser to authorization URL")
        except Exception as e:
            logger.warning(f"Could not open browser automatically: {e}")
            logger.info(f"Please manually visit: {auth_url}")
    
    def wait_for_callback(self, timeout: int = 120) -> tuple[Optional[str], Optional[str]]:
        """Wait for OAuth callback with authorization code.
        
        Polls for callback_received flag, checking for errors and timeout.
        Validates state parameter to prevent CSRF attacks.
        
        Args:
            timeout: Maximum seconds to wait for callback (default: 120)
        
        Returns:
            Tuple of (auth_code, state) if callback received, (None, None) on timeout
        
        Raises:
            OAuthTimeoutError: If callback not received within timeout
            OAuthCallbackError: If callback contains errors
            ValueError: If state parameter doesn't match (CSRF protection)
        """
        start_time = time.time()
        
        while not self.callback_received:
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                error_msg = f"OAuth callback timeout after {timeout} seconds"
                logger.error(error_msg)
                raise OAuthTimeoutError(error_msg)
            
            # Check for callback errors
            if self.callback_error:
                raise self.callback_error
            
            # Sleep briefly before checking again
            time.sleep(0.5)
        
        # Validate state parameter (CSRF protection)
        if self.callback_state != self._state:
            error_msg = "State parameter mismatch - possible CSRF attack"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("OAuth callback received and validated")
        return self.auth_code, self.callback_state
    
    def exchange_tokens(self, code: str, state: str) -> TokenInfo:
        """Exchange authorization code for access/refresh tokens.
        
        Uses the provider's handle_callback() method to exchange the authorization
        code for tokens. Validates the response and returns TokenInfo.
        
        Args:
            code: Authorization code from callback
            state: State parameter (must match original state)
        
        Returns:
            TokenInfo dictionary with access_token, refresh_token, expires_at
        
        Raises:
            OAuthError: If token exchange fails
            ValueError: If state parameter doesn't match
        """
        try:
            # Exchange code for tokens using provider
            token_info = self.provider.handle_callback(code, state)
            
            # Validate token response
            if not token_info.get('access_token'):
                raise OAuthError("Missing access_token in token response")
            
            logger.info("Successfully exchanged authorization code for tokens")
            return token_info
            
        except ValueError:
            # Re-raise state mismatch errors
            raise
        except Exception as e:
            error_msg = f"Failed to exchange authorization code for tokens: {e}"
            logger.error(error_msg)
            raise OAuthError(error_msg) from e
    
    def save_tokens(self, token_info: TokenInfo):
        """Save tokens securely using TokenManager.
        
        Args:
            token_info: TokenInfo dictionary to save
        
        Raises:
            OAuthError: If token saving fails
        """
        try:
            # Convert TokenInfo to dict format expected by TokenManager
            tokens_dict = {
                'access_token': token_info['access_token'],
                'refresh_token': token_info.get('refresh_token'),
                'expires_at': token_info.get('expires_at'),
            }
            
            # Save using TokenManager
            self.token_manager.save_tokens(self.account_name, tokens_dict)
            logger.info(f"Saved tokens for account '{self.account_name}'")
            
        except Exception as e:
            error_msg = f"Failed to save tokens: {e}"
            logger.error(error_msg)
            raise OAuthError(error_msg) from e
    
    def run(self, timeout: int = 120) -> TokenInfo:
        """Run the complete OAuth flow.
        
        Orchestrates all steps of the OAuth 2.0 Authorization Code Flow:
        1. Start local HTTP server
        2. Generate authorization URL
        3. Open browser
        4. Wait for callback
        5. Exchange code for tokens
        6. Save tokens
        
        Args:
            timeout: Maximum seconds to wait for callback (default: 120)
        
        Returns:
            TokenInfo dictionary with saved tokens
        
        Raises:
            OAuthError: If any step fails
            OAuthTimeoutError: If callback timeout
            OAuthPortError: If no ports available
        """
        try:
            # Step 1: Start local server
            port = self.start_local_server()
            logger.info(f"OAuth callback server started on port {port}")
            
            # Step 2: Generate authorization URL
            auth_url = self.get_authorization_url()
            
            # Step 3: Open browser
            print(f"\n{'='*60}")
            print("Please authorize this application by visiting:")
            print(f"{auth_url}")
            print(f"{'='*60}\n")
            self.open_browser(auth_url)
            
            # Step 4: Wait for callback
            print("Waiting for authorization...")
            code, state = self.wait_for_callback(timeout=timeout)
            
            if not code:
                raise OAuthTimeoutError("No authorization code received")
            
            # Step 5: Exchange code for tokens
            print("Exchanging authorization code for tokens...")
            token_info = self.exchange_tokens(code, state)
            
            # Step 6: Save tokens
            print("Saving tokens...")
            self.save_tokens(token_info)
            
            print("✅ Authentication successful! Tokens saved.")
            logger.info(f"OAuth flow completed successfully for account '{self.account_name}'")
            
            return token_info
            
        except (OAuthTimeoutError, OAuthPortError):
            # Re-raise these specific errors
            raise
        except Exception as e:
            error_msg = f"OAuth flow failed: {e}"
            logger.error(error_msg, exc_info=True)
            raise OAuthError(error_msg) from e
        finally:
            # Always cleanup server
            self.stop_local_server()
