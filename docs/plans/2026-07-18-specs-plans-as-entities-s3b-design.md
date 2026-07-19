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
   classified in Component 3. A migrating spec's **own identity declarations**
   (`id:` and its `aliases:` entries, which contain `spec:` tokens) are **not**
   counted as inbound references to itself.

Two distinct passes with different completeness requirements:

- **Entity discovery** (identifying legacy spec docs, feeding `legacy_spec_count`)
  must be **complete**. It cannot use `iter_scannable_files` (`text_scan.py:66`)
  alone: that scanner silently `continue`s on any file over `MAX_SCANNABLE_BYTES`
  (`text_scan.py:25-26`) without emitting a `Skip`, so an oversized Markdown spec
  would vanish from the count while `scan_complete` stayed true. Discovery uses a
  complete Markdown walk; a candidate that is size-excluded or unreadable is
  emitted as a **`scan_skip`** (`{path, reason}`), which forces
  `scan_complete = false` and therefore `flip_ready = false`.
- **Inbound-reference scanning** reuses the canonical `iter_scannable_files` (the
  same scanner `reference_rewrite` and `audit_moved_references` use), so the
  rewrite and the audit see an identical file set.

The whole-tree reach (not just `entities/`) is required because
`entity_conformance` skips singleton homes and only scans existing
`entities/<kind>/` dirs while the loose docs live under `doc/plans/` and
`doc/specs/`.

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

**Field authority.** `Entity` is `ConfigDict(extra="allow")` (a deliberate
D3.3 decision, `model/src/science_model/entities.py:323`: schema-valid extension
fields are *preserved*, never dropped), so `Entity.model_fields` is **not** the
authority — it omits authored relationship keys like `supersedes` and includes
load-derived fields like `project`, `file_path`, `content`. The projection uses
an explicit two-set authority instead:

- **RUNTIME_ONLY** — the load-derived fields, enumerated **exactly** (not "and
  the others"): **`project`, `file_path`, `content`, `content_preview`,
  `canonical_id`**. The first four are values `_enrich_raw` derives at load
  (`sources.py:852-869`); `canonical_id` is derived from `id` immediately after
  (`sources.py:879-881`, `canonical_id = raw.get("canonical_id") or raw.get("id")`)
  — because an authored `canonical_id` there *overrides* the id-derived value, a
  legacy doc that carried one would load with an identity disagreeing with the
  freshly minted numeric `id`, so it must refuse. Every *other* `setdefault` in
  `_enrich_raw` (`related`, `aliases`, `same_as`, `scope`, `source_refs`,
  `relations`, `evidence_refs`, `xrefs`, `provisional`, `deprecated_ids`,
  `ontology_terms`) is an **authored** field with an empty default, not
  runtime-only. `profile` is also defaulted there (`sources.py:884-892`) but
  **only when absent**, so an authored `profile` is legitimately preserved; it is
  deliberately left **authorable** (not in RUNTIME_ONLY), consistent with the
  kind-descriptor contract. A legacy doc carrying any of the five RUNTIME_ONLY
  keys in authored frontmatter **refuses** planning.
- **LEGACY_ALIAS** — the named legacy spellings the projection rewrites (`type`,
  `date`, `related_questions`, `related_specs`).

Every other key is **authored frontmatter and is preserved** as-is (consistent
with `extra="allow"`); authored relationship keys such as `supersedes` /
`superseded_by` therefore survive projection untouched. The projection does not
maintain a closed allowlist of "known" keys — only the RUNTIME_ONLY refusal set
and the LEGACY_ALIAS rewrite set are enumerated.

| Legacy | Canonical | Rule |
|---|---|---|
| `id: spec:<old>` | `id: spec:NNNN-slug` | Old id is authoritative for identity + the alias; the new numeric id is minted (Component 4). Old id appended to `aliases:`. |
| `type: spec` | `kind: spec` | `type` is the legacy spelling; project to `kind`. If both present and disagree → refuse. |
| `date: <d>` | `created`, `updated` | **Independent**: `created = existing created or date`; `updated = existing updated or date`. **Refuse** if either is still absent afterward (e.g. a doc with `created` but no `updated` and no `date`). `date` is dropped once consumed. |
| `title` | `title` | Preserved. |
| `related_questions`, `related_specs` | `related` | Folded into canonical `related` so they actually participate in the graph; under `extra="allow"` they would otherwise persist as inert extension fields no consumer reads. **Existing `related` is preserved and the union is order-preservingly deduplicated** (first occurrence wins). |
| existing `aliases` | `aliases` | Preserved; the old id is appended and the list order-preservingly deduplicated (identity contract below). |
| `supersedes`, `superseded_by` (and the other 9 rewriter-handled keys) | (identity) | Preserved; their `spec:` values **do** get intra-batch id substitution (they are in `_REMOVABLE_FRONTMATTER_REF_KEYS`). |
| any other authored / extension key | (identity) | Preserved verbatim (`extra="allow"`); **not** substituted (the rewriter cannot see it) — a migrating-spec value here stays alias/identity-covered. |
| RUNTIME_ONLY key (`project`, `file_path`, `content`, `content_preview`, `canonical_id`) | — | **Refuse** planning, naming the key and file — load-derived, not authorable. |

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
- **Collision preflight** runs over the **complete projected batch** at plan
  time, not just appended old ids. It refuses if any of these collide with an
  existing canonical id / alias / archive token, or with each other: every **new
  canonical id** (`spec:NNNN-slug`), every **preserved alias** carried over from a
  legacy doc's existing `aliases:`, and every **appended old id**. Any such
  clash would raise `AliasCollisionError` at a later graph build
  (`sources.py:752-754`); the preflight surfaces it now instead.

## Component 3 — reference classification (two orthogonal axes)

A reference has two independent properties — the surface it lives on and the
target it points at; the earlier single-bucket scheme conflated them (a prose
mention of an unresolved id carries *both* a surface property and a target
property at once). Classify on two axes:

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

**Target — classified by exact evidence, never by similarity:**

| Target class | Evidence (exact, deterministic) |
|---|---|
| migrated-spec | the token **exactly equals** a discovered legacy spec's declared old id (has an `id_substitution`) |
| already-canonical | the token **exactly equals** a live numeric spec id or one of its aliases |
| unresolved | everything else — no matching id |

No title/slug-similarity inference is used: an unmatched token is `unresolved`,
never attached to a look-alike entity. There is **no operator retarget mapping in
v1** — a token whose real home is another kind (mm's
`spec:2026-04-11-bayesian-causal-dag-design`, whose natural target is
`design:0025-…`) is simply `unresolved`, and the operator retargets it by hand.
A mapping file is deferred (Out of scope) rather than shipped with an unspecified
schema.

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
  informational only. (Wording matters: *preserved*, not *resolved*.) Does not
  block flip-readiness.
- **unchanged** — target already-canonical (a ref to a live `spec:NNNN-slug`).
  No action, informational count; does not block flip-readiness.
- **manual-retarget** — `discusses`/membership refs (invalid post-flip
  regardless — the alias cannot save them, per the `discusses` correction above)
  and `unresolved` targets. A
  human must retarget or remove them; these **block flip-readiness**
  (Flip-readiness contract).

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
`claim_number_in_dir` itself gets one **behavior-preserving hardening**
(`entity_reservation.py`): after its `O_CREAT|O_EXCL` open proves ownership, a
failed write unlinks the primitive's own partial file before re-raising, so a
mid-`claim` crash leaves nothing behind for any caller (see "Move all"). This is
the only edit to an existing primitive; the rest are consumed unchanged.

### Deterministic canonical id (number + slug)

The new id is `spec:NNNN-<slug>`, both parts pinned deterministically:

- **Number.** `propose_number` (`entity_reservation.py:167-181`) is read-only and
  idempotent — called once it returns `highest+1` over committed + archived
  numbers. But `propose_number` **cannot see preserved-relocation numbers** (an
  already-numeric out-of-home spec keeping its `spec:0007-…` id is not yet in the
  canonical home), so the minted sequence must treat those as **spent**. The
  allocator's forbidden set is `committed ∪ archived ∪ preserved-relocation
  numbers`; the discovered mint-docs are sorted by old id and assigned the next
  free numbers ≥ the `propose_number` start, **skipping the forbidden set**. So a
  preserved `spec:0001-x` and a freshly-minted doc never both land on `0001`
  (tested with a mixed batch). The real per-doc collision gate remains
  `claim_number_in_dir` at apply, whose `O_CREAT|O_EXCL` sentinel re-checks
  committed + archived — a number consumed by concurrent work between plan and
  apply fails the claim and rolls the batch back (tested via live/archive
  collision drift).
- **Slug.** `slug = derive_slug(title)` — the same derivation the reservation path
  uses (`entity_reservation.py:122`, `slug = … derive_slug(title)`). Not the
  old-id-minus-date and not the filename stem, so a doc whose id/filename drifted
  from its title still gets a title-faithful slug. `title` is required (its
  absence is a projection refusal).
- **Already-numeric specs outside the canonical home** — a `type/kind: spec` doc
  whose declared id is *already* `spec:NNNN-slug` but which lives outside
  `entities/specs/` is a **pure relocation**: preserve the id (no renumber, no
  alias), move the file to `entities/specs/NNNN-slug.md`. If that number is
  already taken at the canonical home (committed or archived), **refuse** — the
  operator resolves the number clash. These do not consume a minted number.

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
  (`reference_rewrite.py:252`) for links to **non-migrating** targets — its own
  relative Markdown links move with it from `doc/plans/…` to `entities/specs/…`;
- **intra-batch `path_substitutions`** for Markdown links (incl. anchored
  `b.md#sec`) to **other migrating specs**: `rewrite_outbound_links` only rebases
  a link whose absolute target is unchanged, but a sibling B has *also* moved, so
  a raw rebase would point at B's vacated `doc/plans/b.md`. The migrating body
  therefore receives the merged `path_substitutions` (every sibling old→new path)
  so an A→B link resolves to B's new `entities/specs/…` location;
- **intra-batch id substitution** in its projected frontmatter — a migrating spec
  that references *another* migrating spec (`related`, `supersedes`, …) must have
  that ref rewritten to the neighbor's new numeric id (the merged
  `id_substitutions`), since the corpus replay skips it.

