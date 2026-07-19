---
title: Ship the spec id-remap migration; stage the resolution flip (S3b)
status: design
created: '2026-07-18'
---

# Ship `migrate-specs`; Stage the `spec:` Resolution Flip (S3b)

**Program:** curation S1–S5. This is **S3b**, the deferred second half of S3.
S1 (scope certification), S2 (adaptive rotation), S3a (`spec` as a first-class
creatable/importable entity kind), and S4 (correspondence-drift screen) are all
shipped and merged to local main.

**Goal.** Ship a `science entity migrate-specs` command that canonicalizes a
project's legacy / loose `spec`-typed docs into numeric
`entities/specs/NNNN-slug.md` entities, preserving each old id as an alias and
repointing the references the migration engine can safely rewrite. **`spec`
stays annotation-only in this effort** — the global resolution flip is a
separate, gated follow-on step (see Rollout staging).

**Scope: toolkit-only.** The command, its projection/classification contracts,
the batch coordinator, tests (real legacy frontmatter shapes), and docs are
built in this repo. The migrations of natural-systems, cbioportal, and
multiple-myeloma are separate per-repo efforts and are out of scope here.

## Rollout staging (the load-bearing correction)

The migrate command ships **in the same toolkit revision** as any resolution
flip would. Consumers pin the toolkit by exact revision in `uv.lock`, so
"migrate first, then bump the pin" is **not executable** if the flip and the
command arrive together: before the bump the project has neither the command nor
the break; after the bump it has both at once. Pinning delays the break; it does
not remove the migration cliff. Therefore the flip must **follow** the command
across separate revisions:

1. **This effort — ship `migrate-specs` while `spec` stays annotation-only.**
   `_ANNOTATION_REF_PREFIXES` is unchanged (`frozenset({"meta", "spec"})`).
   `spec:` references remain skipped, so nothing breaks anywhere; a project can
   bump its pin, get the command, and run the migration with zero resolution
   pressure.
2. **Downstream — run the migrations** (natural-systems, cbioportal,
   multiple-myeloma), each its own per-repo effort. Each leaves numeric spec
   entities carrying old-id aliases and repointed structured refs.
3. **Later, gated effort — remove `spec` from `_ANNOTATION_REF_PREFIXES`**, only
   after the surveyed projects are clean. That step inverts S3a's
   `test_spec_materialization.py` edge-absence guard and flips the two `spec:`
   assertions in `test_meta_reference.py`; those test changes belong to that
   step, not this one.

Because this effort does not flip the switch, the S3a guard tests
(`test_spec_materialization.py`, `test_meta_reference.py:26-28`,
`test_membership_materialize.py`) are **left untouched**. The migration's job is
to make each project *flip-ready*, not to flip.

## The `discusses` correction (why an alias cannot save every ref)

A `spec:` membership/`discusses` reference can **never** become valid, migration
or not. Three gates confirm it:

- **String-form `spec:` in `discusses` is skipped today** as a metadata reference
  (`materialize.py:832-833`), so it silently drops — no membership node.
- **Post-flip, unresolved** → `materialize.py:837-842` raises
  `"… does not resolve to a known entity; a discusses frame must resolve to a
  bundle (spec §5)."`
- **Post-flip, resolved to a `spec`** → `emit_discusses_membership`
  (`graph/io.py:67-73`) raises `"… is a 'spec', not a bundle
  (hypothesis/mechanism); membership roles are only valid on bundle frames."`

Membership frames are strictly `hypothesis`/`mechanism`. So a `spec:` in
`discusses` must be **retargeted away from the spec entirely** (a project
judgment), which the old-id alias does **not** address. The migration therefore
**reports** every `spec:` membership reference for manual retargeting and makes
no claim that migration fixes it. `reference_rewrite` does not touch `discusses`
at all (neither rewrite nor report; see Component 3), so the command must scan
`discusses` itself to surface these.

## Component 1 — discovery and the singleton contract

`migrate-specs` discovers, over the project tree:

1. **Legacy spec docs to relocate** — every file whose frontmatter declares
   `type: spec` **or** `kind: spec`, with a declared `id: spec:…`, that is **not
   already** a conforming `entities/specs/NNNN-slug.md` entity **and is not at a
   singleton home**. A file lacking a declared `id:` is **refused** (planning
   error) — identity is authoritative and never guessed from a filename.
