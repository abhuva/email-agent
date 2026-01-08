# Email Agent — Main Documentation Entry Point

This is the top-level guide for all docs, implementation details, and project strategy documents for the Headless AI Email Agent.

## Essential System Docs
- [README.md](../README.md) — The actual starting point and summary of all global system info.
- [pdd.md](../pdd.md) — Product Design Document V3 (✅ In Progress), foundational upgrade with score-based classification, CLI controls, and templating.
- [pdd_v2.md](../pdd_v2.md) — Product Design Document V2 (✅ Complete), outlining Obsidian integration and note creation features.

## User Guides
- **[Complete Guide](COMPLETE_GUIDE.md)** — Comprehensive user guide covering installation, configuration, usage, Obsidian integration, troubleshooting, and deployment (for end users).
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** — Detailed troubleshooting guide with solutions for common issues.

## Deep Dive Module Docs
- [Logging System](logging-system.md)
- [IMAP Fetching](imap-fetching.md)
- [Prompt Pipeline / Markdown Management](prompts.md)
- [Conditional Summarization System](summarization.md) (V2)
- [Task Master Project Management](../README-task-master.md)

## V3 Module Documentation
- **[V3 Configuration Guide](v3-configuration.md)** — V3 configuration system, schema, and settings facade (Task 1)
- **[V3 Migration Guide](v3-migration-guide.md)** — Migrating from V2 to V3 configuration patterns
- **[V3 CLI](v3-cli.md)** — Command-line interface with click (Task 2)
- **[V3 IMAP Client](v3-imap-client.md)** — IMAP connection and email retrieval (Task 3)
- **[V3 LLM Client](v3-llm-client.md)** — LLM API interactions with retry logic (Task 4)
- **[Scoring Criteria](scoring-criteria.md)** — Email scoring criteria and thresholds (Task 5)
- **[V3 Decision Logic](v3-decision-logic.md)** — Threshold-based classification system (Task 6)
- **[V3 Note Generator](v3-note-generator.md)** — Jinja2 templating system for Markdown note generation (Tasks 7-8)
- **[V3 Logging Integration](v3-logging-integration.md)** — Dual logging system (operational logs + structured analytics) (Task 9)
- **[V3 Force-Reprocess](v3-force-reprocess.md)** — Force-reprocess capability for reprocessing already-processed emails (Task 12)
- **[V3 Orchestrator](v3-orchestrator.md)** — High-level pipeline orchestration coordinating all components (Task 14.1)

## Historical Documentation
The following documents provide historical context and implementation decisions:
- [Refactoring Flags Plan](refactoring-flags-plan.md) — Historical refactoring plan for IMAP flags
- [Refactoring Flags Summary](refactoring-flags-summary.md) — Summary of flags refactoring
- [Code Review 2026-01](CODE_REVIEW_2026-01.md) — Code review findings and cleanup
- [Task 16 Proposal](TASK_16_PROPOSAL.md) — IMAP query filtering system proposal
- [Cleanup Report 2026-01](CLEANUP_REPORT_2026-01.md) — Codebase cleanup analysis
- [Cleanup Verification Report](CLEANUP_VERIFICATION_REPORT.md) — Cleanup verification results

## Onboarding / Loading AI Context
1. Read the [README](../README.md) for system structure and tasking.
2. Open [pdd.md](../pdd.md) for current V3 requirements and roadmap (we're working on V3 now).
3. Use Task Master CLI: `task-master list`, `task-master next` for current project todo/context state.
4. Browse module docs for implementation specifics and quick code/testing examples.

> **For Cursor or AI Agents:**
> - Always load this file and README.md first!
> - Then, review the PDD V3 and module docs as needed.
> - **Current Focus:** V3 (Foundational Upgrade) - see [pdd.md](../pdd.md)
> - **V3 Status:** Tasks 1-9 complete (Configuration, CLI, IMAP, LLM, Prompts, Decision Logic, Templating, Logging)

> **For End Users:**
> - Start with the [Complete Guide](COMPLETE_GUIDE.md) for installation and usage
> - Refer to [Troubleshooting Guide](TROUBLESHOOTING.md) if you encounter issues

---
*See README.md for FAQ, upgrade policy, and human+AI best practices.*