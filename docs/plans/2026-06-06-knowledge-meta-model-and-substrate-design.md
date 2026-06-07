# Knowledge meta-model and identity substrate — consolidated design

**Status:** Draft / design — target-state consolidation.
**Created:** 2026-06-06
**Origin:** Surfaced while hardening the v2→v3 entity-layout migration on MM30
(`~/d/cancer/cancer-types/multiple-myeloma`). A run of "renumber some plain-text
files" produced 41 latent alias collisions, opaque slowness, and whack-a-mole
patching. Root-causing it revealed the real problem is not the migrator: it is
that **entity identity is declared in four unreconciled ways** (markdown files,
the `entities.yaml` aggregate, overlays, commons twins) with no single invariant
governing them, and the migrator — like several other tools — re-implements
disk-format awareness instead of consuming a compiled model. This document
defines the ideal long-term shape that removes that whole class of problem.

## 0. Purpose & scope

This is **one consolidated meta-model** in two layers:

- **Part A — the epistemic model** (what knowledge *is*). This layer is already
  designed and largely implemented (the `h00` working model and its supporting
  contracts). Part A's job here is **faithful consolidation and citation**, not
  redesign. It is included so the substrate has a precise thing to serve.
- **Part B — the identity substrate** (how entities are *declared and
  identified* on disk, and how that compiles into the epistemic graph). This is
  the **new** design and the missing parsimony move.
- **Part C** is the seam that connects them.
- **Part D** makes the limitations and open questions obvious.

### Relationship to existing documents

| Document | Role relative to this doc |
|---|---|
| `~/d/science/meta/doc/plans/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md` (h00 RFC) | **Canonical source for Part A.** This doc consolidates and cites it; it does not supersede it. |
| `~/d/science/meta/core/decisions.md` — D-003, D-005, D-006 | Settled decisions Part A rests on. Not reopened. |
| `~/d/science/meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md` (t022) | Evidence payload contract (Part A §A5). Reused. |
| `~/d/science/meta/doc/plans/2026-05-06-t034-causal-graph-extension-design.md` (t034) | Sole causal/edge-typing substrate (Part A §A3, §A8). Reused per D-005. |
| `~/d/science/docs/proposition-and-evidence-model.md` | Propositions, evidence taxonomy, belief, freshness (Part A §A4–A7). Reused. |
| `~/d/science/docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` and `…-commons-scaffolding-design.md` | Adapter architecture + commons store the substrate formalizes (Part C). |
| `~/d/science/docs/plans/2026-06-05-dataset-first-class-entity-design.md` | The dataset dual-SSOT this doc reconciles (Part B §B4). |
| `~/d/science/docs/plans/2026-06-05-local-kind-layout-migration-design.md` | **Tactical / near-term.** Migrates project-local *markdown* kinds as-is. This doc is the **target state** that, additionally, retires structural *fileless* declarations. The two are reconciled explicitly in §D3 so they do not appear to disagree. |

### Non-goals

- Does **not** reopen settled epistemic decisions (D-003 continuous belief,
  D-005 t034-as-sole-causal-substrate, D-006 RDF/TriG substrate).
- Does **not** close the open epistemic forks (uncertainty representation,
  belief backbone, elicited-belief depth, federation topology, etc.). Those are
  inherited as open and listed in §D1.
- Does **not** specify the migration implementation. That is a follow-on plan
  (writing-plans) once this design is approved.

---

## Part A — The epistemic model (consolidated)

> Part A restates an already-designed, partly-implemented model so the substrate
> has a precise target. Every subsection cites its canonical source; where this
> doc and a cited source ever diverge, the cited source wins.

### A1. One graph; patches are named graphs

Knowledge is **not** one monolithic graph nor two fixed layers, but a
**federated patchwork of small epistemic neighborhoods ("patches")** — local
graphical representations (causal DAGs, Bayesian DAGs, data→evidence and
literature→evidence maps, elicited belief subgraphs, discovered CPDAG fragments)
each surrounding a hypothesis / question / evidence cluster (h00 RFC §2).

Per **D-006**, the substrate for this is **W3C-native**: the live
`knowledge/graph.trig` already *is* RDF in TriG with **named graphs**, declares
**PROV-O**, and **reifies edges as first-class IRI nodes**. Therefore:

