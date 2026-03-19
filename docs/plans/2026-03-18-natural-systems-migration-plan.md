# natural-systems Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate `~/d/natural-systems` to the canonical `software` profile while preserving its Vite/React/TypeScript application structure, collapsing duplicate Science-managed document roots into `doc/`, and removing legacy `paths:`-based layout behavior.

**Architecture:** Keep the app’s native roots (`src/`, `public/`, `scripts/`, `tests/`) intact. Treat `doc/`, `specs/`, `tasks/`, and `knowledge/` as the Science-managed context layer. Move duplicate Science writing out of `docs/` and `guide/` references, retire top-level AI/template roots, and eliminate top-level `code/` unless it still contains active project-specific analysis material that should be archived or re-homed.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Playwright, uv, Science `validate.sh`, Science knowledge-graph tooling, Markdown documentation.

---

## Preflight

- create a dedicated branch or worktree for `~/d/natural-systems`
- stage specific files only; do not use `git add .`
- refresh `validate.sh` from the merged `science` framework before validation
- inspect `package.json`, `pyproject.toml`, and current graph/export scripts before moving documentation or code roots

## Current-State Focus

Observed migration targets:

- the repo is software-first and should use `profile: software`
- `science.yaml` still uses `paths:` mappings
- Science-managed writing is split across `doc/`, `docs/`, and `guide/`
- `code/notebooks/` remains as a top-level side root even though the project is software-first
- top-level `prompts/` and `templates/` are still present

### Task 1: Record The Target Layout And Cleanup Inventory

**Files:**
- Create: `doc/project-organization-migration/desired_file_structure.md`
- Create: `doc/project-organization-migration/files_to_remove.md`
- Review: `science.yaml`
- Review: `package.json`
- Review: `pyproject.toml`

**Step 1: Write the desired target layout**

Document the intended steady-state structure:

```text
project/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── science.yaml
├── validate.sh
├── doc/
│   ├── background/topics/
│   ├── background/papers/
│   ├── questions/
│   ├── discussions/
│   ├── interpretations/
│   ├── reports/
│   ├── meta/
│   └── plans/
├── specs/
├── tasks/
├── knowledge/
├── src/
├── tests/
├── public/
└── scripts/
```

**Step 2: Write the cleanup inventory**

List the roots to collapse or retire:

- `docs/`
- `code/`
- top-level `prompts/`
- top-level `templates/`
- any Science-managed content currently treated as if `guide/` were the canonical document root

**Step 3: Commit**

```bash
git add doc/project-organization-migration/desired_file_structure.md doc/project-organization-migration/files_to_remove.md
git commit -m "docs: record natural-systems migration target"
```

### Task 2: Normalize Manifest, Agent Docs, And Validator

**Files:**
- Modify: `science.yaml`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `validate.sh`
- Review: `RESEARCH_PLAN.md`
- Review: `README.md` if present in a later step

**Step 1: Replace `paths:` with the canonical profile model**

Update `science.yaml` to:

- add `profile: software`
- add `layout_version: 2`
- remove the `paths:` block entirely
- preserve `knowledge_profiles`
- preserve valid `aspects`
- update `last_modified`

**Step 2: Rewrite agent-facing guidance**

- make `AGENTS.md` describe the software-profile layout
- make `CLAUDE.md` contain only `@AGENTS.md`
- remove instructions that treat `guide/` or `docs/` as the canonical Science doc roots
- remove instructions that rely on `prompts/` or `templates/` being copied into the project

**Step 3: Refresh `validate.sh`**

Copy the canonical validator from:

```text
~/d/science/scripts/validate.sh
```

Then make it executable.

**Step 4: Decide what to do with `RESEARCH_PLAN.md`**

Because this is a software-profile repo:

- keep `RESEARCH_PLAN.md` only if it still adds clear long-horizon value, or
- fold its active content into `README.md` or `doc/plans/` and retire the root file

Pick one direction and document it in the commit message.

**Step 5: Verify**

Run:

```bash
bash validate.sh --verbose
```

Expected:

- the validator recognizes the repo as `software`
- any remaining failures are real migration drift, not stale profile logic

**Step 6: Commit**

```bash
git add science.yaml AGENTS.md CLAUDE.md validate.sh RESEARCH_PLAN.md README.md
git commit -m "chore: align natural-systems metadata with software profile"
```

### Task 3: Collapse Science-Managed Writing Into `doc/`

