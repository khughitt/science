# Bio Dataset Taxonomy & Epistemic Integration (Pillar A)

Date: 2026-05-26

Status: design ✓; impl: A1 merged (recording layer + validate check order 31); A2 merged (curation down-weight + config v2); Pillar A complete

Related (builds on):
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; this is its Pillar A
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C (A's first `reference` consumer)
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin (`origin`, `tier`, `derivation`)
- `docs/proposition-and-evidence-model.md` — evidence taxonomy (`evidence_type`)
- `docs/plans/historical/2026-05-22-evidence-aggregation-and-belief-design.md` — `evidence_type × evidence_role × strength`
- `docs/plans/historical/2026-05-24-evidence-aggregation-phase2-design.md` — numeric belief / log-odds
- `references/dag-two-axis-evidence-model.md` — `edge_status` × `identification`

---

## 1. Purpose & scope

Pillar A gives the epistemic machinery a way to tell **raw observational data** from **computed/derived
data** from **human-curated reference artifacts** (gene sets, ontologies, hand-curated DBs), so that
curated artifacts can be weighted more skeptically and non-independence is visible. It is the bridge
between the bio data layer and the belief math: A adds *one small dataset property* and specifies exactly
how it **composes into the aggregation machinery that already exists** — it does **not** build a parallel
scoring system.

**Locked decision (this review): small class + reuse the two-axis model.** The source/epistemic class is
deliberately minimal and concerns **independence and curation only**. The orthogonal "how causal is this"
dimension stays on the existing two-axis identification axis (the `identification_strength` field); A does
not duplicate it.

**Explicit non-goals.** A does **not** build identifiers (C), track dataset→consumer influence (B), define
the gene-set type (D), or ingest Reactome (E). It does not introduce new belief levels or a new
aggregation pass; it feeds the existing one.

---

## 2. What exists, and the gap

| Exists | Concerns | Why it is not enough |
|---|---|---|
| `origin: external \| derived`; `derivation.inputs` gated to `origin: derived` | *provenance* (did we make it in-pipeline?) | Says nothing about epistemic status — a curated ontology and a primary matrix are both `origin: external`; and an *externally-produced* derived artifact **cannot** record its inputs (A-D3) |
| `evidence_type` (`empirical_data_evidence`, `literature_evidence`, …) | the *evidence line* | A property of how a claim is argued, not of the dataset; must not be overwritten by a dataset's class (umbrella review) |
| Two-axis identification axis — `identification_strength` (`interventional \| longitudinal \| observational \| structural \| none`) | *causal identification* of an edge | Already owns the experimental-vs-observational distinction — A should route causal strength here, not into the class |
| Aggregation `evidence_type × evidence_role × strength`; independence collapse | weighting + double-counting | Has no input that says "this rests on a human-curated artifact, weight it skeptically" |

**The gap A closes:** a single dataset-level signal — *is this primary observation, a derivation, or a
curated reference?* — plus a precise rule for how that signal **modifies** (never replaces) the existing
weighting, so curated artifacts are down-weighted without being excluded (umbrella principle 1) and
without double-penalizing.

---

## 3. Locked design decisions

### A-D1 — `source_class`: a minimal epistemic class

A dataset-level enum, **orthogonal to `origin`**, with exactly three values:

| `source_class` | Meaning | Examples |
|---|---|---|
| `observational` | **Primary assay-derived signal** — one experiment's measurements, *including* the standard processing of that assay (reads → counts, intensities → calls, guides → dependency scores) | GTEx expression matrix, DepMap dependency scores, a CNV-call set, an scRNA count matrix, a patient cohort |
| `derived` | **Secondary synthesis** — integrates/transforms *multiple* upstream datasets, or is *model output*; **non-independent of its inputs** | a meta-analysis, a co-expression network, AlphaMissense (model output; A-D3) |
| `reference` | Human-curated knowledge / annotation | MSigDB, Reactome, GO, MONDO, curated UniProt annotation |

**The boundary that matters (review finding):** processing a *single* assay into its measurement matrix
does **not** make a dataset `derived` — that is still primary `observational` signal, or almost every
expression/CNV/scRNA matrix would be wrongly pushed into `derived` and trigger spurious independence
collapse. `derived` is reserved for artifacts that **synthesize across datasets or model them**.

The class is about **independence and curation**, nothing else. `origin` and `source_class` are different
questions: Reactome is `origin: external` **and** `source_class: reference`; a meta-analysis we computed is
`origin: derived` **and** `source_class: derived`; an externally-produced model output is `origin: external`
**and** `source_class: derived` — the case that needs the A/B provenance contract (A-D3).

### A-D2 — Causal strength stays on the two-axis identification axis (`identification_strength`)

The distinction the stress-test exposed — DepMap is observational data but *experimental/perturbational*
(a CRISPR knockout is an intervention) — is a **causal-identification** question, which the two-axis model
already owns. So:

- An evidence line built from perturbational data licenses `identification_strength: interventional`; one
  built from a cross-sectional cohort gets `identification_strength: observational`. This is set by the
  **analysis/edge**, not by the dataset's `source_class`. (The two-axis reference names this axis
  `identification`; the implemented entity/frontmatter field is `identification_strength` — same axis, and
  A always means the implemented `identification_strength` field when touching evidence-line metadata.)
