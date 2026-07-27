---
name: science-catalog-benchmarks
description: "Discover, classify, and summarize benchmark-capable datasets without adding belief edges or benchmark outcomes."
user-invocable: true
---

# Catalog Benchmarks

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

Catalog benchmark-capable datasets for the user input.
If no argument is provided, run the v1 descriptive benchmark loop over the project's active questions, hypotheses, and existing datasets.

## Scope

v1 is descriptive only:

- discover benchmark-capable datasets;
- classify `benchmark.domains`, `benchmark.modalities`, `benchmark.signal_types`, and `benchmark.benchmark_kinds`;
- add sparse `benchmark.tasks[]` only when the task is concrete;
- run `science benchmark list` and the facet coverage summary;
- record limitations when a dataset is facets-only.

Do not create belief-test plans, benchmark outcomes, graph edges, or benchmark gap entities in v1. Those are Phase 2/3.

## Setup


Read:

1. the `science-data-management` skill
2. `references/docs/user-guide/benchmarking.md`
3. `entities/datasets/`, if present
4. `entities/questions/`, `entities/hypotheses/`, and `entities/propositions/`, if present

## Step 1: Inspect Current Benchmark Coverage

Run:

```bash
science benchmark list --format json
science benchmark list --coverage-summary --format json
science benchmark list --commons --coverage-summary --format json
```

Use the JSON `summary` object as the source of truth for facet counts by domain, modality, signal type, benchmark kind, dataset class, and task completeness.

## Step 2: Classify Candidate Benchmarks

For each candidate dataset, decide whether it is:

- `dataset_class: deposit` when the benchmark data can be obtained and staged;
- `dataset_class: reference` when it is a benchmark portal, registry, atlas, or leaderboard used for lookup;
- `dataset_class: pointer` when it is worth tracking but not yet usable as data or lookup.

Do not infer `dataset_class` from `source_class`. A reference genome or reference atlas can be a downloadable deposit; a portal can be reference-only.

Fill the `benchmark` block with sparse, concrete metadata:

```yaml
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response"]
  source_datasets: []
  related_beliefs: []
  limitations:
    - "Facets only; no held-out task definition yet."
```

Add `benchmark.tasks[]` only when the task is concrete. The preferred minimum
for a useful catalog entry is a `prediction_target` and a `held_out_unit` (what
is predicted and what is withheld), plus `metric` and `baseline`:

```yaml
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response"]
  tasks:
    - id: "compound-response"
      task_type: "response-prediction"
      prediction_target: "post-treatment expression signature"
      held_out_unit: "compound"
      metric: "rank-correlation"
      baseline: "untreated expression profile"
      ground_truth:
        type: "measured-outcome"
        description: "measured post-perturbation expression state"
      interpretation_limits:
        - "Positive rank correlation against held-out perturbation response is the intended signal."
      intervention: "compound and dose"
      contexts: ["cell line", "compound", "dose"]
```

Task identity is local to the dataset. Render it as `dataset:<slug>#<task-id>` in prose and reports.

## Step 3: Search for Missing Facets

Prefer candidates that add new information relative to the existing summary:

- first proteomics benchmark before another RNA-seq benchmark;
- first perturbation or time-series signal before another static association dataset;
- first multimodal benchmark before another single-modality dataset;
- a reference registry when it makes future concrete deposits discoverable.

Useful biology/omics signal types include perturbation, time-series, longitudinal cohort, proteomics, spatial, single-cell, bulk RNA-seq, and multimodal proteogenomics.

## Step 4: Validate

Run:

```bash
science benchmark list --coverage-summary --format json
science validate --profile commit
```

Resolve benchmark metadata warnings before handing off. A facets-only record should have `limitations`; perturbation records should name `intervention` or `contexts` when they have tasks; time-series records should name `timepoints` when they have tasks.
