# V4 Documentation Guide

**Status:** Documentation Structure and Style Guide  
**Task:** 20.1  
**Purpose:** Define documentation structure, audience, tooling, and style guidelines for V4 documentation

---

## Documentation Overview

This guide defines the structure, audience, tooling, and style guidelines for V4 documentation. All V4 documentation should follow these guidelines for consistency and clarity.

---

## Target Audiences

### Primary Audiences

1. **Operators/System Administrators**
   - Installing and configuring V4
   - Setting up multi-account deployments
   - Troubleshooting operational issues
   - Managing configuration files
   - **Needs:** Installation guides, configuration reference, troubleshooting, best practices

2. **Developers/Rule Writers**
   - Writing blacklist and whitelist rules
   - Understanding rule syntax and patterns
   - Customizing processing behavior
   - **Needs:** Rule syntax reference, examples, pattern matching guide, rule best practices

3. **Existing V3 Users (Migrating)**
   - Understanding differences between V3 and V4
   - Migrating existing V3 configurations
   - Adapting workflows to V4 multi-account model
   - **Needs:** Migration guide, compatibility matrix, step-by-step migration checklist, V3→V4 mapping

4. **New Users**
   - First-time installation and setup
   - Understanding core concepts
   - Getting started quickly
   - **Needs:** Quick start guide, installation instructions, minimal working examples, core concepts

---

## Documentation Structure

### Main Documentation Sections

1. **Installation & Setup** (`v4-installation-setup.md`)
   - Prerequisites and system requirements
   - Installation steps (fresh install, upgrade from V3)
   - Initial configuration
   - Verification steps
   - Common installation issues

2. **Configuration Reference** (`v4-configuration-reference.md`)
   - Complete configuration schema
   - All configuration options (global and account-specific)
   - Configuration examples (single-account, multi-account, performance-tuned)
   - Configuration validation and troubleshooting

3. **Rule Syntax & Examples** (`v4-rule-syntax-guide.md`)
   - Complete rule syntax specification
   - Blacklist rule syntax and examples
   - Whitelist rule syntax and examples
   - Pattern matching (exact, regex, domain matching)
   - Rule best practices and patterns

4. **Command-Line Usage** (`v4-cli-usage.md`)
   - CLI command reference
   - Command options and flags
   - Common workflows and examples
   - Exit codes and error handling
   - Dry-run mode usage

5. **Migration Guide V3→V4** (`v4-migration-guide.md`)
   - Key differences between V3 and V4
   - Migration paths (in-place upgrade, parallel deployment)
   - Step-by-step migration checklist
   - Configuration mapping (V3 → V4)
   - Compatibility matrix
   - Migration troubleshooting

6. **Troubleshooting** (`v4-troubleshooting.md`)
   - Common issues and solutions
   - Configuration errors
   - Rule syntax errors
   - CLI errors
   - Multi-account issues
   - Advanced troubleshooting

7. **Multi-Account Best Practices** (`v4-multi-account-best-practices.md`)
   - Architecture patterns (centralized vs. per-account)
   - Configuration sharing strategies
   - Account isolation best practices
   - Security considerations
   - Performance optimization
   - Maintenance and monitoring

### Quick Reference Documents

- **Quick Start Guide** (`v4-quick-start.md`) - Minimal setup to get running quickly
- **Configuration Examples** (`v4-config-examples.md`) - Real-world configuration examples
- **Rule Examples** (`v4-rule-examples.md`) - Common rule patterns and examples

---

## Documentation Platform

### Platform Choice

- **Format:** Markdown (`.md` files) in repository
- **Location:** `docs/` directory
- **Naming Convention:** `v4-<topic>.md` for V4-specific docs
- **Versioning Strategy:** 
  - V3 docs: `v3-*.md` (existing, on `main` branch)
  - V4 docs: `v4-*.md` (new, on `v4-orchestrator` branch)
  - Clear separation between V3 and V4 content

### Navigation Structure

- **Main Index:** `docs/MAIN_DOCS.md` (updated to include V4 section)
- **V4 Section:** Dedicated V4 documentation section in `MAIN_DOCS.md`
- **Cross-References:** Links between related V4 docs and to V3 docs where relevant

### Documentation Maintenance

- **Update Process:** Documentation updated alongside code changes
- **Review:** Technical review for accuracy, usability review for clarity
- **Version Sync:** Documentation kept in sync with codebase changes

---

## Style Guide