**Files:**
- Modify: `doc/`
- Modify: `specs/`
- Move/Retire: `docs/`
- Review: `guide/`
- Review: `kg-project-migration-guide.md`

**Step 1: Create the canonical background roots**

Ensure these directories exist:

- `doc/background/topics/`
- `doc/background/papers/`

**Step 2: Migrate duplicated document roots**

Move active content from:

- `doc/topics/` -> `doc/background/topics/`
- `docs/topics/` -> `doc/background/topics/`
- `docs/papers/` -> `doc/background/papers/`
- `docs/datasets/` -> `doc/datasets/`
- `docs/methods/` -> `doc/methods/`
- `docs/searches/` -> `doc/searches/`
- `docs/discussions/` -> `doc/discussions/`
- `docs/interpretations/` -> `doc/interpretations/`
- `docs/meta/` -> `doc/meta/`
- `docs/plans/` -> `doc/plans/`

**Step 3: Re-home stray root docs**

- move `kg-project-migration-guide.md` under `doc/plans/` or `doc/reports/`
- inspect `docs/superpowers/`; move active plans/specs into `doc/plans/` and `specs/` respectively

**Step 4: Treat `guide/` as app content, not the Science doc root**

Keep `guide/` only if it is runtime/build input for the app. Do not keep instructions or manifest settings that present it as the canonical Science writing root.

**Step 5: Archive the retired duplicate docs tree**

After active content is moved, archive the old `docs/` material under:

```text
archive/project-layout-legacy/docs/
```

Do not leave both `doc/` and `docs/` active.

**Step 6: Verify**

Run:

```bash
bash validate.sh --verbose
npm run test
```

Expected:

- validator no longer warns about duplicate document roots
- Vitest still passes after doc path updates that affect build-time data references

**Step 7: Commit**

```bash
git add doc specs archive
git commit -m "refactor: consolidate natural-systems documentation roots"
```

### Task 4: Remove Software-Profile Root Drift

**Files:**
- Review: `code/notebooks/`
- Review: `data/`
- Move/Retire: `code/`
- Move/Retire: `prompts/`
- Move/Retire: `templates/`
- Review: `scripts/`
- Review: `src/`

**Step 1: Keep the native software roots**

Do not move the active application structure:

- `src/`
- `tests/`
- `public/`
- `scripts/`

**Step 2: Retire `code/` unless it contains active software-independent research assets**

Inspect `code/notebooks/model-similarity.py` and `code/notebooks/viz.py`.

Choose one of these outcomes:

- move still-active notebook logic into `scripts/analysis/`, or
- archive the notebook files under `archive/project-layout-legacy/code/notebooks/`

The steady-state software profile should not keep a top-level `code/` root.

**Step 3: Inspect `data/`**

If `data/` is active application input, document that in `AGENTS.md` and keep it.

If it is only a placeholder or superseded research residue, archive it under `archive/project-layout-legacy/data/`.

**Step 4: Retire copied AI/template roots**

Archive:

- `prompts/`
- `templates/`

Project-specific overrides should only live in `.ai/` if they are still needed after migration.

**Step 5: Verify the software surface**

Run:

```bash
bash validate.sh --verbose
npm run test
npm run typecheck
npm run build
```

Expected:

- validator no longer warns about top-level `code/`
- test, typecheck, and build all pass

**Step 6: Commit**

```bash
git add AGENTS.md archive scripts src package.json package-lock.json
git commit -m "refactor: remove natural-systems software-profile layout drift"
```

### Task 5: Refresh Knowledge Graph Artifacts And Close The Migration

**Files:**
- Modify: `knowledge/`
- Review: `scripts/export_kg_model_sources.py`
- Review: `science.yaml`

**Step 1: Re-run the KG export/build flow**

Run:

```bash
uv run --frozen python scripts/export_kg_model_sources.py
uv run --frozen science-tool graph audit --project-root . --format json
uv run --frozen science-tool graph build --project-root .
uv run --frozen science-tool graph validate --format json --path knowledge/graph.trig
```

Expected:

- graph audit is clean or only has intentional follow-up warnings
- graph build and validate pass

**Step 2: Run the final migration verification**

Run:

```bash
bash validate.sh --verbose
npm run test
npm run typecheck
npm run build
```

**Step 3: Commit**

```bash
git add knowledge science.yaml
git commit -m "chore: finalize natural-systems software-profile migration"
```
