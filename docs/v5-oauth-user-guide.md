# V5 OAuth User Guide

**Version:** 5.0  
**Status:** Complete  
**Target Audience:** End users setting up OAuth authentication

## Overview

This guide provides step-by-step instructions for setting up OAuth 2.0 authentication for Google and Microsoft email accounts. OAuth 2.0 is a modern, secure authentication method that replaces app passwords and provides better security for your email accounts.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setting Up Google OAuth](#setting-up-google-oauth)
3. [Setting Up Microsoft OAuth](#setting-up-microsoft-oauth)
4. [Configuring Your Account](#configuring-your-account)
5. [Authenticating Your Account](#authenticating-your-account)
6. [Using OAuth Accounts](#using-oauth-accounts)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before setting up OAuth authentication, ensure you have:

1. **Python 3.8+** installed
2. **Email Agent** installed and configured
3. **Access to Google Cloud Console** (for Google accounts) or **Azure Portal** (for Microsoft accounts)
4. **Administrative access** to create OAuth applications

---

## Setting Up Google OAuth

### Step 1: Create OAuth 2.0 Credentials in Google Cloud Console

1. **Go to Google Cloud Console**
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Sign in with your Google account

2. **Create or Select a Project**
   - Click the project dropdown at the top
   - Click "New Project" or select an existing project
   - Give your project a name (e.g., "Email Agent OAuth")

3. **Enable Gmail API**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

4. **Configure OAuth Consent Screen**
   - Go to "APIs & Services" > "OAuth consent screen"
   - Select "External" (unless you have a Google Workspace account)
   - Fill in required information:
     - **App name**: Email Agent (or your preferred name)
     - **User support email**: Your email address
     - **Developer contact information**: Your email address
   - Click "Save and Continue"
   - On "Scopes" page, click "Add or Remove Scopes"
   - Add scope: `https://mail.google.com/`
   - Click "Save and Continue"
   - On "Test users" page, add your email address as a test user
   - Click "Save and Continue"

5. **Create OAuth 2.0 Client ID**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" as application type
   - Give it a name (e.g., "Email Agent Desktop")
   - Click "Create"
   - **Important**: Copy the **Client ID** and **Client Secret** immediately
     - You won't be able to see the secret again!

### Step 2: Configure Environment Variables

Add the Google OAuth credentials to your `.env` file:

```bash
# Google OAuth Credentials
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

**Security Note:** Never commit your `.env` file to version control. It's already in `.gitignore`.

---

## Setting Up Microsoft OAuth

### Step 1: Register Application in Azure Portal

1. **Go to Azure Portal**
   - Visit [Azure Portal](https://portal.azure.com/)
   - Sign in with your Microsoft account

2. **Navigate to App Registrations**
   - Go to "Azure Active Directory" > "App registrations"
   - Click "New registration"

3. **Register Your Application**
   - **Name**: Email Agent (or your preferred name)
   - **Supported account types**: 
     - Select "Accounts in any organizational directory and personal Microsoft accounts"
   - **Redirect URI**: 
     - Platform: "Public client/native (mobile & desktop)"
     - Redirect URI: `http://localhost:8080/callback`
   - Click "Register"

4. **Configure API Permissions**
   - Go to "API permissions"
   - Click "Add a permission"
   - Select "Microsoft Graph"
   - Select "Delegated permissions"
   - Add the following permissions:
     - `https://outlook.office.com/IMAP.AccessAsUser.All`
     - `https://outlook.office.com/User.Read`
     - `offline_access` (for refresh tokens)
   - Click "Add permissions"
   - Click "Grant admin consent" (if you have admin rights)

5. **Create Client Secret**
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Add a description (e.g., "Email Agent Secret")
   - Set expiration (recommend 24 months)
   - Click "Add"
   - **Important**: Copy the **Value** immediately (not the Secret ID)
     - You won't be able to see the value again!

6. **Get Application (Client) ID**
   - Go to "Overview"
   - Copy the **Application (client) ID**

### Step 2: Configure Environment Variables

Add the Microsoft OAuth credentials to your `.env` file:

```bash
# Microsoft OAuth Credentials
MS_CLIENT_ID=your_application_client_id_here
MS_CLIENT_SECRET=your_client_secret_value_here
```

**Security Note:** Never commit your `.env` file to version control. It's already in `.gitignore`.

---

## Configuring Your Account

### Step 1: Create Account Configuration File

Create or edit your account configuration file in `config/accounts/<account-name>.yaml`:

**For Google Account:**
```yaml
imap:
  server: imap.gmail.com
  username: your.email@gmail.com
  port: 993
  use_ssl: true

auth:
  method: oauth
  provider: google
```

**For Microsoft Account:**
```yaml
imap:
  server: outlook.office365.com
  username: your.email@outlook.com
  port: 993
  use_ssl: true

auth:
  method: oauth
  provider: microsoft
```

### Step 2: Verify Configuration

Verify your configuration is correct:

```bash
python main.py show-config --account <account-name>
```

This will display your merged configuration (global + account-specific).

---

## Authenticating Your Account

### Step 1: Run the Auth Command

Authenticate your account using the `auth` command:

```bash
python main.py auth --account <account-name>
```

Replace `<account-name>` with the name of your account configuration file (without `.yaml`).

### Step 2: Complete the OAuth Flow

The authentication process will:

1. **Start Local Server**: A local HTTP server starts on port 8080 (or next available port)
2. **Open Browser**: Your default browser opens to the OAuth authorization page
3. **Authorize Application**: 
   - Sign in with your email account
   - Review the permissions requested
   - Click "Allow" or "Accept" to grant permissions
4. **Receive Callback**: The application receives the authorization code automatically
5. **Save Tokens**: Tokens are saved securely to `credentials/<account-name>.json`

### Step 3: Verify Authentication

After successful authentication, you should see:

```
✅ Authentication successful for account '<account-name>'!
   Tokens saved to: credentials/<account-name>.json
   Provider: google
```

### Handling Existing Tokens

If tokens already exist for the account, you'll be prompted:

```
⚠️  Warning: Tokens already exist for account '<account-name>'
   Location: credentials/<account-name>.json
   Do you want to overwrite existing tokens? (yes/no): 
```

- Type `yes` to overwrite existing tokens
- Type `no` to keep existing tokens and cancel

---

## Using OAuth Accounts

### Processing Emails

Once authenticated, use OAuth accounts exactly like password accounts:

```bash
# Process single account
python main.py process --account <account-name>

# Process all accounts (including OAuth)
python main.py process --all
```

### Automatic Token Refresh

OAuth tokens are automatically refreshed when needed:

- **Expiry Checking**: Tokens are checked before each use
- **5-Minute Buffer**: Tokens are refreshed if expiring within 5 minutes
- **Automatic Refresh**: No user intervention required
- **Transparent Operation**: Works seamlessly in the background

### Token Storage

Tokens are stored securely:

- **Location**: `credentials/<account-name>.json`
- **Permissions**: 0600 (read/write for owner only)
- **Format**: JSON with encrypted tokens
- **Backup**: Consider backing up the `credentials/` directory

---

## Troubleshooting

### Common Issues

#### 1. "No available ports 8080-8099"

**Problem**: All callback ports are busy.

**Solution**:
- Close applications using ports 8080-8099
- Or manually specify a different port (requires code modification)

#### 2. "Authentication timed out"

**Problem**: Authorization wasn't completed in time.

**Solution**:
- Try again and complete authorization quickly
- Ensure browser isn't blocking redirects
- Check firewall settings

#### 3. "Failed to initialize OAuth provider"

**Problem**: Missing or invalid environment variables.

**Solution**:
- Verify `.env` file exists and contains correct credentials
- Check for typos in variable names:
  - Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
  - Microsoft: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`
- Ensure no extra spaces or quotes around values

#### 4. "Invalid OAuth provider"

**Problem**: Provider name is incorrect in config.

**Solution**:
- Verify `auth.provider` is exactly `google` or `microsoft` (lowercase)
- Check account configuration file syntax

#### 5. "Redirect URI mismatch"

**Problem**: Redirect URI in OAuth app doesn't match application.

**Solution**:
- **Google**: Ensure redirect URI is `http://localhost:8080/callback` (or matching port)
- **Microsoft**: Ensure redirect URI is `http://localhost:8080/callback` in app registration

#### 6. "Token refresh failed"

**Problem**: Refresh token is invalid or expired.

**Solution**:
- Re-authenticate the account: `python main.py auth --account <account-name>`
- Ensure `offline_access` scope is included (Microsoft)

### Getting Help

If you encounter issues not covered here:

1. **Check Logs**: Review `logs/agent.log` for detailed error messages
2. **Verify Configuration**: Run `python main.py show-config --account <account-name>`
3. **Test OAuth Credentials**: Verify credentials work in provider's test tools
4. **Check Documentation**: See [Troubleshooting Guide](v5-oauth-troubleshooting.md)

---

## Security Best Practices

### Credential Management

1. **Never Commit Secrets**: 
   - `.env` file is in `.gitignore`
   - Never commit OAuth client secrets
   - Never commit token files

2. **Rotate Credentials**:
   - Rotate OAuth client secrets periodically
   - Re-authenticate if refresh tokens are compromised

3. **File Permissions**:
   - Token files have 0600 permissions (owner only)
   - Credentials directory has 0700 permissions

### OAuth Best Practices

1. **Scope Minimization**: Only request necessary scopes
2. **State Parameter**: Always validated (CSRF protection)
3. **HTTPS**: All OAuth endpoints use HTTPS
4. **Token Storage**: Tokens stored securely with restricted permissions

---

## Migration from Password Authentication

If you're migrating from password authentication to OAuth:

1. **Keep Password Config**: Your existing password accounts continue to work
2. **Add OAuth Config**: Create new account configs with `auth.method='oauth'`
3. **Gradual Migration**: Migrate accounts one at a time
4. **Test Thoroughly**: Verify OAuth accounts work before removing password configs

**Example Migration:**

**Before (Password):**
```yaml
imap:
  server: imap.gmail.com
  username: your.email@gmail.com
  password_env: GMAIL_PASSWORD
```

**After (OAuth):**
```yaml
imap:
  server: imap.gmail.com
  username: your.email@gmail.com

auth:
  method: oauth
  provider: google
```

---

## Related Documentation

- [V5 OAuth Flow](v5-oauth-flow.md) - Technical implementation details
- [V5 Token Manager](v5-token-manager.md) - Token management system
- [V5 Google Provider](v5-google-provider.md) - Google OAuth provider
- [V5 Microsoft Provider](v5-microsoft-provider.md) - Microsoft OAuth provider
- [V5 OAuth Troubleshooting](v5-oauth-troubleshooting.md) - Detailed troubleshooting guide
- [V4 CLI Usage](v4-cli-usage.md) - CLI command reference

---

## Quick Reference

### Environment Variables

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# Microsoft OAuth
MS_CLIENT_ID=your_client_id
MS_CLIENT_SECRET=your_client_secret
```

### Account Configuration

```yaml
# Google
auth:
  method: oauth
  provider: google

# Microsoft
auth:
  method: oauth
  provider: microsoft
```

### CLI Commands

```bash
# Authenticate account
python main.py auth --account <account-name>

# Process account
python main.py process --account <account-name>

# Show configuration
python main.py show-config --account <account-name>
```

---

**Last Updated:** 2026-01-25  
**Version:** 5.0
