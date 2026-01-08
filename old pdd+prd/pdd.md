# **Product Design Document: Headless AI Email Agent (V1)**

*   **Document Status:** `Approved for Development`
*   **Author(s) & Stakeholders:** Marc Bielert (NICA e.V.)

## **1. Overview & Strategy (The "Why")**

*   **Executive Summary:** This project is for a headless AI agent that automatically reads emails via IMAP from configured accounts, triaging and tagging them based on customizable prompts. This reduces manual sorting effort and ensures important messages are never missed.
*   **Problem Statement:** Our team manages dozens of shared and personal email accounts, leading to an overwhelming volume of incoming mail. The current manual process of sorting and managing these emails is inefficient, stressful, and error-prone, causing us to miss important communications and struggle to maintain organization.
*   **Strategic Alignment:** This project is critical to do now for three main reasons:
    1.  **Risk Mitigation:** By automating the initial triage of emails, we will significantly reduce the risk of missing critical communications like client requests or urgent deadlines.
    2.  **Increased Efficiency:** The agent will automate hours of manual email sorting each week, freeing up the team to focus on higher-value project work instead of inbox administration.
    3.  **Workflow Integration:** This tool is the foundational first step to eventually bridging our email servers and our Obsidian-based project management system, transforming unstructured emails into structured, actionable insights.

## **2. The User & The Goal (The "Who" and "What Success Looks Like")**

*   **Target Audience / User Personas:**
    *   **Primary User Persona (The Admin):** Marc, the technical team lead. He is responsible for building, configuring, and maintaining the AI agent. The system must be configurable and debuggable for him.
    *   **Secondary User Persona (The Team Member):** Two (and growing) less technical team members. They interact with the output of the agent (the tags) within their email client and expect it to be reliable and trustworthy.
*   **Goals & Success Metrics:**
    *   **Product Goals (Agent Performance):**
        *   **Triage Accuracy:** The agent correctly applies the intended tag for at least **90%** of cases.
        *   **Critical Error Rate:** The agent maintains a false negative rate of **less than 1%**, where a truly urgent email is incorrectly classified as low-priority or spam.
    *   **Business Goals (Team Impact):**
        *   **Efficiency Gain:** Reduce the Primary User's time spent on manual email sorting by an average of **3 hours per week**.
        *   **Team Confidence:** Achieve a state where the team reports **zero critical emails being missed** per month.
    *   **Counter-Metrics (What We Must Avoid):**
        *   **System Noise:** Fewer than **2 incidents per week** where a team member has to manually correct a mis-tagged email.
        *   **False Positive 'Urgent' Tags:** The 'Urgent' tag must have a precision of over **95%** to maintain system trust.

## **3. Scope & Requirements (The "What")**

### **3.1 Scope & Boundaries (V1)**

*   **In-Scope:**
    *   A headless Python CLI script connecting to a single IMAP server.
    *   Fetches emails based on a single, configurable IMAP query.
    *   Sends email content to OpenRouter using prompts from external Markdown files.
    *   Applies a tag to the email based on the AI response, with a safe default.
    *   Applies a unique `[AI-Processed]` tag to prevent re-processing.
    *   All actions are non-destructive (adding tags/flags only).
    *   Logging to both the console and a specified log file.
*   **Out-of-Scope:**
    *   **Obsidian Integration** (Defined as a V-Next feature).
    *   **Graphical User Interface (GUI)** (The agent is explicitly a command-line tool).
    *   **Multi-Account/Per-User Rules** (V1 will use a single global configuration).
    *   **Advanced AI Logic** (Multi-step AI chains are deferred).
    *   **Destructive Actions** (The agent will not move, delete, or archive emails).
    *   **Processing or reading email attachments** (Only the text/HTML body is considered).

### **3.2 User Stories & Acceptance Criteria**

---
**Story 1: Agent Configuration & Execution**
> As **Marc (the Admin)**, I want to **configure the agent using a `.env` file for my credentials and a separate `config.yaml` for its behavior**, so that I can **run the agent from my command line and have it securely process emails without hardcoding sensitive information.**

*   **AC 1:** Reads IMAP/OpenRouter credentials from a `.env` file. The script MUST exit immediately with an error if required credentials are missing.
*   **AC 2:** Reads operational parameters from a `config.yaml` file (e.g., `imap_query`, `prompt_file` path, `log_level`, etc.).
*   **AC 3:** Fails gracefully with a clear error if config files/keys are missing.
*   **AC 4:** Application starts via a single command (e.g., `python main.py`).
*   **AC 5:** The agent processes a maximum number of emails defined by `max_emails_per_run` in `config.yaml`.
*   **AC 6:** A command-line flag (`--limit N`) can override the `max_emails_per_run` value.
*   **AC 7:** If available emails exceed the limit, the summary report MUST state how many remain unprocessed.

---
**Story 2: Dynamic Prompt Management**
> As **Marc (the Admin)**, I want to **edit the AI prompts in simple Markdown files**, so that I can **quickly refine and improve the email classification rules without changing any code.**

