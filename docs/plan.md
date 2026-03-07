# Science: Planning Document

> *Named after [Science the lab rat](https://adventuretime.fandom.com/wiki/Science) from Adventure Time — an intelligent research assistant who helps explore the unknown.*

## Vision

**Science** is an open-source Claude Code plugin and staged research copilot system.
It helps scientists and researchers explore ideas, refine hypotheses, formalize explicit models, and operationalize reproducible analyses when needed.
It provides **skills** (structured methodology the agent follows automatically), **commands** (interactive tools invoked via `/science:*`), and — in later phases — **autonomous loop prompts** for sustained research sessions.

The agent draws on patterns from [Superpowers](https://github.com/obra/superpowers) (composable skill framework) and [Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum) (autonomous loop-driven development), adapted for scientific research rather than software engineering.

Science does not replace thinking — the researcher must understand and evaluate the project and results. The goal is to provide a useful research colleague that helps explore and refine ideas, and accelerates the path from initial ideation to a feasible, reproducible, data-based workflow with explicit validation.

### Product Framing

- **Primary framing:** research copilot first; modeling and workflow support are deeper stages, not mandatory requirements for every project.
- **Flexible trajectories, not a fixed pipeline:** many projects start with explore/discuss and may branch to graph/model formalization, software-spec planning, workflow operationalization, or a mix.
- **Multi-agent through role profiles:** a shared system with distinct role configurations (research assistant, discussant/critic, modeler, workflow architect), all grounded in shared project artifacts.
- **Orchestration over framework-building:** Science coordinates existing modeling/pipeline libraries rather than becoming a new causal framework or workflow engine.

### Core Principles

- **Research as first-class output.** The primary artifacts are well-structured documents, reproducible pipelines, and curated data — not just code.
- **Templates as structural backpressure.** Consistent document structure constrains the agent's output quality and gives it familiar scaffolding to work within.
- **Persistent state on disk.** All knowledge, plans, and progress live in version-controlled files. Each loop iteration reads from and writes to this shared state.
- **LLM knowledge first.** Use Claude's training data before searching, and search before reading PDFs. Cross-check key facts that inform project direction.
- **Progressive refinement.** Start interactive (slash commands), scale to autonomous (loops) as the project matures.
- **Reproducibility by default.** Snakemake pipelines, Frictionless data packages, and structured metadata make every result traceable.

### Program-Level Success Criteria (2026)

- A new research project can be scaffolded and produce its first validated background summary in under 15 minutes.
- Literature search + summarization workflows are reproducible from repository state alone (no hidden manual steps).
- Users can follow non-linear paths (for example, research exploration -> software planning -> dataset demos) without losing shared context.
- The knowledge graph layer supports at least three end-to-end workflows: concept exploration, hypothesis traceability, and causal model export.
- Every generated causal model artifact is linked back to provenance-bearing graph assertions.
- `validate.sh` and graph-specific checks are reliable enough to block broken outputs before commit.
- At least one biomedical exemplar project (for example, disease → pathway → intervention) runs through Phases 1-4 completely.

---

## Architecture Overview

### Distribution Model

Science is a **Claude Code plugin**. Users install it via a marketplace or load it locally with `claude --plugin-dir ./science`. This constrains the initial scope to Claude Code users but simplifies installation and testing. The loop infrastructure (Phase 5) may require expanding beyond the plugin model, but that's a future design decision.

### Plugin Structure

```
science/                              # The plugin itself (installed once)
├── .claude-plugin/
│   ├── plugin.json                   # Plugin manifest
│   └── skills/
│       └── knowledge-graph/
│           └── SKILL.md              # Graph authoring skill (entity extraction, ontology, provenance)
├── commands/                         # Slash commands → /science:*
│   ├── create-project.md
│   ├── research-topic.md             # Capability-first topic synthesis
│   ├── research-paper.md             # Capability-first paper synthesis
│   ├── research-gaps.md              # Coverage analysis and gap identification
│   ├── search-literature.md          # OpenAlex/PubMed search + ranking
│   ├── discuss.md                    # Structured critical discussion
│   ├── review-tasks.md               # RESEARCH_PLAN.md reprioritization
│   ├── add-hypothesis.md             # Interactive hypothesis refinement
│   ├── create-graph.md               # Agent-guided graph construction
│   ├── update-graph.md               # Incremental graph updates
│   ├── summarize-topic.md            # (backward compat alias)
│   └── summarize-paper.md            # (backward compat alias)
├── skills/                           # Agent skill definitions
│   ├── research/
│   │   └── SKILL.md                  # Core research methodology
│   ├── writing/
│   │   └── SKILL.md                  # Scientific writing conventions
│   └── data/
│       ├── SKILL.md                  # Data management
│       └── sources/
│           ├── openalex.md           # OpenAlex search/normalization guide
│           └── pubmed.md             # PubMed E-utilities guide
├── templates/                        # Document templates (copied into projects)
│   ├── background-topic.md
│   ├── paper-summary.md
│   ├── hypothesis.md
│   ├── discussion.md
│   ├── open-question.md
│   ├── data-source.md
│   └── notes/
│       ├── index.md
│       ├── topic-note.md
│       ├── article-note.md
│       ├── question-note.md
│       ├── method-note.md
│       └── dataset-note.md
├── scripts/
│   └── validate.sh                   # Structural validation (copied into projects)
├── references/                       # Reference docs for agent use
│   ├── claude-md-template.md         # Template for project CLAUDE.md
│   ├── notes-organization.md         # Notes system conventions
│   ├── project-structure.md          # Directory layout reference
│   ├── science-yaml-schema.md        # Manifest format documentation
│   └── role-prompts/
│       ├── research-assistant.md     # Research assistant role profile
│       └── discussant.md             # Critical discussant role profile
├── science-tool/                     # Python CLI package (graph, distill, DOI)
│   ├── pyproject.toml
│   ├── src/science_tool/
│   │   ├── cli.py                    # Click CLI entry point
│   │   ├── output.py                 # Shared query output contract (table/json)
│   │   ├── doi.py                    # DOI metadata lookup
│   │   ├── prose.py                  # Prose annotation scanner
│   │   ├── graph/
│   │   │   ├── store.py              # Graph store, queries, entity management
│   │   │   └── viz_template.py       # Marimo visualization notebook template
│   │   └── distill/
│   │       ├── openalex.py           # OpenAlex hierarchy distiller
│   │       └── pykeen_source.py      # PyKEEN dataset distiller
│   └── tests/
└── README.md
```

### Generated Project Structure

When a user runs `/science:create-project`, the plugin scaffolds this in their working directory:

```
my-project/                           # A research project (one per investigation)
├── science.yaml                      # Project manifest
├── .env                              # API keys (gitignored)
├── .gitignore
├── CLAUDE.md                         # Project-level instructions for Claude Code
├── AGENTS.md                         # Operational guide
├── RESEARCH_PLAN.md                  # Investigation queue (auto-populated)
├── validate.sh                       # Copied from plugin
├── specs/                            # Research scope
│   ├── research-question.md
│   ├── scope-boundaries.md
│   └── hypotheses/
│       └── h01-*.md
├── doc/                              # Research documents (primary output)
│   ├── background/
│   │   └── NN-topic-name.md
│   ├── 01-overview.md
│   ├── 02-background.md
│   ├── 03-model.md
│   ├── 04-approach.md
│   ├── 05-data.md
│   ├── 06-evaluation.md
│   ├── 07-hypotheses.md
│   ├── 08-open-questions.md
│   ├── 09-causal-model.md
│   └── 99-next-steps.md
├── papers/                           # Reference management
│   ├── references.bib
│   ├── pdfs/                         # (gitignored)
│   └── summaries/
│       └── AuthorYear-short-title.md
├── notes/                            # Compact linked notes
│   ├── index.md
│   ├── topics/
│   ├── articles/
│   ├── questions/
│   ├── methods/
│   └── datasets/
├── knowledge/                        # Knowledge graph artifacts (Phase 3)
├── models/                           # Formal models (Phase 4)
│   └── README.md
├── data/                             # Frictionless Data Packages (Phase 4)
│   ├── raw/
│   ├── processed/
│   └── README.md
├── code/                             # Analysis code
│   ├── pipelines/
│   ├── notebooks/
│   ├── scripts/
│   └── lib/
├── tools/                            # Thin wrappers around shared `science-tool` CLI (Phase 2+)
└── templates/                        # Copied from plugin
```

### How It Maps to Ralph/Superpowers

| Concept | Software Dev (Ralph) | Research Agent |
|---|---|---|
| Requirements | `specs/*.md` | `specs/` — research questions, hypotheses, scope |
| Task queue | `IMPLEMENTATION_PLAN.md` | `RESEARCH_PLAN.md` — prioritized investigation queue |
| Operational guide | `AGENTS.md` | `AGENTS.md` — tools, data sources, conventions |
| Source code | `src/` | `code/`, `data/`, `doc/` |
| Backpressure | Tests (pass/fail) | `validate.sh` — structural validation, citation checks, template conformance |
| Completion signal | Tests pass → commit | Section drafted + validated → commit |
| Subagent work | Code search, implementation | Literature search, summarization, data analysis |

### Four Modes of Operation

1. **Interactive (slash commands)** — Single-turn tools for specific tasks. User initiates, agent executes, user reviews. Best for: early-stage work, paper summaries, hypothesis refinement. **(Phase 1 — implemented)**

2. **Planning loop** — Autonomous gap analysis. Reads specs + existing docs, identifies what's missing or incomplete, generates/updates `RESEARCH_PLAN.md`. Best for: periodic reassessment of project state. *(Phase 5)*

3. **Research loop** — Autonomous deep work. Picks tasks from `RESEARCH_PLAN.md`, researches topics, writes/updates docs, commits. Best for: bulk literature review, background writing, systematic exploration. *(Phase 5)*

4. **Exploration loop** — Open-ended investigation. Reads open questions, follows citation chains, identifies new directions. Best for: discovery phase, finding unexpected connections. *(Phase 5)*

### Staged Research Model

| Stage | Goal | Required? | Typical roles |
|---|---|---|---|
| A. Explore and discuss | Build shared understanding, identify gaps, sharpen questions | Yes | `research-assistant`, `discussant` |
| B. Formalize | Encode key concepts/claims and causal assumptions in graph/model artifacts | Optional | `modeler`, `discussant` |
| C. Operationalize | Connect datasets and build reproducible computational workflows | Optional | `workflow-architect`, `modeler` |

These stages are a reusable vocabulary, not a strict sequence.
Projects can stop at Stage A, iterate between stages, or branch to software-oriented planning while still using shared graph and evidence artifacts.

### Example Non-Linear Path

`explore/discuss` -> `software specs/plans` -> `dataset discovery for demos` -> `optional graph/model refinement`

This pattern supports tool-building projects where the primary output is software design and implementation plans, not only causal/model outputs.

### Role Profiles (Shared Context, Different Emphasis)

- `research-assistant`: literature synthesis, topic mapping, background expansion, evidence hygiene.
- `discussant`: critical dialogue, alternative explanations, confounder surfacing, hypothesis stress-testing.
- `modeler`: graph and causal structure formalization, identification checks, model export preparation.
- `workflow-architect`: data-source integration, pipeline scaffolding, reproducibility guardrails.

All roles operate over the same repository artifacts (`specs/`, `doc/`, `knowledge/`, `code/`, `RESEARCH_PLAN.md`) to avoid context fragmentation.

### Knowledge + Model Representation Stack

To avoid ambiguity between prose outputs and computational artifacts, Science uses a layered representation:

| Layer | Primary artifact | Purpose |
|---|---|---|
| Research narrative | `doc/*.md`, `papers/summaries/*.md` | Human-readable synthesis and decisions |
| Structured knowledge | `knowledge/graph.trig` (`:graph/knowledge`, `:graph/provenance`, `:graph/datasets`) | Machine-checkable claims, evidence, and data links |
| Causal structure | `knowledge/graph.trig` (`:graph/causal`) | Explicit assumptions for causal reasoning |
| Executable models | `code/models/*.py` (PyMC/Pyro generated + edited) | Simulation, estimation, and critique workflows |

The companion design doc [docs/plans/2026-03-01-knowledge-graph-design.md] defines the ontology and graph-level use cases in detail.
Capability and role contract definitions are captured in [docs/plans/2026-03-02-agent-capabilities-design.md].

---

## Templates

Templates serve dual purposes: they guide human writing AND constrain agent output. Every template should be concise enough that the agent can hold it in context alongside the actual content it's producing.

The following templates are implemented in `templates/`:

| Template | Purpose | Used By |
|---|---|---|
| `background-topic.md` | Structured topic summaries | `/science:summarize-topic` |
| `paper-summary.md` | Structured paper summaries with source provenance | `/science:summarize-paper` |
| `hypothesis.md` | Falsifiable hypotheses with predictions and evidence tracking | `/science:add-hypothesis` |
| `open-question.md` | Prioritized questions with approaches | Commands, loops |
| `data-source.md` | Data acquisition and preprocessing docs | Manual, data skill |
| `notes/topic-note.md` | Compact topic note format | `/science:research-topic`, `/science:search-literature` |
| `notes/article-note.md` | Compact article note format | `/science:research-paper`, `/science:search-literature` |
| `notes/question-note.md` | Compact question note format | `/science:search-literature`, `/science:discuss` |
| `notes/method-note.md` | Compact method note format | Manual, future workflow commands |
| `notes/dataset-note.md` | Compact dataset/accession note format | `/science:find-datasets`, `/science:search-literature` |

Templates deferred to later phases:
- `pipeline-step.md` — Phase 4 (Snakemake workflows)
- `experiment.md` — Phase 4 (computational experiments)

---

## Skills

Skills are structured instruction sets loaded into the agent's context when performing specific types of work. Each skill directory contains a `SKILL.md` with YAML frontmatter (name, description) and markdown instructions.

Skills trigger in two ways:
1. **Automatic:** The project's `CLAUDE.md` contains rules that trigger skill reads for common task types.
2. **Explicit:** Commands reference specific skills in their "Before Writing" sections.

This is intentional redundancy — both mechanisms complement each other.

### Implemented Skills (Phase 1)

**`skills/research/SKILL.md` — Research Methodology**
- Source hierarchy (LLM knowledge → web search → PDF)
- Confidence calibration for LLM-first summaries (high/moderate/low thresholds)
- Cross-checking key facts before committing to documents
- Source evaluation criteria (relevance, recency, quality, reproducibility, consensus)
- Synthesis over summarization (agreement, disagreement, gaps, assumptions)
- Hypothesis development workflow (falsifiability, predictions, evidence)
- Citation discipline (`[@AuthorYear]`, `[UNVERIFIED]`, `[NEEDS CITATION]` markers)
- Project awareness (check existing docs before writing to prevent duplication)

**`skills/writing/SKILL.md` — Scientific Writing**
- Voice and tone (precise, evidence-based, concise, active voice)
- Hedging guide (confidence level → appropriate language)
- Document structure principles (lead with the point, sections self-contained, end with implications)
- Citation format (inline, multiple, narrative, with page numbers)
- Formatting conventions (ATX headers, one sentence per line, tables for comparisons)
- Length guidelines per document type

**`skills/data/SKILL.md` — Data Management**
- Core principles (raw data immutable, Frictionless packages, provenance, reproducible preprocessing)
- Directory conventions
- Source-skill references for OpenAlex and PubMed
- Interim manual workflow fallback (when structured tooling is unavailable)

### Implemented Skills (Phase 2)

| Skill | Purpose |
|---|---|
| `skills/data/sources/openalex.md` | OpenAlex source guidance for literature search and metadata normalization |
| `skills/data/sources/pubmed.md` | PubMed E-utilities source guidance for biomedical literature search |

### Implemented Skills (Phase 3)

| Skill | Purpose |
|---|---|
| `.claude-plugin/skills/knowledge-graph/SKILL.md` | Entity extraction, ontology alignment (Biolink, CiTO, SKOS), relation types, provenance discipline, graph layering, prose annotation guidance |

### Skills Planned for Later Phases

| Skill | Phase | Purpose |
|---|---|---|
| `skills/models/causal-dag.md` | 4 | DAG construction, d-separation, adjustment sets |
| `skills/pipelines/snakemake.md` | 4 | Workflow construction |
| `skills/pipelines/marimo.md` | 4 | Reactive notebooks |

---

## Commands

Each command is a markdown file in `commands/` with YAML frontmatter (description) and structured instructions. All commands are namespaced as `/science:*`.

### Implemented Commands (Phase 1)

**`/science:create-project`**
- Interactive conversation to refine research question
- Scaffolds full project directory structure with `.gitkeep` files
- Populates core files: `science.yaml`, `CLAUDE.md`, `AGENTS.md`, `RESEARCH_PLAN.md`, `references.bib`, doc stubs
- Copies templates and `validate.sh` from plugin
- Initializes git and commits
- Checks for existing project (prevents accidental overwrite)

**`/science:summarize-topic`**
- Reads research-methodology and scientific-writing skills
- Checks for existing coverage in `doc/background/` (prevents duplication)
- Follows source hierarchy: LLM knowledge → web search (no PDFs unless provided)
- Writes to `doc/background/NN-topic-name.md` following template
- Updates `references.bib`, cross-references hypotheses and open questions
- Creates `references.bib` if it doesn't exist

**`/science:summarize-paper`**
- Accepts paper title, author, DOI, URL, or PDF file path
- Checks for existing summary in `papers/summaries/`
- Three source strategies: title/author → LLM first; PDF → guided extraction; URL → fetch + supplement
- Paper Not Found fallback: asks for more info, refuses to fabricate
- Includes source provenance field (LLM knowledge / web search / PDF)
- Creates `references.bib` if it doesn't exist

**`/science:add-hypothesis`**
- Reads existing hypotheses to avoid duplication
- Adaptive interactive refinement (guidelines, not rigid questionnaire — skips ahead if input is specific)
- Five dimensions: clarify claim, test falsifiability, identify predictions, assess evidence needs, check connections
- Assigns sequential ID (lowercase `h` in filenames, uppercase `H` for cross-references)
- Updates `doc/07-hypotheses.md` and `doc/08-open-questions.md`
- Suggests relevant papers (cross-checked via web search)

### Implemented Commands (Phase 2)

| Command | Purpose |
|---|---|
| `/science:research-paper` | Capability-oriented single-paper synthesis (maps to `summarize-paper`) |
| `/science:research-topic` | Capability-oriented topic synthesis (maps to `summarize-topic`) |
| `/science:research-gaps` | Analyze project coverage and generate prioritized gap tasks |
| `/science:discuss` | Structured critical discussion mode (including double-blind flow) |
| `/science:review-tasks` | Re-rank and justify priorities in `RESEARCH_PLAN.md` |
| `/science:search-literature` | Literature search via LLM knowledge + web search + OpenAlex/PubMed guidance |

### Implemented Commands (Phase 3)

| Command | Purpose |
|---|---|
| `/science:create-graph` | Agent-guided initial knowledge graph construction from project artifacts |
| `/science:update-graph` | Agent-guided incremental graph updates with change detection via `graph diff` |

### Implemented Commands (Phase 4a)

| Command | Purpose |
|---|---|
| `/science:sketch-model` | Agent-guided inquiry subgraph sketching from research context |
| `/science:specify-model` | Formal variable/edge/parameter specification for an inquiry |
| `/science:plan-pipeline` | Computational pipeline planning from inquiry structure |
| `/science:review-pipeline` | Critical review of inquiry/pipeline against 7-dimensional rubric |

### Commands Planned for Later Phases

| Command | Phase | Purpose |
|---|---|---|
| `/science:find-datasets` | 4b | Discover and document candidate datasets for research or tool demos |
| `/science:build-dag` | 4b | Interactive causal DAG construction (optional, project-dependent) |
| `/science:critique-approach` | 4b | Identify weaknesses using graph/model + literature |
| `/science:explore-open-questions` | 5 | Autonomous exploration of open questions |

---

## Validation / Backpressure

### `validate.sh`

Structural checks that serve as backpressure in the research workflow. Returns non-zero on failure (errors), zero on success (including warnings). Designed to be run before every commit.

**Implemented checks (Phase 1):**

| # | Check | Severity | What It Catches |
|---|---|---|---|
| 1 | Project manifest | Error | Missing `science.yaml` or required fields |
| 2 | Core structure | Error | Missing required directories (`specs/`, `doc/`, `papers/`, `data/`, `code/`) or files (`CLAUDE.md`, `AGENTS.md`) |
| 3 | Research question | Error | Missing `specs/research-question.md` |
| 4 | Background doc conformance | Warning | Background docs missing template sections |
| 5 | Hypothesis completeness | Error/Warning | Missing `## Falsifiability` section or empty content, missing `Status` field |
| 6 | Citation integrity | Warning | `[@Key]` citations in docs without matching `references.bib` entries |
| 7 | Paper summary conformance | Warning | Summaries missing template sections |
| 8 | Unresolved markers | Warning | `[UNVERIFIED]` and `[NEEDS CITATION]` counts |

**Implemented checks (Phase 2 additions):**

| # | Check | Severity | What It Catches |
|---|---|---|---|
| 9 | Research gaps conformance | Warning | `doc/10-research-gaps.md` missing required sections or missing explicit P1/P2/P3 markers |
| 10 | `RESEARCH_PLAN.md` conventions | Warning | Missing Stage A plan sections, legacy `## Status` format, weak/empty rationale, oversized active queue |
| 11 | Discussion conformance | Warning | `doc/discussions/*.md` missing required sections, including double-blind sections when mode is `double-blind` |
| 12 | Notes conformance | Warning | `notes/*/*.md` missing required frontmatter/sections, note `type`-path mismatches, malformed optional `datasets` lists |

**Checks planned for later phases:**
- Internal link integrity (no broken cross-references)
- Data package validity (Frictionless `datapackage.json` validation)
- DAG validity (no cycles in `models/causal-dag.*`)
- Open questions freshness (questions older than N days flagged for review)

---

## Tooling (Python)

Tooling is split into a reusable shared package and optional per-project wrappers:

| Layer | Status | Purpose |
|---|---|---|
| `science-tool/` package (inside plugin repo) | Implemented | Graph store, query presets, DOI lookup, distillation (OpenAlex, PyKEEN), visualization, validation |
| `tools/*` in generated projects (optional wrappers) | Planned | Thin project-local helper scripts that call `uv run science-tool ...` with project defaults |

Current `science-tool` CLI surface: `graph` (17 subcommands), `inquiry` (8 subcommands), `distill` (2 subcommands), `doi` (1 subcommand). 106 tests across 4 test files (+ 10 in `test_distill.py` blocked by missing `numpy` dev dep).

This avoids duplicated logic across commands, loops, and ad-hoc scripts.

---

## Loop Prompts

All planned for Phase 5. The plugin model may need extension to support loops (which require running `claude` in a shell loop with prompt files). Design options include:
- A `/science:loop` command that executes the outer loop
- A standalone `loop.sh` script that wraps `claude --plugin-dir`
- An agent definition that implements the loop internally

### `PROMPT_plan.md` — Research Planning Mode

The agent reads all `specs/`, existing `doc/`, and `papers/summaries/`. Performs gap analysis, prioritizes tasks, generates/updates `RESEARCH_PLAN.md`. Does NOT write research docs or code.

### `PROMPT_research.md` — Research Execution Mode

The agent picks the highest-priority task from `RESEARCH_PLAN.md`, reads relevant skills, executes the task, validates, updates the plan, and commits. Loop restarts with fresh context.

### `PROMPT_explore.md` — Exploration Mode

The agent reads open questions and next steps, follows interesting threads, writes findings, proposes new hypotheses or tasks. Updates `RESEARCH_PLAN.md` with discoveries.

---

## AGENTS.md Content

The operational guide. Present in every generated project. Contains:

- **Project overview** — one paragraph on what this research is about
- **Validation** — how to run `validate.sh`
- **Conventions** — file naming (kebab-case), commit message format (`<scope>: <description>`), citation style
- **Data access** — which data sources are available, any credentials needed
- **Known issues** — operational learnings from previous work

---

## CLAUDE.md Content

Project-level instructions that Claude Code reads automatically. Includes **automatic skill triggers**:

- **Writing any document in `doc/` or `papers/summaries/`:** Read the `scientific-writing` skill
- **Literature review, source evaluation, paper summarization:** Read the `research-methodology` skill
- **Working with data sources:** Read the `data-management` skill

Additional instructions:
- Use templates for all new documents
- Run `validate.sh` before committing
- Commit after each completed unit of work
- Update `RESEARCH_PLAN.md` with discoveries
- Cross-reference: when writing about a topic, check if related hypotheses or open questions exist
- Paper summarization order: LLM knowledge → web search → PDF (only if user provides path)
- Mark unverified facts with `[UNVERIFIED]` and unsourced claims with `[NEEDS CITATION]`

---

## Implementation Phases

### Phase 1: Foundation ✅

Scaffold the plugin structure, write templates, create core skills and commands.

**Deliverables:**
- [x] Plugin structure (`.claude-plugin/plugin.json`, `commands/`, `skills/`, `templates/`, `scripts/`, `references/`)
- [x] `science.yaml` project manifest format (documented in `references/science-yaml-schema.md`)
- [x] All Phase 1 templates (`background-topic.md`, `paper-summary.md`, `hypothesis.md`, `open-question.md`, `data-source.md`)
- [x] `CLAUDE.md` template (in `references/claude-md-template.md`)
- [x] `AGENTS.md` skeleton (generated by `create-project` command)
- [x] `.gitignore` template (covers `.env`, PDFs, data, Python caches, Snakemake, OS files)
- [x] `/science:create-project` command (interactive scaffolding with `.gitkeep`, doc stubs, validation)
- [x] `/science:summarize-topic` command (LLM-first, handles missing `references.bib`)
- [x] `/science:summarize-paper` command (LLM-first, Paper Not Found fallback, source provenance)
- [x] `/science:add-hypothesis` command (adaptive refinement, ID conventions, cross-referencing)
- [x] `validate.sh` with 8 structural checks (tested against 5 scenarios)
- [x] `skills/research/SKILL.md` (source hierarchy, confidence calibration, synthesis methodology)
- [x] `skills/writing/SKILL.md` (voice, hedging, formatting, length guidelines)
- [x] `skills/data/SKILL.md` (stub with interim manual workflow)
- [x] `README.md` (plugin documentation)
- [x] Agent capability API + role profile design draft (`docs/plans/2026-03-02-agent-capabilities-design.md`)

**Review findings (22 issues, all fixed):**
- Critical: `validate.sh` — `set -e` incompatible with error-counting pattern; marker counting double-output bug from `pipefail` + `|| echo 0` interaction
- Important: empty dirs lost on git clone (added `.gitkeep`); doc stubs 02-09 had no content; missing initial `RESEARCH_PLAN.md`, `references.bib` content; CLAUDE.md template structure confusing; hypothesis questionnaire too rigid
- Added: confidence calibration for LLM-first paper summaries; Paper Not Found fallback; existing project detection; `last_modified` validation; data skill interim workflow

### Phase 2: Capability-First Core (Stage A Priority)

Deliver the highest-value role profiles and capability interfaces for non-linear research workflows.

**Deliverables:**
- [x] Implement Stage A capability set: `research_paper`, `research_topic`, `research_gaps`, `discuss`, `review_tasks`
- [x] Define command naming migration/alias strategy (`summarize-*` compatibility vs capability-first names)
- [x] Add role-profile prompt packs for `research-assistant` and `discussant`
- [x] Implement double-blind discussion flow and discussion artifact template (`doc/discussions/`)
- [x] Add prioritization writeback conventions for `RESEARCH_PLAN.md` (expand -> compress loop)
- [x] Extend validation checks for Stage A outputs (gap-analysis structure, task rationale completeness)
- [x] `/science:search-literature` command with OpenAlex/PubMed source skills
- [x] `skills/data/sources/openalex.md` and `skills/data/sources/pubmed.md` source guides

### Phase 3: Shared Knowledge Runtime + Stage B Entry ✅

Establish the `science-tool` Python package, graph infrastructure, and agent-guided
formalization workflows. Validate end-to-end on one exemplar project.

Detailed specifications for the ontology, CLI surface, query presets, and delivery slices
are in the companion [docs/plans/2026-03-01-knowledge-graph-design.md].

**Key design decisions:**
- `science-tool` lives inside the plugin repo (monorepo), installed via `uv`.
- No literature search in the CLI — agents handle this effectively via LLM knowledge + web search.
- Graph authoring is agent-guided (not fully automated), backed by a dedicated skill.
- Agent-facing CLI uses use-case-driven query presets, not raw SPARQL.
- Prose ↔ graph bridge via ontology annotations (frontmatter `ontology_terms:` + inline CURIEs).
- Graph revision metadata (timestamp + content hash) is stored in graph metadata for change detection.

**Phase 3 execution guardrails (refined 2026-03-03):**
- Strict dependency chain: 3a (foundation) -> 3b (authoring) -> 3c (bootstrapping) -> 3d (validation/exemplar). No slice starts before prerequisites are green.
- CLI contract is part of scope: every graph command supports `--format table|json`; non-zero exit codes are required for validation/parse failures.
- `graph diff` uses hybrid staleness detection (mtime + content hash), not mtime-only checks.
- Snapshot reproducibility is mandatory: each snapshot manifest records source URI, fetch date, upstream version/date, node/triple counts, and SHA-256 checksum.
- Phase 3 non-goals remain explicit: no DAG export execution path, no automated entity matching pipeline, no SHACL engine (document design only).
- Phase 3 done criteria must be evidenced by command output and test logs, not narrative completion claims.

**Deliverables (3a — Graph Foundation):** ✅
- [x] `science-tool/` package scaffold inside plugin repo (`pyproject.toml`, `uv` managed)
- [x] Graph store: `science_tool/graph/{store,viz_template}.py`, `cli.py`, `output.py`, `prose.py`, `doi.py`
- [x] CLI: `graph init`, `graph stats`, `graph add` (concept, paper, claim, hypothesis, question, edge), `graph predicates`, `graph scan-prose`, `graph stamp-revision`
- [x] CLI contract: `--format table|json` output on all query commands + stable non-zero failure exit codes
- [x] Use-case query presets: `graph neighborhood`, `graph claims`, `graph evidence`, `graph coverage`, `graph gaps`, `graph uncertainty`
- [x] Change detection: `graph diff` (hybrid file mtimes + content hash vs graph revision metadata)
- [x] Validation: `graph validate` (structural checks on `graph.trig`) — parseability, claim/hypothesis provenance completeness, causal acyclicity
- [x] Visualization: `graph viz` (Graphviz DOT → file/stdout) *(kitty/SVG rendering fallback still pending)*
- [x] DOI lookup: `doi lookup <doi>` (fetch metadata from CrossRef/OpenAlex for note validation)
- [x] Test suite: 48 CLI tests + 7 prose scanner tests covering init/stats/add/validate/diff/viz/lookup/queries/enrichment

**Deliverables (3b — Graph Authoring):** ✅
- [x] `.claude-plugin/skills/knowledge-graph/SKILL.md` (entity extraction, ontology alignment with CiTO/SKOS/Biolink, relation types, provenance discipline, graph layering, prose annotation guidance)
- [x] `/science:create-graph` command (agent-guided initial graph construction from project artifacts)
- [x] `/science:update-graph` command (agent-guided incremental updates with change detection via `graph diff`)
- [x] Prose annotation conventions (frontmatter `ontology_terms:` + inline CURIEs) documented in skill and enforced by `graph scan-prose`

**Deliverables (3c — Knowledge Base Bootstrapping):** ✅
- [x] `science_tool/distill/{openalex,pykeen_source}.py` distillation modules
- [x] `science-tool distill openalex` and `science-tool distill pykeen` CLI commands
- [x] Import flow: `science-tool graph import <snapshot>` → `:graph/knowledge`
- [x] Pre-generated snapshots: `data/snapshots/openalex-science-map.ttl` + `manifest.ttl`
- [x] Biomedical starter profile: `docs/biomedical-starter-profile.md` (ontology types, predicates, CURIE prefixes, example commands, graph size guidelines)
- [x] Fix `test_distill.py` — add `numpy` to dev deps ✅ (`1612394`)
- [x] ~~Ontology caching groundwork~~ — **deferred** to Phase 4b (not required for Phase 3 gate; groundwork for future entity matching)

**Deliverables (3d — Validation + Exemplar):** ✅
- [x] `validate.sh` graph checks: parseable TriG, provenance completeness, orphaned nodes, causal acyclicity, graph-prose sync staleness
- [x] Biomedical exemplar: `~/d/3d-attention-bias/` — 3D Structure-Aware Attention Bias for Nucleic Acid Foundation Models
- [x] Exemplar evidence bundle archived at `docs/exemplar-evidence/` (graph-stats, graph-validate, graph-diff, neighborhood query, claims query, coverage query, validate.sh log)
- [x] Exemplar graph: 2,761 triples (35 concepts, 25 papers, 27 claims, 1 hypothesis, 10 questions + 1,684 OpenAlex import), all 4 validation checks pass

**Phase 3 Progress Snapshot (2026-03-07 — GATE CLOSED):**
- **3a (Graph Foundation): Complete.** All CLI commands implemented. 48 CLI tests + 7 prose scanner tests passing.
- **3b (Graph Authoring): Complete.** Knowledge-graph skill, `create-graph` and `update-graph` commands.
- **3c (Knowledge Base Bootstrapping): Complete.** Distillation modules, `graph import`, OpenAlex snapshot at `data/snapshots/openalex-science-map.ttl`, biomedical starter profile at `docs/biomedical-starter-profile.md`. 116 tests passing (including 10 distill tests).
- **3d (Validation + Exemplar): Complete.** Exemplar project `~/d/3d-attention-bias/` run end-to-end through Phases 1-3. Graph: 2,761 triples, 4/4 validation checks pass, `validate.sh` passes. Evidence bundle archived at `docs/exemplar-evidence/`.

### Phase 4: Modeling + Operationalization (Stage B/C Optional Paths) (4a ✅, 4b in progress)

Support projects that need explicit models, datasets, or computational workflows.

**Phase 4a Progress Snapshot (2026-03-07):**
- **4a (Inquiry Workflow): Complete.** All 12 deliverables implemented. Inquiry command group (8 subcommands), 4 slash commands (`sketch-model`, `specify-model`, `plan-pipeline`, `review-pipeline`), inquiry template, `render_inquiry_doc()`, `validate.sh` section 14, knowledge-graph skill updated. Design doc at `docs/plans/2026-03-06-inquiry-workflow-design.md`. 106 tests passing across `test_graph_cli.py`, `test_inquiry.py`, `test_inquiry_e2e.py`, `test_prose.py`.

**Deliverables (4a — Inquiry Workflow):** ✅
- [x] Ontology extensions: `sci:Inquiry`, `sci:Variable`, `sci:Transformation`, `sci:Assumption`, `sci:Unknown`, `sci:ValidationCheck` types + 12 new predicates
- [x] Graph store inquiry methods: `add_inquiry`, `set_boundary_role`, `add_inquiry_edge`, `add_assumption`, `add_transformation`, `set_param_metadata`, `get_inquiry`, `list_inquiries`, `validate_inquiry`, `render_inquiry_doc`
- [x] CLI: `science-tool inquiry` command group (init, add-node, add-edge, add-assumption, add-transformation, list, show, validate)
- [x] `validate.sh` section 14: inquiry validation checks (boundary_reachability, unknown_resolution, provenance_completeness, target_exists, no_cycles, orphaned_interior)
- [x] Knowledge-graph skill updated with inquiry entity types, predicates, boundary roles, and parameter provenance
- [x] `/science:sketch-model` command
- [x] `/science:specify-model` command
- [x] `/science:plan-pipeline` command
- [x] `/science:review-pipeline` command
- [x] `templates/inquiry.md` template
- [x] Inquiry document rendering from graph (`render_inquiry_doc()`)
- [x] Design doc: `docs/plans/2026-03-06-inquiry-workflow-design.md`

**Deliverables (4b — Causal Modeling):**
- [x] `--type causal` on `inquiry init` + `sci:inquiryType` predicate
- [x] `sci:treatment` and `sci:outcome` predicates + `inquiry set-estimand` command
- [x] Causal-specific validation checks (acyclicity for inquiry members)
- [x] `science_tool/causal/export_pgmpy.py` — pgmpy scaffold script generation
- [x] `science_tool/causal/export_chirho.py` — ChiRho/Pyro scaffold script generation
- [x] `inquiry export-pgmpy` and `inquiry export-chirho` CLI commands
- [x] `pgmpy` and `chirho` as optional `[causal]` extras in pyproject.toml
- [x] `.claude-plugin/skills/models/causal-dag.md` skill
- [x] `/science:build-dag` command
- [x] `/science:critique-approach` command
- [x] Design doc: `docs/plans/2026-03-07-phase4b-causal-dag-design.md`
- [ ] Run on exemplar project and archive evidence
- [ ] Deferred inquiry-projection refactor documented: `docs/plans/2026-03-07-inquiry-projection-refactor.md`

**Deliverables (4c — Operationalization):**
- [ ] `find_datasets` capability + command surface
- [ ] Data validation tooling (Frictionless checks and dataset ↔ variable mapping checks)
- [ ] `skills/data/frictionless.md`
- [ ] `skills/pipelines/snakemake.md`, `skills/pipelines/marimo.md`
- [ ] Snakefile template and templates `pipeline-step.md`, `experiment.md`
- [ ] PyMC export (if needed)
- [ ] Stage C capability set implemented (`find_datasets`, workflow recommendations, reproducibility handoff)

### Phase 5: Autonomous Loops

Implement the Ralph-style loop infrastructure. May require extending beyond the plugin model.

**Deliverables:**
- [ ] Loop execution mechanism (agent, script, or command — TBD)
- [ ] `PROMPT_plan.md`
- [ ] `PROMPT_research.md`
- [ ] `PROMPT_explore.md`
- [ ] `/science:explore-open-questions` command
- [ ] Enhanced `validate.sh` with full backpressure suite
- [ ] Research skill sub-skills (literature-review, critique, etc.)

### Phase 6: Refinement

Iterate based on real usage. Observe failure modes and add guardrails.

**Deliverables:**
- [ ] Tuned prompts based on observed agent behavior
- [ ] Additional validation checks as failure modes emerge
- [ ] Documentation and README for open-source release

## Immediate Next Steps

**Phase 3: COMPLETE** (gate closed 2026-03-07). See `docs/exemplar-evidence/README.md` for evidence bundle.

**Phase 4b (Causal Modeling) — in progress:**
10. ~~Implement inquiry type system~~ ✅
11. ~~Implement causal exports (pgmpy, ChiRho)~~ ✅
12. ~~Create causal DAG skill + build-dag + critique-approach commands~~ ✅
13. Run causal DAG on exemplar project and archive evidence to close Phase 4 gate.

**Phase 4c (Operationalization):**
14. Implement `find_datasets` capability + command surface.
15. Create data validation tooling (Frictionless) + skill.
16. Create pipeline skills (Snakemake, Marimo) + templates.

## Phase Gates (Exit Criteria)

| Phase | Gate (must be true before phase is "done") |
|---|---|
| 2 | Stage A capabilities run end-to-end on a real project and produce prioritized, evidence-backed next steps |
| 3 | ✅ At least one project can agent-construct a knowledge graph from prose, import a distilled snapshot, run use-case queries with table/json output, detect changes via hybrid `graph diff`, pass `graph validate` + `validate.sh`, and provide an archived exemplar evidence bundle. **Closed 2026-03-07.** Evidence: `docs/exemplar-evidence/` |
| 4 | At least one optional path (causal modeling or software/data operationalization) runs end-to-end with reproducible outputs |
| 5 | Loop runs for at least 3 iterations without manual intervention and produces auditable, validated commits |
| 6 | Known high-frequency failure modes have explicit guardrails and regression tests |

---

## Program Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Plugin instructions drift from `science-tool` behavior | Commands and loops behave inconsistently | Keep graph/model logic in `science-tool`; plugin commands become orchestration only |
| Overfitting to a single linear workflow | Lower usefulness across project types | Keep capability contracts stage-labeled but path-agnostic; validate non-linear exemplar paths |
| Graph schema too abstract for biomedical workflows | Low usefulness for bio research | Ship a biomedical starter profile (Biolink + curated examples) in Phase 3 |
| Model export appears "correct" but is unidentified | False confidence in causal conclusions | Add identification checks + explicit warnings in Phase 4 validation gates |
| Distilled snapshots become stale | Outdated recommendations and hypotheses | Snapshot manifests include source date/version and refresh workflow |
| Scope spread across docs, data, graph, and models | Slow delivery | Enforce phase gates and keep one reference exemplar project through all phases |

---

## Design Decisions (Resolved)

1. **Skill discovery: hybrid automatic + prompted.** `CLAUDE.md` contains rules that automatically trigger skill reads for common task types. Commands also explicitly reference skills. Both mechanisms complement each other.

2. **Paper summarization: LLM knowledge first, with confidence calibration.** Claude summarizes from training data when confident, searches first when uncertain, and refuses to fabricate when unfamiliar. Key facts are always cross-checked via web search before being committed to documents.

3. **Knowledge graphs: first-class shared runtime.** `science-tool` is the canonical implementation for graph and causal operations; plugin commands and loops orchestrate it rather than reimplementing logic.

4. **Multi-project: single-project first, designed for extension.** Consistent metadata conventions (`science.yaml`) enable a future multi-project management layer.

5. **Collaboration model: defer.** Git branches per researcher as a reasonable starting point if needed.

6. **API key management: `.env` file.** Store credentials in `.env`, reference from `AGENTS.md`. Gitignored.

7. **Notebooks: support both, Marimo first.** Marimo is the primary notebook format (reactive, Python-native, better for reproducibility).

8. **Loop model selection: Opus primary.** Research tasks require strong reasoning. Opus primary agent, Sonnet subagents for mechanical tasks.

9. **Agent, not framework.** Science is an opinionated, batteries-included research assistant. Ships with sensible defaults, specific templates, and a clear workflow.

10. **Name: Science.** Named after the lab rat from Adventure Time.

11. **Distribution model: Claude Code plugin.** Simplifies installation and limits initial scope. Can expand to standalone repo or alternate deployment models in later phases.

12. **Shared implementations.** Commands and loop tasks should use the same underlying logic where possible, not separate codepaths.

13. **Version tracking via git.** Git history is sufficient for tracking plan evolution. No archive files — reduces noise when using tools like `rg`.

14. **Project manifest: `science.yaml`.** Fields: name, created, last_modified, summary, status, tags, data_sources.

15. **Multi-agent architecture: role profiles over shared state.** Science exposes multiple role-oriented behaviors without splitting into disconnected agent systems.

16. **Scope boundary: orchestration, not replacement.** Science integrates with existing modeling and workflow libraries rather than creating a new general-purpose framework.

---

## Lessons Learned (Phase 1)

1. **`set -e` is incompatible with error-counting scripts.** Bash's `set -e` exits on the first non-zero return code. Validation scripts that count errors and report at the end must NOT use `set -e`. Use `set -uo pipefail` instead.

2. **`pipefail` + `|| fallback` produces double output.** When `grep` returns no matches, `awk` already outputs "0" via its `END` block. With `pipefail`, the pipeline still fails, so `|| echo 0` runs too, producing "0\n0". Use `|| true` instead.

3. **Empty directories vanish in git.** Git doesn't track empty directories. Any directory that starts empty (e.g., `knowledge/`, `papers/pdfs/`) needs a `.gitkeep` file.

4. **Commands need "first use" handling.** The first time a command runs in a fresh project, files it assumes exist (like `references.bib`) may not. Every command should handle the "create if missing" case gracefully.

5. **LLM confidence matters more than LLM knowledge.** The "LLM knowledge first" principle is about efficiency, not blind trust. The confidence calibration section (high → write then verify, moderate → search first, low → search is primary) prevents the worst failure mode: confidently writing about a paper that doesn't exist.

6. **Interactive commands shouldn't feel like interrogations.** Rigid sequential questionnaires are exhausting. Framing questions as guidelines with "skip ahead if the user already provided enough detail" produces better interactions.

7. **Skill descriptions should be "pushy."** Claude tends to under-trigger skills. Descriptions should explicitly list trigger words and contexts, per Anthropic's own skill-creator documentation.

## Lessons Learned (Phase 3)

1. **`uv run --with` caches aggressively.** When developing `science-tool` locally, `uv run --with /path/to/science-tool` caches wheel builds. After adding new CLI commands or flags, the cached build may serve old code. Neither `--reinstall-package` nor `--refresh-package` reliably clear it — use `uv cache prune` or `uv cache clean science-tool`.

2. **Agents ignore constraints buried at the bottom.** Three test runs of `/science:create-graph` all failed to follow predicate rules and enrichment flags documented in the middle/end of the prompt. Moving imperative Rules to the top of the command file (MUST/MUST NOT) fixed compliance immediately.

3. **Agents default to preserving state even when told to create fresh.** When `create-graph` said "initialize", agents still tried to check for existing graph content and preserve it. Replacing ambiguous language with explicit `graph init` as Step 1 fixed this.

4. **Removing a dependency that appears unused may break downstream.** Commit `308e910` removed `pyyaml` because no direct import was visible in the main modules. But `prose.py` (added later in the same slice) imported `yaml` for frontmatter parsing. The CLI crashed at import time, making it look like commands/flags didn't exist rather than surfacing the actual missing-dependency error.