2. **Singleton-home spec files** — a `kind:/type: spec` file at a singleton home
   (e.g. `entities/research-question.md`, `kind: spec`, id
   `spec:research-question`). These are **reported, never auto-relocated**:
   whether such a file is a mis-kinded research-question or a spec that landed at
   the wrong path is project judgment. This resolves the design conflict a
   reviewer flagged — "relocate every nonconforming spec" now explicitly excludes
   singleton homes.
3. **Inbound `spec:` references** — every `spec:` token across all surfaces
   (frontmatter reference fields, `relations[].target`, the `spec:` frontmatter
   *key*, `discusses`/membership, markdown links, and prose/code mentions),
   classified in Component 3.

`entity_conformance` already skips singleton homes and only scans existing
`entities/<kind>/` dirs, so the discovery walk must scan the whole tree, not just
`entities/` — the loose docs live under `doc/plans/` and `doc/specs/`.

## Component 2 — legacy frontmatter projection

A legacy spec doc already carries frontmatter, so `plan_import` **cannot** run on
it — it refuses any source with frontmatter (`entity_import.py:140-144`: "An
entity that already carries an id needs a move, not an import."). `migrate-specs`
therefore performs an explicit, tested **projection** from legacy frontmatter to
the canonical `spec` schema, then a move (not an import). Real NS inputs (sampled
from the worktree) look like:

```yaml
id: "spec:2026-03-16-meta-model-design"
type: "spec"
title: "Meta-Model Design: A Typed Compositional Theory of Natural Models"
date: 2026-03-16
status: approved
related_questions:
  - question:0001-model-granularity
  - question:0005-compositional-relationships-between-models
```

### Field mapping

The **field authority** — what counts as "recognized" — is explicit, because
`extra=ignore` makes "unrecognized" otherwise undefined: a key is recognized iff
it is a declared field of the canonical `Entity` model (`Entity.model_fields`)
**or** one of the projection's named legacy-alias keys (`type`, `date`,
`related_questions`, `related_specs`). Any frontmatter key outside that union
refuses planning.

| Legacy | Canonical | Rule |
|---|---|---|
| `id: spec:<old>` | `id: spec:NNNN-slug` | Old id is authoritative for identity + the alias; the new numeric id is minted (Component 4). Old id appended to `aliases:`. |
| `type: spec` | `kind: spec` | `type` is the legacy spelling; project to `kind`. If both present and disagree → refuse. |
| `date: <d>` | `created`, `updated` | **Independent**: `created = existing created or date`; `updated = existing updated or date`. **Refuse** if either is still absent afterward (e.g. a doc with `created` but no `updated` and no `date`). `date` is dropped once consumed. |
| `title` | `title` | Preserved. |
| `related_questions`, `related_specs` | `related` | Folded into canonical `related` (they hold entity refs); `extra=ignore` would otherwise silently drop them on load, so projection is mandatory. **Existing `related` is preserved and the union is order-preservingly deduplicated** (first occurrence wins). |
| existing `aliases` | `aliases` | Preserved; the old id is appended and the list order-preservingly deduplicated (Component 2 identity contract). |
| any other key not in the field authority | — | **Refuse** planning, naming the key and file. No silent drop; the operator pre-edits or the projection is extended. |

### Status adjudication

The canonical `spec` vocabulary is `draft / active / complete / superseded /
retired / archived` (S3a). Legacy statuses are projected only where the mapping
is unambiguous:

| Legacy status | Canonical |
|---|---|
| `draft`, `proposed`, `design` | `draft` |
| `active`, `in-progress`, `current` | `active` |
| `complete`, `completed`, `implemented` | `complete` |
| `superseded`, `retired`, `archived` | (identity) |

