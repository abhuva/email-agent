# V5 Token Manager

Token management system for OAuth 2.0 authentication tokens.

**Status:** ✅ Complete (Task 4)

## Overview

The `TokenManager` class provides secure storage, loading, and automatic refresh of OAuth 2.0 tokens for Google and Microsoft email accounts. It handles token expiry checking, automatic refresh, and maintains backward compatibility with V4 token formats.

## Features

- **Secure Token Storage**: JSON files in `credentials/` directory with restricted permissions (0600)
- **Automatic Token Refresh**: Automatically refreshes expired tokens using refresh tokens
- **Expiry Checking**: 5-minute buffer to account for clock skew
- **Atomic File Writes**: Uses temp files + rename for safe concurrent access
- **Token Validation**: Validates token structure before saving/loading
- **Backward Compatibility**: Handles V4 token formats gracefully
- **Provider Support**: Google and Microsoft OAuth 2.0 providers

## Usage

### Basic Usage

```python
from src.auth.token_manager import TokenManager
from datetime import datetime, timedelta

# Initialize TokenManager (defaults to 'credentials/' directory)
manager = TokenManager()

# Save tokens
tokens = {
    'access_token': 'your_access_token',
    'refresh_token': 'your_refresh_token',
    'expires_at': datetime.now() + timedelta(hours=1),
    'expires_in': 3600,
}
manager.save_tokens('my_account', tokens)

# Load tokens
loaded_tokens = manager.load_tokens('my_account')

# Get valid token (automatically refreshes if expired)
access_token = manager.get_valid_token('my_account', 'google')
```

### Custom Credentials Directory

```python
from pathlib import Path

# Use custom credentials directory
manager = TokenManager(credentials_dir=Path('/custom/path/credentials'))
```

### Token Refresh

```python
# Manually refresh tokens
refreshed_tokens = manager.refresh_token('my_account', 'google')
```

## API Reference

### TokenManager Class

#### `__init__(credentials_dir: Optional[Path] = None)`

Initialize TokenManager with credentials directory.

- **credentials_dir**: Path to credentials directory. Defaults to `credentials/` in project root.

#### `save_tokens(account_name: str, tokens: Dict[str, Any]) -> None`

Save OAuth tokens to a JSON file.

- **account_name**: Name of the account
- **tokens**: Dictionary containing token information (access_token, refresh_token, expires_at, etc.)
- **Raises**: `OSError`, `PermissionError`, `ValueError`

Creates credentials directory if missing, uses atomic file writes, and sets file permissions to 0600.

#### `load_tokens(account_name: str) -> Optional[Dict[str, Any]]`

Load OAuth tokens from a JSON file.

- **account_name**: Name of the account
- **Returns**: Dictionary containing token information, or None if file doesn't exist
- **Raises**: `PermissionError`, `json.JSONDecodeError`, `ValueError`

Deserializes datetime objects from ISO strings.

#### `refresh_token(account_name: str, provider: str) -> Dict[str, Any]`

Refresh OAuth access token using refresh token.

- **account_name**: Name of the account
- **provider**: OAuth provider name ('google' or 'microsoft')
- **Returns**: Dictionary containing refreshed token information
- **Raises**: `TokenRefreshError`

Implements OAuth 2.0 refresh token flow per RFC 6749. Requires environment variables:
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Microsoft: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`

#### `get_valid_token(account_name: str, provider: str) -> Optional[str]`

Get a valid access token, automatically refreshing if needed.

- **account_name**: Name of the account
- **provider**: OAuth provider name ('google' or 'microsoft')
- **Returns**: Access token string if available, None if refresh fails after retry

Main public method for obtaining access tokens. Includes retry logic and brief caching.

## Token Structure

### Required Fields

- `access_token` (str): OAuth 2.0 access token

### Optional Fields

- `refresh_token` (str): Refresh token for obtaining new access tokens
- `expires_at` (datetime): Token expiration timestamp
- `expires_in` (int): Seconds until token expiration

### Example Token Dictionary

```python
{
    'access_token': 'ya29.a0AfH6SMBx...',
    'refresh_token': '1//0gX...',
    'expires_at': datetime(2026, 1, 26, 12, 0, 0),
    'expires_in': 3600,
}
```

## Security Features

### File Permissions

- Credentials directory: 0700 (owner only)
- Token files: 0600 (read/write for owner only)

### Atomic Writes

Token files are written atomically using temp files + rename to prevent corruption during concurrent access.

### Token Validation

Token structure is validated before saving/loading to ensure required fields are present and have correct types.

### Environment Variables

Client IDs and secrets are loaded from environment variables, never hardcoded:
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` for Google
- `MS_CLIENT_ID`, `MS_CLIENT_SECRET` for Microsoft

## Expiry Checking

Tokens are checked for expiration with a 5-minute buffer to account for:
- Clock skew between systems
- Network latency
- Processing time

A token is considered expired if:
- `expires_at <= now + 5 minutes`, or
- `expires_in <= 5 minutes`, or
- No expiry information is available (conservative approach)

## Error Handling

### TokenRefreshError

Raised when token refresh fails:
- Invalid refresh token
- Network errors
- HTTP errors (4xx, 5xx)
- Missing credentials

### File I/O Errors

- `OSError`: Directory creation or file write failures
- `PermissionError`: File permission issues
- `json.JSONDecodeError`: Invalid JSON in token files

## Backward Compatibility

The TokenManager handles V4 token formats gracefully:
- Allows tokens without `access_token` when `strict=False`
- Preserves existing token structure during refresh
- Logs warnings for V4 format tokens

## Testing

Comprehensive test suite with 39 tests covering:
- Token saving and loading
- Expiry checking with various scenarios
- Token refresh (success and failure cases)
- Automatic refresh in `get_valid_token`
- File permissions and error handling
- Token validation
- Path sanitization

Run tests:
```bash
pytest tests/test_token_manager.py -v
```

## Implementation Details

### Token Serialization

- Datetime objects are serialized to ISO format strings for JSON storage
- ISO strings are deserialized back to datetime objects when loading

### Provider Configuration

Token endpoints:
- Google: `https://oauth2.googleapis.com/token`
- Microsoft: `https://login.microsoftonline.com/common/oauth2/v2.0/token`

### Caching

Valid tokens are cached briefly (5 minutes TTL) to avoid unnecessary file I/O and refresh operations.

## References

- RFC 6749: OAuth 2.0 Authorization Framework
- RFC 6819: OAuth 2.0 Security Best Current Practice
- [V5 Authentication Interfaces](v5-auth-interfaces.md) - Authentication protocols and OAuth providers

## Related Documentation

- [V5 Authentication Interfaces](v5-auth-interfaces.md) - Authentication protocols and OAuth providers
- [V4 Configuration System](v4-configuration.md) - Configuration system for OAuth settings
