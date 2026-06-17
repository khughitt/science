# Curate Canonical-Entity Inventory (G2) — Design

> **Status:** proposed design, pre-implementation. Feeds writing-plans/TDD.
> **Series:** closes G2 from the entity-consolidation audit
> (`2026-06-15-entity-consolidation-and-archive-design.md` §5, §12.3), the last
> deferred structured item in that arc.
> **Scope:** `curate/inventory.py` + its tests, plus one line in the scanner-guard
> allowlist (`tests/test_entity_scan_guard.py` `ENTITY_SCANNERS`, see §3/§5).
> Behavior-changing for the entity-discovery portion only; signals/params/JSON
> contract preserved.

## 1. Why

`curate/inventory.py` discovers entity markdown by globbing the **retired**
pre-v3 layout — `specs/hypotheses/**` and `doc/<kind>/**` (`_collect_markdown_paths`,
`_markdown_artifact_class`, `_DOC_KIND_BY_DIR`). Every other consumer (big-picture
resolver/validator/knowledge-gaps, the consolidation-candidate detector, the KG
adapter) reads the canonical `entities/<kind>/*.md` homes via the shared
`iter_entity_markdown` iterator. So in any canonical project curate's inventory
finds **zero** entities, and its entity signals (`missing_related`,
`missing_source_refs`, `no_outbound_links`, `artifact_counts`, recency) fire on
nothing. The design doc (§5) called for migrating curate to the canonical homes
before the detector was added; the detector shipped reading the graph directly, so
this migration was deferred (§12.3). This closes it.

## 2. Decisions (resolved with the author)

1. **Canonical-only replace.** Discover entities solely via
   `iter_entity_markdown(project_root / "entities")`. Drop the legacy
   `specs/hypotheses/` + `doc/<kind>/` entity scanning and `_DOC_KIND_BY_DIR`
   entirely — no transitional augment, no legacy-compat reader. This mirrors
   big-picture's v2→v3 fix and honors "no legacy/compat layers". A project still
   on the old layout should run `entities migrate`; curate must not perpetuate the
   retired reader.
2. **Drop the non-entity `spec` class.** The depth-2 `specs/*.md` → `spec`
   artifact (in no signal set; contributes only to counts/recency) is removed.
   Curate's inventory becomes canonical-entities + tasks + knowledge-sources.
   Design docs are not entities and curate is not their home.

## 3. What changes (`curate/inventory.py`)

**Entity discovery — replace `_collect_markdown_paths`.** New private helper
enumerates `iter_entity_markdown(project_root / "entities")` (relocation-aware:
the iterator already skips `_archive/` and every `_`-prefixed segment, so archived
members and reserved dirs drop out for free; `include_archived` stays False).

**`artifact_class` derivation — replace `_markdown_artifact_class`.** Derive the
class from the entity's own frontmatter, matching the established `_infer_kind`
priority used elsewhere:
1. frontmatter `type` if a non-empty string;
2. else frontmatter `kind` if a non-empty string;
3. else the `id` prefix before `:` (e.g. `interpretation:0069-x` → `interpretation`),
   **only when `id` is colon-prefixed** — a bare/unprefixed `id` yields no kind.
A file under `entities/` with frontmatter but no `type`/`kind` and no
colon-prefixed `id` is not a classifiable entity record — skip it (it cannot key
any signal). The class is the entity kind string, so the existing
signal-eligibility sets
(`_RELATED_CLASSES = {hypothesis, interpretation, paper, question}`,
`_SOURCE_REF_CLASSES = {interpretation, paper}`) keep working unchanged — they key
on kind names that still match.

**`no_frontmatter_files`** — now flags any `*.md` under `entities/` that lacks a
`---` frontmatter delimiter (entity-file drift), via the existing `_has_frontmatter`
check over the iterator's yield. (Previously: markdown in known doc roots.)

**Visibility.** No status filter. The iterator already excludes *relocated*
(archived) members; a *superseded-status-but-not-yet-archived* entity stays in the
inventory deliberately — curate is exactly where a human looks to find such
entities and act on them. (This differs from the consolidation-candidate detector,
which `is_default_visible`-filters for clustering; the inventory is a fuller
picture, by design.)

