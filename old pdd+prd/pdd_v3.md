# Product Design Document: V3 Foundational Upgrade
This document outlines the strategy, scope, and requirements for the V3 overhaul of the email processing tool.

## **1. Overview & Strategy (The "Why")**

*   **Document Status:** `Approved`
*   **Author(s):** Strata (AI Guide), Project Developer
*   **Stakeholders:** Project Developer
*   **Executive Summary:** V3 is a foundational architectural upgrade that transforms the tool from a simple proof-of-concept into a testable, scalable, and intelligent system. It replaces the rigid classification model with a granular, score-based system and introduces a suite of developer-centric CLI tools to enable rapid iteration and debugging.

*   **Problem Statement:** The current tool lacks the necessary functionality for effective development and refinement. The core AI classification is an opaque "black box" that produces rigid, low-value results, and there is no direct way to test, debug, or improve it. This, combined with a minimal data output, renders the final notes functionally useless for downstream analysis or automation, putting the project at a "functionality without value" impasse.

*   **Strategic Alignment:** This project is the foundational step required to transition the tool from a proof-of-concept into a viable, long-term system. By building in testability (CLI controls), intelligence (granular scores), and flexibility (templating), V3 directly enables the future vision of a reliable, automated email processing pipeline that produces genuinely valuable, enriched notes.

## **2. The User & The Goal (The "Who" and "What Success Looks Like")**

*   **Target Audience / User Personas:**
    *   **Primary User:** "The Developer." This is the user actively building and refining the tool. Their core needs are control, testability, and the ability to improve the AI's intelligence.
    *   **Secondary User (Beneficiary):** "The Note Consumer." This is the user who will benefit from the enriched, queryable notes created by a more mature system, enabled by the work in V3.

*   **Goals & Success Metrics:**
    *   **Product Goals (Capabilities):**
        *   **Enable Single-Email Debugging:** The user can target, process, and re-process a single email using its UID.
        *   **Provide Granular AI Feedback:** Classification output includes numerical scores (0-10) for `importance` and `spam`.
        *   **Decouple Output from Logic:** Markdown note structure is defined in an external, user-editable template file.
        *   **Enable Consequence-Free Testing:** A `--dry-run` mode allows for testing without writing files or setting server flags.
        *   **Provide a Clean State Reset:** A dedicated, safeguarded command allows the developer to remove application-specific flags from the mail server.
    *   **Business Goals (Impact):**
        *   **Reduce Debugging Cycle Time by >95%:** The time to test a change on a single email is reduced from minutes/hours to seconds.
        *   **Unlock AI Prompt Iteration:** The workflow becomes practical for iterating on and improving LLM prompts with clear, immediate feedback.
    *   **Counter-Metrics (Guardrails):**
        *   **No Unintended Data Loss:** The `cleanup-flags` command must not delete any IMAP flags not explicitly defined in the application's configuration.

## **3. Scope & Requirements (The "What")**

*   **Guiding Architectural Principle:** Shift from a "Mailbox as Database" model to a "Knowledge Vault as Database" model. IMAP flags are for state; Markdown frontmatter is for rich, permanent data.
*   **Prerequisites:** **(Completed)** Manual validation of the score-based classification prompting strategy confirmed that a well-engineered prompt can reliably produce meaningful `importance` and `spam` scores like {"spam_score":2,"importance_score":8}.

*   **In-Scope (User Stories):**
    1.  **Core Logic:** Replace `urgent/neutral/spam` classification with a numerical scoring system (`urgency_score`, `spam_score`) and update decision logic to use configurable thresholds.
    2.  **CLI Controls:** Implement `--uid <ID>`, `--force-reprocess`, and `--dry-run` flags for fine-grained process control.
    3.  **Templating:** Use a templating engine (e.g., Jinja2) to generate Markdown from a user-editable template file.
    4.  **State Management:** Create a `cleanup-flags` command and a local log of processed emails.
    5.  **LLM Control:** Add an `llm_temperature` setting to the configuration to control model output.

*   **Out-of-Scope (for V3):**
    *   Large-scale prompt engineering and optimization.
    *   A complex, user-defined rules engine (beyond simple thresholds).
    *   Automatic note linking (backlinks).
    *   A Graphical User Interface (GUI).

## **4. Design & User Experience (UX) (The "How" - User Facing)**

*   **Core User Flow 1: The Iteration Loop:**
    1.  Developer edits logic/prompt.
    2.  Runs `python main.py --uid <UID> --force-reprocess`.
    3.  Inspects the overwritten Markdown file. Repeats.
*   **Core User Flow 2: The Non-Destructive Peek:**
    1.  Developer wants to inspect output without side effects.
    2.  Runs `python main.py --uid <UID> --dry-run`.
    3.  Reviews verbose output printed to the console.
*   **CLI "Wireframes":**
    *   **Primary Test Command:** `python main.py --uid <ID> --force-reprocess`
    *   **Quick Peek Command:** `python main.py --uid <ID> --dry-run`
    *   **Reset Command:** `python main.py cleanup-flags` (with mandatory confirmation prompt)

## **5. Technical & Non-Functional Requirements (The "How" - System Facing)**

*   **Configuration:** A single `config.yaml` will manage all user-configurable parameters (credentials, paths, thresholds, IMAP flags, LLM parameters). The file must be well-commented and organized into logical groups (`[api]`, `[imap]`, `[thresholds]`, etc.).
*   **LLM Interaction & Error Handling:**
    *   The prompt sent to the LLM must request a structured JSON object.
    *   The system must retry the API call a configurable number of times on failure.
    *   If all retries fail, the script must not crash. It will create a note with default error values (e.g., `spam_score: -1`) and tag it `#process_error`.
*   **Data & Analytics:** `spam_score` and `importance_score` must be parsed from the LLM's JSON output and stored as key-value pairs in the Markdown frontmatter.
*   **Dependencies:**
    *   CLI Argument Parsing Library (e.g., `argparse`, `click`).
    *   Templating Engine (e.g., `Jinja2`).

## **6. Go-Live Plan & Future Work**

*   **Deployment Plan:**
    1.  Development replaces the current `main.py` with the new V3 logic.
    2.  Post-testing, the V3 script will be executed across the entire target mailbox to backfill all historical emails with the new, rich metadata.
*   **Future Iterations (V4, V-Next):**
    *   **V4 Idea:** Implement a deterministic rules engine (e.g., `blacklist.txt`, `whitelist.txt`).
    *   **V-Next Idea:** Extend classification to include specific topic modeling (e.g., "Project X," "Funding").
*   **Open Questions & Risks:**
    *   **LLM Costs:** Managed via a budget-limited API.
    *   **IMAP Server Stability:** Considered low risk for the primary target server (Netcup).
*   **Decision Log:**
    *   **Architecture:** Adopted "Knowledge Vault as Database" model.
    *   **CLI Design:** `–-dry-run` is for non-destructive peeks; `--force-reprocess` is for the destructive iteration loop.
    *   **Resilience:** Agreed on a retry-then-log-error strategy for LLM failures.