- a **patch** is a **named graph** (an addressable unit carrying ladder level +
  provenance + uncertainty as triples about the graph IRI);
- a **multi-edge** (e.g. an associative edge and a causal claim over the same
  pair) is **distinct reified-edge nodes** over the same subject/object — the
  associative edge is never rewritten (t034 promotion-by-reference);
- **world↔claim** reification uses the existing edge-as-node n-ary pattern.

RDF-star and labeled-property-graph substrates were considered and rejected
(D-006). **This RDF/TriG graph is the single model that everything else
compiles into** — the fact Part B makes load-bearing.

### A2. Entities and entity classes

Entities carry a canonical identity `<kind>:<local-id>` (regex enforced;
case-insensitive aliases; deprecated-id support — `entity_identity.py`). Entities
fall into three orthogonal **classes** that determine belief/freshness behavior
(`~/d/science/docs/plans/2026-05-03-epistemic-dependency-graph-design.md`):

| Class | Examples | Belief-carrying | Freshness |
|---|---|---|---|
| **Epistemic** | hypothesis, question, proposition, observation, finding, interpretation, discussion, story, mechanism, model, assumption, report | yes | yes (`bears_on` sink) |
| **Operational** | task, dataset, workflow, workflow-run, data-package, experiment, method, transformation, paper (artifact), spec, plan | no | no |
| **Reference** | concept, topic, variable, article, inquiry, canonical_parameter, domain entities | no | no |

Load-bearing distinctions (h00 corpus): *observation* is epistemic (a claim
about data), *paper* is operational (the artifact) while *article* is reference
(the bibliographic record), *assumption* and *model* are epistemic.

### A3. Relations / edges

Edges are **typed and reified**. The causal/edge-typing vocabulary is **t034,
reused verbatim** (D-005): `graph_object_type` (DAG/CPDAG/PAG/ADMG/…), the
10-role `epistemic_role` taxonomy, the Petersen-stage payload pipeline
(`causal-prior-bundle → causal-discovery-run + causal-graph → graph-diagnostic →
causal-identification → causal-effect-estimate` + mediation/MR), and
identification-by-reference promotion (edge roles are never rewritten in place).
No second CPDAG/edge-role vocabulary may be introduced.

A forward-in-time **`bears_on`** dependency relation
(`…/2026-05-03-epistemic-dependency-graph-design.md`) records "what should be
revisited": any source kind → epistemic target. It is auto-derived from
`tests`/`supports`/`disputes`/`grounds`/`contains`/`synthesizes`/… plus
`prov:wasDerivedFrom`, transitively closed, terminating at epistemic targets;
hand-authored `bears_on` is permitted where auto-rules miss.

### A4. Propositions, hypotheses, claim layers, lifecycle

The primary truth-apt unit is the **proposition**
(`~/d/science/docs/proposition-and-evidence-model.md`). Authored: text, S-P-O
triple, scope, provenance, qualifiers. Derived: `belief_state`, `confidence`,
`uncertainty`, `contestation`, `fragility`. **Hypotheses** are proposition
bundles / proposition-like conjectures with aggregate support rolled up. There
are **no hard gates**: a proposition stays queryable when belief drops; working
models are revised, not deleted. Default stance is **skeptical**.

