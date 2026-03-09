---
description: Add Science research framework to an existing project. Use when the user has a pre-existing codebase, documentation, or research project and wants to adopt Science conventions without restructuring. Triggered by "import project", "adopt science", "add science to existing project", or similar.
---

# Import an Existing Project into Science

You are adding Science research infrastructure to an existing project. The key principle:
**additive only** — never overwrite, rename, or restructure existing files.

## Step 0: Pre-flight Checks

1. Confirm you are inside an existing project root (look for `.git/`, `package.json`,
   `pyproject.toml`, `Cargo.toml`, `go.mod`, or similar project markers).
2. If `science.yaml` already exists, this project has already been imported. Ask the user
   if they want to re-run import (which will fill in any missing pieces) or cancel.
3. Read the project's existing `CLAUDE.md` and `AGENTS.md` if they exist — you will
   extend these, not replace them.

## Step 1: Discover Existing Structure

Scan the project directory and identify existing equivalents for Science conventions:

| Science convention | Look for |
|---|---|
| `doc/` | `docs/`, `documentation/`, `doc/` |
| `code/` | `src/`, `lib/`, `app/`, `code/` |
| `data/` | `data/`, `datasets/` |
| `models/` | `models/`, `src/models/` |
| `papers/` | `papers/`, `references/`, `bibliography/` |
| `CLAUDE.md` | `CLAUDE.md` |
| `AGENTS.md` | `AGENTS.md` |
| `.bib` files | any `*.bib` file |

Present your findings to the user:

```
Found existing project structure:
  docs/          → will map as doc_dir
  src/           → will map as code_dir
  CLAUDE.md      → will extend (not replace)

No equivalent found for:
  papers/        → will create
  specs/         → will create
  data/          → will create (or skip if not needed)
```

Ask the user to confirm or adjust the mappings.

## Step 2: Gather Research Context

Have an interactive conversation to understand:

1. **Research question** — what is this project investigating or building?
2. **Brief summary** — 2-3 sentences describing the project
3. **Tags** — keywords for categorization
4. **Status** — likely `active` (since it's an existing project being worked on)

If the project has existing documentation (README, planning docs, design docs), read them
first and propose a research question based on what you find. Let the user refine it.

Don't ask all questions at once — have a natural conversation.

## Step 3: Create Science Infrastructure

### `science.yaml`

Create with the `paths:` section reflecting discovered mappings. Only include non-default
mappings — if a key would map to the Science default, omit it.

```yaml
name: "<project-name>"
created: "<original project creation date if known, else today>"
last_modified: "<today YYYY-MM-DD>"
summary: "<from conversation>"
status: "active"
tags:
  - "<tag1>"
  - "<tag2>"
data_sources: []
paths:
  doc_dir: "<mapped dir, e.g. docs/>"
  code_dir: "<mapped dir, e.g. src/>"
  # Only list non-default mappings
```

For the schema, see `${CLAUDE_PLUGIN_ROOT}/references/science-yaml-schema.md`.

### Create missing directories

Create these Science-specific directories (they won't have existing equivalents):

```bash
mkdir -p specs/hypotheses
mkdir -p papers/pdfs
mkdir -p knowledge
mkdir -p prompts/roles
mkdir -p templates
mkdir -p tasks
```

Skip any that already exist. Add `.gitkeep` to empty directories.

### Create subdirectories in the mapped doc dir

The mapped doc directory needs Science-standard subdirectories for research artifacts.
Create them inside the mapped `doc_dir`:

```bash
# Using the mapped doc_dir (e.g., docs/)
mkdir -p <doc_dir>/topics
mkdir -p <doc_dir>/papers
mkdir -p <doc_dir>/questions
mkdir -p <doc_dir>/methods
mkdir -p <doc_dir>/datasets
mkdir -p <doc_dir>/searches
mkdir -p <doc_dir>/discussions
mkdir -p <doc_dir>/interpretations
mkdir -p <doc_dir>/meta
```

Only create subdirectories that don't already exist. Add `.gitkeep` to empty ones.

### `specs/research-question.md`

Write the research question from the conversation. If the project has existing planning
or design documents, reference them and synthesize the question from those.

### `specs/scope-boundaries.md`

Write scope boundaries based on the conversation and any existing project documentation.

### `papers/references.bib`

If the project already has a `.bib` file, map to it in `science.yaml` paths (or symlink).
Otherwise create a new one:

```bibtex
% references.bib — BibTeX database for this Science project
% Add entries here for every paper cited in docs.
% Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)
```

### `RESEARCH_PLAN.md`

Create based on the project's current state. If existing planning docs exist, synthesize
them into the Science format:

```markdown
# Research Plan

> High-level research strategy and direction for this project.
> For the operational task queue, see `tasks/active.md`.

## Research Direction

<synthesized from existing docs and conversation>

## Current State

<what has been accomplished so far>

## Long-Term Goals

<from conversation and existing docs>
```

### `tasks/active.md`

```markdown
<!-- Task queue. Use /science:tasks to manage. -->
```

### `validate.sh`

Copy from plugin:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh ./validate.sh
chmod +x validate.sh
```

### `templates/`

Copy all templates from `${CLAUDE_PLUGIN_ROOT}/templates/`:

```bash
mkdir -p ./templates
cp -R ${CLAUDE_PLUGIN_ROOT}/templates/* ./templates/
```

### `prompts/roles/`

Copy role prompts from `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/`:

```bash
mkdir -p ./prompts/roles
cp ${CLAUDE_PLUGIN_ROOT}/references/role-prompts/*.md ./prompts/roles/
```

### Extend `CLAUDE.md`

If `CLAUDE.md` exists, **append** a Science section (do not replace existing content).
If it doesn't exist, create one from `${CLAUDE_PLUGIN_ROOT}/references/claude-md-template.md`.

When appending, add:

```markdown

## Science Project

This project uses the Science research framework.
See `science.yaml` for project manifest and path mappings.

### Automatic Skill Triggers

Before performing any of the following tasks, read the corresponding skill:

- **Writing any document in `<doc_dir>/` or `specs/`:** Read the `scientific-writing` skill
- **Literature review, source evaluation, paper summarization:** Read the `research-methodology` skill
- **Knowledge graph work:** Read the `knowledge-graph` skill (when available)

### Role Prompt Packs

- `prompts/roles/research-assistant.md` for research/synthesis/prioritization tasks
- `prompts/roles/discussant.md` for critical discussion tasks

### Document Conventions

- Use templates from `templates/` for all new research documents
- Run `bash validate.sh` before committing research artifacts
- Every factual claim needs a citation; use BibTeX keys `[@AuthorYear]`
- Mark unverified facts with `[UNVERIFIED]` and unsourced claims with `[NEEDS CITATION]`

### Path Mappings

<list the active non-default mappings, e.g.:>
- Research docs: `docs/` (Science default: `doc/`)
- Code: `src/` (Science default: `code/`)
```

Replace `<doc_dir>` with the actual mapped directory name, and list only non-default mappings.

### Extend `AGENTS.md`

If `AGENTS.md` exists, **append** a Science section (do not replace existing content).
If it doesn't exist, create a skeleton (same format as `create-project` Step 3).

When appending, add:

```markdown

## Science Conventions

### Validation

Run structural checks before committing research artifacts:

    bash validate.sh
    bash validate.sh --verbose

### Commit Messages for Research Artifacts

Use format: `<scope>: <description>` for research commits:
- `doc: add background on topic-x`
- `hypothesis: add H01`
- `papers: summarize Smith2024`
- `specs: refine research question`

### Citations

Use BibTeX keys `[@AuthorYear]` inline. All entries go in `papers/references.bib`.

### Markers

- `[UNVERIFIED]` for unverified facts
- `[NEEDS CITATION]` for unsourced claims

### Task Management

Tasks tracked in `tasks/active.md`. Manage via `/science:tasks`.
```

## Step 4: Update .gitignore (if needed)

Check the existing `.gitignore` and add Science-specific entries if missing:

```gitignore
# Science project
papers/pdfs/
.env
```

Do NOT add entries that conflict with existing gitignore rules or the project's needs.

## Step 5: Verify

Run validation:

```bash
bash validate.sh --verbose
```

It should pass. Warnings are acceptable (empty hypothesis directory, etc.). If there are
errors due to path mapping issues, fix the mappings in `science.yaml` and re-run.

## Step 6: Summarize

Tell the user what was created, what was mapped, and suggest next steps:

1. Review the generated `specs/research-question.md` and refine it
2. Add initial hypotheses with `/science:add-hypothesis`
3. Explore background with `/science:research-topic`
4. Review existing docs for papers to add to `papers/references.bib`
5. Run `/science:next-steps` to prioritize work

**Important:** Do NOT create a git commit automatically. The user may want to review the
changes first, especially since this modifies an existing project. Ask if they'd like to
commit.
