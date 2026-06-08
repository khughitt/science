# Epistemic Edges — Facet Design

**Date:** 2026-06-08
**Status:** Design (planning only — implementation held until `layout_version: 3`, per umbrella §7)
**Kind:** Facet design. Elaborates the edge region of the umbrella
[`2026-06-08-epistemic-data-model-design.md`](./2026-06-08-epistemic-data-model-design.md).
**Sibling facet:** `dataset-evidence-flow` (owns the evidence-line↔dataset binding; see §9).

> **Authority boundary.** This facet is **subordinate to the umbrella**, which is itself subordinate
> to `h00` and beside the substrate. It reuses, without replacing: `h00`, `meta/core/decisions.md`
> D-005 (reuse t034 verbatim) / D-006 (W3C-native RDF/TriG, edge-as-node reification),
> `docs/proposition-and-evidence-model.md` (canonical `claim_layer` / `identification_strength` /
> authored-vs-derived), and the t034 causal/edge-typing substrate. Where this doc and a reused
> authority disagree, the authority wins.

---

## 1. The spine: three boundaries, one move

The whole facet rests on one structural move and one separation-of-boundaries.

**The move.** A truth-apt causal-DAG edge **is** a relational `proposition` — it is *not linked to*
one. This deletes today's parallel store (`*.edges.yaml`, which is rendered + staleness-audited but
never enters the knowledge graph or belief engine; `materialize.py` compiles evidence-lines, not
edges) rather than building a synchronization bridge across two stores.

**The boundaries** (the load-bearing abstraction):

| Boundary | Owns | Carries belief? |
|---|---|---|
| **Patch** | review / edit (graph-shaped authoring + audit) | no |
| **Proposition** | identity / belief (the truth-apt unit) | **yes (derived)** |
| **Evidence-line** | grounding (support / dispute provenance) | no (it *is* the grounding) |
| Generated DAG view | disposable projection | no |

No field outside proposition / evidence-line entities may affect belief.

### 1.1 Invariants (normative)

1. A truth-apt DAG edge **is** a relational proposition (subject · predicate · object +
   `claim_layer` + `identification_strength`). It is not linked to a separate proposition.
2. The relational proposition's **IRI is also its reified edge-node IRI** for rendering and patch
   membership. Belief and rendering address the *same* node — never split across two.
3. **Identity is per-claim, not per-pair.** Multiple relational propositions may share a
   `(subject, object)` pair (D-006 multi-edge semantics).
4. t034 typing (`epistemic_role`, `graph_object_type`) is **payload on the proposition**, not a
   second edge-identity system (D-005). No new edge vocabulary.
5. Evidence targets **only the proposition IRI**, via evidence-line entities and
   `cito:supports` / `cito:disputes`.
6. Belief is **derived exactly where it already is** — `belief.py` aggregating evidence-lines that
   target the proposition IRI (`belief.py:95–121`). The edge gets no belief mechanism of its own.
7. `edge_status` becomes only a renderer projection (`derived_edge_status`, §6); never authored,
   never consumed by the belief engine.
8. Non-truth-apt **plumbing edges are not propositions** and never receive belief.
9. `*.edges.yaml` is **retired as an epistemic source of truth**.

---

## 2. The relational proposition (data model)

A relational proposition's computational relation is **factored into orthogonal axes**. No single
field may secretly combine truth content, evidence status, causal role, identification strength, or
rendering behavior (this is the same anti-conflation discipline that motivates retiring `edge_status`).

```yaml
# relational proposition (conceptual shape; storage is the v3 entity layout)
id:                    proposition:<slug>          # entity-layer-owned identity; also the edge-node IRI
subject:               <canonical entity IRI>       # §3
predicate:             <controlled, sign-free>      # §2.1
object:                <canonical entity IRI>        # §3
polarity:              positive | negative | unsigned | not_applicable   # §2.2 — SOLE sign carrier
claim_layer:           empirical_regularity | causal_effect | mechanistic_narrative | structural_claim  # canonical
identification_strength: observational | longitudinal | interventional | structural   # canonical
epistemic_role:        <t034 verbatim taxonomy>      # D-005 — payload, not identity
measurement_model:     <proxy/latent wiring, optional>  # §3 — measurement is here, not in subject/object
legacy_relation_label: "<free text from legacy edge>"  # NON-computational, audit/display only
# belief, derived_edge_status, freshness: DERIVED — never authored
```

