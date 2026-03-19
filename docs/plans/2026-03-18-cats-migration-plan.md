# cats Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adopt the Science framework cleanly in `~/d/cats` as a canonical `software` profile project, adding only the minimal Science-managed roots needed for a small CLI tool and folding the repo’s current loose docs into the new structure.

**Architecture:** Keep the existing Python package in root `src/` and the existing tests in root `tests/`. Add the Science context layer (`science.yaml`, `AGENTS.md`, `CLAUDE.md`, `doc/`, `specs/`, `tasks/`, `knowledge/`, `validate.sh`) without introducing a research-style `code/` tree. Re-home the current loose docs into `doc/` and `specs/`, and keep the repo intentionally small.

**Tech Stack:** Python, uv, pytest, ruff, pyright, Click, Rich, Markdown documentation, Science `validate.sh`.

---

## Preflight

- create a dedicated branch or worktree for `~/d/cats`
- stage specific files only; do not use `git add .`
- inspect current dev tooling in `pyproject.toml` before adding Science-specific config or dependencies
- keep the final layout minimal; do not scaffold unused research roots such as `code/`, `papers/`, or `models/`

## Current-State Focus

Observed migration targets:

- the repo is already a clean software package with `src/` and `tests/`
- there is no `science.yaml`, `AGENTS.md`, `CLAUDE.md`, `validate.sh`, `doc/`, `specs/`, `tasks/`, or `knowledge/`
- current project notes live loosely in `docs/superpowers/`
- `kg-project-migration-guide.md` is still at the repo root

### Task 1: Record The Target Layout Before Refactoring

**Files:**
- Create: `doc/project-organization-migration/desired_file_structure.md`
- Create: `doc/project-organization-migration/files_to_remove.md`

**Step 1: Create the minimal target layout document**

Document the intended steady-state structure:

```text
project/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── science.yaml
├── validate.sh
├── doc/
│   ├── plans/
│   ├── meta/
│   └── reports/
├── specs/
├── tasks/
│   └── active.md
├── knowledge/
├── src/
└── tests/
```

**Step 2: Record what should be retired**

At minimum list:

- `docs/`
- root `kg-project-migration-guide.md`

**Step 3: Commit**

```bash
git add doc/project-organization-migration/desired_file_structure.md doc/project-organization-migration/files_to_remove.md
git commit -m "docs: record cats migration target"
```

### Task 2: Add The Minimal Science Software-Profile Scaffold

**Files:**
- Create: `science.yaml`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `validate.sh`
- Create: `README.md` if missing
- Create: `doc/`
- Create: `specs/`
- Create: `tasks/active.md`
- Create: `knowledge/`
- Modify: `pyproject.toml`

**Step 1: Create `science.yaml`**

Use a minimal software-profile manifest with:

- `profile: software`
- `layout_version: 2`
- a short project summary
- `status: active`
- tags appropriate for a CLI sequence-analysis tool
- `aspects: [software-development]`
- `knowledge_profiles`

**Step 2: Add the agent/validator files**

- write `AGENTS.md` for the package/CLI workflow
- make `CLAUDE.md` contain only `@AGENTS.md`
- copy the canonical `validate.sh` from `~/d/science/scripts/validate.sh`
- make `validate.sh` executable

**Step 3: Add the minimal Science-managed roots**

Create:

- `doc/plans/`
- `doc/meta/`
- `doc/reports/`
- `specs/`
- `tasks/active.md`
- `knowledge/`

Do not create `code/`, `papers/`, or `models/`.

**Step 4: Decide how to wire in `science-tool`**

Inspect `pyproject.toml` and add `science-tool` only through the repo’s existing uv conventions.

Preferred direction:

- add a dev-only entry that keeps the runtime package clean
- add a local source path to `../science/science-tool` if this repo will use graph tooling locally

**Step 5: Verify the scaffold**

Run:

```bash
bash validate.sh --verbose
uv run --frozen pytest -q
```

Expected:

- software-profile validation passes or only reports missing doc-content refinements
- the existing test suite still passes

**Step 6: Commit**

```bash
git add science.yaml AGENTS.md CLAUDE.md validate.sh README.md doc specs tasks knowledge pyproject.toml
git commit -m "feat: adopt science software-profile scaffold for cats"
```

### Task 3: Re-home Existing Loose Docs Into The Canonical Roots

**Files:**
- Move/Retire: `docs/superpowers/plans/`
- Move/Retire: `docs/superpowers/specs/`
- Move/Retire: `docs/`
- Move: `kg-project-migration-guide.md`
- Modify: `doc/plans/`
- Modify: `specs/`

**Step 1: Move existing plan/spec content**

Re-home current docs as follows:

- `docs/superpowers/plans/` -> `doc/plans/superpowers/`
- `docs/superpowers/specs/` -> `specs/superpowers/`

If any files are not active, archive them instead of moving them into the canonical roots.

**Step 2: Move the loose root guide**

Move:

- `kg-project-migration-guide.md` -> `doc/plans/kg-project-migration-guide.md`

**Step 3: Retire the old docs root**

After active content is moved:

- archive `docs/` under `archive/project-layout-legacy/docs/`, or
- delete it if it only contained duplicated migrated files and the project prefers a clean history

Do not leave `docs/` active beside `doc/`.

**Step 4: Verify**

Run:

```bash
bash validate.sh --verbose
uv run --frozen pytest -q
```

Expected:

- no duplicate-doc-root warnings
- no regressions in the existing package tests

**Step 5: Commit**

```bash
git add doc specs archive
git commit -m "refactor: migrate cats docs into canonical science roots"
```

### Task 4: Finalize Tooling And Close The Migration

**Files:**
- Modify: `AGENTS.md`
- Modify: `science.yaml`
- Modify: `README.md`
- Review: `pyproject.toml`

**Step 1: Align the docs with the final steady state**

Make sure:

- `AGENTS.md` references `doc/`, `specs/`, `tasks/`, and `knowledge/`
- `README.md` briefly explains that the repo is a CLI tool using the Science software profile
- `science.yaml` has the final `last_modified` timestamp and accurate tags

**Step 2: Run the final verification set**

Run:

```bash
bash validate.sh --verbose
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected:

- software-profile validation passes
- test, lint, and typecheck all pass

**Step 3: Commit**

```bash
git add AGENTS.md README.md science.yaml pyproject.toml
git commit -m "chore: finalize cats software-profile migration"
```
