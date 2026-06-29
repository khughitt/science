# Open Targets associations reference graph — design

- Status: design (approved for planning)
- Date: 2026-06-01
- Related:
  - `docs/plans/historical/2026-05-31-bio-reference-graph-design.md` — the `bio.reference_graph` resource model (RG1–RG5)
  - `docs/plans/historical/2026-05-26-bio-data-architecture-umbrella-design.md` — bio data umbrella
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
- Key normalization (every id is a **hard gate** — a non-conforming id aborts the
  build, counted as an id-form / unknown-prefix reject per §7.5, never silently
  passed through):
  - target id **must** match `^ENSG[0-9]+$` → `ENSEMBL:<id>`; anything else is an
    id-form error.
  - disease id **must** match `^(EFO|MONDO|HP|Orphanet|OTAR|…)_[0-9A-Za-z]+$`
    where the prefix is in the frozen `member_key_space.prefixes` → colonized
    CURIE (`EFO:…`, `MONDO:…`, …); an out-of-set prefix is an unknown-prefix
    error. (The exact disease-prefix set is discovered by the preflight, §7.6.)
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

**Canonical edge orientation.** Every edge is `subject = target CURIE`,
`object = disease CURIE`, `predicate = associated_with`. Edges are emitted sorted
by `(subject, predicate, object)`, and a duplicate normalized `(subject,
predicate, object)` triple is a **hard error** (the build aborts rather than
silently de-duplicating) — duplicate `(targetId, diseaseId)` rows in the source
are surfaced by the preflight (§7) first.

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

**Score validation (hard gate) and canonical JSON.** OT overall scores are a
0–1 heuristic. The build asserts, per edge: `score` is **present, numeric, and
finite** (no `null`/`NaN`/`inf`) and `0.0 <= score <= 1.0`; any violation aborts
the build (not a tally — a malformed score is a structural defect). `graph.jsonl`
is written with a **fixed key order** (`subject, predicate, object, score`) and
**stable separators** (`json.dumps(..., separators=(",", ":"))`, no trailing
whitespace, `\n`-terminated, UTF-8), and floats are formatted deterministically
(e.g. `repr`/`float` round-trip), so the artifact — and therefore its datapackage
hash — is byte-reproducible across runs of the same pinned release.

**RG2 returns *unscored* incident edges.** `ReferenceGraphEdge`
(`subject, predicate, object, evidence, dataset_usage`) has no score field, and
the RG2 payload serializer emits only those columns — so even when
`edge_resource` is declared (§8), incident-edge resolution returns the target↔
disease *adjacency* without the score. The scored edge (target, disease, score)
lives only in `graph.jsonl`; a scored query is answered by reading that artifact
directly. Promoting score to a first-class edge field (or `evidence`-encoded
metadata) is deferred — it is an RG schema change, out of scope for the first
recipe. This is a second reason the declare-`edge_resource` branch (§8) buys
little for OT.

## 6. Artifacts and pinning

Source: Open Targets Platform per-version **immutable** FTP parquet datasets
(`target`, `disease`, `association_overall_direct` — exact directory paths and
dataset names vary by release and are confirmed by the preflight). Because OT
ships each dataset as a directory of parquet part-files (not a single file), the
integrity anchor is multi-part:

- `fetch.py` pins **each parquet part-file's `sha256` + `bytes`** in
  `lockfile.yaml`, and rejects any non-dated / "latest" / mutable URL (analogous
  to the GO `fetch.py` mutable-URL guard).
- `build.py` deterministically synthesizes, from the pinned parquet, via an
  **in-memory normalize + sort** pipeline. The original ~11 M-row estimate that
  motivated a bounded-memory external sort was corrected by the §7 preflight: the
  real `association_overall_direct` count is **4,492,971** edges, which comfortably
  fits in memory as interned `(subject, object, score)` tuples. This is also the
  approach the existing `dataset:go` and `dataset:mondo` recipes take (both sort
  their edge set in memory), so it keeps the reference-graph recipe family
  consistent. The chosen pipeline:
  1. **Normalize** — read the association parquet (pyarrow), join target/disease
     ids, apply the §3 id gates and §5 score gate, and collect each normalized
     `(subject, object, score)` triple into an in-memory list.
  2. **Sort** the collected triples in memory via a single `edges.sort()` keyed on
     `(subject, object)` — deterministic order independent of parquet part/row-group
     order.
  3. **Emit** `graph.jsonl` by streaming the sorted list: write one canonical JSON
     line per triple (§5), and **reject adjacent duplicate** `(subject, predicate,
     object)` triples as a hard error (adjacency suffices after the sort).
     Collect the participating member set in the same pass to build `nodes.csv`.

  The **bounded-memory external-sort / spill-to-disk** variant (normalize to a temp
  TSV → `sort` with a fixed `LC_ALL=C` collation, or a pyarrow/duckdb spill — then
  stream-emit) remains the documented fallback: adopt it if a future Open Targets
  release grows the overall-direct edge count enough to pressure available memory.
  - `graph.jsonl` — `graph_format: jsonl_edges`; every line a full edge
    (`subject, predicate, object, score`, canonical per §5). This is the canonical
    `graph_resource`; RG1 validation **only existence-checks** it (its
    datapackage hash is the real integrity pin), so it can hold the full edge set
    at any size.
  - `nodes.csv` — the validated node index (`node_index_resource`), sorted by
    `member_key`.
  - `edges.csv` — the edge projection (`edge_resource`); **on the expected
    omit branch (§8) it is neither written nor registered in `datapackage.yaml`**
    (`graph.jsonl` is then the *only* full edge artifact — no duplicated ~GB
    file). Written only if §8 resolves to the declare branch.
  - `build_summary.json` — deterministic counts: `member_count`, `edge_count`,
    `kind_counts` (target/disease), `prefix_counts` (per disease prefix),
    participating-target / participating-disease counts, and the fallback /
    reject tallies from §7 (join misses, duplicate triples, unknown-prefix rows).

