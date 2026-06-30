# Graph And Derived State

Science builds graph state from authored project sources.

```bash
science graph build
science graph dashboard-summary
science belief snapshot
```

## Graph Build

`science graph build` materializes project sources into graph files under
`knowledge/`. The graph is a derived view over source-authored entities,
bibliography records, structured sources, and project configuration.

Do not edit `knowledge/graph.trig` as the durable fix. Correct the source and
rebuild.

Inquiry graphs are also derived views. The graph-backed inquiry source is a
`patch-definition` file with `patch_type: inquiry` under `entities/patches/`;
`science graph build` compiles it into a dedicated `sci:Inquiry` named graph and
patch-membership layer. Use `science inquiry show` and `science inquiry
validate` to read the compiled view.

Patch definitions are authored intent, not authored member lists. A
`patch-definition` names a focal entity, local scope, derivation policy, seeds,
and excludes. `science graph build` derives membership after the `bears_on`
closure is available, emits reified `sci:PatchMembership` records into patch
named graphs, and generates `sci:hasMember` / `sci:inPatch` convenience edges
from those records. The membership node is authoritative; orphan convenience
edges fail validation.

The v1 patch policy is `local-closure-v1`. It uses local project scope, a
depth-bounded `sci:bearsOn` neighborhood based on precomputed
`sci:bearsOnDepth`, and one-hop direct relations over `cito:discusses`,
`cito:supports`, and `cito:disputes`. Non-local scopes, snapshot publication,
patch maturity levels, latent/ontology glue, and remote commons neighborhoods
are deferred.

Patch diagnostics read the same derived state and do not write a second graph
artifact:

```bash
science patch explain <patch-definition-id>
science patch check
```

Archived entity references resolve from `entities/_archive/archive-index.jsonl`.
Graph materialization uses that active index to emit archived-entity stubs and
`sci:consolidates` edges where consolidation rows exist. It does not rehydrate
full archived Markdown into the live graph; edit or restore archived records
through the archive workflow described in [Entities](entities.md).

For local cleanup in a project that declares peers, use:

```bash
science graph build --local-only
```

This refreshes `knowledge/graph.trig` and leaves `knowledge/composite.trig` untouched.
Use the default `science graph build` when you intentionally want to refresh the
peer-composed graph.

### Source Snapshots

Graph build records source-observation provenance for loaded Markdown-backed
entities. Each observed file gets a `sci:SourceSnapshot` node in the provenance
graph with its project-relative `sourcePath` and raw-file SHA-256. The snapshot
also bears on the entity it backs, so source changes participate in derived
freshness through the same dependency layer as other graph causes.
Aggregate rows, datapackages, remote APIs, DOI records, Zenodo records, and
dataset manifests are not source-snapshotted yet.

The first build establishes a baseline and emits no `sci:SourceChange`. On later
builds, a changed content hash mints a `sci:SourceChange` event with the new
hash and `observedOn` date, linked from the snapshot via
`sci:latestSourceChange`. If the content hash is unchanged, the prior snapshot
and latest-change event are carried forward unchanged; rebuilds should not churn
the observed date.

Only the current/latest source-change event is persisted for each source.
Science does not keep a full source-change event log in the graph. Source
snapshots are emitted even when freshness-state derivation is disabled, so the
baseline remains continuous if freshness checks are re-enabled later.

## Dashboard Summaries

Dashboard summaries are compact readings of the current graph: unresolved
references, evidence status, graph hygiene, and project orientation. They help
agents and humans decide where to work next.

## Graph JSON Export

`science graph export-json` emits the reusable graph payload for inspection,
scripting, and dashboard consumers:

```bash
science graph export-json
science graph export-json --overlay causal --overlay evidence
```

The payload is a semantic export contract owned by Science, not a renderer
configuration. It has these top-level fields:

| Field | Purpose |
|---|---|
| `schema_version` | Export contract version. |
| `nodes` | Base graph nodes with stable URI ids, labels, optional type/status/confidence, source refs, and primary graph layer. |
| `edges` | Base graph edges keyed by deterministic `(subject, predicate, object, graph_layer)` ids. |
| `layers` | Named graph-layer summaries with node and edge counts. |
| `scopes` | Typed graph slices such as `project` and `inquiry/<slug>`, each with node and edge membership. |
| `overlays` | Optional typed semantic overlays requested by `--overlay`. |
| `warnings` | Partial-export diagnostics, such as skipped missing claim or causal referent refs. |

Base nodes use canonical graph URI strings as exported ids. Base edge ids are
deterministic strings derived from subject URI, predicate URI, object URI, and
graph layer, so repeated exports have stable identity. The base graph stays
generic: causal meaning and evidence interpretation live in overlays.

Supported overlays are:

| Overlay | Semantics |
|---|---|
| `causal` | Inquiry-keyed causal structure: treatment, outcome, boundary roles, inquiry-local node/edge membership, and causal edge kind such as `causes` or `confounds`. |
| `evidence` | Edge-centric claim bundles for proposition-backed edges, including support/dispute counts, evidence semantics, source refs, pre-registrations, interaction terms, falsifications, and cross-hypothesis bridge metadata when present. |

Exports fail for invalid parameters or malformed internal graph structure. They
do not invent missing semantic objects: optional missing referents are skipped
and surfaced in `warnings` so consumers can render partial graphs without
silently hiding data-quality issues.

Dashboard code consumes this shared payload and may add renderer-specific
metadata such as level-of-detail, lens values, style values, encoding metadata,
or reference dates. Those additions belong to the dashboard layer; Science owns
the graph semantics and overlay shape.

## Public Snapshot Distillation

`science distill` creates small Turtle snapshots from public knowledge graph
sources that are too broad to author by hand. These snapshots are generated
artifacts, not project source files.

Use distillation when a project needs a compact reference layer for browsing,
orientation, or graph queries:

```bash
science distill openalex --level subfields
science distill openalex --level topics
science distill pykeen DBpedia50
science distill pykeen PrimeKG --budget 170
```

OpenAlex distillation writes a SKOS-style science hierarchy. PyKEEN
distillation writes a compact RDF view of a named PyKEEN dataset; `--budget`
keeps the highest-rank entities and edges between them for large datasets. If
no `--output` is supplied, snapshots are written under `data/snapshots/`.

Each distillation updates `data/snapshots/manifest.ttl` with the source URL,
version string, generation time, node/triple count, and SHA-256 of the Turtle
file. Treat the manifest as the reproducibility record for generated snapshots.

## Snapshot Import

`science graph import` merges a Turtle snapshot into the project's
`graph/knowledge` layer and records import provenance in `graph/provenance`:

```bash
science graph import data/snapshots/openalex-science-map.ttl
science graph import data/snapshots/primekg-core.ttl
```

Import is additive derived state. If the imported context is wrong or stale,
regenerate the snapshot or rebuild the graph rather than editing
`knowledge/graph.trig` directly.

## Belief Snapshots

`science belief snapshot` appends reproducible belief-state rollups to
`knowledge/belief-snapshots.jsonl`. Use snapshots at review milestones when you
want to preserve the state of support, dispute, fragility, and contestation.

Snapshot rows include the policy identity that produced the belief state:
`policy_id` and `policy_version`. They also record cap and ceiling flags such as
`capped_by_refutation`, `authored_capped`, and `qa_dataset_capped` where
applicable. Snapshot de-duplication includes policy identity, scalar enablement,
scalar config version, claim, date, and input hashes, so a later policy version
can produce a new reproducible row even when the evidence inputs are unchanged.

Rows from older projects that predate explicit belief-policy fields are read as
`core-default` policy version `1`; older rows without cap fields are read with
those caps set to `false`.

## Belief Profile

`science belief profile` lists a read-only epistemic profile for belief-bearing
entities. It reuses the same graph and belief machinery as snapshots and does
not persist new RDF or source metadata.

```bash
science belief profile
science belief profile --format json
science belief profile --kind proposition
science belief profile --label fragile --label no_empirical_data
science belief profile --all
```

