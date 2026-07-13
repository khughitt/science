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
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
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
├── entities/
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
├── entities/
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
layout_version: 3
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
name = "<project-slug>-sciences"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
```

Resolve and install the project-local tooling environment:

```bash
uv lock
uv sync --frozen
uv run --frozen science --version
```

Commit `uv.lock`: it records the exact Science Git revision selected for this
project.

### `.env`

Preserve or create `.env` only for unrelated secrets or environment
configuration, and ensure it remains in `.gitignore`. Science itself is resolved
from the tracked manifest and lock.

### `AGENTS.md`

Extend or create `AGENTS.md` so it reflects:

- the canonical active roots
- validation commands
- conventions
- operational constraints

Use `templates/agents-md.md` as the structural reference.

If the existing `AGENTS.md` begins with `@core/overview.md` or
`@core/decisions.md` directives, remove them. Those files routinely run into
the hundreds of lines and would be injected into context every turn. The
"Load-bearing constraints" digest in `AGENTS.md` is maintained by
`science-curate` based on `core/decisions.md` instead.

### `CLAUDE.md`

Create or normalize to a single line:

```md
@AGENTS.md
```

If the existing `CLAUDE.md` carries duplicated `@core/*` directives or
project-specific guidance, move any non-include guidance into `AGENTS.md` and
collapse `CLAUDE.md` to the single `@AGENTS.md` pointer.

### Install the managed validator

Install Science's managed `validate.sh`:

```bash
science project artifacts install validate.sh --project-root <project-path>
```

This drops the canonical `validate.sh` into the project root with the managed header. To stay current on future Science releases, run `science project artifacts check validate.sh` periodically (or rely on `science health` to surface drift).

If the project already has a `validate.sh` from a pre-managed-system era, adopt it:

```bash
science project artifacts install validate.sh --adopt --project-root <project-path>
```

`--adopt` rewrites the managed header in place if the body matches a known historical version. If the body diverges from every known version, use `--force-adopt` instead (writes a `.pre-install.bak`).

### `entities/` And `doc/`

Move typed entity owners into `entities/<kind>/`. Keep `doc/` for prose,
reports, background, discussions, figures, and other documents that are not
entity owners.

Collapse active Science-managed prose into:

```text
doc/
├── background/
│   ├── topics/
│   └── papers/
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
- `*.pre-update*.bak`

Add profile-specific ignores only when they match the project's actual layout.

Never exclude a directory wholesale when it also holds version-controlled
sources. A bare `models/` entry is a trap: git won't descend into a
fully-excluded directory, so child negations silently fail and `git add`
commits nothing. `models/` holds causal DAG sources (`.dot`/`.json`) that must
stay tracked — if it also holds regenerable dumps, use `models/*` plus
`!models/*.dot` / `!models/*.json` negations, or write dumps to a separate
ignored directory.

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
- whether high-level project context and strategy now live in `README.md`
- what still needs manual review before commit