### Tone and Voice

- **Professional but approachable:** Technical accuracy with clear explanations
- **User-focused:** Write from the user's perspective, not the system's
- **Action-oriented:** Use imperative mood for instructions ("Install...", "Configure...")
- **Concise:** Be clear and direct, avoid unnecessary verbosity

### Terminology

- **Consistent Terms:**
  - "Account" (not "tenant" or "user account") for email account configurations
  - "Global config" (not "base config" or "default config") for `config/config.yaml`
  - "Account config" (not "override config") for `config/accounts/*.yaml`
  - "Blacklist rule" and "Whitelist rule" (not "filter" or "policy")
  - "EmailContext" (capitalized) for the data class
  - "MasterOrchestrator" (capitalized) for the orchestrator class

- **Version References:**
  - "V3" and "V4" (capitalized, no spaces)
  - "V3 mode" and "V4 mode" when referring to operational modes

### Code Snippets

- **Format:** Use fenced code blocks with language specification
- **Completeness:** Show complete, runnable examples when possible
- **Context:** Include comments explaining key parts
- **File Paths:** Use relative paths from project root (e.g., `config/config.yaml`)

**Example:**
```yaml
# config/config.yaml - Global configuration
imap:
  server: "imap.example.com"
  port: 993
  username: "user@example.com"
```

### Configuration Examples

- **Minimal Examples:** Show the smallest working configuration
- **Full Examples:** Show complete configurations with all options
- **Real-World Examples:** Include practical, realistic scenarios
- **Comments:** Use YAML comments to explain non-obvious choices

### Command Examples

- **Format:** Show command with expected output
- **Context:** Include working directory and prerequisites
- **Output:** Show both success and error cases when relevant

**Example:**
```bash
# Process all accounts
python main.py process --all

# Expected output:
# INFO: Processing account: work
# INFO: Processing account: personal
# ...
```

### File Structure Examples

- **Tree Format:** Use ASCII tree structure for directory layouts
- **File Contents:** Show file paths and key contents
- **Annotations:** Use comments to explain structure

**Example:**
```
config/
├── config.yaml              # Global configuration
├── accounts/                # Account-specific configs
│   ├── work.yaml           # Work account config
│   └── personal.yaml       # Personal account config
├── blacklist.yaml          # Global blacklist rules
└── whitelist.yaml          # Global whitelist rules
```

### Cross-References

- **Internal Links:** Use relative Markdown links to other docs
- **Format:** `[Link Text](v4-other-doc.md#section)`
- **PDD References:** Reference PDD sections when relevant: `[pdd_V4.md](../pdd_V4.md) Section X.Y`

### Examples and Use Cases

- **Real-World Scenarios:** Use practical, relatable examples
- **Progressive Complexity:** Start simple, build to complex
- **Common Patterns:** Highlight frequently used patterns
- **Edge Cases:** Document important edge cases and gotchas

### Error Messages and Troubleshooting

- **Format:** Show actual error messages in code blocks
- **Context:** Explain when/why errors occur
- **Solutions:** Provide step-by-step solutions
- **Prevention:** Include prevention tips when applicable

---

## Documentation Checklist

When creating or updating V4 documentation:

- [ ] Follows style guide (tone, terminology, formatting)
- [ ] Includes practical examples
- [ ] Cross-references related documentation
- [ ] References PDD sections where applicable
- [ ] Includes troubleshooting information for common issues
- [ ] Uses consistent terminology throughout
- [ ] Code examples are complete and runnable
- [ ] File paths are relative to project root
- [ ] Navigation links are updated in `MAIN_DOCS.md`
- [ ] Version clearly indicated (V4 vs V3)

---

## Next Steps

After completing this structure guide:

1. **Subtask 20.2:** Document installation, setup, and core configuration
2. **Subtask 20.3:** Create detailed configuration, rule syntax, and CLI usage reference
3. **Subtask 20.4:** Develop V3→V4 migration guide and multi-account best practices
4. **Subtask 20.5:** Review, validate, and refine all V4 documentation

---

## Related Documentation

- [V4 Configuration System](v4-configuration.md) - Technical implementation details
- [V4 Rules Engine](v4-rules-engine.md) - Rules engine implementation
- [V4 Account Processor](v4-account-processor.md) - Account processing pipeline
- [PDD V4](../pdd_V4.md) - Product Design Document
- [Main Documentation Index](MAIN_DOCS.md) - Complete documentation index