- `source_class` therefore stays small and never encodes "how causal." DepMap is simply
  `source_class: observational`; its experimental nature shows up as stronger `identification_strength` on
  the edges drawn from it.

This is the whole point of the "small class + reuse two-axis" decision: two orthogonal axes, each owned in
one place.

### A-D3 — Model output is `derived` + `derived_kind: model_output`, and the external-derived provenance contract

Model predictions (AlphaMissense, a trained classifier's scores) are computed and **non-independent of
their training data**, so they are `source_class: derived` with `derived_kind: model_output` (vs
`aggregate`, `transform`).

**The provenance contract (review finding).** A-D4's independence collapse relies on knowing a derived
artifact's inputs. Today that lives in `derivation.inputs`, but the dataset schema **gates `derivation` to
`origin: derived`** and forbids it on `origin: external`. An externally-produced model output or
meta-analysis is `origin: external` (we did not produce it) yet `source_class: derived` — so it **cannot**
carry `derivation.inputs`. The fix is an origin-independent provenance record for *externally-produced*
derived/reference artifacts. Pillar B provides this as its unified **`dataset_usage`** object with
`role ∈ {upstream, training}` (model training data is `training`; a broad external dependency of unknown
precise role is `upstream`); A relies on that `{upstream, training}` projection rather than defining a
separate field. `derivation.inputs` stays for in-pipeline `origin: derived` datasets. Without this record,
AlphaMissense and external meta-analyses have no derivable independence — the contract that makes A-D4 work.

### A-D4 — The class is a modifier on evidence, never an `evidence_type` override

This is the load-bearing integration rule (and the correction from umbrella review):

- `evidence_type` keeps describing the **evidence line**. Enrichment of *your* data against a `reference`
  set is `empirical_data_evidence` (it is your data), *structured by a curated prior* — it is **not**
  remapped to `literature_evidence`. Remapping would contradict principle 1 and risk a double penalty.
- `source_class: reference` composes as a **bounded curation down-weight** applied **once, at the
  EvidenceUnit scoring layer** — mirroring the existing `PROXY_STEP_PENALTY` precedent in `unit_score`.
  Concretely: subtract **one ordinal score step, floored at zero**, from the unit's effective score, and
  route that same one-step discount through **both** the winner-selection path (`quality_key`,
  `science/src/science_tool/graph/belief.py`) **and** the scalar/log-odds path (`unit_score`,
  `science/src/science_tool/graph/belief_scalar.py`), so it lands **exactly once** in each. It **must not**
  mutate `stance`, `strength`, `evidence_type`, or independence grouping, and there is **no `strength` cap**
  (that would double-penalize). Landing this **bumps the belief config version**.
- When the curated artifact **is itself the basis** of the claim (e.g. "these genes are co-annotated in
  Reactome"), the edge additionally takes `identification_strength: structural` (definitional/proxy), which
  the two-axis model already treats conservatively.
- `derived` contributes through the **existing independence machinery**: a `derived` dataset is
  non-independent of its inputs — `derivation.inputs` for in-pipeline `origin: derived`, or `dataset_usage`
  (`role ∈ {upstream, training}`) for externally-produced ones (A-D3) — so lines resting on it and on those
  inputs collapse. No new collapse mechanism, just the provenance record that feeds it.

### A-D5 — A records, B and the aggregator consume

A's responsibility ends at *recording* the class (and subtype) on the dataset and *defining* the modifier
rule. Detecting that a `reference` set was **defined from** the same study it is then tested in (the
circularity case) is Pillar B's job, using the class A records plus the usage semantics B adds. A makes the
signal available; it does not itself trace influence.

---

## 4. Resolved decisions (review steer)

1. **Field home.** `source_class` lives on the **core dataset model/mixin**, not a bio extension — it feeds
   generic evidence aggregation, not bio-shape handling. `derived_kind` lives there too, **required only when
   `source_class: derived`**. The external-derived provenance record (A-D3) is Pillar B's `dataset_usage`
   (`role ∈ {upstream, training}`), also core and co-owned with B.
2. **Default flow.** `source_class` is **stored on the dataset**; the per-line curation modifier is
   **derived at graph build** into materialized evidence-unit metadata — authors do **not** copy it onto
   every evidence line. An explicit per-line **override** is allowed for exceptional cases and is
   **auditable** (recorded as an override, not a silent value).
3. **Down-weight.** One default curation penalty: **subtract one ordinal score step, floored at zero**,
   applied through the same unit-score path for both winner selection and the scalar (A-D4). **No `strength`
   cap.** **Bump the belief config version** when it lands.
4. **`derived_kind` vocabulary.** Start with `aggregate | transform | model_output`, **required only when
   `source_class: derived`**. No `assay_processed` value — processed primary matrices stay `observational`
   (A-D1 boundary).

---

## 5. Skepticism rationale (why a down-weight at all)

Gene sets, ontologies, and hand-curated databases are belief-biased, incomplete, and collapse dynamic,
context-dependent biology into a static snapshot (umbrella principle 2). The curation down-weight encodes
that they are a **weaker, more human-mediated** signal than a fresh independent measurement — *without*
zeroing them (principle 1: signal-weighting, not exclusion). A `reference`-structured empirical result
still counts as `empirical_data_evidence`; it just counts less, and more conservatively on the causal axis,
than the same result anchored on an independent primary dataset.

---

## 6. Stress-test recheck (against umbrella §5)

| Source | `source_class` | Causal axis (`identification_strength`) | Modifier |
|---|---|---|---|
| GTEx bulk RNA-seq | observational | observational | none |
| DepMap CRISPR | observational | **interventional** (perturbational) | none — experimental strength is on the causal axis, not the class |
| Meta-analysis we ran (e.g. MM30 SumZ) | derived (`origin: derived`) | inherited from inputs | independence collapse via `derivation.inputs` (existing) |
| AlphaMissense (external) | derived (`origin: external`, `derived_kind: model_output`) | typically `structural`/proxy | model-output skepticism; independence via `dataset_usage` `role: training` (A-D3) |
| MSigDB / Reactome / GO / MONDO | reference | `structural` when the set *is* the claim | curation down-weight (once) |
| UniProt curated annotation | reference | `structural`/proxy | curation down-weight |

All six land with **one small enum + the existing two-axis and independence machinery** — no special-casing,
which is the test the umbrella set.

---

## 7. Open items (deferred to other pillars)

1. **Where the curation marker lives for gene sets** is settled in D (per-set vs collection-level), since a
   collection can mix curated and experimentally-derived sets; A only sets the dataset-level default.
2. **External-derived provenance is B's `dataset_usage`** (A-D3): A needs the `{upstream, training}`
   projection for independence; B owns the field, its role semantics, and the influence index. Fixed in the
   B design, consistent with this contract.

(`observational` is kept **atomic**: finer nuance — experimental / longitudinal / cross-sectional — is the
`identification_strength` axis's job, not the class's. Settled by A-D1/A-D2.)

---

## 8. Decomposition & phasing (within A)

| Sub-phase | Locks | Status |
|---|---|---|
| A1 — `source_class` + `derived_kind` on the **core** dataset mixin + the A/B external-derived provenance contract (B's `dataset_usage` `role ∈ {upstream, training}`, full six-role schema shipped) + validation (`derived_kind` required for `derived`; `dataset_taxonomy` check at **order 31**) | the recorded signal + external-derived provenance contract | **merged** — landed at four layers: `mixin-dataset-1.0.json`, Pydantic `Entity` model (kind-gated `_validate_dataset_taxonomy`), `frontmatter.py` parse path, `DatapackageAdapter` whitelist; `science validate` check at order 31 |
| A2 — Wire the curation penalty into EvidenceUnit scoring (one ordinal step floored at 0 via the shared unit-score path — both winner-selection and scalar) + `identification_strength: structural` tendency for reference-as-basis; **bump belief config version** | the epistemic effect | **merged** — `CURATION_STEP_PENALTY = 1` applied as a full ordinal step (floored at 0) in `unit_score` (the scalar/log-odds path) and as a tiebreaker-only least-significant demotion in `quality_key` (Phase-1 `reduce_units` winner-selection); does NOT demote across the lexicographic `type/role/strength` tiers — a true cross-tier penalty would require flattening `quality_key` to a summed-step scalar (out of A2 scope); `sci:sourceClass` materialized on dataset entity URIs in the `knowledge` graph; `EvidenceUnit.is_reference_dataset` threaded by scanning `prov:wasDerivedFrom` objects against the reference-dataset URI set; `CONFIG_VERSION` bumped `belief-logodds-v1` → `belief-logodds-v2`; `identification_strength: structural` shipped as a **recording-only** `science validate` WARN nudge (`evidence.reference-basis-no-identification-strength`) — not wired into scoring; per-line curation override deferred (YAGNI) |

A1 depends on C only for the **`reference`-dataset pattern** (C's identity snapshots are the first
`reference` datasets, which validates the class on a real case). A2 depends on the aggregation internals
already built. A unblocks both B (which needs the class to reason about independence) and D (which needs the
curation marker for gene sets).

---

## 9. Status & next step

**A1 implemented and merged** to `~/d/science` `main`. The recording layer landed at four layers:
JSON mixin schema (`mixin-dataset-1.0.json`), Pydantic `Entity` model (+ kind-gated
`_validate_dataset_taxonomy` validator), the `frontmatter.py` parse path, and the
`DatapackageAdapter._ENTITY_FIELDS` whitelist (graph path). The full `dataset_usage` schema (all six
roles `analyzed|set_definition_source|validation_source|cited|upstream|training` + `overlap`
`full|partial|unknown`) shipped in A1 per the co-ownership decision, so Pillar B1 does not migrate a
partial field. A1 validates the `{upstream,training}` projection (the A-D3 external-derived
independence nudge). A new tolerant `science validate` check `dataset_taxonomy` shipped at **order
31** (the plan originally estimated order 29, but 29 was already taken by `evidence_lines`; actual
order is 31).

**A2 implemented and merged** to `~/d/science` branch `feat/a2-curation-downweight`. The curation
down-weight landed across the belief machinery:

- `CURATION_STEP_PENALTY = 1` applied as a **full ordinal step (floored at 0)** in `unit_score`
  (the scalar/log-odds path, `~/d/science/science/src/science_tool/graph/belief_scalar.py`) and as
  a **tiebreaker-only least-significant demotion** in `quality_key` (Phase-1 `reduce_units`
  winner-selection, `~/d/science/science/src/science_tool/graph/belief.py`). This realizes A-D4's
  "route through both paths": the scalar takes the full step; Phase-1 winner-selection takes it
  only as the least-significant tiebreaker. It does **not** demote across the lexicographic
  `type/role/strength` tiers — a true cross-tier penalty would require flattening `quality_key` to
  a summed-step scalar and is **out of A2 scope**.
- `sci:sourceClass` materialized on dataset entity URIs in the `knowledge` graph (`sci:sourceClass`
  predicate registered and written at graph build time).
- `EvidenceUnit.is_reference_dataset` threaded by scanning a line's `prov:wasDerivedFrom` objects
  against the reference-dataset URI set derived from `sci:sourceClass`.
- `CONFIG_VERSION` bumped `belief-logodds-v1` → `belief-logodds-v2`.
- `identification_strength: structural` shipped as a **recording-only** `science validate` WARN
  nudge (`evidence.reference-basis-no-identification-strength`, order 32) — NOT wired into scoring.
- Per-line curation override deferred (YAGNI).

**Pillar A is complete.** D (`bio.geneset`) and B (influence/provenance) designs are ready and
unblocked; B's paper arm and D can begin immediately.
