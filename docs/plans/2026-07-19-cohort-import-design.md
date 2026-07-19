---
title: Cohort Import for `science entities import` — Design
status: proposed
created: '2026-07-19'
updated: '2026-07-19'
revision: v3 (folds design-review round 2 — 2 critical + 1 high + 2 clarifications)
---

# Cohort Import — Design

## Problem

`science entities import` imports **one** loose markdown document as a canonical
entity per invocation. A downstream consumer (the natural-systems plan-curation
transaction engine, "Plan 2") needs to import **many** loose documents of one
kind as a single, previewable, atomically-appliable unit.

The single-import path cannot be composed for this. An `ImportPlan` embeds its
`project_root` and `apply_import` refuses a plan built against a different root
(`entity_import.py:82`, `:567`), so plans cannot be generated in a throwaway
overlay and replayed in the real checkout. And the number is derived by
`propose_number` from **live** state at preview time (`entity_reservation.py:149`),
so two independently-previewed imports propose the **same** next number and
collide at apply. A cohort must therefore be planned in **one pass against the
real project-root**, assigning a contiguous number block, with external
referrers repointed in **one** reference scan.

## Scope

- **In:** a cohort mode on the existing `science entities import` command that
  imports 2+ loose documents of **one uniform kind** in a single
  save-plan/apply-plan cycle; sequential number-block assignment against the
  real root; one combined inbound reference rewrite over auto-rewritable external
  referrers; exception-atomic all-or-nothing apply; the mandatory approval
  envelope (`--expected-plan-sha256`, science 0.5.1).