### 2.1 `predicate` — the one new controlled vocabulary

`predicate` names the **relation kind only** and is **sign-free** (sign lives in `polarity`, §2.2). It
is the single vocabulary this facet introduces; everything else reuses an existing authority. Seed set
(finalized empirically against the corpus during migration, §8):

`affects` · `regulates` · `associates_with` · `binds` · `is_proxy_for` ·
`induces_state` / `transitions_to` · `subtype_of` / `part_of`

All v1 predicates are **strictly binary**: `subject` and `object` are entity IRIs (§3). A `predicate`
value may later be **promoted to a first-class relation-type reference entity** (the umbrella's
deferred "relation-type entities" option) with no change to proposition identity or evidence
targeting.

**Graph roles are derived, not predicates.** `mediator` / `confounder` describe a proposition's
*position in a patch relative to a focal effect* (the `X→A→B→Y` topology), so they are **derived from
patch structure + the query**, never authored on the proposition. In v1 they are *always* derived.

**Higher-order mediation is deferred.** A claim where mediation/confounding is *itself* the assertion
("A mediates the effect of X on Y") is genuinely **n-ary** and does not fit the binary subject/object
shape. The clean extension — out of v1 scope — is a higher-order proposition whose `object` is an
**effect-proposition IRI** (since propositions are IRI-addressable, `object` could range over
proposition IRIs as well as entity IRIs). v1 does **not** mint `mediates_effect_of`; the corpus's
"mediator" relations are graph-roles (derived) rather than authored mediation claims. If a genuine
authored mediation claim surfaces during migration, it is a curation case escalated under this
extension, not silently coerced into a binary edge.

### 2.2 `polarity` — the sole sign carrier

Because `predicate` carries no sign, `predicate` and `polarity` cannot disagree — there is nothing to
reconcile. Validation binds the polarity domain to the predicate's sign-aptitude:

- sign-meaningful predicates (`affects`, `regulates`, `associates_with`) → `positive | negative |
  unsigned` (`unsigned` = effect exists, sign unknown / unspecified);
- sign-less predicates (`binds`, `is_proxy_for`, `subtype_of`, `part_of`) → `not_applicable`.

`polarity` is the renderer's hue channel (§6).

### 2.3 Reused axes — bound to canonical enums (anti-drift)

Three axes are owned by reused authorities; this facet **binds to them verbatim** and coins no
parallel names (a parallel vocabulary would be exactly the parallel system the umbrella forbids):

- `claim_layer` → `proposition-and-evidence-model.md` (`empirical_regularity | causal_effect |
  mechanistic_narrative | structural_claim`).
- `identification_strength` → `proposition-and-evidence-model.md` (`observational | longitudinal |
  interventional | structural`). The legacy DAG renderer's extra `none` maps to **absent /
  unspecified**, not a new value.
- `epistemic_role` → t034's verbatim taxonomy (D-005). Not a new `mediator/confounder/proxy` set.

### 2.4 Claim-edge vs plumbing (umbrella §2.3, applied)

The test is **truth-aptitude**, not the word "structural". A relational proposition is a
proposition-edge (belief-bearing) — including `claim_layer: structural_claim` (definitional /
benchmark / model-structure assertions are still claims). **Plumbing edges** — organizational links
(containment, grouping, patch membership) and measurement-model wiring — are **not** propositions and
never receive belief. A measurement *proxy assertion* ("X is a valid proxy for latent Y") is a
`structural_claim` proposition **only when proxy validity is itself under claim**; otherwise the
proxy is plumbing recorded in `measurement_model` (§3).

---

## 3. Node identity & resolution

