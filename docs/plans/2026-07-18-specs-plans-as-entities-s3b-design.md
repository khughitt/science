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

| Legacy | Canonical | Rule |
|---|---|---|
| `id: spec:<old>` | `id: spec:NNNN-slug` | Old id is authoritative for identity + the alias; the new numeric id is minted (Component 4). Old id → `aliases:`. |
| `type: spec` | `kind: spec` | `type` is the legacy spelling; project to `kind`. If both present and disagree → refuse. |
| `date: <d>` | `created: <d>`, `updated: <d>` | A single `date` seeds both when neither `created` nor `updated` is present; an existing `created`/`updated` is preserved and `date` is dropped. |
| `title` | `title` | Preserved. |
| `related_questions`, `related_specs` | `related` | Known legacy list fields are folded into canonical `related` (they hold entity refs). Because `Entity` is `extra=ignore`, leaving them unprojected would **silently drop** them on load — so projection is mandatory, not cosmetic. |
| any other unrecognized key | — | **Refuse** planning, naming the key and file. No silent drop; the operator decides (pre-edit or extend the projection). |

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
either would be tuning metadata to pass, which the program forbids. The operator
resolves them by pre-editing the doc's status or supplying an explicit
`--status <canonical>` override that applies to the whole batch. The projection
never invents a status silently.

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

**Target — what the reference points to:**

| Target class | Meaning |
|---|---|
| migrated-spec | names a legacy spec this batch relocates (has an `id_substitution`) |
| already-canonical-spec | already `spec:NNNN-slug`; **unchanged** — not a migration target |
| dead | a `spec:` id with no findable target (e.g. `spec:2026-01-01-x`) |
| cross-kind | a `spec:` id whose real home is another kind (e.g. mm's
  `spec:2026-04-11-bayesian-causal-dag-design` → `design:0025-…`) |

**The command's rewrite rule:** auto-rewrite a reference **iff** its surface is
one `reference_rewrite` handles **and** its target is `migrated-spec`. Everything
else is **reported**, grouped by (surface, target), with an explicit count. The
report distinguishes:

- **rewritten** — surface-handled, target migrated-spec.
- **alias-covered** — target migrated-spec but on an invisible surface
  (`discusses` excepted); not rewritten, but the old-id alias keeps it resolving
  post-flip. Reported so the operator can optionally clean it up.
- **manual-retarget** — `discusses`/membership refs (invalid post-flip
  regardless — Issue 1) and all `dead` / `cross-kind` targets. The alias does not
  save these; a human must retarget or remove them.

This is the **honest narrow contract**: the command does not claim to rewrite
surfaces the engine cannot. Building a shared structured-reference traversal
authority that covers all frontmatter fields is a real, separable piece of work
and is listed out of scope.

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

### The batch transaction

1. **Preflight all** — project-root check; project each legacy doc's frontmatter
   (Component 2, refusing on unmappable status / unknown key / missing id);
   render every destination and validate it through `_validate_prospective_write`;
   assign sequential numbers; build the merged `id_substitutions` /
   `path_substitutions` and the single merged `RewriteReport`; pre-check alias
   collisions. **Nothing is written; any refusal aborts the whole batch.**
2. **Snapshot all** — one `_snapshot` over the union of every source, every
   destination, and every referrer named in the merged report.
3. **Move all** — per doc: `claim_number_in_dir` the destination, write the
   projected entity, unlink the source (each path added to `mutated` only after
   its own step succeeds — the concurrency-safety bookkeeping from
   `apply_import`).
4. **Replay once** — a single `apply_reference_rewrite` over the merged report,
   accumulating `written`.
5. **Audit all** — `audit_moved_references` for every moved destination.
6. **Global restore on any caught failure** — `_restore(snapshot,
   restrict={*mutated, *written})`, then re-raise. One rollback set for the whole
   batch.

### Journal + resume

Mirror `migrate_hypothesis`'s journal discipline with batch-aware phases: the
plan is journaled before the first write; `--resume` replays an interrupted write
pass from the journal and never re-plans (so a crash between "move all" and
"replay once" resumes deterministically). Phases recorded: `planned`,
`moved`, `rewritten`, `audited`. Plan-only (no `--apply`) writes nothing and no
journal.

## Component 5 — docs and the sequencing contract

- **User guide** (`docs/user-guide/entities.md`, near the Source Entity CLI
  material): document `science entity migrate-specs` — plan-then-`--apply`, the
  projection rules, the three report groups (rewritten / alias-covered /
  manual-retarget), the singleton report, and the refusal cases. State plainly
  that **`spec:` references still resolve as annotation-only today** — the command
  makes a project flip-ready; it does not change resolution.
- **Sequencing contract, stated honestly:** the resolution flip is a **future,
  separately-shipped** step gated on the surveyed projects being migrated. A
  project runs `migrate-specs` (bumping its pin to a revision that has the
  command but not the flip), lands clean, and only then adopts the later revision
  that flips resolution. Migrate-then-flip across revisions — not
  migrate-then-bump within one.
- No `sources.py` comment changes in this effort (the switch is not touched); the
  S3a comment already names the flip as S3b's future work.

## Error handling / refusal cases (consolidated)

Planning refuses (writes nothing) on: a legacy spec doc without a declared `id:`;
`type`/`kind` disagreement; an unmappable legacy status; an unrecognized
frontmatter key; a duplicate old id in the batch; a proposed old-id alias that
collides with an existing canonical id / alias / archive token; a rendered
destination that fails `_validate_prospective_write`. Apply additionally rolls
the whole batch back on: a `claim_number_in_dir` failure (number consumed since
planning), a `ReferenceDriftError` from `apply_reference_rewrite` (corpus changed
since planning), a `preimage_sha256` mismatch, or any non-empty
`audit_moved_references` result. `discusses` / dead / cross-kind references are
**reported**, never silently resolved.

## Testing (real legacy shapes, synthetic project)

A fixture project built from the **real legacy shapes** (not an already-conforming
doc):

- **Projection**: a `type: spec` + `date:` + `status: approved` +
  `related_questions:` doc — assert `type→kind`, `date→created`/`updated`,
  `related_questions→related`, old id → `aliases`; assert `status: approved`
  **refuses** planning; assert an unrecognized key refuses; assert a mappable
  status (`design→draft`, `implemented→complete`) projects; assert `--status`
  override applies.
- **Batch numbering**: **≥2** legacy docs get **distinct sequential** ids
  (`spec:0001-…`, `spec:0002-…`); a collision-drift test where a `0001` entity
  appears (live or archive) between plan and apply → `claim` fails → whole batch
  restored.
- **Reference classification**: `related: [spec:<old>]` → rewritten to numeric;
  a `discusses: [spec:<old>]` → **manual-retarget** (documented both failure
  modes, no "migration fixes it" assertion); a `same_as: [spec:<old>]` →
  **alias-covered** (not rewritten, reported); a prose old-id mention →
  alias-covered/reported; a `dead` and a `cross-kind` ref → manual-retarget;
  an already-`spec:NNNN` ref → unchanged.
- **Identity**: missing `id:` refuses; duplicate old ids refuse; an old-id alias
  colliding with a live entity refuses at plan time.
- **Singleton**: a `kind: spec` file at `entities/research-question.md` is
  **reported, not relocated**.
- **Transaction/resume**: apply relocates all docs, rewrites the covered refs,
  audits, and leaves a loadable tree (the migrated entities build with their
  aliases and no `AliasCollisionError`); `--resume` finishes an interrupted
  journal without re-planning.
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
  Until it exists, those surfaces are alias-covered or manual-retarget, not
  auto-rewritten.
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
