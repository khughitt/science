# Bio Data Architecture: Identity, Dataset Taxonomy, Gene Sets & Influence Tracking (Umbrella)

Date: 2026-05-26

Status: approved; implementation underway — foundation substrate + Pillar C sub-phases C1/C2/C3/C4a/C4b merged locally and C4c-1 rsID input implemented locally with full dbSNP artifact build/operator smoke pending + Pillar A (A1 + A2) merged and complete; Pillar D1, B1, B-migration, B2, and E (Reactome ingestion) merged locally; non-tabular reference modeling is partly resolved by `bio.reference_graph` RG1 with RG2+ pending; C4c transcript/protein projection and D2 remain open. Spawns focused per-area docs.

Related (builds on):
- `docs/proposition-and-evidence-model.md` — core reasoning model
- `docs/claim-and-evidence-model.md` — evidence edges, freshness
- `references/dag-two-axis-evidence-model.md` — `edge_status` × `identification`
- `docs/plans/2026-05-22-evidence-line-entity-phase0-plan.md` — evidence-line entity
- `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` — independence-aware aggregation
- `docs/plans/2026-05-24-evidence-aggregation-phase2-design.md` — numeric belief scalar
- `docs/plans/2026-05-21-provenance-propagation-contract-c-design.md` — `produced_by` / `bears_on`
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin
- `docs/plans/2026-05-23-store-decomposition-design.md` — commons store
- consumer context: `health/meta:doc/topics/large-scale-biological-datasets-landscape.md`,
  `health/meta:doc/plans/2026-05-25-reactome-commons-ingestion-design.md` (`~/d/health/meta`)

---

## 1. Purpose & scope

This is the umbrella design for the **bio-domain data layer** of the Science commons. It defines how
biological datasets are classified, how curated/reference artifacts (gene sets, ontologies) are
typed and *weighted*, how a dataset's downstream influence is tracked so signal is not double-counted,
and how gene/protein/variant identity and reference genomes are canonicalized so anything can join.

It exists because ingesting the first curated resource (Reactome) surfaced a set of decisions that
will be inherited by every later gene-set/reference resource. Rather than bake them into one
ingestion, we settle the architecture first, then instantiate.

**Explicit non-goal: this does not redesign the generic epistemic machinery.** Evidence lines,
independence-aware aggregation, belief derivation, provenance propagation, and the two-axis DAG model
already exist (§2). This document specifies the **bio-domain layer that plugs into them**, and where
that requires small, additive extensions to shared schemas, it says so and routes the detail to a
focused per-area doc (§6).

It spawns several design docs, each implemented in its own phase. The Reactome ingestion plan is the
*last* piece and is deferred until the areas it depends on land.

---

## 2. What already exists (build on, do not reinvent)

The framework has, in the last weeks, built most of the epistemic substrate this layer needs:

