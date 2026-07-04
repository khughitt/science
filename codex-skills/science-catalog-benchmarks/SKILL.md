---
name: science-catalog-benchmarks
description: "Discover, classify, and summarize benchmark-capable datasets without adding belief edges or benchmark outcomes."
---

# Catalog Benchmarks

Converted from Claude command `/science:catalog-benchmarks`.

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

Follow `references/command-preamble.md` with role `research-assistant`.

Read:

1. `skills/data/SKILL.md`
2. `~/d/science/docs/user-guide/benchmarking.md`
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