`subject` / `object` are **canonical entity IRIs**, never the patch-local slugs used today
(`gain1q`, `pbx1`). Resolution is **semantic, not slug-keyed**: the corpus has one slug carrying
divergent meanings across patches (`mcl1` = "MCL1 dependency" *and* "MCL1 expression"; `prolif`
carries five labels), so slugs cannot be unified blindly.

**Kind sourcing — minimal, not a bio taxonomy.** This facet defines node-resolution *requirements* and
introduces only the **minimal missing reference-class node kinds** required to canonicalize endpoints:

- `construct` — latent scientific variable / state / process / abstraction that can be claimed about
  (e.g. *Proliferation* (latent), *Tumor burden*, *Cell-cycle state*, *PRC2 retargeting*).
- `outcome` — clinical / experimental endpoint being explained, predicted, modified, or measured
  (e.g. *PFS*, *OS*, *DOR*, *MRD-neg*).

Both are **reference-class** (same class as `gene` / `drug` / `pathway`): **no belief, no freshness**.
The proposition carries belief; the node is merely *what the proposition is about*. Reuse existing
kinds wherever possible (gene, gene-set / pathway / signature for multi-gene modules, drug,
cytogenetic-feature). Richer subtypes (`immune_state`, `evolutionary_state`, `treatment_regime`) are
**deferred** type-refinements under `construct` / `outcome` / existing bio kinds — not invented here.

**Construct, not proxy.** A causal endpoint is the **construct**, never a raw measurement proxy. The
claim is about *Proliferation* (latent), not *the proliferation score*. The proxy is recorded in
`measurement_model` (which readout measured the construct); a separate `is_proxy_for` `structural_claim`
proposition is minted **only** when proxy validity is itself asserted/tested. Migration does **not**
split all measured nodes into construct + readout pairs — only where a proxy claim is actually made.

**Resolution gates (loud-fail).** Every legacy node must resolve to **exactly one** canonical entity
IRI or migration fails. Failure modes that must halt for curation, not silently mint:

1. unresolvable slug (no canonical entity);
2. one slug with divergent labels/meanings across patches (the `mcl1` case);
3. measurement-vs-construct conflation that cannot be classified.

---

## 4. Patches, ladder, identification (reused from umbrella §2.7)

- **Patch** = a named-graph subgraph around a hypothesis/question (D-006). Relational propositions
  live in patches; the graph is a federated patchwork.
- **Patch membership is durable on the proposition / its named-graph**, never file-only (§5).
  Renderers query membership from entities, never from a workbench file.
- **Ladder L0–L4** + the **identification** axis are honest defaults L0–L2; L3–L4 are local and earned.
- **Provenance is orthogonal axes**, not one tier (`ProvenanceType`, dataset `source_class`, evidence
  `evidence_type`, PROV-O agent + `review_state` / freshness).

---

## 5. Authoring — the workbench contract

A causal patch is a graph-shaped object; humans must author and audit it as one. But the bulk
authoring surface must not become a second epistemic store. It is a **patch transaction / workbench**:
an editable normalized projection over the entity layer, kept honest by an idempotent compile cycle.

> **Canonical Rule.** The entity layer is the only durable epistemic store. A `<patch>.workbench.yaml`
> is an editable normalized projection over it; its committed form must **byte-equal** the canonical
> serialization produced by applying its own valid edits to the patch's proposition / evidence-line
> entities.

**The cycle:**

1. Developers may edit `<patch>.workbench.yaml`.
2. `compile` applies those edits to proposition / evidence-line entities — **minting proposition IDs
   for id-less rows** (the entity layer owns identity; the workbench may *request* but never *invent*
   it) and **lifting inline evidence stubs to evidence-line entities**.
3. `compile` rewrites `<patch>.workbench.yaml` into canonical form (id-less rows now carry minted IDs;
   evidence stubs now appear as evidence-line **references**, never substance).
