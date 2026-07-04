---
name: science-create-graph
description: "Build a project knowledge graph from canonical upstream sources, then materialize graph.trig."
---

# Create Knowledge Graph

Converted from Claude command `/science:create-graph`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
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
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If you are operating from a git worktree and `uv run --frozen science ...`
   fails because a relative editable `tool.uv.sources` path resolves to a
   nonexistent checkout, use the main checkout's synced environment while
   keeping the worktree as the current directory:
   `$MAIN/.venv/bin/science <command>`. For wrappers or rules that shell out to
   nested `uv run --frozen ...`, export `UV_PROJECT=$MAIN` so dependencies
   resolve from the main checkout while cwd-relative project files still come
   from the worktree.
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

> **Prerequisite:** Read `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, `docs/user-guide/graph-and-derived-state.md`, and `docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics before starting.

## Overview

This command does **not** author triples directly. It organizes project knowledge into canonical upstream sources, audits reference resolution, and materializes `knowledge/graph.trig` as a generated artifact.

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

For brevity, the examples below write just `science <command>`; always expand them to `uv run science <command>` when executing.

## Rules

- **MUST NOT** edit `knowledge/graph.trig` directly.
- **MUST** define `knowledge_profiles` in `science.yaml` before building the graph.
- **MUST** treat markdown docs, task files, and `knowledge/sources/` files as the canonical graph inputs.
- **MUST** add project-local entities through supported source owners such as `entities/`, `knowledge/sources/<local-profile>/`, or CLI helpers, not as ad hoc triples.
- **MUST** run `science graph audit` before `science graph build`.
- **MUST** keep tasks as graph entities; do not treat them as out-of-band metadata.

## Cross-Project Registry Check

Before adding new entities, check the cross-project registry for existing definitions. Run `science sync status` to see if the registry is populated. If it is, new entities added during graph creation will be checked against the registry during `graph build` to detect potential duplicates across projects. If a match is found, prefer reusing the existing canonical ID and aliases rather than creating a new entity.

For every new entity, read `docs/process/entity-creation-cookbook.md` and
check shared kinds before creating project-local entries. If no shared identity fits,
prefer the most specific registered kind. Use
`science terms add <id> --title "<title>"` for simple project-scoped concepts, or
`science entity create concept "<title>"` when
the concept needs a full Markdown owner.

## Canonical Inputs

Build the graph from these upstream sources:

- Typed markdown entities in `specs/` and `doc/` with YAML frontmatter (`id`, `type`, `title`, `related`, `source_refs`, etc.)
- Task files in `tasks/active.md` and `tasks/done/*.md`
- Structured local extensions in:
  - `knowledge/sources/<local-profile>/entities.yaml`
  - `knowledge/sources/<local-profile>/terms.yaml`
  - `knowledge/sources/<local-profile>/relations.yaml`
  - `knowledge/sources/<local-profile>/mappings.yaml`

Use `science-model/core` semantics for shared entity and relation types. Declare domain ontologies (e.g., `biology`, `chemistry`, or `physics`) in `science.yaml` to enable vocabulary for entity types and relation predicates. Put anything project-local but still useful in the configured local profile directory, which defaults to `local`.

## Workflow

### Step 1: Configure profiles

Ensure `science.yaml` declares the ontologies and profiles you want to compose:

```yaml
ontologies: [biology]
knowledge_profiles:
  local: local
```

`ontologies` declares which community ontologies provide vocabulary for entity types and relation predicates. Currently available: `biology`, `physics`, `units`, `math`, `earth`, `chemistry`, `astronomy`, and `information`. `core` is always implied.
`local` also determines the directory name under `knowledge/sources/`; if omitted, use `local`.

### Step 2: Author canonical sources

For each project entity:

1. Put first-class research objects in typed markdown docs:
   - hypotheses in `entities/hypotheses/`
   - questions in `entities/questions/`
   - interpretations, discussions, pre-registrations, bias audits, methods, datasets, and similar entities in their typed `doc/` locations
2. Keep task links in `tasks/*.md` `related:` / `blocked-by:` fields using canonical IDs.
3. Put unresolved but legitimate project-local semantics in `knowledge/sources/<local-profile>/`:
   - `entities.yaml` for local entities such as project topics or legacy questions not yet migrated into standalone docs
   - `terms.yaml` for lightweight local semantic term rows
   - `mappings.yaml` for explicit aliases during migration
   - `relations.yaml` only when you need project-local relation declarations

Example `entities.yaml` entry:

```yaml
entities:
  - canonical_id: topic:evaluation
    kind: topic
    title: Evaluation
    profile: local
    source_path: knowledge/sources/local/entities.yaml
```

### Step 3: Audit canonical reference resolution

Run:

```bash
science graph audit --project-root . --format json
```

Fix every unresolved reference in the canonical sources before building:

- add missing frontmatter to existing docs
- convert legacy short IDs to canonical IDs
- add explicit aliases in `mappings.yaml` when a temporary migration bridge is still needed
- add missing local-profile entities for legitimate project-local concepts
- add `theme` markdown entities under `entities/themes/` when the missing node is a durable cross-cutting organizing frame that links multiple questions, hypotheses, tasks, reports, methods, concepts, child projects, or guardrails.

### Step 4: Materialize the graph

Once audit is clean:

```bash
science graph build --project-root .
science graph validate --format json
science graph stats --format json
```

`science graph build` generates `knowledge/graph.trig` deterministically from the upstream sources. That file is a view over the canonical inputs, not the place to curate knowledge manually.

## Output

At completion, the project should have:

1. Canonical entity/task/source files with resolved IDs
2. `knowledge/sources/<local-profile>/` for local extensions and explicit aliases
3. A generated `knowledge/graph.trig`
4. Clean `graph audit` and `graph validate` output

## Important Notes

- Prefer fixing the upstream source over adding a temporary alias.
- If you feel compelled to hand-edit `graph.trig`, stop and add or repair the missing upstream source instead.
- Ontology declarations enable standard vocabulary; use them when the project works with domain entities.
