# Bio Dataset-Influence & Provenance Tracking (Pillar B)

Date: 2026-05-26

Status: design for review (Phase 3 of the bio data architecture)

Related (builds on):
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; this is its Pillar B ("north star")
- `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` — Pillar A; the A/B external-derived provenance contract is realized here
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; dataset identity the refs resolve through
- `docs/plans/2026-05-21-provenance-propagation-contract-c-design.md` — `consumed_by`, `bears_on`, the provenance closure
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin (`derivation.inputs`)
- `science/model/src/science_model/schemas/mixin-paper-2.0.json` — existing `paper.datasets`
- `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` — independence collapse, `suspect-circular`

---

## 1. Purpose & scope

Pillar B makes every dataset's downstream flow — into papers, gene sets, derived datasets, observations,
and propositions — a **graph query** ("what does this dataset influence?", "do these two evidence lines
share a dataset ancestor?"), and turns the framework's **currently-manual** independence signal into a
**derived** one. It is the umbrella's north star: the double-counting machinery already exists but is
hand-fed; B feeds it from authored provenance.

**Locked decision (this review): one unified, structured forward-provenance object, `dataset_usage`,
authored in frontmatter and materialized as reified, qualified usage nodes (graph) at build time.** This
takes the single-model queryability of an edge-based approach *without* hiding the facts inside the graph
builder — the provenance stays visible and editable in the entity files.

**Explicit non-goals.** B does not build identifiers (C) or the epistemic class (A) — it *consumes* both.
It does not define the gene-set type (D); D **realizes** per-set `dataset_usage` provenance through B's
interface. It does not ingest Reactome (E).

---

## 2. What exists, and the gap

| Exists | Concerns | Limitation |
|---|---|---|
| `paper.datasets` (`[dataset:ref]`, plain) | which datasets a paper uses | no **usage role** — "analyzed" vs "cited as background" vs "set was defined from" are indistinguishable, yet they have opposite independence meaning |
| `derivation.inputs` (gated to `origin: derived`) | in-pipeline derivation inputs | only in-pipeline; an external derived artifact (AlphaMissense) cannot record inputs (the A/B contract) |
| `consumed_by` (dataset backlink, author-populated) | reverse "who used this" | hand-authored, drifts, not a derived index |
| Contract C `bears_on` / provenance closure | data→finding propagation | has no consumer→dataset usage edges to traverse |
| Independence collapse + `suspect-circular` WARN | double-counting | fires only on **hand-set** `shared_dataset`/`independence_group` |

**The gap B closes:** a single authored provenance object with usage semantics, materialized as graph
edges, from which `consumed_by`, the influence query, and **candidate** independence tags are all
*derived* rather than hand-maintained.

---

## 3. Locked design decisions

### B-D1 — `dataset_usage`: one structured forward-provenance object

A single object type used **everywhere** a consumer rests on data — `paper`, gene-set entities (D),
and derived/reference `dataset` entities — authored in frontmatter:

```yaml
dataset_usage:
  - ref: dataset:gtex-v8
    role: analyzed
    overlap: full          # full | partial | unknown
```

`ref` is a `dataset:` entity reference (external accessions resolve *through* the dataset entity, per the
umbrella's "one meaning per field"). Authored as a list; materialized as edges (B-D4).

### B-D2 — Role and overlap vocabulary

`role` ∈ **`analyzed | set_definition_source | validation_source | cited | upstream | training`**:

| role | Meaning |
|---|---|
| `analyzed` | primary data the consumer directly analyzed |
| `set_definition_source` | data a gene set / signature / annotation was **constructed from** |
| `validation_source` | independent data used to **validate** a result or set |
| `cited` | referenced as background; not a data dependency |
| `training` | model **training** data (e.g. AlphaMissense) — kept distinct from `upstream` because model provenance needs it |
| `upstream` | broad dependency role for external derived artifacts where the precise role is unknown |

`overlap` ∈ `full | partial | unknown` records how much of the referenced dataset the dependency actually
touches, so partial/uncertain overlaps are not collapsed as if identical.

### B-D3 — Reconciling existing fields (migrate cleanly, don't preserve duplicates)

- **`paper.datasets` → migrate to `dataset_usage`** with `role: analyzed`, `overlap: unknown` (or `full`
  where existing semantics guarantee it). Bump the `paper` mixin version. `paper.datasets` is **not**
  preserved as the long-term semantic field — one model, not two.
- **A's `upstream_datasets` → the `{upstream, training}` projection of `dataset_usage`**, not a separate
  model. Pillar A is updated to define its external-derived provenance as `dataset_usage` entries with
  `role ∈ {upstream, training}` (a role-restricted view of the same schema).
- **`derivation.inputs` → kept** as in-pipeline *execution* provenance. B **derives** equivalent
  dataset-use edges from it (`role: upstream`) at build, but does not replace or duplicate it in authored
  frontmatter.
- **`consumed_by` → a derived index/cache**, never an authored truth source. Reverse-consumer query
  surfaces derive from `dataset_usage` + `derivation.inputs`; any legacy authored `consumed_by` is retained
  for **migration/compat only**, not read as ground truth.

### B-D4 — Authored structure, materialized as a qualified usage node

At `graph build`, each `dataset_usage` entry (plus the entries derived from `derivation.inputs`)
materializes as a **reified, qualified usage node**, not a bare predicate — a simple `consumer —uses:role→
dataset` edge would lose the role / overlap / source metadata (and later D's per-set provenance):

```text
consumer    sci:hasDatasetUsage  usage-node
usage-node  rdf:type             sci:DatasetUsage
usage-node  sci:dataset          dataset:x
usage-node  sci:usageRole        "analyzed"
usage-node  sci:usageOverlap     "full"
usage-node  sci:usageSource      "authored" | "derivation.inputs"
```

The qualified usage node is **canonical**; convenience edges (e.g. a direct consumer→dataset link) may be
derived from it for query ergonomics. The authored frontmatter lists remain the source of truth and stay
human-visible/editable; the usage nodes are their build-time projection. This is the deliberate blend:
edge-based queryability, authored-file visibility.

### B-D5 — Role-specific independence semantics

Independence is **not** "shares any ref" — it is role-aware:

- `analyzed`, `set_definition_source`, `training`, `upstream` → **dependence-implying**: a shared ref via
  these roles can imply non-independence / a collapse candidate.
- `validation_source` → an **anti-circularity positive signal**: it should **not** collapse with
  `training`/`set_definition_source` *unless the same ref overlaps* (validating on the very data a set was
  defined from is the circular case and is still caught).
- `cited` → **never collapses by itself**; at most a review warning or a weak candidate.

### B-D6 — Auto-independence with a hard committed/candidate split

At build, B derives independence signals from shared dataset usage — but it **must not write candidate
signals into the fields the aggregator collapses on**. `aggregate_belief` collapses **any** shared
`independence_group`/`shared_dataset` with no notion of "candidate", so routing tentative signals there
would *silently collapse* independent evidence while the doc claims "WARN only." The hard split:

- **Established direct dependence** — same `ref`, dependence-implying roles (`analyzed` /
  `set_definition_source` / `training` / `upstream`), `overlap: full` — **may** materialize the
  **committed** collapse fields (`shared_dataset` / `independence_group`) that `aggregate_belief` reads.
- **Everything tentative** — `overlap: partial`/`unknown`, `cited`-only links, or any not-yet-confirmed
  inference — materializes **separate** metadata (`candidate_shared_dataset`,
  `candidate_independence_reason`) or stays internal to the validate pass. It is **never** written to the
  committed fields.
- **Readers:** `independence.suspect-circular` reads **both** committed and candidate signals (so it warns
  on tentative cases); `aggregate_belief` reads **only** the committed collapse fields (so it never
  collapses on a candidate). This is what makes "WARN, don't silently collapse" true in implementation, not
  just in prose.

The `validation_source` anti-circularity rule (B-D5) applies first: it suppresses a candidate unless the
same `ref` overlaps a dependence role.

### B-D7 — Influence query

The reverse query — "what does dataset X influence?" — runs over the materialized `sci:DatasetUsage` nodes
plus the Contract C `bears_on` closure: dataset → consumers (papers/sets/derived datasets) → the
propositions those bear on. `consumed_by` is the derived cache of this reverse slice, not a separate truth.

---

## 4. The circularity case B exists to catch

The dangerous pattern is **define-a-set-from-study-A, then test enrichment of that set in study-A**:

- the gene set declares `dataset_usage: {ref: dataset:studyA, role: set_definition_source}`,
- the proposition's evidence line analyzes `dataset:studyA` (`role: analyzed`).

Sharing `dataset:studyA` through two dependence roles with overlapping data → a **circular** candidate →
`suspect-circular` WARN (and collapse if `overlap: full`). Contrast the *legitimate* case — a set defined
from study-A but **validated** in an independent cohort (`validation_source`, different ref) — which is an
independence *positive* and is not collapsed. This is exactly the provenance D's per-set records feed.

---

## 5. Honest scope

- **Auto-derived:** non-independence from *declared* shared refs with dependence roles and known overlap.
- **Reviewer flag, not auto:** semantic / citation-chain overlap with no declared shared ref; `cited`-only
  links; `overlap: partial`/`unknown`. B surfaces these as candidates; it does not silently act on them.
- **Out of scope:** full citation-ancestry de-duplication (tracing that two papers ultimately rest on the
  same primary data through an unstated chain). B makes the *declared* layer queryable; the undeclared
  layer stays a human judgment.

---

## 6. Stress-test recheck (against umbrella §5)

| Case | `dataset_usage` | Independence effect |
|---|---|---|
| Paper analyzing GTEx | `{ref: gtex, role: analyzed}` | normal dependence on GTEx |
| Paper citing GTEx as background | `{ref: gtex, role: cited}` | no collapse; weak candidate only |
| MSigDB set built from a study | `{ref: studyA, role: set_definition_source}` | dependence; circular if tested in studyA |
| Set validated in an independent cohort | `{ref: cohortB, role: validation_source}` | independence-positive; no collapse |
| AlphaMissense | `{ref: …, role: training}` (= A's `upstream_datasets` projection) | training dependence derivable (the A/B contract) |
| Meta-analysis we ran | (from `derivation.inputs`, `role: upstream`) | committed collapse vs its inputs (existing machinery, now usage-node-materialized) |

All cases use **one field + role-aware semantics** — no per-case special handling.

---

## 7. Open items & dependencies

1. **D realizes per-set `dataset_usage`.** A gene-set *collection* can mix sets with different
   `set_definition_source`s; D decides where per-set provenance lives (per-set vs collection-level) and how
   it surfaces as `dataset_usage` on a promoted set. B defines the interface; D realizes it.
2. **`ref` to a not-yet-minted dataset.** If a consumer used data that has no `dataset:` entity yet, the
   default is to mint/point-to one (umbrella unresolved-accession question); B does not invent an
   unresolved-accession escape hatch unless that proves necessary.
3. **Overlap precision.** `full|partial|unknown` is intentionally coarse; finer overlap quantification is
   deferred unless the circularity logic needs it.

---

## 8. Decomposition & phasing (within B)

| Sub-phase | Locks |
|---|---|
| B1 — `dataset_usage` object on the core model + `paper.datasets` migration + qualified `sci:DatasetUsage` node materialization at build + `consumed_by` as derived cache + derive usage nodes from `derivation.inputs` | the authored→graph provenance layer |
| B2 — auto-independence with the committed/candidate split (B-D6): committed `shared_dataset`/`independence_group` only on established full-overlap dependence, `candidate_*` fields otherwise; `suspect-circular` reads both, `aggregate_belief` reads committed only + the influence query | the epistemic automation |

B depends on A (`source_class`, and the `{upstream, training}` projection that replaces `upstream_datasets`)
and C (dataset identity the refs resolve through). Within Phase 3, **D leads B's gene-set arm** (D's
collection schema must exist before per-set `dataset_usage` can attach); B1's paper/derived-dataset side
and the edge engine can proceed in parallel.

---

## 9. Status & next step

Pillar B design for review. On approval, Pillar D (`bio.geneset`, which realizes per-set `dataset_usage`)
is the last foundational design, after which Pillar E (Reactome) is revised to consume A–D and
writing-plans produces the implementation plans. A small companion edit to the Pillar A doc reconciles
`upstream_datasets` into the unified `dataset_usage` model defined here.
