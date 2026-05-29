# Bio Gene-Set / Annotation Resource Type (Pillar D)

Date: 2026-05-26

Status: approved; D1 collection type implemented, D2 promoted-member implementation deferred

Related (builds on):
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; this is its Pillar D
- `docs/plans/2026-05-26-reference-collection-member-promotion-design.md` — foundation primitive; D is its first concrete instance
- `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md` — Pillar B; D realizes per-set `dataset_usage`
- `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` — Pillar A; `source_class: reference`
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; `identifier_space`
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin (`origin`, `derivation`, `parent_dataset`)
- `science/model/src/science_model/schemas/extension-bio-*.json` — sibling bio extensions

---

## 1. Purpose & scope

Pillar D fills the "no gene-set data type" gap. It defines how a **collection** of gene sets / pathways /
signatures / annotations is typed, how each set's **identifier space** and **per-set provenance** are
recorded, and how an individual set becomes an evidence-bearing, citable object **without eagerly proliferating
entities** (the never-cited long tail stays collection rows). It is the realization of Pillar B's
provenance interface for gene sets, and the consumer of Pillar A's `reference` class and Pillar C's
identity layer.

**D is the first concrete instance of the reference-collection / keyed-member / promoted-member foundation
primitive** (`2026-05-26-reference-collection-member-promotion-design.md`). The collection→member→
promotion model, the resolve-or-`declared_unresolved` invariant (RCM-D2), the `member_of` derivation and
virtual-member rule (RCM-D5), and the equality-vs-compatibility guardrail (RCM-D6) are **inherited** from
the primitive; D fixes the member key to `set_key` and adds the gene-set-specific fields. The decisions
below are stated in those inherited terms.

**Locked decisions (this review):**

1. **Two granularities, one entity model.** A gene-set *collection* is a `dataset` + a `bio.geneset`
   extension. An *individual set* is, by default, just a **row of the collection addressed by `set_key`**
   (the qualified sub-reference, kept as an internal detail). It is **promoted to its own child `dataset`**
   (+ a `bio.geneset.member` extension) **only on demand**.
2. **Promotion trigger.** Promote a set **only when it becomes evidence-bearing** — it is cited by an
   evidence line (`source: dataset:<set-id>`) or needs independent provenance / review. Not eagerly.

This reuses the durable entity, provenance, `dataset_usage`, `source_class`, `parent_dataset`, freshness,
and evidence machinery rather than inventing a new entity kind before gene sets have a lifecycle distinct
from "a small dataset subset with provenance."

**Implementation boundary.** The first implementation plan is **D1 only**: the `bio.geneset`
collection extension, collection-level row contract, identifier-space declaration, and validate
check. D2's promoted-member model stays designed here but is not implemented until a real
evidence-bearing set needs a citable child dataset. This keeps Reactome/MSigDB-style collection
ingestion and B's gene-set provenance arm unblocked without forcing member promotion mechanics too
early.

**Explicit non-goals.** D does not build identity (C), the epistemic class (A), or the influence engine
(B). It does not ingest Reactome (E) — it is what E will instantiate against. The D1 plan also does not
add `bio.geneset.member`, new promotion commands, or virtual member payload resolution.

---

## 2. What exists, and the gap

The bio extensions cover matrices and tables (`bio.matrix`, `bio.table`, `bio.rnaseq`, …) but **nothing
represents a collection of sets**: no set count, no per-set membership keyed by identifier space, no per-set
source provenance, no way for one set to carry its own `dataset_usage`. Today a gene-set collection could
only be shoehorned into `bio.table`, losing exactly the structure (set membership, per-set provenance) that
the double-counting and circularity machinery needs.

---

## 3. Locked design decisions

### D-D1 — The collection: `dataset` + `bio.geneset`

A gene-set collection is a `dataset` (typically `origin: external`, `source_class: reference`) carrying a
`bio.geneset` extension. On top of the primitive's collection mechanism (RCM-D1), D adds **only** the
gene-set-specific fields:

- `n_sets`, set-size distribution summary
- `members_resource` — the Frictionless datapackage resource name for the collection's row table
- `identifier_space` — an object declaring the gene/protein identity tier and namespace the members are
  keyed in, **resolved through Pillar C** (for example `{tier: gene, namespace: hgnc_id, registry:
  dataset:gene-crosswalk-hgnc}`); enables the unsafe-join lesson to be enforced
