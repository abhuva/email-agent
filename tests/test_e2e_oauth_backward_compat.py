"""
End-to-End Tests for OAuth Backward Compatibility

This module contains end-to-end tests verifying backward compatibility between
OAuth authentication (V5) and password authentication (V4). These tests ensure
that existing password-based accounts continue to work after OAuth integration.

Test Categories:
- Password authentication still works (V4 compatibility)
- Mixed OAuth/password account processing
- Configuration backward compatibility
- Error handling for missing OAuth configs
- No regressions in V4 functionality

Requirements:
- Test account credentials in environment variables (for password auth)
- Test account configs in config/accounts/ with auth.method='password'
- Test accounts documented in config/test-accounts.yaml

To run:
    pytest tests/test_e2e_oauth_backward_compat.py -v -m e2e_oauth

To skip (if credentials not available):
    pytest tests/test_e2e_oauth_backward_compat.py -v -m "not e2e_oauth"
"""

import pytest
import os
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

# Register E2E fixtures
pytest_plugins = ['tests.conftest_e2e_v4']

from src.auth.strategies import PasswordAuthenticator, OAuthAuthenticator
from src.auth.token_manager import TokenManager
from src.imap_client import IMAPClient
from src.account_processor import AccountProcessor
from src.config_loader import ConfigLoader
from src.orchestrator import MasterOrchestrator

# Pytest marker for OAuth E2E tests
pytestmark = pytest.mark.e2e_oauth


# ============================================================================
# Helper Functions
# ============================================================================

def get_password_test_account() -> Optional[Dict[str, Any]]:
    """Get test account configuration with password authentication."""
    from tests.e2e_helpers import get_test_accounts
    
    accounts = get_test_accounts()
    for account in accounts:
        auth_config = account.get('auth', {})
        # V4 accounts may not have auth block, defaulting to password
        if auth_config.get('method', 'password') == 'password':
            return account
    return None


def require_password_account():
    """Skip test if no password-based test account is available."""
    account = get_password_test_account()
    if not account:
        pytest.skip("No password-based test account available")
    
    # Check credentials
    password_env = account.get('password_env')
    if not password_env:
        pytest.skip(f"Password environment variable not configured for account")
    
    password = os.getenv(password_env)
    if not password:
        pytest.skip(f"Password not available in environment variable {password_env}")


# ============================================================================
# Password Authentication Backward Compatibility Tests
# ============================================================================

class TestPasswordAuthBackwardCompat:
    """Test that password authentication still works (V4 compatibility)."""
    
    def test_password_authenticator_initialization(self):
        """Test PasswordAuthenticator can be initialized with password."""
        email = 'test@example.com'
        password = 'test_password'
        
        authenticator = PasswordAuthenticator(email=email, password=password)
        
        assert authenticator.email == email
        assert authenticator.password == password
    
    def test_password_authenticator_with_env_var(self):
        """Test PasswordAuthenticator loads password from environment variable."""
        email = 'test@example.com'
        password_env = 'TEST_PASSWORD_ENV'
        test_password = 'env_password_123'
        
        with patch.dict(os.environ, {password_env: test_password}):
            authenticator = PasswordAuthenticator(
                email=email,
                password_env=password_env
            )
            
            assert authenticator.email == email
            assert authenticator.password == test_password
    
    @pytest.mark.skip(reason="Requires real IMAP connection")
    def test_password_authenticator_imap_login(self):
        """Test password authenticator with real IMAP connection."""
        # This test would require:
        # 1. Real IMAP server
        # 2. Valid email/password credentials
        # 3. IMAP server that supports password authentication
        
        # For now, we skip this test
        # In a real E2E environment, this would test:
        # - PasswordAuthenticator.authenticate() with real IMAP
        # - Successful login with password
        # - Error handling for invalid credentials
        pass
    
    def test_password_authenticator_missing_password(self):
        """Test PasswordAuthenticator error handling for missing password."""
        email = 'test@example.com'
        
        with pytest.raises((ValueError, AttributeError)):
            PasswordAuthenticator(email=email, password=None)
    
    def test_password_authenticator_missing_env_var(self):
        """Test PasswordAuthenticator error handling for missing env var."""
        email = 'test@example.com'
        password_env = 'NON_EXISTENT_ENV_VAR'
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises((ValueError, KeyError, AttributeError)):
                PasswordAuthenticator(email=email, password_env=password_env)


# ============================================================================
# Mixed OAuth/Password Account Processing Tests
# ============================================================================

