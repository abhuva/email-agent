# V5 Authentication Strategies

**Task:** 8  
**Status:** ✅ Complete  
**Version:** 1.0.0

## Overview

The authentication strategies module (`src/auth/strategies.py`) implements concrete authenticator classes for password-based and OAuth 2.0 authentication methods, following the Strategy pattern. These authenticators provide a pluggable authentication system that can be used by the IMAP client to authenticate with email servers.

This module provides:
- **PasswordAuthenticator**: Traditional username/password authentication
- **OAuthAuthenticator**: OAuth 2.0 XOAUTH2 SASL authentication
- **Error Handling**: Comprehensive error handling with security best practices
- **Protocol Compliance**: Both classes conform to `AuthenticatorProtocol`

## Architecture

The authentication strategies follow the Strategy pattern, allowing the IMAP client to use different authentication methods without being tightly coupled to specific implementations:

```
IMAPClient
    ↓
AuthenticatorProtocol (interface)
    ↓
    ├── PasswordAuthenticator (concrete)
    └── OAuthAuthenticator (concrete)
            ↓
        TokenManager (token storage & refresh)
```

## PasswordAuthenticator

### Overview

The `PasswordAuthenticator` class implements traditional username/password authentication using the IMAP LOGIN command (RFC 3501). Credentials are loaded from environment variables for security.

### Initialization

```python
from src.auth.strategies import PasswordAuthenticator

# Password is loaded from environment variable
authenticator = PasswordAuthenticator(
    email='user@example.com',
    password_env='IMAP_PASSWORD'  # Name of environment variable
)
```

**Parameters:**
- `email`: Email address for authentication (required)
- `password_env`: Name of environment variable containing the password (required)

**Raises:**
- `ValueError`: If email is empty, password_env is empty, or password environment variable is not set

**Security:**
- Passwords are never exposed in error messages
- Passwords are loaded from environment variables (not hardcoded)
- Uses SSL/TLS encryption via `IMAP4_SSL` for secure credential transmission

### Authentication

```python
import imaplib

imap_conn = imaplib.IMAP4_SSL('imap.example.com', 993)
result = authenticator.authenticate(imap_conn)
# Returns True if authentication succeeds
```

**Method Signature:**
```python
def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
    """Authenticate with IMAP server using username and password."""
```

**Returns:**
- `True` if authentication succeeds

**Raises:**
- `AuthenticationError`: If authentication fails (invalid credentials, etc.)

**Error Handling:**
- Catches `imaplib.IMAP4.error` and maps to `AuthenticationError`
- Never exposes passwords in error messages
- Provides user-friendly error messages

### Example Usage

```python
import os
import imaplib
from src.auth.strategies import PasswordAuthenticator

# Set password in environment
os.environ['IMAP_PASSWORD'] = 'your_password_here'

# Create authenticator
authenticator = PasswordAuthenticator('user@example.com', 'IMAP_PASSWORD')

# Connect and authenticate
imap_conn = imaplib.IMAP4_SSL('imap.example.com', 993)
try:
    authenticator.authenticate(imap_conn)
    print("Authentication successful!")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

## OAuthAuthenticator

### Overview

The `OAuthAuthenticator` class implements OAuth 2.0 XOAUTH2 SASL authentication (RFC 7628) for IMAP servers. It uses `TokenManager` to retrieve and refresh access tokens automatically.

### Initialization

```python
from src.auth.strategies import OAuthAuthenticator
from src.auth.token_manager import TokenManager

token_manager = TokenManager()
authenticator = OAuthAuthenticator(
    email='user@example.com',
    account_name='my-account',
    provider_name='google',  # or 'microsoft'
    token_manager=token_manager
)
```

**Parameters:**
- `email`: Email address for authentication (required)
- `account_name`: Account name used for token storage/retrieval (required)
- `provider_name`: OAuth provider name - 'google' or 'microsoft' (required, case-insensitive)
- `token_manager`: `TokenManager` instance for token operations (required)

**Raises:**
- `ValueError`: If any required parameter is empty, invalid, or None

**Provider Name Normalization:**
- Provider names are automatically normalized to lowercase
- Only 'google' and 'microsoft' are supported

### Authentication

```python
import imaplib

imap_conn = imaplib.IMAP4_SSL('imap.gmail.com', 993)
result = authenticator.authenticate(imap_conn)
# Returns True if authentication succeeds
```

**Method Signature:**
```python
def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
    """Authenticate with IMAP server using OAuth 2.0 XOAUTH2."""
