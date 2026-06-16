# Entity Consolidation P3 — Archive Tier (Design)

> Part of the Entity Consolidation & Archive series. P1 (lifecycle visibility) and
> P2 (consolidation-candidate detector) shipped. This is **P3 = Tier 2 (archive
> tier)**. The semantic-cluster *digest* consolidation (Tier 3) and
> `consolidate --apply` (Tier 4) remain **P4**. Master design:
> `~/d/science/docs/plans/2026-06-15-entity-consolidation-and-archive-design.md`
> (§4 Tier 2). Named "consolidation / archive", never "distill".

**Goal:** relocate hidden-status entities out of the canonical scan into a tracked,
scan-excluded `entities/_archive/` tree, recording each in an append-only index so
their IDs stay resolvable — losslessly, reversibly, and without ever rehydrating
archived markdown as live entities.

---

## 1. Scope & the two-axis visibility model

**In scope (P3):**
- A single shared entity-markdown scanner (`entity_scan.py`) that skips the archive.
- The reserved-path contract (`_`-prefixed segments under `entities/`).
- `entities/_archive/archive-index.jsonl` — append-only, fold-to-active, the SSOT
  for archived-id resolution.
- Status-driven `science entities archive` / `science entities unarchive`
  mutators (report-then-apply).
- Archive-aware reference resolution (index-only) wired into `science validate`
  and graph build, plus a graph tombstone stub node.
- `science search --archived` and a location-axis `--include-archived` flag.

**Out of scope (→ P4):** the cluster-digest entity, member demotion via digest,
consumer digest substitution, and `science entities consolidate --apply`.

**Two-axis visibility model** — the central mental model, and why P1 status-hide
and P3 relocation are *different operations*:

| Axis | Introduced | Mechanism | Effect |
|------|-----------|-----------|--------|
| **1 — status** | P1 | `is_default_visible(status)`, `_HIDDEN_STATUSES={superseded,archived}` | hides from *views*; file still **scanned** and resolvable |
| **2 — location** | P3 | relocation into `entities/_archive/` + scan-skip | removes file from **scanning entirely** (strictly stronger) |

The axes are orthogonal. `--include-hidden` (P1) overrides axis 1; `--include-archived`
(P3) overrides axis 2. Seeing a relocated entity in a view therefore requires
**both** flags, because a relocated entity is also hidden-status.

---

## 2. Module structure

- **New `science_tool/entity_scan.py`** — dependency-light **leaf** (stdlib only),
  the **sole sanctioned** recursive scanner of canonical entity markdown. After P3,
  any direct `entities/**/*.md` rglob elsewhere is a bug (guard test enforces).
  - `iter_entity_markdown(entities_root: Path, *, include_archived: bool = False) -> Iterator[Path]`
- **New `science_tool/archive.py`** — `ArchiveEntry` / `ArchiveIndex` models; index
  read/append/fold; `load_archive_index()`; relocate/restore; the report-then-apply
  `archive_entities()` / `unarchive_entities()`; and `verify_archive()` (the
  reconciler used by the validate subcheck).
- **Extensions:**
  - `entities.py::_resolve_local_home` — reserved-path guard.
  - `validate/checks/cross_references.py` — union archive resolvable-ids; new
    archive-verify subcheck.
  - graph `ReferenceResolver` (`graph/sources.py` / `graph/materialize.py`) —
    archive-aware resolution + tombstone stub node.
  - The 6 direct scan sites routed through `entity_scan` (see §3).
  - CLI: `science entities archive` / `unarchive`; new top-level `science search`.

---

## 3. Shared scanner & reserved-path contract

**The scan-skip rule (two tiers):**
- Any path containing a `_`-prefixed segment **below** the entities root is skipped.
- **`entities/_archive/`** is the one *conditionally*-skipped subtree:
  `include_archived=True` un-skips **only `entities/_archive/**`**. All **other**
  `_`-prefixed segments stay skipped unconditionally (reserved, not archive).

**Comprehensive coverage** — route all six direct scan sites through
`iter_entity_markdown`. `list_entities` and curate `build_inventory` already funnel
through `MarkdownAdapter.discover` (via `load_project_sources`), so fixing the
adapter covers them transitively. The direct sites needing routing:

1. `graph/storage_adapters/markdown.py::MarkdownAdapter.discover` (KG ingestion;
   the most important — relocation is what drops a file from graph build).
2. `consolidation.py::iter_entity_frontmatter` (P1/P2 detectors).
3. `validate/checks/cross_references.py` (`all_ids` construction).
4. `big_picture/validator.py::_collect_project_ids`.
5. `big_picture/resolver.py::_load_entities`.
6. `entities.py::_load_markdown_entities` (find_entity / resolve_entity_ref).

**Guard test:** assert no `rglob("*.md")` / `glob("*.md")` over an `entities/` root
survives outside `entity_scan.py` (a source-grep test), so the SSOT can't silently
regress.

