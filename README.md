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

`/science:summarize-topic` and `/science:summarize-paper` remain supported for backward compatibility.

## Skills

| Skill | Triggers When |
|---|---|
| `research-methodology` | Conducting literature review, evaluating sources, synthesizing findings |
| `scientific-writing` | Writing research documents, background sections, summaries |
| `data-management` | Working with datasets, data packages, provenance |

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

## Design Principles

- **Research as first-class output.** Documents, pipelines, and curated data — not just code.
- **Templates as structural backpressure.** Consistent structure constrains output quality.
- **Persistent state on disk.** All knowledge and progress in version-controlled files.
- **LLM knowledge first.** Use Claude's training data before searching, and search before reading PDFs.
- **Reproducibility by default.** Snakemake, Frictionless data packages, structured metadata.

## License

MIT
