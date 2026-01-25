# V5 OAuth Flow Implementation

**Task:** 7 - Implement OAuth flow for CLI interaction  
**Status:** ✅ Complete  
**Module:** `src/auth/oauth_flow.py`

## Overview

The OAuth flow module implements the complete OAuth 2.0 Authorization Code Flow for CLI-based authentication. It orchestrates the entire authentication process, including local HTTP server setup, browser automation, callback handling, token exchange, and secure token storage.

## Architecture

The `OAuthFlow` class coordinates all steps of the OAuth 2.0 flow:

1. **Local HTTP Server**: Starts a local server to receive OAuth callbacks
2. **Port Management**: Automatically finds available ports (8080-8099) with conflict resolution
3. **Authorization URL**: Generates secure authorization URLs with CSRF protection
4. **Browser Automation**: Opens user's default browser to authorization URL
5. **Callback Handling**: Receives and validates OAuth callbacks
6. **Token Exchange**: Exchanges authorization codes for access/refresh tokens
7. **Token Storage**: Saves tokens securely using TokenManager

## Key Components

### OAuthFlow Class

Main orchestrator class that manages the complete OAuth flow.

**Initialization:**
```python
from src.auth.oauth_flow import OAuthFlow
from src.auth.providers.google import GoogleOAuthProvider
from src.auth.token_manager import TokenManager

provider = GoogleOAuthProvider()
token_manager = TokenManager()
flow = OAuthFlow(
    provider=provider,
    token_manager=token_manager,
    account_name='my_account',
    callback_port=8080  # Optional, defaults to 8080
)
```

**Running the Flow:**
```python
try:
    token_info = flow.run(timeout=120)
    print("✅ Authentication successful!")
except OAuthError as e:
    print(f"❌ Authentication failed: {e}")
```

### OAuthCallbackHandler

HTTP request handler for processing OAuth callbacks from providers.

- Parses query parameters (`code`, `state`, `error`)
- Validates state parameter (CSRF protection)
- Stores callback data in OAuthFlow instance
- Sends user-friendly HTML responses

### Port Management

**Automatic Port Detection:**
- Tries ports sequentially from 8080 to 8099
- Skips busy ports automatically
- Raises `OAuthPortError` if no ports available

**Example:**
```python
# Automatically finds available port
port = flow.find_available_port(start_port=8080, max_attempts=20)
# Returns first available port in range
```

## Usage Examples

### Basic OAuth Flow

```python
from src.auth.oauth_flow import OAuthFlow
from src.auth.providers.google import GoogleOAuthProvider
from src.auth.token_manager import TokenManager

# Initialize components
provider = GoogleOAuthProvider()
token_manager = TokenManager()
flow = OAuthFlow(provider, token_manager, account_name='work_account')

# Run complete flow
token_info = flow.run()
# Flow will:
# 1. Start local server
# 2. Generate auth URL
# 3. Open browser
# 4. Wait for callback
# 5. Exchange code for tokens
# 6. Save tokens
```

### Custom Port Configuration

```python
# Use specific port
flow = OAuthFlow(
    provider=provider,
    token_manager=token_manager,
    account_name='account',
    callback_port=9000
)

# Or let it auto-detect
flow = OAuthFlow(
    provider=provider,
    token_manager=token_manager,
    account_name='account',
    callback_port=None  # Auto-detect
)
```

### Manual Flow Control

```python
# Step-by-step control
flow.start_local_server()
auth_url = flow.get_authorization_url()
flow.open_browser(auth_url)
code, state = flow.wait_for_callback(timeout=120)
token_info = flow.exchange_tokens(code, state)
flow.save_tokens(token_info)
flow.stop_local_server()
```

## Error Handling

### OAuthPortError

Raised when no ports are available for callback server.

```python
try:
    flow.run()
except OAuthPortError as e:
    print(f"No ports available: {e}")
    # User should free a port or use manual code entry
```

### OAuthTimeoutError

Raised when callback is not received within timeout period.

```python
try:
    flow.run(timeout=60)  # 60 second timeout
except OAuthTimeoutError as e:
    print(f"Timeout waiting for callback: {e}")
```

### OAuthCallbackError

Raised when callback contains errors (user denied, invalid code, etc.).

```python
try:
    flow.run()
except OAuthCallbackError as e:
    print(f"Callback error: {e}")
```

