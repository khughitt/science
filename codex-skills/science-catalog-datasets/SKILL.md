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

> This command is the front half of the dataset arc (design: `~/d/science/docs/plans/2026-06-21-catalog-datasets-design.md`). Operationalization is `plan-pipeline`; commons promotion is deferred and gated on `access.verified`.

Catalog datasets for the user input.
If no argument is provided, run the full gap-driven loop against the project's active questions and hypotheses.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `skills/data/SKILL.md` for data management conventions.
2. Read `.ai/templates/dataset.md` first; if not found, read `templates/dataset.md`.
3. Read project context:
   - `specs/research-question.md`
   - `specs/scope-boundaries.md`
   - `entities/hypotheses/` (all hypothesis files)
   - `entities/questions/` (all question files, if present)
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

Cross-reference every `question:` and `hypothesis:` entity found in `entities/`:

- A Q/H is a **gap** if:
  - No dataset entity has a `related:` edge to it (frontmatter path, either direction), AND no evidence-line carries a `dataset_usage` block pointing to a dataset that reaches it; **or**
  - Every dataset that does reach it has `access.verified: false` and no `access.exception.mode` set, AND its `readiness.state` is `unverified` or inaccessible (weight < 0.4 from the scorer).

Collect the gap list and present it as a table:

| Q/H ID | Title | Gap reason |
|--------|-------|------------|
| ... | ... | `no-edge` / `unverified` / `all-inaccessible` |

Note the `no-edge` and `unverified` gap-flags surfaced by the prioritizer — these are the primary signal in a sparse graph.

---

## Step 2: Discover

For each gap Q/H, invoke `science-find-datasets` to surface public candidate datasets.
Focus on obtainable omics (GEO, SRA, Zenodo) for under-covered Q/H triggers; prefer datasets with a direct accession or DOI that can be verified without credentialing.

For each promising candidate found, author a dataset entity:

```bash
science dataset add <slug> \
  --title "<Human-readable title>" \
  --level public \
  --source-url "<landing page or accession URL>" \
  --related "question:<id>"   # repeat for each related Q/H
```

`science dataset add` defaults `--level` to `controlled`; pass `--level public` explicitly for GEO/SRA/Zenodo resources that are freely downloadable. Use `registration` or `controlled` when the repository requires login or a DUA.
`status` defaults to `candidate` — do not override unless the dataset is already verified.

After authoring, confirm each file was created under `entities/datasets/`.

---

## Step 3: Verify accessibility

For **each candidate** dataset (status `candidate`, `access.verified: false`), confirm it is obtainable and record the result in the entity's `access` block.

**Branch A — verifiable under current credentials** (public or registration-only datasets):

1. Confirm the landing page or accession URL resolves and the files are downloadable without application.
2. Edit `entities/datasets/<slug>.md`:
   - Set `access.verified: true`
   - Set `access.verification_method: "<how you checked, e.g. GEO landing page confirmed public>">`
   - Set `access.last_reviewed: "<YYYY-MM-DD>"`
   - Append a dated line to the verification log (create the block if absent):
     ```yaml
     access:
       verified: true
       verification_method: "GEO landing page — files freely downloadable"
       last_reviewed: "2026-06-21"
       verification_log:
         - date: "2026-06-21"
           note: "Confirmed public access; no login required."
     ```

**Branch B — requires credentials the project does not hold** (controlled, DUA-gated, commercial):

Apply the `plan-pipeline` Dimension-3 data-access gate logic:

- **(a) scope-reduce:** defer acquisition; populate `access.exception`:
  ```yaml
  access.exception:
    mode: "scope-reduced"
    decision_date: "<YYYY-MM-DD>"
    followup_task: "task:<id>"
  ```
- **(b) expand-to-acquire:** add credential acquisition to the current task; populate:
  ```yaml
  access.exception:
    mode: "expanded-to-acquire"
    decision_date: "<YYYY-MM-DD>"
  ```
- **(c) substitute:** choose an alternative dataset; populate:
  ```yaml
  access.exception:
    mode: "substituted"
    superseded_by_dataset: "dataset:<alternative-slug>"
  ```

In all Branch B cases, append a dated verification-log line explaining the decision.

**No new findings store.** These fields are the existing `access` schema — do not introduce a parallel record.

---

## Step 4: Connect

Wire datasets to the questions and hypotheses they inform.

**Add `related:` edges** in each dataset entity's frontmatter for any Q/H it reaches that is not already listed:

```yaml
related:
  - "question:q0001"
  - "hypothesis:h0003"
```

Also add the back-edge: in the Q/H entity, add the dataset to its `related:` block if it is not present.

**Author `dataset_usage` blocks** where an evidence-line already exists (or author a minimal evidence-line stub):

```yaml
# In an evidence-line or interpretation entity:
dataset_usage:
  - ref: "dataset:<slug>"
    role: "analyzed"        # analyzed | validation_source | cited | upstream | training | set_definition_source
    overlap: "full"         # full | partial | unknown
```

This is load-bearing: `dataset_usage` edges participate in the `reach` term of the prioritizer and appear in the graph once materialized.

---

## Step 5: Prioritize

Re-run the prioritizer after connecting:

```bash
science dataset prioritize --explain
```

Present the ranked table. Highlight:
- Datasets that moved up because of the new `related:` / `dataset_usage` edges added in Step 4.
- Remaining `no-edge` and `unverified` gap-flags.
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
