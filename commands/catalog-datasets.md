---
description: Gap-driven dataset discovery, accessibility verification, and reproducible prioritization. Drives the front half of the dataset arc — gap-scan → discover → verify → connect → prioritize → handoff.
---

# Catalog Datasets

> This command is the front half of the dataset arc (design: `~/d/science/docs/plans/2026-06-21-catalog-datasets-design.md`). Operationalization is `plan-pipeline`; commons promotion is deferred and gated on `access.verified`.

Catalog datasets for `$ARGUMENTS`.
If no argument is provided, run the full gap-driven loop against the project's active questions and hypotheses.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md` for data management conventions.
2. Read `.ai/templates/dataset.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/dataset.md`.
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

For brevity, examples write just `science <command>` — **always expand to `uv run science <command>` when executing. See step 8 of `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` for the fallback.**

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
  - No dataset reaches it through any load-bearing authoring surface: dataset `related:`, Q/H `related:` back-edge, Q/H `datasets:`, evidence-line/paper `dataset_usage` + proposition reach, or paper/consumer `dataset_usage` + `related:`; **or**
  - Every dataset that does reach it has `access.verified: false` and no `access.exception.mode` set, AND its `readiness.state` is `unverified` or inaccessible (weight < 0.4 from the scorer).

Collect the gap list and present it as a table:

| Q/H ID | Title | Covered datasets | Gap reason |
|--------|-------|------------------|------------|
| ... | ... | `dataset:<id>` / none | `no-edge` / `unverified` / `all-inaccessible` |

Note the `no-edge` and `unverified` gap-flags surfaced by the prioritizer — these are the primary signal in a sparse graph.
Use the `--coverage` output as the per-question/per-hypothesis source of truth; do not manually eyeball only frontmatter edges and miss `dataset_usage` reach.

---

## Step 2: Discover

For each gap Q/H, invoke `/science:find-datasets` to surface public candidate datasets.
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
   - Set `access.verification_method: "retrieved"` for public files you directly retrieved or listed; use `"credential-confirmed"` only when access required a valid login/credential. Do not put free text in this enum field.
   - Set `access.last_reviewed: "<YYYY-MM-DD>"`
   - Append a dated line to the body `## Access verification log` with the free-text method/evidence:
     ```yaml
     access:
       verified: true
       verification_method: "retrieved"
       last_reviewed: "2026-06-21"
     ```
     Body log line:
     ```markdown
     - 2026-06-21 (agent): GEO landing page and file list confirmed public access; no login required.
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

Present the ranked table. Highlight:
- Datasets that moved up because of the new `related:` / `dataset_usage` edges added in Step 4.
- Remaining `no-edge` and `unverified` gap-flags.
- The top-ranked **obtainable** datasets (those with `access.verified: true` or `access.level: public` and a plausible Branch A path).

If the graph was stale, the prioritizer will warn on stderr — run `science graph build` to update it before re-running if you want `leverage_tilt` to reflect the latest proposition graph.

---

## Step 6: Handoff

Route the top obtainable datasets to `/science:plan-pipeline` for per-dataset download, QA, and preprocessing.

For each top-ranked dataset where `access.verified: true` (or Branch A has just been confirmed):

1. Invoke `/science:plan-pipeline` for that dataset, providing:
   - The `dataset:<slug>` entity as the primary data source.
   - The target Q/H as the inquiry context.
2. Let `plan-pipeline` handle its own data-access gate (Step 2b) — at this point the entity's `access` block should already satisfy the PASS condition.

**Per-dataset QA and download are out of scope for this command.** The handoff is the front/back boundary; this command ends once `/science:plan-pipeline` has been invoked for each top candidate.

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
