---
title: Cohort Import for `science entities import` — Design
status: proposed
created: '2026-07-19'
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
  real root; one combined inbound reference rewrite over external referrers;
  exception-atomic all-or-nothing apply; the mandatory approval envelope
  (`--expected-plan-sha256`, science 0.5.1).
- **Out:** mixed kinds in one cohort; per-member title/slug overrides;
  cross-member reference repointing (cohorts are required to be
  reference-independent — see below); crash-durability of standalone cohort
  apply (delegated to the caller's transaction journal); any change to the
  single-import contract.

## Non-goals / explicit boundaries

- **Cohorts are reference-independent.** A member may not link to another member
  of the same cohort. This is enforced (rejected at plan time), not assumed. It
  keeps all cross-member link-repointing logic out of scope. Cross-referencing
  documents are imported in **separate** batches, where the existing
  single-import inbound rewrite already repoints each still-loose referrer as its
  target lands — so correctness is preserved without cohort-internal cross-member
  logic.
- **Standalone cohort apply is exception-atomic, not crash-durable.** Sequential
  `claim_number_in_dir` calls create/write/release one member at a time; rollback
  covers *caught* failures (a failed claim, source drift, a raised rewrite, a
  failed audit) by restoring everything already mutated. Abrupt process death
  (SIGKILL) can still leave a partial cohort on disk. That is acceptable **only**
  because Plan 2 wraps every apply in its own snapshot + write-ahead journal and
  owns crash recovery. This boundary is stated, not hidden.

## Public surface

Single-source invocation is **unchanged** — same command, same `ImportPlan`,
same `--title`/`--slug` ergonomics, same result shape, same tests. The cohort
path is triggered purely by passing **2+ positional sources**:

```
# preview (writes a self-contained plan)
science entities import A.md B.md C.md --kind plan --save-plan p.json

# apply (approval envelope mandatory, science 0.5.1)
science entities import --apply-plan p.json --expected-plan-sha256 SHA
```

### CLI option matrix (enforced, not ignored)

| Invocation | `--kind` | `--status` | `--title` / `--slug` | sources | `--save-plan` |
|---|---|---|---|---|---|
| 1 source (single) | required | optional | **allowed** | exactly 1 | optional |
| 2+ sources (cohort) | required, uniform | optional, uniform | **rejected** (UsageError) | 2+ distinct | optional |
| `--apply-plan` | rejected | rejected | rejected | **none** | rejected |

`--kind` and (if retained) `--status` apply uniformly to the whole cohort.
Passing `--title`/`--slug` with 2+ sources is a hard `UsageError`, never a silent
ignore. `--apply-plan` continues to reject all sources and all preview options.

## Data model

### The shared member-planner refactor

Extract the number-taking core of `plan_import` into a helper that does **no**
inbound scan:

```python
def _plan_member(
    project_root: Path, source: Path, *, kind: str, number: int,
    title: str | None = None, status: str | None = None, slug: str | None = None,
    today: date | None = None,
) -> ImportMember:
    """Parse one source, construct identity, rebase its OWN outbound links into
    rendered_text, run prospective-write validation, and render. Takes a FORCED
    number; performs NO inbound reference scan."""
```

`plan_import` becomes `_plan_member(..., number=propose_number(root, kind))`
followed by its existing single-source inbound scan — behavior-preserving for
single import. `plan_cohort_import` calls `_plan_member` per source with forced
sequential numbers, then runs **one** combined inbound scan. Single and cohort
share exactly one member-planner; only the inbound-scan wrapper differs.

`ImportMember` carries the per-document facts:
`source_rel, source_sha256, entity_id, kind, number, dest_rel, title, status,
frontmatter, rendered_text` (the member's own outbound links already rebased
into `rendered_text` via `rewrite_outbound_links`, exactly as single import
bakes them today).

### `CohortImportPlan`

```
CohortImportPlan {
  plan_type: "cohort-import"          # discriminator (single ImportPlan has none)
  schema_version: 1
  project_root: str                    # embedded + apply-checked, like single
  kind: str                            # uniform across members
  members: list[ImportMember]          # 2+, in plan-member order
  ref_report: RewriteReport            # ONE combined inbound rewrite, external referrers only
  warnings: list[dict]                 # each attributed to a source_rel
}
```

- `extra="forbid"` on the model.
- `warnings` are aggregated across members but each entry names its
  `source_rel`, so a warning is never ambiguous about which document raised it.
- The single `ImportPlan` gains **no** field, stays byte- and schema-compatible;
  its saved plans and result shape are untouched.

## Planning — `plan_cohort_import(project_root, sources, *, kind, status=None, today=None)`

1. **Pre-flight:** ≥2 sources; resolve each; reject **duplicate resolved
   sources** before any planning; each source is a readable UTF-8 file.
2. **Number block:** `base = propose_number(root, kind)`; assign
   `number_i = base + i` for member `i` in **input order** (contiguous, ordered).
3. **Per member:** `member_i = _plan_member(root, source_i, kind=kind,
   number=number_i, status=status, today=today)` — derives title/slug/dest,
   rebases its own outbound links into `rendered_text`, hashes the source.
4. **Reference-independence guard (one proven scan):** run
   `plan_reference_rewrite(root, id_substitutions={source_rel_i → entity_id_i},
   path_substitutions={source_rel_i → dest_rel_i}, exclude={saved-plan artifact
   only})` — i.e. **do not exclude the members**. Inspect the resulting report:
   any `hit` **or** `manual` whose `rel_path` is a member source ⇒ the cohort is
   reference-dependent (a member links to, or bare-path-mentions, another member,
   or itself) ⇒ raise `RefDependentCohortError` naming the offending
   source/target pair. (A self-link — a member substituting into its own body —
   is treated as member-local and likewise rejected; degenerate and not worth a
   special case.) If there are **no** member-local findings, the members
   contributed nothing to the report, so that same report **is** the external
   inbound report — reuse it directly as `ref_report`.
5. **Assemble** `CohortImportPlan`, sorted deterministically; warnings keyed by
   `source_rel`.

The scan in step 4 does double duty — it is the independence guard **and** the
external inbound report — so external referrers are repointed against the whole
cohort map in a single pass (the scanner already applies an N-entry
substitution map; only single-move callers exist today).

## Apply — `apply_cohort_import(project_root, plan, *, exclude=frozenset())`

Mirrors single `apply_import`'s snapshot + mutated-set self-rollback, extended
across the whole cohort.

1. **Root + shape validation (before any byte moves):**
   `plan.project_root == str(project_root)`; `plan_type`/`schema_version` known;
   `len(members) ≥ 2`; numbers **ordered and contiguous** from their base;
   entity_ids, source_rels, dest_rels each **unique**; source set and destination
   set **disjoint**; and the `ref_report` substitution maps **exactly equal** the
   member mapping (`{source_rel_i: dest_rel_i}` / `{source_rel_i: entity_id_i}`) —
   no extra, no missing. Per-member: containment, canonical destination, identity
   coherence (reuse `_validate_plan_for_apply` per member).
2. **Source drift:** every source still hashes to its `source_sha256`, else
   refuse (a source edited during review must force a fresh preview).
3. **Snapshot:** every source, every destination, and every file named in
   `ref_report.edits` (the concrete writes — not merely `hits`).
4. **Claim the number block:** for each member in order,
   `claim_number_in_dir(root, kind, number_i, dest_stem_i, rendered_text_i)`.
   A destination joins the mutated set **as soon as its exclusive creation
   begins** (so a partially-written destination from a raised write is still
   rolled back). Any failed claim (number committed/archived/reserved since
   preview) → roll back all mutations, raise.
5. **Unlink sources** (each after its destination is claimed) → mutated set.
6. **Inbound rewrite:** `apply_reference_rewrite(root, plan.ref_report,
   exclude=exclude | {all sources, all dests}, written=...)` for external
   referrers; drift against the frozen report → roll back, raise.
7. **Post-move audit:** resolve every inbound/outbound link for every destination;
   any dangling reference → roll back, raise.
8. **Result:** `{"applied": [entity_id for each member in plan-member order],
   ...}` — `applied` is a **list** (consistent with archive/mark-superseded;
   single import keeps its object shape). The plan already carries the complete
   mapping, so an id list is sufficient.

Rollback restores only paths this transaction mutated (the `mutated` set), never
a referrer another writer changed — the snapshot bounds what *can* be restored;
`mutated` bounds what *should* be, exactly as single import documents.

## Apply-plan dispatch (CLI)

The `--apply-plan` branch reads the raw bytes once, verifies the envelope
(`verify_envelope`, single read before parse), then dispatches on the parsed
discriminator: `plan_type == "cohort-import"` → `parse_cohort_import_plan` +
`apply_cohort_import`; absent `plan_type` → legacy `parse_import_plan` +
`apply_import`; any other/unknown `plan_type` or unknown `schema_version` → a
clean error, no mutation.

## Error handling

| Condition | When | Result |
|---|---|---|
| < 2 sources to cohort planner | plan | falls through to single path (not a cohort) |
| duplicate resolved sources | plan | `EntityImportError`, nothing written |
| member links to another member / self | plan | `RefDependentCohortError` naming the pair |
| `--title`/`--slug` with 2+ sources | CLI | `UsageError` |
| number committed/archived/reserved since preview | apply | whole-cohort rollback + raise |
| any source changed since preview | apply | refuse before mutation |
| ref-rewrite drift vs frozen report | apply | whole-cohort rollback + raise |
| post-move audit dangling ref | apply | whole-cohort rollback + raise |
| envelope missing / sha mismatch | apply | existing upstream refusal, no mutation |
| unknown `plan_type` / `schema_version` | apply | clean error, no mutation |

## Testing

- **Happy path:** cohort of 3 independent plans → contiguous numbers `base..base+2`;
  all three sources moved to canonical destinations; a shared **external**
  referrer of two members has **both** links repointed in one pass; `applied` is
  the id list in member order.
- **Independence guard:** a cohort where member B links to member A (markdown
  link) → `RefDependentCohortError`; a bare-prose path mention of a member →
  rejected too (proves the `manual` branch); a self-link → rejected.
- **Atomicity:** pre-claim one of the cohort's numbers in the live tree after
  preview → apply fails with **no partial** (no destination created, no source
  unlinked, referrers untouched); a raised inbound-rewrite → full rollback;
  a dangling-ref audit failure → full rollback.
- **Drift:** edit one source after preview → apply refuses; tamper the plan bytes
  → envelope refusal.
- **Shape validation:** a plan with non-contiguous numbers / duplicate ids /
  overlapping source∩dest / a `ref_report` map that disagrees with the members →
  rejected at apply before mutation.
- **CLI matrix:** 2+ sources with `--title` → `UsageError`; `--apply-plan` with a
  source → `UsageError`.
- **Regression / compat:** single-source import unchanged end-to-end (byte-equal
  saved plan, object-shaped `applied`); the `_plan_member` extraction is
  behavior-preserving for single import (existing suite green); a legacy
  single-plan file (no `plan_type`) still applies via the single path.
- **Discriminator:** an unknown `plan_type` and an unknown `schema_version` each
  refuse cleanly.

## Versioning

Bump `0.5.1 → 0.5.2`: `science/pyproject.toml`, `.claude-plugin/plugin.json`,
`science/tests/test_cli_version.py`, and `science/uv.lock` (re-locked). The
acceptance/compat test that checks a floor (`test_agent_cli_compatibility.py`)
needs no pinned-value edit.

## Consumer delivery

After merge + push, natural-systems re-pins science `0.5.2` (surgical `uv.lock`
edit + `expected_science_revision.txt` + a surface test exercising cohort
save-plan/apply-plan) — the same gate the envelope used. Plan 2 v5 then drops the
overlay and calls cohort import for its batch's import moves.

## Alternatives considered

1. **Sibling `CohortImportPlan` (chosen)** — additive; preserves the single-import
   saved-plan and result contracts intact.
2. **Unified one-or-many plan** — internally tidy, but needlessly changes the
   established single saved-plan and result shapes and their tests.
3. **Composition of single plans** — smallest code, but cannot provide one
   numbering decision, one inbound rewrite pass, or cohort-wide rollback; it is
   precisely the overlay approach that fails on the embedded `project_root`.
