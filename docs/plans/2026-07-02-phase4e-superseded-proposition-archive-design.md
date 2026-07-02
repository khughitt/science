# Proposition Reconciliation Phase 4e: Superseded Proposition Archive

Date: 2026-07-02

## 1. Goal

Phase 4e Half C and Half D can now leave superseded propositions in a coherent
live state:

- Half C canonicalization marks duplicate propositions `status: superseded` with
  `superseded_by: <canonical proposition>`.
- Half D replacement marks fully replaced broad propositions `status: superseded`
  with either `superseded_by: <single replacement>` or
  `resynthesized_into: [<replacement propositions>]`.
- Live lineage visibility materializes both shapes as `sci:supersededBy`.

This phase adds a deliberate archive path for settled superseded propositions:
move them out of the live entity tree while preserving archive-index resolution,
graph-visible lineage, and cross-paper evidence correctness.

## 2. Scope

In scope:

- selecting live `proposition:*` entities with `status: superseded`;
- validating that each selected proposition has resolvable reconciliation lineage;
- blocking archive movement when live annotation sidecars still promote statements
  to the superseded proposition;
- preserving scalar and multi-successor lineage in the archive index;
- extending archive-row graph materialization so unreferenced archived rows that
  carry resolvable lineage still get tombstone nodes and `sci:supersededBy` edges;
- extending archive-row graph materialization so archived `resynthesized_into`
  emits one `sci:supersededBy` edge per successor;
- reusing existing archive relocation primitives for the actual file move and
  append-only index write.

Out of scope:

- rewriting sidecar `promoted_to` backlinks during archive;
- deleting proposition files;
- changing Half C or Half D apply behavior;
- adding a new `sci:resynthesizedInto` predicate;
- authoring inverse `sci:supersedes` relations;
- changing belief aggregation or cross-paper evidence semantics;
- broadening the generic archive command to understand annotation-specific
  readiness rules.

## 3. Design Choice

Add a 4e-specific archive surface over the existing archive tier:

```text
science annotate archive-superseded-propositions [--apply] [--format table|json]
```

The generic `science entities archive` command already relocates hidden-status
entities, but it is intentionally content-agnostic. That makes it the wrong place
to enforce proposition-reconciliation invariants such as promoted annotation
backlinks. The new command should own 4e readiness checks, then delegate the file
move and append-only index write to shared archive primitives.

Shared archive support still needs one small schema extension: `ArchiveRow` must
carry multi-successor lineage. Today it stores `superseded_by` but not
`resynthesized_into`, so archiving a Half D multi-successor original would lose
index-level lineage even though live frontmatter had it. This shared extension
should be available to archive primitives generally, but the reconciliation-aware
readiness checks stay in the new `science annotate` command.

Alternatives considered:

- **Extend `science entities archive` with 4e checks.** Rejected. It couples a
  generic entity archive command to annotation sidecars and proposition-specific
  semantics.
- **Tell users to run the existing generic archiver.** Rejected. It does not
  preserve `resynthesized_into` in the archive index and does not block stale live
  `promoted_to` backlinks.
- **Archive automatically at the end of Half C/D apply.** Rejected. The apply
  surfaces should remain narrow. Archive movement is a separate lifecycle decision
  with its own dry-run/report step.

## 4. Candidate Semantics

A candidate is a live markdown entity loaded as a proposition whose canonical id
starts with `proposition:` and whose raw frontmatter has:

```yaml
status: superseded
```

The candidate is archive-ready only when all checks pass:

1. It declares exactly one lineage shape:
   - `superseded_by: <proposition-ref>`; or
   - `resynthesized_into: [<proposition-ref>, ...]`.
2. `superseded_by` is a non-empty string, when present.
3. `resynthesized_into` is a non-empty list of non-empty strings, when present.
4. Multi-successor targets are unique.
5. The candidate does not name itself as a successor.
6. Every successor resolves to either a live entity id or an active archived id.
7. No live project annotation sidecar contains an active proposition annotation
   whose `promoted_to` still equals the candidate id.
8. The derived archive destination does not already exist.
9. The candidate id and aliases do not collide with active archive rows or live
   alias space beyond the entity being archived.

`status: superseded` propositions without lineage are not ready. They should appear
in the report with a blocker rather than being silently ignored, because they are
hidden from default entity listings but not safely archival.

The report should also surface generic inbound live references, matching the
existing archive command's decision-support behavior for `related`, `source_refs`,
and `relations[].target`. These refs remain resolvable after archive through the
archive index, so they are not hard blockers in this phase. They are still useful
context for review, and they can mask missing archive-lineage emission in tests
because they incidentally put the archived id into `referenced_archived`.

## 5. Cross-Paper Evidence Boundary

The critical 4e-specific readiness check is the sidecar backlink scan.

Cross-paper evidence derives from live annotation sidecars by reading
`ann.promoted_to`. If an annotation still points at a superseded proposition and
the proposition is archived, belief attribution can remain stranded on an archived
claim. The archive command must therefore fail closed:

- any active sidecar backlink to the candidate is a blocker;
- the report names the annotation refs that block movement;
- archive apply performs the same live scan immediately before moving files.

The command does not rewrite sidecars. Rewriting `promoted_to` is owned by Half C
canonicalization apply and Half D resynthesis apply, where reviewed judgments and
draft assignments define the new targets.

## 6. Archive Index Semantics

Extend `ArchiveRow` with:

```python
resynthesized_into: list[str] = Field(default_factory=list)
```

For archived proposition rows:

- `superseded_by` stores scalar replacement lineage;
- `resynthesized_into` stores multi-successor replacement lineage;
- exactly one should be populated for 4e superseded proposition archive rows.

Existing rows without `resynthesized_into` remain valid because the field defaults
to an empty list. `unarchive` tombstone rows do not need lineage fields.

The archived markdown file remains a frozen historical record. Its frontmatter and
body are moved unchanged, including historical `source_refs`. After relocation, the
active archive index is the resolver-visible summary; archived markdown is not
loaded as a live entity.

The generic `science entities archive` command can remain content-agnostic. It may
copy lineage fields that are present in frontmatter, but it should not be described
as the evidence-safe proposition reconciliation archive path because it does not
check live annotation backlinks.

## 7. Graph Semantics

Graph materialization should preserve lineage across live and archived states:

- live `superseded_by` already emits one `sci:supersededBy`;
- live `resynthesized_into` already emits one `sci:supersededBy` per successor;
- archived `ArchiveRow.superseded_by` should emit one `sci:supersededBy` when the
  target resolves, even when no live entity currently points at the archived id;
- archived `ArchiveRow.resynthesized_into` should emit one `sci:supersededBy` per
  target and fail materialization if any target is unresolved, even when no live
  entity currently points at the archived id.

Current archive tombstone emission is not enough for this archive-movement phase.
Today materialization emits archived tombstone nodes only for ids collected in
`referenced_archived`, and that set is populated when a live entity references an
archived id. The archive row's own `superseded_by` does not add the archived row
itself to `referenced_archived`. Therefore a cleanly superseded proposition with no
remaining inbound live refs would lose its `sci:supersededBy` edge immediately after
relocation.

This phase must close that gap explicitly. Materialization should seed the
tombstone-emission worklist with active archive rows that carry lineage:

- for scalar `superseded_by`, seed the row when its target resolves to a live entity
  or active archived id;
- for multi-successor `resynthesized_into`, validate every target first, fail on
  any unresolved target, then seed the row;
- when a resolved successor is itself an active archived id, also mark that successor
  as referenced so it emits its own archived stub; otherwise an archived-to-archived
  lineage chain would leave the successor as a bare URI with no `sci:ArchivedEntity`
  type;
- after seeding, the existing tombstone loop can emit the archived stub and lineage
  edges in one place. That loop currently reads only `row.superseded_by`; it must
  also emit one `sci:supersededBy` per `resynthesized_into` target.

This seeding is deliberately general, not proposition-scoped. The seeding key is
`ArchiveRow.superseded_by` (and the new `resynthesized_into`), and the generic
`science entities archive` command already writes `superseded_by` onto archive rows
for any superseded entity, not just propositions. So this change also makes
pre-existing, unreferenced archived rows from earlier generic archiving emit a
tombstone stub and `sci:supersededBy` edge on the next graph materialization. That
is intended: an archived entity's supersession lineage should be graph-visible
regardless of how it was archived or whether a live entity still points at it. The
change is in materialization, not in the archive command, so the command stays
content-agnostic even though the graph rendering of its past outputs gains edges.

Existing archive behavior for legacy scalar `superseded_by` rows can remain as-is:
today an unresolvable scalar successor is omitted, and if no live entity references
that archived id, no tombstone stub is emitted. That lenience is historical archive
behavior, not a baseline that satisfies 4e. The new command prevents dangling
scalar lineage before archive, and the new `resynthesized_into` field should be
strict from the start because it has no legacy row population.

Acceptance should compare graph triples before and after archive movement: the
superseded proposition should remain graph-visible as an archived stub with the
same lineage edges.

## 8. Command Surface

Dry run:

```text
science annotate archive-superseded-propositions [--format table|json]
```

Apply:

```text
science annotate archive-superseded-propositions --apply [--format table|json]
```

The report should include:

- candidate id;
- original path;
- lineage kind: `superseded_by` or `resynthesized_into`;
- successor ids;
- blocking annotation refs, if any;
- inbound live refs, if any;
- archive destination;
- status: `ready`, `blocked`, or `skipped`.

JSON output should be deterministic: sort candidates by id, blockers by annotation
ref, and successors lexically after validation.

Apply should move only `ready` candidates. If any selected candidate becomes invalid
between dry run and apply, fail before moving that candidate. The command may be
non-atomic across multiple candidates, matching the existing archive tier, but it
must report which ids were applied and which were skipped or blocked.

The apply timestamp should be captured once and threaded into archive-row creation.
Dry-run JSON should not include `archived_at`; tests should inject a fixed timestamp
when asserting applied archive rows so output comparisons stay deterministic.

## 9. Data Flow

Recommended flow:

1. Load project sources to get live typed entities and raw markdown documents.
2. Build a live proposition index from typed entities.
3. Build raw frontmatter rows keyed by frontmatter `id`.
4. Load the active archive index for archived target resolution and destination
   collision checks.
5. Scan live annotation sidecars under `entities/` and build
   `promoted_to -> annotation refs`.
6. Scan generic inbound live refs using the same fields as the generic archive
   command: `related`, `source_refs`, and `relations[].target`.
7. Build candidate reports for every live superseded proposition.
8. On apply, pass ready candidate rows to an archive relocation helper that writes
   complete `ArchiveRow` entries, including `resynthesized_into`.
9. Postflight by reloading the archive index and verifying each moved id is active
   in the index, its live file is absent, its archive file exists, and graph
   materialization still emits the expected lineage triples.

The implementation should reuse existing sidecar parsing and archive relocation
helpers instead of duplicating serialization or filesystem-move logic.
It should not reuse the generic `_candidate_rows` helper for this command's
candidate construction: that helper is status-based and currently reads only
`superseded_by`, while this phase must preserve `resynthesized_into` and report
annotation-backlink blockers.

## 10. Error Handling

Fail loud on:

- malformed lineage frontmatter;
- both lineage fields present;
- no lineage field present;
- self-successor lineage;
- duplicate `resynthesized_into` successors;
- unknown successors;
- live sidecar backlinks still pointing at the candidate;
- archive destination collision;
- archive id or alias collision;
- missing source file during apply;
- index write failure.

Do not silently drop invalid candidates from the report. Hidden superseded
propositions with blockers are exactly the cases users need to see.

## 11. Idempotency

Re-running apply after a successful archive should be quiet:

- archived ids are no longer live candidates because `iter_entity_markdown` skips
  `entities/_archive/`;
- the active archive index keeps them resolvable;
- graph materialization should still emit archive tombstone lineage.

If a partially completed previous run moved a file but failed to append the index,
existing archive verification should surface the mismatch. The 4e command should
not invent silent recovery; it should fail and direct the user to archive
validation/unarchive repair paths.

## 12. Tests

Focused tests should cover:

- dry-run reports a ready scalar `superseded_by` proposition;
- dry-run reports a ready multi-successor `resynthesized_into` proposition;
- apply moves ready propositions and writes archive rows with preserved lineage;
- graph triples for lineage are stable before and after archive movement;
- a clean archived superseded proposition with no inbound live refs still emits an
  archived stub and lineage edge after relocation;
- a pre-existing, unreferenced non-proposition archived row that carries a resolvable
  `superseded_by` now emits a stub and `sci:supersededBy` edge, confirming the
  materialization change is general and intentional;
- an archived-to-archived lineage chain emits a stub for the successor row, not a
  bare URI;
- active archived successors are accepted as lineage targets;
- stale live sidecar `promoted_to` backlinks block movement and are reported;
- malformed lineage blocks movement;
- destination collision blocks movement before overwriting;
- re-running after successful apply reports no live candidates;
- existing generic archive tests still pass; any that snapshot graph triples for an
  already-archived entity with a resolvable `superseded_by` must be re-baselined for
  the newly emitted stub and edge rather than assumed unchanged.

The graph-stability tests should parse the materialized dataset and assert exact
`sci:supersededBy` triples in the knowledge graph, not serialized TriG substrings.

## 13. Acceptance Criteria

- Settled Half C duplicate propositions can be moved to the archive tier without
  losing scalar `sci:supersededBy` graph lineage.
- Settled Half D replaced propositions can be moved to the archive tier without
  losing multi-successor graph lineage.
- Any remaining live sidecar backlink to the superseded proposition blocks archive
  movement.
- Archive rows preserve enough lineage for archived-id resolution and graph
  tombstone emission.
- The generic archive command remains content-agnostic. The materialization change
  is general: it makes any lineage-bearing archived row graph-visible, including
  pre-existing rows from earlier generic archiving. That is an intended, more-correct
  graph rendering of past outputs, not a change to the archive command's behavior.
- No sidecar rewrite, deletion, belief recomputation, or Half C/D apply change is
  introduced in this phase.

## 14. Future Work

Later phases may:

- add health summaries for superseded propositions that are ready to archive;
- add explicit `sci:resynthesizedInto` if consumers need to distinguish factorized
  replacement from ordinary supersession;
- add richer archive repair tooling for partial filesystem/index failures;
- promote lineage fields into typed entity schemas if more consumers need them.
