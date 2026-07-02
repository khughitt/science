# Proposition Reconciliation Phase 4e: Live Lineage Visibility

Date: 2026-07-02

## 1. Goal

Phase 4e Half C and Half D now leave durable reconciliation lineage in live
proposition frontmatter:

- Half C canonicalization marks duplicate propositions `status: superseded` with
  `superseded_by: <canonical proposition>`.
- Half D resynthesis marks a fully replaced broad proposition `status: superseded`
  with either `superseded_by: <single replacement>` or
  `resynthesized_into: [<replacement propositions>]`.

Those fields are file-visible and managed by entity reference rewrite/removal
machinery, but graph materialization currently emits `sci:supersededBy` only for
archive-index rows. Live superseded proposition lineage is therefore durable but
graph-invisible.

This phase makes live reconciliation lineage visible in the graph without changing
Half C/D apply behavior.

## 2. Scope

In scope:

- reading live entity raw frontmatter during graph materialization;
- emitting `sci:supersededBy` from live `superseded_by`;
- emitting one `sci:supersededBy` edge per `resynthesized_into` target;
- validating that live lineage fields appear only on `status: superseded` owners;
- failing loud on dangling or malformed live lineage targets;
- preserving existing archive-index `superseded_by` materialization.

Out of scope:

- changing Half C or Half D apply commands;
- moving superseded propositions into archive storage;
- adding a new `sci:resynthesizedInto` predicate;
- authoring explicit `sci:supersedes` relation records;
- changing belief aggregation or cross-paper evidence semantics;
- widening the typed entity model unless implementation proves raw source records
  are insufficient.

## 3. Design Choice

Use raw live entity frontmatter already carried by project source loading, and emit
the existing graph predicate `sci:supersededBy`.

`load_project_sources` already records markdown source documents with raw
frontmatter. That lets materialization inspect live `superseded_by` and
`resynthesized_into` without pretending those fields are typed entity attributes.
This matches the current reality: the fields are valid durable frontmatter, but the
Pydantic entity model does not expose them as first-class fields.

Alternatives considered:

- **Add typed model fields now.** Rejected for this phase. It broadens schema
  surface area and validation semantics for fields that are currently owned by
  narrow reconciliation apply commands.
- **Mirror archive behavior and omit dangling successors.** Rejected for live
  frontmatter. Archive rows are historical index records, but live files are editable
  project state. Dangling live lineage should fail early.
- **Add `sci:resynthesizedInto`.** Rejected for now. Consumers need lineage reachability
  first. A dedicated predicate can be added later if downstream use needs to
  distinguish factorized replacement from ordinary supersession.

## 4. Materialization Semantics

During graph materialization, for each live markdown entity source with an entity id:

1. Read `status`, `superseded_by`, and `resynthesized_into` from raw frontmatter.
2. If neither lineage field is present, do nothing.
3. If either lineage field is present and `status != "superseded"`, fail
   materialization with a clear error naming the owner and field.
4. Normalize lineage targets:
   - `superseded_by` must be one non-empty string;
   - `resynthesized_into` must be a non-empty list of non-empty strings;
   - duplicates are invalid, not silently deduped;
   - the owner id cannot appear as a successor.
5. Every target must resolve to either a live entity id or an active archived id.
   Unknown targets fail materialization.
6. Emit `(owner, sci:supersededBy, target)` into the knowledge graph for each target.

If both `superseded_by` and `resynthesized_into` are present on the same live entity,
fail materialization. Half C/D intentionally write one shape or the other:
`superseded_by` for scalar successor lineage, `resynthesized_into` for multi-successor
factorized replacement. Allowing both would create an ambiguous owner state.

Archive-index tombstone behavior remains unchanged. Active archived rows may still
emit `sci:supersededBy` when their `ArchiveRow.superseded_by` target resolves to a
live or active archived id.

## 5. Error Handling

Live lineage is treated as authoritative project state, so errors fail loud:

- malformed `superseded_by`;
- malformed `resynthesized_into`;
- both lineage fields on one owner;
- lineage on a non-`superseded` owner;
- self-supersession;
- duplicate multi-successor targets;
- unknown successor target.

Errors should include enough context for repair: owner id, file path if available,
field name, and bad value or target.

Do not silently drop invalid live lineage edges. The user-facing fix is to correct
frontmatter, not to materialize a partial graph that hides broken reconciliation
state.

## 6. Data Flow

The implementation should avoid duplicating markdown discovery logic.

Recommended flow:

1. Use `sources.markdown_documents` or an equivalent raw-source index from the
   existing project source load.
2. Select documents whose frontmatter has an entity id and kind/type.
3. Build owner id -> frontmatter/path rows for live entities.
4. Reuse the materialization entity indexes for successor resolution:
   - live target: `target in entity_index`;
   - archived target: `target in archive_active`.
5. Add lineage triples in the emit phase before returning the materialized dataset.

This keeps the feature graph-only and read-only. It should not mutate entity files or
archive indexes.

## 7. Tests

Focused tests should cover:

- live `status: superseded` + `superseded_by` emits `sci:supersededBy`;
- live `status: superseded` + `resynthesized_into` emits one edge per target;
- `resynthesized_into` can target live replacement propositions;
- successors may resolve through active archive rows;
- dangling live successor fails;
- lineage on `status: active` fails;
- both lineage fields on one owner fail;
- duplicate `resynthesized_into` targets fail;
- self-supersession fails;
- archive-index `superseded_by` emission remains unchanged.

The tests should exercise graph materialization, not only helper functions, because
the core risk is whether live raw frontmatter reaches the graph emit path.

## 8. Acceptance Criteria

- A proposition superseded by Half C becomes graph-visible via `sci:supersededBy`.
- A proposition replaced by Half D with multiple replacement propositions becomes
  graph-visible via multiple `sci:supersededBy` edges.
- Invalid live lineage frontmatter blocks graph materialization with actionable
  errors.
- Existing archive tombstone lineage behavior is preserved.
- No Half C/D apply command behavior changes.

## 9. Non-Goals And Future Work

This phase intentionally stops at graph visibility. Later work may:

- add a dedicated `sci:resynthesizedInto` predicate if consumers need it;
- surface live lineage in health summaries or decision logs;
- move long-settled superseded propositions into archive storage;
- author explicit inverse `sci:supersedes` relation records;
- promote lineage fields into typed entity schemas if repeated consumers make raw
  frontmatter access too fragile.
