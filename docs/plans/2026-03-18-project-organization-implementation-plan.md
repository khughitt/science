# Science Project Organization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Science's mixed structure/mapping model with two explicit project profiles (`research`, `software`), align the framework on one canonical vocabulary, and migrate the current outlier projects (`seq-feats`, `3d-attention-bias`, `natural-systems`, `cats`) into the new model.

**Architecture:** Update the Science framework first so scaffolding, validation, templates, and metadata all agree on the new profile model. Then migrate each project into one of the two supported steady-state layouts and remove redundant roots. Keep the final runtime model simple by eliminating broad path remapping from normal operation.

**Tech Stack:** Markdown documentation, Bash validation scripts, Python `science-tool`, Science command docs, existing project repositories.

---

## Closeout Status

Closeout snapshot recorded on 2026-03-18 after the framework refactor, all four project migrations, and the end-to-end verification pass.

### Completed

- Tasks `1`-`12`: complete

### Verified Clean

- `science`
  - framework profile refactor merged to `main`
  - `uv run --frozen python -m pytest tests/test_graph_cli.py tests/test_paths.py tests/test_refs.py tests/test_validate_script.py -q` -> pass

- `seq-feats`
  - migrated to the `research` profile
  - `bash validate.sh --verbose` -> pass
  - `uv run --frozen pytest -q` -> pass
  - `uv run --frozen --extra snakemake snakemake --snakefile code/workflows/Snakefile --config profile=pilot -n` -> pass

- `3d-attention-bias`
  - migrated to the `research` profile
  - `bash validate.sh --verbose` -> pass
  - `uv run --frozen pytest -q` -> pass
  - knowledge graph rebuilt cleanly after canonical reference and documentation cleanup

- `natural-systems`
  - migrated to the `software` profile
  - `bash validate.sh --verbose` -> pass
  - `npm run test -- --run` -> pass
  - `npm run typecheck` -> pass
  - `npm run build` -> pass
  - knowledge graph and frontmatter references refreshed cleanly

- `cats`
  - migrated to the `software` profile
  - `bash validate.sh --verbose` -> pass
  - `uv run --frozen pytest -q` -> pass
  - `uv run --frozen ruff check .` -> pass
  - `uv run --frozen pyright` -> pass

### Interpretation

The project-organization program is complete. The framework and example repos now conform to the profile-based model, the migration targets are verified clean, and the implementation plan can be treated as closed.

## Preflight

Before modifying the framework repo or any target project:

- create a dedicated branch or worktree for the migration work
- keep one branch/worktree per repository to avoid cross-repo staging mistakes
- stage specific files only; do not use `git add .` during migrations
- treat per-project `validate.sh` copies as managed artifacts that must be refreshed after framework validator changes
- check each project's `pyproject.toml`, test config, and lint/type-check settings before moving code roots

### Task 1: Lock The Canonical Model In Framework Docs

**Files:**
- Modify: `README.md`
- Modify: `references/project-structure.md`
- Modify: `references/science-yaml-schema.md`
- Modify: `references/claude-md-template.md`
- Modify: `references/command-preamble.md`
- Test: doc consistency via `rg`

**Step 1: Update the documented project model**

Define and document:

- `profile: research | software`
- `layout_version: 2`
- canonical `doc/` taxonomy using `doc/background/topics/` and `doc/background/papers/`
- `.ai/` for project-specific agent overrides/additions
- `CLAUDE.md` as `@AGENTS.md`
- optional `archive/`
- the relationship between `profile` and `aspects`
- preservation of `knowledge_profiles`
- `code/workflows/` as the canonical workflow directory name
- `RESEARCH_PLAN.md` placement guidance versus `README.md`

**Step 2: Remove steady-state `paths:` guidance from docs**

Rewrite schema/reference text so `paths:` is no longer presented as the normal organization mechanism.

**Step 3: Align examples and vocabulary**

Replace references to mixed legacy terms such as:

- `doc/topics/` when the new design says `doc/background/topics/`
- `doc/papers/` when the new design says `doc/background/papers/`
- `papers/summaries/`
- `doc/background/` used as a flat directory
- copied project-local prompt/template defaults

**Step 4: Verify documentation consistency**

Run:

```bash
rg -n "paths:|doc/topics|doc/papers|papers/summaries|doc/background/" README.md references commands skills templates
```

Expected:

- only intentional remaining references, or no matches after the migration

**Step 5: Commit**

```bash
git add README.md references/project-structure.md references/science-yaml-schema.md references/claude-md-template.md references/command-preamble.md
git commit -m "docs: define canonical project organization profiles"
```

