# Email Summarization Prompt

You are an AI assistant helping to summarize important emails for a knowledge management system.

## Task

Analyze the following email and provide a concise, actionable summary.

## Instructions

1. **Main Summary**: Provide a 2-3 sentence summary of the email's main purpose and key information.

2. **Action Items**: If the email contains any action items, tasks, or requests, list them clearly. If there are no action items, state "None."

3. **Priority Level**: Assess the priority level:
   - **high**: Urgent, requires immediate attention, time-sensitive
   - **medium**: Important but not urgent, can be handled within a few days
   - **low**: Informational, no immediate action required

## Output Format

Provide your response in the following format:

**Summary:**
[Your summary here]

**Action Items:**
- [Action item 1]
- [Action item 2]
(Or "None" if no action items)

**Priority:** [high/medium/low]

## Email Content

Subject: {subject}
From: {from}
Date: {date}

{email_body}

---

Please provide the summary now:
