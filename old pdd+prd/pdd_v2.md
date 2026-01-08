# **Product Design Document: Headless AI Email Agent (V2)**

*   **Document Status:** `Approved for Development`
*   **Author(s) & Stakeholders:** Marc Bielert (NICA e.V.), Strata (AI Strategist)

## **1. Overview & Strategy (The "Why")**

*   **Executive Summary:** This project (V2) extends the Headless AI Email Agent to automatically extract structured data (summaries, tasks, key entities) from important emails and create well-formatted, linkable Markdown notes directly within our team's Obsidian vault. This transforms high-priority emails from siloed alerts into integrated project assets, saving significant manual data entry and dramatically improving project context.
*   **Problem Statement:** While V1 successfully flags potentially important emails, this is only the first step. The team still bears the cognitive load of interpreting *why* an email is important, manually extracting actionable tasks or information, and copy-pasting that content into our project management system (Obsidian). This process is slow, inefficient, and creates a disconnect between our communication hub (email) and our knowledge hub (Obsidian). The value of the information remains trapped within the email client.
*   **Strategic Alignment:** V2 directly executes on the foundational vision outlined in V1: "transforming unstructured emails into structured, actionable insights." By building a direct bridge to Obsidian, we move from passive email *tagging* to active project *integration*. This creates a single source of truth for communication related to a project, fulfilling the core goal of making our project management system smarter and more automated.

## **2. The User & The Goal (The "Who" and "What Success Looks Like")**

*   **Target Audience / User Personas:**
    *   **Primary User (The Admin):** Marc, responsible for configuring and running the agent.
    *   **Secondary User (The Team Member):** The team who will now primarily interact with the agent's output (Obsidian notes) to find information and context.

### **Goals & Success Metrics**

#### **Product Goals (Agent Performance)**
*   **Note Creation Reliability:** The agent successfully creates a corresponding `.md` note in the `/emails` directory for **>99%** of targeted emails.
*   **Data Integrity:** The YAML frontmatter (sender, date, subject) in the generated notes has an accuracy rate of **100%**.
*   **Summary Quality:** Team members qualitatively report that the AI-generated summaries for 'Urgent' emails are "helpful and accurate" at least **80%** of the time.

#### **Business Goals (Team Impact)**
*   **Information Accessibility:** Dramatically reduce the time a team member spends finding and opening project-related emails. This will be measured qualitatively, with the goal of exceeding the cumbersome search experience in traditional email clients.
*   **Workflow Integration:** After one month, the team reports that using Obsidian to search/review emails has become a primary workflow for finding past communications.

#### **Counter-Metrics (What We Must Avoid)**
*   **Vault Contamination:** **Zero** files are ever created by the agent outside the designated `/emails` subdirectory.
*   **Critical Misinformation:** Fewer than **1 in 100** summaries contains a factually incorrect statement about the source email that could lead to a wrong action.
*   **Unpredictable Cost:** The agent **must** retain its hard-limit mechanism (`max_emails_per_run`) to ensure cost is always predictable and under user control per execution.

## **3. Scope & Requirements (The "What")**

### **3.1 Scope & Boundaries (V2)**

*   **In-Scope:**
    *   **Obsidian Note Creation:** For each processed email, create a `.md` file in a configurable, dedicated sub-directory.
    *   **YAML Frontmatter:** The `.md` file must contain a YAML frontmatter block with structured data from the email.
    *   **Email Body as Content:** The body of the email will be included as the main content of the `.md` file.
    *   **Conditional Summarization:** A second LLM call will be triggered for emails with specific tags to generate a summary.
    *   **Changelog Note:** Maintain a single `.md` file that logs all processed emails for easy auditing.
    *   **Flexible Processing Logic:** The agent's query logic will be made configurable to support advanced use cases beyond just `UNREAD` emails.

*   **Out-of-Scope:**
    *   **Automatic Project Linking:** The agent will not attempt to automatically associate an email note with a project note.
    *   **Advanced Content Analysis (V3):** The agent will not perform deep task extraction, contact parsing, or event creation.
    *   **Advanced Filtering/Spam Detection (V-Next):** Improving the initial classification is not part of V2.
    *   **Destructive Actions:** The agent will not move, delete, or modify original emails.

### **3.2 User Stories & Acceptance Criteria**

---
**Story 1: Email to Obsidian Note Generation**
> As **Marc (the Admin)**, I want the **agent to create a structured Markdown note in a dedicated Obsidian directory for each processed email**, so that **my team can find, read, and filter email content directly within our knowledge base.**

*   **AC 1: Configurable Location:** A root directory for new notes MUST be specified in `config.yaml` (e.g., `obsidian_vault_path: /path/to/vault/emails`). The script MUST fail with an error if this path does not exist.
*   **AC 2: File Naming Convention:** Each note's filename MUST be unique and human-readable, following a format like `YYYY-MM-DD-HHMMSS - <Sanitized-Subject>.md`.
*   **AC 3: YAML Frontmatter:** The note MUST begin with a YAML frontmatter block containing, at a minimum: `subject`, `from`, `to`, `cc`, `date`, and `source_message_id`.
*   **AC 4: Content Placement:** The sanitized email body MUST be placed after the YAML frontmatter and summary.
*   **AC 5: Idempotency Tag:** After *successfully* creating and saving a note, the agent MUST apply a new, dedicated IMAP tag (e.g., `[Obsidian-Note-Created]`).
*   **AC 6: Query Logic:** The IMAP query to find emails for this process MUST exclude emails already possessing the `[Obsidian-Note-Created]` tag.
*   **AC 7: Failure Handling:** If the agent fails to create/save the `.md` file (e.g., I/O error), it MUST NOT apply the success tag. Instead, it MUST apply a distinct failure tag (e.g., `[Note-Creation-Failed]`) to the email, log the error, and continue.

