# V5 OAuth Troubleshooting Guide

**Version:** 5.0  
**Status:** Complete  
**Target Audience:** Users troubleshooting OAuth authentication issues

## Overview

This guide provides detailed troubleshooting steps for common OAuth 2.0 authentication issues. For basic setup instructions, see [V5 OAuth User Guide](v5-oauth-user-guide.md).

## Table of Contents

1. [Diagnostic Commands](#diagnostic-commands)
2. [Common Error Messages](#common-error-messages)
3. [Provider-Specific Issues](#provider-specific-issues)
4. [Configuration Issues](#configuration-issues)
5. [Network and Port Issues](#network-and-port-issues)
6. [Token Issues](#token-issues)
7. [Advanced Troubleshooting](#advanced-troubleshooting)

---

## Diagnostic Commands

### Check Configuration

Verify your account configuration is correct:

```bash
python main.py show-config --account <account-name>
```

This displays:
- Merged configuration (global + account overrides)
- Authentication method and provider
- IMAP settings
- Any configuration errors

### Check Environment Variables

Verify OAuth credentials are loaded:

```bash
# Linux/Mac
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET
echo $MS_CLIENT_ID
echo $MS_CLIENT_SECRET

# Windows PowerShell
$env:GOOGLE_CLIENT_ID
$env:GOOGLE_CLIENT_SECRET
$env:MS_CLIENT_ID
$env:MS_CLIENT_SECRET
```

### Check Logs

Review application logs for detailed error information:

```bash
# View recent log entries
tail -n 50 logs/agent.log

# Search for OAuth errors
grep -i "oauth" logs/agent.log
grep -i "auth" logs/agent.log
```

### Verify Token Files

Check if tokens exist and are readable:

```bash
# List token files
ls -la credentials/

# Check file permissions (should be 0600)
stat credentials/<account-name>.json

# View token file (be careful - contains sensitive data)
cat credentials/<account-name>.json
```

---

## Common Error Messages

### "Failed to initialize OAuth provider"

**Symptoms:**
```
❌ Error: Failed to initialize google OAuth provider: ...
   Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set in .env
```

**Causes:**
1. Missing environment variables
2. Incorrect variable names
3. Empty values
4. `.env` file not loaded

**Solutions:**

1. **Verify `.env` file exists:**
   ```bash
   ls -la .env
   ```

2. **Check variable names (case-sensitive):**
   ```bash
   # Correct
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   
   # Incorrect
   google_client_id=...  # Wrong case
   GOOGLE_CLIENT_ID=...  # Missing _SECRET
   ```

3. **Verify values are not empty:**
   ```bash
   # In .env file
   GOOGLE_CLIENT_ID=your_actual_client_id_here
   GOOGLE_CLIENT_SECRET=your_actual_secret_here
   ```

4. **Check for extra spaces or quotes:**
   ```bash
   # Correct
   GOOGLE_CLIENT_ID=abc123.apps.googleusercontent.com
   
   # Incorrect
   GOOGLE_CLIENT_ID="abc123.apps.googleusercontent.com"  # Quotes not needed
   GOOGLE_CLIENT_ID= abc123.apps.googleusercontent.com  # Space after =
   ```

5. **Reload environment:**
   ```bash
   # Restart terminal/command prompt
   # Or source .env manually (Linux/Mac)
   source .env
   ```

### "No available ports 8080-8099"

**Symptoms:**
```
❌ Error: No available ports 8080-8099. Please free a port or use manual code entry.
```

**Causes:**
1. All ports 8080-8099 are in use
2. Firewall blocking ports
3. Permission issues

**Solutions:**

1. **Find what's using the ports:**
   ```bash
   # Linux/Mac
   lsof -i :8080
   netstat -an | grep 8080
   
   # Windows
   netstat -ano | findstr :8080
   ```

2. **Free up a port:**
   - Close applications using ports 8080-8099
   - Stop other services on these ports
   - Restart your computer if needed

3. **Check firewall:**
   - Allow localhost connections on ports 8080-8099
   - Temporarily disable firewall for testing

4. **Use different port (requires code modification):**
   ```python
   # In oauth_flow.py or CLI
   flow = OAuthFlow(..., callback_port=9000)
   ```

### "Authentication timed out"

**Symptoms:**
```
❌ Error: Authentication timed out: No authorization code received
   Please try again and complete the authorization in your browser.
```

**Causes:**
1. Browser didn't open
2. Authorization not completed
3. Callback not received
4. Network issues

**Solutions:**

1. **Manually open authorization URL:**
   - Copy the authorization URL from console output
   - Paste into browser manually
   - Complete authorization

2. **Complete authorization quickly:**
   - Default timeout is 120 seconds
   - Complete authorization within 2 minutes

3. **Check browser redirects:**
   - Ensure browser allows redirects to `localhost:8080`
   - Check browser console for errors

4. **Verify callback URL:**
   - Should be `http://localhost:8080/callback`
   - Check OAuth app configuration matches

5. **Increase timeout (requires code modification):**
   ```python
   flow.run(timeout=300)  # 5 minutes
   ```

### "State parameter mismatch"

**Symptoms:**
```
ValueError: State parameter mismatch. Possible CSRF attack.
```

**Causes:**
1. Multiple auth flows running simultaneously
2. Browser session issues
3. Timeout between URL generation and callback

**Solutions:**

1. **Run one auth flow at a time:**
   - Don't run multiple `auth` commands simultaneously
   - Wait for one to complete before starting another

2. **Clear browser state:**
   - Clear cookies for OAuth provider
   - Use incognito/private mode
   - Restart browser

3. **Retry authentication:**
   ```bash
   python main.py auth --account <account-name>
   ```

### "Redirect URI mismatch"

**Symptoms:**
```
Error 400: redirect_uri_mismatch
```

**Causes:**
1. Redirect URI in OAuth app doesn't match application
2. Port mismatch
3. Protocol mismatch (http vs https)

**Solutions:**

1. **Google OAuth:**
   - Go to Google Cloud Console > Credentials
   - Edit OAuth 2.0 Client ID
   - Add authorized redirect URI: `http://localhost:8080/callback`
   - Save changes

2. **Microsoft OAuth:**
   - Go to Azure Portal > App registrations
   - Select your app > Authentication
   - Add platform: "Public client/native"
   - Add redirect URI: `http://localhost:8080/callback`
   - Save

3. **Verify port:**
   - If using different port, update redirect URI accordingly
   - Example: `http://localhost:9000/callback` for port 9000

---

## Provider-Specific Issues

### Google OAuth Issues

#### "Access blocked: This app's request is invalid"

**Cause:** OAuth consent screen not configured or app in testing mode.

**Solution:**
1. Go to Google Cloud Console > OAuth consent screen
2. Complete all required fields
3. Add test users if app is in testing mode
4. Publish app if ready for production

#### "Error 403: access_denied"

**Cause:** User denied authorization or insufficient permissions.

**Solution:**
1. Retry authorization
2. Ensure you're signed in with correct account
3. Grant all requested permissions
4. Check OAuth consent screen configuration

#### "Invalid client"

**Cause:** Client ID or secret is incorrect.

**Solution:**
1. Verify `GOOGLE_CLIENT_ID` matches Client ID in Google Cloud Console
2. Verify `GOOGLE_CLIENT_SECRET` matches Client Secret
3. Regenerate client secret if needed
4. Update `.env` file with new credentials

### Microsoft OAuth Issues

#### "AADSTS50020: User account not found"

**Cause:** Account doesn't exist or wrong account type.

**Solution:**
1. Verify email address is correct
2. Ensure account is Microsoft account (not Google)
3. Try signing in with different account

#### "AADSTS70011: Invalid scope"

**Cause:** Requested scopes not configured in app registration.

**Solution:**
1. Go to Azure Portal > App registrations > API permissions
2. Verify scopes are added:
   - `https://outlook.office.com/IMAP.AccessAsUser.All`
   - `https://outlook.office.com/User.Read`
   - `offline_access`
3. Grant admin consent if needed

#### "AADSTS65001: User or administrator has not consented"

**Cause:** Permissions not granted.

**Solution:**
1. Grant admin consent in Azure Portal
2. Or complete consent during OAuth flow
3. Ensure you have permission to grant consent

#### "Token refresh failed"

**Cause:** Refresh token expired or invalid.

**Solution:**
1. Re-authenticate account:
   ```bash
   python main.py auth --account <account-name>
   ```
2. Ensure `offline_access` scope is included
3. Check token file permissions

---

## Configuration Issues

### "Account not configured for OAuth authentication"

**Cause:** `auth.method` is not set to `oauth` in account config.

**Solution:**
1. Edit account config file: `config/accounts/<account-name>.yaml`
2. Add or update auth block:
   ```yaml
   auth:
     method: oauth
     provider: google  # or microsoft
   ```
3. Verify with: `python main.py show-config --account <account-name>`

### "OAuth provider not specified"

**Cause:** `auth.provider` is missing or incorrect.

**Solution:**
1. Edit account config file
2. Add provider:
   ```yaml
   auth:
     method: oauth
     provider: google  # Must be exactly 'google' or 'microsoft'
   ```
3. Verify provider name is lowercase and exact match

### "Invalid OAuth provider"

**Cause:** Provider name is not `google` or `microsoft`.

**Solution:**
1. Check provider name spelling
2. Ensure lowercase: `google` not `Google` or `GOOGLE`
3. Valid values: `google`, `microsoft`

---

## Network and Port Issues

### Port Already in Use

**Symptoms:** Error when starting OAuth flow, port conflict.

**Diagnosis:**
```bash
# Linux/Mac
lsof -i :8080
netstat -an | grep 8080

# Windows
netstat -ano | findstr :8080
```

**Solution:**
1. Close application using port
2. Wait for port to be released
3. Retry authentication

### Firewall Blocking Callback

**Symptoms:** Authorization completes but callback not received.

**Solution:**
1. Allow localhost connections in firewall
2. Temporarily disable firewall for testing
3. Check Windows Firewall / Linux iptables rules

### Network Connectivity

**Symptoms:** Can't reach OAuth provider endpoints.

**Diagnosis:**
```bash
# Test Google OAuth endpoint
curl https://accounts.google.com/o/oauth2/v2/auth

# Test Microsoft OAuth endpoint
curl https://login.microsoftonline.com/common/oauth2/v2.0/authorize
```

**Solution:**
1. Check internet connection
2. Verify DNS resolution
3. Check proxy settings
4. Verify firewall allows HTTPS

---

## Token Issues

### "Token refresh failed"

**Symptoms:** Tokens expire and refresh fails.

**Causes:**
1. Refresh token expired
2. Invalid refresh token
3. Network error during refresh
4. Provider credentials changed

**Solutions:**

1. **Re-authenticate:**
   ```bash
   python main.py auth --account <account-name>
   ```

2. **Check token file:**
   ```bash
   cat credentials/<account-name>.json
   ```
   - Verify `refresh_token` exists
   - Check `expires_at` timestamp

3. **Verify provider credentials:**
   - Check `.env` file has correct credentials
   - Verify credentials haven't been rotated

4. **Check network:**
   - Ensure internet connection is active
   - Verify OAuth provider endpoints are reachable

### "Token file not found"

**Symptoms:** `load_tokens()` returns None.

**Solutions:**

1. **Authenticate account:**
   ```bash
   python main.py auth --account <account-name>
   ```

2. **Check file exists:**
   ```bash
   ls -la credentials/<account-name>.json
   ```

3. **Verify file permissions:**
   ```bash
   chmod 600 credentials/<account-name>.json
   ```

### "Invalid token format"

**Symptoms:** Token file exists but can't be parsed.

**Solutions:**

1. **Check file content:**
   ```bash
   cat credentials/<account-name>.json
   ```
   - Should be valid JSON
   - Should contain `access_token` field

2. **Delete and re-authenticate:**
   ```bash
   rm credentials/<account-name>.json
   python main.py auth --account <account-name>
   ```

---

## Advanced Troubleshooting

### Enable Debug Logging

Get detailed logs for OAuth operations:

```bash
python main.py --log-level DEBUG auth --account <account-name>
```

### Test OAuth Provider Directly

Test provider initialization:

```python
# Python interactive shell
from src.auth.providers.google import GoogleOAuthProvider
provider = GoogleOAuthProvider()
print(provider.client_id)  # Should print client ID
```

### Verify Token Manager

Test token operations:

```python
from src.auth.token_manager import TokenManager
manager = TokenManager()
tokens = manager.load_tokens('test_account')
print(tokens)  # Should print token dict or None
```

### Check IMAP Authentication

Test OAuth authenticator with IMAP:

```python
from src.auth.strategies import OAuthAuthenticator
from src.auth.token_manager import TokenManager
import imaplib

token_manager = TokenManager()
authenticator = OAuthAuthenticator(
    email='test@example.com',
    account_name='test_account',
    provider_name='google',
    token_manager=token_manager
)

# Test with real IMAP connection
imap = imaplib.IMAP4_SSL('imap.gmail.com', 993)
authenticator.authenticate(imap)
```

### Manual Token Refresh

Test token refresh manually:

```python
from src.auth.token_manager import TokenManager

manager = TokenManager()
refreshed = manager.refresh_token('account_name', 'google')
print(refreshed)  # Should print new token dict
```

---

## Getting Additional Help

If issues persist:

1. **Check Logs:** Review `logs/agent.log` for detailed errors
2. **Verify Configuration:** Run `python main.py show-config --account <account-name>`
3. **Test Credentials:** Verify OAuth credentials work in provider's test tools
4. **Review Documentation:**
   - [V5 OAuth User Guide](v5-oauth-user-guide.md)
   - [V5 OAuth Flow](v5-oauth-flow.md)
   - [V5 Token Manager](v5-token-manager.md)

---

## Error Code Reference

| Error Code | Description | Solution |
|------------|-------------|----------|
| `redirect_uri_mismatch` | Redirect URI doesn't match | Update OAuth app redirect URI |
| `invalid_client` | Client ID/secret incorrect | Verify credentials in `.env` |
| `access_denied` | User denied authorization | Retry and grant permissions |
| `invalid_grant` | Authorization code invalid | Re-authenticate account |
| `invalid_scope` | Requested scopes invalid | Check OAuth app permissions |
| `token_expired` | Access token expired | Token should auto-refresh |
| `invalid_refresh_token` | Refresh token invalid | Re-authenticate account |

---

**Last Updated:** 2026-01-25  
**Version:** 5.0
