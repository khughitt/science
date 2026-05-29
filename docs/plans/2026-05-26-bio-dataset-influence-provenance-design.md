# Bio Dataset-Influence & Provenance Tracking (Pillar B)

Date: 2026-05-26

Status: approved; B1 design refreshed for additive transition, implementation plan next

Related (builds on):
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; this is its Pillar B ("north star")
- `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` — Pillar A; `dataset_usage` and source-class substrate
- `docs/plans/2026-05-26-bio-geneset-type-design.md` — Pillar D; D1 realizes row-level gene-set provenance
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; dataset identity the refs resolve through
- `docs/plans/2026-05-21-provenance-propagation-contract-c-design.md` — `consumed_by`, `bears_on`, the provenance closure
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin (`derivation.inputs`)
- `science/model/src/science_model/schemas/mixin-dataset-1.0.json` — shipped `dataset_usage` vocabulary
- `science/model/src/science_model/schemas/mixin-paper-2.0.json` — existing `paper.datasets` transition field
- `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` — independence collapse, `suspect-circular`

---

## 1. Purpose & Scope

Pillar B makes every dataset's downstream flow — into papers, gene sets, derived datasets, observations,
and propositions — a **graph query** ("what does this dataset influence?", "do these two evidence lines
share a dataset ancestor?"). It turns the currently manual independence signal into a derived signal, but
does so in phases so provenance materialization lands before any belief-aggregation behavior changes.

**Locked decision:** one structured forward-provenance object, `dataset_usage`, is the canonical model for
declared data dependence. The object is authored in frontmatter where supported and materialized as
reified, qualified `sci:DatasetUsage` nodes at graph-build time.

**Current implementation reality.** A1 already shipped `dataset_usage` on the base `Entity` model and
the dataset schema with the full six-role vocabulary. D1 already accepts row-level `dataset_usage` in
`bio.geneset` collection member rows. B1 therefore does **not** invent the object. For papers, the model
side is likely a no-op because `PaperEntity` inherits the base field; the B1 work is to expose the field
explicitly in the paper schema/frontmatter contract, document it as canonical, make it queryable in the
graph, and add validate checks around references and transition behavior.

**B1 boundary.** B1 is the authored-to-graph provenance layer:

- expose `dataset_usage` on paper schema/frontmatter, reusing the existing model field where possible,
- keep `paper.datasets` as a transition input,
- project legacy `paper.datasets` into usage records,
- materialize authored and derived usage records as `sci:DatasetUsage` nodes,
- derive usage nodes from `derivation.inputs`,
- validate malformed/unresolved/legacy usage,
- document and enforce a migration path toward the single canonical system.

**B2 boundary.** B2 derives candidate and committed independence signals from the usage graph. It owns the
committed/candidate split, `suspect-circular` integration, and any changes to belief aggregation inputs.

**Explicit non-goals for B1.** B1 does not implement auto-independence, does not write
`shared_dataset`/`independence_group`, does not change `aggregate_belief`, does not implement D2 promoted
members, and does not ingest Reactome.

---

## 2. What Exists, And The Gap

| Exists | Concerns | Limitation |
|---|---|---|
| `dataset_usage` on datasets | structured forward provenance | not graph-materialized yet |
| D1 row-level `dataset_usage` | per-set provenance in `bio.geneset` members resource | row-shape checked, but not projected into the graph as usage nodes |
| `paper.datasets` (`[dataset:ref]`, plain) | datasets a paper used | no role or overlap; cannot distinguish analyzed data from background citation |
| `derivation.inputs` | in-pipeline execution provenance | not visible as `DatasetUsage` nodes for influence queries |
| `consumed_by` | reverse "who used this" | authored/cache-like field that can drift |
| Contract C `bears_on` / provenance closure | data-to-finding propagation | lacks consumer-to-dataset usage nodes to traverse |
| Independence collapse + `suspect-circular` WARN | double-counting | currently relies on manually authored evidence-line metadata |

**The B1 gap:** make declared dataset use queryable and consistent without changing independence scoring.
`dataset_usage`, `paper.datasets`, and `derivation.inputs` all need one graph projection.

---

## 3. Canonical Usage Object

### B-D1 — `dataset_usage`

`dataset_usage` is the canonical authored object for a consumer resting on data:

```yaml
dataset_usage:
  - ref: dataset:gtex-v8
    role: analyzed
    overlap: full
```

`ref` is a `dataset:` entity reference. External accessions resolve through dataset entities, not through
`dataset_usage`; this preserves one meaning per field. `overlap` defaults to `unknown` in the Pydantic
model when omitted.

### B-D2 — Role And Overlap Vocabulary

`role` is the canonical six-role vocabulary already shipped by A1:

| Role | Meaning |
|---|---|
| `analyzed` | primary data the consumer directly analyzed |
| `set_definition_source` | data a gene set, signature, or annotation was constructed from |
| `validation_source` | independent data used to validate a result or set |
| `cited` | referenced as background; not by itself a data dependency |
| `training` | model training data |
| `upstream` | broad dependency role where the precise role is unknown |

`overlap` is `full | partial | unknown`.

---

## 4. Additive Paper Transition

### B-D3 — `paper.datasets` Is A Transition Input

B1 exposes `dataset_usage` on papers but does not break existing projects that still author
`paper.datasets`. The model field already exists through the base `Entity`; the implementation should
verify that parse/materialization paths preserve it for `PaperEntity` rather than adding duplicate model
state.

During B1:

- `paper.dataset_usage` is canonical per referenced dataset.
- `paper.datasets` remains readable as legacy transition input and is projected per ref.
- Each `paper.datasets` ref is projected as:

```yaml
ref: dataset:<id>
role: analyzed
overlap: unknown
source: paper.datasets
```

- The validate check emits a migration warning when a paper still uses `datasets` without equivalent
  `dataset_usage`.
- If both fields are present, materialization uses a **per-ref union**: refs present only in
  `paper.datasets` are still projected, and refs present in `dataset_usage` use the explicit
  `dataset_usage` entry. Same-ref legacy duplicates are not double-materialized. A same-ref legacy
  `datasets` entry plus an explicit non-`analyzed` usage is reported as a migration conflict because the
  legacy field semantically implied `analyzed`.

### B-D4 — Migration To One System

B1 deliberately starts additive, but the long-term state is one system:

1. **B1:** add `dataset_usage`, project `paper.datasets`, and warn on legacy use.
2. **B-migration:** provide/plan a mechanical migration from `paper.datasets` to `dataset_usage` entries
   with `role: analyzed`, `overlap: unknown`.
3. **Later B phase:** convert legacy `paper.datasets` from warning to error once downstream projects have
   migrated.
4. **Final cleanup:** remove `paper.datasets` from the canonical paper schema/model surface.

This avoids compatibility layers as permanent architecture: the transition field is named, warned on, and
given an explicit removal path.

---

## 5. Graph Materialization

### B-D5 — Qualified Usage Nodes

At graph build, each usage record materializes as a reified node. A bare `consumer -> dataset` edge would
lose role, overlap, and source metadata.

```text
consumer    sci:hasDatasetUsage  usage-node
usage-node  rdf:type             sci:DatasetUsage
usage-node  sci:dataset          dataset:x
usage-node  sci:usageRole        "analyzed"
usage-node  sci:usageOverlap     "full"
usage-node  sci:usageSource      "authored" | "paper.datasets" | "derivation.inputs" | "geneset.members_resource"
```

The usage node is canonical. Convenience edges may be derived for query ergonomics, but they are not the
source of truth. `sci:usageSource` is a closed B1 enum with exactly the four values shown above; multiple
frontmatter locations can map to the same source value (`authored`).

### B-D6 — Sources Of Usage Records

B1 materializes usage records from five sources:

| Source | Projection |
|---|---|
| authored `dataset_usage` on datasets | `usageSource: authored` |
| authored `dataset_usage` on papers | `usageSource: authored` |
| legacy `paper.datasets` | `role: analyzed`, `overlap: unknown`, `usageSource: paper.datasets` |
| `derivation.inputs` on derived datasets | `role: upstream`, `overlap: unknown`, `usageSource: derivation.inputs` |
| D1 `bio.geneset` member rows | `usageSource: geneset.members_resource`, consumer is a virtual collection-member URI |

D1 gene-set rows are already parsed and validate-checked. B1 turns a row-level `dataset_usage` block into
usage records for a deterministic virtual collection-member URI, derived from `(collection dataset id,
set_key)`. The collection side uses the same canonical dataset id/slug parsing as ordinary entity URIs;
the `set_key` segment is percent-encoded as a path segment, and the encoder must be a shared helper with
round-trip tests. If two distinct `(collection id, set_key)` pairs produce the same virtual URI, graph
build fails rather than merging them.

The virtual member URI is a graph/provenance address only; it is **not** a promoted dataset entity and
does not require D2. In B1, row-level usage nodes make the forward query "which gene-set row declares use
of dataset X?" visible, but they do not automatically participate in the broader dataset → proposition
influence closure unless another edge already connects that virtual row to a proposition. D2 promotion, or
a later explicit evidence-line reference to a row, is what gives an individual set a normal `bears_on`
path. If a row is later promoted by D2, the promoted dataset can point back to the same collection/set key
and carry equivalent `dataset_usage`.

When a consumer has usage records for the same dataset from multiple sources, B1 keeps separate usage
nodes because the provenance of the assertion differs. B2 must de-duplicate by `(consumer, dataset, role,
overlap)` or a stricter policy before deriving independence so multi-source assertions do not create
double-counted dependence.

### B-D7 — Reverse Influence Groundwork

The immediate B1 graph question is: "which consumers declare use of dataset X?" That query runs over
`sci:DatasetUsage` nodes. The broader influence query — dataset → consumers → propositions they bear on —
uses the existing `bears_on` / provenance closure and can be built on top of the same nodes.

`consumed_by` becomes a derived cache/index target, not authored truth. B1 may validate authored
`consumed_by` as legacy/stale, but graph queries should use usage nodes.

---

## 6. Validate Checks

B1 adds a tolerant validate check for dataset influence/provenance. It should report issues without
requiring every referenced commons artifact to be built locally.

The B1 check covers:

- malformed `dataset_usage` on papers and datasets,
- unresolved `dataset_usage.ref` values against local/commons dataset entities,
- legacy `paper.datasets` usage and migration warnings,
- duplicate/conflicting `paper.datasets` and `paper.dataset_usage` declarations,
- invalid `paper.datasets` entries that are not `dataset:` refs,
- optional checks for authored `consumed_by` as stale/cache-like metadata,
- `derivation.inputs` projections only when their input refs resolve to datasets,
- D1 gene-set row-level `dataset_usage.ref` values resolve to datasets when the members resource is
  available.

D1 row-level `dataset_usage` shape remains checked by `genesets`; B1 reuses the D1 parser for projection
and adds reference-resolution checks for the parsed row usage records.

The optional `consumed_by` staleness check is a different cost class from per-record shape/reference
checks: it requires building the reverse usage index and comparing authored backlinks to the derived view.
It should be planned as a separate B1 task or deferred if it threatens the narrower provenance
materialization path.

---

## 7. Independence Semantics Deferred To B2

B1 does not derive or write evidence-line independence fields. It only creates the graph layer B2 will
read.

B2 will interpret roles as follows:

- `analyzed`, `set_definition_source`, `training`, `upstream` are dependence-implying.
- `validation_source` is an independence-positive signal unless it overlaps the same ref used through a
  dependence role.
- `cited` never collapses by itself.

B2 also owns the hard committed/candidate split:

- committed fields (`shared_dataset`, `independence_group`) are written only for established direct
  full-overlap dependence;
- candidate signals use separate metadata and can feed `suspect-circular` warnings;
- `aggregate_belief` reads committed fields only.

This separation prevents B1 from silently changing belief behavior while the provenance graph is still
being introduced.

---

## 8. Circularity Case

The dangerous pattern is **define a set from study A, then test enrichment of that set in study A**:

- the gene set row declares `{ref: dataset:study-a, role: set_definition_source}`,
- the paper or evidence context declares `{ref: dataset:study-a, role: analyzed}`.

B1 makes those facts visible as usage nodes. B2 later turns the shared dependence into a circularity
candidate or committed collapse depending on overlap and policy. The legitimate case — a set defined from
study A and validated in independent cohort B — remains distinguishable through `validation_source`.

---

## 9. Stress-Test Recheck

| Case | B1 materialization | B2 interpretation |
|---|---|---|
| Paper analyzing GTEx via `dataset_usage` | authored usage node, `analyzed` | dependence |
| Paper still using `datasets: [dataset:gtex-v8]` | transition usage node, `analyzed`, `unknown`, warning | dependence candidate only until migrated/overlap known |
| Paper citing GTEx as background | authored usage node, `cited` | no collapse by itself |
| MSigDB set built from a study | gene-set row usage, `set_definition_source` | circular if tested in same data |
| Set validated in independent cohort | gene-set row usage, `validation_source` | independence-positive |
| AlphaMissense training data | dataset usage node, `training` | training dependence |
| Derived dataset from workflow inputs | `derivation.inputs` usage nodes, `upstream`, `unknown` | dependence candidate unless overlap is later declared as full |

---

## 10. Decomposition & Phasing

| Sub-phase | Locks | Status |
|---|---|---|
| B1 — additive `dataset_usage` transition for papers, usage-node graph materialization, `derivation.inputs` projection, legacy `paper.datasets` warnings, influence-query groundwork | authored-to-graph provenance layer | design refreshed; implementation plan next |
| B-migration — mechanical conversion of `paper.datasets` to `paper.dataset_usage` | single-system migration path | planned after B1 |
| B2 — auto-independence with committed/candidate split; `suspect-circular` reads candidates; aggregation reads committed fields only | epistemic automation | deferred |

B1 depends on A1's shipped `dataset_usage` vocabulary, C's dataset identity refs, and D1's gene-set row
contract. B2 depends on B1's materialized usage nodes.

---

## 11. Status & Next Step

Pillar B is approved with a B1-first implementation boundary. The next artifact is a B1 implementation
plan that exposes paper `dataset_usage`, materializes usage nodes, validates references and legacy fields,
and documents the migration path from `paper.datasets` to the single canonical `dataset_usage` system.