### Task 2: Update Project Scaffolding And Migration Commands

**Files:**
- Modify: `commands/create-project.md`
- Modify: `commands/import-project.md`
- Test: command docs consistency via `rg`

**Step 1: Make create-project profile-aware**

Update `/science:create-project` so it scaffolds one of two supported layouts:

- `research`
- `software`

Ensure the created top-level structure matches the approved design.

For research projects, preserve packaging conventions:

- if the project includes an installable Python package, keep root `src/` and `tests/`
- use `code/` for scripts, notebooks, and workflows rather than nesting package code under `code/`

Select `profile` separately from `aspects`:

- `profile` determines layout
- `aspects` remain explicit behavioral/domain mixins

**Step 2: Repurpose import-project as a migration command**

Rewrite `/science:import-project` so it migrates a project into one of the supported layouts rather than preserving arbitrary legacy path mappings as the steady state.

**Step 3: Stop copying framework defaults into projects**

Rewrite scaffolding so framework prompts/templates are referenced centrally at runtime.

Project-local `.ai/` content should be created only for:

- overrides
- project-specific additions

**Step 4: Remove mapping-heavy instructions**

Delete or rewrite instructions that tell the system to keep indefinite `paths:`-based layouts.

**Step 5: Verify command docs**

Run:

```bash
rg -n "doc_dir|code_dir|paths:|mapped dir|docs/ instead of doc|src/ instead of code|cp -R .*templates|cp .*role-prompts" commands/create-project.md commands/import-project.md
```

Expected:

- only intentional migration-procedure language remains if needed

**Step 6: Commit**

```bash
git add commands/create-project.md commands/import-project.md
git commit -m "commands: align project scaffolding and migration flow"
```

### Task 3: Simplify science.yaml And Path Resolution Code

**Files:**
- Modify: `science-tool/src/science_tool/paths.py`
- Modify: `science-tool/tests/test_paths.py`
- Modify: any schema/parser helpers that depend on `paths:`
- Test: `science-tool/tests/test_paths.py`

**Step 1: Replace broad path-mapping assumptions**

Refactor path resolution so steady-state logic is driven by `profile` and the known canonical layout, not arbitrary per-directory mappings.

**Step 2: Keep the API explicit**

Resolve paths from:

- project root
- `profile`
- fixed defaults per profile

Avoid silent fallbacks beyond the two approved profiles.

Preserve:

- `knowledge_profiles`

Treat optional package roots in research projects deliberately:

- root `src/` and `tests/` remain conventional project/package structure
- Science path resolution should still treat `code/` as the research-execution root for scripts/notebooks/workflows

**Step 3: Update tests**

Rewrite path tests so they verify:

- `research` projects resolve Science-managed execution/document roots such as `code/`, `doc/`, and `results/`
- `software` projects resolve implementation/document roots such as `src/`, `doc/`, and `tests/`
- root `src/` in research projects is treated as an allowed packaging convention, not as a path-mapping exception

