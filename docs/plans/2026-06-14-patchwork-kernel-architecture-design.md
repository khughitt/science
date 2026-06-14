# Patchwork kernel architecture — target-state overview

**Date:** 2026-06-14
**Status:** Design / architecture overview
**Scope:** Ideal target state plus subsystem decomposition. This is not an
implementation plan.

## Purpose

Recent Science design work has converged on the right conceptual direction:
knowledge is a federated patchwork of provenance-typed, uncertainty-bearing
epistemic neighborhoods. The target model is cleaner than the current
implementation, which still carries older entity, schema, graph, evidence, and
view systems in parallel.

This document defines the ideal architecture without compromising it around
today's code. It should be read as a north star and decomposition map for
follow-on specs. Migration implications are explicit, but detailed migration
mechanics belong in a later migration strategy.

## Design stance

The target system is a single semantic graph with strict ownership boundaries:

- nodes are entities whose kinds come from one descriptor system;
- truth-apt assertions are propositions;
- relational propositions are also their rendered edge nodes;
- evidence-lines are the only units that ground belief;
- belief is derived once by a versioned policy and exposed through projections;
- patches are durable named graphs, not merely files or renderer state;
- scopes own identities across local projects, commons, peers, remote sources,
  and external authorities;
- views are generated projections and never own epistemic truth.

The clean architecture is therefore not a different system. It is the existing
Science direction with the keystone primitives made explicit and the parallel
copies removed.

## Kernel primitives

The kernel has a small set of primitives. Each primitive has exactly one job.

| Primitive | Purpose |
|---|---|
| `KindDescriptor` | The single source of truth for what a kind is: class, schema, identity policy, home, lifecycle vocabulary, relation behavior, and projection behavior. |
| `Scope` | An identity-owning address space: local project, commons, peer project, GitHub repository, Zenodo deposit, external authority, or other source. Local versus remote is a scope property, not a different model. |
| `Agent` | A human, AI model, tool, workflow, organization, or service that authors, derives, reviews, imports, or validates knowledge. |
| `SourceSnapshot` | A pinned observation of a source: local file, git revision, DOI/version, Zenodo record version, dataset manifest, API response, or generated artifact. |
| `Entity` | Any addressable thing in a scope. An entity has one owner declaration, or it participates as a borrower or external reference. Its behavior comes from its `KindDescriptor`. |
| `Proposition` | The only truth-apt, belief-bearing assertion. A relational proposition is also its reified edge-node for graph rendering. |
| `EvidenceLine` | The only grounding unit for belief. It supports, disputes, qualifies, or contextualizes propositions, with provenance and dependency metadata. |
| `BeliefResult` | A derived result of applying a versioned belief policy to evidence-lines. Ordinal magnitude, log-odds scalar, subjective opinion, and edge status are views of this result. |
| `Patch` | A durable named graph: an epistemic neighborhood around a question, hypothesis, model fragment, dataset evidence flow, or synthesis. Patch membership is compiled graph state, never only workbench state. |
| `View` | Any generated projection: DAG diagram, dashboard, edge-status summary, composite graph, report, workbench, export, or inventory. Views are disposable and do not own truth. |

The load-bearing invariant is:

> Only `Proposition` carries belief. Only `EvidenceLine` grounds belief. Only
> `Patch` groups epistemic neighborhoods. Only `Scope` owns identities. Only
> `KindDescriptor` defines kind behavior.

Two clarifications prevent later subsystem specs from splitting the model:

- `Agent` and `Scope` are distinct even when they refer to the same real-world
  actor. A person can be an `Agent` with an ORCID and can also control a personal
  `Scope`; authorship/review identity and namespace ownership are linked by
  relations, not collapsed into one object.
- `SourceSnapshot` is provenance/compiler state, not a truth-apt entity by
  default. It may be addressable in the provenance graph, but it does not carry
  belief.

## Layered architecture

The kernel is served by five layers. Each layer owns one concern and exposes a
narrow contract to the next layer.

| Layer | Owns | Does not own |
|---|---|---|
| **Model Registry** | `KindDescriptor`, schemas, relation descriptors, field-provenance rules, lifecycle vocabularies | Disk layout, graph output, belief math |
| **Source Compiler** | Loading local and remote sources into typed declarations: entities, identity rows, source snapshots, relation rows, patch memberships | Scientific semantics beyond declared contracts |
| **Epistemic Semantics** | Propositions, evidence-lines, dataset usage, independence, `bears_on` revisit dependencies, belief policies, derived belief results | Authoring layouts, DAG status files, remote sync |
| **Patch & Federation** | Patch named graphs, patch membership, patch maturity, patch-level diagnostics, cross-scope addressing, composite views | Raw source parsing, kind definitions |
| **Views & Interfaces** | Workbenches, DAG renderers, dashboards, inventories, CLI mutation surfaces, reports, exports | Durable truth or belief state |

The data flow is one-way:

```text
sources
  -> Source Compiler
  -> compiled identity/source/provenance model
  -> epistemic graph
  -> derived belief + patch diagnostics
  -> views/projections
```

