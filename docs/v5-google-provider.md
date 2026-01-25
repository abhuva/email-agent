# V5 Google OAuth Provider

**Task:** 5  
**Status:** ✅ Complete  
**Version:** 1.0.0

## Overview

The Google OAuth provider (`src/auth/providers/google.py`) implements OAuth 2.0 authentication for Google accounts, specifically configured for Gmail IMAP access. It uses the `google-auth-oauthlib` library to handle the OAuth 2.0 Authorization Code Flow with offline access for refresh tokens.

This provider enables secure authentication to Gmail IMAP servers without requiring app-specific passwords, which Google is deprecating in favor of OAuth 2.0.

## Architecture

The `GoogleOAuthProvider` implements the `OAuthProvider` abstract base class from `src/auth/interfaces.py`:

```
OAuthProvider (ABC)
    ↓
GoogleOAuthProvider (concrete)
    ↓
google-auth-oauthlib.Flow
    ↓
Google OAuth 2.0 API
```

## Features

- **Authorization Code Flow**: Implements OAuth 2.0 Authorization Code Flow with offline access
- **Token Refresh**: Automatic token refresh using refresh tokens
- **Gmail IMAP Scopes**: Pre-configured with required scopes for Gmail IMAP access
- **State Validation**: CSRF protection via state parameter validation
- **Error Handling**: Comprehensive error handling with informative messages
- **Environment Variable Support**: Loads credentials from environment variables

## Configuration

### Environment Variables

The provider requires the following environment variables:

```bash
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

These should be set in your `.env` file or system environment variables.

### Google Cloud Console Setup

1. **Create OAuth 2.0 Credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" or "Web application" as application type
   - Set authorized redirect URI: `http://localhost:8080/callback`

2. **Configure OAuth Consent Screen:**
   - Go to "APIs & Services" > "OAuth consent screen"
   - Fill in app name, support email, and developer contact
   - Add scopes: `https://mail.google.com/`, `openid`, `email`, `profile`
   - Save and continue

3. **Download Credentials:**
   - Copy the Client ID and Client Secret
   - Add them to your `.env` file

## Usage

### Basic Usage

```python
from src.auth.providers.google import GoogleOAuthProvider

# Initialize provider (loads credentials from environment)
provider = GoogleOAuthProvider()

# Generate authorization URL
from src.auth.interfaces import generate_state
state = generate_state()
auth_url = provider.get_auth_url(state)

# User visits auth_url and authorizes the app
# After authorization, handle the callback
code = "authorization_code_from_callback"
token_info = provider.handle_callback(code, state)

# Use token_info to authenticate with IMAP
access_token = token_info['access_token']
```

### Custom Configuration

```python
# Initialize with explicit credentials
provider = GoogleOAuthProvider(
    client_id='your-client-id',
    client_secret='your-client-secret',
    redirect_uri='http://localhost:9000/callback',
    scopes=['https://mail.google.com/', 'custom_scope']
)
```

### Token Refresh

```python
from datetime import datetime, timedelta

# Token info from initial authorization
token_info = {
    'access_token': 'current_token',
    'refresh_token': 'refresh_token',
    'expires_at': datetime.now() + timedelta(hours=1)
}

# Refresh expired token
refreshed_token = provider.refresh_token(token_info)
new_access_token = refreshed_token['access_token']
```

## API Reference

### GoogleOAuthProvider

#### `__init__(client_id=None, client_secret=None, redirect_uri=None, scopes=None)`

Initialize Google OAuth provider.

**Parameters:**
- `client_id` (str, optional): OAuth 2.0 client ID. If None, loaded from `GOOGLE_CLIENT_ID` env var.
- `client_secret` (str, optional): OAuth 2.0 client secret. If None, loaded from `GOOGLE_CLIENT_SECRET` env var.
- `redirect_uri` (str, optional): OAuth redirect URI. Defaults to `http://localhost:8080/callback`.
- `scopes` (list[str], optional): List of OAuth scopes. Defaults to Gmail IMAP scopes.

**Raises:**
- `GoogleOAuthError`: If required credentials are missing

**Default Scopes:**
- `https://mail.google.com/` - Gmail IMAP access
- `openid` - OpenID Connect
- `email` - User email
- `profile` - User profile

#### `get_auth_url(state: str) -> str`

Generate Google OAuth 2.0 authorization URL.

**Parameters:**
- `state` (str): Cryptographically secure state parameter for CSRF protection

**Returns:**
- `str`: Complete authorization URL with all required parameters

**Raises:**
- `GoogleOAuthError`: If URL generation fails

**Example:**
```python
from src.auth.interfaces import generate_state

state = generate_state()
auth_url = provider.get_auth_url(state)
# User visits auth_url in browser
```

#### `handle_callback(code: str, state: str) -> TokenInfo`

Handle OAuth 2.0 authorization callback and exchange code for tokens.

**Parameters:**
- `code` (str): Authorization code received from Google
- `state` (str): State parameter that must match the one used in `get_auth_url()`

**Returns:**
- `TokenInfo`: Dictionary containing `access_token`, `refresh_token`, and `expires_at`

**Raises:**
- `GoogleOAuthError`: If code exchange fails
- `ValueError`: If state parameter doesn't match (CSRF protection)

**Example:**
```python
# After user authorizes and callback is received
token_info = provider.handle_callback(auth_code, stored_state)
access_token = token_info['access_token']
```

#### `refresh_token(token_info: TokenInfo) -> TokenInfo`

Refresh an expired access token using refresh token.