### OAuthError

Generic OAuth error for other failures.

```python
try:
    flow.run()
except OAuthError as e:
    print(f"OAuth error: {e}")
```

## Security Features

### CSRF Protection

- Generates cryptographically secure state parameter using `secrets.token_urlsafe(32)`
- Validates state parameter on callback to prevent CSRF attacks
- Raises `ValueError` if state mismatch detected

### Secure Token Storage

- Tokens saved using TokenManager with file permissions 0600
- Atomic file writes (temp file + rename) for safety
- No tokens logged or exposed in error messages

### Input Validation

- Validates authorization code presence
- Validates state parameter matching
- Validates token response structure

## Integration Points

### With OAuth Providers

Works with any provider implementing `OAuthProvider` interface:
- `GoogleOAuthProvider` (Task 5)
- `MicrosoftOAuthProvider` (Task 6)

### With TokenManager

Integrates with `TokenManager` (Task 4) for:
- Token storage: `token_manager.save_tokens(account_name, tokens)`
- Token loading: `token_manager.load_tokens(account_name)`
- Token refresh: `token_manager.refresh_token(account_name, provider)`

### With CLI

Designed for integration with CLI `auth` command (Task 10):
```python
# In CLI command handler
flow = OAuthFlow(provider, token_manager, account_name)
token_info = flow.run()
```

## Configuration

### Environment Variables

OAuth providers require environment variables (set by provider):
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Microsoft: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`

### Redirect URI

Default redirect URI: `http://localhost:8080/callback`

Automatically updated based on detected callback port:
- If port 8080 is busy, uses next available port
- Redirect URI updated to match: `http://localhost:{port}/callback`

## Testing

Comprehensive test suite in `tests/test_oauth_flow.py`:

- **Initialization Tests**: Valid provider validation, custom port configuration
- **Port Management Tests**: Available port detection, busy port skipping, port conflict handling
- **Server Tests**: Server startup/shutdown, auto port detection
- **Authorization URL Tests**: URL generation, redirect URI updates, provider errors
- **Callback Tests**: Successful callbacks, missing parameters, OAuth errors, state validation
- **Token Exchange Tests**: Successful exchange, missing tokens, provider errors, state mismatch
- **Token Storage Tests**: Successful saving, error handling
- **Complete Flow Tests**: End-to-end flow, port errors, timeouts, cleanup on errors
- **Edge Cases**: Multiple busy ports, invalid state, expired codes

**Test Coverage:** 90%+ for `oauth_flow.py`

## Implementation Details

### Threading

- HTTP server runs in background thread (`ThreadingHTTPServer`)
- Non-blocking operation allows main thread to wait for callback
- Graceful shutdown on completion or error

### State Management

- State parameter stored in `OAuthFlow._state`
- Callback state validated against original state
- Prevents CSRF attacks

### Timeout Handling

- Default timeout: 120 seconds
- Configurable via `run(timeout=...)` parameter
- Raises `OAuthTimeoutError` if callback not received

### Browser Automation

- Uses `webbrowser.open()` to launch default browser
- Falls back gracefully if browser cannot be opened
- Prints authorization URL for manual access if needed

## References

- **OAuth 2.0 RFC 6749**: Authorization Code Flow
- **RFC 7636**: PKCE (Proof Key for Code Exchange)
- **RFC 6819**: OAuth 2.0 Security Best Practices
- **RFC 7628**: OAuth 2.0 SASL Mechanism (XOAUTH2)

## Related Documentation

- [V5 Authentication Interfaces](v5-auth-interfaces.md) - OAuth provider interfaces
- [V5 Token Manager](v5-token-manager.md) - Token storage and refresh
- [V5 Google OAuth Provider](v5-google-provider.md) - Google provider implementation
- [V5 Microsoft OAuth Provider](v5-microsoft-provider.md) - Microsoft provider implementation (Task 6)

## Task Completion

✅ **Task 7 Complete** - All subtasks implemented:
- ✅ 7.1: OAuthFlow class skeleton and local HTTP server
- ✅ 7.2: Port conflict resolution and automatic port fallback
- ✅ 7.3: Authorization URL generation and browser opening
- ✅ 7.4: Callback handling, state validation, and token exchange
- ✅ 7.5: TokenManager integration, user messaging, and error handling
- ✅ 7.6: Comprehensive testing for OAuth flow components