```

**Process:**
1. Retrieves a valid access token from `TokenManager` (automatically refreshes if expired)
2. Generates XOAUTH2 SASL string per RFC 7628
3. Calls IMAP `authenticate()` command with 'XOAUTH2' mechanism

**SASL String Format:**
The SASL string format is: `base64('user=' + email + '^Aauth=Bearer ' + token + '^A^A')`
where `^A` represents the ASCII control character 0x01.

**Returns:**
- `True` if authentication succeeds

**Raises:**
- `AuthenticationError`: If IMAP authentication fails
- `TokenError`: If token retrieval or refresh fails

**Error Handling:**
- Catches `imaplib.IMAP4.error` and maps to `AuthenticationError`
- Never exposes tokens in error messages
- Provides user-friendly error messages with suggestions (e.g., "run 'auth' command")
- Automatically handles token refresh when tokens are expired

### Token Management

The `OAuthAuthenticator` integrates with `TokenManager` to handle token lifecycle:

- **Token Retrieval**: `TokenManager.get_valid_token()` is called to get a valid access token
- **Automatic Refresh**: If the token is expired or near expiration, `TokenManager` automatically refreshes it
- **Error Handling**: If token refresh fails, a `TokenError` is raised with helpful error messages

### Example Usage

```python
import imaplib
from src.auth.strategies import OAuthAuthenticator
from src.auth.token_manager import TokenManager

# Initialize token manager
token_manager = TokenManager()

# Create authenticator
authenticator = OAuthAuthenticator(
    email='user@gmail.com',
    account_name='my-gmail-account',
    provider_name='google',
    token_manager=token_manager
)

# Connect and authenticate
imap_conn = imaplib.IMAP4_SSL('imap.gmail.com', 993)
try:
    authenticator.authenticate(imap_conn)
    print("OAuth authentication successful!")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except TokenError as e:
    print(f"Token error: {e}")
    print("Please run 'auth' command to authenticate.")
```

## Error Handling

### AuthenticationError

Raised when IMAP authentication fails for any reason.

**Password Authentication:**
- Error messages never expose passwords
- Provides generic error messages like "Authentication failed. Please check your credentials."

**OAuth Authentication:**
- Error messages never expose tokens
- Provides helpful suggestions like "Please run 'auth' command to re-authenticate."
- Distinguishes between token errors and IMAP errors

### TokenError

Raised when token retrieval or refresh fails.

**Common Scenarios:**
- No tokens found for account
- Token refresh failed (invalid refresh token, network error, etc.)
- Missing environment variables for token refresh

**Error Messages:**
- Always user-friendly and actionable
- Suggests running 'auth' command when appropriate

## Security Best Practices

### Password Security

1. **Environment Variables**: Passwords are always loaded from environment variables, never hardcoded
2. **Error Messages**: Passwords are never exposed in error messages or logs
3. **SSL/TLS**: Uses `IMAP4_SSL` for encrypted credential transmission

### OAuth Security

1. **Token Storage**: Tokens are stored securely by `TokenManager` with restricted file permissions (0600)
2. **Token Refresh**: Automatic token refresh prevents expired token errors
3. **Error Messages**: Tokens are never exposed in error messages or logs
4. **SASL Format**: XOAUTH2 SASL strings are generated per RFC 7628 specification

## Protocol Compliance

Both `PasswordAuthenticator` and `OAuthAuthenticator` conform to the `AuthenticatorProtocol` interface:

```python
from src.auth.interfaces import AuthenticatorProtocol

# Both classes can be used as AuthenticatorProtocol
authenticator: AuthenticatorProtocol = PasswordAuthenticator(...)
# or
authenticator: AuthenticatorProtocol = OAuthAuthenticator(...)
```

This allows the IMAP client to use either authenticator interchangeably without being tightly coupled to specific implementations.

## Testing

Comprehensive unit tests are provided in `tests/test_auth_strategies.py`:

- **PasswordAuthenticator Tests**: Initialization, authentication success/failure, error handling, security
- **OAuthAuthenticator Tests**: Initialization, authentication success/failure, token refresh, error handling, security
- **Security Tests**: Verifies passwords and tokens are never exposed in error messages
- **Integration Tests**: Tests with real `TokenManager` instances

**Test Coverage:**
- 27 tests covering all major scenarios
- 100% code coverage for both authenticator classes
- Security-focused tests for credential protection

## Integration with IMAP Client

The authenticators are designed to be used by the IMAP client (Task 9):

```python
from src.auth.strategies import PasswordAuthenticator, OAuthAuthenticator
from src.imap_client import ImapClient

# Password authentication
password_auth = PasswordAuthenticator('user@example.com', 'PASSWORD_ENV')
client = ImapClient(authenticator=password_auth)

# OAuth authentication
oauth_auth = OAuthAuthenticator(
    email='user@example.com',
    account_name='my-account',
    provider_name='google',
    token_manager=token_manager
)
client = ImapClient(authenticator=oauth_auth)
```

## References

- **RFC 3501**: IMAP4 Protocol
- **RFC 7628**: OAuth 2.0 SASL Mechanism (XOAUTH2)
- **RFC 6749**: OAuth 2.0 Authorization Framework
- **V5 Authentication Interfaces**: See [v5-auth-interfaces.md](v5-auth-interfaces.md)
- **V5 Token Manager**: See [v5-token-manager.md](v5-token-manager.md)

## Related Tasks

- **Task 2**: Authentication interfaces and base classes
- **Task 4**: Token management system
- **Task 5**: Google OAuth provider
- **Task 6**: Microsoft OAuth provider
- **Task 9**: Refactor IMAP client to use authenticator strategy