**Parameters:**
- `token_info` (TokenInfo): Current token information containing `refresh_token`

**Returns:**
- `TokenInfo`: Updated token information with new `access_token` and `expires_at`

**Raises:**
- `AuthExpiredError`: If refresh token is invalid or expired
- `GoogleOAuthError`: If token refresh fails

**Example:**
```python
# Token is expired, refresh it
refreshed = provider.refresh_token(token_info)
new_token = refreshed['access_token']
```

#### `exchange_code_for_tokens(code: str, state: str) -> TokenInfo`

Alias for `handle_callback()` for backward compatibility.

**Parameters:**
- `code` (str): Authorization code
- `state` (str): State parameter

**Returns:**
- `TokenInfo`: Token information

## Error Handling

### GoogleOAuthError

Custom exception for Google OAuth-specific errors.

```python
from src.auth.providers.google import GoogleOAuthError

try:
    provider = GoogleOAuthProvider()
except GoogleOAuthError as e:
    print(f"OAuth error: {e}")
```

### Common Error Scenarios

1. **Missing Credentials:**
   ```
   GoogleOAuthError: GOOGLE_CLIENT_ID environment variable is required.
   ```
   **Solution:** Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` file.

2. **State Mismatch:**
   ```
   ValueError: State parameter mismatch - possible CSRF attack
   ```
   **Solution:** Ensure the state parameter matches between `get_auth_url()` and `handle_callback()`.

3. **Invalid Refresh Token:**
   ```
   AuthExpiredError: Refresh token is invalid or expired
   ```
   **Solution:** User needs to re-authenticate. The refresh token may have been revoked.

4. **Token Exchange Failure:**
   ```
   GoogleOAuthError: Failed to exchange authorization code for tokens
   ```
   **Solution:** Check that the authorization code is valid and hasn't expired (codes expire quickly).

## Security Considerations

1. **State Parameter:** Always use a cryptographically secure state parameter to prevent CSRF attacks. Use `generate_state()` from `src/auth/interfaces`.

2. **Offline Access:** The provider requests `access_type='offline'` to ensure refresh tokens are provided. Without this, tokens expire after 1 hour with no refresh capability.

3. **Token Storage:** Store tokens securely using `TokenManager` which sets file permissions to 0600 (owner-only read/write).

4. **HTTPS:** Always use HTTPS for production redirect URIs. The default `http://localhost:8080/callback` is acceptable for local development.

5. **Client Secret:** Never expose the client secret in code or logs. Always use environment variables.

## Integration with TokenManager

The provider works seamlessly with `TokenManager` for token storage and automatic refresh:

```python
from src.auth.token_manager import TokenManager
from src.auth.providers.google import GoogleOAuthProvider

# Initialize components
token_manager = TokenManager()
provider = GoogleOAuthProvider()

# Get authorization URL
state = generate_state()
auth_url = provider.get_auth_url(state)

# After user authorizes
token_info = provider.handle_callback(code, state)

# Save tokens
token_manager.save_tokens('gmail_account', {
    'access_token': token_info['access_token'],
    'refresh_token': token_info['refresh_token'],
    'expires_at': token_info['expires_at'],
    'provider': 'google',
})

# Later, get valid token (automatically refreshes if needed)
access_token = token_manager.get_valid_token('gmail_account', 'google')
```

## Testing

Comprehensive unit tests are available in `tests/test_google_provider.py`.

**Run tests:**
```bash
pytest tests/test_google_provider.py -v
```

**Test Coverage:**
- 28 tests covering all provider functionality
- Initialization and configuration
- Authorization URL generation
- Callback handling and token exchange
- Token refresh
- Error handling
- Interface compliance
- Integration tests

## Implementation Details

### OAuth 2.0 Flow

1. **Authorization Request:**
   - User visits authorization URL generated by `get_auth_url()`
   - Google prompts user to authorize the application
   - User grants permissions

2. **Authorization Callback:**
   - Google redirects to `redirect_uri` with authorization code
   - Application calls `handle_callback()` with code and state
   - Provider exchanges code for access and refresh tokens

3. **Token Refresh:**
   - When access token expires, call `refresh_token()`
   - Provider uses refresh token to obtain new access token
   - New tokens are returned for storage

### Google-Specific Configuration

- **Authorization Endpoint:** `https://accounts.google.com/o/oauth2/v2/auth`
- **Token Endpoint:** `https://oauth2.googleapis.com/token`
- **Required Scopes:** `https://mail.google.com/` for Gmail IMAP access
- **Access Type:** `offline` (required for refresh tokens)
- **Prompt:** `consent` (ensures refresh token is provided)

## References

- **Google OAuth 2.0 Documentation:** https://developers.google.com/identity/protocols/oauth2
- **Gmail API Scopes:** https://developers.google.com/gmail/api/auth/scopes
- **google-auth-oauthlib:** https://google-auth-oauthlib.readthedocs.io/
- **RFC 6749:** OAuth 2.0 Authorization Framework
- **RFC 6819:** OAuth 2.0 Security Best Current Practice

## Related Documentation

- [V5 Authentication Interfaces](v5-auth-interfaces.md) - Core authentication protocols and interfaces
- [V5 Token Manager](v5-token-manager.md) - Token storage and automatic refresh
- [V5 OAuth Flow](v5-oauth-flow.md) - Interactive OAuth flow for CLI
- [V5 Configuration Schema](v4-config-schema-reference.md#7-authentication-configuration-auth) - OAuth configuration in account configs
- [V5 OAuth Integration PDD](../pdd_v5.md) - Product Design Document for OAuth integration
