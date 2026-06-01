# Open Targets associations reference graph — design

- Status: design (approved for planning)
- Date: 2026-06-01
- Related:
  - `docs/plans/2026-05-31-bio-reference-graph-design.md` — the `bio.reference_graph` resource model (RG1–RG5)
  - `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — bio data umbrella
  - `docs/plans/2026-06-01-go-reference-graph-commons-ingestion-plan.md` — the GO recipe, used as the template

## 1. Goal

Add Open Targets as the **third** `bio.reference_graph` commons dataset (after
`dataset:mondo` and `dataset:go`) and the **first association graph** — the
resource the reference-graph design (§8, open question 2) deferred until a real
target was in hand. This validates the association-graph extension point with a
faithful, hash-pinned projection of a single immutable Open Targets release.

Slug: `opentargets-associations` (id `dataset:opentargets-associations`).

## 2. Relationship to the existing `opentargets-platform` dataset

A different, pre-existing commons dataset `dataset:opentargets-platform` already
exists: an MM30-specific, MM-family-**filtered** annotation slice
(`mm-associations` / `mm-drugs` / `mm-tractability`, version `25.03`, built by an
mm30 project script, recipe stubbed "back-fill needed", `access.verified: false`).
It is a narrow project annotation product, not a general reference graph.

This design does **not** touch it. The reference graph is a new, distinct dataset
under a new slug. No collision, no reorganization of the existing slice.

## 3. Member model (Model A — entity nodes)

Nodes are the biological entities; associations are edges.

- **Members** = targets ∪ diseases that participate in at least one selected
  association. No orphan nodes — every member has ≥1 incident edge, so
  `member_count` is meaningful and the node index stays self-consistent with the
  edge set.
- `member_kind ∈ {target, disease}`.
- `member_key_space`: `kind: curie`, `resolution_status: resolved`,
  `prefixes: [ENSEMBL, EFO, MONDO, HP, Orphanet, …]` — the exact disease-prefix
  set is enumerated by the preflight (§7) and frozen into the entity.
- Key normalization:
  - target `ENSG…` → `ENSEMBL:ENSG…`
  - disease `EFO_…` / `MONDO_…` / `HP_…` / `Orphanet_…` / `OTAR_…` → colonized
    CURIE (`EFO:…`, `MONDO:…`, …).
- `status = active` for every node. Open Targets does not track entity
  deprecation in these tables; obsolete disease terms are the disease ontology's
  concern (MONDO/EFO reference graphs), not OT's. `replaced_by` is therefore
  always empty.
- Node extra (preserved, unvalidated) columns: `symbol` and `biotype` for
  targets, `name` for diseases. These ride in the node CSV for convenience; the
  RG1 node contract only requires `member_key, member_kind, label, status,
  replaced_by, dataset_usage`.

Model B (reified associations keyed by deterministic tuples) was considered and
rejected for the first recipe: it invents a tuple-key format, ~doubles node
count, and adds reification edges, with no payoff until per-association
provenance is itself addressable (RG3+ / B materialization).

## 4. Edge scope

`associationByOverallDirect` only:

- **Overall** score (one score per (target,disease) pair → one edge), not
  per-datatype. Per-datatype scores (genetic / somatic / drug / pathway /
  literature / animal-model / expression) are deferred.
- **Direct** associations only (explicitly-evidenced links), not indirect.
  Indirect propagates each association up the EFO/MONDO disease ontology (a
  target tied to a child disease becomes tied to every ancestor) → tens of
  millions of semantically *derived* edges. Direct is the clean identity set;
  propagation is reconstructable later by composing this graph with the
  MONDO/EFO disease-ontology reference graph.
- `predicate = associated_with` (a stable literal label, mirroring GO's bare
  `is_a`).

## 5. Score handling

The RG1 edge contract (`ReferenceGraphEdge`) has required columns
`subject, predicate, object` plus optional `evidence` and `dataset_usage`; there
is **no first-class numeric score field**. The OT overall score therefore rides
as:

- a field on each line of the canonical `jsonl_edges` artifact (source of
  truth), and
- an extra `score` column on the `edges.csv` projection — preserved through the
  CSV, ignored by the RG1 parser.

This mirrors the GO recipe, where the rich upstream `go.json` was the source and
`edges.csv` was the thin validated projection. The score is never silently
dropped; it is simply not part of the validated edge contract.

## 6. Artifacts and pinning

Source: Open Targets Platform per-version **immutable** FTP parquet datasets
(`target`, `disease`, `association_overall_direct` — exact directory paths and
dataset names vary by release and are confirmed by the preflight). Because OT
ships each dataset as a directory of parquet part-files (not a single file), the
integrity anchor is multi-part:

- `fetch.py` pins **each parquet part-file's `sha256` + `bytes`** in
  `lockfile.yaml`, and rejects any non-dated / "latest" / mutable URL (analogous
  to the GO `fetch.py` mutable-URL guard).
- `build.py` deterministically synthesizes, from the pinned parquet:
  - `graph.jsonl` — `graph_format: jsonl_edges`; every line a full edge
    (`subject, predicate, object, score, …`). This is the canonical
    `graph_resource`; RG1 validation **only existence-checks** it (its
    datapackage hash is the real integrity pin), so it can hold the full edge set
    at any size.
  - `nodes.csv` — the validated node index (`node_index_resource`).
  - `edges.csv` — the edge projection (`edge_resource`); **declared or omitted
    per §8**.
  - `build_summary.json` — deterministic counts: `member_count`, `edge_count`,
    `kind_counts` (target/disease), `prefix_counts` (per disease prefix),
    plus any fallback tallies.

Bulk artifacts live outside the git repos at
`~/d/science-commons-data/opentargets-associations/`, wired via a per-slug entry
in `~/.config/science/data.yaml`. Only the recipe, the hash-pinned
`datapackage.yaml`, and `entity.md` are committed. Recipe scripts default their
output to `/data/science-commons/<slug>` and must be run with an explicit
`--output-dir` / `--data-dir` pointing at the data-root path; a science-commons
*worktree* is invisible to `resolve_commons_root` / `validate`, so this recipe
is built on an in-place feature branch.

## 7. Preflight (real-data grounding)

Network egress is blocked on the controller (matches MONDO/GO); the preflight
runs as a subagent that **cd's into the recipe worktree path and verifies the
branch** before any work. It must return:

1. The latest **pinnable** OT release (dated/versioned, immutable) and the exact
   FTP directory layout for `target`, `disease`, and the overall-direct
   association dataset (the dataset name changed across releases — e.g.
   `associationByOverallDirect` vs `association_overall_direct`).
2. Per parquet part-file: relative path, `sha256`, `bytes`.
3. **Exact row counts**: targets, diseases, and overall-direct associations
   (this number decides §8).
4. The exact set of disease-id **prefixes** present (to freeze
   `member_key_space.prefixes`).
5. The actual target/disease id string forms and the association schema column
   names (e.g. `targetId`, `diseaseId`, `score`).
6. The license string as published for that release (expected CC0-1.0).

## 8. `edge_resource` decision (preflight-count driven)

`commons validate` and RG2 (`resolve_reference_graph_member_payload`) both
**fully load** the declared edge CSV into memory. The overall-direct row count
(from §7.3) decides:

- **≤ ~2 M edges → declare `edge_resource`** (full `edges.csv`). RG1 validates
  `edge_count`; RG2 answers the headline query ("all disease associations for
  target X" / "all targets for disease Y") by incident-edge resolution.
- **> ~2 M edges → omit `edge_resource`.** `validate`/RG2 stay light; the full
  edge set is still hash-pinned in `graph.jsonl`; RG2 returns node-only payloads
  (`incident_edges=()`, a supported, documented degradation). RG2-over-OT
  incident resolution is then deferred to a later increment (e.g. an indexed /
  streaming edge reader).

Either branch pins the full graph; only the validated-CSV incident-resolution
path is at stake. The chosen branch is recorded in `entity.md` and the recipe
README.

## 9. Entity frontmatter (parity with GO/MONDO)

`entity.md` carries the full `science-entity-base/1.0 + dataset/1.0 +
bio.reference_graph/1.0` frontmatter, including: `version: "1.0.0"`,
`graph_resource: graph`, `graph_format: jsonl_edges`, `member_key_space`
(§3), `node_index_resource: nodes`, `edge_resource: edges` (only if §8 declares
it), `member_count`, `edge_count`, `license: CC0-1.0`, `origin: external`,
`source_class: reference`, `status: active`, `tier: use-now`,
`access.verification_method: retrieved`, and an `update_cadence: quarterly`.

## 10. Out of scope (explicit)

- Indirect (ontology-propagated) associations.
- Per-datatype association scores.
- Drugs / tractability / known-drug tables (the existing `opentargets-platform`
  slice already covers the MM use case; a general tractability layer is separate
  future work).
- Reified per-association members (Model B) and per-association provenance / B
  materialization (RG3+).
- Any change to `dataset:opentargets-platform`.

## 11. Execution plan shape

Mirrors the GO ingestion:

1. Preflight subagent (§7) → ground the plan with real numbers; resolve §8.
2. Subagent-driven-development on **in-place feature branches** (a science-commons
   worktree is invisible to `resolve_commons_root` / `validate`), TDD per task:
   `fetch.py`, `build.py` + hermetic `test_*` over a tiny synthetic parquet/edge
   fixture, `build_datapackage.py`, `datapackage.yaml`, `entity.md`, README,
   `lockfile.yaml`.
3. Run the recipe against the pinned release into the data-root; `commons
   validate --slug opentargets-associations`; RG1 parse + (if §8 declares edges)
   RG2 payload spot-check.
4. Mark `dataset:opentargets-associations` implemented in the reference-graph
   design (§9 phasing / RG4 row) and the umbrella doc.
5. `finishing-a-development-branch`; user pushes to origin.