4. **CI runs the same `normalize` on a non-mutating scratch graph and fails on any diff.** CI parses
   the committed workbench, applies its valid edits to an in-memory copy of the patch's entities,
   regenerates the canonical workbench, and diffs. The equality demanded is therefore "*the committed
   workbench is a fixed point of `normalize`*" — which a generator that ignores the workbench's
   proposed edits could not compute, and which never writes real entity files during a check. This
   permits id-less rows as legitimate **local, pre-compile** input while failing any **committed**
   drift.
5. Consumers never read the workbench for epistemic truth.

**Allowed fields:** stable proposition id/slug; `subject` / `predicate` / `object`; patch membership;
`claim_layer`; `identification_strength`; t034 payload (`epistemic_role`); inline evidence authoring
stubs that compile to evidence-line entities.

**Forbidden fields:** `edge_status`; authored belief; `posterior`-*as-status*; support arrays that
remain embedded after compile; anything the belief engine or renderer would consume directly instead
of consuming compiled entities. (A *quantitative* posterior result — effect estimate / interval / sign
probability — is legitimate **evidence substance**: it is authored only via an evidence stub that
lifts to an evidence-line entity and appears at rest as a reference, per §8 step 5 — never as edge
status on the proposition row.)

**Layout** (pixel positions, etc.) is non-epistemic presentation state and lives in a **sibling
disposable view/layout file**, never in the workbench (so the §5 round-trip stays a clean equality)
and never on the proposition entity.

**Name.** `<patch>.workbench.yaml` (signals "editable projection", not "authoritative graph store").
The legacy name `edges.yaml` is dropped — it carries the old, parallel-store mental model.

---

## 6. Projection & rendering

> Derived state is rendered as **orthogonal visual channels**. The old 5-value `edge_status` survives
> only as a compatibility/summary projection (`derived_edge_status`), never as authored data or
> canonical semantics.

**Primary runtime model — the orthogonal tuple, each on its own channel:**

| Axis | Source | Render channel |
|---|---|---|
| belief magnitude (`speculative < fragile < supported < well_supported`) | derived (`belief.py`) | intensity |
| `contested` (boolean) | derived | overlay |
| `(massed_support, massed_dispute)` + robustness band | derived (`belief_scalar.py`) | (detail panel / weight) |
| `polarity` | authored (§2.2) | hue |
| `identification_strength` | authored (§2.3) | line-style |
| freshness / lifecycle | derived (§7) | opacity / badge |
| `claim_layer` / t034 `epistemic_role` | authored payload | glyph / shape |

**The lossy summary.** `derived_edge_status ∈ {supported, tentative, structural, unknown, eliminated}`
plus `derived_edge_status_reason` (its basis). It is computed from the canonical fields by an ordered,
documented projection (first match wins; thresholds bind to `belief.py` magnitude bands):

1. **`eliminated`** — the decisive-refutation cap has fired (§7).
2. **`unknown`** — no evidence-lines, or only below-threshold ones (belief `speculative` with empty
   support); the edge exists as a drawn hypothesis but is `not_yet_tested`. **Ordered before
   `structural`** so an *ungrounded* `structural_claim` surfaces as `unknown`, never hidden behind a
   "structural" label (structural assertions are belief-carrying and must not escape summary filters
   just because they are definitional).
3. **`structural`** — `claim_layer == structural_claim` **and** it has grounding evidence (passed the
   `unknown` test); a scaffold/definitional assertion, flagged structurally regardless of magnitude —
   the channels still carry its real belief.
4. **`supported`** — belief magnitude ∈ {`supported`, `well_supported`}.
5. **`tentative`** — otherwise (belief magnitude ∈ {`speculative`, `fragile`} with some evidence).

`contested` is **not** folded into this ordinal — it remains a separate overlay channel (§6 table).
Precedence above is a pragmatic convenience for the coarse summary; it is explicitly lossy, and:

- **No** authored `edge_status`; **no** migration writes it into proposition entities; **no** belief
  engine consumes it.
- New renderers consume the orthogonal channels directly.
- A **legacy adapter** exposes `derived_edge_status` as bare `edge_status` *only at the boundary* where
  old `science dag` tooling requires that shape.
- Filtering prefers **axis-specific filters**; summary-status filters are convenience only.