**Scanner-guard registration.** `curate/inventory.py` becomes a ninth file that
scans `entities/` through the SSOT iterator, so add it to `ENTITY_SCANNERS` in
`tests/test_entity_scan_guard.py` (the positive guard that asserts each entity
scanner contains `iter_entity_markdown`; otherwise a future regression dropping the
SSOT usage in inventory would go uncaught). The frozen `rglob` `ALLOWLIST` is
**not** touched: inventory only *calls* `iter_entity_markdown` (the sanctioned
`rglob` lives in `entity_scan.py`), so inventory never holds a local
`rglob("*.md")`.

**Preserved unchanged:** `_collect_task_paths`/`_record_tasks`,
`_collect_knowledge_source_paths`/`_record_knowledge_source`,
`collect_agents_md_state`, the `_emergent-threads.md` orphan-absorption pass (read
directly from `doc/reports/synthesis/_emergent-threads.md`, independent of entity
discovery — stays as-is), all of `CandidateSignals` (`missing_related`,
`missing_source_refs`, `no_outbound_links`, `recently_modified`, `long_idle`,
`no_frontmatter_files`), the `recent_days`/`recent_top_k` knobs, the
`InventoryArtifact`/`CurationInventory` schemas, and the JSON CLI contract
(`science curate inventory`).

## 4. Non-goals

- The consolidation-candidate detector (`consolidation_candidates.py`) is
  untouched — it already reads the graph and does not call `collect_inventory`.
- Tasks, knowledge-sources, agents_md drift, and emergent-threads handling are
  out of scope (not entity markdown).
- No change to the `science curate inventory` JSON shape or CLI options.

## 5. Test plan (TDD)

`tests/test_curate_inventory.py` — the `curated_project` fixture currently builds
the **legacy** `specs/hypotheses/`, `doc/questions/`, `doc/papers/`,
`doc/interpretations/`, `doc/topics/`, `doc/discussions/` tree. Rewrite it to the
canonical `entities/<kind>/` homes (e.g. `entities/questions/0001-q1.md` with
`type: question`), keeping the same per-class fixture content so the signal logic
is exercised identically. Update the path assertions accordingly
(`missing_related == ["entities/questions/…"]`, etc.). Preserve and re-verify:
emergent-threads fresh/stale orphan absorption, `recent_top_k`/`recent_days`,
`no_frontmatter_files`, agents_md state + drift, task/knowledge-source records,
`artifact_counts`.

New/changed assertions to add:
- `artifact_class` derivation covers all three paths (each independently, so an
  implementation handling only `type:` fails):
  - frontmatter `type:` wins (an entity in an unexpected dir is still classed by
    its `type`);
  - frontmatter `kind:` is used when `type:` is absent;
  - the colon-prefixed `id` prefix is used when both `type:` and `kind:` are absent
    (e.g. `id: interpretation:0069-x` → `interpretation`);
  - a record with no `type`/`kind` and a bare/unprefixed `id` (no colon) is skipped
    (not classified, keys no signal).
- An archived (relocated) member under `entities/_archive/` is **absent** from the
  inventory (iterator skip).
- A superseded-status entity still **present** in the inventory (no status filter).
- A `*.md` under `entities/` lacking frontmatter lands in `no_frontmatter_files`.
- The legacy `specs/*.md` "spec" class no longer appears.
- `tests/test_entity_scan_guard.py::test_entity_scanners_use_the_ssot` stays green
  with `curate/inventory.py` added to `ENTITY_SCANNERS`.

## 6. Risks

- **Behavior change for legacy-layout projects.** They will now report zero
  entities (same posture big-picture already took at v2→v3). Accepted and intended:
  the canonical layout is the contract; `entities migrate` is the remedy.
- **Lost `spec` surfacing.** Minor: the `spec` class fed only counts/recency, no
  curation signal. Accepted per Decision 2.
