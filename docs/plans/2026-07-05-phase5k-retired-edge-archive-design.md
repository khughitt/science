# Phase 5k Design: Retired Edge File Archive

Date: 2026-07-05

## 1. Context

Phase 5f removed retired `*.edges.yaml` files from default DAG render,
validate, audit, and inventory paths. Phase 5g added a read-only migration
planner for those retired files. Phase 5h added a workbench scaffold surface.
Phase 5i applied reviewed workbenches into proposition and evidence-line
entities. Phase 5j then made migration closure a derived view over live
proposition lineage.

The first dogfood target, `~/d/protein-landscape`, now has six migrated rows in
`doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml`. The live
propositions carry:

- `legacy_patch: h01-multi-manifold-protein-universe`
- `legacy_edge_id: <retired row id>`
- matching `subject` / `object`

`science dag retired-edge-migration-plan` therefore reports all six retired
rows as `closed`, and `science dag scaffold-retired-edge-workbench` reports
`complete` without writing a new workbench. The retired YAML file is no longer
authoritative, but it still sits in the active DAG directory and remains visible
to explicit retired-edge inspection.

Phase 5k is the first safe mutation of that retired DAG source: once every row
in a retired edge file is closed by live proposition lineage, move the retired
file out of `doc/figures/dags/` into a project archive path.

## 2. Goal

Add a reusable toolkit feature for archiving closed retired DAG edge files:

```bash
science dag archive-retired-edges \
  --dag <slug> \
  --project <project-root> \
  [--apply] \
  [--format table|json]
```

Without `--apply`, the command is a read-only plan. With `--apply`, it moves a
fully closed retired edge file to an archive path and writes a small manifest
describing the move.

Protein-landscape is the acceptance fixture for the first apply. Other projects
with retired edge files are follow-up migration work, not part of the initial
Phase 5k apply.

## 3. Non-Goals

- Do not archive files that still have `ready`, `blocked`, or `skipped` rows.
- Do not edit retired YAML in place to add `migration_status` or closure
  metadata.
- Do not mutate propositions, evidence lines, DOT files, graph output, or
  workbench files.
- Do not extend the entity archive index to cover non-entity DAG artifacts.
- Do not create a generic non-entity archive framework in Phase 5k.
- Do not bulk-apply archive moves across every known project.
- Do not make `science dag retired-edges` scan archived retired edge files by
  default.

## 4. Approaches Considered

### A. Dedicated DAG Retired-Edge Archive Surface

Chosen. Add a narrow DAG command that moves only fully closed retired
`*.edges.yaml` files from the active DAG directory to
`archive/dag-retired-edges/`. The command is explicit, deterministic, and
reversible through git. It keeps retired DAG source archival separate from the
entity archive index because retired edge files are not entities.

### B. Extend the Entity Archive Index to Non-Entity Artifacts

Rejected for Phase 5k. A single archive system is appealing long-term, but the
current index is explicitly entity-oriented: it resolves entity ids, preserves
entity aliases, and materializes archived entity stubs. Retired DAG edge files
are source artifacts, not entity records. Generalizing that model would expand
the blast radius of a small DAG cleanup feature.

### C. Mark Retired Files Closed In Place

Rejected. Adding `migration_status: closed` to retired YAML would revive retired
YAML as writable migration state and keep obsolete source files in the active
DAG directory. Closure already exists in live proposition lineage and should not
be duplicated inside retired YAML.

### Open Decision: Archive Destination Path

Approach A is chosen, but *where* the closed file lands is a deliberate choice
this phase must make explicitly, because the two candidates differ in how
visible the archived file stays to unrelated project-wide tooling.

- **Option 1 — top-level `archive/dag-retired-edges/`.** A new top-level
  location that signals "this file is dead and no longer part of the DAG
  directory tree," matching the Section 1 goal of moving the file *out of*
  `doc/figures/dags/`. Downside: `archive/` is not on any scanner's skip list,
  so project-wide walkers still visit it — the `science entities remove`
  reference scanner (`_REFERENCE_SCAN_SKIP_DIRS` does not include `archive`) and
  `data_audit`'s `os.walk` both read files under it. Nothing in Section 9
  breaks, but "invisible after archive" is only true for the DAG inspection
  surfaces, not for every tool.

