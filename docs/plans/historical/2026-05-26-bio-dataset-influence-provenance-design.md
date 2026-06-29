# Bio Dataset-Influence & Provenance Tracking (Pillar B)

Date: 2026-05-26

Status: implemented; retained as historical Pillar B rationale

Related (builds on):
- `docs/plans/historical/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; this is its Pillar B ("north star")
- `docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` — Pillar A; `dataset_usage` and source-class substrate
- `docs/plans/2026-05-26-bio-geneset-type-design.md` — Pillar D; D1 realizes row-level gene-set provenance
- `docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; dataset identity the refs resolve through
- `docs/plans/historical/2026-05-21-provenance-propagation-contract-c-design.md` — `consumed_by`, `bears_on`, the provenance closure
- `docs/user-guide/entities.md#dataset-lifecycle` — dataset mixin (`derivation.inputs`)
- `science/model/src/science_model/schemas/mixin-dataset-1.0.json` — shipped `dataset_usage` vocabulary
- `science/model/src/science_model/schemas/mixin-paper-2.0.json` — existing `paper.datasets` transition field
- `docs/plans/historical/2026-05-22-evidence-aggregation-and-belief-design.md` — independence collapse, `suspect-circular`

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
- materialize authored `dataset_usage` from any entity as `sci:DatasetUsage` nodes,
- derive usage nodes from `derivation.inputs`,
- validate malformed/unresolved/legacy usage,
- document the migration path toward the single canonical system and emit transition warnings.

**B2 boundary.** B2 derives candidate and committed independence signals from the usage graph. It owns the
committed/candidate split, `suspect-circular` integration, and any changes to belief aggregation inputs.

**Explicit non-goals for B1.** B1 does not implement auto-independence, does not write
`shared_dataset`/`independence_group`, does not change `aggregate_belief`, does not implement D2 promoted
members, and does not ingest Reactome.

---

## 2. What Exists, And The Pre-B1 Gap

| Exists | Concerns | Limitation |
|---|---|---|
| `dataset_usage` on base `Entity` | structured forward provenance any entity can carry | before B1, not graph-materialized |
| D1 row-level `dataset_usage` | per-set provenance in `bio.geneset` members resource | before B1, row-shape checked but not projected into the graph as usage nodes |
| `paper.datasets` (`[dataset:ref]`, plain) | datasets a paper used | no role or overlap; cannot distinguish analyzed data from background citation |
| `derivation.inputs` | in-pipeline execution provenance | before B1, not visible as `DatasetUsage` nodes for influence queries |
| `consumed_by` | reverse "who used this" | authored/cache-like field that can drift |
| Contract C `bears_on` / provenance closure | data-to-finding propagation | lacks consumer-to-dataset usage nodes to traverse |
| Independence collapse + `suspect-circular` WARN | double-counting | currently relies on manually authored evidence-line metadata |

**The pre-B1 gap:** make declared dataset use queryable and consistent without changing independence
scoring. `dataset_usage`, `paper.datasets`, and `derivation.inputs` all needed one graph projection.
Because `dataset_usage` is on the base `Entity` model, B1 now materializes authored `dataset_usage`
universally for any entity that carries it; restricting materialization to only datasets/papers would
silently drop valid parsed frontmatter on other entity kinds. B1 also closes the graph-materialization
gaps for D1 row-level usage records and `derivation.inputs`. Follow-up work implemented the mechanical
`paper.datasets` migration path and B2 dataset-derived independence layer.

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
  legacy field semantically implied `analyzed`; materialization still uses the explicit `dataset_usage`
  entry and emits a warning rather than blocking graph build.

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

Graph materialization is strict even though validation is tolerant. The materializer assumes validate has
passed; if a malformed usage record, self-referential dataset usage, or other ERROR-class condition
reaches graph build, graph build fails. It must never silently skip the record or emit a partial/bad
usage node.

### B-D6 — Sources Of Usage Records

B1 materializes usage records from four usage-source classes:

| Source | Projection |
|---|---|
| authored `dataset_usage` on any entity kind | `usageSource: authored`, consumer is that entity |
| legacy `paper.datasets` | `role: analyzed`, `overlap: unknown`, `usageSource: paper.datasets` |
| `derivation.inputs` on derived datasets | `role: upstream`, `overlap: unknown`, `usageSource: derivation.inputs` |
| D1 `bio.geneset` member rows | `usageSource: geneset.members_resource`, consumer is a virtual collection-member URI |

D1 gene-set rows are already parsed and validate-checked. B1 turns a row-level `dataset_usage` block into
usage records for a deterministic virtual collection-member URI, derived from `(collection dataset id,
set_key)`. The collection side uses the same canonical dataset id/slug parsing as ordinary entity URIs;
the `set_key` segment is normalized to Unicode NFC, encoded as UTF-8, then percent-encoded as a path
segment with uppercase hex escapes and only RFC 3986 unreserved bytes left literal. The encoder must be a
shared helper with round-trip tests. Virtual member URIs live under a reserved project namespace prefix
that cannot collide with real entity URIs such as `project:dataset/<slug>`. If two distinct `(collection
id, set_key)` pairs produce the same virtual URI, graph build fails rather than merging them.

