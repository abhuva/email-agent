# V5 Authentication Interfaces

**Task:** 2  
**Status:** ✅ Complete  
**Version:** 1.0.0

## Overview

The authentication interfaces module (`src/auth/interfaces.py`) defines the core protocols, base classes, and utilities for implementing authentication strategies in the email agent. It supports both traditional password-based authentication and OAuth 2.0 authentication via the Strategy pattern.

This module provides:
- **AuthenticatorProtocol**: Protocol interface for all authentication strategies
- **OAuthProvider**: Abstract base class for OAuth 2.0 providers
- **Token Management Utilities**: Functions for token validation, parsing, and security
- **XOAUTH2 SASL Utilities**: IMAP XOAUTH2 authentication string generation per RFC 7628
- **Error Handling**: Custom exceptions for authentication and token errors

## Architecture

The authentication system uses the Strategy pattern to decouple authentication logic from IMAP client code:

```
IMAPClient
    ↓
AuthenticatorProtocol (interface)
    ↓
    ├── PasswordAuthenticator (concrete)
    └── OAuthAuthenticator (concrete)
            ↓
        OAuthProvider (abstract)
            ↓
        ├── GoogleOAuthProvider
        └── MicrosoftOAuthProvider
```

## Core Interfaces

### AuthenticatorProtocol

Protocol defining the interface for all authentication strategies.

```python
class AuthenticatorProtocol(Protocol):
    def authenticate(self, imap_connection: imaplib.IMAP4_SSL) -> bool:
        """Authenticate with the IMAP server."""
```

**Usage:**
- Implemented by `PasswordAuthenticator` and `OAuthAuthenticator`
- Used by `IMAPClient` to perform authentication
- Supports both password and OAuth 2.0 XOAUTH2 authentication

**References:**
- RFC 3501: IMAP4 Protocol
- RFC 7628: OAuth 2.0 SASL Mechanism (XOAUTH2)
- RFC 6749: OAuth 2.0 Authorization Framework

### OAuthProvider

Abstract base class for OAuth 2.0 providers implementing the Authorization Code Flow.

```python
class OAuthProvider(ABC):
    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """Generate OAuth 2.0 authorization URL."""
    
    @abstractmethod
    def handle_callback(self, code: str, state: str) -> TokenInfo:
        """Handle OAuth callback and exchange code for tokens."""
    
    @abstractmethod
    def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
        """Refresh an expired access token."""
    
    def validate_token(self, token_info: TokenInfo) -> bool:
        """Check if token is valid (not expired) with 5-minute buffer."""
```

**Security Best Practices:**
- Always validate state parameter to prevent CSRF attacks
- Use PKCE (Proof Key for Code Exchange) for public clients when supported
- Implement secure token storage and refresh mechanisms
- Use HTTPS for all OAuth endpoints

**References:**
- RFC 6749: OAuth 2.0 Authorization Framework
- RFC 7636: Proof Key for Code Exchange (PKCE)
- RFC 6819: OAuth 2.0 Security Best Current Practice

## Type Definitions

### TokenInfo

OAuth 2.0 token information structure.

```python
class TokenInfo(TypedDict):
    access_token: str
    expires_at: Optional[datetime]
    refresh_token: Optional[str]
```

**Fields:**
- `access_token`: The OAuth 2.0 access token string
- `expires_at`: Optional expiration timestamp (datetime object)
- `refresh_token`: Optional refresh token for obtaining new access tokens

### OAuthConfig

OAuth 2.0 configuration structure.

```python
class OAuthConfig(TypedDict):
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    auth_url: str
    token_url: str
```

**Fields:**
- `client_id`: OAuth 2.0 client identifier
- `client_secret`: OAuth 2.0 client secret
- `redirect_uri`: OAuth 2.0 redirect URI for authorization callback
- `scopes`: List of OAuth 2.0 scopes to request
- `auth_url`: OAuth 2.0 authorization endpoint URL
- `token_url`: OAuth 2.0 token endpoint URL

## Token Management Utilities

### is_token_valid()

Check if OAuth token is valid (not expired) with configurable clock skew.

