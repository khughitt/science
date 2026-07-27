---
name: science-wander
description: "Serendipitous random-sample review loop. Draws N epistemic entities (default 3) from the project graph, reviews each for gaps, looks for unappreciated pairwise connections, and writes a short walk report. Read-only by default; --apply may create tasks."
user-invocable: true
---

# Wander · Random-sample review loop

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

Run a small, serendipitous review pass across the project's epistemic
entities. Sampling is weighted by the existing attention machinery
(freshness, time since last review, evidence balance). The agent reviews
each sampled entity for gaps, looks for unappreciated pairwise connections,
flags stub candidates, and writes a short report.


Use the user input for optional flags. Recognized:

- `--apply` — consumed by this slash command; permits exactly one side
  effect (creating tasks via `science tasks add`). Without it: report-only.
- `--n N` — number of entities to sample (default 3). Forwarded to CLI.
- `--seed N` — reproducibility seed. Forwarded.
- `--kind K` — restrict to entity kind(s); may repeat. Forwarded.
- `--epsilon F` — sampler weight floor. Forwarded.
- `--graph-path PATH` — override default `knowledge/graph.trig`. Forwarded.

## Phase 1: Materialize the skeleton

Generate a walk path and run the CLI:

```bash
WALK_ID="$(date +%Y-%m-%d-%H%M)"
WALK_PATH="entities/meta/walks/walk-${WALK_ID}.md"
mkdir -p entities/meta/walks
uv run science wander --format markdown --out "${WALK_PATH}" \
  <forwarded flags from the user input, EXCLUDING --apply>
```

If `science wander` exits non-zero with the message about `science graph
build`, surface that to the user and stop — there is no graph to walk.

## Phase 2: Read the skeleton

Read `${WALK_PATH}`. The frontmatter lists the sampled entity IDs. Each
per-entity section already contains a **Context** block (kind, weight,
source path, created date, mtime, length, neighbor counts, active
references) and a **Stub-smell signals** block with four booleans plus
`is_stub_candidate`. Use these — do not re-query the graph.

For each sampled entity, also read its source file (if `source` is set) so
the per-entity review can reference actual content, not just metadata.

## Phase 3: Per-entity review

Fill in the **Gaps:** line under each entity. Categories:

- **Text gaps:** prose quality, missing citations or provenance, broken
  cross-refs, weak or disconnected annotation.
- **Code/data gaps:** *only when the entity references implementation*
  (e.g., a hypothesis pointing at a pipeline). Look for silent failures,
  magic numbers, drift from claimed behavior. Skip if not grounded in code.
- **Epistemic gaps:** unstated assumptions, claims without support edges,
  propositions with stale verdicts.

Brief is correct. If nothing surfaces, write "no gaps surfaced."

## Phase 4: Pairwise connections

For each pair (the skeleton has one heading per pair), write one paragraph
answering:

> Is there an unappreciated connection between these two? If so, what
> would tracking it look like?

Most pairs will be "no obvious connection." Say so in one line and move
on. **Do not invent connections to fill the section.**

## Phase 5: Prune candidates

Replace the **Prune candidates** placeholder with a list of every entity
where `is_stub_candidate: true` in its Stub-smell block. Format:

```
- <entity-id> — <one-line rationale> [first flagged YYYY-MM-DD]
```

If none qualify, write `- none`.

## Phase 6: --apply (only if passed)

If `--apply` is in the user input, you may make exactly one kind of side
effect: create tasks via `science tasks add`. Two cases:

1. For pairwise connections you judge worth tracking, add a task:
   `investigate connection: <id-a> ↔ <id-b> — <one-line summary>`.
2. For each prune candidate, add a task:
   `review for deprecation: <entity-id> — reconsider on YYYY-MM-DD`
   (where the date is `today + 30 days`).

Tag each task description with `source: wander/${WALK_ID}` so it traces
back to this walk. Append the resulting task IDs under
**Spawned tasks** in the walk file.

Without `--apply`: leave **Spawned tasks** empty.

## Phase 7: Verify and report

Re-read the walk file end-to-end. Confirm:

- Every per-entity section has a non-empty `Gaps:` line.
- Every pairwise heading has a paragraph.
- `Prune candidates` and `Spawned tasks` are filled (even if "none" or empty).

Print the path of the walk file to the user.