**Step 4: Run tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_paths.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/paths.py science-tool/tests/test_paths.py
git commit -m "feat: resolve project paths from profile layouts"
```

### Task 4: Rework Validation Around Canonical Profiles

**Files:**
- Modify: `scripts/validate.sh`
- Modify: related validator tests if present
- Test: `validate.sh` and selected `science-tool` tests

**Step 1: Replace legacy structural assumptions**

Update validation to check the new canonical structure:

- `research` profile expectations
- `software` profile expectations
- canonical `doc/` taxonomy
- `.ai/` conventions where applicable

**Step 2: Remove obsolete checks**

Delete checks for legacy sections and legacy directories unless they remain intentionally supported during the short migration window.

Examples to remove or replace:

- `papers/summaries`
- flat `doc/background/*.md` assumptions
- old `RESEARCH_PLAN.md` task-section expectations

**Step 3: Add drift detection**

Warn or fail on duplicate active roots after migration, for example:

- `doc/` and `docs/`
- `code/` and top-level `scripts/` in a research project
- multiple topic/paper note locations
- `code/pipelines/` versus `code/workflows/`

Explicitly allow the intentional packaged-research pattern:

- root `src/` + root `tests/` alongside `code/`

**Step 4: Run validation-focused checks**

Run:

```bash
bash scripts/validate.sh --verbose
uv run --frozen pytest science-tool/tests/test_refs.py science-tool/tests/test_graph_materialize.py -q
```

Expected:

- validator runs cleanly for the framework repo
- targeted tests pass

**Step 5: Commit**

```bash
git add scripts/validate.sh science-tool/tests
git commit -m "feat: validate canonical research and software layouts"
```

### Task 5: Align Templates, Skills, And Prompt References

**Files:**
- Modify: `templates/*` as needed
- Modify: `skills/research/SKILL.md`
- Modify: `skills/writing/SKILL.md`
- Modify: other `skills/*` and `references/role-prompts/*.md` files that mention old paths
- Test: reference search

**Step 1: Normalize all path references**

Replace old path vocabulary so templates and skills point to the same canonical directories.

**Step 2: Update cross-reference language**

Ensure writing guidance references:

- `doc/background/topics/`
- `doc/background/papers/`
- `doc/questions/`
- `doc/discussions/`
- `doc/interpretations/`

Also update distribution guidance so framework defaults are referenced centrally and project `.ai/` directories are override-only.

**Step 3: Verify by search**

Run:

```bash
rg -n "doc/topics|doc/papers|papers/summaries|doc/background/|prompts/|templates/|cp -R .*templates|cp .*role-prompts" templates skills references/role-prompts commands
```

Expected:

- only intentional references to the new model

**Step 4: Commit**

```bash
git add templates skills references/role-prompts
git commit -m "docs: align templates and skills with canonical layout"
```

### Task 6: Add Or Update Framework Tests For The New Layout Model

**Files:**
- Modify: `science-tool/tests/test_graph_cli.py`
- Modify: any create/import/validation tests that encode old paths
- Test: targeted pytest selection

**Step 1: Update fixtures**

Adjust test fixtures and sample projects so they match the new canonical profile layouts.

**Step 2: Cover both profiles**

Add explicit tests for:

- `research` profile project structure
- `software` profile project structure
- bibliography vs. document separation
- duplicate-root detection where appropriate

**Step 3: Run targeted tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_cli.py science-tool/tests/test_paths.py science-tool/tests/test_refs.py -q
```

Expected:

- PASS

**Step 4: Commit**

```bash
git add science-tool/tests
git commit -m "test: cover canonical project profile layouts"
```

### Task 7: Migrate seq-feats To The Research Profile

**Files:**
- Modify: `/mnt/ssd/Dropbox/seq-feats/science.yaml`
- Modify: `/mnt/ssd/Dropbox/seq-feats/AGENTS.md`
- Modify: `/mnt/ssd/Dropbox/seq-feats/CLAUDE.md`
- Modify: `/mnt/ssd/Dropbox/seq-feats/RESEARCH_PLAN.md`
- Modify: `/mnt/ssd/Dropbox/seq-feats/pyproject.toml`
- Modify: project docs referencing old roots
- Move/restructure: `scripts/`, `notebooks/`, `workflow/`, `notes/`, `results/`
- Test: project `validate.sh`

**Step 1: Set canonical profile metadata**

Update `science.yaml` to the new steady-state schema and remove obsolete layout remapping.

**Step 2: Preserve the packaged Python layout**

Keep:

- root `src/`
- root `tests/`

as the canonical package/test roots.

**Step 3: Consolidate research execution roots**

Move research execution code under `code/`:

- top-level `scripts/` -> `code/scripts/`
- top-level `notebooks/` -> `code/notebooks/`
- top-level `workflow/` -> `code/workflows/`

**Step 4: Consolidate document roots**

Move active `notes/` content into canonical `doc/` locations:

- topic notes -> `doc/background/topics/`
- article notes -> `doc/background/papers/` or retire/archive if superseded

**Step 5: Normalize result naming**

Replace phase-heavy directory naming with analysis-slug-based organization for durable outputs.

**Step 6: Update project config after moves**

Update `pyproject.toml`, pytest config, Ruff config, and any tool references affected by the code-root changes.

**Step 7: Refresh validator copy**

Copy in the updated `validate.sh` from the framework after Task 4 is complete.

**Step 8: Clean redundant roots**

Remove or archive obsolete top-level roots such as unused `tools/`.

**Step 9: Validate**

Run:

```bash
bash validate.sh
```

Expected:

- no structural errors under the new validator

**Step 10: Commit**

```bash
git add /mnt/ssd/Dropbox/seq-feats/science.yaml /mnt/ssd/Dropbox/seq-feats/AGENTS.md /mnt/ssd/Dropbox/seq-feats/CLAUDE.md /mnt/ssd/Dropbox/seq-feats/RESEARCH_PLAN.md /mnt/ssd/Dropbox/seq-feats/pyproject.toml /mnt/ssd/Dropbox/seq-feats/code /mnt/ssd/Dropbox/seq-feats/doc /mnt/ssd/Dropbox/seq-feats/results /mnt/ssd/Dropbox/seq-feats/tests /mnt/ssd/Dropbox/seq-feats/src /mnt/ssd/Dropbox/seq-feats/validate.sh
git commit -m "refactor: migrate seq-feats to research profile layout"
```

### Task 8: Migrate 3d-attention-bias To The Research Profile

**Files:**
- Modify: `/mnt/ssd/Dropbox/3d-attention-bias/science.yaml`
- Modify: `/mnt/ssd/Dropbox/3d-attention-bias/AGENTS.md`
- Modify: `/mnt/ssd/Dropbox/3d-attention-bias/CLAUDE.md`
- Modify: `/mnt/ssd/Dropbox/3d-attention-bias/RESEARCH_PLAN.md`
- Modify: `/mnt/ssd/Dropbox/3d-attention-bias/pyproject.toml`
- Move/restructure: `doc/`, `docs/`, `notes/`, `code/`, `src/`
- Test: project `validate.sh`

**Step 1: Set canonical profile metadata**

Convert the manifest to the new `research` profile model.

**Step 2: Preserve the packaged Python layout**

Keep root `src/` as the canonical package/production-code root.

**Step 3: Consolidate exploratory execution assets**

Keep `code/` for exploratory scripts, notebooks, workflows, or archived experimental material. Move useful content into canonical subdirectories and retire/archive placeholder residue.

**Step 4: Collapse document sprawl**

Merge active content from:

- `doc/`
- `docs/`
- `notes/`

into canonical `doc/` subdirectories.

**Step 5: Update project config after moves**

Update `pyproject.toml`, pytest config, Ruff config, and any tool references affected by the cleanup.

**Step 6: Refresh validator copy**

Copy in the updated `validate.sh` from the framework after Task 4 is complete.

**Step 7: Update guidance files**

Align `AGENTS.md`, `CLAUDE.md`, and `RESEARCH_PLAN.md` with the new vocabulary.

**Step 8: Validate**

Run:

```bash
bash validate.sh
```

Expected:

- no structural errors under the new validator

**Step 9: Commit**

```bash
git add /mnt/ssd/Dropbox/3d-attention-bias/science.yaml /mnt/ssd/Dropbox/3d-attention-bias/AGENTS.md /mnt/ssd/Dropbox/3d-attention-bias/CLAUDE.md /mnt/ssd/Dropbox/3d-attention-bias/RESEARCH_PLAN.md /mnt/ssd/Dropbox/3d-attention-bias/pyproject.toml /mnt/ssd/Dropbox/3d-attention-bias/code /mnt/ssd/Dropbox/3d-attention-bias/doc /mnt/ssd/Dropbox/3d-attention-bias/src /mnt/ssd/Dropbox/3d-attention-bias/tests /mnt/ssd/Dropbox/3d-attention-bias/validate.sh
git commit -m "refactor: migrate 3d-attention-bias to research profile layout"
```

### Task 9: Migrate natural-systems To The Software Profile

**Files:**
- Modify: `/mnt/ssd/Dropbox/natural-systems/science.yaml`
- Modify: `/mnt/ssd/Dropbox/natural-systems/AGENTS.md`
- Modify: `/mnt/ssd/Dropbox/natural-systems/CLAUDE.md`
- Modify: `/mnt/ssd/Dropbox/natural-systems/RESEARCH_PLAN.md` if retained
- Move/restructure: `doc/`, `docs/`, `guide/`, `.ai/`
- Modify: `/mnt/ssd/Dropbox/natural-systems/package.json` or build/test config if paths change
- Test: project `validate.sh`, `npm run test`, `npm run typecheck`

**Step 1: Set canonical profile metadata**

Convert the manifest to `profile: software` with the new steady-state schema.

**Step 2: Preserve natural app structure**

Keep:

- `src/`
- `tests/`
- `public/`
- app/toolchain files

Do not introduce `code/`.

**Step 3: Resolve documentation split intentionally**

Define one clear model:

- `doc/` for Science-managed project documents
- `guide/` only if it remains end-user/product content
- retire or merge `docs/` content so there is no ambiguity
- move high-level planning into `doc/plans/` or `README.md` unless a separate root-level `RESEARCH_PLAN.md` is still clearly justified

**Step 4: Align all guidance**

Ensure `science.yaml`, `AGENTS.md`, and `CLAUDE.md` all point to the same canonical locations.

**Step 5: Refresh validator copy**

Copy in the updated `validate.sh` from the framework after Task 4 is complete.

**Step 6: Validate app + structure**

Run:

```bash
bash validate.sh
npm run test
npm run typecheck
```

Expected:

- structure passes
- app tests/typecheck pass

**Step 7: Commit**

```bash
git add /mnt/ssd/Dropbox/natural-systems/science.yaml /mnt/ssd/Dropbox/natural-systems/AGENTS.md /mnt/ssd/Dropbox/natural-systems/CLAUDE.md /mnt/ssd/Dropbox/natural-systems/RESEARCH_PLAN.md /mnt/ssd/Dropbox/natural-systems/doc /mnt/ssd/Dropbox/natural-systems/guide /mnt/ssd/Dropbox/natural-systems/src /mnt/ssd/Dropbox/natural-systems/tests /mnt/ssd/Dropbox/natural-systems/validate.sh /mnt/ssd/Dropbox/natural-systems/package.json
git commit -m "refactor: migrate natural-systems to software profile layout"
```

### Task 10: Migrate cats To The Software Profile

**Files:**
- Modify: `/mnt/ssd/Dropbox/cats/AGENTS.md` if created
- Modify: `/mnt/ssd/Dropbox/cats/CLAUDE.md` if created
- Modify: `/mnt/ssd/Dropbox/cats/science.yaml` if created
- Modify: `/mnt/ssd/Dropbox/cats/pyproject.toml` if needed
- Move/restructure: `/mnt/ssd/Dropbox/cats/docs/superpowers/`
- Test: project test/CLI commands

**Step 1: Add only the needed Science roots**

For this small CLI project, introduce the minimal canonical software-profile structure:

- `doc/`
- `.ai/` only if needed
- optional `tasks/`, `specs/`, `knowledge/` if the project will actively use them

**Step 2: Preserve implementation layout**

Keep:

- `src/`
- `tests/`

as the canonical implementation structure.

**Step 3: Clean inherited documentation residue**

Review `docs/superpowers/` and either:

- migrate useful material into `doc/` or `.ai/`
- remove/archive it if it is obsolete scaffolding residue

**Step 4: Add standard guidance files**

If the project is being brought under Science management, add:

- `AGENTS.md`
- `CLAUDE.md` with `@AGENTS.md`
- `science.yaml`

using the software profile model.

**Step 5: Refresh validator copy**

If this project will use Science validation, copy in the updated `validate.sh` from the framework after Task 4 is complete.

**Step 6: Validate**

Run the project’s normal tests, for example:

```bash
uv run --frozen pytest
```

Expected:

- PASS

**Step 7: Commit**

```bash
git add /mnt/ssd/Dropbox/cats/AGENTS.md /mnt/ssd/Dropbox/cats/CLAUDE.md /mnt/ssd/Dropbox/cats/science.yaml /mnt/ssd/Dropbox/cats/pyproject.toml /mnt/ssd/Dropbox/cats/doc /mnt/ssd/Dropbox/cats/src /mnt/ssd/Dropbox/cats/tests /mnt/ssd/Dropbox/cats/validate.sh
git commit -m "refactor: migrate cats to software profile layout"
```

### Task 11: End-To-End Verification Across Framework And Example Projects

**Files:**
- No new files required
- Verify framework repo and all four migrated projects

**Step 1: Re-run framework verification**

Run:

```bash
uv run --frozen pytest science-tool/tests -q
bash scripts/validate.sh --verbose
```

Expected:

- PASS

**Step 2: Re-run project validations**

Run:

```bash
bash /mnt/ssd/Dropbox/seq-feats/validate.sh
bash /mnt/ssd/Dropbox/3d-attention-bias/validate.sh
bash /mnt/ssd/Dropbox/natural-systems/validate.sh
bash /mnt/ssd/Dropbox/cats/validate.sh
```

Expected:

- PASS, or only known intentional warnings with follow-up tickets

**Step 3: Re-run project-native tests where applicable**

Run:

```bash
uv run --frozen pytest -q
npm run test
npm run typecheck
```

Use the appropriate commands in each repository.

**Step 4: Commit**

```bash
git add README.md docs commands references scripts science-tool templates skills
git commit -m "chore: verify canonical project organization migration"
```

### Task 12: Publish Migration Guidance

**Files:**
- Create or modify: `docs/` guidance file explaining the two profiles and migration rules
- Modify: `README.md` if needed

**Step 1: Write concise migration guidance**

Document:

- when to choose `research`
- when to choose `software`
- canonical directory expectations
- migration rules for collapsing duplicate roots
- naming conventions for research analyses/results

**Step 2: Verify discoverability**

Ensure the main `README.md` links to the migration/profile guidance.

**Step 3: Commit**

```bash
git add README.md docs
git commit -m "docs: publish project profile migration guidance"
```
