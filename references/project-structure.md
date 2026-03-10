# Science Project Structure Reference

This document describes the standard directory layout for a Science research project.

## Top-Level Files

| File | Purpose | Updated By |
|---|---|---|
| `science.yaml` | Project manifest (name, summary, status, tags, data sources) | User + agent |
| `.env` | API keys (gitignored) | User |
| `.gitignore` | Git ignore rules | Agent on project creation |
| `CLAUDE.md` | Instructions for Claude Code (skill triggers, conventions) | Agent on project creation |
| `AGENTS.md` | Operational guide (tools, validation, conventions) | Agent during loops |
| `RESEARCH_PLAN.md` | High-level research strategy (direction, phases, long-term goals) | Agent during planning |
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

### `doc/` — Research Documents

The primary written output of the project.

- `topics/<topic-slug>.md` — background topic summaries
- `papers/<citekey>.md` — structured paper summaries
- `questions/<slug>.md` — structured open questions
- `methods/<slug>.md` — method and tool notes
- `datasets/<slug>.md` — dataset and accession notes
- `searches/YYYY-MM-DD-<slug>.md` — literature search runs
- `discussions/YYYY-MM-DD-<slug>.md` — structured discussion artifacts
- `interpretations/YYYY-MM-DD-<slug>.md` — result interpretation documents
- `meta/skill-feedback.md` — process reflection log
- `index.md` — document coverage map
- `01-overview.md` through `09-causal-model.md` — structured project narrative
- `99-next-steps.md` — immediate action items
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

### `code/` — Analysis Code

- `pipelines/Snakefile` — Snakemake workflow
- `notebooks/*.py` — Marimo notebooks
- `scripts/` — standalone analysis scripts
- `lib/` — shared Python utilities

### `prompts/` — Role Prompt Packs

- `roles/research-assistant.md` — role instructions for synthesis and prioritization capabilities
- `roles/discussant.md` — role instructions for critical discussion and double-blind mode

### `tools/` — Project Tooling

Python scripts for external services: `openalex.py`, `pubmed.py`, `dag.py`, etc.

### `templates/` — Document Templates

Copied from the Science plugin on project creation.
Includes templates for topics, paper summaries, hypotheses, questions, methods, datasets, and interpretations.

### `aspects/` — Project Aspects (Plugin-Level)

Composable mixins that adapt commands and templates to project characteristics.
Defined in the Science plugin, not in individual projects.

- `causal-modeling/causal-modeling.md` — causal inference, DAGs, structural models
- `hypothesis-testing/hypothesis-testing.md` — formal hypothesis tracking and evaluation
- `computational-analysis/computational-analysis.md` — exploratory analysis, benchmarks, pipelines
- `software-development/software-development.md` — applications, tools, libraries

Projects declare which aspects apply in `science.yaml`:

```yaml
aspects:
  - causal-modeling
  - computational-analysis
```

See `references/science-yaml-schema.md` for the schema and each aspect file for what it contributes.

## Imported Projects

Projects initialized with `/science:import-project` may have non-standard directory layouts.
Check `science.yaml` for a `paths:` section that maps Science conventions to existing directories.

For example, a project with `paths: { doc_dir: docs/, code_dir: src/ }` stores research
documents in `docs/` instead of `doc/` and code in `src/` instead of `code/`.

All Science commands, `validate.sh`, and `science-tool` respect these mappings.
When a `paths:` key is absent, the standard Science default applies.

See `references/science-yaml-schema.md` for the full list of mappable paths.
