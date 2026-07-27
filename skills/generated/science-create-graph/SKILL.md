---
name: science-create-graph
description: "Build a project knowledge graph from canonical upstream sources, then materialize graph.trig."
user-invocable: true
---

# Create Knowledge Graph

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `science-literature`, `science-literature`, `science-epistemics`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

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
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

> **Prerequisite:** Read `references/docs/user-guide/science-model.md`, `references/docs/user-guide/entities.md`, `references/docs/user-guide/graph-and-derived-state.md`, and `references/docs/plans/historical/2026-03-01-knowledge-graph-design.md` for model, entity, and graph semantics before starting.

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

For every new entity, read `references/docs/process/entity-creation-cookbook.md` and
check shared kinds before creating project-local entries. If no shared identity fits,
prefer the most specific registered kind. Use
`science entity create concept "<title>"` when a project-scoped concept needs a
durable graph identity. Keep weak ideas in prose until they need an owner.

## Canonical Inputs

Build the graph from these upstream sources:

- Typed markdown entities under `entities/` with YAML frontmatter (`id`,
  `kind`, `title`, `related`, `source_refs`, etc.)
- Task files in `tasks/active.md` and `tasks/done/*.md`
- Structured local extensions in:
  - `knowledge/sources/<local-profile>/external_refs.yaml`
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

1. Put first-class research objects in typed markdown entity owners:
   - hypotheses in `entities/hypotheses/`
   - questions in `entities/questions/`
   - interpretations, discussions, pre-registrations, bias audits, methods,
     datasets, and similar entities in their typed `entities/<kind>/` locations
2. Keep task links in `tasks/*.md` `related:` / `blocked-by:` fields using canonical IDs.
3. Put unresolved but legitimate project-local semantics in `knowledge/sources/<local-profile>/`:
   - `external_refs.yaml` for external authority rows
   - `mappings.yaml` for explicit aliases during migration
   - `relations.yaml` only when you need project-local relation declarations

Example `external_refs.yaml` entry:

```yaml
refs:
  - canonical_id: paper:smith2024
    kind: paper
    title: Smith 2024
    primary_external_id:
      source: DOI
      id: 10.1000/example
      curie: doi:10.1000/example
      provenance: manual
```

### Step 3: Audit canonical reference resolution

Run:

```bash
science graph audit --project-root . --format json
```

Fix every unresolved reference in the canonical sources before building:

- add missing frontmatter to existing docs
- convert incorrect short IDs to canonical IDs
- add explicit aliases in `mappings.yaml` only for current, intentional
  project-local equivalences
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