The single corpus-wide `apply_reference_rewrite` then rewrites only the
**non-migrating referrers**.

### The batch transaction

1. **Preflight all** — project-root check; project each legacy doc (Component 2,
   refusing on unmappable status / RUNTIME_ONLY key / missing id or title /
   unresolved date);
   render every destination, apply intra-batch id substitution, and validate it
   through `_validate_prospective_write`; assign sequential numbers; build the
   merged `id_substitutions` / `path_substitutions`, the single merged
   `RewriteReport` (scanned with the `{sources ∪ destinations}` exclusion), and
   the per-path journal plan; pre-check alias collisions. **Nothing is written;
   any refusal aborts the whole batch.**
2. **Snapshot all** — one `_snapshot` over the union of every source, every
   destination, and every non-migrating referrer named in the merged report.
3. **Move all** — per doc: verify source SHA; call `claim_number_in_dir` to
   claim + write the projected+rebased+substituted entity; **add the destination
   to `mutated` only after the claim returns successfully**; then unlink the
   source and add it to `mutated`. The coordinator must **not** pre-register the
   destination before the claim: between our snapshot (dest recorded **absent**)
   and our claim, a concurrent writer could create that exact path, and a
   pre-registered `mutated` entry would then make `_restore` delete the
   bystander's file. Instead, `claim_number_in_dir` is **hardened** to clean up
   after itself: `open(path,"x")` (O_CREAT|O_EXCL) succeeding *proves* the
   coordinator owns that path (no bystander held it), so if the subsequent
   `handle.write(text)` fails the primitive unlinks its own partial file before
   re-raising (`entity_reservation.py:201-203`, wrap the write body in
   `try/except` that unlinks on failure). Ownership-proven cleanup and
   claim-then-register together give both rollback completeness and
   concurrent-writer safety: the coordinator only ever records — and only ever
   restores — paths a successful claim confirmed it owns.
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
fails its fresh-report comparison on a naive replay. Hashes alone let resume
*detect* a state but not *reconstruct* the target, so the journal stores, for
every path the transaction will touch, its **role** and both its **preimage** and
**postimage** as `content | absent`. Per role:

| Role | preimage | postimage | replay op |
|---|---|---|---|
| moved-source | content | **absent** | `unlink` |
| moved-dest | **absent** | content | `claim_number_in_dir` (writes the content) |
| referrer | content | content | atomic replace (temp + rename) with stored bytes |

The journal is written **atomically** (temp file + rename) **before the first
mutation**.

`--resume` never re-plans and never re-runs `apply_reference_rewrite`:

1. **Classify every journaled path first**, before writing anything: hash the
   current on-disk file and match it to the recorded preimage or postimage
   (each `content | absent`).
2. **Any path matching neither** → external drift since planning; **refuse the
   whole resume** (do not guess).
3. Otherwise **perform each not-yet-done path by its role's replay op** — a
   moved-dest via `claim_number_in_dir`, a referrer via atomic replacement of the
   stored postimage bytes, a moved-source via `unlink`. Not one generic write.
4. **Run `audit_moved_references` for every destination** before finishing —
   post-move audit is the semantic check (a dangling ref the move introduced),
   which per-path hash equality does **not** capture.

**Crashed reservation sentinels.** `claim_number_in_dir` refuses on *any*
existing `.NNNN.reserving` sentinel (`entity_reservation.py:187-190`), and its
`finally: unlink` runs only if the process survives. **Two** crash points leave a
sentinel: (a) after sentinel-create but before the destination is written (dest
absent + sentinel), and (b) after the destination is written but before `finally`
(dest committed + sentinel). Resume clears the leftover sentinel for any number in
*its own* journal in **both** cases before acting (case (b)'s dest is already at
its postimage, so only the sentinel needs clearing). This rests on an explicit
**single-writer** assumption that excludes **every** concurrent number consumer —
not just another `migrate-specs` run but any `entity create` / `entities import`
touching `entities/specs/`; a sentinel for a non-journaled number is unsupported
and refuses. Token-owned reservations are the robust upgrade, deferred.

After completing every remaining action and the destination audits, resume
deletes the journal. A successful **caught-failure restore also deletes the
journal** (step 6); a later `--resume` then finds no journal and **refuses —
"no interrupted transaction"** — rather than acting. Plan-only (no `--apply`)
writes nothing and no journal.

## Component 5 — docs and the sequencing contract

- **User guide** (`docs/user-guide/entities.md`, near the Source Entity CLI
  material): document `science entity migrate-specs` — plan-then-`--apply`, the
  projection rules, the five report groups (rewritten / alias-resolved /
  identity-preserved / unchanged / manual-retarget), the singleton report, the
  `flip_ready` field, and the refusal cases. State plainly that **`spec:` references still
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

The command emits a machine-checkable `flip_ready` boolean, the actual gate the
later resolution-flip step keys on, so "flip-ready" is never a prose judgment.

`flip_ready = true` **iff all three** hold:

- `legacy_spec_count == 0` — no un-relocated legacy spec remains. This is what
  makes a **plan-only dry run** correctly report `false` (it discovers legacy
  specs but has not applied), rather than falsely `true`.