Any status **outside both** the canonical set and this table — notably
`approved` (the dominant NS status), `ready-with-caveats`, `draft-for-review`,
`not-ready` — is **refused**, listed per file. These encode "design approved,
implementation not started," which straddles `draft` and `active`; auto-choosing
either would be tuning metadata to pass, which the program forbids. **The operator
resolves each by pre-editing that doc's status** — the v1 contract has no
`--status` override. A single batch-wide override would silently recolor
already-unambiguous docs (an `implemented→complete` and a `draft→draft` doc both
forced to the operator's choice for an unrelated `approved` record); a
per-old-id adjudication map is possible later but is deferred as unnecessary
complexity. The projection never invents a status silently.

### Identity and alias contract

- The declared `id: spec:<old>` is **required and authoritative** (refuse if
  absent).
- The migrated entity records the old id in its frontmatter `aliases:` list, so
  it registers at `_PROV_FRONTMATTER` in `build_alias_map`
  (`sources.py:764-768`). Post-flip, any un-rewritten inbound reference to the
  old id still resolves to the new numeric entity.
- **Duplicate old ids** across the discovered set → refuse planning.
- **Alias collisions** → refuse planning: if a proposed old-id alias is already
  claimed by a different canonical id (a live entity, a canonical id, or an
  archive token), `build_alias_map` would raise `AliasCollisionError`
  (`sources.py:752-754`). The command pre-checks this at plan time and refuses,
  rather than discovering it at a later graph build.

## Component 3 — reference classification (two orthogonal axes)

A reference has two independent properties; the earlier four-bucket scheme
conflated them (a prose mention of a cross-kind id is *both*). Classify on two
axes:

**Surface — where the reference lives** (this determines whether it is
machine-rewritable, and by which map):

| Surface | Handled by `reference_rewrite`? |
|---|---|
| `related` + the other 10 `_REMOVABLE_FRONTMATTER_REF_KEYS` (`entities.py:1311-1325`) | **rewritten** via `id_substitutions` |
| `relations[].target` | **rewritten** (special-cased) |
| markdown path-links in prose | **rewritten** via `path_substitutions` (fences skipped) |
| `discusses` / membership | **not touched, not reported** — invisible |
| the `spec:` frontmatter *key* | **not touched, not reported** — invisible |
| `participants`, `propositions`, `same_as`, `blocked_by`, `evidence_refs`, `source`, `commits_to` | **not touched, not reported** — invisible |
| prose/code mention of an old *canonical id* (not a path) | **not touched, not reported** — invisible |

**Token boundary (deterministic scanning).** The inventory scanner matches a
`spec:` token only with an explicit **left boundary** (not preceded by
`[A-Za-z0-9_-]`) so `science-spec:2026-04-19-…` — which really occurs in mm — is
**not** parsed as an embedded `spec:` token, and a **right boundary** that stops
at the id charset (`[A-Za-z0-9._/-]`) with trailing punctuation trimmed (mm has a
`spec:…design.` sentence-final case).

**Target — classified by evidence, never by similarity:**

| Target class | Evidence (exact, deterministic) |
|---|---|
| migrated-spec | the token **exactly equals** a discovered legacy spec's declared old id (has an `id_substitution`) |
| already-canonical | the token **exactly equals** a live numeric spec id or one of its aliases |
| cross-kind | the token appears in an **explicit operator retarget mapping** (`old-id → other-kind-id`); never inferred |
| unresolved | everything else — no matching id, no operator mapping |

No title/slug-similarity inference is used to guess a target: an unmatched token
is `unresolved`, not silently attached to a look-alike entity.

**The command's rewrite rule:** auto-rewrite a reference **iff** its surface is
one `reference_rewrite` handles **and** its target is `migrated-spec`. Everything
else is **reported**, grouped by (surface, target) with counts. The report groups
are:

- **rewritten** — surface-handled, target migrated-spec.
- **alias-resolved** — target migrated-spec, on a materializer-**read** but
  rewriter-invisible frontmatter field (`same_as`, `blocked_by`, `evidence_refs`,
  `participants`, `propositions`, `source`, `commits_to`). Not rewritten, but a
  consumer reads the field and the old-id alias makes it resolve post-flip.
  Reported for optional cleanup; does **not** block flip-readiness.
- **identity-preserved (inert)** — target migrated-spec, but on a surface **no
  consumer reads** (prose/code mentions of the old id, the `spec:` frontmatter
  *key*). The alias preserves the identity mapping but nothing resolves these —
  they are informational, not a resolution concern, and do not block
  flip-readiness. (Wording matters: these are *preserved*, not *resolved*.)
- **manual-retarget** — `discusses`/membership refs (invalid post-flip
  regardless — the alias cannot save them, Issue 1), `cross-kind`, and
  `unresolved` targets. A human must retarget or remove them; these **block
  flip-readiness** (Flip-readiness contract).

This is the **honest narrow contract**: the command does not claim to rewrite
surfaces the engine cannot. A shared structured-reference traversal authority
covering all frontmatter fields is separable work, listed out of scope.

## Component 4 — the batch coordinator (new orchestration)

`apply_import` is a **complete per-document transaction** (`entity_import.py:537-620`):
per-doc gates → one `_snapshot(touched)` → `try:` claim dest → unlink source →
replay that doc's rewrite → audit that doc → `except:` restore. It cannot perform
"all moves, then one batch rewrite," and `migrate_hypothesis` supplies a
journal/resume pattern, **not** a reusable batch engine. So `migrate-specs`
composes a **new** coordinator from the extractable low-level primitives —
`_snapshot`/`_restore` (arbitrary path list + `restrict` set), `claim_number_in_dir`,
`apply_reference_rewrite` (already batch-friendly: `written` accumulator +
`exclude`), and `audit_moved_references` — welding none of them into per-doc order.

### Deterministic batch numbering

`propose_number` (`entity_reservation.py:167-181`) is read-only and idempotent —
called once per doc it returns the same `highest+1` every time. So the plan calls
it **once** for the starting number, sorts the discovered legacy specs by a
deterministic key (old id), and assigns `start, start+1, …` sequentially. The
real collision gate is per-doc `claim_number_in_dir` at apply, whose
`O_CREAT|O_EXCL` sentinel re-checks committed + archived numbers — so a number
consumed by concurrent work between plan and apply fails the claim and rolls the
batch back (tested via live/archive collision drift).

### The moved docs are excluded from the corpus replay

The merged `RewriteReport` is frozen at plan time and replayed after the moves,
so its inbound scan must exclude **every source and every destination**, at
**both** plan and replay, identically — otherwise the post-move fresh scan
diverges from the frozen plan and `apply_reference_rewrite` raises
`ReferenceDriftError`. `apply_import` already does this for one doc
(`entity_import.py:211`, `exclude=exclude | {source}`); the batch coordinator
excludes the whole `{sources ∪ destinations}` set. Consequently each **migrating
doc is handled per-destination, not by the corpus replay**, and each destination
separately receives, immediately before its own mutation:

- **source-SHA verification** against the plan's recorded hash (the per-doc gate
  from `apply_import:570-578`, which cannot be batched away);
