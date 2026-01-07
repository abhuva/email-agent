# Email Agent — Main Documentation Entry Point

This is the top-level guide for all docs, implementation details, and project strategy documents for the Headless AI Email Agent.

## Essential System Docs
- [README.md](../README.md) — The actual starting point and summary of all global system info.
- [pdd.md](../pdd.md) — Product Design Document V1 (✅ Complete), including business context, acceptance criteria, and non-technical requirements.
- [pdd_v2.md](../pdd_v2.md) — Product Design Document V2 (🚧 In Progress), outlining Obsidian integration and note creation features.

## User Guides
- **[Complete Guide](COMPLETE_GUIDE.md)** — Comprehensive user guide covering installation, configuration, usage, Obsidian integration, troubleshooting, and deployment (for end users).
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** — Detailed troubleshooting guide with solutions for common issues.

## Deep Dive Module Docs
- [Logging System](logging-system.md)
- [IMAP Fetching](imap-fetching.md)
- [Prompt Pipeline / Markdown Management](prompts.md)
- [Conditional Summarization System](summarization.md) (V2)
- [Task Master Project Management](../README-task-master.md)

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
2. Open [pdd_v2.md](../pdd_v2.md) for current V2 requirements and roadmap (we're working on V2 now).
3. Use Task Master CLI: `task-master list`, `task-master next` for current project todo/context state.
4. Browse module docs for implementation specifics and quick code/testing examples.

> **For Cursor or AI Agents:**
> - Always load this file and README.md first!
> - Then, review the PDD V2 and module docs as needed.
> - **Current Focus:** V2 (Obsidian Integration) - see [pdd_v2.md](../pdd_v2.md)

> **For End Users:**
> - Start with the [Complete Guide](COMPLETE_GUIDE.md) for installation and usage
> - Refer to [Troubleshooting Guide](TROUBLESHOOTING.md) if you encounter issues

---
*See README.md for FAQ, upgrade policy, and human+AI best practices.*