# Email Agent (Headless AI Email Tagger)

## Overview
An extensible Python CLI agent connecting to IMAP accounts, fetching emails, tagging/classifying them via AI (OpenAI-compatible or Google/Gemini via OpenRouter), and logging every step. Built for robust team, audit, and production use.

---

## Quick Start
- **Configuration:** Copy `.env.example` to `.env`, add your credentials.
- **Run:** `python main.py` (for full agent) or `python src/openrouter_client.py` (for OpenRouter/AI test).
- **Docs:** Deep dive into specific modules below.

---

## Documentation Overview
- [Product Design Doc (PDD)](pdd.md) — Project strategy, requirements, roadmap.
- [Logging System](docs/logging-system.md) — Logger, analytics, config, test patterns, and CLI integration.
- [IMAP Email Fetching](docs/imap-fetching.md) — IMAP workflow, error handling, and orchestrator details.
- [Prompt Loader/Markdown Management](docs/prompts.md) — How AI prompts are loaded and managed.
- [Task Master Workflow](README-task-master.md) — AI-driven task/project management for long-lived development.

---

## Maintaining Context (Agent, AI, and Human)
> To restart after a break, or for Cursor AI:
>
> 1. Open this `README.md` and [pdd.md](pdd.md).
> 2. Run 
>    ```
>    task-master list
>    task-master next
>    ```
>    to see project state/tasks.
> 3. Review the doc links above for any system/module orientation.

*Don’t forget: Secrets and configs are in `.env` and `config/config.yaml`. See docs above for details.*

---

## FAQ
- **Switching models:** Edit `openrouter.model` in `config/config.yaml` (fallbacks provided).
- **Testing:** See module docs for pytest or CLI commands.
- **Upgrades:** See Task Master doc for workflow upgrades.
- **How do I restart the agent after a break?**
    - Reread this README and run the main CLI entry point.

---

> For AI agents: Always reread this file and the PDD before military-grade automation or code changes!