- **outbound-link rebasing** via `rewrite_outbound_links`
  (`reference_rewrite.py:252`) — its own relative Markdown links move with it
  from `doc/plans/…` to `entities/specs/…`;
- **intra-batch id substitution** in its projected frontmatter — a migrating spec
  that references *another* migrating spec must have that ref rewritten to the
  neighbor's new numeric id (the merged `id_substitutions`), since the corpus
  replay skips it.

The single corpus-wide `apply_reference_rewrite` then rewrites only the
**non-migrating referrers**.

### The batch transaction

1. **Preflight all** — project-root check; project each legacy doc (Component 2,
   refusing on unmappable status / unknown key / missing id / unresolved date);
   render every destination, apply intra-batch id substitution, and validate it
   through `_validate_prospective_write`; assign sequential numbers; build the
   merged `id_substitutions` / `path_substitutions`, the single merged
   `RewriteReport` (scanned with the `{sources ∪ destinations}` exclusion), and
   the per-path journal plan; pre-check alias collisions. **Nothing is written;
   any refusal aborts the whole batch.**
2. **Snapshot all** — one `_snapshot` over the union of every source, every
   destination, and every non-migrating referrer named in the merged report.
3. **Move all** — per doc: verify source SHA, `claim_number_in_dir` the
   destination, write the projected+rebased+substituted entity, unlink the
   source (each path enters `mutated` only after its step succeeds).
4. **Replay once** — a single `apply_reference_rewrite` over the merged report
   (same exclusion as plan), accumulating `written`.
5. **Audit all** — `audit_moved_references` for every moved destination.
6. **Global restore on any caught failure** — `_restore(snapshot,
   restrict={*mutated, *written})`, delete the journal, then re-raise. One
   rollback set for the whole batch.

### Journal + resume (per-path, crash-safe)

