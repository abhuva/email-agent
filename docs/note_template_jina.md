
{# ============================================================================
   Processing Metadata Footer
   ============================================================================
   Footer showing when and how the email was processed. This helps with
   debugging and tracking processing history.
   ============================================================================ #}
---
*Processed on {{ processing_meta.processed_at }} using script version {{ processing_meta.script_version }}*

{# ============================================================================
   TEMPLATE USAGE DOCUMENTATION
   ============================================================================
   
   This section provides documentation for customizing this template. Since
   Jinja2 comments are stripped during rendering, this won't appear in the
   final output but is available for reference when editing the template.
   
   HOW THE TEMPLATE IS APPLIED:
   ----------------------------
   1. Email data is retrieved from IMAP server (via ImapClient)
   2. Email is classified using LLM (via LLMClient)
   3. Classification results are processed (via DecisionLogic)
   4. Template context is prepared with email data + classification results
   5. Template is rendered using Jinja2 (via NoteGenerator)
   6. Rendered Markdown is saved to Obsidian vault
   
   AVAILABLE VARIABLES:
   --------------------
   Email Data:
   - uid: str - Email UID from IMAP
   - subject: str - Email subject
   - from: str - Sender address
   - to: list[str] - Recipient addresses
   - date: str - Email date (various formats, use format_datetime filter)
   - body: str - Plain text email body
   - html_body: str - HTML email body (if available)
   - headers: dict - All email headers
   
   Classification Results:
   - is_important: bool - True if importance_score >= threshold
   - is_spam: bool - True if spam_score >= threshold
   - importance_score: int - 0-10 importance score (or -1 for errors)
   - spam_score: int - 0-10 spam score (or -1 for errors)
   - confidence: float - 0.0-1.0 confidence level
   - status: str - "success" or "error"
   - tags: list[str] - List of tags (includes "email", "important" if applicable)
   
   LLM Output (nested):
   - llm_output.importance_score: int
   - llm_output.spam_score: int
   - llm_output.model_used: str
   
   Processing Metadata (nested):
   - processing_meta.script_version: str (always "3.0")
   - processing_meta.processed_at: str (ISO timestamp)
   - processing_meta.status: str
   
   Configuration:
   - importance_threshold: int - Threshold for importance (default: 8)
   - spam_threshold: int - Threshold for spam (default: 5)
   
   CUSTOM JINJA2 FILTERS:
   ----------------------
   - format_date(value, format_str='%Y-%m-%d'): Format date string
   - format_datetime(value): Format to ISO datetime (YYYY-MM-DDTHH:MM:SSZ)
   - truncate(value, length=100): Truncate string with ellipsis
   - tojson: Convert to JSON (built-in Jinja2 filter)
   - join(separator): Join list with separator (built-in Jinja2 filter)
   
   CREATING CUSTOM TEMPLATES:
   --------------------------
   1. Copy this template to a new file (e.g., custom_template.md.j2)
   2. Modify the structure and formatting as needed
   3. Update config.yaml: paths.template_file: 'config/custom_template.md.j2'
   4. Test with: python main.py process --uid <email_uid> --dry-run
   
   BEST PRACTICES:
   ---------------
   - Always quote string values in YAML frontmatter to handle special characters
   - Use conditional blocks ({% if %}) to show/hide sections based on data
   - Test templates with various email types (important, spam, error cases)
   - Keep frontmatter structure aligned with PDD Section 3.2 specification
   - Use Jinja2 comments ({# ... #}) for documentation (they're stripped in output)
   - Escape user content properly (Jinja2 autoescape handles this for HTML)
   - Use filters for data transformation (format_date, truncate, etc.)
   
   TEMPLATE STRUCTURE:
   ------------------
   1. YAML Frontmatter (between --- markers)
      - Email identification (uid, subject, from, to, date)
      - Tags (automatically generated)
      - LLM output (scores, model)
      - Processing metadata (version, timestamp, status)
   
   2. Email Header Section
      - Subject as H1
      - Metadata (from, to, date)
   
   3. Classification Indicators
      - Conditional banners for important/spam/error
   
   4. Classification Details
      - Detailed scores and confidence (if successful)
   
   5. Email Body
      - Main content (plain text preferred, HTML fallback)
   
   6. Attachments
      - Placeholder for future attachment handling
   
   7. Footer
      - Processing metadata
   
   EXAMPLES:
   ---------
   Conditional rendering:
   {% if is_important %}
   > This email is important!
   {% endif %}
   
   Using filters:
   {{ date | format_datetime }}
   {{ body | truncate(200) }}
   
   Accessing nested data:
   {{ llm_output.model_used }}
   {{ processing_meta.processed_at }}
   
   Looping (if needed):
   {% for tag in tags %}
   - {{ tag }}
   {% endfor %}
   
   For more information, see:
   - PDD Section 3.2 (pdd.md) - Frontmatter specification
   - docs/v3-note-generator.md - Note generator documentation
   - Jinja2 Documentation: https://jinja.palletsprojects.com/
   ============================================================================ #}
