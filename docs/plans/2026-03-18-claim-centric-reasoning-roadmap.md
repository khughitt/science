# Claim-Centric Reasoning Roadmap

> See also:
> - [`2026-03-16-claim-centric-uncertainty-design.md`](./2026-03-16-claim-centric-uncertainty-design.md)
> - [`2026-03-16-claim-centric-uncertainty-plan.md`](./2026-03-16-claim-centric-uncertainty-plan.md)
> - [`2026-03-17-dashboard-gap-closure-and-project-migrations-plan.md`](./2026-03-17-dashboard-gap-closure-and-project-migrations-plan.md)
> - [`2026-03-18-multi-scale-research-summaries-plan.md`](./2026-03-18-multi-scale-research-summaries-plan.md)

## Purpose

This roadmap extends the original claim-centric uncertainty design into a longer-term reasoning architecture.
The earlier design and implementation plan established the skeptical baseline:

- scientific assertions should be uncertain by default
- `claim` and `relation_claim` should be the primary units of belief
- evidence should update belief rather than validate or delete edges

This roadmap defines what comes next: how `science` should evolve from a claim-aware graph into a reusable reasoning system with stable summary contracts, multi-scale uncertainty views, and action-oriented prioritization.

## Status Snapshot (2026-03-18)

This roadmap is no longer purely forward-looking.
Several of its early phases now have concrete first-pass implementations on the `neighborhood-summaries` branch:

- Phase 1 is largely complete.
- Phase 2 is complete for the first stable contract pass.
- Phase 3 is complete for the first claim-neighborhood pass.
- Phase 5 is partially underway through store-backed claim and neighborhood dashboards.

What has landed so far:

- a canonical dashboard contract for `claim_summary`, `neighborhood_summary`, and `evidence_mix_summary`
- `graph dashboard-summary`
- `graph neighborhood-summary`
- a store-backed marimo dashboard that consumes those summary queries
- shared guidance that teaches dashboard-guided prioritization and migration posture

Important caveats:

- richer evidence-item-first authoring and structured study/result metadata are still future work
- higher-level summaries for questions, inquiries, and projects do not exist yet in the repository state captured by this roadmap snapshot
- prioritization is still mostly ranking-oriented rather than decision-oriented
- the remaining phases should now assume the profile-based organization model from `2026-03-18-project-organization-design.md`

## Target End State

The long-term goal is not just a better dashboard.
It is a reasoning architecture with four clean layers:

1. `raw_graph`
   - entities, claims, relation-claims, evidence items, studies, results, provenance
2. `derived_reasoning`
   - store-level summary objects computed from the graph
3. `summary_contract`
   - stable, versioned schemas for those summary objects
4. `presentation`
   - CLI, notebooks, reports, exports, and downstream tools

In that end state:

- the graph store owns epistemic computation
- the dashboard becomes a thin presentation layer
- users can move cleanly from evidence item -> claim -> neighborhood -> inquiry -> project
- prioritization outputs help users decide what to investigate next, not just what looks uncertain
- research-profile projects are the primary home for full claim-centric reasoning
- software-profile projects can opt into lighter overlays later, but they should not define the first-pass contract for higher-level summaries

## Guiding Principles

- Keep the skeptical baseline: absence of support is not support, and one line of evidence is rarely decisive.
- Put semantics in the store, not in notebook-local heuristics.
- Make every new layer opt-in and composable.
- Prefer explicit summary types over overloaded generic outputs.
- Separate evidential fragility from structural fragility.
- Preserve a path from lightweight authoring to richer structured evidence.

## Desired Architecture

### Layer 1: Raw Graph

The graph should remain the source of record for:

- `question`
- `hypothesis`
- `claim`
- `relation_claim`
- `evidence_item`
- `study`
- `result`
- `inquiry`
- provenance for support, dispute, methods, sources, and uncertainty annotations

This layer should stay flexible enough for partially migrated projects, but it should stop teaching users that asserted edges are established truth.

### Layer 2: Derived Reasoning

The store should compute reusable summaries rather than forcing each consumer to rediscover them.

These summaries should eventually include:

- `claim_summary`
- `neighborhood_summary`
- `question_summary`
- `inquiry_summary`
- `project_summary`
- later, `next_step_summary` or `decision_summary`

This is where belief state, evidential composition, contestation, fragility, and prioritization should be computed.

### Layer 3: Summary Contract

Summary objects should have explicit, documented shapes.

