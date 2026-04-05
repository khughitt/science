# Project Model Design

> Supersedes aspects of: [`2026-03-16-claim-centric-uncertainty-design.md`](./2026-03-16-claim-centric-uncertainty-design.md) (claim/evidence entity model), [`2026-03-01-knowledge-graph-design.md`](./2026-03-01-knowledge-graph-design.md) (entity type definitions).
> Companion spec: [`2026-04-05-paper-model-design.md`](./2026-04-05-paper-model-design.md) defines the compositional paper hierarchy built on this foundation.
> Motivation: Upstream requirements from MM30 reorganization (`~/d/r/mm30/doc/reorg/upstream-science-requirements.md`) identified critical gaps in task-artifact linking, findings representation, and project organization.

## Summary

The Project Model is a clean-slate redesign of the core entity types and relations that every
science project uses. It replaces the current ad-hoc collection of entity types with a principled
three-layer architecture:

1. **Atomic layer** — three primitive entity types (proposition, question, observation) from which
   all epistemic content composes.
2. **Compositional layer** — entities that compose atoms into increasingly higher-level structures
   (finding, interpretation, story, paper).
3. **Operational layer** — entities that represent the "doing" side of research (task, workflow,
   workflow_run, workflow_step, data_package, dataset, method).

The Project Model is the structural backbone of every science project. The knowledge graph builds
on this core, extending it with domain-specific ontologies and project-local content via the
existing profile system.

## Goals

- Establish a small, closed set of core entity types with clear compositional semantics.
- Make every scientific assertion trace from high-level narrative down to specific data and code.
- Represent evidence as a relation (edge) rather than an entity (node).
- Enable bottom-up assembly of research communication from atomic findings.
- Support top-down gap analysis to identify missing evidence and incomplete narratives.
- Provide a clean migration path from the current entity model.

## Non-Goals

- Replace or redesign domain-specific ontology profiles (biology, physics, etc.).
- Define paper-level composition rules (see Paper Model spec).
- Build a Bayesian inference engine or formal logic system.
- Generate publication-ready prose.
- Redesign the graph materialization pipeline (sources → RDF → TriG).

## Design

### Layer 1: Atomic Entities

Three primitive types from which all epistemic content composes.

#### `proposition`

The single truth-apt unit. Replaces both `claim` and `relation_claim` from the current model.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier (e.g., `prop:brca1-regulates-dna-repair`) |
| `text` | string | yes | Natural language statement |
| `subject` | ref | no | Structured S-P-O form: subject entity |
| `predicate` | string | no | Structured S-P-O form: predicate |
| `object` | ref | no | Structured S-P-O form: object entity |
| `provenance` | ref | yes | Source reference (paper, analysis, expert judgment) |
| `status` | enum | derived | `hypothesized \| supported \| contested \| established \| refuted` |

- Status is *derived* from the evidence graph (support/dispute edges), never authored directly.
- A proposition can originate from literature, your own analysis, or expert judgment —
  provenance distinguishes these.
- When S-P-O fields are populated, the proposition participates in structured graph queries
  (replacing the current `relation_claim` use case).

#### `question`

The fundamental interrogative unit framing inquiry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `text` | string | yes | Natural language question |
| `status` | enum | authored | `open \| partially_resolved \| resolved` |
| `scope` | string | no | What would count as an answer |

- Questions connect to propositions via `addresses` edges.
- Semantically unchanged from the current model; reclassified as one of three atoms.

#### `observation`

A concrete empirical fact anchored to specific data. New entity type.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `description` | string | yes | Natural language description |
| `metric` | string | no | What was measured |
| `value` | string | no | Measured value (string to accommodate varied formats) |
| `uncertainty` | string | no | Measurement uncertainty or confidence interval |
| `conditions` | string | no | Context, constraints, experimental conditions |
| `data_source` | ref | yes | Link to `data_package` or `dataset` |

- Observations are NOT interpretive. "r = 0.73, p < 0.001" is an observation;
  "X and Y are strongly correlated" is a proposition.
- Observations bridge the computational layer (data_packages produced by workflows)
  to the epistemic layer (propositions).

