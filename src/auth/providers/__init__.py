"""OAuth provider implementations."""

from src.auth.providers.google import GoogleOAuthProvider, GoogleOAuthError
from src.auth.providers.microsoft import MicrosoftOAuthProvider, MicrosoftOAuthError

__all__ = [
    'GoogleOAuthProvider',
    'GoogleOAuthError',
    'MicrosoftOAuthProvider',
    'MicrosoftOAuthError',
]
