# Email Agent — Main Documentation Entry Point

This is the top-level guide for all docs, implementation details, and project strategy documents for the Headless AI Email Agent.

## Essential System Docs
- [README.md](../README.md) — The actual starting point and summary of all global system info.
- [pdd.md](../pdd.md) — Product Design Document V3 (✅ Complete, Current Version), foundational upgrade with score-based classification, CLI controls, and templating.
- [pdd_v2.md](../pdd_v2.md) — Product Design Document V2 (✅ Complete, Historical), outlining Obsidian integration and note creation features.
- [prd.md](../prd.md) — Product Requirements Document

## User Guides
- **[Complete Guide](COMPLETE_GUIDE.md)** — Comprehensive user guide covering installation, configuration, usage, Obsidian integration, troubleshooting, and deployment (for end users).
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** — Detailed troubleshooting guide with solutions for common issues.

## Deep Dive Module Docs

### V3 Module Documentation (Current)
- See V3 Module Documentation section below for comprehensive V3 docs

### Historical Module Documentation
- [Logging System](logging-system.md) — Detailed logging implementation (V1/V2)
- [IMAP Fetching](imap-fetching.md) — IMAP implementation details and patterns
- [Prompt Pipeline / Markdown Management](prompts.md) — Prompt management system
- [Conditional Summarization System](summarization.md) — Summarization system (V2, historical)
- [IMAP Keywords vs Flags](imap-keywords-vs-flags.md) — Technical explanation of IMAP flags
- [Live Test Guide](live-test-guide.md) — Guide for manual live testing
- [Task Master Project Management](../README-task-master.md) — Task management system

## V3 Module Documentation

### Core V3 Features
- **[V3 Configuration Guide](v3-configuration.md)** — V3 configuration system, schema, and settings facade (Task 1) ✅
- **[V3 Migration Guide](v3-migration-guide.md)** — Migrating from V2 to V3 configuration patterns ✅
- **[V3 CLI](v3-cli.md)** — Command-line interface with click (Task 2) ✅
- **[V3 IMAP Client](v3-imap-client.md)** — IMAP connection and email retrieval (Task 3) ✅
- **[V3 LLM Client](v3-llm-client.md)** — LLM API interactions with retry logic (Task 4) ✅
- **[Scoring Criteria](scoring-criteria.md)** — Email scoring criteria and thresholds (Task 5) ✅
- **[V3 Decision Logic](v3-decision-logic.md)** — Threshold-based classification system (Task 6) ✅
- **[V3 Note Generator](v3-note-generator.md)** — Jinja2 templating system for Markdown note generation (Tasks 7-8) ✅
- **[V3 Logging Integration](v3-logging-integration.md)** — Dual logging system (operational logs + structured analytics) (Task 9) ✅
- **[V3 Orchestrator](v3-orchestrator.md)** — High-level pipeline orchestration coordinating all components (Task 14) ✅

### V3 Advanced Features
- **[V3 Force-Reprocess](v3-force-reprocess.md)** — Force-reprocess capability for reprocessing already-processed emails (Task 12) ✅
- **[V3 Cleanup Flags](v3-cleanup-flags.md)** — Safeguarded command to remove application-specific IMAP flags (Task 13) ✅
- **[V3 Backfill](v3-backfill.md)** — Process historical emails with date range filtering, progress tracking, and throttling (Task 15) ✅
- **[V3 Dry-Run Mode](v3-dry-run.md)** — Preview processing without making changes ✅

### V3 Testing & CI/CD
- **[V3 E2E Tests](v3-e2e-tests.md)** — End-to-end tests with live IMAP connections (Task 18.9-18.11) ✅
- **[CI Integration](ci-integration.md)** — CI/CD configuration and test automation (Task 18.12) ✅
- **[Test Isolation Fix](test-isolation-fix.md)** — Settings singleton reset fixture for test isolation ✅

## Analysis & Reports
- **[Documentation Audit 2026](documentation-audit-2026.md)** — Comprehensive documentation audit and consolidation (Task 17) 🔄
- **[Code Cleanup Assessment 2026](code-cleanup-assessment-2026.md)** — Code quality assessment (Task 16.1) ✅
- **[V3 PDD Task Alignment](V3_PDD_TASK_ALIGNMENT_ANALYSIS.md)** — PDD task alignment analysis
- **[Documentation Consolidation Plan](DOCUMENTATION_CONSOLIDATION_PLAN.md)** — Documentation consolidation strategy

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
> - **Current Version:** V3 (Foundational Upgrade) - see [pdd.md](../pdd.md)
> - **V3 Status:** ✅ **Complete and Production-Ready** - All features implemented and tested (Tasks 1-18 complete)
>   - Core: Configuration, CLI, IMAP, LLM, Decision Logic, Note Generator, Logging, Orchestrator
>   - Advanced: Force-Reprocess, Cleanup Flags, Backfill, Dry-Run
>   - Testing: Comprehensive test suite with unit, integration, and E2E tests
>   - CI/CD: Automated testing and quality checks
> - **Historical Versions:** V1 and V2 are historical. V3 is the current production version.

> **For End Users:**
> - Start with the [Complete Guide](COMPLETE_GUIDE.md) for installation and usage
> - Refer to [Troubleshooting Guide](TROUBLESHOOTING.md) if you encounter issues

---
*See README.md for FAQ, upgrade policy, and human+AI best practices.*