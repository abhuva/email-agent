# V3 PDD vs Generated Tasks Alignment Analysis

**Date:** 2026-01-12  
**Purpose:** Identify misalignments and missing requirements between the PDD and generated tasks

## Executive Summary

The generated tasks from the PRD are generally well-aligned with the PDD, but there are several **critical architectural components** and **specific technical details** that need to be added or clarified in the tasks.

---

## Critical Missing Components

### 1. **`settings.py` Facade (HIGH PRIORITY)**

**PDD Requirement (Section 2, 5.2):**
- "The system is architected around a central **Configuration Facade (`settings.py`)** which is the sole module responsible for loading and providing access to parameters from `config.yaml`."
- "All other application modules retrieve configuration through this facade, decoupling them from the YAML file's structure."

**Current Task Status:**
- Task 1 mentions configuration loading but doesn't explicitly call out the **facade pattern** or the need for a dedicated `settings.py` module
- The PDD explicitly states this should be a separate step (PDD Section 5, point 2)

**Required Action:**
- Add a new subtask to Task 1 or create a separate Task 1.5: "Create `settings.py` Configuration Facade"
- This facade should provide getter methods like:
  - `settings.get_openrouter_api_url()`
  - `settings.get_openrouter_api_key()`
  - `settings.get_imap_server()`
  - etc.

**Impact:** This is a foundational architectural decision that affects all other modules.

---

### 2. **Refactor App to Use Facade (HIGH PRIORITY)**

**PDD Requirement (Section 5, point 3):**
- "Systematically replace all direct `config['key']` access across the codebase with calls to the new `settings.py` getters."

**Current Task Status:**
- Not explicitly mentioned in any task
- This is a significant refactoring effort that should be its own task or major subtask

**Required Action:**
- Add Task 1.6 or Task 2: "Refactor existing codebase to use `settings.py` facade"
- This should include:
  - Finding all direct config access patterns
  - Replacing with facade method calls
  - Updating tests
  - Ensuring backward compatibility during transition

**Impact:** Required for V3 architecture compliance.

---

### 3. **Modular Structure - Specific Module Names**

**PDD Requirement (Section 5, point 4):**
- Specific module names are specified:
  - `src/orchestrator.py`: High-level business logic
  - `src/imap_client.py`: IMAP interactions
  - `src/llm_client.py`: LLM API interactions and retry logic
  - `src/note_generator.py`: Jinja2 template rendering
  - `src/logger.py`: Logging and analytics

**Current Task Status:**
- Tasks mention modules but don't use these specific names
- Task 3 mentions "IMAP client module" but not `imap_client.py`
- Task 4 mentions "LLM client" but not `llm_client.py`
- Task 7 mentions templating but not `note_generator.py`
- No mention of `orchestrator.py` for high-level business logic

**Required Action:**
- Update task details to specify exact module names
- Add Task 14.1 should explicitly mention `orchestrator.py` for high-level orchestration

**Impact:** Ensures consistency with PDD architecture.

---

## Configuration Schema Misalignments

### 4. **Configuration Section Names**

**PDD Requirement (Section 3.1):**
```yaml
imap:
paths:
openrouter:
processing:
```

**Current Task Status:**
- Task 1 mentions sections like `[api]`, `[imap]`, `[thresholds]`, `[paths]`, `[llm]`
- PDD uses `openrouter` (not `api` or `llm`)
- PDD uses `processing` (not `thresholds`)

**Required Action:**
- Update Task 1 to match PDD schema exactly:
  - `imap` ✓
  - `paths` ✓
  - `openrouter` (not `api` or `llm`)
  - `processing` (not `thresholds`)

**Impact:** Configuration structure must match PDD exactly.

---

### 5. **Specific Configuration Parameters**

**PDD Requirements (Section 3.1):**
- `imap.processed_tag: 'AIProcessed'` - explicitly mentioned
- `paths.template_file: 'config/note_template.md.j2'` - specific path
- `paths.prompt_file: 'config/prompt.md'` - specific path
- `openrouter.retry_attempts: 3` - specific value
- `openrouter.retry_delay_seconds: 5` - specific value
- `processing.importance_threshold: 8` - specific value
- `processing.spam_threshold: 5` - specific value
- `processing.max_body_chars: 4000` - specific value
- `processing.max_emails_per_run: 15` - specific value

