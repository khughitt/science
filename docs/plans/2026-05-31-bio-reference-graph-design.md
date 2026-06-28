# Bio Reference Graph Resource Type

Date: 2026-05-31

Status: RG1, RG2, and RG4 implemented; real recipes built — `dataset:mondo` (pushed to origin) and `dataset:go` from pinned OBO Graph JSON, plus the first association graph `dataset:opentargets-associations` (Open Targets 25.12 overall-direct, Model A); RG3 and RG5 pending

Related:
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; RG1 partly addresses its non-tabular-reference open item
- `docs/plans/historical/2026-05-26-reference-collection-member-promotion-design.md` — foundation primitive; graph nodes/associations are keyed members
- `docs/plans/historical/2026-05-26-bio-geneset-type-design.md` — flat set collections; this design is the sibling for graph-shaped references
- `docs/plans/historical/2026-05-26-bio-dataset-influence-provenance-design.md` — Pillar B; graph/member provenance feeds dataset influence
- `docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` — Pillar A; reference graphs are `source_class: reference`
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; non-molecular identity resolution is a later consumer
- `science/model/src/science_model/ontologies/` — lightweight ontology catalogs; related but not the data-artifact layer

---

## 1. Purpose and scope

The bio umbrella intentionally left GO, MONDO, Open Targets, and similar resources out of
`bio.geneset`: they are not flat set collections. They are graph-shaped reference artifacts with typed
nodes, relations, provenance, deprecated/replaced terms, and sometimes association evidence. This design
adds the missing sibling resource type: a pinned commons dataset profile for **non-tabular reference
graphs**.

The core decision is:

> A graph-shaped reference resource is a normal `dataset` with `source_class: reference` plus a new
> `bio.reference_graph` extension. Its terms, nodes, and association records are keyed members of the
> pinned graph artifact. They promote to child `dataset` entities only when an evidence line or review
> workflow needs a citable member.

This design starts with the data-artifact model, not non-molecular identity resolution. Disease, ontology,
cell-line, tissue, and association identity resolvers can consume this substrate later. The first
implementation should prove schema, parsing, validation, graph-member resolution, and provenance hooks
with tiny fixture artifacts; the real MONDO, GO, and Open Targets recipes (`dataset:mondo`, `dataset:go`, `dataset:opentargets-associations`) are now implemented.

Explicit non-goals:

- Do not replace the existing `science_model.ontologies` catalog system.
- Do not build full GO, MONDO, or Open Targets ingestion in the first increment.
- Do not add live ontology-service calls to reproducible validation or graph builds.
- Do not force graph resources into `bio.geneset` or `bio.table`.
- Do not implement broad non-molecular identity resolution in this phase.

---

## 2. Existing layers and the gap

Science already has three nearby layers:

1. **Ontology catalogs in code** (`science_model.ontologies`). These register entity kinds,
   predicates, CURIE prefixes, and non-blocking suggestions. They are lightweight model vocabulary.
2. **Imported/distilled graph snapshots** (`science graph import`, `science distill`). These can add
   Turtle snapshots to a project graph, but they do not make the source a commons dataset with access,
   hashes, source class, or dataset-usage provenance.
3. **Reference collections** (assembly registry, crosswalks, Reactome). These are pinned commons
   datasets with keyed members and optional promotion, but existing concrete profiles are table-shaped.

The missing layer is a **pinned, graph-shaped commons reference dataset**. A resource like MONDO should
be able to say: this release is a `dataset`, these files are hash-pinned, these prefixes and member keys
are valid, these nodes/edges are the addressable members, this upstream source built it, and a specific
member can later become an evidence-bearing child dataset.

---

## 3. Locked design decisions

### RG-D1 — `bio.reference_graph` is a dataset extension

A reference graph is a `dataset` with:

```yaml
id: dataset:mondo
type: dataset
origin: external
source_class: reference
tier: use-now
profiles:
  - science-entity-base/1.0
  - dataset/1.0
  - bio.reference_graph/1.0
datapackage: datapackage.yaml
graph_resource: mondo.nt
member_key_space:
  kind: curie
  prefixes: [MONDO]
  resolution_status: resolved
node_index_resource: nodes.csv
edge_resource: edges.csv
```

The extension is deliberately about graph-shaped reference data, not just ontologies. GO and MONDO fit as
term graphs. Open Targets may fit later as an association graph whose members include disease, target, and
association keys, but that fit is unproven until an association graph is the implementation target. The
first schema should avoid ontology-only field names where a more general graph term is clearer, while RG1
validates only term-graph fixtures.

### RG-D2 — Graph members are keyed members, not eager entities

Each addressable graph member is keyed within the parent dataset. Common key shapes:

| Resource style | Member key |
|---|---|
| GO term graph | `GO:0006915` |
| MONDO disease graph | `MONDO:0005148` |
| Open Targets association graph | a stable association id or deterministic tuple key |
| Mixed RDF graph | canonical IRI or compact CURIE |

The key is the member identity within that release. In RG1, a member row in the required node index is
the cheap addressable form; a promoted child `dataset` is only minted on demand through
`derivation.kind: member_of`.

Exact key equality is identity inside one release. Cross-release replacement, obsoletion, xref,
equivalence, or close-match assertions are relations between distinct keys, not key collapse.

### RG-D3 — Promotion uses the existing `member_of` substrate

A promoted graph member is a child `dataset`:

```yaml
id: dataset:mondo-0005148
type: dataset
origin: derived
source_class: reference
parent_dataset: dataset:mondo
profiles:
  - science-entity-base/1.0
  - dataset/1.0
  - bio.reference_graph.member/1.0
datapackage: virtual:member-of
derivation:
  kind: member_of
  parent_dataset: dataset:mondo
  member_key: MONDO:0005148
member_kind: term
label: multiple myeloma
status: active
```

The required dataset payload is virtual by default: resolve the member by slicing the parent reference
graph on `derivation.member_key`. For graph members, the default slice is the node-index row plus
directly incident edges in the normalized edge resource. Transitive closure, ontology entailments, and
neighborhood expansion are later adapters with their own pinned outputs. A separate artifact is created
only if a workflow needs a frozen materialized export.

Promotion triggers match the foundation primitive:

- evidence-line citation (`source: dataset:<member>`);
- independent per-member provenance or review state;
- materialized asset packaging;
- lifecycle state that must differ from the parent graph.

### RG-D4 — Keep ontology catalogs and reference graphs separate

`science_model.ontologies` remains the code-shipped vocabulary layer:

- register known entity kinds and relation predicates;
- map CURIE prefixes to domain suggestions;
- support authoring and UI affordances.

`bio.reference_graph` is the data layer:

- pins a concrete external release;
- validates artifact shape and member keys;
- records source/access/hash/provenance metadata;
- provides member resolution and promotion hooks.

The biology ontology catalog may say that `MONDO` CURIEs are disease identifiers. The MONDO reference
graph dataset says which `MONDO` terms exist in release X, whether a term is obsolete, what it replaced,
and what upstream sources built the artifact.

### RG-D5 — Provenance lives at both graph and member granularity

Dataset-level `dataset_usage` records upstream resources used to build or curate the graph:

```yaml
dataset_usage:
  - ref: dataset:mondo-upstream-ordo
    role: upstream
    overlap: partial
  - ref: dataset:mondo-upstream-hpo
    role: upstream
    overlap: partial
```

Member-level provenance should remain in cheap graph-side data until a member is promoted. The node index
or edge metadata resource may carry JSON `dataset_usage` entries per member, using the same role and
overlap vocabulary as the dataset mixin. When a member is promoted, that per-member usage becomes normal
dataset-level `dataset_usage` on the child.

B can then derive influence/circularity from graph members the same way it does for gene-set rows:
unpromoted members can materialize virtual usage records; promoted members can materialize ordinary
dataset usage records.

### RG-D6 — Deprecation and replacement are first-class member state

Reference graphs commonly carry obsolete terms, merged terms, and replaced terms. The model must not
silently resolve through them. The first member index should support at least:

- `member_key`
- `member_kind`
- `label`
- `status`: `active | deprecated | withdrawn`
- `replaced_by` as a semicolon-delimited list or JSON array of member keys

Validation flags deprecated or withdrawn members when they are referenced or promoted. It may suggest
`replaced_by`, but it must not rewrite the key automatically.

Cross-key assertions such as `xref`, `equivalent_to`, and `close_match` are graph edges, not node-index
columns. They are RCM-D6 compatibility/equivalence relations between distinct keys, so keeping them in
`edge_resource` avoids inviting consumers to treat a node-row column as identity collapse.

