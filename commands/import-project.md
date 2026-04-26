---
description: Migrate an existing repository into one of the two supported Science project profiles (`research` or `software`). Use when a pre-existing project wants to adopt Science and converge on the canonical layout.
---

# Import An Existing Project Into Science

You are migrating an existing repository into the canonical Science model.

This command is not a long-term path-mapping escape hatch.
Its job is to move the project toward one of the two supported steady-state profiles:

- `research`
- `software`

## Step 0: Pre-Flight Checks

1. Confirm you are inside an existing project root.
2. Read existing `AGENTS.md`, `CLAUDE.md`, `README.md`, and core project manifests if present.
3. If `science.yaml` already exists, treat this as a migration/refinement of an existing Science-managed project rather than a fresh import.
4. Do not auto-commit. The user should review migration changes before commit.

## Step 1: Audit The Existing Structure

Scan the repository and identify:

- documentation roots (`doc/`, `docs/`, `notes/`, `guide/`)
- implementation roots (`src/`, `code/`, `scripts/`, `workflow/`, `notebooks/`)
- bibliography roots (`papers/`, `.bib` files)
- AI artifact roots (`prompts/`, `templates/`, `.ai/`)
- archived material (`archive/`)

Present the findings and recommend a target profile:

- use `research` for research-first repositories
- use `software` for tools/apps/libraries/CLIs, even if they retain some research context

Ask the user to confirm the target profile if it is not already obvious.

## Step 2: Gather Project Context

Gather or infer:

1. Summary
2. Tags
3. Aspects
4. Data sources
5. Knowledge graph usage (`knowledge_profiles`)

If the target profile is `research`, also gather:

1. Research question
2. Scope boundaries
3. Whether an installable package should remain in root `src/`

## Step 3: Migrate Toward The Canonical Layout

### Common Migration Rules

- `doc/` becomes the canonical root for Science-managed documents
- `CLAUDE.md` becomes `@AGENTS.md`
- root `pyproject.toml` is the home for project-local Science tooling
- `.ai/` is for project-specific prompt/template overrides only
- framework prompt/template defaults are not copied into the project
- `archive/` is allowed for superseded material

### If Target Profile Is `research`

Target structure:

```text
project/
├── science.yaml
├── pyproject.toml
├── AGENTS.md
├── CLAUDE.md
├── doc/
├── tasks/
├── specs/
├── knowledge/
├── code/
│   ├── scripts/
│   ├── notebooks/
│   └── workflows/
├── data/
├── results/
├── models/
└── papers/
```

If the project has an installable Python package, preserve:

```text
project/
├── src/
└── tests/
```

Do not move package code under `code/`.

### If Target Profile Is `software`

Target structure:

```text
project/
├── science.yaml
├── pyproject.toml
├── AGENTS.md
├── CLAUDE.md
├── doc/
├── tasks/
├── specs/
├── knowledge/
├── src/
└── tests/
```

Keep framework-native roots natural for the stack:

- `public/`
- `scripts/`
- `assets/`
- application/toolchain files

Do not introduce `code/` just to satisfy symmetry.

## Step 4: Populate Or Update Core Files

### `science.yaml`

Create or update:

```yaml
name: "<project-name>"
created: "<original project creation date if known, else today>"
last_modified: "<today YYYY-MM-DD>"
summary: "<from conversation>"
status: "active"
profile: "<research-or-software>"
layout_version: 2
tags: []
data_sources: []
ontologies: []
knowledge_profiles:
  local: local
aspects: []
```

Do not add broad `paths:` mappings as the long-term solution.

### `pyproject.toml`

Create or update the root tool manifest so Science tooling is installed locally for every project.
If the repository already has a root `pyproject.toml`, extend it. Otherwise create a minimal tool-only manifest.
This applies even to non-Python repos because the manifest is for project-local tooling, not the app runtime.

Minimum shape:

```toml
[project]
name = "<project-slug>-science-tools"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = []
```

Install `science-tool` into the manifest with:

```bash
uv add --dev --editable "$SCIENCE_TOOL_PATH"
```

### `.env`

Create or update `.env` with the **resolved absolute path** to `science-tool`:

```env
SCIENCE_TOOL_PATH=<absolute-path-to-science-tool>
```

Resolve `${CLAUDE_PLUGIN_ROOT}/science-tool` to its absolute path at creation time. Ensure `.env` is in `.gitignore`.

### `AGENTS.md`

Extend or create `AGENTS.md` so it reflects:

- the canonical active roots
- validation commands
- conventions
- operational constraints

### `CLAUDE.md`

Create or normalize:

```md
@AGENTS.md
```

### Install the managed validator

Install Science's managed `validate.sh`:

```bash
science-tool project artifacts install validate.sh --project-root <project-path>
```

This drops the canonical `validate.sh` into the project root with the managed header. To stay current on future Science releases, run `science-tool project artifacts check validate.sh` periodically (or rely on `science-tool health` to surface drift).

If the project already has a `validate.sh` from a pre-managed-system era, adopt it:

```bash
science-tool project artifacts install validate.sh --adopt --project-root <project-path>
```

`--adopt` rewrites the managed header in place if the body matches a known historical version. If the body diverges from every known version, use `--force-adopt` instead (writes a `.pre-install.bak`).

### `doc/`

Collapse active Science-managed documentation into:

```text
doc/
├── background/
│   ├── topics/
│   └── papers/
├── questions/
├── methods/
├── datasets/
├── searches/
├── discussions/
├── interpretations/
├── reports/
├── meta/
└── plans/
```

### Prompts And Templates

Do not copy framework defaults into the project.

Only create `.ai/prompts/` and `.ai/templates/` if the project needs project-specific overrides or additions.

## Step 5: Update `.gitignore` If Needed

Ensure the project ignores:

- `.env`
- `papers/pdfs/`
- `.worktrees/`

Add profile-specific ignores only when they match the project's actual layout.

## Step 6: Verify

Run:

```bash
bash validate.sh --verbose
```

If the project has native test or typecheck commands, run those too.

## Step 7: Summarize

Tell the user:

- which profile the project was migrated to
- which roots were consolidated
- which material was archived versus kept active
- whether `RESEARCH_PLAN.md` was retained, moved into `README.md`, or replaced by `doc/plans/`
- what still needs manual review before commit