- **Option 2 — co-located `doc/figures/dags/_archive/`.** Matches the existing
  archive idiom: the entity archive lives at `entities/_archive/`, and
  underscore-prefixed segments are what convention-aware scanners already skip
  (`entity_scan.iter_entity_markdown`). Because the default DAG scanners use a
  non-recursive `dag_dir.glob("*.edges.yaml")`, an `_archive/` subdirectory is
  still excluded from them. Downside: the file stays physically *inside* the DAG
  directory tree, which reads as less final than Section 1 implies.

Neither extends the entity archive index (Approach B stays rejected either way);
this is purely about the destination directory. The default recommendation is
**Option 1** for the clearer "out of the DAG tree" signal, on the condition that
the phase accepts that non-DAG project-wide walkers still see the archived file.
If scanner-invisibility matters more than physical relocation, switch to
Option 2. The rest of this document is written against Option 1's paths; a
switch to Option 2 changes only the literal directory prefix, not the planning,
manifest, or apply semantics.

## 5. Planning Semantics

The archive planner computes one candidate for the requested DAG slug. It first
classifies filesystem state for:

- source: `doc/figures/dags/<slug>.edges.yaml`;
- archive: `archive/dag-retired-edges/<slug>.edges.yaml`;
- manifest: `archive/dag-retired-edges/<slug>.edges.yaml.archive.json`.

Filesystem-state rules:

1. Source exists, archive absent, manifest absent: inspect active retired rows.
2. Source absent, archive exists, manifest exists: `already_archived`.
3. Source exists and archive exists: `ambiguous_state`.
4. Archive exists without manifest, or manifest exists without archive:
   `ambiguous_state`.
5. Source absent and no complete archive record: `blocked` with
   `retired-edge-file-missing`.

For an active source file, the planner uses the existing
`build_retired_edge_migration_plan(project_root, dag=slug, ...)` machinery to
classify every row:

1. A file with zero migration rows is blocked as `empty-retired-edge-file`.
2. If any row is `ready`, `blocked`, or `skipped`, the archive candidate is
   blocked and the plan reports the row statuses and blockers.
3. If every row is `closed`, the candidate is `ready_to_archive`.

Closure remains derived from live proposition lineage. The archive command does
not trust retired YAML metadata and does not introduce a second closure record.

The planner should expose a stable JSON payload:

```json
{
  "dag": "h01-multi-manifold-protein-universe",
  "status": "ready_to_archive",
  "source": "doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml",
  "archive": "archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml",
  "manifest": "archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml.archive.json",
  "closed_rows": 6,
  "closed_by": [
    "proposition:snapshots-affects-pc1"
  ],
  "blockers": []
}
```

Status vocabulary:

- `ready_to_archive`
- `blocked`
- `already_archived`
- `ambiguous_state`

## 6. Archive Layout

The active retired file moves from:

```text
doc/figures/dags/<slug>.edges.yaml
```

to:

```text
archive/dag-retired-edges/<slug>.edges.yaml
```

The command writes a manifest next to the archived file:

```text
archive/dag-retired-edges/<slug>.edges.yaml.archive.json
```

Manifest fields:

- `schema_version`
- `dag`
- `original_path`
- `archived_path`
- `closed_by`
- `closed_rows`
- `sha256`
- `archived_at`
- `tool`
- `reason: "all-retired-edges-closed"`

Paths stored in the manifest should be project-relative and use `~/d/` only in
documentation examples, not absolute machine paths.

Concrete field values follow existing precedent: `schema_version: 1` (as in
`archive.py`), `tool: "science dag archive-retired-edges"`, and `sha256`
computed with the established `hashlib.sha256(data).hexdigest()` idiom. There is
no existing per-file `.archive.json` sidecar in the codebase — the closest
precedents are the single `manifest.json` from `science project serialize` and
the append-only `archive-index.jsonl` from the entity archive — so this sidecar
format is new and owned by this feature.

`archived_at` must be deterministic for tests. Follow the archive layer's
clock-injection convention rather than reading the wall clock inside the archive
function: the pure archive function takes an injected `now: str | None = None`
argument (as `archive_entities(..., now=...)` does), and only the CLI command
body reads the clock —
`datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` — and threads it in.
Tests then pass a fixed `now` string and assert the manifest byte-for-byte.

## 7. Apply Semantics

Apply is a narrow filesystem mutation:

1. Recompute the archive plan from live project state.
2. Refuse to apply unless the candidate is `ready_to_archive`.
3. Compute the source file SHA-256 from the bytes that will be moved.
4. If apply is operating from an in-memory dry-run plan, confirm the source
   bytes still match the planned SHA-256 before moving.