**Reserved-path guard (`_resolve_local_home`):** mirror the scan rule **exactly** —
reject any `_`-prefixed segment at any depth under `entities/` (`entities/_foo` *and*
`entities/foo/_bar`), fail-loud, so a local kind can never declare a home the shared
scanner would hide. **Precondition audit already run: zero `_`-prefixed paths exist
across the active projects**, so this is safe as a hard rule going forward.

---

## 4. `archive-index.jsonl` — schema & atomicity

**One append-only JSONL per project** at `entities/_archive/archive-index.jsonl`.
Each line is one **operation**; reversal never rewrites history (appends a
tombstone). `load_archive_index()` folds rows in order, **last-write-wins per id**
into `active_by_id`: latest `op:"archive"` ⇒ currently archived; latest
`op:"unarchive"` ⇒ restored.

**Archive row** (P3 omits the P4-reserved fields — they are added *additively* when
P4's digest consolidation writes them; consumers read via `.get()`):
```json
{"schema_version":1,"op":"archive",
 "id":"interpretation:0067-parameter-derivation-dag-v2","kind":"interpretation",
 "title":"…","aliases":["…"],"same_as":["…"],
 "status":"superseded","superseded_by":"interpretation:0081-…-v5",
 "original_path":"entities/interpretations/0067-…-v2.md",
 "archived_at":"2026-06-15T14:03:11Z","reason":"status:superseded"}
```
**Unarchive (tombstone) row:**
```json
{"schema_version":1,"op":"unarchive","id":"interpretation:0067-…-v2",
 "restored_path":"entities/interpretations/0067-…-v2.md",
 "unarchived_at":"2026-06-15T14:09:02Z"}
```

Field contract:
- `schema_version` on **every** row — the index is a durable on-disk API.
- `id` ∪ `aliases` ∪ `same_as` form the normalized resolvable-id set (§5).
- `kind` lets the graph mint the canonical URI without loading the file.
- `title`, `superseded_by` are searchable/displayable from the index alone.
- `status` = the entity's status **at archive time** (e.g. `superseded`), not forced
  to `archived`.
- `original_path` is authoritative (restore target); the archive location is
  *derived* — `entities/<rest>` → `entities/_archive/<rest>` (kind subtree mirrored)
  — so no redundant path field can drift.
- `reason` = `f"status:{status}"` in P3 (so an `archived`-status entity records
  `status:archived`); distinguishes P3 status-driven archiving from future
  `consolidation` (P4).
- `archived_at` / `unarchived_at` use wall-clock; the writer takes an **injectable
  clock** so tests are deterministic.
- P4-reserved (omitted in P3, additive later): `digest_insight`,
  `consolidated_into`, `cluster_id`.

**Atomicity across two resources (file move + index append).** True 2-resource
atomicity needs a journal; the honest contract is:
- Per entity, **move-first-then-append** with rollback (append fails ⇒ move the file
  back and raise). Chosen because its failure residue — *moved-but-unindexed* — is
  self-detecting (the archive-verify subcheck flags a `_archive/` file with no active
  row; its refs also dangle), whereas *indexed-but-not-moved* would leave an entity
  both live **and** "archived."
- **Durability:** write one complete JSON line, `flush`+`fsync` the index, and
  `fsync` the `_archive` parent dir after moves where practical.
- **`verify_archive()`** (run as a `science validate` subcheck **and** available
  standalone) reconciles filesystem ↔ index and fails loud (§5).

---

## 5. Archive-aware reference resolution (index-only invariant)

**Invariant:** the *active archive index* — never archived-markdown scanning — is the
source of truth for archived resolution. Archived entities are resolvable reference
targets but are never rehydrated as live entities.

- **`load_archive_index()`** exposes `resolvable_ids: dict[alias → canonical_id]`
  over canonical ∪ aliases ∪ same_as of **active** entries, plus per-entry metadata
  (`kind`, `title`, `superseded_by`, `original_path`).

- **`validate/cross_references.py`:** union `resolvable_ids` into `all_ids` so a live
  `related:` / `source_refs:` / `relations[].target` ref to an archived id **resolves**
  instead of WARN-dangling. Unknown ids are still flagged.

- **Archive-verify subcheck** (fail-loud) detects:
  - a `_archive/` markdown file with **no active index row**;
  - an active index row whose file is **missing**;
  - an **alias collision** — an archived `id`/alias/same_as that collides with a live
    entity id or with another active archive entry.

- **Graph `ReferenceResolver`:** register active archive ids/aliases so a ref to an
  archived id **resolves to its canonical URI (minted from `id`+`kind`)** — replacing
  today's *silent edge drop* — without loading the file.

- **Tombstone stub node** (emitted **only** from the index, never archived markdown).
  For each archived URI that is an edge target, emit:
  - `rdf:type sci:ArchivedEntity` (+ the original kind class if cheap) and a
    `sci:entityKind` literal;
  - `rdfs:label` / title from the index;
  - `sci:archived true`;
  - `sci:supersededBy <uri>` **only** when `superseded_by` is present *and*
    resolvable.
  - **No** domain facts, source/related refs, claims, or body-derived triples.

---

## 6. Mutators (report-then-apply)

**`science entities archive --project-root <p> [--status superseded|archived] [--apply]`**
(mirrors P1 `mark-superseded`). Default driver = live entities whose status is in the
hidden set `{superseded, archived}` (scanned via `entity_scan`, so already-archived
files are never re-considered).
- **Report** (no `--apply`): per candidate — `id, kind, status, original_path,
  superseded_by`, plus its **inbound live refs** (informational; §5 makes relocation
  safe regardless, but a human should see them). Moves nothing.
- **Apply**: per candidate, move-first-then-append (§4), building the row from
  frontmatter (`id, kind, title, aliases, same_as, status, superseded_by`, with
  `reason=f"status:{status}"`). Reports `applied` / `skipped`.

**`science entities unarchive <id>… [--apply]`** (explicit ids — recovering specific
entities). Report shows `id → restored_path`; **collision-checks first** (target
exists ⇒ fail before moving, never overwrite); apply moves `_archive/…` →
`original_path` and appends the `unarchive` tombstone. Restored entity is live again
at its original status (still `superseded`, so P1 status-hide still applies to views
until `--include-hidden`).

---

## 7. Retrieval surfaces

**`science search` — new top-level command, archive-only in P3.**
`science search QUERY --archived [--project-root <p>] [--format text|json]` reads
the active index and substring/case-insensitive matches over `id, title, aliases,
same_as, kind` (and `digest_insight` once P4 populates it). Invoked **without**
`--archived` it **fails loud** — general live-entity search is out of scope (its own
future project), no silent fallback. Search never scans archived markdown.

**`--include-archived` — location-axis override**, scoped to read surfaces where it
is meaningful: `science entities list --include-archived` and big-picture bundle
assembly → `iter_entity_markdown(include_archived=True)` (un-skips only `_archive/`).
It does **not** imply `--include-hidden`, so surfacing an archived entity in `list`
needs **both** flags. **Deliberately not** added to graph build (uses stub nodes, not
rehydration) or validate (index-only resolution).

**Grep honesty.** `_archive/` is tracked, so raw `rg`/`grep` still matches it — the
guarantee is **tool-mediated** retrieval only. Ship an `.rgignore`/`.ignore` entry
for `entities/_archive/` (with `rg --no-ignore` as the documented override) as an
ergonomic add, but the contract is the tool surface, not raw grep.

---

## 8. Testing (TDD, synthetic `entities/` fixtures)

- **`entity_scan`:** default skips `_archive/`; `include_archived` un-skips **only**
  `_archive/`; **always** skips other `_`-prefixed (`_foo`); + **guard test** — no
  direct entity-`rglob`/`glob` survives outside `entity_scan.py`.
- **`_resolve_local_home`:** rejects `_foo` *and* `foo/_bar`; accepts normal homes.
- **Index:** append→fold→tombstone last-write-wins; `schema_version` on every row;
  derived archive path mirrors the kind subtree.
- **`archive`:** report lists candidates; apply mirrors path under `_archive/` +
  appends row; rerun idempotent (already-archived not re-considered); move-first
  rollback on simulated append failure.
- **`unarchive`:** restores to `original_path` + tombstone; collision (target exists)
  fails before moving.
- **`verify_archive` / validate subcheck:** moved-but-unindexed, indexed-but-missing-
  file, alias collision → each fails loud.
- **`validate cross_references`:** live ref to archived id resolves; unknown id still
  flagged.
- **Graph (acceptance, verbatim):**
  1. a live `related:` / `source_refs:` / `relations[].target` ref to an archived id
     produces an edge to the canonical URI;
  2. the target URI carries the archived stub triples;
  3. the archived markdown file was **not** scanned as a live entity;
  4. an unknown ref still **fails** validation and gets **no** stub.
- **P3 acceptance invariant:** after `archive --apply` on a *referenced* superseded
  entity, `science validate` passes and graph build succeeds with the materialized
  edge.

---

## 9. Risks & mitigations

- **Half-covered scan-skip ⇒ inconsistent visibility.** Mitigated by the single
  `entity_scan` SSOT + the no-direct-rglob guard test.
- **Lossy/irreversible archiving.** Files are `git mv`-relocated, never deleted;
  `unarchive` + git history provide recovery; index is append-only/auditable.
- **Two-resource non-atomicity.** Bounded by move-first ordering + fsync + the
  archive-verify reconciler (run in `validate`).
- **Alias/id collisions corrupting resolution.** Detected fail-loud by the
  archive-verify subcheck before they can mislead resolution.
- **Reserved-path regressions.** Scan rule and `_resolve_local_home` guard share the
  exact same `_`-prefix rule, tested in lockstep.

---

## 10. Relationship to P4

P3 ships the archive **substrate** and the status-driven mutator. P4 (`consolidate
--apply`) reuses it: a cluster digest is minted, members get `status:archived` +
`consolidated_into:<digest-id>`, then are relocated via the **same** `archive_entities`
path — populating the P4-reserved index fields (`digest_insight`, `consolidated_into`,
`cluster_id`) additively. No schema or module changes to P3 are anticipated.