The virtual member URI is a graph/provenance address only; it is **not** a promoted dataset entity and
does not require D2. In B1, row-level usage nodes make the forward query "which gene-set row declares use
of dataset X?" visible, but they do not automatically participate in the broader dataset → proposition
influence closure unless another edge already connects that virtual row to a proposition. D2 promotion, or
a later explicit evidence-line reference to a row, is what gives an individual set a normal `bears_on`
path. If a row is later promoted by D2, the promoted dataset can point back to the same collection/set key
and carry equivalent `dataset_usage`.

Because row usage nodes require parsing the collection's members resource, graph materialization treats
that resource as required for any `bio.geneset` collection selected for graph build. If the members
resource is absent or cannot be resolved, graph build fails rather than under-materializing the influence
graph. Fresh-checkout validation may still report this as INFO when the resource is unavailable; graph
build has a stricter contract because its output is queryable truth, not a lint report.

When a consumer has usage records for the same dataset from multiple sources, B1 keeps separate usage
nodes because the provenance of the assertion differs. The handoff to B2 is intentionally explicit:
before deriving independence, B2 must collapse same `(consumer, dataset)` assertions using a
most-dependent-wins policy over role and overlap, not just exact-tuple de-duplication. For example, an
authored `{role: analyzed, overlap: full}` record and a derived `{role: upstream, overlap: unknown}`
record for the same pair are not contradictory graph facts; they are multi-source assertions that B2 must
reduce to one dependence interpretation.

### B-D7 — Reverse Influence Groundwork

The immediate B1 graph question is: "which consumers declare use of dataset X?" That query runs over
`sci:DatasetUsage` nodes. The broader influence query — dataset → consumers → propositions they bear on —
uses the existing `bears_on` / provenance closure and can be built on top of the same nodes.

`consumed_by` becomes a derived cache/index target, not authored truth. B1 graph queries use usage
nodes; validation of authored `consumed_by` as legacy/stale is deferred outside B1.

---

## 6. Validate Checks

B1 adds a tolerant validate check for dataset influence/provenance. It should report issues without
requiring every referenced commons artifact to be built locally.

The B1 check covers these cases with pinned severities:

| Case | Severity | Rule intent |
|---|---|---|
| malformed `dataset_usage` shape on any entity | ERROR | the authored object cannot be safely materialized |
| `dataset_usage.ref` or `derivation.inputs` self-reference | ERROR | self-loop usage would create false circularity candidates |
| invalid `paper.datasets` entry that is not a `dataset:` ref | ERROR | legacy transition input still has a strict ref contract |
| duplicate/conflicting `paper.datasets` and `paper.dataset_usage` declarations | WARNING | explicit `dataset_usage` materializes; warning directs migration cleanup |
| legacy `paper.datasets` without equivalent `dataset_usage` | WARNING | accepted during transition, but authors should migrate |
| unresolved ref when commons/local registry needed to check it is unavailable | INFO | tolerant fresh-checkout behavior |
| unresolved ref when local/commons discovery is available and the dataset is absent | WARNING | likely authoring gap without crashing validation |
| D1 row-level `dataset_usage.ref` unresolved while members resource is available | WARNING or INFO by the same ref-resolution rule above | row usage is parsed by D1, resolved by B1 |

D1 row-level `dataset_usage` shape remains checked by `genesets`; B1 reuses the D1 parser for projection
and adds reference-resolution checks for the parsed row usage records.

The self-reference rule applies only where the consumer itself is a dataset id, such as a dataset entity's
authored `dataset_usage` or its `derivation.inputs`. Paper consumers and virtual gene-set member consumers
cannot equal a `dataset:` ref and therefore cannot trigger this rule.

The optional future `consumed_by` staleness check is a different cost class from the B1 per-record
shape/reference checks: it requires building the reverse usage index and comparing authored backlinks to
the derived view. It did not land in B1 and is explicitly deferred outside B1 as future optional work.

---

## 7. Independence Semantics Implemented By B2

B1 does not derive or write evidence-line independence fields. It creates the graph layer that B2 reads.

B2 interprets roles as follows:

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

B1 makes those facts visible as usage nodes. B2 turns the shared dependence into a circularity candidate
or committed collapse depending on overlap and policy. The legitimate case — a set defined from study A
and validated in independent cohort B — remains distinguishable through `validation_source`.

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
| B1 — additive `dataset_usage` transition for papers, usage-node graph materialization, `derivation.inputs` projection, legacy `paper.datasets` warnings, influence-query groundwork | authored-to-graph provenance layer | implemented |
| B-migration — mechanical conversion of `paper.datasets` to `paper.dataset_usage` | single-system migration path | implemented via `science graph migrate-paper-datasets` |
| B2 — auto-independence with committed/candidate split; `suspect-circular` reads candidates; aggregation reads committed fields only | epistemic automation | implemented |

B1 depends on A1's shipped `dataset_usage` vocabulary, C's dataset identity refs, and D1's gene-set row
contract. B2 depends on B1's materialized usage nodes.

---

## 11. Status & Next Step

Pillar B is implemented as the authored-to-graph provenance layer, the `paper.datasets` migration tool,
and the B2 candidate/committed dataset-independence derivation layer. Later policy cleanup can still
escalate legacy `paper.datasets` warnings after downstream migration campaigns complete.
