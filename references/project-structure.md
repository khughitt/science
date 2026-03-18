# Science Project Structure Reference

This document describes the standard directory layouts for Science-managed projects.

## Top-Level Files

| File | Purpose | Updated By |
|---|---|---|
| `science.yaml` | Project manifest (profile, aspects, metadata, data sources, knowledge_profiles) | User + agent |
| `.env` | API keys (gitignored) | User |
| `.gitignore` | Git ignore rules | Agent on project creation |
| `CLAUDE.md` | Single-line pointer to `AGENTS.md` | Agent on project creation |
| `AGENTS.md` | Operational guide (tools, validation, conventions) | Agent during loops |
| `RESEARCH_PLAN.md` | Optional high-level research strategy when not inlined into `README.md` | Agent during planning |
| `validate.sh` | Structural validation script | Copied from plugin |

## Directories

### `tasks/` — Task Queue

Lightweight task management.

- `active.md` — current task queue (structured entries with ID, type, priority, status, links)
- `done/YYYY-MM.md` — completed tasks archived monthly

### `specs/` — Research Scope

The "requirements" for the research project.

- `research-question.md` — the overarching question
- `scope-boundaries.md` — what's in/out of scope
- `hypotheses/h01-*.md` — structured hypothesis documents

### `doc/` — Project Documents

The canonical root for Science-managed written output.

- `background/topics/<topic-slug>.md` — background topic summaries
- `background/papers/<citekey>.md` — structured paper summaries
- `questions/<slug>.md` — structured open questions
- `methods/<slug>.md` — method and tool notes
- `datasets/<slug>.md` — dataset and accession notes
- `searches/YYYY-MM-DD-<slug>.md` — literature search runs
- `discussions/YYYY-MM-DD-<slug>.md` — structured discussion artifacts
- `interpretations/YYYY-MM-DD-<slug>.md` — result interpretation documents
- `meta/skill-feedback.md` — process reflection log
- `reports/` — audits and structured reports
- `plans/` — project plans and design docs
- `meta/next-steps-*.md` — gap analysis and prioritization output (written by `/science:next-steps`)

### `papers/` — Reference Management

- `references.bib` — BibTeX database (the single source of truth for citations)
- `pdfs/` — downloaded PDFs (gitignored)

### `knowledge/` — Knowledge Graph Artifacts

- `graph.trig` — RDF knowledge graph
- Build scripts and export files

### `models/` — Formal Models

- `causal-dag.dot` — Graphviz DOT format
- `causal-dag.json` — machine-readable format
- `README.md` — model documentation

### `data/` — Data (Frictionless Data Packages)

- `raw/` — original, unmodified data + `datapackage.json`
- `processed/` — cleaned, transformed data + `datapackage.json`
- `README.md` — data overview

### `code/` — Research Execution Artifacts

- `workflows/` — Snakemake and other workflow definitions
- `notebooks/*.py` — Marimo notebooks
- `scripts/` — standalone analysis scripts
- other execution assets as needed

If a research project ships an installable Python package, keep the package in root `src/`
and tests in root `tests/`. Do not nest the package under `code/`.

### `.ai/` — Project-Specific AI Overrides

- `prompts/` — optional project-specific prompt overrides/additions
- `templates/` — optional project-specific template overrides/additions

Framework defaults for prompts/templates are resolved from the Science framework at runtime.

### `archive/` — Optional Archived Material

Accepted optional root for superseded material that should remain in-repo but is no longer active.

### `aspects/` — Project Aspects (Plugin-Level)

Composable mixins that adapt commands and templates to project characteristics.
Defined in the Science plugin, not in individual projects.

- `causal-modeling/causal-modeling.md` — causal inference, DAGs, structural models
- `hypothesis-testing/hypothesis-testing.md` — formal hypothesis tracking and evaluation
- `computational-analysis/computational-analysis.md` — exploratory analysis, benchmarks, pipelines
- `software-development/software-development.md` — applications, tools, libraries

Projects declare both profile and aspects in `science.yaml`:

```yaml
profile: research
aspects:
  - causal-modeling
  - computational-analysis
```

`profile` selects the canonical layout. `aspects` remain explicit composable behavior mixins.
See `references/science-yaml-schema.md` for the schema and each aspect file for what it contributes.