---
**Story 2: Conditional AI Summarization**
> As **Marc (the Admin)**, I want to **configure the agent to generate AI summaries for only a specific subset of emails**, so that I can **provide high-value insights while carefully managing API costs.**

*   **AC 1: Configurable Trigger:** `config.yaml` MUST contain `summarization_tags`, a list of IMAP tags that trigger the summary step.
*   **AC 2: Selective Execution:** The summarization LLM call MUST ONLY run if an email has a tag listed in `summarization_tags`.
*   **AC 3: Separate Prompt:** The prompt for summarization MUST be loaded from a separate file path specified in `config.yaml`.
*   **AC 4: Summary Placement:** The generated summary MUST be inserted into the note *after* the YAML frontmatter but *before* the email body, formatted as an Obsidian callout.
*   **AC 5: Robustness:** If summarization fails, the agent MUST log the error but still proceed with creating the base note.

---
**Story 3: Human-Readable Audit Log**
> As **Marc (the Admin)**, I want the **agent to append a summary of each processed email to a single Markdown 'Changelog' file**, so that I can **quickly find and verify which emails the agent has acted upon.**

*   **AC 1: Configurable Path:** The path to the changelog file MUST be defined in `config.yaml`.
*   **AC 2: Markdown Table Format:** The file should be a Markdown table where new rows are appended on each run.
*   **AC 3: Granular Detail:** Each row MUST contain `Timestamp`, `Email Account`, `Subject`, `From`, and the generated `Filename`.
*   **AC 4: Run Grouping:** Each execution run should be visually separated in the log.

---
**Story 4: Flexible Email Selection Logic**
> As **Marc (the Admin)**, I want to **define what emails to process using a flexible IMAP query in the config file**, so that I can **reliably re-process historical emails or create targeted workflows.**

*   **AC 1: Configurable Query:** `config.yaml` MUST contain the primary `imap_query` string (e.g., `'(UNSEEN)'` or `'(SINCE "01-Jan-2024")'`).
*   **AC 2: Preserved Idempotency:** The query sent to the server MUST be an `AND` combination of the user-defined `imap_query` and the check to exclude already-processed emails.

## **4. Design & User Experience (UX)**

*   **CLI User Experience:** The terminal UI remains simple: a progress bar during execution and an updated final summary report detailing `Notes Created`, `Summaries Generated`, and `Note Creation Failures`.
*   **Obsidian Note Structure:** The structure of the generated `.md` file is the core design:

    ```markdown
    ---
    subject: Project Alpha - Weekly Update & Action Items
    from: client@example.com
    to: marc@myteam.com
    date: 2023-10-27T10:00:00Z
    source_message_id: <CAKdfgkj34s...@mail.gmail.com>
    ---
    
    >[!info]+ Summary
    > The client provided a weekly update for Project Alpha. Key action items include updating the deployment script by Monday and sending them the revised mockups.
    
    ## Original Content
    
    Hi Marc,
    
    Just wanted to send over the weekly update...
    *(...rest of the sanitized email body converted to Markdown...)*
    ```

## **5. Technical & Non-Functional Requirements**

*   **Technical Considerations:** The file-writing mechanism must robustly handle I/O Errors and permission issues, aligning with Story #1, AC #7.
*   **Data & Analytics:** The `analytics_file` JSON schema will be updated to:
    ```json
    {"timestamp": "...", "total_processed": N, "notes_created": N, "summaries_generated": N, "note_creation_failures": N}
    ```
*   **Dependencies:** The agent now has a critical dependency on file system write access to the configured `obsidian_vault_path`.

## **6. Go-Live Plan & Future Work**

*   **Go-Live & Rollout Plan:**
    *   **Phase 1 (Alpha Test):** V2 will be tested exclusively on the Primary User's personal email account to validate functionality and cost.
    *   **Phase 2 (Team Briefing):** A formal team demonstration will set expectations, clarifying that this tool is an **additional information source**, not a replacement for an email client. The primary source of truth remains the email server.
    *   **Phase 3 (Staged Rollout):** The agent will be configured for shared inboxes one at a time.

*   **Future Iterations (The Roadmap):**
    *   **V3: Intelligent Linking & Structuring:** Implement automatic project linking and advanced content analysis (task extraction).
    *   **V-Next: Curation & System Health:** build features for signal-to-noise reduction and content lifecycle management. Introduce a dedicated **"Note Migration/Processing Tool"** to perform bulk updates on existing notes (e.g., adding new YAML fields).

*   **Open Questions & Risks:**
    *   **Accepted Risk: Vault Pollution:** Creating a note for every non-spam email may lead to a high volume of low-value notes. This is accepted for V2 and will be monitored.
    *   **Boundary: Non-Text Content:** The agent will strip inline images and will not process attachments.