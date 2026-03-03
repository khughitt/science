# CLAUDE.md Template Reference

> **Instructions for the agent:** When creating a new project's `CLAUDE.md`, adapt the
> content below the "Template content starts below" marker. Replace all `{{placeholders}}`
> with project-specific values. Do not include this instruction header in the output.

---
<!-- ═══ Template content starts below ═══ -->

# Project: {{project_name}}

## Overview

{{One paragraph describing the research question and project scope.}}

## Automatic Skill Triggers

Before performing any of the following tasks, read the corresponding skill:

- **Writing any document in `doc/` or `papers/summaries/`:** Read the `scientific-writing` skill
- **Literature review, source evaluation, paper summarization:** Read the `research-methodology` skill
- **Working with data sources or data acquisition:** Read the `data-management` skill (when available)
- **Pipeline work (Snakemake, analysis scripts):** Read the `pipelines` skill (when available)
- **Causal modeling or DAG construction:** Read the `causal-dag` skill (when available)
- **Knowledge graph work:** Read the `knowledge-graph` skill (when available)

## Role Prompt Packs

Use role prompt packs for capability-first workflows:

- `prompts/roles/research-assistant.md` for research/synthesis/prioritization tasks
  (`/science:research-paper`, `/science:research-topic`, `/science:research-gaps`, `/science:review-tasks`)
- `prompts/roles/discussant.md` for critical discussion tasks
  (`/science:discuss`, including optional double-blind mode)

If these files are missing (older project), fall back to plugin references:
`${CLAUDE_PLUGIN_ROOT}/references/role-prompts/*.md`.

## Paper Summarization Order

When summarizing papers, always follow this priority:
1. **LLM knowledge first** — start from what you know
2. **Web search second** — verify key facts, find recent work
3. **PDF last** — only when user provides a file path

Always cross-check: author lists, publication year, specific numerical results, method details.

## Document Conventions

- Use templates from `templates/` for all new documents
- Run `bash validate.sh` before committing
- Commit after each completed unit of work with descriptive messages
- Use commit format: `<scope>: <description>` (e.g., `doc: add background on X`)
- Every factual claim needs a citation; use BibTeX keys `[@AuthorYear]`
- Mark unverified facts with `[UNVERIFIED]` and unsourced claims with `[NEEDS CITATION]`

## Cross-Referencing

When writing about any topic:
1. Check `specs/hypotheses/` — does this connect to a hypothesis?
2. Check `doc/08-open-questions.md` — does this address or raise a question?
3. Check `doc/background/` — has this been covered? Don't duplicate.
4. Check `papers/summaries/` — have we reviewed relevant papers?

## Project State Files

- `RESEARCH_PLAN.md` — current investigation queue. Update with discoveries.
- `AGENTS.md` — operational guide. Update with new tools or conventions.
- `science.yaml` — project manifest. Update `last_modified` on significant changes.