- `singleton_count == 0` — no `kind:/type: spec` file at a singleton home awaits
  reconciliation (Component 1).
- `manual_retarget_count == 0` — no reference in the **manual-retarget** group
  (`discusses`/membership, `unresolved`).

`alias-resolved`, `identity-preserved`, and `unchanged` findings **may remain**
with `flip_ready = true`. **Any incomplete scan** (an unreadable file, a skipped
path) forces `flip_ready = false` and is reported — readiness is never asserted
over an unscanned corpus.

**Freshness.** A stored report cannot prove the *current* tree is still ready. So
the later flip step **recomputes** `flip_ready` by re-running the classifier
against the tree at flip time (equivalently, it consumes a report bound to a
corpus fingerprint it re-verifies); a stale report is advisory only. The flip
refuses on a non-`flip_ready` recomputation.

**Output schema** (JSON, `--format json`; the pinned, tested contract):

```
{
  "flip_ready": bool,
  "legacy_spec_count": int,
  "singleton_count": int,
  "manual_retarget_count": int,
  "singletons": [ "<path>", … ],
  "migrated": [ { "old_id": str, "new_id": str, "dest": "<path>" }, … ],
  "references": {
    "rewritten": int, "alias_resolved": int,
    "identity_preserved": int, "unchanged": int, "manual_retarget": int
  },
  "manual_retarget": [ { "ref": str, "surface": str, "reason": str, "in": "<path>" }, … ],
  "scan_complete": bool,
  "scan_skips": [ { "path": str, "reason": str }, … ]
}
```

`manual_retarget_count` is the top-level scalar the readiness formula reads
(equal to `references.manual_retarget`); `scan_complete` is `false` iff
`scan_skips` is non-empty.

Tests assert this schema and every `flip_ready` transition.

## Error handling / refusal cases (consolidated)

Planning refuses (writes nothing) on: a legacy spec doc without a declared `id:`
or `title`; `type`/`kind` disagreement; an unmappable legacy status; a
`created`/`updated` still absent after date projection; a RUNTIME_ONLY frontmatter
key (`project`, `file_path`, `content`, `content_preview`, `canonical_id`); a duplicate old id in
the batch; any
batch id or preserved alias colliding with an existing canonical id / alias /
archive token or with another batch member (the Component 2 collision preflight);
an already-numeric out-of-home spec whose number is taken at the canonical home;
a rendered destination that fails `_validate_prospective_write`. Apply
additionally rolls the whole batch back on: a `claim_number_in_dir` failure
(number consumed since planning), a `ReferenceDriftError` from
`apply_reference_rewrite` (corpus changed since planning), a `preimage_sha256`
mismatch, or any non-empty `audit_moved_references` result. `--resume` refuses on
any journaled path in a third state (matching neither preimage nor postimage) and
refuses with "no interrupted transaction" when no journal exists. `manual-retarget`
references (`discusses`/membership, `unresolved`) are **reported**, never silently
resolved.

## Testing (real legacy shapes, synthetic project)

A fixture project built from the **real legacy shapes** (not an already-conforming
doc):

- **Projection**: a `type: spec` + `date:` + `status: approved` +
  `related_questions:` doc — assert `type→kind`, both `created` and `updated`
  seeded from `date`, `related_questions` folded into `related` with existing
  `related` preserved and deduplicated (order-preserving), old id appended to an
  existing `aliases` list and deduplicated, and an authored **`supersedes` key
  survives** untouched; assert `status: approved` **refuses**; assert a
  RUNTIME_ONLY key (`content`) refuses; assert an authored `canonical_id:`
  refuses (it would otherwise override the minted numeric id); assert a doc with `created` but no
  `updated` and no `date` **refuses**; assert mappable statuses (`design→draft`,
  `implemented→complete`) project.