#### Evidence as Relation

Evidence is a relation (annotated edge), not an entity. This replaces the current `evidence`
entity type.

**`supports`** and **`disputes`**: directed edges from `observation|proposition` to `proposition`.

| Annotation | Type | Description |
|------------|------|-------------|
| `strength` | enum | `strong \| moderate \| weak` |
| `caveats` | string | Limitations or qualifications |
| `method` | string | How the support/dispute was established |

In RDF: reified edges in the provenance layer using `cito:supports`/`cito:disputes` predicates
with annotation properties on the reified statement.

Proposition status (`hypothesized`, `supported`, `contested`, `established`, `refuted`) is
derived from the pattern of support/dispute edges, consistent with the belief-update rules in
the claim-and-evidence model documentation.

#### `hypothesis`

A named bundle of related propositions under investigation. Unchanged semantically from
the current model — hypotheses remain a higher-level conjecture that groups propositions,
not a separate competing epistemic unit.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `text` | string | yes | Natural language description of the conjecture |
| `propositions` | list[ref] | no | Propositions bundled under this hypothesis |
| `status` | enum | authored | `active \| supported \| refuted \| superseded` |

- Hypothesis status is authored (a judgment call), unlike proposition status which is derived.
- Hypotheses connect to the compositional layer via `story.about` — a story can be organized
  around a hypothesis.

### Layer 2: Compositional Entities

Entities that compose atoms into increasingly higher-level structures. These form the bridge
between raw analysis and communicable research.

#### `finding`

The fundamental unit of "we learned something from an analysis." A finding wraps propositions
and observations together with traceability to the code/data that produced them.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `summary` | string | yes | Brief natural language summary |
| `confidence` | enum | yes | Authored, subjective: `high \| moderate \| low \| speculative` |
| `propositions` | list[ref] | yes | Proposition(s) this finding asserts |
| `observations` | list[ref] | yes | Observation(s) grounding this finding |
| `source` | ref | yes | `data_package` or `workflow_run` that produced the observations |

Relations:
- `contains(finding → proposition)` — the finding asserts these propositions
- `contains(finding → observation)` — the finding is grounded in these observations
- `grounded_by(finding → data_package|workflow_run)` — traceability to code/data

#### `interpretation`

One analysis session's narrative and its findings.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `summary` | string | yes | Brief summary of the interpretation session |
| `context` | string | no | What prompted this analysis |
| `findings` | list[ref] | yes | Findings produced in this session |
| `prose` | string | no | Narrative text connecting findings |
| `prior` | ref | no | Previous interpretation (provenance chain) |

Relations:
- `contains(interpretation → finding)` — the interpretation bundles these findings

This is what `interpret-results` produces. Currently interpretation documents are prose;
in the new model they become structured entities that *contain* findings.

#### `story`

A coherent narrative arc synthesizing multiple interpretations around a question or hypothesis.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `title` | string | yes | Descriptive title |
| `summary` | string | yes | Brief summary of the narrative arc |
| `about` | ref | yes | The `question` or `hypothesis` this story is organized around |
| `interpretations` | list[ref] | yes | Interpretations drawn upon (ordered) |
| `prose` | string | no | Synthesis narrative — the "so what" connecting interpretations |
| `status` | enum | authored | `draft \| developing \| mature` |

Relations:
- `synthesizes(story → interpretation)` — story draws from these interpretations
- `organized_by(story → question|hypothesis)` — what the story is about

#### `paper`

An ordered composition of stories, structured for communication.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable identifier |
| `title` | string | yes | Paper title |
| `abstract` | string | no | Paper abstract |
| `stories` | list[ref] | yes | Stories composing this paper (ordered) |
| `sections` | map | no | Section label → list of story refs + prose |
| `bibliography` | list[ref] | no | Article references |
| `status` | enum | authored | `outline \| draft \| revision \| final` |

Relations:
- `comprises(paper → story)` — paper is composed of these stories

A paper is not necessarily a journal publication — it could be a report, a thesis chapter,
a whitepaper. A project can contain 0+ papers.