Coarse phase markers are insufficient: a crash *within* "move all" or
`apply_reference_rewrite` lands before any phase advances, and
`apply_reference_rewrite` is **not idempotent** — an already-written postimage
fails its fresh-report comparison on a naive replay. So the journal is
**per-path**, recording for every path the transaction will touch: its role
(moved-source / moved-dest / referrer), its **preimage hash**, and its expected
**postimage hash**.

`--resume` never re-plans. For each journaled path it reads the current on-disk
state and:

- **postimage hash** → that action already completed; skip it.
- **preimage hash** → not yet done; perform it.
- **any third state** → external drift since planning; **refuse** (do not guess),
  leaving the operator to restore or re-plan.

After completing every remaining action the resume verifies all postimages, then
deletes the journal. A successful **caught-failure restore also deletes the
journal** (step 6) — otherwise a later `--resume` could reapply a transaction
that was already rolled back. Plan-only (no `--apply`) writes nothing and no
journal.

## Component 5 — docs and the sequencing contract

- **User guide** (`docs/user-guide/entities.md`, near the Source Entity CLI
  material): document `science entity migrate-specs` — plan-then-`--apply`, the
  projection rules, the four report groups (rewritten / alias-resolved /
  identity-preserved / manual-retarget), the singleton report, the `flip_ready`
  field, and the refusal cases. State plainly that **`spec:` references still
  resolve as annotation-only today** — the command makes a project flip-ready; it
  does not change resolution.
- **Sequencing contract, stated honestly:** the resolution flip is a **future,
  separately-shipped** step gated on the surveyed projects being migrated. A
  project runs `migrate-specs` (bumping its pin to a revision that has the
  command but not the flip), lands clean, and only then adopts the later revision
  that flips resolution. Migrate-then-flip across revisions — not
  migrate-then-bump within one.
- No `sources.py` comment changes in this effort (the switch is not touched); the
  S3a comment already names the flip as S3b's future work.

## Flip-readiness contract (machine, not prose)

The command emits a machine-checkable `flip_ready` boolean in its report — the
actual gate the later resolution-flip step keys on, so "flip-ready" is never a
prose judgment. Given a project (post-`--apply`, or in a plan-only dry run):

- `flip_ready = true` **iff** `singleton_count == 0` **and**
  `manual_retarget_count == 0`.
- `singleton_count` = `kind:/type: spec` files at singleton homes still awaiting
  reconciliation (Component 1).
- `manual_retarget_count` = references in the **manual-retarget** group
  (`discusses`/membership, `cross-kind`, `unresolved`).
- `alias-resolved` and `identity-preserved` findings **may remain** with
  `flip_ready = true` — they resolve (or are inert) via the old-id alias.

The flip step (out of scope here) must refuse to run against a project whose
latest `migrate-specs` report is not `flip_ready`. The value is pinned in the
output schema and asserted in tests.

## Error handling / refusal cases (consolidated)

Planning refuses (writes nothing) on: a legacy spec doc without a declared `id:`;
`type`/`kind` disagreement; an unmappable legacy status; a `created`/`updated`
still absent after date projection; an unrecognized frontmatter key (outside the
field authority); a duplicate old id in the batch; a proposed old-id alias that
collides with an existing canonical id / alias / archive token; a rendered
destination that fails `_validate_prospective_write`. Apply additionally rolls
the whole batch back on: a `claim_number_in_dir` failure (number consumed since
planning), a `ReferenceDriftError` from `apply_reference_rewrite` (corpus changed
since planning), a `preimage_sha256` mismatch, or any non-empty
`audit_moved_references` result. `--resume` refuses on any journaled path in a
third state (neither preimage nor postimage). `manual-retarget` references
(`discusses`/membership, `cross-kind`, `unresolved`) are **reported**, never
silently resolved.

## Testing (real legacy shapes, synthetic project)

A fixture project built from the **real legacy shapes** (not an already-conforming
doc):

- **Projection**: a `type: spec` + `date:` + `status: approved` +
  `related_questions:` doc — assert `type→kind`, both `created` and `updated`
  seeded from `date`, `related_questions` folded into `related` with existing
  `related` preserved and deduplicated (order-preserving), old id appended to an
  existing `aliases` list and deduplicated; assert `status: approved` **refuses**;
  assert a key outside the field authority refuses; assert a doc with `created`
  but no `updated` and no `date` **refuses**; assert mappable statuses
  (`design→draft`, `implemented→complete`) project.