This re-grounds the paused web-app viewer (its `hue × intensity × style` edge encoding is exactly the
channel set above) on **derived belief + per-dataset breadth** instead of an authored status string.

---

## 7. Lifecycle & elimination (derived, per "derive don't author")

**Lifecycle/freshness is derived, not an authored proposition field.** The legacy lifecycle families
(`not_yet_tested` / `probe` / `closed` / `addressed` / `conditional`) decompose into:

- **evidence-presence** — `not_yet_tested` / `unknown` = "a relational proposition exists (the edge is
  drawn as a hypothesis) but has zero or only weak evidence-lines" → derived, feeds
  `derived_edge_status: unknown`;
- **freshness/staleness** — reuse the framework's existing `review_state` / `last_reviewed` machinery
  (`freshness.py`); drives the opacity/badge channel; no new axis;
- **inquiry open/closed** — a property of the *question/task* investigating the proposition, **not**
  the proposition (a proposition does not "close"; the inquiry into it does). Surfaced as
  linked-question context.

There is **no authored `lifecycle` field**.

**`eliminated_by` → disputing evidence-line.** Each legacy `eliminated` / `eliminated_by` becomes a
`cito:disputes` **evidence-line carrying the eliminating provenance**. The existing decisive-refutation
rule in `belief.py` (independent + strong + direct-test + whole-proposition) caps belief; then
`derived_edge_status: eliminated` *derives* when that cap fires. No `eliminated` value is authored or
lost — it becomes refutation provenance + a derived summary.

---

## 8. Migration (design-level; gates that the `-plan` must enforce)

Scope: **~356 edges across 15 patches**, plus their `data_support` (task refs) and `lit_support`
(DOIs). Much is mechanical; the rest is curation forced by loud-fail gates. **No silent drops.**

Per-edge migration:

1. **Classify truth-apt vs plumbing** (§2.4). A wrong call either inflates belief (plumbing treated as
   a proposition) or loses a real assertion (proposition treated as plumbing) — gate for review.
2. **Resolve endpoints** (§3): each `source`/`target` slug → exactly one canonical entity IRI;
   loud-fail on unresolvable / ambiguous / construct-vs-proxy conflation.
3. **Decompose the relation** (§2): map the free-text `relation` (260 distinct strings) onto
   `predicate` + `polarity` + `claim_layer` + `identification_strength` + `epistemic_role`; retain the
   original as `legacy_relation_label`; **fail loudly on any string that does not decompose**.
4. **Lift evidence**: each `data_support` / `lit_support` item → an evidence-line targeting the
   proposition (`cito:supports` / `cito:disputes`), with `evidence_type` (canonical enum) + `stance` +
   `strength`. **Dataset binding (`dataset_usage`, `task → dataset` resolution) is the
   `dataset-evidence-flow` facet's responsibility** (§9). An **empirical** evidence-line whose
   `dataset_usage` is not yet resolved is created as a **migration staging artifact, excluded from the
   compiled graph and the belief engine** — `dataset_usage` is a precondition for *compiling* an
   empirical evidence-line, so the umbrella's mandatory-`dataset_usage` invariant always holds in the
   compiled graph and belief never aggregates ungrounded empirical evidence. Literature / expert
   evidence-lines (no dataset requirement) compile immediately.
5. **Preserve quantitative posterior payload**: the legacy `posterior` block (`beta`, `HDI`,
   `prob_sign`) is *fitted quantitative evidence*, not status. It migrates onto the relevant
   evidence-line as a **quantitative result** (effect estimate + interval + sign probability) feeding
   the continuous scalar-belief input (`belief_scalar.py` `massed_support` / `massed_dispute`), or onto
   a linked analysis/result artifact where the posterior is a separate fitted object. It is **not**
   dropped — only `posterior`-*as-authored-status* is (step 7).
6. **Map elimination** (§7): `eliminated` / `eliminated_by` → `cito:disputes` evidence-line + decisive
   refutation.
7. **Drop authored status only**: `edge_status` and `posterior`-*as-status* are not written into
   entities; they are derived (§6). This drops the authored **status interpretation**, never the
   quantitative posterior payload preserved in step 5.

