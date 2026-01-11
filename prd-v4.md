# Product Design Document: V4 "Orchestrator" Upgrade

**Document Status:** `Approved (Final)`
**Author(s):** Marc Bielert
**Version:** 1.0 (Post-Review)

---

### **1. Overview & Strategy**
*   **Executive Summary:** V4, the "Orchestrator" upgrade, transforms the tool from a single-purpose script into a multi-tenant platform capable of managing multiple, distinct email accounts. It introduces a sophisticated rules engine for fine-tuning AI classification and enhances core intelligence by parsing rich HTML content, all while implementing critical safety and architectural guardrails.
*   **Problem Statement:** The V3 tool is highly effective but architecturally limited to a single inbox and unified processing logic. To expand utility, it must handle isolated accounts (e.g., personal vs. work) with unique rules. Furthermore, reliance on plain-text bodies limits accuracy, and the lack of deterministic pre/post-processing rules limits user control.
*   **Strategic Alignment:** Moves the tool from a simple script to a centralized "command center" for email intelligence. It establishes the foundation for scalability via multi-account support and reliability via strict state isolation.

### **2. System Architecture & Design Principles**
*   **Core Architecture: "Default + Override" Model:**
    *   Base settings reside in a global `config.yaml`.
    *   Account-specific settings reside in named `.yaml` files (e.g., `work.yaml`).
    *   At runtime, the system deep-merges the account file *over* the default config to produce the final session configuration.
*   **Key Principle: Isolated State:**
    *   To prevent data bleeding, the orchestrator **must** instantiate a new, self-contained `AccountProcessor` object for every account loop.
    *   No mutable state (paths, IMAP clients, counters) survives between account transitions.

### **3. The User & The Goal**
*   **Target Audience:** The Developer/Admin.
*   **Goals & Metrics:**
    *   **Capability:** Successfully process multiple accounts in one sequence with distinct rules.
    *   **Accuracy:** Improved classification via HTML-to-Markdown parsing.
    *   **Control:** Ability to explicitly `drop`, `record` (without AI), or `boost` (add to AI score) via YAML rules.
    *   **Safety:** Zero accidental "wallet-drain" events via mandatory cost estimates and dry-runs for mass operations.

### **4. Scope & Requirements (The "What")**

#### **4.1 CLI & Controls**
*   **Commands:**
    *   `process --account <name>`: Runs a specific account.
    *   `process --all`: Runs the default sequence defined in config.
    *   `show-config --account <name>`: Outputs the merged configuration for debugging.
*   **Safety Interlock & Cost Estimation:**
    *   Any command triggering a mass re-process (global or full account) **must** halt for confirmation (`y/n`).
    *   **The Prompt:** The prompt must display a "Crude Cost Estimate" calculated as: `(Total Emails) * (Model Cost)`.
    *   **Configuration:** The `Model Cost` value must be editable in `config.yaml` to tune estimation acc.

#### **4.2 The Processing Engine (Rules & Logic Pipeline)**
The system follows a strict linear pipeline for every email found.

**A. Blacklist Check (Pre-Processing)**
*   **Trigger:** Matches sender, subject, or domain against `blacklist.yaml`.
*   **Behavior Modes (`action` property):**
    *   **`action: drop` (Default):** The email is ignored entirely. Logged at `DEBUG` level. No generic file created.
    *   **`action: record`:** A "Silent Capture." A `.md` file is generated, but **NO** LLM processing occurs and **NO** HTML parsing is attempted (raw text only). The file is tagged `status/blacklisted`.

**B. Content Parsing & Fallback**
*   **Primary:** Attempt to parse HTML content to Markdown (via `html2text`).
*   **Fallback:** If parsing fails (exception or empty result), the system **automatically reverts** to the raw `text/plain` email body.
    *   *Constraint:* This event must be logged as a `WARN`, and the output file tagged with `error/html_fallback`.

**C. LLM Processing**
*   **Action:** The parsed content (or fallback text) is sent to the LLM for scoring/summarization.

**D. Whitelist Modifiers (Post-LLM)**
*   **Trigger:** Matches sender, subject, or domain against `whitelist.yaml`.
*   **Logic Type:** **Additive/Modifier** (Not a bypass).
*   **Behavior:**
    *   **Tags:** Appends specified tags (e.g., `#vip`) to the frontmatter.
    *   **Score:** If defined, adds a `score_boost` (e.g., +20) to the LLM's generated score.

#### **4.3 Configuration Logic**
*   **List Handling:** When merging configurations, if an account override defines a list property (e.g., `folders_to_scan`), it **completely replaces** the default list (no appending).

#### **4.4 Out-of-Scope (V4)**
*   GUI (Graphical User Interface).
*   Advanced content-based triggers (Regex inside body).
*   Complex analytics (SQLite).

### **5. Design & User Experience**
*   **Output:** Flat YAML frontmatter in `.md` files for Obsidian/Dataview compatibility.
*   **Progress:** CLI progress bars showing "Fetching," "Parsing," and "AI Processing" steps with ETR.

### **6. Technical & Non-Functional Requirements**
*   **Observability:**
    *   **Override Logging:** On startup, the system must log `INFO: Account 'X' overriding 'Y'` for any changed parameters.
*   **Resilience:** The system must not crash on malformed YAML rules or bad HTML (see Fallback logic).
*   **Performance:** Initial IMAP search counts must be lightweight.

### **7. Future Work (V5+)**
*   Dedicated SQLite Analytics Pipeline.
*   Advanced "pre-LLM" content rules.
*   Topic/Entity Modeling.
