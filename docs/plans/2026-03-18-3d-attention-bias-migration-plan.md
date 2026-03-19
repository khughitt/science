# 3d-attention-bias Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate `~/d/3d-attention-bias` to the canonical `research` profile without breaking its root `src/` package layout, while consolidating duplicate documentation roots, retiring legacy AI/template roots, and replacing baseline-style result naming with stable analysis slugs.

**Architecture:** Keep the installable Python package in root `src/` and root `tests/`. Treat `code/` as the execution-artifact root for notebooks, scripts, and workflows. Collapse Science-managed writing into `doc/`, reserve `papers/` for bibliography/PDF management, and move retired structure into `archive/project-layout-legacy/` rather than leaving multiple active roots.

**Tech Stack:** Python, uv, pytest, ruff, pyright, Science `validate.sh`, Science knowledge-graph tooling, Markdown documentation.

---

## Preflight

- create a dedicated branch or worktree for `~/d/3d-attention-bias`
- stage specific files only; do not use `git add .`
- refresh `validate.sh` from the merged `science` framework before structural validation
- inspect `pyproject.toml`, `tool.pytest.ini_options`, and any path-sensitive imports before moving files

## Current-State Focus

Observed migration targets:

- packaged Python code already lives in root `src/` and should stay there
- execution code is split across `code/causal/`, `code/notebooks/`, placeholder `code/pipelines/`, and top-level `scripts/`
- Science-managed writing is split across `doc/`, `docs/`, `notes/`, and `papers/summaries/`
- AI assets still live in top-level `prompts/` and `templates/`
- `results/` currently uses `baseline/` buckets instead of stable analysis slugs

### Task 1: Record The Target Structure And Cleanup Set

**Files:**
- Create: `doc/project-organization-migration/desired_file_structure.md`
- Create: `doc/project-organization-migration/files_to_remove.md`
- Review: `science.yaml`
- Review: `pyproject.toml`
- Review: `tests/`

**Step 1: Write the desired target layout**

Document the intended steady-state structure:

```text
project/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── RESEARCH_PLAN.md
├── science.yaml
├── validate.sh
├── specs/
├── tasks/
├── doc/
│   ├── background/topics/
│   ├── background/papers/
│   ├── questions/
│   ├── discussions/
│   ├── meta/
│   └── plans/
├── knowledge/
├── src/
├── tests/
├── code/
│   ├── scripts/
│   ├── notebooks/
│   └── workflows/
├── data/
├── results/
├── models/
├── papers/
│   ├── references.bib
│   └── pdfs/
└── archive/
```

**Step 2: Write the cleanup inventory**

List the roots that should be retired or consolidated:

- `docs/`
- `notes/`
- `papers/summaries/`
- top-level `scripts/`
- `code/pipelines/`
- `code/lib/`
- top-level `prompts/`
- top-level `templates/`
- `tools/`

**Step 3: Commit the migration prep docs**

```bash
git add doc/project-organization-migration/desired_file_structure.md doc/project-organization-migration/files_to_remove.md
git commit -m "docs: record 3d-attention-bias migration target"
```

### Task 2: Normalize Manifest, Agent Docs, And Validator

**Files:**
- Modify: `science.yaml`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `validate.sh`
- Review: `RESEARCH_PLAN.md`

**Step 1: Update `science.yaml` to the canonical profile model**

Make these changes:

- add `profile: research`
- add `layout_version: 2`
- keep `knowledge_profiles`
- keep existing `aspects`
- update `last_modified`
- do not introduce `paths:`

**Step 2: Rewrite agent-facing docs**

- make `AGENTS.md` describe the canonical layout
- make `CLAUDE.md` contain only `@AGENTS.md`
- remove references to `papers/summaries/`, `prompts/`, `templates/`, and other legacy active roots

**Step 3: Refresh `validate.sh`**

Copy the canonical validator from:

```text
~/d/science/scripts/validate.sh
```

Then make it executable.

**Step 4: Verify the metadata/validator layer**

Run:

```bash
bash validate.sh --verbose
```

Expected:

- no legacy-path errors caused by the validator itself
- project still fails only on real structural drift until later tasks are complete

**Step 5: Commit**

```bash
git add science.yaml AGENTS.md CLAUDE.md validate.sh
git commit -m "chore: align 3d-attention-bias project metadata with research profile"
```

### Task 3: Consolidate Science-Managed Writing Under `doc/`

**Files:**
- Modify: `doc/background/`
- Modify: `doc/questions/`
- Modify: `doc/plans/`
- Modify: `specs/`
- Move/Retire: `docs/`
- Move/Retire: `notes/`
- Move/Retire: `papers/summaries/`
- Review: `doc/inquiries/`