**Current Task Status:**
- Tasks mention these parameters but don't specify exact values or paths
- Missing explicit mention of `processed_tag` in imap section

**Required Action:**
- Update Task 1 subtasks to include these specific parameters with their default values
- Ensure all paths match PDD specification

**Impact:** Ensures configuration matches PDD exactly.

---

## CLI Design Misalignments

### 6. **CLI Command Structure**

**PDD Requirement (Section 6):**
- `python main.py process`: Main command for bulk or single processing
  - `--uid <ID>`: Target a single email
  - `--force-reprocess`: Ignore existing `processed_tag`
  - `--dry-run`: Output to console instead of writing files/setting flags
- `python main.py cleanup-flags`: Maintenance command with confirmation prompt

**Current Task Status:**
- Task 2 mentions flags but doesn't explicitly structure as `process` subcommand
- The PDD shows `process` as a subcommand, not just flags on main command

**Required Action:**
- Update Task 2 to clarify CLI structure:
  - Main command: `python main.py process` (with flags)
  - Subcommand: `python main.py cleanup-flags`
- Ensure click library is used (PDD Section 5, point 1: "Refactor CLI from `argparse` to `click`")

**Impact:** CLI structure must match PDD specification.

---

### 7. **CLI Library: argparse vs click**

**PDD Requirement (Section 5, point 1):**
- "Refactor CLI from `argparse` to `click`"

**Current Task Status:**
- Task 2 subtask 1 says "argparse or click" - should be explicit: **click only**

**Required Action:**
- Update Task 2.1 to specify **click** library only
- Note that this is a refactoring from existing argparse implementation

**Impact:** Must use click for subcommands and interactive prompts.

---

## API Contract Details

### 8. **LLM API Contract Specifics**

**PDD Requirement (Section 4):**
- Endpoint: `POST` to URL from `settings.get_openrouter_api_url()`
- Auth: `Bearer` token via `settings.get_openrouter_api_key()`
- Request: JSON payload with `model`, `temperature`, and messages
- Response: String of JSON containing `{"spam_score": <int>, "importance_score": <int>}`
- Error handling: Retry N times, then generate note with error values (-1) and error status

**Current Task Status:**
- Task 4 covers LLM interaction but doesn't explicitly mention:
  - Using `settings.get_openrouter_api_url()` (depends on settings.py facade)
  - Using `settings.get_openrouter_api_key()` (depends on settings.py facade)
  - Specific error values (-1) for failed processing

**Required Action:**
- Update Task 4 to reference settings.py facade methods
- Update Task 10 to explicitly mention error values (-1) for spam_score and importance_score

**Impact:** API contract must match PDD exactly.

---

## Output Schema Details

### 9. **Markdown Frontmatter Schema**

