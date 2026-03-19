# Science Project Organization Design

## Goal

Define a simpler, more cohesive organization model for Science-managed projects by replacing the current mixed convention/mapping system with two explicit first-class project profiles:

- `research`
- `software`

This design also defines the migration target for the current example projects:

- `seq-feats`
- `3d-attention-bias`
- `natural-systems`
- `cats`

## Problems Observed In The Audit

### 1. The framework itself is internally inconsistent

The `science` repository currently describes one layout in some places and validates another in others.

Examples from the audit:

- `README.md`, `commands/create-project.md`, and most newer commands describe `doc/topics/` and `doc/papers/`
- `scripts/validate.sh` still checks for older structures such as `doc/background/` and `papers/summaries/`
- some project-level `CLAUDE.md` / `AGENTS.md` content still refers to older locations and concepts

### 2. Path mappings have become a source of drift

The current `paths:` model in `science.yaml` was intended to ease adoption, but in practice it creates multiple active mental models for where documents and code live.

Observed examples:

- `natural-systems/science.yaml` points to `doc/`, while `CLAUDE.md` points to `guide/`, and the repository also has a populated `docs/`
- `seq-feats` maps `code_dir: src`, but still uses `scripts/`, `workflow/`, and `notebooks/` as independent top-level roots

### 3. Documentation is fragmented across overlapping roots

Across the audited projects, Science-managed notes and documents are split across combinations of:

- `doc/`
- `docs/`
- `notes/`
- `papers/`
- `guide/`

This causes ambiguity about:

- which directory is canonical
- which files are active versus legacy
- how topic notes, paper notes, and process artifacts differ

### 4. Research code and outputs lack a stable naming model

Research projects currently mix:

- top-level `src/`
- top-level `scripts/`
- top-level `workflow/`
- top-level `notebooks/`
- `code/` in some projects

Generated outputs are similarly mixed:

- by phase (`phase2`, `phase3a`, `pilot`)
- by analysis subject (`kmer`)
- by broad study bucket (`full_study`)

This makes it hard to see which script produced which result set and which interpretation document explains it.

### 5. Some scaffolding creates low-value clutter

Several projects contain placeholder or lightly used top-level directories such as:

- `tools/`
- `prompts/`
- `templates/`

For active projects, these often add noise without clarifying the workflow.

## Design Principles

- Support both research-first and software-first projects explicitly
- Keep the number of supported steady-state layouts small
- Eliminate broad runtime path mapping from the long-term model
- Preserve standard packaging and framework conventions where they are already the ecosystem norm
- Make canonical locations obvious from directory names alone
- Separate bibliography management from project writing
- Make code, outputs, tasks, and interpretation artifacts easy to connect
- Avoid placeholder top-level directories unless they are actively useful

## Supported Project Profiles

Science should support exactly two active project profiles.

### `research`

Use for projects whose primary output is scientific investigation, reproducible analysis, dataset work, modeling, or experiment interpretation.

Examples:

- `seq-feats`
- `3d-attention-bias`

### `software`

Use for projects whose primary output is a tool, CLI, app, web interface, or library, even if they also contain some research/planning material.

Examples:

- `natural-systems`
- `cats`

## Canonical Common Roots

Science-managed projects should draw from a small common root set:

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `science.yaml`
- `doc/`
- `specs/`
- `tasks/`
- `knowledge/`
- `.ai/`

Rules:

- `AGENTS.md` is the primary agent-facing guide
- `CLAUDE.md` should contain only `@AGENTS.md`
- `doc/` is the canonical root for Science-managed written project artifacts
- `.ai/` contains only project-specific agent overrides/additions and keeps them out of the visible top-level surface
- small software projects do not need to create every optional Science root on day one; avoid scaffolding unused directories just to satisfy symmetry

## Optional Accepted Roots

Some top-level roots are acceptable when they serve a clear purpose and are not duplicating active canonical locations.

Examples:

- `archive/` for retired, superseded, or frozen material that should remain in-repo for reference

Rules:

- `archive/` is optional
- it should not contain the active canonical version of current project artifacts
- migrations may move superseded material into `archive/` instead of deleting it

