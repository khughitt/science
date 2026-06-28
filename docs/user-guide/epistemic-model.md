# Epistemic Model

Science treats uncertainty as part of the project record. The goal is not to
turn every claim green; the goal is to make current support, dispute,
fragility, and missing evidence visible.

## Core Types

| Type | Purpose |
|---|---|
| `question` | Frames what the project wants to learn. |
| `hypothesis` | Organizes one or more propositions into a working conjecture. |
| `proposition` | The primary truth-apt, belief-bearing assertion. |
| `observation` | A concrete empirical finding or recorded datum. |
| `evidence-line` | Durable support or dispute linked to a proposition or other epistemic target. |
| `inquiry` | A scoped work program connecting questions, variables, assumptions, propositions, datasets, transformations, and decisions. |
| `mechanism` | Named explanatory structure linking multiple typed entities and propositions. |
| `patch-definition` | Authored profile for a local epistemic neighborhood. |

## Inquiries

An `inquiry` is a scoped work program: it names what the project is trying to
understand, which variables or data sources are treated as givens, which outputs
or decisions it is trying to produce, and which assumptions or transformations
connect those parts.

Science has two inquiry-related source surfaces:

| Surface | Role |
|---|---|
| `entities/inquiries/<slug>.md` | A normal inquiry entity for prose-first records, legacy projects, and human-readable scoped work notes. |
| `entities/patches/<slug>.md` with `type: patch-definition` and `patch_type: inquiry` | The source-first graph inquiry profile compiled by `science graph build`. |

The queryable inquiry graph is derived state. Do not hand-edit
`knowledge/graph.trig` to change an inquiry. Edit the source file, then run
`science graph build`.

### Inquiry Patch Profiles

The graph-backed inquiry path uses `patch-definition` because an inquiry is also
a local epistemic neighborhood: it has a focal hypothesis or question and a
derived member set around that focal target. `science inquiry init` scaffolds
this source file:

```bash
science inquiry init <slug> \
  --label "<title>" \
  --target hypothesis:<id> \
  --profile investigation
```

For causal inquiries, include the estimand when the file is created:

```bash
science inquiry init <slug> \
  --label "<title>" \
  --target hypothesis:<id> \
  --profile causal \
  --treatment concept:<treatment> \
  --outcome concept:<outcome>
```

The authored `inquiry:` block carries:

| Field | Purpose |
|---|---|
| `profile` | `investigation` or `causal`. Causal profiles require `treatment` and `outcome`. |
| `status` | `sketch`, `specified`, `planned`, `in-progress`, or `complete`. |
| `boundary_roles` | Existing entity refs marked as `BoundaryIn` or `BoundaryOut`. |
| `flow_edges` | Directed inquiry edges using `feedsInto`, `produces`, or `causes`, optionally backed by `proposition:` refs in `claim_refs`. |
| `assumptions` | Inquiry-local assumption nodes minted during graph build, with optional provenance. |
| `transformations` | Inquiry-local transformation nodes, tools, parameters, and validation refs. |
| `unknowns` | Existing refs marked as `sci:Unknown` until resolved or justified. |

The graph build compiles inquiry patch profiles into dedicated `sci:Inquiry`
named graphs and then derives patch-membership records. Boundary nodes and edge
endpoints must resolve to existing entities; assumption and transformation nodes
are minted by the compiler.

### Inquiry CLI

The current `science inquiry` CLI is source-first:

- `science inquiry init` scaffolds the source file and does not write the graph.
- `science inquiry import` is a bridge from an existing graph inquiry into a
  patch-definition source file.
- `science inquiry list`, `science inquiry show`, `science inquiry validate`,
  `science inquiry export-pgmpy`, and `science inquiry export-chirho` read the
  materialized graph.
- The old graph-mutating commands (`add-node`, `add-edge`, `add-assumption`,
  `add-transformation`, and `set-estimand`) are retired. Edit the source file
  and rebuild instead.

## Proposition-Centered Belief

Propositions are the main units whose belief can be summarized. A proposition
may be simple prose or carry subject/predicate/object structure when that makes
the scientific relation clearer.

Evidence does not prove propositions outright. Evidence lines support or dispute
propositions, and the belief machinery derives the current state from eligible
evidence.

## Belief Vocabulary

| Term | Meaning |
|---|---|
| `belief_state` | Derived interpretation of the proposition given the current evidence. |
| `speculative` | Little or no eligible support. |
| `fragile` | Some support, but narrow, weak, indirect, or dependent on too little evidence. |
| `supported` | Support clears the configured floor. |
| `well_supported` | Stronger support, usually requiring multiple independent and relevant lines. |
| `contestation` | Credible support and credible dispute coexist. |
| `fragility` | The current belief could change easily because support is narrow or dependent. |
| `uncertainty` | Remaining lack of warranted confidence. |

Use these as readings of the record, not as manually assigned labels to chase.

## Authored Versus Derived

Authored fields record what a person, source, result, or project file says:
proposition text, scope, evidence stance, source, method, caveats, and quality
inputs.

Derived fields summarize what follows from the authored record: belief state,
support and dispute summaries, contestation, fragility, and freshness.

## Hypotheses And Bundle Belief

A hypothesis is an organizing conjecture. It may contain several propositions
whose evidence differs. A hypothesis should not be treated as supported merely
because it was written down or because one member proposition looks promising.

For mechanisms and proposition bundles, Science uses weakest-link rollups where
appropriate: the bundle is only as strong as its least-supported required
member. Refutation propagates as a cap, not as a separate positive belief state.

## Optional Layered-Claim Metadata

Use optional metadata when it clarifies the scientific claim:

- `claim_layer`: `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`.
- `identification_strength`: what kind of identification leverage exists, such as structural, observational, longitudinal, interventional, analogical, or none.
- `measurement_model`: how an observed proxy relates to a latent construct.
- `supports_scope`: a review-radius hint, not a graph override.
- `rival_model_packet`: a bounded comparison among competing models.

Do not fill these fields performatively. Add them when they reduce ambiguity.

## Evidence Integrity

Belief state, validation, and health checks are instruments for reading the
evidence. They are not targets to game.

Never relabel weak or indirect evidence as strong or direct just to clear a
warning. Never split a shared cohort, instrument, or source into fake
independence groups. Never overstate stance, strength, relevance, or
identification strength to improve a dashboard.

An honest yellow warning is often the correct state of the science.