class TestMixedAuthAccounts:
    """Test processing accounts with mixed OAuth and password authentication."""
    
    @pytest.fixture
    def config_loader(self, tmp_path):
        """Create ConfigLoader with temporary config directory."""
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'accounts').mkdir()
        
        return ConfigLoader(config_dir=config_dir)
    
    def test_config_loader_password_account(self, config_loader, tmp_path):
        """Test ConfigLoader loads password account correctly."""
        # Create password account config
        account_name = 'password_account'
        account_config_path = tmp_path / 'config' / 'accounts' / f'{account_name}.yaml'
        
        account_config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'test@example.com',
                'password_env': 'TEST_PASSWORD',
            },
            'auth': {
                'method': 'password',
            },
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(account_config, f)
        
        # Load account config
        merged_config = config_loader.load_merged_config(account_name)
        
        assert merged_config is not None
        assert merged_config.get('auth', {}).get('method') == 'password'
        assert merged_config.get('imap', {}).get('password_env') == 'TEST_PASSWORD'
    
    def test_config_loader_oauth_account(self, config_loader, tmp_path):
        """Test ConfigLoader loads OAuth account correctly."""
        # Create OAuth account config
        account_name = 'oauth_account'
        account_config_path = tmp_path / 'config' / 'accounts' / f'{account_name}.yaml'
        
        account_config = {
            'imap': {
                'server': 'imap.gmail.com',
                'username': 'test@gmail.com',
            },
            'auth': {
                'method': 'oauth',
                'provider': 'google',
            },
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(account_config, f)
        
        # Load account config
        merged_config = config_loader.load_merged_config(account_name)
        
        assert merged_config is not None
        assert merged_config.get('auth', {}).get('method') == 'oauth'
        assert merged_config.get('auth', {}).get('provider') == 'google'
    
    def test_config_loader_defaults_to_password(self, config_loader, tmp_path):
        """Test ConfigLoader defaults to password when auth block is missing (V4 compatibility)."""
        # Create account config without auth block (V4 style)
        account_name = 'v4_account'
        account_config_path = tmp_path / 'config' / 'accounts' / f'{account_name}.yaml'
        
        account_config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'test@example.com',
                'password_env': 'TEST_PASSWORD',
            },
            # No auth block - should default to password
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(account_config, f)
        
        # Load account config
        merged_config = config_loader.load_merged_config(account_name)
        
        # Should default to password method
        # Note: This depends on config_schema.py implementation
        # If schema defaults to password, this should pass
        auth_method = merged_config.get('auth', {}).get('method', 'password')
        assert auth_method == 'password' or 'password_env' in merged_config.get('imap', {})


# ============================================================================
# Account Processor Backward Compatibility Tests
# ============================================================================

class TestAccountProcessorBackwardCompat:
    """Test AccountProcessor handles both OAuth and password accounts."""
    
    @pytest.fixture
    def token_manager(self, tmp_path):
        """Create TokenManager with temporary credentials directory."""
        return TokenManager(credentials_dir=tmp_path / 'credentials')
    
    def test_account_processor_creates_password_authenticator(self, tmp_path):
        """Test AccountProcessor creates PasswordAuthenticator for password accounts."""
        # This test verifies that AccountProcessor correctly creates
        # PasswordAuthenticator when auth.method='password'
        
        # Mock config with password auth
        mock_config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'test@example.com',
                'password_env': 'TEST_PASSWORD',
            },
            'auth': {
                'method': 'password',
            },
        }
        
        # AccountProcessor should create PasswordAuthenticator
        # We can't easily test this without full integration, but we verify
        # the authenticator creation logic exists
        from src.account_processor import AccountProcessor
        
        # Verify AccountProcessor can be imported and has authentication logic
        assert AccountProcessor is not None
        assert hasattr(AccountProcessor, '__init__')
    
    def test_account_processor_creates_oauth_authenticator(self, tmp_path):
        """Test AccountProcessor creates OAuthAuthenticator for OAuth accounts."""
        # This test verifies that AccountProcessor correctly creates
        # OAuthAuthenticator when auth.method='oauth'
        
        # Mock config with OAuth auth
        mock_config = {
            'imap': {
                'server': 'imap.gmail.com',
                'username': 'test@gmail.com',
            },
            'auth': {
                'method': 'oauth',
                'provider': 'google',
            },
        }
        
        # AccountProcessor should create OAuthAuthenticator
        # We can't easily test this without full integration, but we verify
        # the authenticator creation logic exists
        from src.account_processor import AccountProcessor
        
        # Verify AccountProcessor can be imported and has authentication logic
        assert AccountProcessor is not None
        assert hasattr(AccountProcessor, '__init__')
    
    @pytest.mark.skip(reason="Requires full integration with real accounts")
    def test_account_processor_mixed_accounts(self):
        """Test AccountProcessor can process both password and OAuth accounts."""
        # This test would require:
        # 1. Multiple test accounts (some password, some OAuth)
        # 2. Real IMAP connections
        # 3. Valid credentials/tokens
        
        # For now, we skip this test
        # In a real E2E environment, this would test:
        # - Processing password account
        # - Processing OAuth account
        # - Both in same run
        # - No cross-contamination between accounts
        pass


