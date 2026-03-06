# 🐀 Science

> *Named after [Science the lab rat](https://adventuretime.fandom.com/wiki/Science) from Adventure Time — an intelligent research assistant who helps explore the unknown.*

Science is a Claude Code plugin that helps scientists and researchers develop ideas, refine hypotheses, and build reproducible computational pipelines.

## What It Does

Science provides **skills** (structured research methodology) and **commands** (interactive research tools) that turn Claude Code into a research colleague:

- **Summarize topics** from Claude's training knowledge, supplemented by web search
- **Summarize papers** using LLM knowledge first, web search second, PDFs only when provided
- **Identify research gaps** and turn them into prioritized next tasks
- **Run structured discussions** (including optional double-blind mode)
- **Review and reprioritize task plans** using explicit rationale
- **Capture compact linked notes** across topics, papers, questions, methods, and datasets
- **Develop hypotheses** with structured falsifiability criteria and evidence tracking
- **Create research projects** with consistent, version-controlled structure
- **Validate project structure** with automated checks (template conformance, citation integrity)

## Installation

### From a Marketplace

```
/plugin marketplace add <marketplace-url>
/plugin install science@<marketplace>
```

### Local Development

```
claude --plugin-dir /path/to/science
```

## Commands

| Command | Description |
|---|---|
| `/science:create-project` | Scaffold a new research project with full directory structure |
| `/science:research-paper` | Capability-first paper research/synthesis command |
| `/science:research-topic` | Capability-first topic research/synthesis command |
| `/science:research-gaps` | Analyze current project coverage and identify high-impact gaps |
| `/science:discuss` | Structured critical discussion for ideas, hypotheses, or approaches |
| `/science:review-tasks` | Reprioritize `RESEARCH_PLAN.md` with explicit rationale |
| `/science:search-literature` | Search OpenAlex/PubMed, rank results, and create a prioritized reading queue |
| `/science:summarize-topic` | Write a background document on a topic |
| `/science:summarize-paper` | Summarize a paper (LLM knowledge → web search → PDF) |
| `/science:add-hypothesis` | Develop and refine a hypothesis interactively |
| `/science:create-graph` | Build a knowledge graph from project documents |
| `/science:update-graph` | Incrementally update the graph after document changes |

`/science:summarize-topic` and `/science:summarize-paper` remain supported for backward compatibility.

## Skills

| Skill | Triggers When |
|---|---|
| `research-methodology` | Conducting literature review, evaluating sources, synthesizing findings |
| `scientific-writing` | Writing research documents, background sections, summaries |
| `data-management` | Working with datasets, data packages, provenance |
| `knowledge-graph` | Building and updating the project knowledge graph |

## Project Structure

When you run `/science:create-project`, Science scaffolds:

```
my-project/
├── science.yaml              # Project manifest
├── .env                      # API keys (gitignored)
├── CLAUDE.md                 # Instructions for Claude Code
├── AGENTS.md                 # Operational guide
├── RESEARCH_PLAN.md          # Investigation queue (auto-generated)
├── validate.sh               # Structural validation
├── specs/                    # Research scope
│   ├── research-question.md
│   └── hypotheses/
├── doc/                      # Research documents
│   ├── background/
│   ├── discussions/
│   ├── 01-overview.md
│   ├── ...
│   └── 99-next-steps.md
├── papers/                   # References
│   ├── references.bib
│   ├── pdfs/
│   └── summaries/
├── notes/                    # Compact linked notes
│   ├── topics/
│   ├── articles/
│   ├── questions/
│   ├── methods/
│   └── datasets/
├── models/                   # Formal models (causal DAGs, etc.)
├── knowledge/                # Knowledge graph artifacts
├── data/                     # Frictionless Data Packages
│   ├── raw/
│   └── processed/
├── code/                     # Analysis code
│   ├── pipelines/
│   ├── notebooks/
│   ├── scripts/
│   └── lib/
├── prompts/                  # Role prompt packs
│   └── roles/
├── tools/                    # Project tooling
└── templates/                # Document templates
```

## Typical Workflow

A research project typically moves through these phases. Commands can be repeated and interleaved as understanding deepens.

### 1. Bootstrap the project

```
/science:create-project
```

Interactive conversation refines your research question, then scaffolds the full directory structure, populates core files, and makes the initial git commit. You'll end up with `science.yaml`, `specs/research-question.md`, a starter `doc/01-overview.md`, and empty slots for everything else.

### 2. State your hypotheses

```
/science:add-hypothesis
```

For each conjecture — even vague ones — this command walks you through clarifying the claim, defining falsifiability criteria, listing predictions, and identifying required evidence. Output lands in `specs/hypotheses/` and gets cross-linked to open questions.

### 3. Build background knowledge

```
/science:research-topic "circadian regulation of immune response"
```

Synthesizes a structured background document from LLM knowledge + web search, adds BibTeX entries, and creates a compact linked note in `notes/topics/`. Repeat for each major topic area your project touches.

### 4. Search the literature

```
/science:search-literature
```

Queries OpenAlex and PubMed with multiple query variants, deduplicates, and ranks results by project relevance. Produces a prioritized reading queue with tiers: *Core now*, *Relevant next*, *Peripheral monitor*. High-priority papers get queued in `RESEARCH_PLAN.md`.

### 5. Summarize key papers

```
/science:research-paper "Doe et al. 2023 circadian immune oscillations"
```

For each high-priority paper from the search, this command synthesizes a structured summary (from LLM knowledge, web search, or a provided PDF), adds it to `papers/summaries/`, updates the bibliography, and creates a linked note in `notes/articles/`.

### 6. Identify gaps and reprioritize

```
/science:research-gaps
/science:review-tasks
```

`research-gaps` audits coverage across five dimensions (concepts, evidence quality, contradictions, testability, data feasibility) and writes `doc/10-research-gaps.md` with prioritized gap-closing tasks.

`review-tasks` then reshuffles `RESEARCH_PLAN.md` using an expand/compress method — scoring tasks by impact, uncertainty reduction, feasibility, and dependency order.

### 7. Stress-test ideas

```
/science:discuss "H1: circadian gating of inflammatory cytokine release"
```

Runs a structured critical discussion that surfaces assumptions, alternative explanations, confounders, and missing evidence. Supports an optional **double-blind mode** where you and the agent write independent analyses before comparing. Discussion output feeds back into open questions and the research plan.

### 8. Build the knowledge graph

```
/science:create-graph
```

Reads all project documents and extracts entities (concepts, papers, claims, hypotheses, questions) and their relationships into a formal knowledge graph (`knowledge/graph.trig`). Uses ontology-aligned types and controlled predicates (`cito:supports`, `skos:related`, `scic:causes`, etc.). Source documents get annotated with ontology terms.

After subsequent research rounds, run:

```
/science:update-graph
```

This detects stale documents via content hashing and incrementally adds new entities and relations without disturbing existing ones.

### Iterate

Research isn't linear. A typical session might look like:

```
research-topic → add-hypothesis → search-literature → research-paper ×3
→ research-gaps → review-tasks → discuss → update-graph
→ research-topic (deeper) → research-paper ×2 → review-tasks
```

Each command reads existing project state and builds on it. All artifacts are version-controlled, cross-linked, and validated by `bash validate.sh`.

## Design Principles

- **Research as first-class output.** Documents, pipelines, and curated data — not just code.
- **Templates as structural backpressure.** Consistent structure constrains output quality.
- **Persistent state on disk.** All knowledge and progress in version-controlled files.
- **LLM knowledge first.** Use Claude's training data before searching, and search before reading PDFs.
- **Reproducibility by default.** Snakemake, Frictionless data packages, structured metadata.

## License

MIT