| Capability | Status | Where | What it gives us |
|---|---|---|---|
| Evidence-line entity | built (Phase 0) | `2026-05-22-evidence-line-entity-phase0-plan.md` | `stance`, `target`, `source` (`paper:`/`dataset:`/`data-package:`), `strength`, **`independence` (independent\|shared-source\|circular)**, `dispute_scope`; observability fields **`shared_dataset`/`shared_lab`/`shared_platform`/`shared_cohort`**; inherited `evidence_role`, `independence_group` |
| Independence-aware aggregation | built (Phase 1) | `2026-05-22-evidence-aggregation-and-belief-design.md` | collapses lines sharing an `independence_group`/`shared-source`; excludes `circular`; ordinal belief (`speculative<fragile<supported<well_supported`) + orthogonal `contested` flag; QA checks `independence.suspect-circular` (WARN), `independence.ungrouped-collapse` (ERROR) |
| Numeric belief scalar | built (Phase 2) | `2026-05-24-evidence-aggregation-phase2-design.md` | `(support_band, dispute_band)` pair + additive-log-odds net; suppressed when not robust |
| Provenance propagation | designed (Contract C) | `2026-05-21-provenance-propagation-contract-c-design.md` | `produced_by` (data→code), `prov:wasDerivedFrom` (data→finding), `bears_on` transitive closure + freshness; `consumed_by` dataset backlink (author-populated) |
| Two-axis DAG model | locked | `references/dag-two-axis-evidence-model.md` | `edge_status` (replication) × `identification` (causal id); `identification: structural` for definitional/proxy claims; conservative defaults (`unknown`+`none`) |
| Dataset mixin | built | `2026-04-19-dataset-entity-lifecycle-design.md` | `origin: external\|derived`, `tier`, `accessions`, `access`, `derivation{inputs,workflow,workflow_run}`, `parent_dataset`, `siblings`, `consumed_by`, `produced_by`; emergent logical role (input/intermediate/result) |
| Bio domain extensions | built | `science/model/src/science_model/schemas/extension-bio-*.json` | `bio.rnaseq`, `bio.scrna`, `bio.cna` (carry free-text `reference_genome`), `bio.matrix`, `bio.table` (`n_records`, typed `columns`) |

**The load-bearing observation.** Double-counting avoidance is *already* a first-class mechanism — but
it is **fed by hand**: an author must set `independence: shared-source`, assign an `independence_group`,
or fill `shared_dataset`/`shared_lab` for the collapse and the `suspect-circular` check to fire. There
is no automated way to discover that two supporting lines — one citing a paper, one citing a gene set —
ultimately rest on the *same* primary dataset. **Closing that gap is the spine of this layer**, and the
user's proposed mechanisms (a dataset→consumer map; declaring the `dataset:` entities a `paper` or
gene set consumes — reusing the existing `paper.datasets` ref, §4.3) are exactly what turns the manual
signal into a derived one.

---

## 3. Design principles

1. **Signal-weighting, not signal-exclusion.** A gene set / pathway / ontology is not zero-evidence.
   Significant enrichment of *your* data against a curated set is genuine (if indirect) evidence — and
   its **evidence type stays `empirical_data_evidence`** (it is your data), *structured by a curated
   prior*. The curated origin is a **modifier** on that line — a down-weight plus a structural/curated
   flag (§4.2) — **not** a reclassification to `literature_evidence`. What must be governed is **how
   much** and **how independently** the curated artifact counts, not **whether** it counts.
2. **Skepticism toward human-curated artifacts.** Gene sets, ontologies, and hand-curated databases are
   belief-biased, incomplete, and collapse dynamic, context-dependent biology into a static snapshot.
   They warrant a systematic down-weight and a `structural`/curated identification, distinct from a
   fresh empirical observation.
3. **Avoid double-counting; make non-independence queryable.** Independence is the property the belief
   machinery already keys on. The bio layer's job is to make *shared upstream sources* (datasets,
   papers) **derivable from the graph** rather than hand-tagged.
4. **Precise dataset-influence tracking is the north star.** Every dataset's flow — into papers, gene
   sets, derived datasets, observations, and propositions — should be a graph query: "what does this
   dataset influence?" and "do these two evidence lines share a dataset/paper ancestor?".
5. **Identity is the substrate.** Nothing joins, dedupes, or aggregates across datasets without
   canonical gene/protein/variant identifiers and explicit reference-genome/assembly versioning.
6. **Reproducibility over convenience for reference data.** Prefer pinned, versioned crosswalks and
   release-archived sources over live id-mapping services (consistent with the immutable-source rule
   already adopted for commons ingestion). Live services are discovery conveniences, not reproducibility
   handles.

---

## 4. The bio-domain layer — pillars

Each pillar below is summarized here and detailed in its own spawned design doc (§6). Pillar tags
(C/A/B/D/E) are used throughout for the dependency graph.

### 4.1 Pillar C — Gene/protein/variant identity, reference genomes & id mapping (foundational)

The deepest dependency: aggregation, dedup, and gene-set membership all require resolvable identity.