Optional layered-claim metadata (use deliberately, do not auto-upgrade):
`claim_layer` (`empirical_regularity | causal_effect | mechanistic_narrative |
structural_claim`), `identification_strength` (a "what kind of identification
situation" hint — **not** a Pearl-rung encoding), `measurement_model`,
`supports_scope`, `rival_model_packet`.

**Freshness** (`fresh | needs-review | stale`) is a flag, not a gate; set/cleared
via `science entity review`. Pre-reg semantics split: operational pre-regs gate;
epistemic pre-regs feed the evidence base via weighted `bears_on`.

### A5. Evidence is first-class (not a scalar)

Evidence is carried by the **t022 evidence payload** (core contract: 18 fields,
12 required), dispatched by `artifact_type`, composed via typed `extensions`,
with explicit provenance axes (`input_artifact_refs`, `claim_source_ref`,
`method_ref`, `agent_ref`, `pipeline_provenance_ref`), `support_direction`,
`validation_role` (permission) vs `validation_status` (state),
`uncertainty_summary`, and `reason_codes` (some auto-injected by the validator;
biconditional declaration rules). Evidence *types*: literature, empirical,
simulation, benchmark, expert-judgment; *stances*: `supports | disputes` (both
first-class). Negative results are observations with a disputing/weakened stance,
not a separate type.

### A6. Belief and uncertainty (the no-double-counting machinery)

Belief is **derived**, ordinal, and audited — never a hand-set truth value
(`~/d/science/science/src/science_tool/graph/belief.py`, `belief-logodds-v3`):

1. Collect evidence units (reified edges + metadata).
2. **Independence-aware reduction** — group by `(independence_group, stance)`;
   keep the highest-quality winner per group; exclude circular dependencies.
3. Ordinal magnitude: 0 support → `speculative`; 1 → `fragile`; ≥2 clean support
   + a qualifying direct test → `well_supported`; else ≥2 → `supported`.
4. Decisive-refutation cap; `contested` flag when both stances present.
5. Proxy gating (an indirect/derived proxy without a `measurement_model` cannot
   contribute at full weight).

The **`EvidenceIndependence`** taxonomy — `independent`, `shared_source`,
`shared_dataset`, `circular` — is exactly the mechanism that prevents counting
the same underlying source twice. The canonical example in the design corpus:
*ten papers asserting the same finding via one shared dataset collapse to one
unit (≈53% of the naive support score).* **This requirement is already
satisfied; the substrate must not regress it.** Per **D-003**, belief is
continuous in (0,1), never collapsed; binary decisions are computed *from* belief
at the decision point. Calibration is an audited property, not an assumption.

### A7. Provenance as orthogonal axes

Provenance is **not one tier enum** but four reused axes (h00 RFC §5):
`ProvenanceType` (mathematical/empirical/editorial/derived); dataset
`source_class` + `derived_kind`; evidence-edge `evidence_type`; and the
PROV-O agent + `review_state`. An audit view joins them (e.g. "produced-by ai
and unreviewed"). Source **dependence is explicit graph structure**, not a
per-item caveat, because it spans claims (q03).

### A8. Progressive ladder; discovery vs elicitation

Representations coexist on a ladder; each subsumes the prior (h00 RFC §6):

| Level | Representation |
|---|---|
| L0 | typed edge + scalar |
| L1 | + belief result + provenance axes + independence |
| L2 | + associative-vs-causal role + measurement model |
| L3 | partial causal structure (CPDAG/PAG/ADMG) + identification |
| L4 | full PGM/SCM; `do()` + counterfactual (pgmpy / Pyro·ChiRho exporters) |

"Honest default L0–L2 for almost everything; L3–L4 local and earned." A model
arrives by two equally-first-class routes (h00 RFC §3.5): **elicitation** (a
prior — believed structure/parameters with honest uncertainty) and **discovery**
(a posterior from data). They differ only in provenance and where on the
prior→posterior arc they sit. The Pearl rungs crosswalk strictly to t034 payload
states, not to proposition-level hints.

### A9. Federation & meta-analysis as first-class

Patches connect by **two glue mechanisms** (h00 RFC §2; t066/t067): **ontology
alignment** (shared symbolic identifiers — MONDO/MeSH/HGNC) and a **data-driven,
bias-corrected latent axis** (publication-attention removed via PMI; diseases
embed in a learned coordinate). Composition is multi-scale:
`patch ⊂ project ⊂ project-collection`, with views `within(...)` or
`aggregate(subset | sampled | global)`. Meta-analysis is therefore a **modeled
object** (a federated view over patches), not merely a pipeline stage.

---

## Part B — The identity substrate (new design)

### B0. Thesis (load-bearing)

> The substrate has **one identity compiler**. All authoring inputs declare
> either **owner**, **borrower**, or **external-reference** participation. The
> compiler produces the identity table and the RDF/TriG graph. Migration,
> conformance, belief, graph materialization, and audit consume that **compiled
> model**, not raw disk layouts.

The h00 epistemic layer (Part A) is already coherent. The substrate is what was
never made precise; this thesis is the missing parsimony move.

### B1. The substrate invariant

Every entity participates in the identity system in exactly one of **three
modes**, **relative to an address space** (see §B3 for `owner_scope`):

- **Owned entity.** Exactly **one canonical owner declaration**, usually
  `entities/<kind>/<id>.md`. The owner mints the id and may renumber it.
- **Borrowed entity.** **Zero local owner declarations.** May have local
  **context attachments** (e.g. overlays) that add project-specific context to an
  id owned elsewhere. Never renumbered locally.
- **External reference.** An **authority-owned bare identity** (e.g. an
  HGNC/MONDO term), optionally resolved through an authority registry. It may
  enter the graph as a referenced node but has **no local declaration** and is
  **never renumbered**.

The single corresponding error condition (not a fourth mode):

- **Collision.** **Two owner declarations for the same canonical id in the same
  address space.** This — and only this — is the identity error the compiler must
  reject.

This is precise without pretending overlays disappeared: overlays are still
files, and external refs still enter the graph — they simply are **not identity
declarations**.

### B2. One canonical declaration surface (not one file-like surface)

The parsimony claim is about **declarations**, not files:

> **Every owned, framework-minted entity has exactly one owner declaration.**
> Most owner declarations are markdown entity files (`entities/<kind>/<id>.md`).
> Externally authoritative things (HGNC/MONDO/…) are not locally owned and do
> not need files.

Consequences:

- **Overlays are context attachments, not declarations.** An overlay file
  (`overlay_of: <id>`) contributes local body/metadata to a borrowed id; it never
  appears in the owner column of the identity table. Overlays are read by
  **exactly one adapter** (`OverlayAdapter`, §C3); an `overlay_of` file under an
  owner root (`entities/`) is a **conformance error**, so each substrate role has
  a single reader.
- **External references are graph participants, not declarations.** They never
  get files and never get renumbered; at most they resolve through an authority
  registry.
- **"Everything is a file" is explicitly *not* the rule** — it breaks at scale
  (one would never author 20,000 HGNC gene files). The rule is one *declaration*
  per *owned* entity.

This collapses the historical four mechanisms: markdown files **are** the owner
surface; overlays **are** the borrow-arm's context attachments; commons twins
**are** owner declarations in another scope (§B3); the `entities.yaml` aggregate
**is retired in the target state** (a transitional deprecated-owner mode bridges
rollout — §B5, §C3).

### B3. Two columns: `participation_mode` and `owner_scope`

The identity table records **two** independent facts per row, not one
owned/borrowed bit — conflating them is what made "`owner_scope = commons`"
ambiguous:

- **`participation_mode`** ∈ {`owner`, `borrower`, `external-reference`} — what
  *this row* contributes.
- **`owner_scope`** — *where the owner declaration lives* (the scope that owns
  the id): `<this-project>`, `commons`, another named project, or an
  `<external-authority>` (HGNC/MONDO/…).

So a local project that overlays a commons topic has the row
`participation_mode = borrower, owner_scope = commons`. When the commons store is
*also* loaded, *its* row for the same id is
`participation_mode = owner, owner_scope = commons`. `owner_scope` therefore
always means one thing (where the owner lives); `participation_mode` says what
the current row contributes. "No owned file here" is precisely
`participation_mode = borrower` (or `external-reference`) — a project-scoped
statement, never a global one.

The identity **key** is the pair **`(owner_scope, canonical_id)`**. The collision
rule is then exact: **two `owner` rows with the same `(owner_scope,
canonical_id)`** is the error. A commons-scoped owner plus a project-scoped
borrower of the same `canonical_id` are two *different* rows (one `owner`, one
`borrower`) — the normal overlay case, which the old migrator misread as a
collision 41 times.

### B3a. Reference resolution must be executable

`(owner_scope, canonical_id)` is the identity key, but **references in bodies and
frontmatter are written bare** (`topic:bayesian`, `paper:Adams2025`). Bare refs
are only safe under an explicit resolution rule; without one, cross-scope /
federated resolution is ambiguous (the gap flagged in review). The rule:

1. **Bare refs resolve through a fixed resolution *search* chain:** this-project →
   imported scopes (commons, then named imported projects) → external authority.
   The chain only enumerates *candidate* scopes to look in — it is **never** used
   to break owner ambiguity by shadowing (rule 3 governs that).
2. **Bare ids must be unambiguous across all *loaded* scopes.** Commons slugs are
   already globally unique within type (commons-scaffolding design), so the
   common case is safe by construction.
3. **A bare id that resolves to an `owner` in more than one loaded scope is an
   `ambiguous_reference` error** — the compiler refuses it (it does *not* let an
   earlier link in the search chain win), and a **scoped reference form**
   (`commons:topic:bayesian`, `<project>:topic:x`) is required.

This makes scope semantics executable *before* a full cross-project reference
syntax exists (the federation primitive `t068`, §D4): until then a project loads
a single owner scope plus commons, where bare uniqueness holds, and the scoped
form is both the escape hatch and the forward-compatible path to `t068`.

### B4. Datasets — the dual-SSOT edge case, resolved

The dataset design
(`~/d/science/docs/plans/2026-06-05-dataset-first-class-entity-design.md`) gives
dataset metadata a dual single-source-of-truth: an **entity descriptor** for
project metadata and a **datapackage** for resource metadata. Stated naively this
looks like a second entity-declaration system and would reopen the
"multiple systems" fight. It is resolved by the §B1 invariant:

> For a dataset, the **entity file is the identity declaration**; the
> **datapackage is attached resource metadata**, **not** a second entity
> declaration.

The datapackage compiles into the graph as resource/`prov` triples *about* the
dataset entity; it never occupies the owner column. There is still exactly one
owner declaration per owned dataset. (Same shape generalizes: any sidecar —
datapackage, `.anno.trig`, generated index — is an attachment, never a
declaration.)

**Zero-owner datapackages (rollout).** A datapackage may currently exist before
an entity-file owner does. **Target state:** a datapackage with **no** owner
declaration is an **error** — an attachment must attach to something. **During
rollout:** the compiler **synthesizes a deprecated, transitional `owner` row**
for an orphan datapackage (mirroring the aggregate transitional mode, §C3), so
datapackage-only datasets keep loading and are surfaced for migration to a real
owner file. Conformance flags every synthesized/deprecated owner; Phase 2 (§Next
step) flips the rule from "synthesize + warn" to "error".

### B5. Retirement of structural fileless entities (`entities.yaml`)

The aggregate manifest (`knowledge/sources/<profile>/entities.yaml`) survives
today for one non-redundant reason: it sole-sources **fileless** kinds
(concept/decision/latent). Everything else it does is **stub-shadowing** real
markdown owners — pure debt. In the target state:

- **`entities.yaml` structural entity declarations are retired.** Each former
  entry resolves to one of the §B1 modes:
  - coined-here lightweight node (a concept/decision/latent this project
    introduces) → an **owned declaration** (`entities/<kind>/<id>.md`, a small
    file: frontmatter + a line of definition + links);
  - a reference to external/standard vocabulary → an **external reference** (no
    file);
  - a stub shadowing an existing markdown owner → **deleted**.
- **`core/decisions.md` becomes a generated view** over `entities/decision/*.md`
  (like `big-picture` generates `synthesis.md`). This also clears the
  "_Digest pending_" load-bearing constraint in MM30's `AGENTS.md`.

This is the **ideal long-term direction**; the near-term migrator (June-5 doc)
explicitly treats structural `entities.yaml` kinds as out of scope (§D3).

### B6. What is *not* a surface

Generated artifacts are **outputs, never authoring surfaces**: `core/decisions.md`
(decision log), glossaries, indices, dashboards, `synthesis.md`. They are derived
from owner declarations and must never be a place an identity is declared. The
compiler ignores them as inputs.

---

## Part C — The compiler seam (how A and B connect)

### C1. The identity compiler

A single pipeline turns authoring inputs into the compiled model:

```
authoring inputs ──▶ identity compiler ──▶ { identity table , RDF/TriG graph }
(owner decls,                              (one owner per (id, owner_scope);
 overlays,                                  borrowers + external refs attached;
 datapackages,                              reified edges; PROV-O)
 external refs)
```

Each input declares its **participation mode** (owner / borrower / external-ref)
and, for owners, its **`owner_scope`**. The compiler enforces the §B1 invariant
once, centrally.

### C2. The architectural law

> **Every consumer reads the compiled model, not raw disk.** Migration,
> conformance, belief, graph materialization, and audit operate on the identity
> table + graph the compiler produced — never by re-walking directories with
> bespoke, per-tool format awareness.

Violating this law is the direct cause of the migration sprawl: the migrator
re-implemented disk-format awareness, knew about three of four surfaces
inconsistently, and treated borrowers as owners — yielding 41 phantom
collisions. Centralizing the invariant makes that class of bug structurally
impossible.

### C3. Adapters, formalized

The existing adapter set (`…/2026-05-13-multiproject-schema-and-shared-store-design.md`)
already funnels into a global identity table; the substrate formalizes each
adapter's **participation mode** + **owner_scope**:

| Adapter | `participation_mode` | `owner_scope` | Change |
|---|---|---|---|
| `MarkdownAdapter` | `owner` **only** | this project | owner-only for identity; `overlay_of` in an owner root is a conformance error (§B2) |
| `SharedEntityAdapter` (commons) | `owner` | `commons` | declares scope explicitly |
| `OverlayAdapter` | `borrower` (context attachment) | the borrowed owner's scope | **sole** borrower-context reader |
| `DatapackageAdapter` | attachment (rides a dataset owner) | n/a | never a declaration (§B4); zero-owner handling per §B4 |
| authority/ontology resolver | `external-reference` | external authority | bare-id resolution; no files |
| `AggregateAdapter` | `owner` *(deprecated, transitional)* | this project | emits deprecated owner rows so nothing drops before content migrates; **removed at §B5 retirement (Phase 3)** |

### C4. Migration as a pure function of the compiled model

With the compiled model in hand, migration is small and total:

- **renumber** *real* entities owned in *this* scope (`participation_mode = owner`,
  `owner_scope = this-project`, **not** transitional), rewriting references through
  the id-map;
- **migrate/promote transitional owners by their phase, never blindly renumber
  them:** deprecated `AggregateAdapter` rows are *promoted* to real owner files by
  the §B5 triage (Phase 3); synthesized orphan-datapackage owners are *promoted*
  to real dataset owner files by the §B4 migration (Phase 2). Until promoted, a
  transitional owner is carried as-is (it keeps its existing id), so a half-rolled
  project is never renumbered into an inconsistent state;
- **never touch** borrowed ids or external references;
- **ignore** attachment surfaces and generated views;
- **collision** = two `owner` rows with the same `(owner_scope, canonical_id)` →
  reported, blocks apply.

The held "simulation-mask" hack and the per-tool overlay/aggregate special-casing
are no longer needed: they were compensating for the missing compiled model.

---

## Part D — Limitations & open questions (made obvious)

### D1. Inherited-open epistemic forks (NOT resolved here)

This doc consolidates Part A; it does **not** close these recorded forks. They
remain open and are owned by the h00 RFC:

- **Uncertainty representation** (RFC §12.3): log-odds scalar vs subjective-logic
  opinion vs credal/Dempster–Shafer. Recommended: opinion as a derived view;
  decision deferred pending prototype.
- **Belief backbone** (RFC §12.4): fixed reduction formula vs
  argumentation-framework semantics. Deferred.
- **Elicited-belief depth** (RFC §12.5): per-edge held-credence only vs also
  parameter priors (whether elicitation can reach L4). Deferred.
- **Federation topology** (D-006 carry-forward; t067/t068): whether patch
  named-graphs nest or stay flat. The **full validating cross-project reference
  syntax** (verifying a scoped ref against a remote scope's loaded owners) is
  deferred to the federation primitive `t068`; §B3a defines only the **minimal
  compiler-scoped disambiguation form** needed now (a scoped ref the local
  compiler can parse and require when bare ids collide across loaded scopes).
- **`claim_layer: counterfactual`** (RFC §12.6): default no; schema migration only
  if a proposition-level need is shown.
- **Field-vs-entity provenance threshold** (q03): when a source/transformation
  becomes a first-class graph node vs a payload field. No algorithm; guidance
  emerging from use.

### D2. Substrate migration costs (real, not hand-waved)

- **Decisions promotion:** the ~19 `D…`-style sections in `core/decisions.md` →
  individual `entities/decision/*.md` owner declarations; `decisions.md` becomes
  generated.
- **Concept triage:** the ~24 `entities.yaml` concepts each need a per-entity
  own-vs-external call (coined-here → file; external vocab → bare ref). This
  judgment is *forced* by the model — a feature, but real work.
- **Tooling rewrite:** migration + conformance must be re-pointed to consume the
  compiled model (§C2). Until then they remain the fragile disk-walkers.
- **Mid-cutover compatibility:** projects part-way through v2→v3 must not be
  bricked; the compiler and migrator need to tolerate mixed states during
  rollout.

### D3. Tension with the June-5 tactical design — explicitly reconciled

The June-5 local-kind migration design
(`…/2026-06-05-local-kind-layout-migration-design.md`) migrates project-local
**markdown** kinds as-is and **explicitly scopes out** structural fileless
entities (its "Out of scope: structurally-defined local entities
(`entities.yaml`)"). That is **correct as near-term tactics** and does **not**
contradict this doc:

- **June-5 (tactical):** get markdown local kinds into `entities/<kind>/` so MM30
  reaches `layout_version: 3` now; leave `entities.yaml` structural kinds
  untouched.
- **This doc (target):** *additionally* retire structural fileless declarations
  (§B5) and move every consumer onto the compiled model (§C2).

Stated plainly so the two docs do not appear to disagree: **the June-5 doc is a
way-station; this doc is the destination.** The June-5 work is forward-compatible
— its renumbered markdown owners are already valid owner declarations under §B1.

### D4. Asserted-but-unbuilt pieces

- **Authority-registry resolution** for external references (§B1, §B2) is
  asserted; the bio **identity pillar** is where it gets built. Until then,
  external refs are recognized but not richly resolved.
- **Cross-scope resolution** (`owner_scope = commons` / another project) needs
  the federation primitive `t068`; the local-only resolver cannot yet verify a
  cross-scope owner exists.

### D5. Where the model could still be wrong

- **Are concepts worth owner declarations at all,** or are some pure tags? §B5
  forces the call but the boundary between "coined lightweight entity" and "tag"
  is judgment, not algorithm.
- **Multi-edge proliferation:** reified edges per pair (assoc + causal + …) are
  correct but could explode graph size; no pruning policy is specified.
- **Calibration is unaudited** (D-003): the entire belief layer's value rests on
  a calibration property not yet measured on a ground-truthable subset.

---

## Next step

Per the brainstorming → writing-plans flow: on approval of this design, produce a
phased implementation plan. The natural phasing, smallest-blast-radius first:

1. **Compiler seam (§C):** introduce `participation_mode` + `owner_scope` (§B3)
   and the bare-ref resolution rule (§B3a) in the identity table; route migration
   & conformance through the compiled model. **The compiler supports two
   transitional `owner` states from day one** — `AggregateAdapter` deprecated-owner
   rows (§C3) and synthesized owners for orphan datapackages (§B4) — so nothing is
   dropped before its content is migrated. Subsumes and retires the June-5
   disk-walking once parity is proven.
2. **Dataset reconciliation (§B4):** migrate orphan datapackages to real
   entity-file owners; flip zero-owner from "synthesize + warn" to **error**; add
   the conformance check that forbids a second declaration.
3. **`entities.yaml` retirement (§B5):** concept/decision/latent triage; generate
   `core/decisions.md`; delete stub-shadows; **remove the `AggregateAdapter`
   deprecated-owner mode** once no aggregate declarations remain.
4. **External-reference resolver (§B2, §B3a, §D4):** behind the bio identity
   pillar; enables scoped refs across more than one loaded owner scope (`t068`).

Each phase is independently shippable and leaves the tree green. The transitional
`owner` modes (§C3, §B4) exist only between the phase that introduces them
(1) and the phase that migrates their content and removes them (2–3) — the model
is never simultaneously "routed through the compiler" *and* dropping declarations.