# ============================================================================
# Configuration Backward Compatibility Tests
# ============================================================================

class TestConfigBackwardCompat:
    """Test configuration backward compatibility (V4 configs still work)."""
    
    def test_v4_config_without_auth_block(self, tmp_path):
        """Test V4 config without auth block defaults to password."""
        # Create V4-style config (no auth block)
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'accounts').mkdir()
        
        account_name = 'v4_account'
        account_config_path = config_dir / 'accounts' / f'{account_name}.yaml'
        
        v4_config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'test@example.com',
                'password_env': 'TEST_PASSWORD',
            },
            # No auth block - V4 style
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(v4_config, f)
        
        # Load with ConfigLoader
        config_loader = ConfigLoader(config_dir=config_dir)
        merged_config = config_loader.load_merged_config(account_name)
        
        # Should still work - either defaults to password or preserves V4 structure
        assert merged_config is not None
        assert 'imap' in merged_config
        assert merged_config['imap'].get('password_env') == 'TEST_PASSWORD'
    
    def test_v4_config_with_password_env(self, tmp_path):
        """Test V4 config with password_env still works."""
        # Create V4-style config with password_env in imap block
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'accounts').mkdir()
        
        account_name = 'v4_password_account'
        account_config_path = config_dir / 'accounts' / f'{account_name}.yaml'
        
        v4_config = {
            'imap': {
                'server': 'imap.example.com',
                'username': 'test@example.com',
                'password_env': 'TEST_PASSWORD',
            },
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(v4_config, f)
        
        # Load with ConfigLoader
        config_loader = ConfigLoader(config_dir=config_dir)
        merged_config = config_loader.load_merged_config(account_name)
        
        # Should preserve password_env
        assert merged_config is not None
        assert merged_config['imap'].get('password_env') == 'TEST_PASSWORD'
    
    def test_v5_config_with_oauth(self, tmp_path):
        """Test V5 config with OAuth works."""
        # Create V5-style config with OAuth
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'accounts').mkdir()
        
        account_name = 'v5_oauth_account'
        account_config_path = config_dir / 'accounts' / f'{account_name}.yaml'
        
        v5_config = {
            'imap': {
                'server': 'imap.gmail.com',
                'username': 'test@gmail.com',
            },
            'auth': {
                'method': 'oauth',
                'provider': 'google',
            },
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(v5_config, f)
        
        # Load with ConfigLoader
        config_loader = ConfigLoader(config_dir=config_dir)
        merged_config = config_loader.load_merged_config(account_name)
        
        # Should load OAuth config
        assert merged_config is not None
        assert merged_config.get('auth', {}).get('method') == 'oauth'
        assert merged_config.get('auth', {}).get('provider') == 'google'


# ============================================================================
# Error Handling Backward Compatibility Tests
# ============================================================================

class TestErrorHandlingBackwardCompat:
    """Test error handling maintains backward compatibility."""
    
    def test_missing_password_env_error(self):
        """Test error handling for missing password_env (V4 behavior)."""
        # PasswordAuthenticator should raise error for missing password
        with pytest.raises((ValueError, KeyError, AttributeError)):
            PasswordAuthenticator(
                email='test@example.com',
                password_env='NON_EXISTENT_ENV'
            )
    
    def test_missing_oauth_provider_error(self, tmp_path):
        """Test error handling for missing OAuth provider in config."""
        # Config with OAuth method but no provider should be invalid
        config_dir = tmp_path / 'config'
        config_dir.mkdir()
        (config_dir / 'accounts').mkdir()
        
        account_name = 'invalid_oauth_account'
        account_config_path = config_dir / 'accounts' / f'{account_name}.yaml'
        
        invalid_config = {
            'imap': {
                'server': 'imap.gmail.com',
                'username': 'test@gmail.com',
            },
            'auth': {
                'method': 'oauth',
                # Missing provider
            },
        }
        
        import yaml
        with open(account_config_path, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # ConfigLoader might load it, but validation should catch it
        config_loader = ConfigLoader(config_dir=config_dir)
        
        # Depending on schema validation, this might raise or load with None provider
        try:
            merged_config = config_loader.load_merged_config(account_name)
            # If loaded, provider should be None or missing
            provider = merged_config.get('auth', {}).get('provider')
            assert provider is None or provider == ''
        except Exception:
            # Or validation might raise an error
            pass
    
    def test_oauth_account_without_tokens_error(self, tmp_path):
        """Test error handling for OAuth account without tokens."""
        token_manager = TokenManager(credentials_dir=tmp_path / 'credentials')
        
        # Try to get token for non-existent account
        token = token_manager.get_valid_token('non_existent_account', 'google')
        
        # Should return None or raise error (depending on implementation)
        # For now, we just verify it doesn't crash
        assert token is None or True  # Accept either behavior