- **Batch numbering**: **≥2** legacy docs get **distinct sequential** ids
  (`spec:0001-…`, `spec:0002-…`); a collision-drift test where a `0001` entity
  appears (live or archive) between plan and apply → `claim` fails → whole batch
  restored.
- **Reference classification & token boundary**: `related: [spec:<old>]` →
  rewritten to numeric; `discusses: [spec:<old>]` → **manual-retarget** (both
  failure modes documented, no "migration fixes it" assertion); `same_as:
  [spec:<old>]` → **alias-resolved** (not rewritten, reported); a prose old-id
  mention → **identity-preserved** (reported, not called "resolved"); an
  operator-mapped `cross-kind` ref and an `unresolved` ref → manual-retarget; an
  already-`spec:NNNN` ref → unchanged; a **`science-spec:<old>` token is NOT
  matched** as a `spec:` reference, and a trailing-period `spec:<old>.` matches
  without the period.
- **Flip-readiness**: `flip_ready == false` while any singleton or
  manual-retarget remains; `flip_ready == true` once both are zero even with
  alias-resolved / identity-preserved findings present.
- **Identity**: missing `id:` refuses; duplicate old ids refuse; an old-id alias
  colliding with a live entity refuses at plan time.
- **Singleton**: a `kind: spec` file at `entities/research-question.md` is
  **reported, not relocated** (and counts toward `flip_ready == false`).
- **Transaction/resume**: apply relocates all docs, rewrites the covered refs
  (including an intra-batch spec→spec ref rewritten to its neighbor's new id),
  audits, and leaves a loadable tree (migrated entities build with their aliases
  and no `AliasCollisionError`); a per-path resume completes an interrupted
  journal (postimage paths skipped, preimage paths finished) without re-planning;
  a journaled path forced to a **third state refuses**; a caught-failure restore
  deletes the journal so a subsequent `--resume` does nothing.
- **Guard**: full suite green; `spec` remains in `_ANNOTATION_REF_PREFIXES`
  (assert the switch is untouched); the S3a guard tests still pass unchanged.

Follow the `test_migrate_hypothesis*.py` layout for plan/apply/resume coverage.

## Out of scope / follow-ons

- **The resolution flip** — removing `spec` from `_ANNOTATION_REF_PREFIXES`,
  inverting `test_spec_materialization.py`, and flipping `test_meta_reference.py`;
  a separate revision gated on the surveyed projects being clean (Rollout step 3).
- **Running the migration** on natural-systems (34 date-slug `doc/plans` specs +
  3 semantic `doc/specs` specs + the mis-kinded singleton; ~151 refs; 2 dead
  refs; pre-registration `spec:` key values), cbioportal (one singleton, 13
  refs), and multiple-myeloma (no surviving spec targets; both refs dangle; the
  43-entity `entities/design/*` re-import pool). Each is its own per-repo effort.
- **mm `design` → `spec` re-import** — a project migration.
- **A shared structured-reference traversal authority** covering all frontmatter
  reference fields (`discusses`, the `spec:` key, `participants`, `same_as`, …).
  Until it exists, those surfaces are alias-resolved, identity-preserved, or
  manual-retarget, not auto-rewritten.
- **Singleton reconciliation policy** — whether the `entities/research-question.md`
  `kind: spec` file becomes a numeric spec or is re-kinded is per-project
  judgment; the command reports it.

## Risks

Because the switch is not flipped, this effort adds no resolution pressure to any
project — `migrate-specs` is a read-only-by-default command whose `--apply` is a
rollback-safe batch transaction, and a project that never runs it is unaffected.
The residual risk lives in the batch coordinator (new orchestration): it is
mitigated by composing only the audited primitives, one global snapshot/restore,
the per-doc claim + hash + drift gates inherited from `apply_import`, and a
resume journal. The heavy real-world blast radius (NS's ~151 references) sits
entirely behind the out-of-scope per-repo migrations, and the alias safety-net
plus the honest (surface × target) report mean an un-rewritten reference resolves
rather than dangles once the flip finally lands — with `discusses` the one
documented exception that must be retargeted by hand.