Execution: subagent-driven, with the loud-fail gates as hard stops; mechanical items batched,
curation items surfaced explicitly.

---

## 9. Relationship to the `dataset-evidence-flow` facet

The two facets share the umbrella spine (proposition, evidence-line, the one belief engine) and divide
cleanly at the **evidence-line**:

- **`epistemic-edges` (this doc)** owns the proposition, its relation axes, node identity, the
  workbench, and the projection/rendering — and *creates* evidence-lines (stance, `evidence_type`,
  strength, target proposition) during migration.
- **`dataset-evidence-flow`** owns the evidence-line↔dataset binding: `dataset_usage` (mandatory for
  empirical evidence-lines), the `task → dataset` resolution against `mm30.v8.yml`, independence
  surfacing (A1/A2/B1/B2), and dataset-entity migration.

Sequencing (umbrella §7): `epistemic-edges` is substrate-orthogonal and can lead. Propositions and
literature/expert evidence-lines compile immediately; **empirical evidence-lines awaiting
`dataset_usage` are staged and excluded from the compiled graph/belief engine** (§8 step 4) until
`dataset-evidence-flow` resolves their dataset binding — at which point they compile and enter belief.
So proposition/evidence-line *creation* is never blocked, but empirical evidence never reaches belief
ungrounded; the mandatory-`dataset_usage` invariant holds in the compiled graph at all times.

---

## 10. Conformance summary

- **D-005:** t034 reused verbatim as the sole edge-typing substrate; `epistemic_role` /
  `graph_object_type` are payload on the proposition; no second edge vocabulary; `edge_status`
  retirement touches the **DAG rendering tooling**, not t034.
- **D-006:** the relational proposition's edge-node is an IRI in a named-graph patch (its own IRI,
  §1.1-2); multi-edges over a pair are distinct propositions (§1.1-3); content-addressed edge-node IRIs
  remain correct for derived/deduped plumbing (`bears_on`), not for authored assertions.
- **`proposition-and-evidence-model.md`:** `claim_layer` / `identification_strength` bound verbatim
  (§2.3); belief derived, never authored.
- **Umbrella:** one belief engine, one belief per proposition; datasets ground evidence-lines (one
  path); no parallel store (`edges.yaml` dissolved, not bridged).

---

## 11. Risks & open questions

1. **`predicate` coverage.** The seed set (§2.1) is validated only empirically against the 260 legacy
   strings during migration; expect to add a few kinds. The loud-fail gate prevents silent
   mis-mapping, but a too-coarse predicate set could push nuance into `legacy_relation_label` and lose
   it from reasoning. Review predicate coverage after the first patch is migrated.
2. **Construct/outcome minting discipline.** The minimal-kinds rule (§3) is only safe if migration
   resists minting a `construct` for every fuzzy node; ambiguous labels must become curation cases.
3. **Truth-apt vs plumbing per-edge** (§2.4) is the highest-judgment migration step; a wrong call is
   epistemically costly in both directions.
4. **Edge-node IRI = proposition IRI** must be confirmed against the v3 substrate's edge-as-node
   identity scheme (the umbrella's open substrate-adjacent question); if the substrate forces a
   content-addressed edge-node, this facet needs a `realized_as` shim — to be checked when v3 lands.
5. **Workbench round-trip fidelity.** Canonical serialization must be lossless over the workbench's
   scope (structure + references); comments / hand-formatting do not survive `compile` (accepted cost
   of drift-proofing).
6. **Cross-facet seam / staging discipline** (§9): empirical evidence-lines awaiting `dataset_usage`
   are staging artifacts the compiler must reliably **exclude** from the graph/belief engine until
   `dataset-evidence-flow` grounds them. The risk is a staging leak — a staged empirical evidence-line
   slipping into compilation ungrounded — so the compiler needs an explicit staged/excluded state and a
   validation gate that rejects empirical evidence-lines lacking `dataset_usage` from the *compiled*
   graph (they remain legal only as staging artifacts).
