# Epistemic Data Model — Umbrella Design

**Date:** 2026-06-08
**Status:** Design (approved scope; planning only — implementation held until v3, see §7)
**Kind:** Umbrella design (consolidation SSOT). Facet design+plan docs elaborate regions of this model.

> **Authority boundary (read first).** This document is the **single source of truth for the
> post-v3 epistemic data model consolidation**. It is **not** above `h00` conceptually, and **not**
> above the identity/storage substrate. It sits *below* the `h00` working model (which it makes
> precise) and *beside* the substrate (which remains a separate, in-flight plumbing layer). Its job
> is to collapse the scattered epistemic-model design docs into **one coherent system** — explicitly
> **not** a new system parallel to `evidence-aggregation-and-belief` or anything else. Where this doc
> and a folded-in doc disagree, this doc wins; where this doc and a *reused authority* (§1) disagree,
> the authority wins and this doc is wrong.

---

## 1. Authority chain & consolidation boundary

### 1.1 Reused authorities (NOT superseded)
This spec conforms to and reuses, without replacing:

- **`meta/specs/hypotheses/h00-working-model.md`** — the top-level conceptual working model
  (federated patchwork of patches; the ladder L0–L4; provenance-as-axes). This doc makes h00
  *precise*; it does not overrule it.
- **`meta/core/decisions.md` D-005** — *Reuse t034 verbatim as the sole causal/edge-typing
  substrate; h00 net-new rides the t022 evidence-payload extension contract.* A **proposition's
  relational rendering** (the causal-DAG edge) is **not** a new edge vocabulary — it rides t034
  edge-as-node payloads (governed by D-006), and the proposition's belief/uncertainty payload is a
  t022 extension. No second CPDAG/PAG/edge-role vocabulary is created.
- **`meta/core/decisions.md` D-006** — *W3C-native substrate (RDF/TriG named graphs + PROV-O +
  edge-as-node reification); a patch is a named graph.* A relational proposition's edge rendering
  rides the existing edge-as-node reification; patches are named graphs.
- **`docs/proposition-and-evidence-model.md`** — the canonical claim/evidence vocabulary
  (`claim_layer`, `identification_strength`, authored-vs-derived split, the rule that conclusions must
  not hide inside one manual status field). Retained as the field-level authority.
- **`meta/doc/plans/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md`** — the RFC that
  D-005/D-006 resolved (t034 reuse + W3C-native substrate). Parent of the model precisified here.
- **t034 causal/edge-typing substrate** — `graph_object_type`, the `epistemic_role` taxonomy, the
  payload stages, and promotion-by-reference. Reused **verbatim and untouched** (D-005). A relational
  proposition's edge rendering rides t034; **`edge_status` retirement is NOT a t034 change.**
- **DAG two-axis / rendering tooling** (`references/dag-two-axis-evidence-model.md`,
  `science/src/science_tool/dag/schema.py`) — a *separate* layer owning the canonical **5-value
  `edge_status` + `identification` two-axis enum** and the DAG-figure renderer. Reused, but its
  *role* shifts from authored source-of-truth to a **derived projection** (§3). This — not t034 — is
  the layer `edge_status` retirement touches.

### 1.2 Superseded / folded in (this doc becomes their successor)
Each gets a "superseded by → this doc" banner; their still-valid content is absorbed below or routed
to a facet:

- `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` (+ phase-1/phase-0 plans)
- `docs/plans/2026-05-24-evidence-aggregation-phase2-design.md`
- the **Part-A epistemic content** of `docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md`
  (its Part-B/C substrate content stays with the substrate docs)
- `docs/plans/historical/2026-05-03-epistemic-dependency-graph-design.md`
- April layered-claims/causal-methodology predecessor (deleted during plans cleanup)
- March claim-centric uncertainty predecessor (deleted during plans cleanup)

### 1.3 Predecessors folded as migration/rendering inputs (credited, not authorities)
Their design intent feeds the facet migrations; they are superseded as standalone designs:

- DAG rendering / edge-status predecessors:
  `docs/plans/historical/2026-04-17-edge-status-dashboard-design.md`,
  `docs/plans/historical/2026-04-17-inquiry-edge-posterior-annotations-design.md`,
  `docs/plans/historical/2026-04-19-dag-rendering-and-audit-pipeline-design.md`,
  `docs/plans/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md` → feed `epistemic-edges`.
