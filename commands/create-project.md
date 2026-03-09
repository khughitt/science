---
description: Scaffold a new Science research project with full directory structure, templates, and configuration. Use when starting a new research project from scratch, or when the user says "new project", "start a project", or "set up a research project."
---

# Create a New Science Research Project

You are scaffolding a new research project. Follow these steps:

## Step 0: Check for Existing Project

> **Note:** If the user has an existing project they want to adopt Science for,
> use `/science:import-project` instead. `create-project` is for brand-new projects only.

Before starting, check if a `science.yaml` already exists in the current directory or any parent. If it does, warn the user that they appear to be inside an existing Science project and ask if they want to:
- Create a new project in a subdirectory
- Overwrite the existing project (dangerous — confirm twice)
- Cancel

## Step 1: Gather Information

Have an interactive conversation with the user to understand:

1. **Project name** — short, descriptive, kebab-case (will become directory name)
2. **Research question** — the overarching question this project investigates
3. **Brief summary** — 2-3 sentences describing the project scope
4. **Initial tags** — keywords for categorization
5. **Known data sources** (if any) — datasets they plan to use

Ask follow-up questions to refine the research question. A good research question is:
- **Specific** enough to be answerable
- **Broad** enough to be interesting
- **Falsifiable** — it should be possible to find evidence against it

Don't ask all questions at once — have a natural conversation. The user may not know all the answers upfront.

## Step 2: Create Directory Structure

Create the following directories and files. Use `$ARGUMENTS` as the project name if provided, otherwise use the name from Step 1.

**Important:** Add `.gitkeep` files to directories that would otherwise be empty, so they survive `git commit` and `git clone`.

```
<project>/
├── science.yaml
├── .env
├── .gitignore
├── CLAUDE.md
├── AGENTS.md
├── RESEARCH_PLAN.md
├── tasks/
│   └── active.md
├── validate.sh
├── specs/
│   ├── research-question.md
│   ├── scope-boundaries.md
│   └── hypotheses/
│       └── .gitkeep
├── doc/
│   ├── topics/
│   │   └── .gitkeep
│   ├── papers/
│   │   └── .gitkeep
│   ├── questions/
│   │   └── .gitkeep
│   ├── methods/
│   │   └── .gitkeep
│   ├── datasets/
│   │   └── .gitkeep
│   ├── searches/
│   │   └── .gitkeep
│   ├── discussions/
│   │   └── .gitkeep
│   ├── interpretations/
│   │   └── .gitkeep
│   ├── meta/
│   │   └── .gitkeep
│   ├── index.md
│   ├── 01-overview.md
│   ├── 02-background.md
│   ├── 03-model.md
│   ├── 04-approach.md
│   ├── 05-data.md
│   ├── 06-evaluation.md
│   ├── 09-causal-model.md
│   └── 99-next-steps.md
├── papers/
│   ├── references.bib
│   └── pdfs/
│       └── .gitkeep
├── knowledge/
│   └── .gitkeep
├── models/
│   └── README.md
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── processed/
│   │   └── .gitkeep
│   └── README.md
├── code/
│   ├── pipelines/
│   │   └── .gitkeep
│   ├── notebooks/
│   │   └── .gitkeep
│   ├── scripts/
│   │   └── .gitkeep
│   └── lib/
│       └── .gitkeep
├── prompts/
│   └── roles/
│       └── .gitkeep
├── tools/
│   └── .gitkeep
└── templates/
```

## Step 3: Populate Core Files

### `science.yaml`

```yaml
name: "<project-name>"
created: "<YYYY-MM-DD>"
last_modified: "<YYYY-MM-DD>"
summary: "<2-3 sentence summary from conversation>"
status: "active"
tags:
  - "<tag1>"
  - "<tag2>"
data_sources: []
```

For the schema, see `${CLAUDE_PLUGIN_ROOT}/references/science-yaml-schema.md`.

### `.gitignore`

```
# Secrets
.env

# Large files
papers/pdfs/

# Data (tracked via datapackage.json, not raw files)
data/raw/*
data/processed/*
!data/raw/.gitkeep
!data/processed/.gitkeep
!data/raw/datapackage.json
!data/processed/datapackage.json

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
.mypy_cache/

# Notebooks
.ipynb_checkpoints/

# Snakemake
.snakemake/

# OS
.DS_Store
```

### `.env`

```
# API keys for Science project tools
# Uncomment and fill in as needed:
# NCBI_API_KEY=your_key_here
# OPENALEX_EMAIL=your_email_here
```

### `CLAUDE.md`

Write project-level instructions by adapting the content from `${CLAUDE_PLUGIN_ROOT}/references/claude-md-template.md`. The template file contains a section marked "Template content starts below" — adapt everything after that marker, filling in project-specific details. Do not copy the instruction header.

### `AGENTS.md`

Write a skeleton operational guide:

```markdown
# Operational Guide

## Project Overview

<one paragraph from conversation about what this project investigates>

## Validation

Run structural checks before committing:

    bash validate.sh
    bash validate.sh --verbose  # for detailed output

## Conventions

- **File naming:** kebab-case for all files and directories
- **Commit messages:** `<scope>: <description>` (e.g., `doc: add background on topic-x`, `hypothesis: add H01`, `papers: summarize Smith2024`)
- **Citations:** Use BibTeX keys `[@AuthorYear]` inline, entries in `papers/references.bib`
- **Markers:** `[UNVERIFIED]` for unverified facts, `[NEEDS CITATION]` for unsourced claims

## Task Execution

Tasks are tracked in `tasks/active.md`. Key constraints for this project:

- <note environment requirements, e.g. "GPU tasks require CUDA 12+", "model X needs torch <2.6">
- <note sequential constraints, e.g. "model loading and package installs must not run in parallel">

Update this section when you discover new constraints during task execution.

## Data Access

<note any known data sources, or "No data sources configured yet.">

## Known Issues

<none yet — add operational learnings here as the project develops>
```

### `RESEARCH_PLAN.md`

Create with an initial header:

```markdown
# Research Plan

> High-level research strategy and direction for this project.
> For the operational task queue, see `tasks/active.md`.

## Research Direction

<brief description of the research approach and phases>

## Long-Term Goals

- <to be defined as the project develops>
```

### `tasks/active.md`

Create an empty task file:

```markdown
<!-- Task queue. Use /science:tasks to manage. -->
```

### `specs/research-question.md`

Write the research question from the conversation. Include:
- The question itself
- Why it matters
- What a successful answer looks like
- Known constraints or scope boundaries

### `specs/scope-boundaries.md`

Write a brief scope document:
- What's in scope (based on conversation)
- What's explicitly out of scope (if discussed)
- If scope boundaries aren't clear yet, note that and leave sections with `<!-- TBD -->` markers

### `papers/references.bib`

Create with a header comment:

```bibtex
% references.bib — BibTeX database for this Science project
% Add entries here for every paper cited in doc/.
% Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)
```

### `doc/01-overview.md`

Write an initial overview document (500-800 words) that:
- States the research question
- Provides brief context
- Outlines the intended approach at a high level
- Notes what's known vs. unknown

### `doc/02-09` and `doc/99` stub files

Create each remaining doc file with a title and placeholder:

```markdown
# <Title>

<!-- This document will be developed as the project progresses. -->
```

Use these titles:
- `02-background.md` → "Background"
- `03-model.md` → "Model"
- `04-approach.md` → "Approach"
- `05-data.md` → "Data"
- `06-evaluation.md` → "Evaluation"
- `09-causal-model.md` → "Causal Model"
- `99-next-steps.md` → "Next Steps"

### `doc/index.md`

```markdown
# Document Index

## Topics
<!-- doc/topics/*.md -->

## Papers
<!-- doc/papers/*.md -->

## Hypotheses
<!-- specs/hypotheses/*.md -->

## Questions
<!-- doc/questions/*.md -->

## Methods
<!-- doc/methods/*.md -->

## Datasets
<!-- doc/datasets/*.md -->
```

### `data/README.md`

```markdown
# Data

This directory contains project data organized as Frictionless Data Packages.

- `raw/` — original, unmodified data (with `datapackage.json` descriptor)
- `processed/` — cleaned, transformed data (with `datapackage.json` descriptor)

See the data-management skill for conventions.
```

### `models/README.md`

```markdown
# Models

This directory contains formal models for the project.

- `causal-dag.dot` — Causal DAG in Graphviz DOT format (when created)
- `causal-dag.json` — Machine-readable causal DAG (when created)

Use `/science:build-dag` to construct and update the causal model.
```

### `validate.sh`

Copy the validation script from `${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh` and make it executable:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh ./validate.sh
chmod +x validate.sh
```

### `templates/`

Copy all templates from `${CLAUDE_PLUGIN_ROOT}/templates/` into the project's `templates/` directory:

```bash
mkdir -p ./templates
cp -R ${CLAUDE_PLUGIN_ROOT}/templates/* ./templates/
```

### `prompts/roles/`

Copy role prompt packs from `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/`:

```bash
mkdir -p ./prompts/roles
cp ${CLAUDE_PLUGIN_ROOT}/references/role-prompts/*.md ./prompts/roles/
```

## Step 4: Initialize Git

```bash
cd <project>
git init
git add -A
git commit -m "Initialize Science research project: <project name>"
```

## Step 5: Verify

Run validation to confirm the scaffold is correct:

```bash
bash validate.sh --verbose
```

It should pass with zero errors. Warnings are acceptable at this stage (e.g., empty hypothesis directory).

## Step 6: Summarize

Tell the user what was created and suggest next steps:
1. Add initial hypotheses with `/science:add-hypothesis`
2. Explore background topics with `/science:research-topic`
3. Research relevant papers with `/science:research-paper`
4. Run `/science:research-gaps` and `/science:next-steps` to prioritize next work
5. Edit `specs/scope-boundaries.md` to refine what's in/out of scope