**Build self-verification (mandatory, independent of `commons validate`).**
Because `commons validate` only existence-checks `graph_resource` and only
compares `edge_count` *when `edge_resource` is declared* — and the OT edge set is
omitted on the expected path (§8) — the build must assert its own integrity so
the most important count cannot drift silently:

- `edge_count` (frontmatter / summary) **==** `graph.jsonl` line count, computed
  by the build itself.
- Every `subject` and `object` appearing in `graph.jsonl` **is present** in
  `nodes.csv` (no dangling endpoints), and conversely every node participates in
  ≥1 edge (no orphan members, per §3).
- `member_count` **==** `nodes.csv` row count **==** participating-target +
  participating-disease counts.

These run as build assertions (hard failures) and are re-checked by the recipe
test suite over the synthetic fixture.

**Parquet engine.** The recipe reads Open Targets parquet via **`pyarrow`**
(`pyarrow.parquet`). Exact row counts come from parquet metadata
(`ParquetFile(path).metadata.num_rows`) without materializing the table; the
normalize stage (pipeline step 1) reads the parquet parts and collects the
~4.49 M normalized triples in memory, which the in-memory `edges.sort()` (step 2)
then orders. `pyarrow` is added to **`science/pyproject.toml`**
with **`science/uv.lock`** updated — the same project the GO/MONDO recipes run
under (`uv run --frozen --project ~/d/science/science …`); this recipe does **not**
introduce a separate environment. Synthetic parquet test fixtures are written
with the same engine.

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
   association dataset. Releases post-25.03 changed paths and are **Parquet-only**;
   the dataset directory is `association_overall_direct` (snake_case) under the
   newer layout (older releases used `associationByOverallDirect`). The preflight
   confirms the concrete paths for the chosen version (expected: 25.09 or later).
2. Per parquet part-file: relative path, `sha256`, `bytes`.
3. **Exact row counts** (from parquet metadata): total targets, total diseases,
   and total overall-direct associations. Published 25.09 metrics list
   **10,989,518** target–disease associations, so the §8 decision is expected to
   land on the **omit-`edge_resource`** branch — the preflight confirms the live
   number rather than assuming it.
4. **Participating-member counts** (the actual member surface, per §3): distinct
   `targetId` values and distinct `diseaseId` values appearing in the
   overall-direct association set (these, not the full target/disease catalog
   sizes, become `member_count`).
5. **Integrity gates / fallback tallies** — each reported, and each is either a
   hard build gate or an explicit counted-and-surfaced tally (never a silent
   drop):
   - target/disease **join misses**: association rows whose `targetId` /
     `diseaseId` is absent from the `target` / `disease` index.
   - duplicate `(targetId, diseaseId)` rows in the association set.
   - **id-form / unknown-prefix** rows: target ids that fail `^ENSG[0-9]+$`, or
     disease ids whose prefix is outside the frozen `member_key_space.prefixes`
     (§3). Both are hard gates, not silent drops.
6. The exact set of disease-id **prefixes** present (to freeze
   `member_key_space.prefixes`).
7. The actual target/disease id string forms and the association schema column
   names (e.g. `targetId`, `diseaseId`, `score`).
8. The license string as published for that release (expected CC0-1.0).

## 8. `edge_resource` decision (preflight-count driven)

`commons validate` and RG2 (`resolve_reference_graph_member_payload`) both
**fully load** the declared edge CSV into memory. The overall-direct row count
(from §7.3) decides:

- **≤ ~2 M edges → declare `edge_resource`** (full `edges.csv`). RG1 validates
  `edge_count`; RG2 resolves incident edges — though those payload edges are
  *unscored* (§5).
- **> ~2 M edges → omit `edge_resource`.** `validate`/RG2 stay light; the full
  edge set is still hash-pinned in `graph.jsonl`; RG2 returns node-only payloads
  (`incident_edges=()`, a supported, documented degradation). RG2-over-OT
  incident resolution is then deferred to a later increment (e.g. an indexed /
  streaming edge reader, ideally with score promoted to a first-class field).

**Expected outcome: omit.** Published 25.09 metrics (~10.99 M associations, §7.3)
put OT well above the ~2 M threshold, so omit is the normal path; declare is a
contingency for a future smaller subset. The declare branch is doubly weak for
OT — it would load ~11 M rows on *every* `commons validate` *and* still return
unscored incident edges (§5) — so the bar for choosing it is high. The build
self-verification (§6) — not `commons validate` — is what guarantees
`edge_count`/endpoint integrity on the omit path. The chosen branch is recorded
in `entity.md` and the recipe README, with `edge_count` always set from the
build-computed `graph.jsonl` line count.

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
1a. Add `pyarrow` to **`science/pyproject.toml`** and update **`science/uv.lock`**
   (`uv add pyarrow --project ~/d/science/science`) — the same env the GO/MONDO
   recipes run under (`uv run --frozen --project ~/d/science/science`); no separate
   recipe environment. Needed to read parquet and write synthetic parquet fixtures.
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