- **per-set source provenance stored as cheap data columns** in the collection's bulk artifact (set_key →
  defining PMIDs / `dataset:` refs / canonical `dataset_usage` roles) — the "store fine" half of the
  policy; no graph cost until a set is promoted. D1 accepts the full canonical `dataset_usage` role
  vocabulary (`analyzed`, `set_definition_source`, `validation_source`, `cited`, `upstream`, `training`)
  so row provenance cannot drift from the dataset mixin; B's first circularity logic consumes
  `set_definition_source` and `validation_source`.
- the curation/skeptical marker inherited from A (`source_class: reference` by default; see D-D6 for
  heterogeneous collections)

### D-D2 — Unpromoted set: a collection row addressed by `set_key`

An individual set that has not been promoted is **not** an entity — it is the primitive's **keyed member**
(RCM-D2), addressed as `{collection, set_key}` and, where it must participate in provenance, referenced
*inside* a reified `sci:DatasetUsage` record (B-D4) with a set-key qualifier. A reference to a set by
`set_key` must resolve in the collection or carry `resolution_status: declared_unresolved` (RCM-D2). This keeps B's option-2 (qualified sub-reference)
as an internal detail and avoids minting entities for the long tail of never-cited sets.

### D-D3 — Promotion: an on-demand child dataset

When a set becomes evidence-bearing (D-D1's trigger), it is promoted to its **own child `dataset`** with a
`bio.geneset.member` extension. Promotion gives the set a **stable, citable id** — which B needs to say
"this specific set was defined from dataset A", and which evidence lines need for `source: dataset:<set-id>`.

### D-D4 — The promoted-member shape

```yaml
id: dataset:reactome-r-hsa-12345
type: dataset
origin: derived
source_class: reference            # copied from the per-set override; defaults to collection class (§4)
parent_dataset: dataset:reactome-v89
profiles:
  - science-entity-base/1.0
  - dataset/1.0
  - bio.geneset.member/1.0
derivation:                        # the member_of variant (primitive RCM-D5) — satisfies origin: derived
  kind: member_of
  parent_dataset: dataset:reactome-v89
  member_key: R-HSA-12345          # the gene set's set_key
dataset_usage:                     # per-set provenance B consumes
  - ref: dataset:study-a
    role: set_definition_source
    overlap: full
# bio.geneset.member extension:
identifier_space:
  tier: gene
  namespace: hgnc_id
  registry: dataset:gene-crosswalk-hgnc
n_members: 42
```

The member key and the collection link live in `derivation` (the `member_of` variant — canonical,
machine-checkable, RCM-D5), so the extension carries only the gene-set descriptors (`identifier_space`,
`n_members`).

**`source_class` and `derived_kind` on a member.** A member's `source_class` is **copied from the per-set
override, defaulting to the collection's class** (§4). In the common case it is `reference`, and A requires
`derived_kind` only when `source_class: derived` — so a `reference` member needs **no** `derived_kind`, the
curation down-weight applies, and there is no `derived_kind` tension. **But** a per-set override that makes a
member `source_class: derived` (an experimentally-derived set) **does** require `derived_kind`, per A.

### D-D5 — The `member_of` derivation variant (inherited from the primitive)

The `member_of` derivation variant is **defined by the foundation primitive** (RCM-D5): `derivation`
becomes a discriminated union on `kind`, and the `member_of` kind carries `parent_dataset` + `member_key`,
satisfying `origin: derived` for a promoted member that has no workflow. D consumes it with the gene set's
key as the `member_key` value:

```yaml
derivation:
  kind: member_of
  parent_dataset: dataset:reactome-v89
  member_key: R-HSA-12345          # the gene set's set_key
```

`set_key` survives as the **name of the collection's key column** (and, where useful, a descriptor on the
`bio.geneset.member` extension); the *derivation* uses the primitive's generic `member_key`. The rationale
the primitive locks — explicit, machine-checkable `origin: derived`, preferred over relaxing `derivation`
validation by profile (which would let `bio.geneset.member` silently weaken a core dataset invariant) or
mislabeling members as `origin: external` (they are not — we extracted them) — applies unchanged.

### D-D6 — Per-set provenance is the circularity substrate