5. Refuse to overwrite an existing archive file or manifest.
6. Move the retired edge file to the archive path.
7. Write the manifest.
8. If manifest writing fails, move the retired file back to its original path.

The command does not claim atomic rollback across process crashes. Its
preflight and state classification make partial states explicit:

- If source exists and archive does not exist: normal plan/apply path.
- If source is absent and archive plus manifest exist: `already_archived`.
- If both source and archive exist: `ambiguous_state`.
- If archive exists without manifest, or manifest exists without archive:
  `ambiguous_state`.

Re-running apply after a successful move should report `already_archived`, not
fail. Re-running apply in an ambiguous state should fail loud and require manual
inspection.

## 8. Diagnostics and Command Surface

Dry-run table output should make the decision readable:

```text
Retired edge archive plan: h01-multi-manifold-protein-universe ready_to_archive
  source: doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml
  archive: archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml
  closed_rows: 6
```

Blocked output should identify the row statuses that prevented archive:

```text
cannot archive retired edge file: 1 ready, 0 closed, 0 blocked, 0 skipped
```

The JSON output should include enough detail for tests and downstream project
scripts:

- source path;
- archive path;
- manifest path;
- status;
- closed row count;
- `closed_by` ids;
- blockers;
- apply result fields such as `applied: true | false`.

The command should live under the flat DAG CLI convention as
`science dag archive-retired-edges`, not as a nested `retired-edges archive`
subcommand.

## 9. Interaction With Existing Surfaces

After a successful archive:

- `science dag validate --dag <slug>` remains OK because default DAG validation
  uses DOT topology plus proposition edges.
- `science dag retired-edge-migration-plan --dag <slug>` fails with the existing
  missing retired file message, or a direct equivalent stating that no active
  retired edge file exists.
- `science dag scaffold-retired-edge-workbench --dag <slug>` fails with a direct
  missing retired file message and must not recreate migration work.
- `science dag retired-edges --dag <slug>` does not scan
  `archive/dag-retired-edges/` by default.

A future flag may inspect archived retired edge files, but Phase 5k keeps the
default inspection surface focused on active retired migration debt.

## 10. Error Handling

All unsafe states fail before moving files:

- missing active retired file with no archive record;
- empty retired edge file;
- any non-closed row;
- destination file exists;
- destination manifest exists;
- source/archive coexistence;
- archive/manifest mismatch;
- archive path derivation escaping the project root.

The archive command should not silently treat these as no-ops. The only no-op
state is a complete prior archive with source absent and both archive file and
manifest present.

## 11. Testing

Unit and CLI tests should cover:

- ready closed file plans as `ready_to_archive`;
- files with ready/blocked/skipped rows block archive;
- empty retired files block archive;
- dry run does not move files or write a manifest;
- apply moves the file and writes a manifest with the expected SHA-256;
- apply refuses destination collisions;
- apply rollback restores the source when manifest writing fails;
- re-run after successful apply reports `already_archived`;
- source/archive coexistence reports `ambiguous_state`;
- default `retired-edges` and migration planning do not scan archived files;
- DAG validation remains proposition-backed after the retired file is archived.

The real-project smoke test should apply the command to
`~/d/protein-landscape` for `h01-multi-manifold-protein-universe` and verify:

- **baseline first:** `science dag validate --dag h01-multi-manifold-protein-universe`
  passes *before* archiving. Section 9's claim that validate stays OK afterward
  rests on the retired `.dot` still validating without its `.edges.yaml`; the
  baseline confirms the DAG already validates independently of the retired file,
  so a post-archive failure cannot be misattributed to the move (and a
  pre-existing failure is caught before any mutation);
- dry run reports `ready_to_archive` and `closed_rows: 6`;
- apply moves the retired file into `archive/dag-retired-edges/`;
- the manifest lists the six closing propositions;
- re-run reports `already_archived`;
- `science dag validate --dag h01-multi-manifold-protein-universe` remains OK;
- the protein-landscape change is committed directly in that project.

## 12. Follow-Up Work

After protein-landscape is clean, inspect other projects with active retired
edge files and queue migrations individually. Phase 5k should provide the
toolkit surface those follow-ups use, not bundle every project cleanup into the
first implementation.

Potential future additions:

- `science dag retired-edges --include-archived`;
- bulk archive planning across all DAG slugs;
- a generic project artifact archive framework;
- richer manifest validation or repair tooling.