Sections are lightweight: named, ordered slots containing story refs and/or prose. They are
not a separate entity type.

### Layer 3: Operational Entities

Entities representing the "doing" side of research. Mostly unchanged from the current model;
key changes are in how they connect to the atomic and compositional layers.

#### `task`

Largely unchanged. Gains linkage to artifacts and findings.

| Field (new) | Type | Description |
|-------------|------|-------------|
| `artifacts` | list[ref] | `data_package`s, scripts, outputs produced by this task |
| `findings` | list[ref] | Findings that resulted from this task |

This closes the traceability loop: task → artifacts → observations → findings → propositions.

#### `workflow`, `workflow_run`, `workflow_step`

Structurally unchanged. Well-designed in the current model.

New relation: `workflow_run --grounds--> observation` as a shortcut for "this run produced
data that an observation cites."

#### `data_package`

Structurally unchanged (Frictionless standard). Becomes the primary anchor for observations —
an observation's `data_source` field points here.

Gains explicit visibility in the compositional chain:
`data_package ←grounded_by← finding`.

#### `artifact` → merged into `data_package`

`artifact` is retired as a separate entity type. A `data_package` with `type: result` is a
result artifact. A `data_package` with `type: interim` is intermediate pipeline output.
This eliminates overlap between the two current entity types.

#### `dataset`

Unchanged. Represents external data sources (not outputs of your own workflows).
Observations reference datasets via their `data_source` field — no additional relation needed.
The bridge relation `dataset --measures--> concept` (in the extension mechanism) captures
what domain entities a dataset measures.

#### `method`

Unchanged. Represents analytical approaches.
Connected via `workflow --realizes--> method` (existing relation).

### Operational → Compositional Connections

```
task ──artifacts──► data_package ◄──grounded_by── finding
  │                      ▲                           │
  │                      │                           │
  └──findings──►  workflow_run ──produces──┘    contains
                                                     │
                                                     ▼
                                              proposition
```

### Extension Mechanism

The core Project Model is closed and small. Domain-specific content plugs in via the existing
profile system, with clarified boundaries.

#### Three extension layers

| Layer | What it adds | Who defines it | Example |
|-------|-------------|---------------|---------|
| Core profile | Atomic + compositional + operational entities and relations | Science framework | proposition, finding, story, supports, contains |
| Domain profile | Concept subtypes + domain predicates | Curated (biology, physics, etc.) | gene, pathway, biolink:related_to |
| Project-local | Project-specific concepts + custom relations | Individual project | custom cell types, project-specific metrics |

#### Key principle

Domain content is always *about* — it provides the subject matter that propositions,
observations, and questions refer to. It never introduces new compositional or operational
structure. You don't need a biology profile to understand how findings compose into stories;
you need it to understand what the findings are *about*.

#### Bridge relations

- `proposition --about--> concept` — this proposition concerns this domain entity
- `dataset --measures--> concept` — this dataset contains measurements of this domain entity
- `variable --represents--> concept` — this causal variable represents this domain entity

### Design Questions (Deferred)

The following current entity types don't map cleanly to the three-layer model. The spec
presents options; resolution is deferred to implementation.

#### `discussion`, `comparison`, `bias_audit`, `pre_registration`

**Option 1: Activities, not entities.** These are processes that produce findings/propositions,
not standalone graph nodes. A bias audit produces findings; a comparison produces propositions.
They get tracked as tasks with specific tags.

**Option 2: Metadata/annotations.** They become annotations on the entities they affect. A
pre-registration is metadata on a set of propositions saying "these were stated before
analysis."

**Option 3: Keep as entities.** They remain in the graph but are reclassified as "process
entities" in a separate category from the three core layers.

Trade-offs:
- Option 1 is simplest and keeps the core model small, but loses queryability (you can't
  easily find "all bias audits for hypothesis H").
- Option 2 preserves traceability without adding entity types, but annotation semantics
  can be awkward in RDF.
- Option 3 preserves current behavior but adds a fourth quasi-layer that may not carry
  its weight.

### Naming Resolution

`paper` in the current model refers to external literature references. In the new model it
also means "your own paper being composed."