The dangerous pattern (B §4) — *define a set from study A, then test enrichment of that set in study A* —
is detectable only if set-definition provenance is explicit. D guarantees it: the defining datasets of a
set are recorded as `set_definition_source` (in the collection's columns while unpromoted, on the member's
`dataset_usage` once promoted). B reads exactly this to raise `suspect-circular`. A set **validated** in an
independent cohort records `validation_source` instead — B's anti-circularity positive.

### D-D7 — Promoted members are virtual unless materialized (inherited from the primitive)

The virtual-member rule is **the primitive's** (RCM-D5), not D-specific; recorded here for completeness.
The dataset mixin **requires `datapackage`**. A promoted member must not force a fabricated tiny artifact
per set: a `member_of` dataset is a **virtual derived dataset** whose runtime payload is **resolved by
slicing `parent_dataset` on `member_key`** (here, the `set_key`) — the `datapackage` requirement is
satisfied by a virtual/derived descriptor pointing at that resolution, not by separate bulk bytes. A
member is materialized to its own artifact only when explicitly needed (e.g. an expensive or frozen
export). Without this rule, implementation would either fabricate many tiny datapackages or fail schema
validation.

---

## 4. Heterogeneous collections

A collection's `source_class: reference` is a **default**, not a straitjacket. MSigDB is the case: some sets
are hand-curated (`reference`), others are *derived from a specific experiment* (effectively
`set_definition_source`-heavy, closer to `derived`). D allows a **per-set source-class override** (stored in
the collection columns, carried onto a promoted member) so an experimentally-derived set is not given the
same curation treatment as a hand-curated one. The collection-level default covers the common case; the
override covers the mixed collection.

---

## 5. Stress-test recheck (against umbrella §5)

| Source | Collection | Notable |
|---|---|---|
| Reactome | `dataset` + `bio.geneset`, `source_class: reference`, `identifier_space: <C>` | the E instantiation; pathways promote to members on citation |
| MSigDB | `dataset` + `bio.geneset` | **heterogeneous** — per-set source-class override (D-D6); per-set PMIDs/`dataset_usage` feed B's circularity check |
| GO / MONDO (ontology) | *not a flat collection* | an ontology is a graph, not a set-of-sets; routed to the umbrella's non-tabular-reference question (matrix row 4) and C's deferred non-molecular identity — **out of D's flat-collection scope**, flagged not forced |
| A signature from one study | promoted member, `set_definition_source: study` | the circularity substrate (D-D6) |

D handles flat set collections cleanly and **explicitly declines** ontologies/knowledge-graphs (a distinct
shape), naming the gap rather than mis-modeling it.

---

## 6. Open items for review

1. **Per-set source-class override storage (D-D6/§4).** A column in the collection + a field on the
   promoted member, vs derived solely from per-set `set_definition_source` density. Recommendation:
   explicit field, defaulting to the collection's class (and copied onto the member, D-D4).
2. **Ontologies / knowledge graphs** (GO, MONDO, Open Targets graph) are **out of D's scope** — they need
   the non-tabular-reference treatment the umbrella parked and C's later non-molecular identity pillar. D
   only states the boundary.

---

## 7. Decomposition & phasing (within D)

| Sub-phase | Locks |
|---|---|
| D1 — `bio.geneset` collection extension (`n_sets`, `identifier_space`, per-set provenance columns, curation marker + per-set override) | the collection type; **implemented** |
| D2 — `bio.geneset.member` extension + on-demand promotion + the `member_of` derivation variant + the virtual-member rule (core-mixin changes) | the citable promoted set; **deferred until needed by evidence-bearing set citation** |

D depends on A (`source_class: reference`, the curation down-weight), C (`identifier_space`), and B
(`dataset_usage` + the `set_definition_source`/`validation_source` roles). Within Phase 3, D1 lands
before B's gene-set arm (B's per-set declarations attach to D's structures); D2 follows once evidence
lines begin citing individual sets.

---

## 8. Status & next step

Pillar D D1 is implemented: `bio.geneset` collections now have a schema profile, collection-row parser,
and `science validate` check for `set_key` uniqueness, row counts, set-size summaries, per-set provenance
row shape, and C-backed identifier-space declarations. D2 promoted members remain deferred until evidence
lines need to cite individual sets as child datasets.

Reactome can first instantiate as a collection with per-pathway provenance rows. Individual pathway
promotion can follow when evidence lines actually cite those pathways.
