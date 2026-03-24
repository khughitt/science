# Import Project Command Design

**Date:** 2026-03-09
**Status:** Approved

## Problem

Science's `create-project` command scaffolds a new project from scratch. Many research
efforts already exist as established projects with their own directory structures, docs,
and code. There is no way to adopt Science for an existing project without manually
recreating its infrastructure.

## Solution

A new `import-project` command that adds Science research framework infrastructure to an
existing project directory. It discovers the current layout, maps existing directories to
Science conventions, scaffolds only what's missing, and extends (never replaces) existing
configuration files.

## Key Design Principles

- **Additive only** — never overwrites or restructures existing files
- **Mapping over convention** — existing `docs/` stays `docs/`, Science just knows where to look
- **Single source of truth** — `science.yaml` `paths:` section, read by all consumers
- **Graceful defaults** — unlisted paths fall back to standard Science layout

## Path Categories

### Tier 1: Must Create (Science-specific, no existing equivalent)

- `science.yaml` — project manifest with path mappings
- `tasks/active.md` — task queue
- `validate.sh` — validation script
- `templates/` — document templates (copied from plugin)

### Tier 2: Create If No Equivalent Exists, Otherwise Map

| Science expects | Possible equivalents |
|---|---|
| `doc/` | `docs/`, `documentation/` |
| `code/` | `src/`, `lib/`, `app/` |
| `data/` | `data/`, `datasets/` |
| `models/` | `src/models/`, `models/` |
| `papers/references.bib` | existing `.bib` files |
| `CLAUDE.md` | existing `CLAUDE.md` |
| `AGENTS.md` | existing `AGENTS.md` |

### Tier 3: Create as New Science-Specific Directories

- `specs/` (research-question.md, scope-boundaries.md, hypotheses/)
- `knowledge/` (graph.trig — only when KG features are used)
- `prompts/roles/`
- `doc/meta/` (feedback logs, placed in mapped doc_dir)
- `notes/`

## Import Flow

### Step 1: Discovery

- Confirm we're in an existing project root (package.json, pyproject.toml, .git, etc.)
- Warn if `science.yaml` already exists (already imported)
- Scan directory structure to identify existing equivalents for Tier 2 paths

### Step 2: Interactive Mapping

Present discovered structure and ask the user to confirm/adjust:

```
Found existing project structure:
  docs/          → will map as doc_dir
  src/           → will map as code_dir
  CLAUDE.md      → will extend (not replace)
  AGENTS.md      → will extend (not replace)

No equivalent found for:
  papers/        → will create
  specs/         → will create
  data/          → will create
```

### Step 3: Gather Research Context

- Research question (what is this project investigating?)
- Summary (2-3 sentences)
- Tags
- Status (likely `active`)

### Step 4: Create Science Infrastructure

- Write `science.yaml` with `paths:` section
- Create Tier 1 files
- Create Tier 3 directories
- Create `specs/research-question.md` and `specs/scope-boundaries.md`
- Copy role prompts from plugin
- **Extend** existing CLAUDE.md/AGENTS.md with Science sections

### Step 5: Initial Content Seeding (Optional)

- Populate `specs/research-question.md` from existing planning docs
- Create `papers/references.bib` from any existing citations
- Draft `RESEARCH_PLAN.md` summarizing current project state

### Step 6: Validate & Summarize

- Run `validate.sh` (respecting path mappings)
- Report what was created, mapped, and skipped
- Suggest next Science commands

## science.yaml Paths Section

```yaml
name: natural-systems-guide
created: 2026-03-09
status: active
summary: "..."
tags: [...]
paths:
  doc_dir: docs/
  code_dir: src/
  data_dir: data/
  models_dir: src/natural/registry/
  # Unlisted keys use standard Science defaults:
  # specs_dir: specs/
  # papers_dir: papers/
  # knowledge_dir: knowledge/
  # tasks_dir: tasks/
  # templates_dir: templates/
  # prompts_dir: prompts/
```

## Supported Path Keys

| Key | Default | Description |
|---|---|---|
| `doc_dir` | `doc/` | Research documents, topics, summaries |
| `code_dir` | `code/` | Scripts, notebooks, pipelines |
| `data_dir` | `data/` | Raw and processed data |
| `models_dir` | `models/` | Model definitions and DAGs |
| `specs_dir` | `specs/` | Research question, hypotheses |
| `papers_dir` | `papers/` | References and paper summaries |
| `knowledge_dir` | `knowledge/` | Knowledge graph |
| `tasks_dir` | `tasks/` | Task queue |
| `templates_dir` | `templates/` | Document templates |
| `prompts_dir` | `prompts/` | Role prompts |

## CLAUDE.md Extension

Appended to existing CLAUDE.md (never replaces):

```markdown
## Science Project

This project uses the Science research framework.
See `science.yaml` for project manifest and path mappings.

Key path mappings:
- Research docs: `docs/` (mapped from Science `doc/`)
- Code: `src/` (mapped from Science `code/`)
- Specs: `specs/` (Science standard)
- Papers: `papers/` (Science standard)
```

## Implementation Changes

### New Files

| File | Purpose |
|---|---|
| `commands/import-project.md` | The import command |

### Modified Files

| File | Change |
|---|---|
| `scripts/validate.sh` | Read `paths:` from science.yaml, use variables instead of hardcoded paths |
| `references/command-preamble.md` | Add path resolution step (propagates to all commands) |
| `references/project-structure.md` | Document imported project layouts |
| `references/science-yaml-schema.md` | Add `paths:` section to schema |
| `science-tool/src/science_tool/cli.py` | Resolve paths from science.yaml config |
| `science-tool/src/science_tool/store.py` | Resolve graph path from config |
| `commands/create-project.md` | Cross-reference import-project |
