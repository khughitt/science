# Entity Consolidation P4 — `entities consolidate` (Tier 3 cluster digest) — Design

> Part of the entity consolidation/archive series. See the umbrella design
> `2026-06-15-entity-consolidation-and-archive-design.md` (§4 Tier 3, §6, §8) and
> the shipped P1 (visibility + `mark-superseded`), P2 (read-only candidate
> detector), and P3 (archive tier: `entity_scan`, append-only
> `archive-index.jsonl`, index-only archive-aware resolution, `entities
> archive`/`unarchive`, `search --archived`).

## 1. Goal

Add a **two-step, opt-in, reversible** command that collapses a human-chosen
cluster of live entities into **one canonical `cluster-digest` entity plus N
archived originals** — reusing P3's relocation/index machinery rather than
introducing a second archive path.

This is the *semantic-cluster* (Tier 3) case. The *linear superseded-lineage*
case is already fully served by the shipped `entities mark-superseded` (sets
`status: superseded` on linear-chain tails) → `entities archive` (relocates
superseded). P4 adds nothing there; it does **not** add an `--auto-superseded`
mode (open question #3 is moot — already shipped as the compose of two commands).

## 2. Scope (locked)

- **In:** the Tier 3 mutator only — `entities consolidate scaffold` + `entities
  consolidate apply`, the `cluster-digest` report_kind, the `archived` status
  vocab groundwork, the `consolidated_into`/`digest_insight` index fields, and a
  shared relocation primitive in `archive.py`.
- **Out (deferred to a later slice, "P5"):** Tier 4 — making big-picture / curate
  *substitute* a digest for its archived members in bundle assembly (one entry,
  not N). Archived members already drop out of every consumer automatically via
  P3's scan-skip; Tier 4 is the separate "collapse N→1 in bundles" concern.
- **Out:** full "un-consolidate" (revert status + strip `consolidated_into` +
  retire the digest in one command). Reversal of *location* reuses the shipped
  `entities unarchive`; the rest is a manual follow-up, stated honestly.
- **Member selection:** explicit `--members <id,…>` list (deterministic; no
  dependency on P2 cluster-id stability). The P2 `curate
  --consolidation-candidates` report is the decision-support a human reads to
  choose ids. Per-cluster opt-in, never a bulk sweep.

## 3. Command surface — `entities consolidate` (Click sub-group)

A new sub-group under `entities_group`, sibling to `migrate` /
`triage-aggregate` / `mark-superseded` / `archive`.

### 3.1 `science entities consolidate scaffold --into <digest-id> --members <id,id,…> [--title T]`

- Validates each member: exists as a live entity, is not already archived (absent
  from the active archive index), is not the digest id itself, and its kind is
  consolidatable (status vocab includes `archived` — see §6; **fail loud**
  otherwise, naming the offending kind).
- Mints a live `synthesis` entity at its canonical home `entities/synthesis/`
  (the `synthesis` kind's `home`) by **create-then-rewrite**: call the existing
  `create_entity` path to mint the file (id minting, home placement, template
  body), then rewrite its frontmatter to set the two fields the generic
  renderer/template don't carry — `report_kind: cluster-digest` and a typed
  `relations:` block (one entry per member, see §7) — and re-validate the result.
  (The synthesis template defaults `report_kind` to `hypothesis-synthesis` and the
  renderer has no `report_kind`/`relations` inputs, so a post-create frontmatter
  rewrite is the lowest-blast-radius mechanism; we do **not** widen the generic
  renderer/template for one kind.) Resulting digest frontmatter:
  - `type: synthesis`
  - `report_kind: cluster-digest`
  - `status: active` (the synthesis default; never a hidden status)
  - `title:` from `--title` (or a derived placeholder)
  - `relations: [{predicate: "sci:consolidates", target: <member-id>}, …]` (§7)
    — the authored-relation contract is `{predicate, target, graph_layer?}`
    (`AuthoredTargetedRelation`), **not** `{kind, target}`.
  - the standard synthesis template body sections for a human/agent to fill.
- **Scaffold rollback contract.** Create-then-rewrite must be atomic: if the
  post-create frontmatter rewrite or the re-validation fails after `create_entity`
  has already written the file, delete the newly created digest file (it is
  brand-new this command — safe to remove) and report failure. The command never
  leaves a half-scaffolded synthesis on disk (neither the default
  `hypothesis-synthesis` stub nor a partially-rewritten invalid digest).
- **Touches no members.** Output names the created digest path and the members it
  will later consolidate.

### 3.2 `science entities consolidate apply <digest-id> [--apply]`

Report-then-apply, matching the `mark_superseded` / `archive_entities`
`apply: bool` convention.

- Re-reads the digest entity on **live state**; fails loud if the digest is
  missing, is not `report_kind: cluster-digest`, or has no `relations:` entry whose
  `predicate` resolves to `sci:consolidates`. The member list is the set of those
  entries' `target`s.
- Re-validates each member exactly as scaffold does (exists, live, not already
  archived, consolidatable, not the digest).
- Dry-run (default): reports the digest, the members, and per-member
  destination archive paths. No mutation.
- `--apply`: for each member, atomically (§5) stamp `status: archived` +
  `consolidated_into: <digest-id>`, relocate to `entities/_archive/<kind>/…`, and
  append an archive index row carrying `consolidated_into` and `digest_insight`.
  The digest stays live.

## 4. Module structure

- **New `src/science_tool/consolidate.py`** — the Tier-3 *apply* half:
  `scaffold_digest(...)`, `apply_consolidation(...)`, and the shared member
  validation. Module docstring spells out the detect/apply split versus the
  existing read-only detector `consolidation.py` (the proximity is deliberate —
  they are the two halves of one feature — but they never import each other's
  mutation/detection internals).
- **`archive.py`** — additive only:
  - Add optional `consolidated_into: str | None = None` and
    `digest_insight: str | None = None` to `ArchiveRow` (the docstring already
    reserves them). Backward-compatible: old rows omit the keys and load as
    `None`; **no `SCHEMA_VERSION` bump** (additive-optional).
  - Extract the per-row move-first → `append_row` → rollback loop currently
    inside `archive_entities` into a shared `_relocate_rows(index_path,
    project_root, rows, *, now)` primitive. **Contract:** it relocates already-
    final-on-disk files and rolls back only the *move* (and the dst-collision
    guard) on an append failure — it performs **no** frontmatter edits and owns
    no content snapshot. `archive_entities` delegates to it unchanged (its
    candidates already carry their terminal status in-file). `apply_consolidation`
    builds member-scoped rows (with `consolidated_into`/`digest_insight`) and
    wraps each `_relocate_rows` call with its own frontmatter snapshot/rewrite/
    restore (§5), so the primitive stays content-agnostic. DRY, composition over
    duplication, identical move/append/rollback discipline.
- **CLI (`cli.py`)** — `consolidate` Click sub-group with `scaffold` and `apply`
  subcommands registered under `entities_group`.

## 5. Per-member atomicity (apply)

Archived members are **frozen/read-only once relocated** (umbrella §6), so all
frontmatter edits happen at the **live** home *before* the move:

1. Read + snapshot the member's original file bytes.
2. Rewrite its frontmatter: `status: archived`, `consolidated_into: <digest-id>`.
3. `shutil.move` the file to its derived `_archive/` path (move-first).
4. `append_row` with the member's archive row (op=`archive`, id, kind, title,
   aliases, same_as, `status="archived"`, `original_path`,
   `consolidated_into=<digest>`, `digest_insight=<member title>`, `archived_at`).

`apply_consolidation` owns the whole per-member transaction: it snapshots the
bytes (step 1), rewrites frontmatter (step 2), then calls `_relocate_rows` for
that single row (steps 3–4). `_relocate_rows` rolls back only the *move* on an
append failure; `apply_consolidation` wraps the call in `try/except` and, on **any**
exception, restores the snapshotted original bytes at the live `original_path`
(the move-rollback or the un-executed move leaves the file at that path either
way) — leaving the member exactly as it was. The frontmatter snapshot/restore is
thus owned by `apply_consolidation`, never by the content-agnostic primitive (§4).
`digest_insight` is the member's title
(deterministic, no agent) — the one-line recall hint the index keeps so recovery
never has to rehydrate the archived markdown.

## 6. Data-model changes

- **`CORE_PROFILE` (`model/src/science_model/profiles/core.py`):** add `archived`
  to the **explicit, hand-picked enumeration of consolidatable markdown kinds**
  below. This is an enumeration, **not** a class-derived filter — do NOT prune it
  by `entity_class`/`EPISTEMIC` (it deliberately includes operational kinds like
  `method`, `plan`, `search`, `topic`, `decision` that are realistic
  consolidation members but are not all `EntityClass.EPISTEMIC`):
  `hypothesis`, `question`, `proposition`, `observation`, `finding`,
  `interpretation`, `synthesis`, `report`, `discussion`, `inquiry`, `mechanism`,
  `theme`, `topic`, `method`, `plan`, `search`, `decision`, `evidence-line`.
  Reference kinds (`paper`/`book`/`talk`) and bio/reference kinds are **excluded**
  — they are not consolidated into digests.
- **Visibility guards stay green for free:** `archived` is already in
  `entities.py::_HIDDEN_STATUSES`, so the `test_status_visibility.py` guards
  (every declared status is in `_LIVE_STATUSES` ∪ `_HIDDEN_STATUSES`; hidden ≠
  `default_status`) pass unchanged. No `_LIVE_STATUSES` change.
- **Parity:** `entities.py::_STATUS_VALUES` / `_DEFAULT_STATUS` are
  profile-derived; the descriptor parity tests that assert they track
  `CORE_PROFILE` are updated to expect `archived` on the listed kinds.
- **`cluster-digest` report_kind:** add to `_VALID_SYNTHESIS_KINDS` in
  `validate/checks/discussions.py`; mirror in the `synthesis.md` template's
  `report_kind` enum comment.
- **New `consolidates` RelationKind (`CORE_PROFILE.relation_kinds`):** the digest→
  member link is a *typed authored relation*, not a bespoke frontmatter field
  (§7). Declare it with RDF `predicate: "sci:consolidates"`, `source_kinds:
  [synthesis]`, and `target_kinds: []` (empty ⇒ unrestricted, per
  `relation_allows_kinds`) — so **no Cartesian kind-pair enumeration is needed**.
  Note the predicate string `sci:consolidates` already resolves to a URI via
  `_resolve_relation_term` (the `sci:` prefix is registered), so emission does
  **not** require registration; registering the RelationKind is what activates
  `_validate_authored_relation_endpoint`'s synthesis→member endpoint gating + the
  self-reference guard, and makes `consolidates` a first-class profile relation
  alongside the others. `_profile_relation_for_predicate` matches it by predicate.
- **Closed-vocab handling — fail loud (no auto-patch).** When a member's kind has
  a *closed* status vocabulary that lacks `archived` (a local kind with an
  explicit `statuses` list, or a non-epistemic core kind not in the list above),
  `consolidate` rejects with a clear message naming the kind and instructing the
  operator to add `archived` to that kind's `statuses` first. This honors
  "explicit > defensive, fail early" and keeps the slice tight. (The umbrella
  design floated auto-patching local manifests; that is deliberately **not** done
  here.) Open-vocab local kinds (`statuses: None`) accept `archived` already.

## 7. Digest↔member linkage and reference resolution

**Correction to an earlier assumption:** a bare `consolidates:` frontmatter field
does **not** auto-resolve. `check_cross_references` extracts only `related:` from
frontmatter, the Entity model has no `consolidates`/`consolidated_into` field
(so they would be dropped by adapter→Entity normalization), and `_add_relations`
/ `_add_authored_relation` never read them. They would be inert — neither
validated nor emitted. So the linkage is modeled explicitly:

- **Digest → members: a typed `sci:consolidates` authored relation (live→archived).**
  The digest carries `relations: [{predicate: "sci:consolidates", target: <member>}]`
  — the `AuthoredTargetedRelation` contract (`{predicate, target, graph_layer?}`),
  flattened by `_entity_nested_relations` reading `relation.predicate`/`.target`.
  This rides the *existing* typed-relation machinery: `sources.relations` →
  `_add_authored_relation` (`materialize.py:216`), which P3 already threads
  `archive_active`/`referenced_archived` through. So when a target resolves to an
  active archived id, the emitter routes it to the archived **tombstone stub**
  (`sci:ArchivedEntity`) via `_archived_uri_if_active` — emitting
  `(digest) sci:consolidates (member-tombstone)` and seeding the stub — instead of
  dangling or force-loading the archived markdown. The reference is validated and
  graph-emitted through machinery that already exists; P4 only adds the
  `consolidates` RelationKind + predicate (§6) and a guard test. **The plan must
  verify the typed-relation *validation* path (not just emission) treats an
  active-archived target as resolved** — P3 wired emission; the plan confirms the
  authored-relation target check is archive-aware too, and extends it if not.
- **Member → digest: `consolidated_into` is provenance only, not a graph edge.**
  Each archived member keeps `consolidated_into: <digest-id>` in its frozen
  frontmatter and as an `ArchiveRow` field, for listing / search / unarchive
  recall. It is **not** emitted (the member is a tombstone stub, which carries no
  outbound authored relations) and **not** reference-validated. Crucially, the
  member is relocated in the **same** apply transaction in which the field is
  written, so its frontmatter is never re-loaded as a *live* Entity — the
  unknown-key / model-tolerance question never arises for it.
- `superseded_by:` (member → survivor) is unchanged P1/P3 behavior.

## 8. Validation & safety summary

- Member must exist, be live, not already in the active archive index, not the
  digest id, and its kind must allow `archived` (else fail loud).
- Digest must exist, be `report_kind: cluster-digest`, and carry at least one
  `relations:` entry whose `predicate` resolves to `sci:consolidates` (apply step).
- Dry-run by default; mutation only under `--apply`.
- Append-only index; move-first-then-append with per-member rollback (incl.
  frontmatter restore).
- Never overwrite: the archive-path collision guard in `_relocate_rows` (inherited
  from `archive_entities`) raises if a destination file already exists.

## 9. Testing

- **scaffold:** mints a digest at the synthesis home with correct frontmatter
  (`type`, `report_kind: cluster-digest`, and one `relations:` entry with
  `predicate: "sci:consolidates"` per member via the create-then-rewrite path);
  validates members; touches no members; fails loud on a non-existent /
  already-archived / non-consolidatable member, or the digest id appearing among
  members.
- **scaffold rollback:** a forced rewrite/revalidate failure after `create_entity`
  leaves **no** digest file on disk (the brand-new file is removed) and reports
  failure.
- **apply dry-run:** reports digest + members + destination paths; zero mutation.
- **apply --apply:** each member stamped `status: archived` + `consolidated_into`;
  relocated under `_archive/`; index rows carry `consolidated_into` +
  `digest_insight`; digest stays live and unmoved.
- **fail-loud:** member already archived; member is the digest; digest has no
  `sci:consolidates` relation entry; digest not `cluster-digest`; member kind
  closed-vocab lacking `archived` (local + non-epistemic core).
- **atomic rollback:** simulate an append failure mid-apply → member file is back
  at its original path with original bytes (frontmatter rewrite reverted); index
  unchanged for that member.
- **relation kind:** `consolidates` RelationKind/predicate registered;
  `relation_allows_kinds` permits `synthesis → <member kind>` (unrestricted target).
- **graph + resolution guard:** after a real consolidate, the graph build emits
  `(digest) sci:consolidates (member-tombstone)` and a `sci:ArchivedEntity` stub
  for each member; `science validate` reports no nonexistent-reference error and
  forces no archived file live; `consolidated_into` is not emitted as an edge.
- **discussions check:** `cluster-digest` accepted as a valid `report_kind`.
- **status vocab:** the listed consolidatable kinds now accept `archived`;
  visibility + parity guard tests stay green.
- **reversibility:** `entities unarchive <member>` restores the member to its
  `original_path` (location only; status/`consolidated_into` revert is the
  documented manual follow-up).
- **acceptance:** end-to-end scaffold → fill digest body → `apply --apply` → graph
  build + validate green, on a fixture project.

## 10. Open questions

None blocking. The two design decisions surfaced during brainstorming are locked:
`archived` goes on the enumerated consolidatable kinds (§6); closed-vocab kinds fail loud
(no auto-patch). Tier 4 consumer substitution is explicitly deferred (§2).