```python
def is_token_valid(token_info: TokenInfo, clock_skew: int = 300) -> bool:
    """Check if token is valid with 5-minute buffer by default."""
```

**Parameters:**
- `token_info`: Token information to validate
- `clock_skew`: Buffer time in seconds before expiration (default: 300 = 5 minutes)

**Returns:**
- `True` if token is valid, `False` if expired or missing expiration info

**Usage:**
```python
token_info: TokenInfo = {
    'access_token': 'token',
    'expires_at': datetime.now() + timedelta(hours=1),
    'refresh_token': 'refresh'
}

if is_token_valid(token_info):
    # Token is valid, use it
    pass
else:
    # Token expired, refresh it
    pass
```

### parse_token_response()

Safely parse OAuth 2.0 token response and convert to TokenInfo.

```python
def parse_token_response(response: dict) -> TokenInfo:
    """Parse OAuth token response with validation."""
```

**Parameters:**
- `response`: Raw token response dictionary from OAuth provider

**Returns:**
- `TokenInfo` dictionary with standardized structure

**Raises:**
- `TokenError`: If response is missing required fields or contains error

**Usage:**
```python
response = {
    'access_token': 'token123',
    'refresh_token': 'refresh123',
    'expires_in': 3600
}

token_info = parse_token_response(response)
```

## Security Utilities

### generate_state()

Generate cryptographically secure state parameter for OAuth 2.0.

```python
def generate_state() -> str:
    """Generate URL-safe random string for OAuth state parameter."""
```

**Returns:**
- URL-safe random string suitable for OAuth state parameter

**Purpose:**
- Prevents CSRF attacks by ensuring authorization callback corresponds to original request

**Usage:**
```python
state = generate_state()
auth_url = provider.get_auth_url(state)
# Store state for validation in callback
```

### generate_pkce_challenge()

Generate PKCE (Proof Key for Code Exchange) challenge and verifier.

```python
def generate_pkce_challenge() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) tuple."""
```

**Returns:**
- Tuple of `(code_verifier, code_challenge)` where:
  - `code_verifier`: Random string (43-128 characters)
  - `code_challenge`: Base64URL-encoded SHA256 hash of verifier

**References:**
- RFC 7636: Proof Key for Code Exchange by OAuth Public Clients

**Usage:**
```python
verifier, challenge = generate_pkce_challenge()
# Use challenge in authorization URL
# Use verifier in token exchange
```

## XOAUTH2 SASL Utilities

### generate_xoauth2_sasl()

Generate XOAUTH2 SASL string for IMAP authentication per RFC 7628.

```python
def generate_xoauth2_sasl(user: str, access_token: str) -> bytes:
    """Generate base64-encoded XOAUTH2 SASL string."""
```

**Parameters:**
- `user`: Email address or username
- `access_token`: OAuth 2.0 access token

**Returns:**
- Base64-encoded SASL string ready for IMAP `authenticate()` call

**Format:**
The SASL string format is: `base64('user=' + user + '^Aauth=Bearer ' + token + '^A^A')`
where `^A` represents the ASCII control character 0x01.

**References:**
- RFC 7628: OAuth 2.0 SASL Mechanism

**Usage:**
```python
sasl_string = generate_xoauth2_sasl('user@example.com', 'token123')
imap.authenticate('XOAUTH2', sasl_string)
```

### validate_sasl_components()

Validate user and token for XOAUTH2 SASL string generation.

```python
def validate_sasl_components(user: str, token: str) -> None:
    """Validate user and token inputs."""
```

**Parameters:**
- `user`: Email address or username to validate
- `token`: Access token to validate

**Raises:**
- `ValueError`: If user or token is empty or contains invalid characters

**Usage:**
```python
try:
    validate_sasl_components('user@example.com', 'token123')
    sasl = generate_xoauth2_sasl('user@example.com', 'token123')
except ValueError as e:
    # Handle validation error
    pass
```

## Error Handling

### Custom Exceptions

The module defines several custom exceptions for authentication and token errors:

```python
class TokenError(Exception):
    """Base exception for token-related errors."""

class OAuthError(TokenError):
    """Exception raised for OAuth 2.0 flow errors."""

class AuthExpiredError(TokenError):
    """Exception raised when authentication token has expired."""

class AuthenticationError(Exception):
    """Exception raised when IMAP authentication fails."""
```

**Exception Hierarchy:**
```
Exception
├── TokenError
│   ├── OAuthError
│   └── AuthExpiredError
└── AuthenticationError
```

**Usage:**
```python
try:
    token_info = provider.handle_callback(code, state)
except OAuthError as e:
    # Handle OAuth flow error
    pass
except TokenError as e:
    # Handle token error
    pass
```

## V4 Compatibility

### is_v4_compatible()

Check if OAuth provider is compatible with V4 configuration system.

```python
def is_v4_compatible(provider: OAuthProvider) -> bool:
    """Check if provider is compatible with V4."""
```

**Returns:**
- `True` if provider is compatible with V4, `False` otherwise

**Note:**
- All providers implementing `OAuthProvider` should be V4 compatible

## Module Exports

The module exports the following public API:

```python
__all__ = [
    'AuthenticatorProtocol',
    'TokenInfo',
    'OAuthConfig',
    'OAuthProvider',
    'TokenError',
    'OAuthError',
    'AuthExpiredError',
    'AuthenticationError',
    'is_token_valid',
    'parse_token_response',
    'generate_state',
    'generate_pkce_challenge',
    'generate_xoauth2_sasl',
    'validate_sasl_components',
    'is_v4_compatible',
    'ProviderFactory',
]
```

## Testing

Comprehensive test suite in `tests/test_auth_interfaces.py` covering:

- Protocol compliance
- Type definitions (TokenInfo, OAuthConfig)
- OAuthProvider abstract base class
- Token management utilities
- Security utilities (state, PKCE)
- XOAUTH2 SASL utilities
- Error handling
- V4 compatibility
- Docstring coverage

**Run tests:**
```bash
pytest tests/test_auth_interfaces.py -v
```

**Test Coverage:**
- 38 tests covering all interfaces and utilities
- 100% coverage of public API
- Edge cases and error conditions tested

## Integration Points

### With IMAP Client

The `AuthenticatorProtocol` is used by `IMAPClient` to perform authentication:

```python
# In IMAPClient.connect()
authenticator.authenticate(self.server)
```

### With OAuth Providers

Concrete OAuth providers (Google, Microsoft) implement `OAuthProvider`:

```python
class GoogleOAuthProvider(OAuthProvider):
    def get_auth_url(self, state: str) -> str:
        # Google-specific implementation
        pass
    
    def handle_callback(self, code: str, state: str) -> TokenInfo:
        # Google-specific implementation
        pass
    
    def refresh_token(self, token_info: TokenInfo) -> TokenInfo:
        # Google-specific implementation
        pass
```

### With Token Manager

Token management utilities are used by `TokenManager` for token validation and parsing:

```python
# In TokenManager
if is_token_valid(token_info):
    return token_info['access_token']
else:
    return self.refresh_token(account_name, provider)
```

## Configuration

No configuration required. The interfaces module is a pure Python module with no external dependencies beyond the standard library and `imaplib`.

## References

- **RFC 3501**: IMAP4 Protocol
- **RFC 6749**: OAuth 2.0 Authorization Framework
- **RFC 6819**: OAuth 2.0 Security Best Current Practice
- **RFC 7628**: OAuth 2.0 SASL Mechanism (XOAUTH2)
- **RFC 7636**: Proof Key for Code Exchange (PKCE)

## Related Documentation

- [V5 OAuth Integration PDD](../pdd_V5.md) - Product Design Document for OAuth integration
- [V5 Configuration Schema](v5-configuration-schema.md) - OAuth configuration schema (Task 3)
- [V5 Token Manager](v5-token-manager.md) - Token storage and refresh (Task 4)
- [V5 OAuth Providers](v5-oauth-providers.md) - Google and Microsoft providers (Tasks 5-6)
- [V5 OAuth Flow](v5-oauth-flow.md) - Interactive OAuth flow (Task 7)
- [V5 Authentication Strategies](v5-auth-strategies.md) - Password and OAuth authenticators (Task 8)
