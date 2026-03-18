# 🐀 Science

> *Named after [Science the lab rat](https://adventuretime.fandom.com/wiki/Science) from Adventure Time — an intelligent research assistant who helps explore the unknown.*

Science is a Claude Code plugin that helps scientists and researchers develop ideas, refine hypotheses, represent uncertain claims, and build reproducible computational pipelines.

Its default stance is skeptical:
- hypotheses are organizing conjectures
- claims and relation-claims are the main units of belief
- evidence supports or disputes claims rather than proving them outright
- uncertainty is something to inspect and prioritize, not hide

See [docs/claim-and-evidence-model.md](docs/claim-and-evidence-model.md) for the canonical reasoning model.

## What It Does

Science provides **skills** (structured research methodology), **commands** (interactive research tools), and **aspects** (project-type modifiers) that turn Claude Code into a research colleague:

- **Summarize topics** from Claude's training knowledge, supplemented by web search
- **Summarize papers** using LLM knowledge first, web search second, PDFs only when provided
- **Identify research gaps** and turn them into prioritized next tasks
- **Run structured discussions** (including optional double-blind mode)
- **Review and reprioritize task plans** using explicit rationale
- **Interpret results** as support/dispute updates on claims, hypotheses, and priorities
- **Develop hypotheses** as bundles of uncertain claims with structured falsifiability criteria
- **Pre-register expectations** — formalize predictions and decision criteria before analysis
- **Compare competing hypotheses** — head-to-head evidence evaluation with discriminating predictions
- **Audit for biases** — systematic cognitive and methodological bias checklist
- **Sketch and formalize models** — capture variables, candidate relationships, and unknowns, then attach claim and evidence provenance
- **Build and critique causal DAGs** — identify treatment, outcome, confounders, and check identifiability
- **Plan and review pipelines** — translate inquiries into computational steps with validation criteria
- **Find datasets** from public repositories, ranked by project relevance
- **Create research projects** with consistent, version-controlled structure
- **Import existing projects** into the Science framework without restructuring
- **Validate project structure** with automated checks (template conformance, citation integrity)

## Reasoning Model

Science treats research graphs as uncertain by default.

- hypotheses are organizing conjectures
- claims and relation-claims are the units of belief
- evidence supports or disputes claims
- dashboard summaries should help you find fragile claims, contested regions, and claims lacking empirical support

If a project still mainly expresses confidence as scalar values on hypotheses or questions, and does not yet expose claim-backed evidence, it is only partially migrated to the current model.

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
| `/science:status` | Curated project orientation — hypotheses, questions, uncertainty hotspots, activity, next steps |
| `/science:create-project` | Scaffold a new Science-managed project using the `research` or `software` profile |
| `/science:import-project` | Migrate an existing project into a canonical Science project profile |
| `/science:research-paper` | Research and synthesize a paper (LLM knowledge → web search → PDF) |
| `/science:research-topic` | Research and synthesize a topic with project context |
| `/science:next-steps` | Gap analysis + progress synthesis + prioritized recommendations |
| `/science:discuss` | Structured critical discussion for ideas, hypotheses, or approaches |
| `/science:tasks` | Manage research and development tasks — add, complete, defer, list, filter |
| `/science:search-literature` | Search OpenAlex/PubMed, rank results, and create a prioritized reading queue |
| `/science:find-datasets` | Discover and document candidate datasets from public repositories |
| `/science:add-hypothesis` | Develop and refine a hypothesis as a bundle of uncertain claims |
| `/science:pre-register` | Formalize expectations and decision criteria before analysis |
| `/science:compare-hypotheses` | Head-to-head comparison of competing claim bundles |
| `/science:bias-audit` | Systematic bias and threat-to-validity check |
| `/science:interpret-results` | Interpret results as claim-level support/dispute updates |
| `/science:sketch-model` | Sketch a research model with tentative claims and unknowns |
| `/science:specify-model` | Formalize a model with explicit claims, evidence, and uncertainty |
| `/science:critique-approach` | Review model for problems, sensitivity analysis |
| `/science:plan-pipeline` | Generate implementation plan with QA checkpoints |
| `/science:review-pipeline` | Audit plan against evidence rubric with QA coverage |
| `/science:create-graph` | Build canonical KG sources, audit them, and materialize the graph |
| `/science:update-graph` | Re-audit and re-materialize the graph after source changes |

## Skills

| Skill | Triggers When |
|---|---|
| `research-methodology` | Conducting literature review, evaluating sources, synthesizing findings |
| `scientific-writing` | Writing research documents, background sections, summaries |
| `data-management` | Working with datasets, data packages, provenance |
| `knowledge-graph` | Reference skill loaded by `create-graph` and `update-graph` as background context |
| `causal-dag` | Reference skill loaded by `sketch-model` (causal mode) and `critique-approach` |

## Aspects

Aspects are project-type modifiers declared in `science.yaml` that tailor command behavior to your research context. Commands detect active aspects and adjust their output sections, prompts, and validation accordingly.

| Aspect | Focus |
|---|---|
| `causal-modeling` | Causal inference and DAG-based reasoning |
| `hypothesis-testing` | Formal hypothesis development, tracking, and evaluation |
| `computational-analysis` | Computational and exploratory data analysis |
| `software-development` | Software engineering — applications, tools, and libraries |

For example, with `hypothesis-testing` active, `/science:interpret-results` can add more explicit claim and evidence evaluation. With `causal-modeling`, it adds causal-model implications instead. Aspects compose — a project can activate several at once.

## Project Structure

See [docs/project-organization-profiles.md](docs/project-organization-profiles.md) for migration rules and profile-selection guidance.

Science supports two steady-state project profiles:

- `research` for research-first projects
- `software` for tools, apps, libraries, and CLIs

All Science-managed projects draw from a common root set:

```
project/
├── science.yaml              # Project manifest (profile, aspects, metadata, knowledge_profiles)
├── AGENTS.md                 # Primary operational guide
├── CLAUDE.md                 # Contains only: @AGENTS.md
├── README.md
├── tasks/
├── specs/
├── doc/
├── knowledge/
└── .ai/                      # Optional project-specific AI overrides/additions
```

Research-profile projects add the research execution/data roots:

```
project/
├── src/                      # Optional installable package root for Python projects
├── tests/                    # Optional package-aligned tests
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

Software-profile projects keep their native implementation roots:

```
project/
├── src/
├── tests/
└── <framework-native roots>
```

Conventions:

- `doc/` is the canonical root for Science-managed project documents
- use `doc/background/topics/` for topic background and `doc/background/papers/` for paper summaries
- root `papers/` is bibliography/PDF management only
- use `code/workflows/` consistently; do not split between `workflows/` and `pipelines/`
- framework prompts/templates are resolved centrally; `.ai/` is for project-specific overrides only
- `archive/` is an accepted optional root for superseded material

## Typical Workflow

A research project typically moves through these phases. Commands can be repeated and interleaved as understanding deepens.

### 1. Bootstrap the project

```
/science:create-project
```

Interactive conversation refines your research question, then scaffolds the full directory structure, populates core files, and makes the initial git commit. You'll end up with `science.yaml`, `specs/research-question.md`, a starter `doc/01-overview.md`, and empty slots for everything else.

Projects that use the knowledge graph should also declare profile composition in `science.yaml`:

```yaml
profile: research
layout_version: 2
knowledge_profiles:
  curated: [bio]
  local: project_specific
```

`local` controls the directory name under `knowledge/sources/`. Most projects should keep the default
`project_specific`, but the tooling now honors a different local profile name when explicitly configured.

### 2. State your hypotheses

```
/science:add-hypothesis
```

For each conjecture — even vague ones — this command walks you through clarifying the organizing idea, decomposing it into testable claims, defining falsifiability criteria, listing predictions, and identifying required evidence. Output lands in `specs/hypotheses/` and gets cross-linked to open questions.

As the project matures, treat each hypothesis as a claim bundle rather than a single verdict target.
Important claims should accumulate explicit support or dispute from:

- `literature_evidence`
- `empirical_data_evidence`
- `simulation_evidence`
- `benchmark_evidence`
- `expert_judgment`
- `negative_result`

After adding hypotheses, formalize your expectations:

```
/science:pre-register
```

This walks you through declaring expected outcomes, decision criteria, and a null-result plan — all before running any analysis. The pre-registration is version-controlled and cross-checked later by `/science:interpret-results`.

### 3. Build background knowledge

```
/science:research-topic "circadian regulation of immune response"
```

Synthesizes a structured background document from LLM knowledge + web search, adds BibTeX entries, and saves to `doc/background/topics/`. Repeat for each major topic area your project touches.

### 4. Search the literature

```
/science:search-literature
```

Queries OpenAlex and PubMed with multiple query variants, deduplicates, and ranks results by project relevance. Produces a prioritized reading queue with tiers: *Core now*, *Relevant next*, *Peripheral monitor*. High-priority papers can be queued as tasks via `/science:tasks`.

### 4b. Compare competing explanations

```
/science:compare-hypotheses
```

When 2+ hypotheses exist for the same phenomenon, this command performs a structured head-to-head comparison — identifying discriminating predictions and crucial experiments.

### 5. Summarize key papers

```
/science:research-paper "Doe et al. 2023 circadian immune oscillations"
```

For each high-priority paper from the search, this command synthesizes a structured summary (from LLM knowledge, web search, or a provided PDF), saves it to `doc/papers/`, and updates the bibliography.

### 6. Identify gaps and reprioritize

```
/science:next-steps
```

Audits coverage across five dimensions (concepts, evidence quality, contradictions, testability, data feasibility), synthesizes recent progress and uncertainty hotspots, and recommends 3-5 high-value next actions.

### 7. Stress-test ideas

```
/science:discuss "H1: circadian gating of inflammatory cytokine release"
```

Runs a structured critical discussion that surfaces assumptions, alternative explanations, confounders, and missing evidence. Supports an optional **double-blind mode** where you and the agent write independent analyses before comparing. Discussion output feeds back into open questions and the research plan.

### 7b. Audit for biases

```
/science:bias-audit
```

Systematic check of cognitive and methodological biases against current project state. Especially valuable before interpreting results or when a project feels "too settled".

### 8. Model cause and effect

```
/science:sketch-model
/science:specify-model
/science:critique-approach
```

`sketch-model` captures variables, candidate relationships, data sources, and unknowns as an inquiry subgraph — auto-detecting causal mode when appropriate. `specify-model` formalizes the sketch with explicit claims, support/dispute links, and evidence provenance.

`critique-approach` reviews the model for missing confounders, identifiability issues, structural problems, and sensitivity analysis.

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

This detects stale canonical sources, runs migration/audit checks for unresolved references, and then re-materializes `knowledge/graph.trig` from upstream inputs.

### Iterate

Research isn't linear. A typical session might look like:

```
research-topic → add-hypothesis → pre-register → search-literature → research-paper ×3
→ compare-hypotheses → next-steps → discuss → bias-audit → update-graph
→ sketch-model → specify-model → critique-approach
→ find-datasets → plan-pipeline → review-pipeline
→ [run analysis] → interpret-results → next-steps
```

Each command reads existing project state and builds on it. All artifacts are version-controlled, cross-linked, and validated by `bash validate.sh`.

For knowledge-graph projects, `knowledge/graph.trig` is generated from canonical upstream sources in `specs/`, `doc/`, `tasks/`, and `knowledge/sources/`. If the graph is wrong, fix the source artifact and re-materialize; do not patch the TriG file directly.

## Packages

Science includes two Python packages that back the plugin commands:

| Package | Description |
|---|---|
| `science-model` | Shared Pydantic data models — entities, relations, tasks, profiles, and project config |
| `science-tool` | CLI (`science-tool`) for knowledge graph operations, causal export, dataset validation, and task management |

Both require Python >= 3.11. `science-tool` depends on `science-model` and provides optional extras for causal modeling (`pgmpy`, `ChiRho`), dataset discovery (`httpx`, `pooch`), and graph distillation (`PyKEEN`, `OpenAlex`).

## Design Principles

- **Research as first-class output.** Documents, pipelines, and curated data — not just code.
- **Templates as structural backpressure.** Consistent structure constrains output quality.
- **Persistent state on disk.** All knowledge and progress in version-controlled files.
- **LLM knowledge first.** Use Claude's training data before searching, and search before reading PDFs.
- **Reproducibility by default.** Snakemake, Frictionless data packages, structured metadata.

## License

MIT