**PDD Requirement (Section 3.2):**
```yaml
---
uid: 12345
subject: "..."
from: "..."
to: ["..."]
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

**Current Task Status:**
- Task 8 mentions frontmatter but doesn't specify the exact structure
- Missing explicit mention of:
  - `llm_output` section with `model_used`
  - `processing_meta` section with `script_version`, `processed_at`, `status`
  - Dynamic tag addition based on thresholds

**Required Action:**
- Update Task 8.1 to include exact frontmatter structure from PDD
- Add logic for dynamic tag addition in Task 8.3

**Impact:** Output format must match PDD specification.

---

## Non-Functional Requirements

### 10. **Performance Requirements**

**PDD Requirement (Section 7):**
- "Local operations should be < 1s; no memory leaks during batch processing"

**Current Task Status:**
- Not mentioned in any task

**Required Action:**
- Add performance requirements to Task 14 (integration task)
- Consider adding performance testing subtask

**Impact:** Ensures system meets performance requirements.

---

### 11. **Security Requirements**

**PDD Requirement (Section 7):**
- "Credentials **must** be loaded from environment variables"
- "The `cleanup-flags` command **must** have a mandatory confirmation prompt"

**Current Task Status:**
- Task 1 mentions environment variables but doesn't emphasize "must"
- Task 13 mentions confirmation prompt but doesn't emphasize "must"

**Required Action:**
- Update Task 1 to emphasize credentials MUST come from env vars
- Update Task 13 to emphasize confirmation prompt is MANDATORY

**Impact:** Security compliance.

---

### 12. **Observability Requirements**

**PDD Requirement (Section 7):**
- "Unstructured operational logs to `agent.log`"
- "Structured `uid, timestamp, status, scores` to `analytics.jsonl` for every processed email"

**Current Task Status:**
- Task 9 mentions logging but doesn't specify:
  - Separate unstructured logs vs structured analytics
  - Specific fields for analytics.jsonl

**Required Action:**
- Update Task 9 to specify:
  - Operational logs → `agent.log` (unstructured)
  - Analytics → `analytics.jsonl` (structured: uid, timestamp, status, scores)
  - Both must be written for every processed email

**Impact:** Observability compliance.

---

## Testing Requirements

### 13. **Testing Strategy**

**PDD Requirement (Section 7):**
- "Unit tests with mocks for each module"
- "Integration tests leveraging the `--dry-run` feature"

**Current Task Status:**
- Tasks mention testing but don't explicitly call out:
  - Mocking requirements for each module
  - Using `--dry-run` for integration tests

**Required Action:**
- Add testing subtasks to relevant tasks emphasizing:
  - Unit tests with mocks
  - Integration tests using `--dry-run`

**Impact:** Testing compliance.

---

## Deployment & Rollout

### 14. **Deployment Steps**

**PDD Requirement (Section 8):**
1. Code Merge: Merge V3 feature branch into `main`
2. Dependencies: Run `pip install click jinja2`
3. Configuration: Update `config.yaml` to new V3 structure
4. Test Run: Execute test run on single UID with `--force-reprocess`
5. Live Operation: Script ready for use
6. (Optional) Backfill: Run script in bulk mode

**Current Task Status:**
- No deployment task exists

**Required Action:**
- Consider adding Task 16: "Deployment and Rollout" with these steps
- Or add as subtasks to Task 14/15

**Impact:** Ensures smooth deployment.

---

## Summary of Required Actions

### High Priority (Must Fix):
1. ✅ Add `settings.py` facade as separate task/subtask
2. ✅ Add refactoring task to replace direct config access
3. ✅ Update configuration schema to match PDD exactly (`openrouter`, `processing`)
4. ✅ Specify exact module names (`orchestrator.py`, `imap_client.py`, etc.)
5. ✅ Update CLI structure to use `process` subcommand with click
6. ✅ Update frontmatter schema to match PDD exactly

### Medium Priority (Should Fix):
7. ✅ Specify exact configuration parameter values and paths
8. ✅ Update LLM API contract to reference settings.py facade
9. ✅ Add performance requirements
10. ✅ Specify observability requirements (agent.log vs analytics.jsonl)
11. ✅ Add deployment/rollout task

### Low Priority (Nice to Have):
12. ✅ Emphasize security requirements
13. ✅ Add testing strategy details

---

## Recommended Task Updates

### Task 1: Add Subtask
- **1.6:** "Create `settings.py` Configuration Facade with getter methods"
- **1.7:** "Refactor existing codebase to use `settings.py` facade (replace all direct config access)"

### Task 2: Update Details
- Specify **click** library only (not argparse)
- Structure as `python main.py process` with flags
- Subcommand: `python main.py cleanup-flags`

### Task 3: Update Module Name
- Specify module name: `src/imap_client.py`

### Task 4: Update Details
- Reference `settings.get_openrouter_api_url()` and `settings.get_openrouter_api_key()`
- Specify module name: `src/llm_client.py`

### Task 7: Update Module Name
- Specify module name: `src/note_generator.py`

### Task 8: Update Frontmatter
- Include exact PDD frontmatter structure with `llm_output` and `processing_meta` sections

### Task 9: Update Observability
- Specify separate unstructured logs (`agent.log`) and structured analytics (`analytics.jsonl`)

### Task 14: Add Orchestrator
- Add subtask: "Create `src/orchestrator.py` for high-level business logic orchestration"

---

## Conclusion

The generated tasks provide a solid foundation, but several **critical architectural components** from the PDD need to be explicitly added:

1. **`settings.py` facade** - This is a core architectural requirement
2. **Refactoring existing code** - Required to use the facade
3. **Exact configuration schema** - Must match PDD
4. **Specific module names** - For consistency
5. **CLI structure** - Must use click with `process` subcommand

These updates will ensure the implementation matches the PDD specification exactly.