- **Reference-genome/assembly as structured, validated metadata.** Today `reference_genome` is free
  text on `bio.rnaseq`/`bio.cna` (so `GRCh37` and `hg19` do not unify). Promote it to a validated,
  canonical assembly identifier with known synonyms; make assembly mismatch a detectable condition.
- **Identifier crosswalks (pinned).** Canonical maps among HGNC symbol ↔ Entrez ↔ Ensembl gene ↔
  UniProt ↔ (where relevant) genomic coordinate/variant. Sourced from versioned, archive-durable
  releases (HGNC quarterly, Ensembl/BioMart release, NCBI) — **not** a live call to MyGene.info.
- **Service vs. pinned tension (decision in the C doc).** [refgenie/refgenieserver](https://github.com/refgenie/refgenieserver)
  is attractive for genome *assets* (assemblies, indices) and MyGene.info for id *queries*, but a live
  service is not a reproducibility handle. The C doc resolves how/whether to use them (e.g., refgenie
  for asset provenance; MyGene.info for interactive discovery only; pinned crosswalk snapshots as the
  authoritative join layer). This is the concrete realization of the landscape's "cross-resource
  identity graph, build first."
- **Cross-link:** this is the commons-side counterpart of
  `health/meta:doc/topics/large-scale-biological-datasets-landscape.md` shortlist #1.

### 4.2 Pillar A — Dataset taxonomy & epistemic integration

Extend the existing `origin` axis (which only splits `external|derived`) so the epistemic machinery can
tell raw observational data from curated reference artifacts and model output.

- **A source/epistemic class, orthogonal to `origin`.** A resolved `source_class` enum now lives on the
  dataset mixin: `observational` (primary assay-derived signal), `derived` (secondary synthesis or model
  output; requires `derived_kind: aggregate|transform|model_output`), and `reference` (human-curated
  knowledge/annotation — gene sets, ontologies, hand-curated DBs). Reactome and MSigDB are `reference`;
  an expression matrix or DepMap CRISPR dependency score matrix is `observational`; AlphaMissense is
  `derived` + `derived_kind: model_output`. Experimental/perturbational strength stays on the existing
  evidence-line `identification_strength` axis rather than becoming a fourth source class.
- **The class is a modifier, not an evidence-type override (review finding).** `evidence_type` is a
  property of an *evidence line* with a fixed taxonomy (`empirical_data_evidence`, `literature_evidence`,
  …) that the aggregator weights as `evidence_type × evidence_role × strength`. The source class must
  **not** rewrite that: enrichment of your data against a `reference` set is still
  `empirical_data_evidence` (principle 1), so mapping `reference → literature_evidence` would both
  contradict principle 1 and risk a *double* penalty if a curation down-weight is also applied. Instead
  the class composes as a **curated-prior modifier** on the line: `source_class: reference` reaches
  `EvidenceUnit.is_reference_dataset` through `sci:sourceClass` and applies `CURATION_STEP_PENALTY = 1`
  once in the scalar/log-odds path and as a tiebreaker-only winner-selection demotion. It does not cap
  `strength`, rewrite `evidence_type`, or zero the signal. `identification_strength: structural` is a
  recording-only validate nudge for curated/definitional edges.

### 4.3 Pillar B — Dataset-influence & provenance tracking (the north star)

Turn the currently-manual independence signal into a derived one, and make influence queryable.

- **Declarations at the source — reuse the existing ref, don't overload it (review finding).**
  `paper.datasets` *already exists* and takes `dataset:` refs (not raw accessions); raw `accessions`
  already live on the `dataset` entity. So a paper/gene-set declares the **`dataset:` entities it
  analyzes / was constructed from**, and external accessions resolve *through* those entities — one
  meaning per field. The canonical forward-provenance field is `dataset_usage` with `dataset:` refs.
  No raw unresolved-accession field is part of the implemented B1/B-migration surface; unresolved
  `dataset:` refs validate as review warnings until the dataset entity exists.
- **Declarations carry usage semantics, not bare links.** A link alone over-collapses: "analyzed as
  primary data" ≠ "cited as background" ≠ "used to *construct* the gene set" ≠ "used to *validate* it",
  and overlap can be partial. The declaration records a **usage role** (e.g. `analyzed` /
  `set_definition_source` / `validation_source` / `cited`) and, where known, overlap extent, so B can
  distinguish dependence that should collapse from mere co-citation that should not.
- **Derived influence + *candidate* auto-independence (user's mechanism 1).** `graph build` derives a
  dataset→consumer index and, via the existing `bears_on`/provenance closure, surfaces when two evidence
  lines rest on the *same* dataset entity. Crucially this is **not** an automatic collapse: a shared
  `dataset:` ancestor with **dependent** usage (e.g. `set_definition_source` on one side, the same data
  re-tested on the other) yields a derived `shared_dataset`/`independence_group` *candidate* that feeds
  the existing `independence.suspect-circular` **WARN**; a mere shared *citation* stays a flag for
  reviewer judgment. Auto-collapse to one effective unit happens only when direct dependence is
  established — the conservative reading of the existing aggregator, not a stronger one.
- **Builds on Contract C.** Extends `consumed_by` from author-populated to graph-derivable, and adds the
  reverse query ("what does dataset X influence?") over the closure.
- **Interface vs. realization (sequencing with D).** B defines the *minimal, entity-agnostic* provenance
  interface — `dataset:`-ref declarations + usage role + the derivation/closure logic. The **gene-set**
  realization of that interface (where a gene set's per-set source provenance lives, and whether an
  individual set is promotable) is D's job, so B's gene-set arm consumes D (see §6). B's paper arm needs
  only the existing `paper.datasets`.
- **Honest scope.** Full citation-ancestry de-duplication is hard; the B doc scopes what is derived
  automatically (declared `dataset:`-ref dependence) vs. what stays a flagged reviewer judgment
  (semantic / citation-chain overlap).

### 4.4 Pillar D — Gene-set / annotation resource type (`bio.geneset`)

A new domain extension (sibling to `bio.table`/`bio.rnaseq`/…), filling the "no gene-set data type" gap.

- **Schema.** Collection identity, set count, **identifier space** (resolved via C), per-set
  **source provenance** — `dataset:` refs (resolving accessions per B) and/or PMIDs — set-size
  distribution, and the curation/skeptical marker (from A). This is the gene-set realization of B's
  provenance interface.
- **Granularity policy (resolved earlier with the user): store fine, promote on demand.** Per-set source
  provenance lives as cheap data columns in the dataset; it is lifted into the epistemic graph
  (`prov:wasDerivedFrom` / independence edges) only when a specific set feeds a proposition.
- **Granularity decision.** The *collection* is a `dataset` + `bio.geneset`; an individual set remains a
  row addressed by `set_key` until it becomes evidence-bearing, then promotes on demand to a child
  `dataset` using the generic `derivation.kind: member_of` substrate. D1 implements the collection; D2
  still needs the gene-set-specific promoted-member extension/promotion path when evidence lines need it.
- **Circularity guidance to encode.** The dangerous pattern is *define-a-set-from-study-A then
  test-enrichment-in-study-A* (circular), not "Reactome + an independent cohort." The extension should
  make set-definition provenance explicit enough to detect that overlap via B.

### 4.5 Pillar E — Reactome ingestion (instantiation)

Reactome ingestion consumes A-D: it tags the collection as `source_class: reference` (A), carries the
implemented `bio.geneset` collection profile (D1), preserves row-level `dataset_usage` hooks for B, and
resolves Entrez membership through the built C2 HGNC gene crosswalk. **Status: implemented and merged
locally** in `~/d/science-commons`, `~/d/health/meta`, and `~/d/health/comparisons/pan-disease`; see
`docs/plans/2026-05-30-reactome-commons-ingestion-plan.md`.

---

## 5. Stress-test matrix

The architecture must not overfit to gene sets. Validate (on paper, not full implementation) against a
diverse set spanning the dimensions that stress it:

| Source | Epistemic class | Identifier space | Shape | Stresses |
|---|---|---|---|---|
| GTEx bulk RNA-seq | observational | gene (Ensembl/Entrez), one assembly | sample × gene matrix | baseline; `bio.rnaseq` + C assembly validation |
| DepMap CRISPR dependency | observational (interventional evidence lines) | gene + cell line (Cellosaurus) | cell-line × gene | non-sample keying; multi-id identity; causal strength stays on `identification_strength` |
| MSigDB | reference (heterogeneous) | gene (symbol/Entrez) | gene-set collection | the double-counting hotspot (some sets *derived from* experiments); per-set PMIDs → B; `bio.geneset` |
| Open Targets / GO / MONDO | reference | gene/disease/ontology terms | knowledge graph (non-tabular) | non-tabular shape; ontology ids; does the model handle graphs, not just tables? |
| AlphaMissense | derived (model output) | variant / genomic coordinate | per-variant table | model-derived (neither observational nor curated); assembly-dependent coordinates → C/liftover |
| UniProt / AlphaFold | reference | protein (UniProt) | per-protein | protein↔gene identity mapping (C) |

If the data model + epistemic mapping accommodate all six without special-casing, it generalizes.
Each per-area doc should re-check its decisions against this matrix.

---

## 6. Decomposition, dependencies & phasing

Spawned design docs (in `~/d/science/docs/plans/`), with the dependency order:

| Phase | Doc | Depends on | Locks | Status |
|---|---|---|---|---|
| 1 | Identity, reference genomes & id mapping (C) | — | canonical assembly + gene/protein/variant crosswalks; pinned-vs-service policy | design ✓; **impl: C1 (assembly), C2 (gene), C3 (protein), C4a (variant identity), and C4b (liftover/compatibility) merged locally; C4c-1 rsID input implemented locally; full dbSNP artifact build/operator smoke and transcript/protein projection pending** |
| 2 | Dataset taxonomy & epistemic integration (A) | C | `source_class` + `derived_kind`; curation down-weight as a *modifier*, mapped into aggregation + two-axis | design ✓; **impl: A1 + A2 merged** (recording layer + curation down-weight, config v2); **Pillar A complete** |
| 3a | Gene-set / annotation type `bio.geneset` (D) | A, C | extension schema; per-set provenance; promotion rule; realizes B's interface for gene sets | design ✓; **impl: D1 collection type implemented; D2 promoted members pending** |
| 3b | Dataset-influence & provenance tracking (B) | A, C (+ D for the gene-set arm) | `dataset:`-ref declarations + usage role; dataset→consumer derivation; *candidate* auto-independence | B1 implemented locally; B-migration implemented; **B2 merged locally** |
| 4 | Reactome ingestion revision (E) | A-D | first instantiation | **implemented and merged locally**; plan/status in `docs/plans/2026-05-30-reactome-commons-ingestion-plan.md` |

C is the long pole (everything joins on identity). A and C unblock D and the paper arm of B; B's
gene-set arm consumes D, so D leads B within Phase 3 (B may start its paper-side and the derivation
engine in parallel, deferring the gene-set declarations until D's collection schema lands). E lands
last. Each doc is independently implementable and reviewable.

**Foundation primitive (cross-pillar).** C's assembly registry and D's gene-set collection turn out to
share one model — *reference collection → keyed member → promoted member* — defined once in
`docs/plans/2026-05-26-reference-collection-member-promotion-design.md` and consumed by both (and by the
C2/C3 crosswalks and the C4 variant-label registry). D is its **first concrete instance**, not its parent:
the mechanism is the generalization of D's collection/member/promotion, so it is settled alongside C/D
rather than as a separately-numbered phase. See that doc for the model and its invariants (resolve-or-
`declared_unresolved`; `derivation.kind: member_of`; exact-key-equality-is-identity vs. compatibility
relations). **Status: implemented and merged** (the generic substrate — `commons/member.py`,
`member_of` schema variant, reference-collections check); C1's assembly registry, C2's gene crosswalk,
and C3's protein crosswalk are its first three keyed-member instances. C4b now exercises its guardrail-2
*compatibility relation* side: distinct seqcol digests are related with pinned liftover provenance, never
collapsed into identity.

---

## 7. Resolved decisions and remaining open design

1. **Resolved (A): class field name & home.** `source_class` and `derived_kind` live on the core dataset
   mixin/model. The per-line curation effect is derived from the dataset's graph-materialized
   `sci:sourceClass`; a per-line override remains deferred/auditable rather than part of A1/A2.
2. **Resolved (A): curation down-weight.** `source_class: reference` applies one bounded ordinal step
   (`CURATION_STEP_PENALTY = 1`) in the scalar/log-odds path and a tiebreaker-only demotion in
   winner-selection. It does not cap `strength` or rewrite `evidence_type`; `identification_strength:
   structural` is a recording-only validate nudge.
3. **Resolved (A): enum breadth.** `source_class` is `observational|derived|reference`; `derived_kind` is
   `aggregate|transform|model_output`; experimental/perturbational strength stays on
   `identification_strength`.
4. **Resolved (B): unresolved accessions.** The canonical record is `dataset_usage.ref: dataset:<slug>`.
   External accessions resolve through dataset entities. Missing dataset refs produce review warnings; no
   raw unresolved-accession field has been added.
5. **Resolved and implemented (B2): scope of derived independence.** B2 commits aggregation-affecting
   shared-source metadata only for direct, full-overlap dataset dependence. Partial/unknown, cited,
   validation-only, virtual gene-set member, or `bears_on`-only paths become candidate/review signals.
6. **Resolved; D2 implementation open (D).** A gene-set collection is a `dataset` + `bio.geneset`; a set
   promotes on demand to a child `dataset` when evidence-bearing. The generic `member_of` substrate is
   implemented; the gene-set-specific promoted-member path remains deferred until needed.
7. **Resolved (C): pinned vs. live identity.** Pinned local snapshots are authoritative for joins. Live
   services are discovery/QA conveniences only; refgenie/refgenieserver may document genome asset
   provenance but not replace pinned identity inputs.
8. **Partly resolved (non-tabular references).** `bio.reference_graph` RG1 and RG2 are implemented for pinned graph-shaped reference datasets:
   RG1 validates node indexes, and RG2 resolves promoted graph-member virtual payloads as node rows plus
   directly incident edges. Real GO/MONDO/Open Targets recipes, broader graph-member promotion workflows,
   unpromoted-member B materialization, and non-molecular identity resolvers remain follow-up work.

---

## 8. Status & next step

**Approved; implementation underway.** The umbrella and all spawned per-area design docs are written and
user-reviewed. The cross-pillar **foundation substrate** (reference collection → keyed member → promoted
member) and **Pillar C sub-phases C1 (assembly registry), C2 (gene crosswalk), C3 (protein crosswalk)**
and C4a (variant identity) are implemented and merged locally in `~/d/science`. Each shipped its
schema(s), a pinned reference collection + recipe, a pure resolver, and the corresponding
`science validate` checks; the C2 gene check was generalized into a shared
`evaluate_tier_identity` that C3's protein check reuses.

**Remaining — Pillar C.** C4a variant identity (VRS 2.0 / SPDI) is merged. C4b is implemented: pinned
cross-assembly liftover chains, seqcol *compatibility relations* (the first realization of the primitive's
RCM-D6 guardrail-2), lifted target-assembly VRS reminting, and the C1 check-3 liftover remedy are in
place. The implementation plan is tracked at `docs/plans/2026-05-31-c4b-cross-assembly-liftover-plan.md`.
C4c-1 rsID input over pinned dbSNP snapshots is implemented locally in `~/d/science` and
`~/d/science-commons`; the full dbSNP archive fetch/build, lockfile pinning, datapackage hash refresh, and
resolver smoke against the real artifact remain operator-pending. Transcript and protein projection inputs
over pinned snapshots remain later C4c work.

**Pillar A — A1 + A2 merged; Pillar A complete.** A1 (`source_class` / `derived_kind` /
`dataset_usage` recording layer) landed on `~/d/science` `main`: JSON mixin schema
(`mixin-dataset-1.0.json`), Pydantic `Entity` model (kind-gated `_validate_dataset_taxonomy`),
`frontmatter.py` parse path, and `DatapackageAdapter` whitelist; full six-role `dataset_usage`
schema shipped (so B1 does not migrate a partial field); `science validate` check `dataset_taxonomy`
at **order 31**. A2 (curation down-weight) landed on branch `feat/a2-curation-downweight`:
`CURATION_STEP_PENALTY = 1` applied as a full ordinal step in `unit_score` (scalar/log-odds path)
and as a tiebreaker-only demotion in `quality_key` (Phase-1 winner-selection); `sci:sourceClass`
materialized in the `knowledge` graph; `EvidenceUnit.is_reference_dataset` threaded from
`prov:wasDerivedFrom`; `CONFIG_VERSION` bumped to `belief-logodds-v2`; `identification_strength:
structural` shipped as a recording-only validate nudge (not scored); per-line override deferred.

**Remaining — other pillars.** D has D1 implemented: the `bio.geneset` collection profile,
row-contract parser, validate check, graph retention guard, and B1 row-level usage materialization are in
place. The generic `member_of` substrate is also implemented, but D2's gene-set-specific promoted-member
extension, promotion path, and virtual member payload resolution remain deferred until evidence lines need
first-class child datasets for individual sets. B1 is implemented locally as the authored-to-graph
provenance layer, B-migration is implemented (`science graph migrate-paper-datasets` plus pure/CLI tests),
and B2 is implemented as the dataset-derived independence layer
(`science_tool.graph.dataset_independence`, graph materialization, validation integration, aggregation
metadata merge, and `belief-logodds-v3`). Pillar A is complete; C (C1-C3 merged, C4a merged, C4b
merged locally, C4c-1 rsID input implemented locally), D1, and B1/B2 are now exercised by E. Reactome is implemented as the first real
`bio.geneset` commons dataset: Reactome release 96 was fetched from the versioned Reactome download URL,
the C2 HGNC gene crosswalk was built, `dataset:reactome` was promoted into `~/d/science-commons`, and the
pan-disease local Reactome stub was removed so consumers resolve through commons. D2 remains deferred
until a real evidence line needs a promoted pathway dataset. `bio.reference_graph` RG1 and RG2 are
implemented locally for pinned graph-shaped reference datasets: RG1 validates node indexes, and RG2
resolves promoted graph-member virtual payloads as node rows plus directly incident edges. Real
GO/MONDO/Open Targets recipes, broader graph-member promotion workflows, unpromoted-member B
materialization, and non-molecular identity resolvers remain follow-up work.

**Operational follow-ups.**
- Push local implementation branches to `origin` when ready.
- `gene-crosswalk-hgnc` is now built and pinned in `~/d/science-commons`; `assembly-registry` and
  `protein-crosswalk-uniprot` may still need their real artifact builds if downstream work requires
  non-placeholder data.
- Reactome and C2 gene-crosswalk bulk CSVs were rebuilt/copied under durable local storage at
  `~/d/science-commons-data`, and the per-machine `reactome` and `gene-crosswalk-hgnc` data overrides
  now point at those directories.
- C3 left three deferred minor review findings (a `parse_secondary` skip-vs-fail-early comment; an
  untested `fetch_text` gzip branch; a docstring nicety).
