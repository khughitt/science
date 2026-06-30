---
name: science-catalog-datasets
description: "Gap-driven dataset discovery, accessibility verification, and reproducible prioritization. Drives the front half of the dataset arc — gap-scan → discover → verify → connect → prioritize → handoff."
---

# Catalog Datasets

Converted from Claude command `/science:catalog-datasets`.

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
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

> This command is the front half of the dataset arc. Current dataset lifecycle, reach, QA, and prioritization semantics are documented in `~/d/science/docs/user-guide/entities.md`. Operationalization is `plan-pipeline`; commons promotion is deferred and gated on `access.verified`.

Catalog datasets for the user input.
If no argument is provided, run the full gap-driven loop against the project's active questions and hypotheses.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `skills/data/SKILL.md` for data management conventions.
2. Read `.ai/templates/dataset.md` first; if not found, read `templates/dataset.md`.
3. Read project context, preferring layout-v3 entity roots:
   - `entities/questions/` (all question files, if present)
   - `entities/hypotheses/` (all hypothesis files)
   - `entities/propositions/` (durable proposition entities, if present)
   - Read legacy specs/research-question.md only if it exists.
   - Read legacy specs/scope-boundaries.md only if it exists.
   - Existing `entities/datasets/` (to know what is already catalogued)
4. Resolve the project root (the directory containing `science.yaml`) — the CLI commands below require it or discover it automatically from the working directory.

## Tool invocation

All `science` commands below use this pattern:

```bash
uv run science <command>
```

For brevity, examples write just `science <command>` — **always expand to `uv run science <command>` when executing. See step 8 of `references/command-preamble.md` for the fallback.**

---

## Step 1: Gap scan

Identify questions and hypotheses that have no accessible dataset.

**Run the prioritizer and export as JSON:**

```bash
science dataset prioritize --format json
```

Also export the inverse coverage view:

```bash
science dataset prioritize --coverage --format json
```

Cross-reference every `question:` and `hypothesis:` entity found in `entities/`:

- A Q/H is a **gap** if:
  - No dataset reaches it through any load-bearing authoring surface: dataset `related:`, Q/H `related:` back-edge, Q/H `datasets:`, evidence-line `dataset_usage` + proposition reach, or paper/consumer `dataset_usage` + `related:` Q/H links; **or**
  - Every dataset that does reach it has `access.verified: false` and no `access.exception.mode` set, AND its `readiness.state` is `unverified` or inaccessible (weight < 0.4 from the scorer).

Collect the gap list and present it as a table:

| Q/H ID | Title | Covered datasets | Gap reason |
|--------|-------|------------------|------------|
| ... | ... | `dataset:<id>` / none | `no-edge` / `unverified` / `all-inaccessible` |

Note the `no-edge` and `unverified` gap-flags surfaced by the prioritizer — these are the primary signal in a sparse graph.
Use the `--coverage` output as the per-question/per-hypothesis source of truth; do not manually eyeball only frontmatter edges and miss `dataset_usage` reach.

---

## Step 2: Discover

For each gap Q/H, invoke `science-find-datasets` to surface public candidate datasets.
Focus on obtainable omics (GEO, SRA, Zenodo) for under-covered Q/H triggers; prefer datasets with a direct accession or DOI that can be verified without credentialing.

Before creating any local dataset entity, check existing project datasets and commons-backed datasets/overlays by accession, DOI, title, and normalized slug. If a canonical commons dataset already exists (for example TCGA PanCanAtlas or METABRIC), link to the existing `dataset:<slug>` or create a project overlay when the project needs local annotations. Do not create a duplicate local dataset entity for the same artefact.

For each promising candidate found, author a dataset entity:

```bash
science dataset add <slug> \
  --title "<Human-readable title>" \
  --level public \
  --source-url "<landing page or accession URL>"
```

Record the dataset/QH connection in the Q/H entity's `datasets:` field during Step 4. Use dataset `related:` only when the dataset entity is the clearer editing surface for the authoring session.

`science dataset add` defaults `--class deposit` and `--level controlled`; pass `--level public` explicitly for GEO/SRA/Zenodo resources that are freely downloadable. Use `registration` or `controlled` when the repository requires login or a DUA.
Use `--class reference` for portals, knowledgebases, indexes, or catalogs used for lookup; `--class reference` requires `--source-url`.
Use `--class pointer` for a metadata-only external resource worth tracking but not yet runnable or useful as a lookup surface.
`status` defaults to `candidate` — do not override unless the dataset is already verified.

After authoring, confirm each file was created under `entities/datasets/`.

---

## Step 3: Verify accessibility

For **each candidate** dataset (status `candidate`, `access.verified: false`), confirm it is obtainable and record the result with **one command** — `science dataset verify-access`. It sets the coupled `origin` / `license` / `access` fields together and appends the verification-log line in a single atomic, idempotent edit (and backfills legacy entities that lack `origin`/`tier`/`access`). Do **not** hand-edit the three fields separately — they have order-dependent failure modes (an `access` block is inert until `origin: external`, which then trips `dataset.license-missing` until a `license` is set).

**Branch A — verifiable under current credentials** (public or registration-only datasets):

1. Confirm the landing page or accession URL resolves and the files are downloadable without application.
2. Record it:
   ```bash
   science dataset verify-access <slug> \
     --level public \
     --method retrieved \
     --license <SPDX-id-or-unknown> \
     --source-url "<landing/accession URL>" \
     --note "GEO landing page and file list confirmed public; no login required."
   ```
   `--method` is **required** (enum `retrieved|credential-confirmed|landing-confirmed|metadata-confirmed` — use `retrieved` for downloadable deposits, `credential-confirmed` only when a valid login/credential was needed, and `landing-confirmed`/`metadata-confirmed` for reference or pointer records; no free text). Use `--class reference|pointer` when verifying a reference or pointer row; those classes require `--source-url` and reject `retrieved`. `landing-confirmed` and `metadata-confirmed` reject default `deposit` rows. `--license` is **required when the entity has none** — pass an SPDX id, or the `unknown` sentinel if it genuinely can't be determined. The command sets `access.verified: true` and `last_reviewed` to today, appends `--note` to the body `## Access verification log`, and prints the resulting access readiness state, prioritizer weight, and runtime state.