Supported kinds are `proposition`, `hypothesis`, and `mechanism`. `--kind` and
`--label` are repeatable; repeated labels use AND semantics. `--all` includes
supported belief-bearing entities even when their profile is otherwise empty or
speculative. Without `--all`, rows are included when they have support, dispute,
diagnostic evidence, resolved bundle membership, active cap flags, or materialized
freshness states that require review.

JSON output emits one row per entity with this shape:

```json
{
  "entity": "proposition:example",
  "kind": "proposition",
  "label": "Short label or text",
  "belief_state": "fragile",
  "contested": false,
  "epistemic_labels": ["fragile", "single_source", "no_empirical_data"],
  "evidence": {
    "support_count": 1,
    "dispute_count": 0,
    "diagnostic_count": 0,
    "source_count": 1,
    "evidence_types": ["expert_judgment"],
    "has_empirical_data": false
  },
  "caps": {
    "authored_capped": false,
    "qa_dataset_capped": false,
    "capped_by_refutation": false
  },
  "freshness_state": null,
  "belief_scalar": null
}
```

`belief_state`, `contested`, and the cap fields are derived from the current
belief result. Evidence counts summarize the units seen by the belief engine.
For bundle rows, `diagnostic_count` is `null` because bundles do not have a
bundle-level diagnostics field. `freshness_state` reflects the materialized
literal when present; missing freshness stays `null`.

Profile labels are derived readings, not authored truth. The v1 label set is:
`speculative`, `fragile`, `supported`, `well_supported`, `contested`,
`single_source`, `no_empirical_data`, `authored_only`, `literature_only`,
`empirical_data_backed`, `authored_capped`, `qa_dataset_capped`,
`capped_by_refutation`, `stale`, and `needs_review`.

When the existing belief scalar feature is enabled, `belief_scalar` contains the
current scalar projection fields. When scalar output is disabled, it is `null`;
the profile command does not invent a fallback score.

## Prose-Derived Reports

When a project uses prose epistemics, decomposition, grounding, and prose health
artifacts are also derived state. They summarize how much authored prose has
been decomposed, promoted, and grounded. They do not replace the source
Markdown, propositions, or evidence lines.

Internal Markdown prose enters the graph through `prose-source:<slug>` source
records and validated decomposition artifacts under
`data/prose-decompositions/<slug>/`. Promotion records provenance with both the
source ref and an `annotation:data/prose-decompositions/...#<unit_id>` ref.

Grounding is a read model over promoted units and the current graph. It writes
latest reports under `data/prose-grounding/<slug>/grounding.json`; rows can be
`grounded`, `below_floor`, `unbacked`, `unpromoted`, `skipped`, or `stale`.
The grounding floor and belief-policy identity travel with the report.

Project-level prose health is the downstream consumer contract. It reads
`data/prose-health/manifest.json` plus decomposition and grounding artifacts,
then writes `data/prose-health/prose-health.json` with promotion, grounding,
and strict-grounding coverage. Downstream renderers should consume this P4
artifact rather than parsing P2/P3 storage internals.

For the full framework contract, command list, and artifact details, see the
[prose epistemics checkpoint](../audits/plans-cleanup/2026-06-17-prose-epistemics-checkpoint.md).

## Patch Workbenches

`<patch>.workbench.yaml` is an editable normalized projection over proposition
and evidence-line entities. It is useful for graph-shaped authoring, but the
entity layer remains the durable epistemic store.

Compile lifts rows into entities: id-less relational rows receive proposition
IDs, inline evidence stubs become evidence-line entities, and empirical stubs
without `dataset_usage` are staged with `belief_eligible: false`. A check
normalizes the committed workbench against a scratch graph and fails on drift;
it does not treat the workbench as a second source of epistemic truth.

Do not put authored belief, authored `edge_status`, row-level
`quantitative_result`, or persistent embedded support arrays in a workbench.
`quantitative_result` belongs inside an evidence stub and then on the generated
evidence-line entity.