*   **AC 1:** The path to the prompt file is specified in `config.yaml`.
*   **AC 2:** Correctly parses the Markdown file, separating YAML frontmatter from the main content.
*   **AC 3:** Changes to the prompt file are loaded on each run of the agent.

---
**Story 3: Email Classification & Tagging**
> As a **Team Member**, I want to **see new emails appear in Thunderbird with helpful tags**, so that I can **immediately understand an email's priority.**

*   **AC 1:** The AI is prompted to return a single, machine-readable keyword (e.g., `urgent`, `neutral`, `spam`).
*   **AC 2:** `config.yaml` contains a `tag_mapping` from AI keywords to IMAP tags.
*   **AC 3:** If the AI response is not in the `tag_mapping`, the agent MUST default to applying the `neutral` tag.
*   **AC 4:** Before being sent to the AI, the email body is truncated to a `max_body_chars` limit defined in `config.yaml`.
*   **AC 5:** A unique `processed_tag` (defined in `config.yaml`) is always applied after any other tagging action.

---
**Story 4: Safety and Idempotency**
> As **Marc (the Admin)**, I want the **agent to only process emails once**, so that I can **run it repeatedly without creating duplicate work or incurring extra costs.**

*   **AC 1:** The IMAP query explicitly excludes emails already having the `processed_tag`.
*   **AC 2:** Applying the `processed_tag` is the final action on any processed email.

---
**Story 5: Troubleshooting & Auditing**
> As **Marc (the Admin)**, I want the agent to **log all its activities**, so that I can **precisely debug misclassifications and audit the agent's decision-making process.**

*   **AC 1:** A `log_file` path can be specified in `config.yaml` to enable file logging.
*   **AC 2:** A `log_level` (`INFO` or `DEBUG`) can be set in `config.yaml`.
*   **AC 3:** When `log_level` is `DEBUG`, the log file must record the full sanitized content sent to the AI and the raw response received.
*   **AC 4:** Each log entry must be timestamped and associated with the email's `Message-ID`.

## **4. Design & User Experience (UX)**

*   **CLI User Flow:** The primary user experience is the output in the command-line terminal for the Admin.
*   **INFO Level Output (Default):** On execution, the CLI will display high-level status updates: connection status, number of emails found, a real-time progress bar that updates per email, and a final summary report of actions taken (e.g., `Tagged 'Urgent': 2`, `Tagged 'Neutral': 11`).
*   **DEBUG Level Output:** Includes all `INFO` level logs, plus detailed information for each email processed, including the raw AI response and the specific tagging action taken.

## **5. Technical & Non-Functional Requirements**

*   **Architecture:** A modular Python CLI script capable of supporting future enhancements (e.g., different classification methods, new integrations).
*   **Security:** Reads all secrets (API keys, passwords) from a `.env` file and will not run if they are missing.
*   **Performance:** A user-configurable `max_emails_per_run` limit prevents runaway execution time and cost, making performance predictable.
*   **Data & Analytics:**
    *   To track success metrics, the agent will append a single-line JSON object to an `analytics_file` (path defined in `config.yaml`) at the end of each run.
    *   **Schema:** `{"timestamp": "...", "total_processed": N, "tags_applied": {"tag1": N1, "tag2": N2}}`

## **6. Go-Live Plan & Future Work**

*   **Go-to-Market & Project Principles:**
    *   **Rollout & Adoption Plan:**
        *   **Phase 1 (Alpha Test):** The agent will be deployed and tested exclusively on the Primary User's personal email account.
        *   **Phase 2 (Team Rollout):** Once proven reliable, the agent will be configured for shared team inboxes after a full team briefing.
    *   **Open-Source Release:** The project source code will be made publicly available on GitHub under a suitable open-source license, in line with the society's mission. The core prompts may remain private initially.
*   **Future Iterations (The Roadmap):**
    *   **V2: Content Extraction & Structuring:** Develop a secondary AI step to extract structured data (tasks, summaries) from high-priority emails.
    *   **V3: Obsidian Vault Integration:** Build a module to create/append Markdown notes in an Obsidian vault from the extracted data.
    *   **V-Next (Broader Vision):** Wider system integration (e.g., Google Calendar), per-user configurations, and advanced classification logic (e.g., trusted sender lists).
*   **Open Questions & Risks:**
    *   **Multi-Language Performance:** The chosen LLM's classification performance on both German and English emails must be validated early. Prompts must be designed to be robust across both languages.
    *   **Rate Limits:** Any API rate limits on a chosen service (e.g., OpenRouter) need to be identified and handled gracefully.
*   **Decision Log:**
    *   **AI Safety Net:** Adopted an `Urgent/Neutral/Spam` classification model with `Neutral` as a mandatory safe fallback to mitigate AI unreliability.
    *   **Cost Control:** V1 will exclude email attachments and truncate email bodies (configurable limit) to control API costs.
    *   **Rollout Strategy:** Agreed on a phased rollout (personal account first, then team) to build trust and de-risk adoption.