## Research Profile Layout

```text
project/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── science.yaml
├── tasks/
├── specs/
├── doc/
├── knowledge/
├── .ai/
├── src/                    # optional: installable package root for Python projects
├── tests/                  # optional: package-aligned test root
├── code/
│   ├── scripts/
│   ├── notebooks/
│   ├── workflows/
│   └── <other execution assets>
├── data/
│   ├── raw/
│   └── processed/
├── results/
├── models/
└── papers/
    ├── references.bib
    └── pdfs/
```

Notes:

- `code/` is the canonical root for research execution artifacts such as scripts, notebooks, and workflows
- if the project ships an installable Python package, keep the standard root `src/` layout instead of nesting package code under `code/`
- if root `src/` is present, root `tests/` may remain alongside it
- `papers/` is for bibliography and PDFs only
- written summaries of papers live under `doc/`, not under `papers/`
- use `code/workflows/` consistently; do not split between `workflows/` and `pipelines/`

## Software Profile Layout

```text
project/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── science.yaml
├── tasks/
├── specs/
├── doc/
├── knowledge/
├── .ai/
├── src/
├── tests/
└── <framework-native roots>
```

Examples of framework-native roots:

- `public/`
- `scripts/`
- `assets/`
- `package.json` ecosystem files
- `pyproject.toml` and package metadata

Rules:

- do not force software projects into `code/`
- keep their implementation structure natural for the stack
- still use `doc/`, `specs/`, `tasks/`, and `knowledge/` for Science-managed project context
- use `RESEARCH_PLAN.md` only if it clearly adds value; otherwise keep high-level planning in `README.md` or `doc/plans/`

## Canonical Documentation Taxonomy

All Science-managed writing should live under `doc/` using one vocabulary:

```text
doc/
├── background/
│   ├── topics/
│   └── papers/
├── questions/
├── methods/
├── datasets/
├── searches/
├── discussions/
├── interpretations/
├── reports/
├── meta/
└── plans/
```

Why this taxonomy:

- `background/topics/` makes conceptual background explicit
- `background/papers/` makes paper understanding explicit
- root `papers/` remains reserved for bibliography/PDF management
- `plans/` stays with other project documents instead of splitting planning across roots

## AI Artifacts

Framework defaults should be referenced from the Science framework at runtime. Project-local AI artifacts should exist only when a project needs overrides or additions, and should live under:

```text
.ai/
├── prompts/
└── templates/
```

Rules:

- do not keep active top-level `prompts/` and `templates/` in steady state
- do not copy framework defaults into each project by default
- framework-provided prompts/templates remain the default source of truth
- `.ai/prompts/` and `.ai/templates/` are for project-specific overrides or additions only
- keep only actively used AI-facing material
- if a project has no project-local AI assets, `.ai/` may be absent until needed

## Naming Model For Research Analyses And Results

Research projects should use stable analysis slugs instead of phase names as the primary storage model.

Recommended form:

- `aNNN-short-analysis-name`

Examples:

- `a030-protein-token-frequency-baseline`
- `a118-cv-residualization-rf`

Use the same slug consistently across artifacts:

- `code/scripts/a118-cv-residualization-rf.py`
- `results/a118-cv-residualization-rf/`
- `doc/interpretations/2026-03-18-a118-cv-residualization-rf.md`
- related task references in `tasks/`

Rules:

- phase labels may still appear inside `RESEARCH_PLAN.md`
- phase labels should not be the primary filesystem taxonomy for results
- each durable result directory should correspond to one identifiable analysis unit

## Analysis IDs And Task IDs

Analysis identifiers and task identifiers should be related but distinct.

Recommended convention:

- tasks use `tNNN`
- analysis artifacts use `aNNN`

When an analysis comes directly from a single originating task, reuse the same numeric portion.

Example:

- task `t118`
- analysis slug `a118-cv-residualization-rf`

This preserves traceability while making it clear whether a reference points to:

- a task/work item
- an analysis artifact and its outputs

## RESEARCH_PLAN.md

Keep `RESEARCH_PLAN.md`, but narrow its purpose.

It should contain:

- research direction
- major workstreams
- decision gates
- strategic risks
- deferred lines of inquiry

It should not contain:

- operational task queues
- granular task status tracking
- duplicated bookkeeping already captured in `tasks/`

Placement guidance:

- for research-profile projects with a lightweight `README.md`, the high-level research plan may be inlined as a `README.md` section instead of living in a separate `RESEARCH_PLAN.md`
- for software-profile projects, any research/planning material should usually live in `doc/plans/` unless there is a strong reason to maintain a separate root-level plan file

## science.yaml

`science.yaml` should describe the project at a high level and identify which profile applies.

Add:

- `profile: research | software`
- `layout_version: 2`
- preserve `knowledge_profiles` for the knowledge-graph system

Remove from the steady-state model:

- broad `paths:` remapping support

`data_sources` should remain part of the manifest and should be kept current as new datasets are added.

## Profile And Aspect Relationship

`profile` and `aspects` answer different questions and should both remain explicit.

- `profile` selects the canonical project layout
- `aspects` select behavioral mixins and domain-specific command/template behavior

Rules:

- `profile` does not replace `aspects`
- `aspects` should not be inferred implicitly from `profile`
- common pairings are expected, but should stay explicit in `science.yaml`

Examples:

- a `research` project may use `hypothesis-testing` and `computational-analysis`
- a `software` project may use `software-development`
- a project can still combine multiple aspects where appropriate

## Migration Strategy

Science should not keep a permanent legacy-path execution model.

Instead:

- migrate the current small set of out-of-shape projects up front
- simplify the framework to assume the supported profile layouts only
- use one-time migration procedures and validation during the migration work

This keeps the long-term system smaller and less brittle.

## Project-Specific Migration Targets

### `seq-feats`

Target profile: `research`

Key migrations:

- preserve root `src/` and `tests/` for the installable Python package
- consolidate research execution artifacts under `code/`
- move top-level `scripts/`, `notebooks/`, and `workflow/` under `code/`
- migrate overlapping `notes/` content into canonical `doc/` locations
- normalize `results/` around stable analysis slugs instead of mixed phase buckets
- remove placeholder/unused roots such as `tools/` if not needed

### `3d-attention-bias`

Target profile: `research`

Key migrations:

- preserve root `src/` as the canonical package/production-code root
- consolidate useful exploratory material under `code/`
- collapse `doc/`, `docs/`, and `notes/` into canonical `doc/`
- move active topic notes into `doc/background/topics/`
- move active paper notes into `doc/background/papers/`
- retire duplicate planning roots

### `natural-systems`

Target profile: `software`

Key migrations:

- keep `src/` and `tests/` as canonical implementation roots
- collapse `doc/`, `docs/`, and `guide/` into a single intentional model:
  - `doc/` for Science-managed research/planning/discussion artifacts
  - `guide/` only if it is end-user/content product material and not Science project documentation
- align `science.yaml`, `AGENTS.md`, and `CLAUDE.md` on the same canonical paths
- remove stale or duplicate documentation roots after migration

### `cats`

Target profile: `software`

Key migrations:

- keep `src/` and `tests/` as canonical
- add the standard Science common roots only where useful
- replace `docs/superpowers/` residue with the canonical `doc/` and `.ai/` model if any retained material is still useful
- avoid creating research-specific clutter for a small CLI tool

## Framework-Level Changes Required

The `science` repository should be updated so every layer agrees on the same model:

- `README.md`
- `references/project-structure.md`
- `references/science-yaml-schema.md`
- `references/claude-md-template.md`
- `commands/create-project.md`
- `commands/import-project.md` or replacement migration command
- `scripts/validate.sh`
- `science-tool` path and structure assumptions
- tests covering scaffolding, validation, and graph tooling
- framework prompt/template resolution so defaults are referenced centrally and project `.ai/` directories are override-only

## Decision Summary

Adopt two first-class steady-state profiles:

- `research`
- `software`

Use a single canonical documentation root:

- `doc/`

Use a single hidden root for project-local agent artifacts:

- `.ai/`

Remove general path remapping from the long-term model and migrate the current small set of affected projects up front.
