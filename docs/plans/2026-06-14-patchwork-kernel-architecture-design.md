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

## Layered architecture

The kernel is served by five layers. Each layer owns one concern and exposes a
narrow contract to the next layer.

| Layer | Owns | Does not own |
|---|---|---|
| **Model Registry** | `KindDescriptor`, schemas, relation descriptors, field-provenance rules, lifecycle vocabularies | Disk layout, graph output, belief math |
| **Source Compiler** | Loading local and remote sources into typed declarations: entities, identity rows, source snapshots, relation rows, patch memberships | Scientific semantics beyond declared contracts |
| **Epistemic Semantics** | Propositions, evidence-lines, dataset usage, independence, belief policies, derived belief results | Authoring layouts, DAG status files, remote sync |
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

## Subsystem specs

The architecture should be decomposed into focused follow-on specs. Each spec
owns one region and must not recreate a parallel mechanism.

| Spec | Purpose | Key decisions |
|---|---|---|
| **1. Kernel Architecture Overview** | This document: primitives, layers, invariants, decomposition, and migration implications. | Names and boundaries. |
| **2. Kind Descriptor & Model Registry** | Collapse entity-kind lists, core profiles, registry classes, path policies, statuses, JSON-schema mixins, and migrated-kind lists into one descriptor system. | Is core just a built-in manifest? Which schema system is canonical? How are descriptors generated and tested? |
| **3. Source Compiler & Identity Substrate** | Define source records, adapter policies, identity rows, error policy, reference-field policy, source snapshots, and compiled outputs. | Replace adapter-name branching; split compiler phases; unify audit and materialization. |
| **4. Patch Contract** | Make `Patch` real: named graph identity, membership, metadata, workbench contract, diagnostics, patch-level uncertainty, L0-L4 maturity. | Can propositions belong to multiple patches? How is maturation computed? What patch metadata is authored versus derived? |
| **5. Proposition, Evidence, and Belief Semantics** | Finish the one-belief model: proposition-as-edge, evidence-line grounding, dataset usage, independence, belief policies, projections. | Pick the internal belief representation; make authored confidence an evidence input; type evidence vocabularies. |
| **6. Provenance, Agents, and Review** | Define one provenance stamp for authored and derived fields/statements; model humans, AI, tools, workflows, organizations, and review. | ORCID/model/tool IDs; field-level provenance; review state; trust policy. |
| **7. Scope, Federation, and Remote Sources** | Unify project, commons, peer, remote, and external authorities as scopes. Add remote source contracts and inventory dependencies. | `scope:kind:id` addressing; peer identity tables; GitHub/Zenodo/GEO source snapshots; sync leases. |
| **8. Views, Workbenches, and Compatibility Projections** | Define generated surfaces: DAGs, edge status, inventories, dashboards, exports, and workbenches. | Which legacy outputs remain? Which are read-only projections? How do we prevent view state from becoming truth? |
| **9. Migration Strategy** | Convert current code and docs in phases without compromising the target model. | Order, compatibility gates, deprecation/removal policy, validation strategy. |

The first implementation-facing sequence should likely be:

1. **Patch Contract** — fixes the missing keystone and exercises named graphs.
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

