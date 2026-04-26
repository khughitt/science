---
name: research-methodology
description: Core research methodology for scientific investigation. This skill should be used whenever conducting literature review, evaluating scientific sources, synthesizing findings across papers, assessing evidence quality, identifying gaps in knowledge, or working with hypotheses. Also use when the user mentions research, papers, citations, evidence, or scientific literature — even if they don't explicitly ask for "research methodology."
---

# Research Methodology

This skill defines how to approach scientific research tasks within a Science project. Read this before any research activity: literature review, paper summarization, hypothesis development, evidence evaluation, or topic exploration.

Science uses a skeptical, proposition-centric model:
- hypotheses are organizing conjectures
- propositions are the main units of belief
- observations and propositions support or dispute propositions via evidence edges
- sparse or single-source support should be treated as fragile
- contested neighborhoods and propositions lacking empirical support should be treated as prioritization signals, not just annotations

## Source Hierarchy

When researching a topic or summarizing a paper, use this priority order:

1. **Known context for orientation only.** Use model memory to frame search
   terms, expected concepts, and likely failure modes. Do not treat it as a
   source for durable claims.
2. **Primary and authoritative sources.** Verify claims against papers, official
   documentation, dataset records, or project-local notes before writing durable
   outputs.
3. **Web search for discovery and recency.** Use search to find recent work,
   source metadata, dataset versions, and missing primary sources.
4. **Full text when details matter.** Read the relevant methods, results,
   tables, and supplements when extracting parameters, numerical results,
   benchmark claims, cohort definitions, or evidence used in project decisions.
   If only the abstract is inspected, mark conclusions as abstract-level and
   avoid durable evidence updates.

### Confidence Calibration

Model memory is for orientation, not citation. Before writing from memory:

- **High confidence** (proceed, then cross-check): You recall specific details — author names, the core method, key findings. The paper is well-known or seminal.
- **Moderate confidence** (search first, then fill in from memory): You have a general sense of the paper's contribution but are fuzzy on specifics. Or the paper is recent / niche.
- **Low confidence** (search is the primary source): You're not sure this paper exists, or you're confusing it with something else. Say so. It's better to search than to confabulate.

The worst outcome is confidently writing about a paper that doesn't exist or attributing findings to the wrong paper. When in doubt, search first.

## Cross-Checking Key Facts

Always cross-check via web search before committing to a document:

- Author lists and affiliations
- Publication year and journal
- Specific numerical results that inform project direction (effect sizes, p-values, sample sizes)
- Method parameterizations that will be used in computational pipelines
- Claims about validation approaches or benchmarks

If you cannot verify a fact, flag it explicitly with `[UNVERIFIED]` in the document.

## Evaluating Sources

When assessing a source's value to the project:

- **Relevance:** Does it directly address a research question or hypothesis?
- **Recency:** Is it current enough? For methods, recent matters more. For foundational theory, older seminal work may be more important.
- **Quality:** Peer-reviewed > preprint > blog post > informal. But quality varies within each tier.
- **Reproducibility:** Did they share code/data? Can the methods be replicated?
- **Consensus:** Does this represent mainstream scientific consensus, or a minority/contrarian view? Note which.

## Synthesis, Not Just Summarization

When writing about multiple sources:

- Identify points of **agreement** across papers
- Identify points of **disagreement** and note the nature of the dispute
- Look for **gaps** — what has nobody studied?
- Look for **assumptions** — what does everyone take for granted that might not hold?
- Connect findings to the project's specific **hypotheses** and **research questions**

## Working with Hypotheses

Hypotheses in this project follow a structured format (see the framework `hypothesis.md` template, or a project override in `.ai/templates/`). When developing or evaluating hypotheses:

- Treat the hypothesis as a **bundle of propositions**, not a single binary truth value
- Every important proposition should be **falsifiable** — specify what evidence would lower confidence
- Distinguish **organizing conjecture** from **proposition-level updates**
- Prefer **support / dispute / unresolved** language over premature verdicts
- Note the **evidence type** when possible: literature, empirical-data, simulation, benchmark
- Track **residual uncertainty** explicitly, especially for single-source or indirect support

When the project uses layered-claim metadata:

- use `claim_layer` only when the authored proposition really needs that distinction
- treat `identification_strength` as an evidence-design label, not as confidence
- keep `measurement_model` separate from the concrete `observation`
- do not promote mechanistic prose into `mechanistic_narrative` unless the supporting lower-layer structure is explicit
- if rival models are genuinely in play, prefer a bounded `rival_model_packet` over free-form prose comparison
- treat `current_working_model` as optional; do not invent one just to satisfy a schema

### Allowed enum values

These fields are strict enums. **Do not invent values** — if no listed value fits, drop the field and explain in `measurement_model.rationale` or `known_failure_modes` instead.

- **`claim_layer`** — what kind of claim is this?
  - `empirical_regularity` — observed pattern in data (a correlation, a frequency, a trend)
  - `causal_effect` — claim about a causal effect of one variable on another
  - `mechanistic_narrative` — proposed mechanism story; requires linked lower-layer support
  - `structural_claim` — claim about graph topology, model structure, or definitional scaffolding
- **`identification_strength`** — how much causal leverage does this evidence carry *in the target system*?
  - `none` — no causal handle (descriptive only)
  - `structural` — derived from network/model structure or theory, not data
  - `observational` — observational study, association adjusted for confounders
  - `longitudinal` — within-subject change over time
  - `interventional` — perturbation in the target system
  - `analogical` — interventional in a *model* system, extrapolated to target by analogy
- **`proxy_directness`** — `direct` | `indirect` | `derived`
- **`supports_scope`** — `local_proposition` | `hypothesis_bundle` | `cross_hypothesis` | `project_wide`

Methodological scaffolding (analysis methods, definitional/framework material, historical context) usually does **not** belong as a `proposition`. Use `method:`, `topic:`, or `discussion:` entity types instead — those don't require enum classification.

## Evidence Classification

When updating the project model, prefer the canonical evidence categories:

- `literature_evidence`
- `empirical_data_evidence`
- `simulation_evidence`
- `benchmark_evidence`
- `expert_judgment`
- `negative_result`

Use `empirical_data_evidence` for project-run analyses over observed data.
Use `simulation_evidence` only when the result primarily comes from a model world.
Use `negative_result` when the finding meaningfully disputes a proposition or undermines prior support.

Do not collapse these into a generic "computational evidence" label.

## Annotation and Curation

When creating curated labels, extracted claims, taxonomy/facet assignments,
or LLM-assisted annotation tables, load
[`annotation-curation-qa`](./annotation-curation-qa.md). Treat curation as a
measurement process: define the schema, preserve source spans, record annotator
or model provenance, measure agreement when possible, and keep adjudication
separate from downstream interpretation.

## Recognizing Unmigrated Projects

Treat a project as only partially migrated when:

- hypothesis documents carry most of the real reasoning
- scalar `confidence` on hypotheses or questions is still doing most of the epistemic work
- propositions are not yet decomposed from broad hypotheses
- evidence is not yet attached as explicit support/dispute

In those cases:

- prefer creating or refining propositions over editing prose alone
- prefer proposition-backed graph updates over summary-only status changes
- call out that the project still needs migration work when that affects interpretation quality

## Using Dashboard Summaries

When `knowledge/graph.trig` exists, use the store summaries to guide effort:

- `science-tool graph dashboard-summary --format json`
- `science-tool graph neighborhood-summary --format json`

Use them to identify:

- contested propositions
- single-source propositions
- propositions lacking empirical support
- high-uncertainty neighborhoods

These are high-value places to direct reading, replication, experimental work, or model cleanup.

## Citation Discipline

- Every factual claim in a document needs a source
- Use BibTeX keys: `[@AuthorYear]` inline, full entries in `papers/references.bib`
- When citing from LLM knowledge, cross-check key facts via web search
- If a claim cannot be sourced, mark it as `[NEEDS CITATION]`
- Prefer primary sources over secondary summaries

## Project Awareness

Before writing any document, check:

1. `specs/research-question.md` — What is this project about?
2. `specs/hypotheses/` — What hypotheses are we tracking?
3. `doc/questions/` — What questions are we trying to answer?
4. `doc/background/papers/` — What have we already reviewed?
5. `doc/background/topics/` — What topics have we already covered?

This prevents duplication and ensures new work connects to the existing knowledge base.

For terminology and modeling details, see `docs/proposition-and-evidence-model.md`.

## Template Usage

All research documents must follow their corresponding framework template unless the project defines a specific override in `.ai/templates/`. Read the relevant template before writing. The template sections are not optional — fill every section, even if briefly.