- **Out:** mixed kinds in one cohort; per-member title/slug overrides;
  cross-member reference repointing (cohorts are required to be
  reference-independent — see below); crash-durability of standalone cohort
  apply (delegated to the caller's transaction journal).
- **Two shared-code primitive changes** (behavior-preserving for single import),
  detailed in *Primitive changes* below: a self-cleaning claim, and a
  content-override on the reference scanner.

## Non-goals / explicit boundaries

- **Cohorts are reference-independent.** A member may not link to (or bare-path
  mention) another member of the same cohort. Enforced (rejected at plan time),
  not assumed. Cross-referencing documents are imported in **separate** batches,
  where the existing single-import inbound rewrite already repoints each
  still-loose referrer as its target lands — correctness preserved without
  cohort-internal cross-member logic.
- **Standalone cohort apply is exception-atomic, not crash-durable.** Rollback
  covers *caught* failures (a failed claim, source drift, a raised rewrite, a
  failed audit) by restoring everything already mutated. Abrupt process death
  (SIGKILL) can still leave a partial cohort on disk. Acceptable **only** because
  Plan 2 wraps every apply in its own snapshot + write-ahead journal and owns
  crash recovery. Stated, not hidden.
- **The single-import contract is preserved with one deliberate exception.**
  Single-source preview and apply semantics, the single `ImportPlan` bytes, and
  the object-shaped `applied` result are unchanged. The **one** intentional
  tightening: `--apply-plan` now rejects the preview-only options it previously
  ignored (`--title`, `--status`, `--slug`, `--save-plan`, `--overwrite-plan`) in
  addition to `SOURCE`/`--kind`. This tightening is tested, not silent.

## Primitive changes to shared code

Both are used by single import; both are behavior-preserving on the success path
and only add safety on the failure path.

1. **Self-cleaning claim (`claim_number_in_dir`, `entity_reservation.py`).**
   Today the destination is created with `open(path, "x")` and written; a caught
   write/close failure leaves a **partial destination** (the `finally` unlinks
   only the `.NNNN.reserving` sentinel, `:204`). Change: wrap the exclusive
   create+write so that on any exception **after** the exclusive `open` the
   partially-written destination it created is unlinked before re-raising — the
   function exclusively created that file, so it owns it. Success path unchanged;
   the returned path is always a complete file or the call raised having left no
   destination. (SIGKILL between `open` and cleanup is the crash boundary,
   delegated to the caller's journal.) This lets cohort/single apply treat a
   destination as mutated **only** on a successful claim, with no external
   "creation began" hook.

2. **Content-override on the reference scanner
   (`plan_reference_rewrite`/`_scan`, `reference_rewrite.py`).** `_scan` iterates
   `iter_scannable_files` (disk enumeration: `rglob`, then a **size filter**,
   `text_scan.py:90`) and reads each once (`:311`, `# the ONLY read of this
   file`). Add an optional `source_overrides: Mapping[str, str]` (rel_path →
   already-read text) that participates in **enumeration**, not just reads —
   overriding only the read is insufficient, because a cached source deleted,
   renamed, or grown past the size limit between plan and scan would drop out of
   `rglob`/size enumeration and never be examined, so a member-local reference in
   the approved cached text could slip past the independence guard. Contract:
   - Each override key is validated as a **contained** project-relative path
     (`resolve_within`) and becomes an **authoritative virtual scan entry**:
     included even if absent on disk or no longer size-eligible, examined
     **exactly once**, and deduplicated against the disk enumeration (a key that
     also enumerates from disk is scanned once, from the override bytes).
   - `exclude` still wins: an excluded path is not scanned even if an override
     names it.
   - The scan runs on `sorted(disk_entries ∪ override_keys)` (minus `exclude`),
     preserving deterministic report order.

   Default empty ⇒ current behavior. **Single import is unaffected and continues
   excluding its own source from its inbound scan** (source ∈ `exclude`); it does
   not pass an override for that source — an override for an excluded path is
   inert (exclude wins), and feeding one would flip self-reference handling and
   break byte-equivalent compatibility. Overrides are for the cohort planner's
   *non-excluded* member sources, whose already-read bytes must drive the
   independence guard.

## Public surface

Single-source invocation is unchanged (per the boundary above). The cohort path
is triggered purely by passing **2+ positional sources**:

```
science entities import A.md B.md C.md --kind plan --save-plan p.json
science entities import --apply-plan p.json --expected-plan-sha256 SHA
```

### CLI option matrix (enforced, not ignored)

| Invocation | `--kind` | `--status` | `--title`/`--slug` | sources | `--save-plan` |
|---|---|---|---|---|---|
| 1 source (single) | required | optional | **allowed** | exactly 1 | optional |
| 2+ sources (cohort) | required, uniform | optional, uniform | **rejected** | 2+ distinct | optional |
| `--apply-plan` | rejected | **rejected** | **rejected** | none | **rejected** |

`--kind`/`--status` apply uniformly to the whole cohort. `--title`/`--slug` with
2+ sources is a hard `UsageError`, never a silent ignore. **Save-plan/source
collision:** the resolved `--save-plan` path must differ from **every** resolved
source in the cohort (generalizing the single guard at
`entities_inventory_cli.py:545`), enforced **even with** `--overwrite-plan` — a
preview must never destroy a document it is about to import.

The single-vs-cohort selection happens in the **CLI**, on the count of resolved
sources; the cohort planner itself raises if handed fewer than 2.

## Data model

### The shared member-planner refactor

Extract the number-taking core of `plan_import` into a helper that does **no**
inbound scan and returns its warnings out-of-band:

```python
@dataclass(frozen=True)
class PlannedMember:            # internal, not persisted
    member: ImportMember
    warnings: list[str]

def _plan_member(
    project_root: Path, source_rel: str, text: str, *, kind: str, number: int,
    status: str | None = None, title: str | None = None, slug: str | None = None,
    today: date | None = None,
) -> PlannedMember:
    """From ALREADY-READ source bytes: construct identity (honoring the optional
    `title`/`slug` overrides exactly as single import does today), rebase the
    member's OWN outbound links into rendered_text, run prospective-write
    validation, and render. Forced number; NO inbound scan; NO second read."""
```

`title`/`slug` are retained so the single-import path keeps its `--title`/`--slug`
behavior. `plan_import` becomes: read the source once → `_plan_member(...,
number=propose_number(root, kind), title=<CLI --title>, slug=<CLI --slug>)` → its
existing single-source inbound scan (feeding the cached text via
`source_overrides` — see the compat note in *Primitive changes*: the single
source stays in `exclude`, so it passes **no** override for itself) → attach
`PlannedMember.warnings` to the single plan. Behavior-preserving for single
import. `plan_cohort_import` calls `_plan_member` per cached source with forced
sequential numbers and `title=None, slug=None` (cohorts reject per-member
title/slug).

### `ImportMember` (persisted, nested)

`source_rel, source_sha256, entity_id, number, dest_rel, title, status,
frontmatter, rendered_text` — **no `kind`** (see below), no warnings field.
`extra="forbid"`.

### `CohortImportPlan` (persisted, top-level)

```
CohortImportPlan {
  plan_type: "cohort-import"          # discriminator (single ImportPlan has none)
  schema_version: 1
  project_root: str                    # embedded + apply-checked, like single
  kind: str                            # THE single authority for member kind
  members: list[ImportMember]          # 2+, in PLAN-MEMBER (input) order
  ref_report: RewriteReport            # ONE combined inbound rewrite, external referrers only
  warnings: list[AttributedWarning]    # {source_rel, message}, sorted
}
```

- `extra="forbid"` on `CohortImportPlan`, `ImportMember`, and `AttributedWarning`.
- **`kind` has one authority.** `ImportMember` carries no `kind`; `plan.kind` is
  used for every member's `claim_number_in_dir` and destination derivation. Apply
  additionally asserts the path returned by `claim_number_in_dir` equals the
  validated `dest_rel`, closing any directory-mismatch gap.
- **Member order is input order** and is preserved for numbering, validation, and
  results. Only `warnings` and report collections are sorted; `members` are not
  reordered.
- Each warning names its `source_rel`, so an aggregated warning is never
  ambiguous about which document raised it.

## Planning — `plan_cohort_import(project_root, sources, *, kind, status=None, exclude=frozenset(), today=None)`

1. **Pre-flight:** raise if `< 2` sources; resolve each; reject **duplicate
   resolved sources**; each is a readable UTF-8 file.
2. **Read each source once** into an internal cache `{source_rel: (text, sha256)}`
   — the single read that both `_plan_member` and the reference scan consume
   (via `source_overrides`), so no source is read twice.
3. **Number block:** `base = propose_number(root, kind)`; assign
   `number_i = base + i` for member `i` in input order (contiguous, ordered).
4. **Per member:** `_plan_member(root, source_rel_i, cached_text_i, kind=kind,
   number=number_i, status=status, today=today)`.
5. **One scan — independence guard *and* external report:**
   `plan_reference_rewrite(root, id_substitutions={source_rel_i → entity_id_i},
   path_substitutions={source_rel_i → dest_rel_i},
   source_overrides={source_rel_i → cached_text_i},
   exclude=exclude` *(the prospective saved-plan artifact only — members are NOT
   excluded)*`)`. Inspect the report: any `hit` **or** `manual` whose `rel_path`
   is a member source ⇒ `RefDependentCohortError` naming the offending
   source/target pair (a member linking to another member, bare-path-mentioning
   one, or itself — the self case is member-local and likewise rejected). If
   there are **no** member-local findings, members contributed nothing, so that
   report **is** the external inbound report — reuse it as `ref_report`.
6. **Assemble** `CohortImportPlan` with `members` in input order; warnings and
   report collections sorted.

External `manual` findings (auto-unrewritable references, surfaced by the
scanner) are carried in `ref_report.manual`. The cohort is still valid; it is
Plan 2's policy (its existing `manual_refs` acknowledgment gate) to decide
whether to require acknowledgment before applying — this design surfaces them, it
does not silently drop or auto-rewrite them.

## Apply — `apply_cohort_import(project_root, plan, *, exclude=frozenset()) -> list[str]`

Returns the **id list** directly (no wrapping dict), so the CLI's existing
`{**plan.model_dump(), "applied": apply(...)}` merge yields a flat result.
Mirrors single `apply_import`'s snapshot + mutated-set self-rollback, cohort-wide.

1. **Root + shape validation (before any read set or byte move):**
   `plan.project_root == str(project_root)`; `plan_type`/`schema_version` known
   (else clean error, no mutation); `len(members) ≥ 2`; numbers ordered and
   **contiguous**; entity_ids, source_rels, dest_rels each **unique**; source and
   destination sets **disjoint**. Per member: containment (`resolve_within`),
   canonical destination for `plan.kind`, identity coherence (reuse
   `_validate_plan_for_apply` per member with `plan.kind`).
2. **Source drift:** every source still hashes to its `source_sha256`, else refuse.
3. **Re-derive and compare the external report from the LIVE corpus** *before*
   any snapshot: `plan_reference_rewrite(root, {source→entity_id}, {source→dest},
   exclude=exclude | {all sources, all dests, plan artifact})`; require the
   re-derived `RewriteReport` to equal the frozen `plan.ref_report` **in its
   entirety** — substitution maps, `edits`, **and** every other collection
   (`manual`, `skipped`, …) — not merely its maps and edits. A divergence in any
   field means the live corpus no longer matches what was approved, so refuse.
   This proves the persisted edit paths against the real corpus so a hand-edited
   (but correctly re-enveloped) plan cannot feed escaping/incoherent paths into
   the snapshot. (The subsequent `apply_reference_rewrite` retains its own
   immediate pre-write re-derivation to close the write-time race.)
4. **Snapshot** the now-verified read set: every source, every destination, and
   every file named in the (verified) `ref_report.edits`.
5. **Claim the number block:** for each member in order, **first prove** the
   destination the primitive will create — `plan.kind` + `dest_stem_i` resolves to
   exactly the validated `dest_rel_i` — *before* calling
   `claim_number_in_dir(root, plan.kind, number_i, dest_stem_i, rendered_text_i)`.
   The claim is self-cleaning (a caught failure leaves no destination). On a
   successful return, **immediately** record the returned path in the mutated set
   (so rollback owns the file the claim just created); then a defensive
   postcondition (returned path == `dest_rel_i`) — if it ever fires despite the
   pre-proof, explicitly unlink that exclusively-created path and raise. Any
   failed claim → roll back all → raise. The path is proven before creation, not
   after, so no created file can escape the mutated set.
6. **Unlink sources** (each after its destination is claimed) → mutated set.
7. **Inbound rewrite:** `apply_reference_rewrite(root, plan.ref_report,
   exclude=exclude | {all sources, all dests}, written=...)` → mutated set; drift
   → roll back, raise.
8. **Post-move audit:** resolve every inbound/outbound link for every destination;
   any dangling reference → roll back, raise.
9. **Return** `[entity_id for each member in plan-member order]`.

Rollback restores only paths this transaction mutated — the snapshot bounds what
*can* be restored, the mutated set bounds what *should* be.

## Apply-plan dispatch (CLI)

Read raw bytes once → `verify_envelope` (single read before parse) → parse JSON
once → dispatch on the discriminator:
- `plan_type == "cohort-import"` and known `schema_version` →
  `parse_cohort_import_plan` + `apply_cohort_import`.
- **no** `plan_type` **and no** `schema_version` (legacy single plan) →
  `parse_import_plan` + `apply_import`.
- any other `plan_type`, an unknown `schema_version`, **or** a plan with a
  `schema_version` but no `plan_type` → clean error, no mutation. A version
  stamp without a discriminator is not treated as permissive legacy; it is
  rejected rather than silently routed to the single-plan parser.

## Error handling

| Condition | When | Result |
|---|---|---|
| `< 2` sources to cohort planner | plan | raises (CLI selects single path by count) |
| duplicate resolved sources | plan | `EntityImportError`, nothing written |
| member links to / mentions another member or itself | plan | `RefDependentCohortError` naming the pair |
| `--title`/`--slug` with 2+ sources | CLI | `UsageError` |
| `--save-plan` equals any resolved source (even `--overwrite-plan`) | CLI | `UsageError` |
| re-derived report ≠ frozen `ref_report` | apply | refuse before snapshot |
| number committed/archived/reserved since preview | apply | whole-cohort rollback + raise |
| any source changed since preview | apply | refuse before mutation |
| claim path ≠ validated destination | apply | whole-cohort rollback + raise |
| ref-rewrite drift / audit dangling ref | apply | whole-cohort rollback + raise |
| envelope missing / sha mismatch | apply | existing upstream refusal, no mutation |
| unknown `plan_type` / `schema_version`, or `schema_version` with no `plan_type` | apply | clean error, no mutation |

## Testing

- **Happy path:** cohort of 3 independent plans → contiguous numbers `base..base+2`;
  all sources moved; a shared **external** referrer of two members has **both**
  links repointed in one pass; `applied` is the id list in member order.
- **One-read:** a source whose bytes would differ between two reads is planned
  from a single cached read (scanner `source_overrides`) — no torn plan.
- **Override enumeration:** a member source that is deleted / renamed / grown past
  the scan-size limit **after** its cached read is still examined by the
  independence guard via its override entry (proves overrides drive enumeration,
  not just reads); an excluded path with an override is not scanned (exclude wins).
- **Single-import title/slug preserved:** `--title`/`--slug` on a single source
  still set the entity's title/slug end-to-end (byte-equal to today), confirming
  the `_plan_member` extraction kept those parameters.
- **Independence guard:** member B links member A (markdown) → reject; a bare-prose
  path mention of a member → reject (proves the `manual` branch); a self-link →
  reject.
- **Self-cleaning claim:** inject a write/close failure after the exclusive
  `open` → no partial destination remains (single-importer regression too).
- **Atomicity:** pre-claim one cohort number after preview → apply fails with **no
  partial** (no dest created, no source unlinked, referrers untouched); a raised
  inbound-rewrite → full rollback; a dangling-ref audit → full rollback.
- **Persisted-report safety:** a hand-edited (correctly re-enveloped) plan whose
  `ref_report.edits` name an escaping/incoherent path → refused at the re-derive
  equality check **before** snapshot.
- **`kind` single authority:** a member destination that would resolve into
  another kind's directory is impossible (no `member.kind`); the claim-path ==
  validated-dest assertion is exercised.
- **Drift / envelope:** edit a source after preview → refuse; tamper plan bytes →
  envelope refusal.
- **Shape validation:** non-contiguous numbers / duplicate ids / overlapping
  source∩dest / a `ref_report` map disagreeing with members → refused at apply
  before mutation.
- **CLI matrix:** 2+ sources with `--title` → `UsageError`; `--save-plan` equal to
  a source (with and without `--overwrite-plan`) → `UsageError`; `--apply-plan`
  with a source → `UsageError`; `--apply-plan` with `--title`/`--status`/`--slug`/
  `--save-plan`/`--overwrite-plan` → `UsageError` (the deliberate tightening).
- **Manual findings:** a cohort with an auto-unrewritable external reference plans
  successfully and surfaces it in `ref_report.manual`.
- **Regression / compat:** single-source import unchanged end-to-end (byte-equal
  saved plan, object-shaped `applied`); `_plan_member` extraction behavior-preserving;
  a legacy single-plan file (no `plan_type`) still applies via the single path.
- **Discriminator:** unknown `plan_type`, unknown `schema_version`, and a
  `schema_version` present with **no** `plan_type` each refuse cleanly; a legacy
  plan with neither field still routes to the single path.
- **Claim-path proof:** the destination is proven from `plan.kind`+`dest_stem`
  before the primitive runs; a forced post-claim mismatch unlinks the
  exclusively-created file (nothing escapes the mutated set).

## Versioning

Bump `0.5.1 → 0.5.2`: `science/pyproject.toml`, `.claude-plugin/plugin.json`,
`science/tests/test_cli_version.py`, and `science/uv.lock` (re-locked). The
floor-checking `test_agent_cli_compatibility.py` needs no pinned-value edit.

## Consumer delivery

After merge + push, natural-systems re-pins science `0.5.2` (surgical `uv.lock`
edit + `expected_science_revision.txt` + a surface test exercising cohort
save-plan/apply-plan) — the same gate the envelope used. Plan 2 v5 then drops the
overlay and calls cohort import for its batch's import moves.

## Alternatives considered

1. **Sibling `CohortImportPlan` (chosen)** — additive; preserves the single-import
   saved-plan and result contracts (bar the deliberate apply-plan tightening).
2. **Unified one-or-many plan** — internally tidy, but needlessly changes the
   established single saved-plan and result shapes and their tests.
3. **Composition of single plans** — smallest code, but cannot provide one
   numbering decision, one inbound rewrite pass, or cohort-wide rollback; it is
   precisely the overlay approach that fails on the embedded `project_root`.