- Dataset predecessors: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`,
  `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md`,
  and the A1/A2/B1/B2 dataset designs/plans → feed `dataset-evidence-flow`.

### 1.4 Out of scope (separate layer)
The identity/storage **substrate** — identity table, adapters, TriG compilation, `layout_version`
v2→v3 migration — keeps its own in-flight docs (`2026-06-06-…-substrate-design.md`,
`2026-06-07-substrate-*`). This spec **assumes** the v3 destination state (§7) and reads the
*compiled model*, never raw disk.

---

## 2. The single model

### 2.1 Entity classes
Three orthogonal classes, registry-enforced (reused from the epistemic-dependency-graph work):
**epistemic** (belief-carrying, freshness-tracked), **operational** (no belief/freshness),
**reference** (names external things). Every registered kind has exactly one class.

### 2.2 Proposition — the one truth-apt unit
- **Proposition** = the atomic, truth-apt assertion (the canonical kind in
  `proposition-and-evidence-model.md`). It is the **single locus of belief**. A proposition is an
  *assertion*, not a sentence: it carries a structured form (subject · relation · object, e.g.
  `A —causal-influence→ B`, possibly n-ary) and an optional prose statement. There is **no separate
  `Claim` entity** — `proposition` already is the abstract truth-apt unit, so a redundant abstraction
  layer is not introduced. *(This collapses the earlier draft's `Claim`/`proposition` split into one
  kind — a parsimony correction folded back from the `epistemic-edges` facet, 2026-06-08.)*
- A proposition has up to two **renderings of the same assertion**, sharing the proposition's **one
  belief**. Renderings are *views*, not entities:
  - **prose rendering** = the proposition's statement text;
  - **graphical rendering** = the proposition shown as a patch edge, present only when the
    proposition is a **relational proposition** (see below). Non-relational propositions (e.g.
    "gene X is overexpressed in MM") have no edge rendering.
- **Relational proposition** = the data-model primitive for a truth-apt DAG edge. A truth-apt edge
  **is** a relational proposition (subject · predicate · object + `claim_layer` +
  `identification_strength`); it is **not** linked to a separate proposition. Its **IRI is also its
  reified edge-node IRI** for rendering and patch membership — belief and rendering address the *same*
  node, never split across two. Identity is **per-claim, not per-pair**: multiple relational
  propositions may share a `(subject, object)` pair.
- **Conformance:** per D-005 the edge rendering carries t034's edge typing (`epistemic_role`,
  `graph_object_type`) as *payload on the proposition*, not as a second edge-identity system — no new
  edge vocabulary. Per D-006 it is an edge-as-node IRI in a named-graph patch. Content-addressed
  edge-node IRIs remain correct for *derived/deduped plumbing* (e.g. `bears_on`), **not** for authored
  scientific assertions, whose canonical identity is the proposition's own.
- **Cross-source identity (deferred).** When two propositions paraphrase the same assertion
  (e.g. a paper's reported claim vs. ours under test), they stay **distinct propositions linked by
  evidence**, preserving *who asserted it*. A canonical "same assertion" merge is YAGNI now; if ever
  needed it is a `same_assertion` / `paraphrase_of` **relation between propositions**, not a new kind.

### 2.3 Edge taxonomy — proposition-edges vs plumbing edges
A precise **two-way distinction** — proposition vs non-proposition (correcting the earlier loose
"structural = no belief"):

1. **Proposition-edges** — truth-apt, belief-carrying edge renderings of relational propositions.
   This **includes `claim_layer: structural_claim`**: definitional, benchmark, and model-structure
   assertions are *still propositions* and still carry belief. `structural_claim` is a `claim_layer`,
   **not** a synonym for plumbing.
2. **Plumbing edges** — **not** truth-apt, **no** belief:
   - **organizational links** (containment, grouping, "see also", patch membership);
   - **measurement-model plumbing** (the proxy/latent wiring described by `measurement_model`
     sidecar metadata — the link itself is structure, not an assertion under test).

The test is truth-aptitude, not the word "structural." A measurement *proxy assertion* ("X is a valid
proxy for latent Y") is a `structural_claim` proposition; the *wiring* that attaches the proxy to the
observation node is plumbing.

### 2.4 Evidence-line — the atomic grounding unit
An **evidence-line** (epistemic entity, already built and registered) is the single subject of
`cito:supports` / `cito:disputes` edges into a proposition. It carries:
`stance` (supports/disputes), `strength`, `evidence_type` (canonical enum: `empirical_data_evidence`,
`literature_evidence`, `simulation_evidence`, `benchmark_evidence`, `expert_judgment`),
`independence` (+ `independence_group`, `shared_dataset`/`shared_lab`/…), and
**`dataset_usage`** (which datasets it analyzed, with role + overlap). It is the **only** thing that
grounds a proposition. Background material that is not an evidence-line does not enter belief.

### 2.5 Belief — derived, never authored
Belief is computed by the **one** belief engine (`science/src/science_tool/graph/belief.py` +
`belief_scalar.py`) from a proposition's evidence-lines, with independence-aware reduction:
- **ordinal magnitude** `speculative < fragile < supported < well_supported`,
- orthogonal **`contested`** boolean,
- optional **continuous log-odds** `(massed_support, massed_dispute)` pair with an adversarially-swept
  robustness band (never a bare net; suppressed when not robust).

No belief is authored. There is exactly one belief engine and one belief result per proposition —
shared by both renderings. This is the anti-parallel guarantee: the edge does not get its own belief
mechanism.

### 2.6 Datasets — ground evidence-lines, one path
Datasets are **operational** entities (no belief of their own). The single grounding path is
`dataset →(dataset_usage)→ evidence-line →(cito:supports/disputes)→ proposition`. Per-dataset influence and
the *N-independent-datasets vs N-analyses-of-one* distinction are resolved by the already-built
independence machinery (A1 `source_class`/`dataset_usage`, A2 reference down-weight, B1 usage
materialization, B2 independence derivation). **No direct dataset→proposition edge** — that would be a
second grounding path, i.e. the parallel system we are ruling out.

### 2.7 Patches, ladder, provenance (from h00, reused)
- **Patches** — propositions live in patches (named-graph subgraphs around a hypothesis/question); the
  graph is a federated patchwork (h00 R1; D-006).
- **Ladder L0–L4** + **identification** axis on proposition-edges — the causal-role progression (typed edge
  → belief+provenance → assoc/causal-role → partial-causal CPDAG/PAG/ADMG → full PGM/SCM). Honest
  default L0–L2; L3–L4 local and earned.
- **Provenance = orthogonal axes**, not one tier: `ProvenanceType`, dataset `source_class`, evidence
  `evidence_type`, PROV-O agent + `review_state`/freshness.

---

## 3. Resolving Issue 2 — `edge_status` misalignment

**Canonical vs legacy.** The canonical `edge_status` is the **DAG two-axis enum**
(`references/dag-two-axis-evidence-model.md` / `dag/schema.py` — the rendering tooling, *distinct
from* the t034 causal substrate): `supported / tentative / structural / unknown / eliminated`, paired
with `identification` ∈ `interventional / longitudinal / observational / structural / none`. The
**23-value vocabulary in
MM30's `*.edges.yaml` is MM30 legacy status/status-family drift** (it never conformed to the enum
because MM30 does not run `science dag validate`). The fix is not to bless 23 values — it is to
**decompose the legacy families onto the axes the model already separates** during migration, and to
make the displayed edge status a **projection**, not an authored field.

**Retire authored `edge_status` as source-of-truth.** A proposition-edge's displayed status becomes a
**derived projection** of: its proposition's **belief** (magnitude + contested + scalar) ×
**identification** × **lifecycle/freshness**.

**Decomposition of the MM30 legacy families:**

| MM30 legacy `edge_status` family | decomposes to |
|---|---|
| `supported` / `tentative` / `suggestive` / `partial` / `reduced` | derived **belief magnitude** |
| `falsified` / `refuted` / `null_after_adjustment` / `unsupported_current_vehicles` / `eliminated` | **disputing** evidence-lines → derived refutation (decisive-refutation rule) |
| `literature_strongly_supported` / `supported_observational_proxy` / `literature_supported_but_cross_section_null` | **identification** axis + **evidence_type** on the evidence-lines |
| `not_yet_tested` / `probe` / `closed` / `addressed` / `conditional` | **freshness / lifecycle** state (or task state) — not belief |
| `structural` / `absorbed` / `mixed` | **proposition-edge vs plumbing** distinction (`structural` → `claim_layer: structural_claim` where truth-apt) |

**Preserve `eliminated_by` semantics.** `eliminated` does **not** become a lost enum value. It becomes
an explicit **disputing/refutation evidence-line carrying the eliminating provenance** (the DAG
two-axis `eliminated_by` ref → a `cito:disputes` evidence-line with that provenance). The decisive-refutation
rule in `belief.py` (independent + strong + direct-test + whole-proposition) already caps belief accordingly;
the migration maps `eliminated`/`eliminated_by` onto that path so the provenance survives and the
refutation is *derived*, not asserted by a vanished label.

---

## 4. Resolving Issue 1 — single-dataset epistemic flow

1. **Make the evidence-line↔dataset link first-class and required** for empirical evidence-lines
   (`dataset_usage` mandatory; role + overlap recorded).
2. **Resolve `task → dataset`** for MM30: today `data_support` is task-keyed and tasks carry no
   structured dataset field (datasets appear only in prose). Provide a structured `task → dataset(s)`
   resolution (a task field and/or a resolution layer against the `mm30.v8.yml` registry) so each
   migrated evidence-line declares the dataset(s) it analyzed. (Detailed in `dataset-evidence-flow`.)
3. **Independence-aware aggregation** (B1/B2, already built) then automatically distinguishes *N
   independent datasets* from *N analyses of one dataset*. Consumers — including the paused web-app
   viewer — render real per-dataset breadth + derived belief, instead of counting task-keyed items as
   a dataset proxy.

---

## 5. The two facets & division of labour

**Shared spine — owned by this umbrella:** proposition (+ renderings), evidence-line, the one belief
engine, entity classes, patches, ladder, provenance axes. Both facets reuse these; neither forks a
parallel mechanism.

- **`epistemic-edges` (design + plan)** — the causal-DAG edge as a relational proposition's rendering
  (conforming to t034/D-005/D-006); proposition-edge vs plumbing; belief→edge projection;
  `edge_status` retirement + the §3 legacy-decomposition migration; `eliminated_by` → disputing
  provenance; ladder/identification on edges; edge rendering for consumers.
- **`dataset-evidence-flow` (design + plan)** — evidence-line↔dataset first-class/required;
  `task → dataset` resolution; `dataset_usage` authoring; independence surfacing; dataset-entity
  migration to the v3 `entities/datasets/` layout.

---

## 6. Scope & deliverables

Full end-to-end (per approved scope):
1. This umbrella design (SSOT).
2. `epistemic-edges` design + plan.
3. `dataset-evidence-flow` design + plan.
4. Framework implementation of the model changes (edge-as-proposition rendering, edge_status→derived,
   evidence-line↔dataset first-class, task→dataset resolution).
5. **Full MM30 corpus migration** — migrate all ~356 `*.edges.yaml` edges' `data_support[]` /
   `lit_support[]` items into evidence-line entities with resolved dataset links; create the dataset
   entities; retire authored `edge_status`.
6. A worked example that **re-grounds the paused web-app viewer** (Plan 3) on derived belief +
   per-dataset breadth.

---

## 7. Sequencing

- **Planning proceeds now.** All three docs **assume / require `layout_version: 3`** as the starting
  point (entities under `entities/<kind>/`; consumers read the compiled model). v2→v3 is being
  implemented in parallel.
- **Implementation is held** until v3 is confirmed in place.
- Suggested post-v3 order: framework model changes → MM30 corpus migration (edges + datasets) → web
  app resumes (Plan 3 re-grounded). The `epistemic-edges` work is substrate-orthogonal and can lead;
  `dataset-evidence-flow` leans on the already-merged dataset substrate and the v3 dataset-entity
  layout.

---

## 8. Consolidation map

| Doc | Relationship | What moves |
|---|---|---|
| `meta/specs/hypotheses/h00-working-model.md` | **reused authority** | conceptual model; this doc makes it precise |
| `meta/core/decisions.md` D-005 / D-006 | **reused authority** | t034-reuse + W3C-native substrate constraints |
| `docs/proposition-and-evidence-model.md` | **reused authority** | `claim_layer`, `identification_strength`, authored-vs-derived |
| `meta/doc/plans/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md` | **reused authority** | parent RFC (t022 extension contract) |
| t034 (`graph_object_type` / `epistemic_role` / payload / promotion) | **reused authority** | causal/edge-typing substrate — reused verbatim, untouched |
| DAG two-axis / rendering tooling (`dag-two-axis-evidence-model.md`, `dag/schema.py`) | **reused authority** | 5-value edge_status + identification; role → derived projection (§3) |
| `2026-05-22-evidence-aggregation-and-belief-design.md` (+ phase0/1 plans) | **superseded — folded** | evidence-line, belief engine, independence → §2.4–2.6 |
| `2026-05-24-evidence-aggregation-phase2-design.md` | **superseded — folded** | continuous log-odds scalar → §2.5 |
| `2026-06-06-knowledge-meta-model-and-substrate-design.md` (Part A only) | **superseded — folded** | epistemic-model consolidation → §2; Part B/C stays with substrate |
| `2026-05-03-epistemic-dependency-graph-design.md` | **superseded — folded** | entity classes + `bears_on` → §2.1, §2.7 |
| April layered-claims/causal-methodology predecessor (deleted during plans cleanup) | **superseded — folded** | claim_layer/identification axes → §2.2–2.3, §3 |
| `2026-03-16-claim-centric-uncertainty-design.md` (deleted during plans cleanup) | **superseded — folded** | claim-centric stance → §2.2, §2.5 |
| `docs/plans/historical/2026-04-17-edge-status-dashboard-design.md` | **predecessor (rendering)** | → `epistemic-edges` |
| `docs/plans/historical/2026-04-17-inquiry-edge-posterior-annotations-design.md` | **predecessor (rendering)** | posterior block → `epistemic-edges` |
| `docs/plans/historical/2026-04-19-dag-rendering-and-audit-pipeline-design.md` | **predecessor (rendering)** | → `epistemic-edges` |
| `2026-04-19-verdict-tokens-and-atomic-decomposition-design.md` | **predecessor (rendering)** | per-interpretation verdict join → `epistemic-edges` |
| `2026-05-26-bio-data-architecture-umbrella-design.md` | **predecessor (dataset)** | → `dataset-evidence-flow` |
| `2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` | **predecessor (dataset)** | → `dataset-evidence-flow` |
| A1/A2/B1/B2 dataset designs+plans | **predecessor (dataset)** | already-merged machinery → `dataset-evidence-flow` |

---

## 9. Risks & open questions

1. **Edge-as-proposition-rendering is a deep reconciliation.** Realizing a relational `proposition`
   as a t034 edge-as-node (one unit, edge is a view), while conforming to t034/D-005, is the
   highest-risk modeling move; the `epistemic-edges` design must show it rides t034 payloads (a
   projection/view), not a new structure — including whether the edge-node IRI is the proposition's
   own IRI or a `realized_as`-linked one.
2. **Legacy `task → dataset` resolvability.** MM30 tasks record datasets only in prose; some links
   will need manual curation against `mm30.v8.yml`. The migration must fail loudly where a dataset
   can't be resolved rather than silently dropping the grain.
3. **Corpus scale (~356 edges).** Migration of every `data_support`/`lit_support` item into
   evidence-lines is large; much is mechanical (item → evidence-line) but stance/strength/dataset for
   prose-only items need curation. Plan for subagent-driven execution with explicit no-silent-drop
   gates.
4. **Evidence-line authoring is net-new framework-wide** — no project has authored evidence-lines
   yet; MM30 will be the first real feeder of the built engine. Expect to surface engine gaps.
5. **Substrate timing coupling.** Implementation is gated on v3; the schedule depends on the parallel
   substrate migration landing and being confirmed.
6. **`structural_claim` vs plumbing boundary** must be drawn crisply per-edge during migration; a
   wrong call either inflates belief (plumbing treated as a proposition) or loses a real assertion
   (proposition treated as plumbing).