Mutation follows the same shape. A CLI command or workbench edit should modify a
source declaration or create a source transaction. The compiler then regenerates
the graph. Direct graph mutation is reserved for scratch or generated outputs
that are not source-of-truth.

Two rules follow:

1. **No parallel stores.** If something affects belief or identity, it compiles
   from source declarations through the same path.
2. **No semantic logic in views.** Renderers can summarize derived data, but they
   cannot invent source-of-truth state such as authored edge status.

Each layer validates its own contract. Cross-layer validation checks only the
interface between layers: source records compile, compiled identities resolve,
epistemic semantics derive, patch memberships materialize, and views regenerate
without drift.

## Load-bearing decisions

These decisions are part of the overview, not deferred details.

### Patch membership is a relation, not a partition

A `Patch` is a named graph with its own IRI, metadata, diagnostics, and view
membership, but proposition triples do not have to live inside exactly one patch
graph. Patch membership is represented by compiled membership relations such as
`sci:inPatch` / `sci:hasMember` between a patch and proposition/evidence nodes.

This permits overlapping patches: the same proposition can participate in an
apoptosis patch, a drug-resistance patch, and a project-level synthesis patch
without duplicating proposition triples or inventing a primary patch. The named
graph remains useful as the addressable patch object and as a container for
patch-specific metadata, diagnostics, layout, and generated view triples. It is
not a hard partition of all member triples.

### BeliefResult is structured

`BeliefResult` is not a single scalar. It is a structured derived object that
contains:

- the reduced evidence set used by the policy;
- support/dispute mass or scalar summaries, when computed;
- ordinal magnitude;
- contestation;
- decisive-refutation / cap state;
- diagnostics and excluded evidence records;
- the policy id/version that produced the result.

Magnitude, log-odds, subjective opinion, and derived edge status are projections
from this whole object. Flags such as `contested` and `capped_by_refutation` must
not be forced into a numeric scalar because they are not reconstructable from a
number alone.

### Agent and trust are explicit policy inputs, never hidden weights

Agent identity, method, review state, and source trust are always provenance.
Whether they affect belief is controlled only by an explicit, versioned
`BeliefPolicy`. The core model must not hardcode "AI means down-weight" or
"human means trusted" into the data model.

A conservative default policy may treat agent identity as audit-only while using
review state to gate belief eligibility. A stricter project policy may choose to
down-weight unreviewed AI-generated evidence, reference-curated evidence, or
low-trust sources. In all cases, the policy and rationale are recorded on the
`BeliefResult`.

### Ladder level belongs to Patch as a derived diagnostic

The L0-L4 ladder is a patch-level maturity diagnostic. It is computed from the
richest validated structures inside the patch: typed relational propositions,
belief/provenance coverage, associative or causal role metadata, partial causal
structures, and full PGM/SCM exports.

Propositions still carry local axes such as claim layer, predicate, polarity,
identification design, measurement model, and evidence role. Those axes feed the
patch-level computation; they are not a second independent ladder.

### Source freshness and review freshness are separate

`SourceSnapshot` introduces source freshness: a pinned source may have moved, a
remote version may have changed, or an upstream file hash may no longer match.
Epistemic review freshness is different: a proposition, evidence-line, or patch
may need human or agent review in light of changed evidence.

A source freshness change does not mutate belief by itself. It creates a new or
stale `SourceSnapshot` state and propagates through `bears_on` / dependency
rules to mark dependent epistemic objects as needing review or recompilation.
Belief changes only after source declarations are updated and the epistemic
graph is recompiled under a recorded policy.

## Subsystem specs

The architecture should be decomposed into focused follow-on specs. Each spec
owns one region and must not recreate a parallel mechanism.

| Spec | Purpose | Key decisions |
|---|---|---|
| **1. Kernel Architecture Overview** | This document: primitives, layers, invariants, decomposition, and migration implications. | Names and boundaries. |
| **2. Kind Descriptor & Model Registry** | Collapse entity-kind lists, core profiles, registry classes, path policies, statuses, JSON-schema mixins, and migrated-kind lists into one descriptor system. | Is core just a built-in manifest? Which schema system is canonical? How are descriptors generated and tested? |
| **3. Source Compiler & Identity Substrate** | Define source records, adapter policies, identity rows, error policy, reference-field policy, source snapshots, and compiled outputs. | Replace adapter-name branching; split compiler phases; unify audit and materialization. |
| **4. Patch Contract** | Make `Patch` real: named graph identity, relational membership, metadata, workbench contract, diagnostics, patch-level uncertainty, L0-L4 maturity. | Membership predicates, graph emission, overlap behavior, maturation computation, and authored-versus-derived patch metadata. |
| **5. Proposition, Evidence, and Belief Semantics** | Finish the one-belief model: proposition-as-edge, evidence-line grounding, dataset usage, independence, belief policies, projections. | Define the structured `BeliefResult`; make authored confidence an evidence input; type evidence vocabularies. |
| **6. Provenance, Agents, and Review** | Define one provenance stamp for authored and derived fields/statements; model humans, AI, tools, workflows, organizations, and review. | ORCID/model/tool IDs; field-level provenance; review state; trust policy. |
| **7. Scope, Federation, and Remote Sources** | Unify project, commons, peer, remote, and external authorities as scopes. Add remote source contracts and inventory dependencies. | `scope:kind:id` addressing; peer identity tables; addressing-grammar unification; GitHub/Zenodo/GEO source snapshots; sync leases. |
| **8. Views, Workbenches, and Compatibility Projections** | Define generated surfaces: DAGs, edge status, inventories, dashboards, exports, and editable workbenches. | Which legacy outputs remain? Which are read-only projections? Which editable projections are allowed, and how does normalize/fixpoint validation keep them honest? |
| **9. Migration Strategy** | Convert current code and docs in phases without compromising the target model. | Order, compatibility gates, deprecation/removal policy, validation strategy. |

The first implementation-facing sequence should likely be:

1. **Patch Contract** — fixes the missing keystone and exercises named graphs.
   This sequence assumes a minimal patch slice can build on today's
   `PropositionEntity`: add durable patch membership and graph emission without
   waiting for the full legacy edge migration. If the patch spec disproves that,
   Proposition/Evidence/Belief moves before Patch.
2. **Kind Descriptor & Model Registry** — removes the largest root duplication.
3. **Source Compiler & Identity Substrate** — cleans the substrate around the new
   descriptor model.
4. **Proposition, Evidence, and Belief Semantics** — finishes semantic collapse
   once the substrate is stable.

## Migration implications

The target design replaces several current patterns. These replacements should
be explicit so transitional code does not become permanent architecture.

| Current pattern | Target replacement |
|---|---|
| Many kind lists and per-kind dictionaries | One `KindDescriptor` registry |
| Pydantic registry plus independent JSON-schema registry | One canonical schema source, with generated adapters/exports if needed |
| Broad `Entity` base with kind-gated fields | Descriptor-driven typed entities or typed payloads |
| `edges.yaml` as an epistemic source | Workbench projection over proposition/evidence entities |
| Direct graph mutation commands | Source transactions compiled into graph outputs |
| Split addressing grammars and hardcoded graph URI schemes | One scope-address grammar plus generated URI mappings |
| Authored `edge_status` | Derived compatibility projection |
| Evidence edges, observations, and support arrays as alternate grounding paths | `EvidenceLine` as the only grounding unit |
| Multiple belief representations | One `BeliefResult`, many views |
| Project, commons, peer, and remote special cases | `Scope` with source/authority policies |
| Ad hoc provenance fields | Uniform provenance stamp for statements and fields |

The migration principle is:

> Build the target contracts first, then move current systems behind them one at
> a time.

Examples:

- A `KindDescriptor` layer can initially generate today's hardcoded registries;
  only later do the old lists disappear.
- A `Patch` entity can initially coexist with inquiries and workbenches; later,
  workbenches become projections over patches.
- A source compiler can first wrap existing adapters; later, direct graph
  mutation paths can be retired.
- A derived `edge_status` projection can preserve legacy DAG outputs while
  preventing authored status from re-entering the epistemic model.

## Design constraints

- The architecture must preserve continuous belief and avoid collapsing belief
  to binary truth.
- Evidence quality, identification, provenance, lifecycle, review, and rendering
  must remain orthogonal axes, not overloaded enum values.
- Human, AI, tool, workflow, and organization authorship must be represented by
  the same `Agent` mechanism, with method and review state recorded separately.
- Local and remote sources must use the same scope/addressing model. Remote
  sources add fetch, version, trust, and lease mechanics; they do not get a
  separate epistemic model.
- Generated views must be reproducible from compiled source state and versioned
  policies.
- Editable projections such as workbenches must round-trip through a normalize /
  fixed-point check. They may propose changes, but they do not own truth at rest.
- Transitional compatibility layers must have explicit retirement criteria.

## Non-goals

- This document does not define exact descriptor file syntax.
- This document does not choose the canonical schema technology.
- This document does not specify belief math beyond the one-result/many-views
  boundary.
- This document does not design a remote sync protocol in detail.
- This document does not provide an implementation schedule.

Those details belong in the subsystem specs above.

## Success criteria

The architecture is successful when:

- adding a new kind requires one descriptor change, not edits across multiple
  hardcoded lists;
- a proposition has exactly one belief result, regardless of whether it is shown
  as prose, a DAG edge, or a dashboard row;
- empirical evidence enters belief only through evidence-lines with explicit
  dataset usage and independence metadata;
- patch membership is durable compiled state and survives workbench regeneration;
- a peer project, commons entry, GitHub source, Zenodo source, and ontology term
  all resolve through the same scope mechanism;
- provenance can distinguish human judgment, AI judgment, tool output, empirical
  observation, and derived computation without relying on prose conventions;
- legacy views such as DAG edge status can still be generated without becoming
  source-of-truth.