For OBO-style ontologies, the recipe maps source lifecycle terms into this compact lifecycle axis:
`owl:deprecated true` and "obsolete" terms map to `status: deprecated`; `IAO:0100001` ("term replaced
by") maps to `replaced_by`; source-specific `consider` relations remain explicit edges. This lifecycle
`status` is separate from `member_key_space.resolution_status`, which describes whether the key space is
validated against a registry.

### RG-D7 — Graph artifacts are pinned; graph import is an adapter, not the model

The graph resource may be RDF (`.ttl`, `.nt`, `.trig`), JSONL edge records, or another explicitly
declared graph format. The commons dataset pins the artifact with the normal datapackage hash. A graph
importer may load the graph into a local RDF store, but that import is an adapter over the pinned
dataset, not the source of truth.

The first implementation should support a small, explicit set of formats:

- `rdf_turtle`
- `rdf_ntriples`
- `jsonl_edges`

For `jsonl_edges`, `graph_resource` is the edge artifact. `edge_resource` is only needed when a distinct
normalized projection is produced from another graph format such as RDF.

Additional formats can be added when a real resource requires them.

---

## 4. Proposed extension shape

### `bio.reference_graph/1.0`

Minimum fields:

```yaml
graph_resource: graph.nt
graph_format: rdf_ntriples
member_key_space:
  kind: curie
  prefixes: [GO, MONDO]
  resolution_status: resolved
node_index_resource: nodes.csv
edge_resource: edges.csv
member_count: 49231
edge_count: 184205
```

Field intent:

| Field | Purpose |
|---|---|
| `graph_resource` | Datapackage resource holding the graph artifact |
| `graph_format` | Parser/import contract for the graph artifact |
| `member_key_space` | Declares how addressable members are keyed |
| `node_index_resource` | Required RG1 table for fast member lookup and status checks |
| `edge_resource` | Optional normalized edge table for validation/query summaries |
| `member_count` | Expected addressable node/member row count, including deprecated/withdrawn rows |
| `edge_count` | Expected edge count, when cheaply knowable |

`node_index_resource` is required for RG1. Without it, the existing keyed-member resolution helper can
only report unknown membership, so promotion checks and count validation become vacuous. A bare
`graph_resource`-only dataset is a later degraded mode, useful only after an RDF adapter can derive or
validate the member index.

The node and edge tables are build-derived projections of the graph artifact. RG1 treats those
projections as the validation surface; reconciling them back against RDF triples is the recipe's
responsibility until a later RDF adapter adds an explicit graph/index consistency check.

The node index resource should have a minimal CSV contract:

```csv
member_key,member_kind,label,status,replaced_by,dataset_usage
MONDO:0005148,term,multiple myeloma,active,,"[]"
MONDO:obsolete,term,old label,deprecated,"MONDO:0005148","[]"
```

`member_kind` is an open vocabulary in RG1. Term-graph fixtures should use `term`; association-specific
kinds such as `disease`, `target`, or `association` are deferred until an association graph is the target
resource.

The edge resource, if present, should have:

```csv
subject,predicate,object,evidence,dataset_usage
MONDO:0005148,is_a,MONDO:0000001,,"[]"
```

### `bio.reference_graph.member/1.0`

Minimum fields:

```yaml
member_kind: term
label: multiple myeloma
status: active
```

This extension intentionally does not duplicate `parent_dataset` or `derivation.member_key`; those live
in the core `dataset`/`derivation` substrate. The extension carries only graph-member descriptors needed
for validation, display, and review.

---

## 5. Validation surface

Initial validation should be cheap and deterministic over pinned local artifacts:

1. **Resource existence.** `graph_resource` and `node_index_resource` must resolve to datapackage
   resources; `edge_resource` must resolve when declared.
2. **Format support.** `graph_format` must be one of the supported graph formats.
3. **Member-key declaration.** `member_key_space.kind`, prefixes, and `resolution_status` must be
   explicit.
4. **Node index contract.** The RG1 node index exists, `member_key` values are unique, and required
   columns parse.
5. **Count checks.** `member_count` and `edge_count` match the index/edge resource when those resources
   are declared.
6. **Member promotion resolution.** A `bio.reference_graph.member` dataset with `derivation.kind:
   member_of` must resolve `derivation.member_key` in its parent reference graph, unless a later
   implementation explicitly adds a declared-unresolved member state.
7. **Deprecated promoted members.** RG1 emits a review warning for promoted deprecated/withdrawn
   members; `replaced_by` is reported, not auto-applied. Arbitrary referenced-member handling is RG2+.
   Tier-based severity graduation is deferred until a concrete validator policy needs it.
8. **Dataset usage shape.** Dataset-level and member-level `dataset_usage` entries use the shared
   `DatasetUsage` role/overlap vocabulary and `dataset:` refs.

The first implementation should not require full RDF reasoning. It should parse enough to verify counts
and member existence through the node index or explicit edge table.

---

## 6. Relationship to dataset influence

Reference graphs are often built from other resources, and individual graph members may inherit only a
subset of that provenance. The design follows the same "store fine, promote on demand" rule used for gene
sets:

- graph-level `dataset_usage` captures whole-resource upstream dependence;
- node/edge-level usage captures member-specific provenance cheaply;
- virtual usage records can be materialized for unpromoted graph members;
- promoted members expose ordinary child-dataset `dataset_usage`;
- B2 can classify full-overlap direct dependence as committed shared-source metadata and weaker overlap
  as candidate review signals.

This lets a later evidence line cite a disease term, pathway term, ontology association, or Open Targets
association without losing the upstream provenance needed for double-counting review.

---

## 7. Relationship to identity

This design does not implement disease, ontology, cell-line, tissue, or association identity resolution.
It provides the pinned graph/member substrate those resolvers need.

Later non-molecular identity work can add resolvers such as:

```text
resolve_disease(curie, registry=dataset:mondo) -> resolved | deprecated | ambiguous | unresolved
resolve_cell_line(curie, registry=dataset:cellosaurus) -> ...
resolve_graph_member(key, registry=dataset:go) -> ...
```

Those resolvers should obey the same pinned-authoritative rule as C: no live service in reproducible
runs, explicit `declared_unresolved` when a namespace is outside implemented resolver scope, and no
automatic collapse across compatibility/xref relations.

---

## 8. Stress-test recheck

| Resource | Fit |
|---|---|
| GO | Term graph keyed by `GO:` CURIEs; obsolete/replaced terms matter; `is_a`/`part_of` edges live in graph artifact |
| MONDO | Disease ontology keyed by `MONDO:` CURIEs; xrefs to DOID/OMIM/EFO/NCIT are relations, not identity collapse |
| Open Targets | Association graph keyed by stable association ids or deterministic tuples; disease/target/source provenance can live on edges. Implemented as `dataset:opentargets-associations` (25.12 overall-direct, Model A entity nodes) |
| Reactome | Remains `bio.geneset` for pathway membership tables; pathway ontology-like relations may later be represented as a reference graph sibling |
| MSigDB | Remains `bio.geneset`; not graph-shaped in the first model |

The model therefore covers non-tabular references without weakening the flat gene-set contract.

---

## 9. Phasing

| Phase | Scope | Status |
|---|---|---|
| RG1 | Schema + parser + validation over tiny fixture graph/index/edge resources; node index required | implemented locally |
| RG2 | Virtual member payload resolution for promoted graph members; payload includes node row plus directly incident edges and exposes member-level `dataset_usage` for later B hooks | implemented locally |
| RG3 | Broader graph-member promotion workflows and unpromoted-member B materialization hooks | pending |
| RG4 | First real commons recipes: `dataset:mondo` (pushed to origin) and `dataset:go` from pinned OBO Graph JSON releases, with node/edge projections; `dataset:opentargets-associations` as the first association graph (Open Targets 25.12 overall-direct, Model A entity nodes, `edge_resource` omitted) | implemented |
| RG5 | Later non-molecular identity resolvers over one or more reference graphs | pending |

RG2 is implemented locally for promoted `bio.reference_graph.member` datasets. The generic
`member_of` payload dispatcher now detects unsupported collection kinds explicitly, and the
reference-graph resolver returns the member node row plus directly incident normalized edges.
Automated B materialization from unpromoted graph members remains RG3+/B follow-up work; RG2
preserves the node/edge `dataset_usage` data needed for that work.

RG2 implemented the generic virtual-member payload dispatcher and the first concrete
`bio.reference_graph.member` resolver. The sibling `bio.geneset.member` resolver is now implemented on the
same dispatch boundary. Unpromoted-member B materialization remains separate follow-up work because RG2
only returns payload data; it does not emit influence graph records.

---

## 10. Open review questions

1. **First real resource.** MONDO is probably the best first real ingestion because disease identity is a
   clear downstream need and term deprecation/xrefs exercise the model. GO is broader but may tempt
   conflation with gene sets. Open Targets is richer but more complex.
2. **Member key form for association graphs.** Term graphs naturally use CURIEs. Association graphs need
   either upstream stable ids or deterministic tuple keys. Resolved by `dataset:opentargets-associations`:
   Model A used heterogeneous CURIE keys (participating targets `ENSEMBL:ENSG…` ∪ diseases `EFO:`/`MONDO:`/…),
   so the first association graph reuses the CURIE key space rather than a tuple key. The generic
   tuple-key format remains unbuilt.
3. **RDF reasoning boundary.** The first increment should validate explicit build-derived index/edge
   artifacts, not infer transitive closure or ontology entailments. Reasoning and graph/index
   reconciliation can be later adapters with their own pinned outputs.

---

## 11. Next step

RG1, RG2, and RG4 are implemented, with `dataset:mondo`, `dataset:go`, and the first association graph
`dataset:opentargets-associations` as the real recipes. Remaining follow-ups are RG3 broader graph-member
promotion workflows, unpromoted-member B materialization, and RG5 non-molecular identity resolvers.
