# Product Design Document: V5 "OAuth Integration"

**Document Status:** `Approved for Development`
**Author:** User & Strata (AI Strategist)
**Version:** 5.0

---

## 1. Overview & Strategy

*   **Executive Summary:** This project integrates OAuth 2.0 authentication for Google and Microsoft accounts. It replaces the legacy `app-password` method (which is being deprecated) with a secure, token-based flow.
*   **Problem Statement:** The Developer cannot currently use personal Google/Microsoft accounts because they require modern authentication. The current V4 system only supports Basic Auth (User/Pass), locking high-value personal data out of the system.
*   **Strategic Alignment:** Ensures the long-term viability of the tool by adopting modern security standards. It unblocks the use of the tool for personal email management without compromising the existing V4 architecture.

## 2. The User & The Goal

*   **Target Audience:** The Developer (Primary).
*   **Goals & Metrics:**
    *   **Success:** Google and Microsoft accounts can be authenticated once via CLI, and run indefinitely via background token refreshing.
    *   **Stability:** The `process` command works identically for OAuth and Password accounts.
    *   **Metric:** 0% regression for existing IMAP-password accounts (Backward Compatibility).

## 3. Scope & Requirements

### 3.1 Scope Limitations
*   **In-Scope:** Google & Microsoft providers, CLI-based Token generation, Token storage, `XOAUTH2` IMAP authentication, Automatic Token Refreshing.
*   **Out-of-Scope:** Custom OAuth providers, GUI, Web-based management interfaces.

### 3.2 User Stories

**Story 1: The "Identity Configuration"**
*   **As a** Developer, **I want** to define my App Credentials (Client ID/Secret) in environment variables/global config, **so that** I don't accidentally commit secrets or duplicate them across account files.
*   **Acceptance Criteria:**
    *   System reads `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` from `.env`.
    *   System reads `MS_CLIENT_ID` / `MS_CLIENT_SECRET` from `.env`.

**Story 2: The Authentication Handshake (CLI)**
*   **As a** User, **I want** to run `python main.py auth --account personal_gmail`, **so that** I can interactively authorize the application.
*   **Acceptance Criteria:**
    *   CLI generates the correct Authorization URL ensuring the correct **Scopes** are requested (see Tech Logic).
    *   CLI listens (localhost) or accepts code paste for the callback.
    *   Tokens (Access + Refresh) are saved to `credentials/<account_name>.json`.

**Story 3: Backward Compatible Execution**
*   **As a** System, **I want** to default to `password` mode if no auth method is defined, **so that** existing V4 account configurations do not break.
*   **Acceptance Criteria:**
    *   If `auth:` block is missing in YAML -> Default to Password logic.
    *   If `auth.method: password` -> use Password logic.
    *   If `auth.method: oauth` -> use Token logic.

## 4. Design: Configuration & Interface

### 4.1 Configuration Schema Updates
**A. Global Config (implicit/env):**
No changes to `config.yaml` file structure; strict reliance on `.env` for Client IDs to differentiate "Code" from "Credentials."

**B. Account Config (`accounts/personal.yaml`):**
```yaml
# EXISTING V4
email: "my.email@gmail.com" 

# NEW V5 SECTION
auth:
  method: "oauth"         # OPTIONS: 'password' (default), 'oauth'
  provider: "google"      # OPTIONS: 'google', 'microsoft'
  # Note: 'password_env' is ignored if method is 'oauth'
```

### 4.2 CLI Interaction
```bash
$ python main.py auth --account personal_google

[INFO] Initiating OAuth flow for provider: Google
[INFO] Please open this URL to authorize: https://accounts.google.com/o/oauth2/...
[INFO] Waiting for callback on port 8080...
[SUCCESS] Authenticated! Credentials saved to credentials/personal_google.json
```

## 5. Technical Architecture (Crucial for Agent-Coding)

### 5.1 Directory & File Structure
To maintain modularity and avoid "monolithic" classes, we will introduce a `src/auth/` module.

```text
email-agent/
├── credentials/                 # NEW: Git-ignored folder for JSON tokens
├── .env                         # Updated with Client IDs
├── src/
│   ├── auth/                    # NEW MODULE
│   │   ├── __init__.py
│   │   ├── oauth_flow.py        # Handles the CLI browser interaction (google-auth/msal)
│   │   ├── token_manager.py     # Handles loading, saving, and refreshing tokens
│   │   └── authenticators.py    # Strategy Pattern Classes
│   ├── imap_client.py           # Modified to use Authenticator Strategy
```

### 5.2 The "Authenticator" Strategy Pattern
Do not put `if/else` logic inside `IMAPClient`. Use a generic interface.

1.  **Interface:** `AuthenticatorProtocol` (Must deliver a simpler `authenticate(imap_connection)` method).
2.  **Concrete Class A:** `PasswordAuthenticator` (Legacy logic).
    *   Uses `user` and `password` from config.
    *   Calls `imap.login(user, password)`.
3.  **Concrete Class B:** `OAuthAuthenticator` (New logic).
    *   Uses `TokenManager` to get a valid Access Token (refreshing if needed).
    *   Generates SASL string: `user={email}\x01auth=Bearer {token}\x01\x01`.
    *   Calls `imap.authenticate('XOAUTH2', sasl_string)`.

**Refactoring `src/imap_client.py`:**
*   The `IMAPClient` should accept an `authenticator` instance during initialization or connection.
*   `IMAPClient.connect()` simply calls `self.authenticator.authenticate(self.server)`.

### 5.3 OAuth Scopes (The Permission Keys)
The coding agent **must** use these specific strings:
*   **Google:** `https://mail.google.com/`
*   **Microsoft:** `https://outlook.office.com/IMAP.AccessAsUser.All`, `https://outlook.office.com/User.Read`, `offline_access`

### 5.4 Security Constraints
*   **Gitignore:** The directory `credentials/` must be added to `.gitignore` **immediately**.
*   **Environment:** Client Secrets must never be hardcoded. Use `os.getenv()`.

## 6. Implementation Plan (Agent Instructions)

1.  **Secure the Perimeter:** Create `credentials/` folder and update `.gitignore`.
2.  **Core Logic (Auth Module):** Create `src/auth/token_manager.py` (Save/Load/Refresh logic) and `src/auth/oauth_flow.py` (The Interactive Login).
3.  **Refactor IMAP:** Modify `imap_client.py` to strip out the hardcoded `login()` method and replace it with the **Strategy Pattern** described in 5.2.
4.  **Wire Up Config:** Update `config_schema.py` to validate the new `auth` block (ensure it defaults to `password` if missing).
5.  **CLI Entry:** Add `auth` command to `cli_v4.py` that calls `oauth_flow.py`.

## 7. Risks & Mitigations
*   **Risk:** Token Refresh fails during a long batch process.
*   **Mitigation:** `OAuthAuthenticator` should check `token.expiry` *before* returning the auth string. If expired, refresh immediately.
*   **Risk:** Microsoft Azure App registration is complex.
*   **Mitigation:** Document exactly which "Redirect URI" (`http://localhost:8080`) is required in the App Registration.