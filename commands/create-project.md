---
description: Scaffold a new Science-managed project using one of the two supported profiles: `research` or `software`. Use when starting a brand-new project from scratch.
---

# Create A New Science Project

You are scaffolding a brand-new Science-managed project. The steady-state model supports exactly two project profiles:

- `research`
- `software`

Do not scaffold legacy path-mapping layouts.

## Step 0: Check For Existing Project

Before starting, check whether a `science.yaml` already exists in the current directory or any parent.

If it does, warn the user they appear to be inside an existing Science project and ask whether they want to:

- create a new project in a subdirectory
- cancel

If the user is adopting Science for an existing repository, use `/science:import-project` instead.

## Step 1: Gather Project Context

Have a natural interactive conversation and gather:

1. Project name
2. Profile: `research` or `software`
3. Summary
4. Tags
5. Aspects
6. Data sources, if any

If the profile is `research`, also gather:

1. Research question
2. Scope boundaries
3. Whether the project includes an installable Python package

If the profile is `software`, also gather:

1. Primary implementation stack
2. Whether the project still has a research/planning layer that should live in `doc/`

`profile` and `aspects` are separate:

- `profile` determines layout
- `aspects` remain explicit behavioral/domain mixins

## Step 2: Create Directory Structure

Use `$ARGUMENTS` as the project name if provided, otherwise use the name from Step 1.

Always create:

```text
<project>/
├── science.yaml
├── pyproject.toml
├── .env
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── validate.sh
├── doc/
│   ├── background/
│   │   ├── topics/
│   │   └── papers/
│   ├── questions/
│   ├── methods/
│   ├── datasets/
│   ├── searches/
│   ├── discussions/
│   ├── interpretations/
│   ├── reports/
│   ├── meta/
│   └── plans/
├── tasks/
│   └── active.md
├── specs/
└── knowledge/
```

For `research` projects, also create:

```text
<project>/
├── data/
│   ├── raw/
│   └── processed/
├── results/
├── models/
└── papers/
    ├── references.bib
    └── pdfs/
```

If the research project includes an installable Python package, create:

```text
<project>/
├── src/
└── tests/
```

Also create:

```text
<project>/
└── code/
    ├── scripts/
    ├── notebooks/
    └── workflows/
```

For `software` projects, keep native implementation roots. Create what matches the stack, for example:

```text
<project>/
├── src/
└── tests/
```

Do not scaffold unused placeholder directories such as `tools/`, top-level `prompts/`, or top-level `templates/`.

Only create `.ai/` if the user explicitly needs project-specific prompt/template overrides.

## Step 3: Populate Core Files

### `science.yaml`

```yaml
name: "<project-name>"
created: "<YYYY-MM-DD>"
last_modified: "<YYYY-MM-DD>"
summary: "<2-3 sentence summary from conversation>"
status: "active"
profile: "<research-or-software>"
layout_version: 2
tags:
  - "<tag1>"
  - "<tag2>"
data_sources: []
ontologies: []
knowledge_profiles:
  local: local
aspects: []
```

Add the requested aspects and any known data sources.

### `pyproject.toml`

Create a root tool manifest so the project can install Science tooling locally, even for non-Python repos.
If the repository already has a root `pyproject.toml`, extend it instead of creating a second one.

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

Install `science-tool` into that manifest with:

```bash
uv add --dev --editable "$SCIENCE_TOOL_PATH"
```

This applies even to non-Python repos because the manifest is for project-local tooling.

### `.env`

Populate with the **resolved absolute path** to `science-tool` so `validate.sh` and other tooling can find it:

```env
SCIENCE_TOOL_PATH=<absolute-path-to-science-tool>
```

Resolve `${CLAUDE_PLUGIN_ROOT}/science-tool` to its absolute path at creation time.

### `.gitignore`

Include at minimum:

```gitignore
# Secrets
.env

# Large files
papers/pdfs/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
.mypy_cache/

# Notebooks
.ipynb_checkpoints/

# Worktrees
.worktrees/

# OS
.DS_Store
```

For research projects, also ignore raw/processed data payloads while keeping descriptors or `.gitkeep` files as appropriate.

### `CLAUDE.md`

Create:

```md
@AGENTS.md
```

### `AGENTS.md`

Create a concise project-specific operational guide that covers:

- project overview
- validation commands
- conventions
- task execution constraints
- data access notes
- known issues

### `RESEARCH_PLAN.md`

For `research` projects, create `RESEARCH_PLAN.md` unless the user prefers to inline the high-level plan into `README.md`.

If created, keep it strategic only:

- research direction
- major workstreams
- decision gates
- strategic risks

Do not put task-queue bookkeeping in it.

For `software` projects, prefer `README.md` and `doc/plans/` unless the user explicitly wants a separate root-level plan file.

### `tasks/active.md`

Create:

```md
<!-- Task queue. Use /science:tasks to manage. -->
```

### `specs/`

For `research` projects:

- write `specs/research-question.md`
- write `specs/scope-boundaries.md`
- create `specs/hypotheses/`

For `software` projects:

- create `specs/` only as needed for project requirements or product/research planning

### `doc/`

Create the canonical document taxonomy and add a minimal overview/plan starter where appropriate.

### `validate.sh`

Copy the validation script from `${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh` and make it executable.

### Prompts And Templates

Do not copy framework defaults into the project.

Framework defaults are resolved centrally from `${CLAUDE_PLUGIN_ROOT}`.
Only create `.ai/prompts/` or `.ai/templates/` when the project needs project-specific overrides or additions.

## Step 4: Initialize Git

```bash
cd <project>
git init
git add -A
git commit -m "Initialize Science project: <project name>"
```

## Step 5: Verify

Run:

```bash
bash validate.sh --verbose
```

Warnings are acceptable at this stage if they reflect intentionally empty starter areas.

## Step 6: Summarize

Tell the user:

- which profile was scaffolded
- which aspects were enabled
- whether `RESEARCH_PLAN.md` was created or the plan was inlined into `README.md`
- whether any `.ai/` overrides were created
- suggested next commands
