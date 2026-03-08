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
| `RESEARCH_PLAN.md` | Prioritized investigation queue | Agent during planning loops |
| `validate.sh` | Structural validation script | Copied from plugin |

## Directories

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
- `10-research-gaps.md` — optional gap analysis and prioritization output
- `99-next-steps.md` — immediate action items

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