The purpose of the contract layer is to ensure that:

- CLI tables
- notebook dashboards
- migration tooling
- exports
- reports

all consume the same semantics rather than inventing their own.

### Layer 4: Presentation

Presentation layers should:

- render the store summaries
- filter and sort them
- explain them to the user
- integrate with the canonical project roots:
  - `doc/` for durable project writing and reports
  - `tasks/` for actionable follow-up work
  - `knowledge/` for notebooks and graph-facing exploration

Presentation layers should not:

- infer belief state by scanning raw triples
- reconstruct uncertainty logic from scratch
- silently collapse evidence types into a single bucket

## Phased Roadmap

### Phase 1: Claim-Centric Foundation

Status:
- largely complete

Delivered or substantially underway:

- claim-centric uncertainty model
- explicit `relation_claim` support
- claim-backed inquiry and causal edges
- support/dispute-aware uncertainty queries
- dashboard-oriented claim summaries
- command/template/guidance rewrites

Primary outcome:
- `science` no longer treats uncertain scientific edges as simple facts by default

Remaining cleanup:
- finish claim-centric reasoning migration for older projects that benefit from it
- keep organization/profile migration distinct from reasoning migration
- tighten any lingering scalar-confidence-first surfaces

### Phase 2: Stable Summary Contract

Status:
- complete for the first pass

Goal:
- make the current summary surfaces explicit and durable

Primary deliverables:

- canonical dashboard contract doc
- explicit `claim_summary` schema
- explicit `neighborhood_summary` schema
- stable CLI/JSON contract for summary commands

Why this phase matters:
- without a contract, the store, notebook, docs, and migration guides will drift

Exit criteria:
- claim summaries are documented and treated as stable
- neighborhood summaries have a first-pass schema even if their scoring evolves

Current state:
- satisfied for the current claim and neighborhood dashboard surfaces
- future revisions should evolve the contract conservatively rather than reopening the summary model ad hoc

### Phase 3: Neighborhood And Locality-Aware Reasoning

Status:
- complete for the first claim-centered pass

Goal:
- move from isolated claim risk to local graph risk

Primary deliverables:

- claim-neighborhood summary queries
- neighborhood-level risk and composition metrics
- separation of evidential fragility from structural fragility
- dashboard panels for high-risk local clusters

Recommended interpretation:
- claim neighborhoods come first
- entity, question, and inquiry locality views should be derived from claim neighborhoods rather than modeled independently at the start

Exit criteria:
- users can identify not just weak claims, but weak or contested regions of the project graph

Current state:
- satisfied for first-pass claim neighborhoods
- further work should refine locality semantics and diffusion rather than reintroducing notebook-local neighborhood logic

### Phase 4: Richer Evidence Modeling

Status:
- partially complete

Goal:
- improve the epistemic quality of belief updates by structuring evidence more precisely
- do so in a way that fits the new project profiles rather than assuming one universal project shape

Primary deliverables:

- stronger evidence-item-first authoring paths
- clearer support for:
  - `literature_evidence`
  - `empirical_data_evidence`
  - `simulation_evidence`
  - `benchmark_evidence`
  - `expert_judgment`
  - `negative_result`
- structured study/result metadata such as:
  - `sample_size`
  - `effect_size`
  - `uncertainty_interval`
  - `analysis_method`
  - `modality`
  - `replication_count`

Longer-term alignment:
- SEPIO for claims and evidence
- ISA for study structure
- STATO for statistical methods and results
- EFO for domain vocabulary

Exit criteria:
- claim confidence depends more on structured evidence than on residual scalar annotations

Current state:
- the evidence taxonomy is active and dashboard summaries distinguish key evidence types
- benchmark evidence now counts toward empirical-presence summaries
- structured study/result metadata and evidence-item-first authoring remain open

Profile implication:
- this phase is core for `research` projects
- for `software` projects, richer evidence modeling should remain opt-in and usually attach to targeted investigations, benchmarks, or evaluation claims rather than becoming the default project mode

### Phase 5: Multi-Scale Research Summaries

Status:
- partially underway

Goal:
- let users navigate uncertainty across the project at multiple levels
- make those higher-level summaries aware of project profile and canonical project organization

Primary deliverables:

- `question_summary`
- `inquiry_summary`
- `project_summary`
- roll-up logic from claims and neighborhoods into higher-level research threads

What this enables:

- project status views that are based on reasoning state rather than prose alone
- better comparison between alternative inquiries or competing hypotheses
- clearer understanding of where evidence is concentrated or missing
- clean integration with canonical project surfaces:
  - `knowledge/` for exploratory dashboards
  - `doc/reports/` and `doc/interpretations/` for durable summaries
  - `tasks/` for converting identified uncertainty into follow-up work

Exit criteria:
- users can move cleanly from a project view down to the exact weak claims and evidence gaps driving that summary

Current state:
- claim and neighborhood summaries exist
- the notebook consumes those store summaries directly
- `question_summary`, `inquiry_summary`, and `project_summary` are still missing in the repository state captured by this roadmap snapshot and remain the next real expansion of this phase

Profile implication:
- `question_summary` and `inquiry_summary` are primarily `research`-profile outputs
- `project_summary` should support both profiles, but with different expectations:
  - `research` projects should roll up claims, evidence, neighborhoods, questions, and inquiries
  - `software` projects should support lighter reasoning overlays, such as benchmark/evaluation claim clusters, without requiring full inquiry structure

### Phase 6: Action-Oriented Prioritization

Status:
- not implemented, but partially scaffolded by current guidance

Goal:
- convert uncertainty summaries into next-step guidance

Primary deliverables:

- prioritization outputs that rank:
  - contested neighborhoods
  - single-source regions
  - claims lacking empirical support
  - inquiries with high leverage for disambiguation
- explicit "what would change belief?" and "what should we test next?" surfaces
- eventually, decision-oriented outputs for planning work

This phase matters because:
- the most useful reasoning system does not stop at describing uncertainty
- it helps direct experimentation, reading, and curation effort

Exit criteria:
- users can use the graph not just to inspect beliefs, but to plan research effort

Current state:
- guidance now tells users to prioritize contested neighborhoods, single-source claims, and claims lacking empirical support
- the store does not yet produce explicit next-step or decision summaries

### Phase 7: Optional Formalization

Status:
- future work

Goal:
- support more formal reasoning only where it pays for itself

Possible deliverables:

- stronger causal-claim semantics
- explicit argument chains
- richer simulation-vs-empirical weighting
- optional probabilistic updates
- decision analysis or intervention-priority views

Non-goal:
- do not force full Bayesian or formal-logic machinery across the whole system prematurely

Exit criteria:
- optional formal layers exist for projects that need them, without burdening lightweight projects

## Migration Strategy

The roadmap should be adopted through rolling migration, not a flag day rewrite.

The project-organization migration is already complete.
What remains is selective reasoning-model migration on top of the new canonical profiles and root structure.

Recommended order:

1. finish migrating high-value `research` projects to the claim-centric reasoning model where they still lag
2. add richer evidence authoring where research projects actually benefit
3. add higher-level summaries once enough projects have meaningful claim graphs
4. define the lightweight reasoning overlay expected for `software` projects
5. connect higher-level summaries to canonical `doc/`, `tasks/`, and `knowledge/` workflows

This keeps the architecture honest: each new layer should be justified by real project use, not only by theoretical completeness.

## Near-Term Priorities

The next concrete steps should be:

1. implement `question_summary`, `inquiry_summary`, and profile-aware `project_summary`
2. connect those summaries to canonical `doc/`, `tasks/`, and `knowledge/` surfaces
3. deepen evidence-item-first authoring and structured study/result metadata for `research` projects
4. define the minimal reasoning overlay expected for `software` projects

These are the shortest-path steps that also move the system toward the long-term architecture rather than creating another temporary dashboard.

## Open Questions

- When should evidence-type metadata live on evidence items only, versus also being allowed on claims as a transitional summary aid?
- What is the right balance between neighborhood diffusion and explicit claim dependency links?
- What is the right minimal reasoning surface for `software` projects?
- How should `project_summary` differ between `research` and `software` profiles without fragmenting the contract model?
- When should question and inquiry summaries become first-class outputs rather than notebook-only aggregations?
- Which prioritization outputs are most useful in practice: uncertainty ranking, expected information gain, discriminating experiment suggestions, or something simpler?
- How much formal probabilistic machinery is worth introducing before richer empirical evidence structure is common across projects?

## Roadmap Decision

The long-term direction for `science` should be:

- a claim/evidence-centric reasoning engine in the store
- a stable contract layer for derived summaries
- a thin presentation layer
- and progressively more action-oriented prioritization built on top of those summaries

The dashboard is part of that vision, but not the center of it.
