# 🐀 Science

> *Named after [Science the lab rat](https://adventuretime.fandom.com/wiki/Science) from Adventure Time — an intelligent research assistant who helps explore the unknown.*

Science is a Claude Code plugin that helps scientists and researchers develop ideas, refine hypotheses, and build reproducible computational pipelines.

## What It Does

Science provides **skills** (structured research methodology), **commands** (interactive research tools), and **aspects** (project-type modifiers) that turn Claude Code into a research colleague:

- **Summarize topics** from Claude's training knowledge, supplemented by web search
- **Summarize papers** using LLM knowledge first, web search second, PDFs only when provided
- **Identify research gaps** and turn them into prioritized next tasks
- **Run structured discussions** (including optional double-blind mode)
- **Review and reprioritize task plans** using explicit rationale
- **Interpret results** and feed findings back into hypotheses, causal models, and priorities
- **Develop hypotheses** with structured falsifiability criteria and evidence tracking
- **Sketch and formalize models** — capture variables, relationships, and unknowns, then add evidence provenance
- **Build and critique causal DAGs** — identify treatment, outcome, confounders, and check identifiability
- **Plan and review pipelines** — translate inquiries into computational steps with validation criteria
- **Find datasets** from public repositories, ranked by project relevance
- **Create research projects** with consistent, version-controlled structure
- **Import existing projects** into the Science framework without restructuring
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
| `/science:status` | Curated project orientation — hypotheses, questions, activity, next steps |
| `/science:create-project` | Scaffold a new research project with full directory structure |
| `/science:import-project` | Add Science framework to an existing project without restructuring |
| `/science:research-paper` | Research and synthesize a paper (LLM knowledge → web search → PDF) |
| `/science:research-topic` | Research and synthesize a topic with project context |
| `/science:research-gaps` | Analyze current project coverage and identify high-impact gaps |
| `/science:discuss` | Structured critical discussion for ideas, hypotheses, or approaches |
| `/science:tasks` | Manage research and development tasks — add, complete, defer, list, filter |
| `/science:next-steps` | Synthesize recent progress, current state, and suggest next actions |
| `/science:search-literature` | Search OpenAlex/PubMed, rank results, and create a prioritized reading queue |
| `/science:find-datasets` | Discover and document candidate datasets from public repositories |
| `/science:add-hypothesis` | Develop and refine a hypothesis interactively |
| `/science:interpret-results` | Interpret analysis results and update the research framework |
| `/science:sketch-model` | Sketch a research model — variables, relationships, and unknowns |
| `/science:specify-model` | Formalize a model with full evidence provenance |
| `/science:build-dag` | Build a causal DAG interactively (treatment, outcome, confounders) |
| `/science:critique-approach` | Review a causal DAG for structural problems and missing confounders |
| `/science:plan-pipeline` | Generate a computational implementation plan from an inquiry |
| `/science:review-pipeline` | Audit a pipeline plan against an evidence rubric |
| `/science:create-graph` | Build a knowledge graph from project documents |
| `/science:update-graph` | Incrementally update the graph after document changes |

## Skills

| Skill | Triggers When |
|---|---|
| `research-methodology` | Conducting literature review, evaluating sources, synthesizing findings |
| `scientific-writing` | Writing research documents, background sections, summaries |
| `data-management` | Working with datasets, data packages, provenance |
| `knowledge-graph` | Building and updating the project knowledge graph |
| `causal-dag` | Building causal DAGs, modeling cause-and-effect, checking identifiability |

## Aspects

Aspects are project-type modifiers declared in `science.yaml` that tailor command behavior to your research context. Commands detect active aspects and adjust their output sections, prompts, and validation accordingly.

| Aspect | Focus |
|---|---|
| `causal-modeling` | Causal inference and DAG-based reasoning |
| `hypothesis-testing` | Formal hypothesis development, tracking, and evaluation |
| `computational-analysis` | Computational and exploratory data analysis |
| `software-development` | Software engineering — applications, tools, and libraries |

For example, with `hypothesis-testing` active, `/science:interpret-results` adds a "Hypothesis Evaluation" section that tracks status transitions. With `causal-modeling`, it adds "Causal Model Implications" instead. Aspects compose — a project can activate several at once.

## Project Structure

When you run `/science:create-project`, Science scaffolds:

```
my-project/
├── science.yaml              # Project manifest (aspects, paths, metadata)
├── .env                      # API keys (gitignored)
├── CLAUDE.md                 # Instructions for Claude Code
├── AGENTS.md                 # Operational guide
├── RESEARCH_PLAN.md          # High-level research strategy
├── tasks/                    # Task queue
│   └── active.md             # Current tasks
├── validate.sh               # Structural validation
├── specs/                    # Research scope
│   ├── research-question.md
│   ├── scope-boundaries.md
│   └── hypotheses/
├── doc/                      # All research documents
│   ├── topics/               # Background topic summaries
│   ├── papers/               # Paper summaries
│   ├── questions/            # Open questions
│   ├── methods/              # Method/tool notes
│   ├── datasets/             # Dataset notes
│   ├── searches/             # Literature search runs
│   ├── discussions/          # Discussion artifacts
│   ├── interpretations/      # Result interpretations
│   ├── meta/                 # Process reflection
│   ├── index.md
│   ├── 01-overview.md        # Project overview
│   ├── 02-background.md      # Background context
│   ├── 03-model.md           # Research model
│   ├── 04-approach.md        # Methodology / approach
│   ├── 05-data.md            # Data landscape
│   ├── 06-evaluation.md      # Evaluation strategy
│   ├── 09-causal-model.md    # Causal model
│   └── 99-next-steps.md      # Next steps
├── papers/                   # References
│   ├── references.bib
│   └── pdfs/
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

Synthesizes a structured background document from LLM knowledge + web search, adds BibTeX entries, and saves to `doc/topics/`. Repeat for each major topic area your project touches.

### 4. Search the literature

```
/science:search-literature
```

Queries OpenAlex and PubMed with multiple query variants, deduplicates, and ranks results by project relevance. Produces a prioritized reading queue with tiers: *Core now*, *Relevant next*, *Peripheral monitor*. High-priority papers can be queued as tasks via `/science:tasks`.

### 5. Summarize key papers

```
/science:research-paper "Doe et al. 2023 circadian immune oscillations"
```

For each high-priority paper from the search, this command synthesizes a structured summary (from LLM knowledge, web search, or a provided PDF), saves it to `doc/papers/`, and updates the bibliography.

### 6. Identify gaps and reprioritize

```
/science:research-gaps
/science:next-steps
```

`research-gaps` audits coverage across five dimensions (concepts, evidence quality, contradictions, testability, data feasibility) and writes `doc/10-research-gaps.md` with prioritized gap-closing tasks.

`next-steps` synthesizes recent progress, current task state, hypothesis status, and open questions to recommend 3-5 high-value next actions.

### 7. Stress-test ideas

```
/science:discuss "H1: circadian gating of inflammatory cytokine release"
```

Runs a structured critical discussion that surfaces assumptions, alternative explanations, confounders, and missing evidence. Supports an optional **double-blind mode** where you and the agent write independent analyses before comparing. Discussion output feeds back into open questions and the research plan.

### 8. Model cause and effect

```
/science:sketch-model
/science:specify-model
/science:build-dag
/science:critique-approach
```

`sketch-model` captures variables, relationships, data sources, and unknowns as an inquiry subgraph. `specify-model` formalizes the sketch with evidence provenance — every variable gets a type, every edge gets evidence.

`build-dag` constructs a causal DAG identifying treatment, outcome, and confounders. `critique-approach` reviews the DAG for missing confounders, identifiability issues, and structural problems.

### 9. Find datasets

```
/science:find-datasets
```

Searches public dataset repositories (via LLM knowledge + repository APIs), ranks results by project relevance, and documents candidates in `doc/datasets/`.

### 10. Plan computational pipelines

```
/science:plan-pipeline
/science:review-pipeline
```

`plan-pipeline` translates a specified inquiry into concrete pipeline steps with tools, configs, tests, and validation criteria. `review-pipeline` audits the plan against an evidence rubric — checking data availability, assumption validity, identifiability, and reproducibility.

### 11. Build the knowledge graph

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
→ research-gaps → next-steps → discuss → update-graph
→ sketch-model → specify-model → build-dag → critique-approach
→ find-datasets → plan-pipeline → review-pipeline
→ research-topic (deeper) → research-paper ×2 → next-steps
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