**Branch B — requires credentials the project does not hold** (controlled, DUA-gated, commercial):

Record a structured access exception instead of flipping verified (the two are mutually exclusive — the command clears `verified`). `--license` is still required; `decision_date` is set to today automatically:

```bash
# (a) scope-reduce — defer acquisition
science dataset verify-access <slug> --license <id-or-unknown> \
  --exception scope-reduced --rationale "<why>" --followup-task task:<id>

# (b) expand-to-acquire — add credential acquisition to the current task
science dataset verify-access <slug> --license <id-or-unknown> \
  --exception expanded-to-acquire --rationale "<why>"

# (c) substitute — choose an alternative dataset
science dataset verify-access <slug> --license <id-or-unknown> \
  --exception substituted --superseded-by dataset:<alternative-slug> --rationale "<why>"
```

A verification-log line is appended in all Branch B cases.

**No new findings store.** These are the existing `access` fields and the existing body log section — do not introduce a parallel record.

---

## Step 4: Connect

Wire datasets to the questions and hypotheses they inform.

**Legacy metadata backfill.** When connecting or backfilling legacy dataset entities, do not add `origin: external` by itself; set `license:` at the same time (`unknown` is acceptable when the license genuinely cannot be determined), preferably by running `science dataset verify-access` so `origin` / `license` / `access` move together. If the row has `source_class: derived` and `origin: external`, also add `dataset_usage` provenance with `role: "upstream"` or `role: "training"` for the input dataset(s); otherwise validation will warn that independence cannot be derived.

**Prefer Q/H `datasets:` for direct dataset needs.** In each question or hypothesis entity, add the dataset IDs it needs or is informed by:

```yaml
datasets:
  - "dataset:<slug>"
```

This is now load-bearing for `science dataset prioritize` and works without a materialized graph.

**Use dataset `related:` when the dataset entity is the active editing surface.** This remains supported:

```yaml
related:
  - "question:q0001"
  - "hypothesis:h0002"
```

Do not add duplicate Q/H `related:` back-edges solely for prioritize reach when `datasets:` already records the fact.

**Author `dataset_usage` blocks** where a paper or evidence-line records how a dataset was used:

```yaml
dataset_usage:
  - ref: "dataset:<slug>"
    role: "analyzed"
    overlap: "full"
```

For papers, pair `dataset_usage` with `related:` Q/H links on the paper. For evidence-lines, pair `dataset_usage` with the existing proposition target. Both paths participate in the `reach` term of the prioritizer; graph materialization is still needed for proposition-derived reach and leverage.

---

## Step 5: Prioritize

Re-run the prioritizer after connecting:

```bash
science dataset prioritize --explain
```

Default ranking excludes gated deposits, reference datasets, and pointer records; the CLI prints an exclusion summary. Use `--include-gated`, `--include-reference`, or `--include-pointer` to inspect excluded classes, or use `--runtime-state runnable|unstaged-deposit|blocked-access|reference-only|pointer-only` for an exact runtime-stageability slice.

Coverage mode reports richer states:

```bash
science dataset prioritize --coverage --format json
```

The JSON shape is `{ "rows": [...], "excluded_summary": {...} }`. Each coverage row includes `coverage_state`, `gap_reason`, runtime-state `counts`, and the reaching dataset IDs.

Present the ranked table. Highlight:
- Datasets that moved up because of the new `datasets:` / `related:` / `dataset_usage` connections added in Step 4.
- Remaining `no-edge` and `unverified` gap-flags, plus coverage `gap_reason` values such as `no-candidate`, `only-gated`, `only-reference`, `only-pointer`, and `unstaged-deposit`.
- The top-ranked **obtainable** datasets (those with `access.verified: true` or `access.level: public` and a plausible Branch A path).

If the graph was stale, the prioritizer will warn on stderr — run `science graph build` to update it before re-running if you want `leverage_tilt` to reflect the latest proposition graph.

---

## Step 6: Handoff

Route the top obtainable datasets to `science-plan-pipeline` for per-dataset download, QA, and preprocessing.

For each top-ranked dataset where `access.verified: true` (or Branch A has just been confirmed):

1. Invoke `science-plan-pipeline` for that dataset, providing:
   - The `dataset:<slug>` entity as the primary data source.
   - The target Q/H as the inquiry context.
2. Let `plan-pipeline` handle its own data-access gate (Step 2b) — at this point the entity's `access` block should already satisfy the PASS condition.

**Per-dataset QA and download are out of scope for this command.** The handoff is the front/back boundary; this command ends once `science-plan-pipeline` has been invoked for each top candidate.

## Commons Promotion Follow-Up

When a catalog record is reusable across projects, promote it with `science commons promote dataset --from <project-id> --slug <slug>` after its class-specific verification is complete.

- `deposit` rows still need a promotable datapackage and QA resource before promotion.
- `reference` rows promote as entity-only commons records when `access.verified: true`, `access.source_url` exists, and `verification_method` is `landing-confirmed`, `metadata-confirmed`, or `credential-confirmed`.
- `pointer` rows promote as metadata stubs with `runtime_state: pointer-only`; they are never counted as runnable datasets.

---

## Process Reflection

Reflect on the **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well), report each item via:

```bash
science feedback add \
  --target "command:catalog-datasets" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
