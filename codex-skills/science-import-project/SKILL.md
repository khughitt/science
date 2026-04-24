---
name: science-import-project
description: "Migrate an existing repository into one of the two supported Science project profiles (`research` or `software`). Use when a pre-existing project wants to adopt Science and converge on the canonical layout."
---

# Import An Existing Project Into Science

Converted from Claude command `/science:import-project`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

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
5. Knowledge-graph usage (`knowledge_profiles`)

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

Resolve `<science-plugin-root>/science-tool` to its absolute path at creation time. Ensure `.env` is in `.gitignore`.

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

### `validate.sh`

Copy `scripts/validate.sh` into the project root and make it executable.

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
