# **Project Design Document: V3 Foundational Upgrade**

**Status:** `Final Draft`
**PDD Author:** Axon (AI Architect)
**Technical Lead:** Marc Bielert

This document provides the detailed technical specification for implementing the V3 Foundational Upgrade, based on the approved requirements in `prd.md`.

### **1. Overview & Context**
*   **Link to PRD:** `pdd_v3.md` (Provided)
*   **Technical Problem Statement:** Refactor the existing email processing script into a modular, configurable, and testable system. This involves replacing the monolithic classification logic with a score-based system driven by an external LLM, introducing CLI controls for targeted debugging, and decoupling the output format from the core logic using an external template file.
*   **Key Technical Stakeholders:** Marc Bielert

### **2. System Architecture & Design**
*   **High-Level Architecture Diagram:**
    ```mermaid
    graph TD
        A[User/Developer] -- Executes --> B(CLI: main.py);
        B -- Reads --> C[settings.py Facade];
        C -- Reads --> D[config.yaml];
        B -- Fetches Email --> E(IMAP Server);
        B -- Sends Prompt --> F(LLM API);
        F -- Returns JSON --> B;
        B -- Parses & Processes --> G(Jinja2 Templating Engine);
        G -- Generates --> H[Markdown Note (.md)];
    ```
*   **Technical Approach:** The system is architected around a central **Configuration Facade (`settings.py`)** which is the sole module responsible for loading and providing access to parameters from `config.yaml`. All other application modules retrieve configuration through this facade, decoupling them from the YAML file's structure. The `main.py` entry point uses the `click` library to orchestrate calls to modular components responsible for IMAP, LLM, and note generation.
*   **Alternatives Considered:** A flatter configuration structure was rejected in favor of a grouped structure to improve long-term maintainability. Using a structured database (e.g., SQLite) was implicitly rejected in favor of the project's core principle of using plaintext formats (IMAP flags for state, Markdown frontmatter for data).

### **3. Data Model & Schema**
#### **3.1. Configuration Schema (`config.yaml`)**
The configuration will be moved from a flat structure to a grouped structure.
```yaml
# Configuration for the V3 Email Processor
imap:
  server: '...'
  port: 143
  username: '...'
  password_env: 'IMAP_PASSWORD'
  query: 'ALL'
  processed_tag: 'AIProcessed'

paths:
  template_file: 'config/note_template.md.j2'
  obsidian_vault: '...'
  log_file: 'logs/agent.log'
  analytics_file: 'logs/analytics.jsonl'
  changelog_path: 'logs/email_changelog.md'
  prompt_file: 'config/prompt.md'

openrouter:
  api_key_env: 'OPENROUTER_API_KEY'
  api_url: 'https://openrouter.ai/api/v1'
  model: '...'
  temperature: 0.2
  retry_attempts: 3
  retry_delay_seconds: 5

processing:
  importance_threshold: 8
  spam_threshold: 5
  max_body_chars: 4000
  max_emails_per_run: 15
```

#### **3.2. Output Data Schema (Markdown Frontmatter)**
```yaml
---
uid: 12345
subject: "..."
from: "..."
to: [ "..."]
date: "YYYY-MM-DDTHH:MM:SSZ"
tags:
  - "email"
  - "important" # Dynamically added if score >= threshold
llm_output:
  importance_score: 9
  spam_score: 1
  model_used: "..."
processing_meta:
  script_version: "3.0"
  processed_at: "YYYY-MM-DDTHH:MM:SSZ"
  status: "success" # 'success' or 'error'
---
```

### **4. API Contract: LLM Interaction**
*   **Endpoint:** `POST` to URL from `settings.get_openrouter_api_url()`.
*   **Auth:** `Bearer` token via `settings.get_openrouter_api_key()`.
*   **Request:** A JSON payload with `model`, `temperature`, and messages, requesting a JSON object in response.
*   **Success Response:** A string of JSON containing `{"spam_score": <int>, "importance_score": <int>}`.
*   **Resilience:** A unified retry mechanism will trigger on any API, parsing, or validation failure. It will retry `N` times with a delay, as configured in `settings.py`. If all retries fail, it will generate a note with error values (`-1`) and an error status.

### **5. Backend Implementation Plan**
1.  **Refactor CLI from `argparse` to `click`:** Replace the `argparse` implementation in `main.py` with `click` to handle subcommands and interactive prompts.
2.  **Create `settings.py` Facade:** Create a `settings.py` module to be the single source of truth for configuration. It will load `config.yaml` and provide getter functions for all parameters.
3.  **Refactor App to Use Facade:** Systematically replace all direct `config['key']` access across the codebase with calls to the new `settings.py` getters.
4.  **Implement Modular App Logic:** Build out the V3 logic in a modular structure:
    *   `src/orchestrator.py`: High-level business logic.
    *   `src/imap_client.py`: IMAP interactions.
    *   `src/llm_client.py`: LLM API interactions and retry logic.
    *   `src/note_generator.py`: Jinja2 template rendering.
    *   `src/logger.py`: Logging and analytics.

### **6. Frontend Implementation Plan (CLI & Template)**
*   **CLI Design (`click`):**
    *   `python main.py process`: Main command for bulk or single processing.
        *   `--uid <ID>`: Target a single email.
        *   `--force-reprocess`: Ignore existing `processed_tag`.
        *   `--dry-run`: Output to console instead of writing files/setting flags.
    *   `python main.py cleanup-flags`: Maintenance command with a confirmation prompt.
*   **Template Design (`Jinja2`):**
    *   A data dictionary containing email data, scores, and config thresholds will be passed to a `.md.j2` template file. The template will contain logic to dynamically generate tags and structure the final Markdown note.

### **7. Non-Functional Requirements (NFRs) & Security**
*   **Performance:** Local operations should be < 1s; no memory leaks during batch processing.
*   **Security:** Credentials **must** be loaded from environment variables. The `cleanup-flags` command **must** have a mandatory confirmation prompt.
*   **Testing:** Unit tests with mocks for each module; integration tests leveraging the `--dry-run` feature.
*   **Observability:** Unstructured operational logs to `agent.log`; structured `uid, timestamp, status, scores` to `analytics.jsonl` for every processed email.

### **8. Deployment & Rollout Plan**
1.  **Code Merge:** Merge the V3 feature branch into `main`.
2.  **Dependencies:** Run `pip install click jinja2`.
3.  **Configuration:** Update `config.yaml` to the new V3 structure and ensure environment variables are correctly set.
4.  **Test Run:** Execute a test run on a single UID with `--force-reprocess` and verify the output.
5.  **Live Operation:** The script is ready for use.
6.  **(Optional) Backfill:** Run the script in bulk mode to backfill historical emails with V3 metadata.
*   **Rollback Plan:** In case of failure, stop the script and revert to the previous stable commit using `git`. Use the `cleanup-flags` command if any state correction is needed on the IMAP server.

### **9. Future Considerations**
*   **Flag Versioning:** For future major versions (V4+), consider introducing versioned IMAP flags (e.g., `'AIProcessed-V4'`) to create a clean separation of state between processing systems.
*   **Feature Ideas (from PRD):** A deterministic rules engine (blacklist/whitelist) and advanced topic modeling are potential next-step features.