**Resolution:** `paper` = your own composed work (compositional entity). `article` = external
literature reference (already exists as an entity type). Clean split with no ambiguity.

## Relation Summary

All relations in the Project Model:

| Relation | Source | Target | Layer | Semantics |
|----------|--------|--------|-------|-----------|
| `supports` | observation, proposition | proposition | provenance | Evidence for |
| `disputes` | observation, proposition | proposition | provenance | Evidence against |
| `addresses` | question | proposition | knowledge | Question frames proposition |
| `contains` | finding | proposition, observation | knowledge | Finding bundles atoms |
| `grounded_by` | finding | data_package, workflow_run | knowledge | Traceability to code/data |
| `contains` | interpretation | finding | knowledge | Interpretation bundles findings |
| `synthesizes` | story | interpretation | knowledge | Story draws from interpretations |
| `organized_by` | story | question, hypothesis | knowledge | What the story is about |
| `comprises` | paper | story | knowledge | Paper composed of stories |
| `produces` | workflow_run | data_package | provenance | Run produced this output |
| `grounds` | workflow_run | observation | provenance | Run's data cited by observation |
| `realizes` | workflow | method | knowledge | Workflow implements method |
| `contains` | workflow | workflow_step | knowledge | Workflow has steps |
| `executes` | workflow_run | workflow | provenance | Run executed this workflow |
| `feeds_into` | workflow_step | workflow_step | knowledge | Data flow between steps |
| `supersedes` | workflow_run | workflow_run | provenance | Newer run replaces older |
| `about` | proposition | concept | bridge | Proposition concerns domain entity |
| `measures` | dataset | concept | bridge | Dataset measures domain entity |
| `represents` | variable | concept | bridge | Variable represents domain entity |
| `tests` | task, workflow_run | hypothesis, question | knowledge | Tests this hypothesis/question |
| `blocked_by` | task | task | knowledge | Task dependency |

## Migration

### Entity mapping

| Current | New | Migration action |
|---------|-----|-----------------|
| `claim` | `proposition` | Rename type; keep all fields |
| `relation_claim` | `proposition` (with S-P-O) | Rename; move S-P-O into optional structured fields |
| `evidence` (node) | Decompose | Empirical content → `observation`; stance → `supports`/`disputes` edge with annotations |
| `interpretation` | `interpretation` | Keep; backfill `findings` refs where possible (may need manual review) |
| `hypothesis` | `hypothesis` | Unchanged; its bundled claims become propositions |
| `question` | `question` | Unchanged |
| `paper` (literature) | `article` | Rename to avoid collision with compositional `paper` |
| `artifact` | `data_package` (with type/role) | Merge; add `type: result \| interim` field |
| `discussion` | Deferred | Preserve as-is during migration |
| `comparison` | Deferred | Preserve as-is during migration |
| `bias_audit` | Deferred | Preserve as-is during migration |
| `pre_registration` | Deferred | Preserve as-is during migration |
| `model` | Unchanged | Research models (causal, mechanistic); connects variables to propositions |
| `inquiry` | Unchanged | Named subgraph container for investigation; continues to organize questions → hypotheses → propositions |
| `experiment` | Unchanged | Bounded investigation design |
| All others | Unchanged | task, workflow, workflow_run, workflow_step, data_package, dataset, method, variable, assumption, transformation, topic, concept |

### Migration approach

1. **Spec first, migrate second.** Specs are written and approved before any code changes.
2. **Automated migration script.** Reads existing graph sources (YAML/markdown in
   `knowledge/sources/`), transforms to new entity types, writes new source files. The graph
   is materialized from sources, so we migrate the *sources*, not the graph itself.
3. **Validation pass.** Re-materialize the graph from migrated sources. Diff against the old
   graph to verify no information loss (modulo expected structural changes).
4. **Manual review for decomposition.** The `evidence` → `observation` + edge decomposition
   may need human judgment when an evidence node mixes empirical content with interpretive
   claims.
5. **Profile update.** The core profile definition (`science-model`) is updated to the new
   entity/relation types. Old types are removed, not deprecated — no compatibility layer.
