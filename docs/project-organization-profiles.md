# Project Organization Profiles

Science supports exactly two steady-state project profiles:

- `research`
- `software`

Choose the profile that matches the project's primary output. Use `research` when the project is centered on scientific investigation, reproducible analyses, datasets, models, and interpreted results. Use `software` when the project is primarily a tool, CLI, app, library, or web product, even if it still carries some research or planning material.

## Common Rules

All Science-managed projects use the same core document and metadata roots:

- `science.yaml`
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `doc/`
- `specs/`
- `tasks/`
- `knowledge/`
- `.ai/`

Conventions:

- `CLAUDE.md` should contain only `@AGENTS.md`
- `doc/` is the canonical root for Science-managed writing
- `.ai/` is for project-specific prompt or template overrides only
- framework prompt and template defaults are resolved centrally at runtime
- `archive/` is an accepted optional root for superseded material

## Research Profile

Use `research` for research-first repositories.

Canonical layout:

```text
project/
├── src/                    # optional installable Python package
├── tests/                  # optional package-aligned tests
├── code/
│   ├── scripts/
│   ├── notebooks/
│   └── workflows/
├── data/
│   ├── raw/
│   └── processed/
├── results/
├── models/
└── papers/
    ├── references.bib
    └── pdfs/
```

Rules:

- keep installable Python package code in root `src/`; do not nest package code under `code/`
- use `code/` for execution artifacts such as scripts, notebooks, and workflows
- use `code/workflows/`, not `code/pipelines/`
- use `papers/` only for bibliography management and PDFs
- store topic background in `doc/background/topics/`
- store paper summaries in `doc/background/papers/`

## Software Profile

Use `software` for software-first repositories.

Canonical layout:

```text
project/
├── src/
├── tests/
└── <framework-native roots>
```

Rules:

- do not force software projects into `code/`
- keep implementation roots natural for the stack
- still use `doc/`, `specs/`, `tasks/`, and `knowledge/` for Science-managed context
- keep high-level planning in `README.md` or `doc/plans/`; use `RESEARCH_PLAN.md` only when it adds clear value

## Profile And Aspects

`profile` and `aspects` are separate.

- `profile` selects the directory layout
- `aspects` remain explicit behavior/domain mixins such as `hypothesis-testing`, `computational-analysis`, or `software-development`

Do not use `aspects` as a substitute for layout selection.

## science.yaml

Projects should declare the active profile explicitly:

```yaml
profile: research
layout_version: 2
aspects:
  - computational-analysis
ontologies: [biolink]
knowledge_profiles:
  local: local
```

`ontologies` declares domain vocabulary from community ontologies. `knowledge_profiles` remains part of the canonical manifest and should be kept up to date as projects add or change graph inputs.

## Migration Rules

When migrating an existing project:

1. Pick the target profile first.
2. Collapse duplicate active roots into the canonical root set.
3. Move superseded structure into `archive/` if it still has reference value.
4. Remove broad `paths:` remapping from the steady-state model.
5. Refresh `validate.sh` after framework validator changes (see below).
6. Re-run project validation and project-native tests before merge.

### Refresh `validate.sh`

`validate.sh` is a managed Science artifact (per `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md`). To check for updates:

```bash
science-tool project artifacts check validate.sh
science-tool project artifacts diff validate.sh   # inspect changes
science-tool project artifacts update validate.sh # apply
```

Updates may carry migration steps; the CLI surfaces them interactively.

Specific consolidation rules:

- collapse `docs/`, `notes/`, `guide/`, and similar active writing roots into `doc/`
- collapse top-level `scripts/`, `notebooks/`, and `workflow/` into `code/` for research projects
- collapse `doc/topics/` into `doc/background/topics/`
- collapse `doc/papers/` or `papers/summaries/` into `doc/background/papers/`
- retire copied top-level `prompts/` and `templates/` in favor of central defaults plus optional `.ai/` overrides

## Research Analysis Naming

Research projects should use stable analysis slugs in `results/` rather than phase buckets.

Recommended form:

```text
results/a118-cv-residualization/
results/a142-kmer-embedding-landscape/
```

Conventions:

- use `aNNN-<slug>` for an analysis artifact namespace
- when an analysis comes directly from a task with a 1:1 relationship, reuse the task number: `t118` -> `a118`
- scripts, workflow config, result directories, and interpretation documents should use the same analysis slug where possible

The goal is to make provenance obvious without requiring phase-specific local conventions.

## Code → Task Back-Link

Close the code-side linkage gap (notebooks and scripts → tasks, questions, hypotheses, interpretations) where it is cheap. Four sanctioned patterns:

- **Filename tag** — `t131_<slug>.py`, `q011_<slug>.py`, `h02_<slug>.py`. Best for notebooks. See [`docs/conventions/code-task-backlinks.md`](conventions/code-task-backlinks.md#pattern-1-filename-tag).
- **Comment-block header** — `# task: t131` near the top of the script body. Best when the filename can't carry the tag. See [`docs/conventions/code-task-backlinks.md`](conventions/code-task-backlinks.md#pattern-2-comment-block-header).
- **Descriptor sidecar field** — optional `task` / `question` / `hypothesis` / `interpretation` on artifact descriptor JSONs. Best for artifact-producing scripts. See [`docs/conventions/code-task-backlinks.md`](conventions/code-task-backlinks.md#pattern-3-descriptor-sidecar-field).
- **Commit-message tag** — `fix(t131): ...` Conventional-Commits scope. Orthogonal to the in-file patterns. See [`docs/conventions/code-task-backlinks.md`](conventions/code-task-backlinks.md#pattern-4-commit-message-tag).

Guidance only; no validator rules. See [`docs/conventions/`](conventions/README.md) for the full convention catalog.