- **Canonical id**: `slug == derive_slug(title)` even when the old id/filename
  differ from the title; **≥2** legacy docs get **distinct sequential** numbers
  (`spec:0001-…`, `spec:0002-…`); a collision-drift test where a `0001` entity
  appears (live or archive) between plan and apply → `claim` fails → whole batch
  restored; an **already-numeric out-of-home** `spec:0007-…` doc is relocated
  preserving its id (no renumber, no alias), and **refuses** if `0007` is taken at
  the canonical home; a **mixed batch** where a preserved relocation holds `0001`
  and a minted doc is present — the minted doc is assigned `0002`, never `0001`.
- **Reference classification & token boundary**: `related: [spec:<old>]` →
  rewritten to numeric; `discusses: [spec:<old>]` → **manual-retarget** (both
  failure modes documented, no "migration fixes it" assertion); `same_as:
  [spec:<old>]` → **alias-resolved** (not rewritten, reported); a prose old-id
  mention → **identity-preserved** (reported, not called "resolved"); an
  `unresolved` ref → manual-retarget; an already-`spec:NNNN` ref → **unchanged**;
  a migrating doc's own `id:`/`aliases:` are **not** counted as inbound refs; a
  **`science-spec:<old>` token is NOT matched** as a `spec:` reference, and a
  trailing-period `spec:<old>.` matches without the period.
- **Intra-batch links**: two migrating specs A and B where A's body has a
  Markdown link to `b.md#section` — after apply the link resolves to B's new
  `entities/specs/…` path (via `path_substitutions`), anchor preserved.
- **Flip-readiness & schema**: a plan-only dry run reports `flip_ready == false`
  with `legacy_spec_count > 0`; `flip_ready == false` while any singleton or
  manual-retarget remains; `flip_ready == true` only when
  `legacy_spec_count == singleton_count == manual_retarget_count == 0`, even with
  alias-resolved / identity-preserved / unchanged findings present; an
  **oversized (`> MAX_SCANNABLE_BYTES`) legacy-spec Markdown** file and an
  unreadable file each appear in `scan_skips` and force
  `scan_complete == false` + `flip_ready == false`; the JSON output matches the
  pinned schema.
- **Identity/collision preflight**: missing `id:` refuses; duplicate old ids
  refuse; a new canonical id, a preserved alias, or an appended old id colliding
  with a live entity/archive token refuses at plan time.
- **Singleton**: a `kind: spec` file at `entities/research-question.md` is
  **reported, not relocated** (and forces `flip_ready == false`).
- **Transaction/resume**: apply relocates all docs, rewrites the covered refs
  (including an intra-batch spec→spec ref rewritten to its neighbor's new id),
  audits, and leaves a loadable tree (migrated entities build with their aliases
  and no `AliasCollisionError`); an **injected write failure mid-`claim` leaves no
  partial destination behind** (proving `claim_number_in_dir`'s
  ownership-proven self-cleanup), and the batch is left fully rolled back; a
  per-path resume performs each remaining path **by its role's
  op** (moved-dest re-claimed, referrer atomic-replaced from its stored postimage,
  moved-source unlinked), then **runs `audit_moved_references` per destination**,
  without re-planning or re-running `apply_reference_rewrite`; a journaled path
  matching neither preimage nor postimage **refuses**; leftover journaled
  sentinels are cleared at **both** crash points (dest-absent and dest-committed);
  a caught-failure restore deletes the journal so a subsequent `--resume`
  **refuses with "no interrupted transaction."**
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
plus the honest (surface × target) report mean an un-rewritten **resolving**
reference keeps resolving via the old id → `aliases` mapping rather than dangling
once the flip finally lands. Two documented exceptions do **not** resolve and are
reported as manual-retarget, never silently fixed: `discusses`/membership refs
(which the alias net cannot save — a resolved `spec:` target is not a valid
bundle) and identity-preserved inert canonical-id mentions in prose (deliberately
left as text, not references).