**Step 1: Create the canonical background roots**

Ensure these directories exist:

- `doc/background/topics/`
- `doc/background/papers/`

**Step 2: Migrate topic and paper summaries**

- move active files from `notes/topics/` into `doc/background/topics/`
- move active files from `papers/summaries/` into `doc/background/papers/`
- inspect `notes/articles/`; move true paper/article summaries into `doc/background/papers/`
- archive thin, duplicate, or superseded article notes under `archive/project-layout-legacy/notes/`

**Step 3: Collapse duplicate planning/spec roots**

- move active files from `docs/plans/` into `doc/plans/`
- inspect `docs/specs/` and move active requirements into `specs/`
- inspect `doc/inquiries/` and re-home each file into `doc/questions/` or `doc/discussions/` based on content

**Step 4: Archive retired roots**

After the active content is moved, archive the retired trees under:

- `archive/project-layout-legacy/docs/`
- `archive/project-layout-legacy/notes/`

Do not leave both the old and new roots active.

**Step 5: Run structural verification**

Run:

```bash
bash validate.sh --verbose
uv run --frozen python -m pytest tests/test_refs.py -q
```

Expected:

- validator stops flagging duplicate document roots
- reference checks still pass

**Step 6: Commit**

```bash
git add doc specs archive
git commit -m "refactor: consolidate 3d-attention-bias documentation roots"
```

### Task 4: Consolidate Execution Roots Without Moving The Package

**Files:**
- Modify: `code/scripts/`
- Modify: `code/notebooks/`
- Create: `code/workflows/`
- Move/Retire: `scripts/`
- Move/Retire: `code/causal/`
- Move/Retire: `code/pipelines/`
- Move/Retire: `code/lib/`
- Review: `code/notebooks/pyproject.toml`
- Review: `code/notebooks/uv.lock`

**Step 1: Keep `src/` and `tests/` as the package/test roots**

Do not move:

- `src/attention_analysis/`
- `src/fine_tuning/`
- `src/models/`
- `src/structure/`
- `tests/`

**Step 2: Re-home execution scripts**

- move top-level `scripts/*.py` into `code/scripts/`
- move `code/causal/*.py` into `code/scripts/causal/` unless they are better represented as formal model artifacts under `models/`
- create `code/workflows/` as the canonical workflow root
- retire empty placeholder roots such as `code/pipelines/` and `code/lib/`

**Step 3: Remove nested execution-environment drift**

Inspect `code/notebooks/pyproject.toml` and `code/notebooks/uv.lock`.

Desired outcome:

- no second package/workspace root hidden under `code/notebooks/`
- notebook dependencies are either handled by the project root or documented intentionally

Archive the nested notebook package files if they are only historical scaffolding.

**Step 4: Update path-sensitive references**

Adjust any tests, docs, or scripts that still point at:

- top-level `scripts/`
- `code/pipelines/`

**Step 5: Verify**

Run:

```bash
bash validate.sh --verbose
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected:

- validator no longer warns about top-level `scripts/` or `code/pipelines/`
- package tests, lint, and type checks pass

**Step 6: Commit**

```bash
git add code src tests pyproject.toml
git commit -m "refactor: consolidate 3d-attention-bias execution roots"
```

### Task 5: Replace Baseline Result Buckets With Analysis Slugs

**Files:**
- Modify: `results/`
- Modify: `code/scripts/`
- Modify: `code/workflows/` if created
- Modify: `doc/interpretations/` or `doc/reports/` if they reference old result paths

**Step 1: Define the slug mapping**

Create a small mapping table from current result buckets to stable slugs. At minimum cover:

- `results/baseline/cpd_s42`
- `results/baseline/cpd_s42_v3`
- `results/baseline/rnass_s42`

Use the canonical `aNNN-<slug>` format.

**Step 2: Rename result directories**

Move each active baseline bucket into its final analysis-slug directory under `results/`.

**Step 3: Update producers and consumers**

Update any script, notebook, workflow, or interpretation doc that references the old baseline paths.

**Step 4: Refresh the knowledge graph if canonical sources changed**

Run:

```bash
uv run --frozen science-tool graph audit --project-root . --format json
uv run --frozen science-tool graph build --project-root .
uv run --frozen science-tool graph validate --format json --path knowledge/graph.trig
```

Expected:

- clean audit or only known intentional warnings
- graph validate passes

**Step 5: Final verification**

Run:

```bash
bash validate.sh --verbose
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen pyright
```

**Step 6: Commit**

```bash
git add results code doc knowledge
git commit -m "refactor: migrate 3d-attention-bias results to analysis slugs"
```
