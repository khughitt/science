---
title: Turn on spec reference resolution and ship the id-remap migration (S3b)
status: design
created: '2026-07-18'
---

# Turn On `spec:` Reference Resolution + Id-Remap Migration (S3b)

**Program:** curation S1–S5. This is **S3b**, the deferred second half of S3.
S1 (scope certification), S2 (adaptive rotation), S3a (`spec` as a first-class
creatable/importable entity kind), and S4 (correspondence-drift screen) are all
shipped and merged to local main.

**Goal.** Make ordinary `spec:` reference fields resolve into real graph edges
(remove `spec` from the annotation-only allowlist), and ship a
`science entity migrate-specs` command that canonicalizes a project's legacy /
loose `spec`-typed docs into numeric `entities/specs/NNNN-slug.md` entities and
repoints the references that named them.

**Scope of this effort: toolkit-only.** The switch, the migration command, its
tests (synthetic fixtures), and the docs are built in this repo. The actual
migrations of natural-systems, cbioportal, and multiple-myeloma are **separate
per-repo follow-on efforts** and are out of scope here (see Out of scope).

## Context — what S3a left in place

S3a made `spec` a first-class kind (`home="entities/specs"`,
`strategy="numeric"`, `default_status="active"`, plan-vocabulary statuses) and
wired the `spec → spec` `sci:supersedes` endpoint, but it **deliberately kept
`spec` annotation-only for ordinary reference fields**:
`graph/sources.py:809` still reads

```python
_ANNOTATION_REF_PREFIXES = frozenset({"meta", "spec"})
```

so `is_metadata_reference("spec:…")` is `True` and every ordinary `spec:` pointer
field is skipped before resolution. S3a shipped a materialization guard
(`science/tests/test_spec_materialization.py`) asserting exactly that: an ordinary
`spec:` metadata reference produces **no edge**. S3b turns that resolution on and
inverts the guard.

### Why S3a deferred this

Making `spec:*` resolve is a **global code constant**, not a per-project switch,
and imported specs get **numeric** ids (`spec:0001-slug`) that do not match the
existing **date-slug** (`spec:2026-04-22-morphism-generator-families-design`) and
**semantic** (`spec:scope-boundaries`) references already in the corpus. Flipping
the switch without first reconciling those ids would strand every existing
reference. S3b ships both halves together — the switch and the migration that
reconciles the ids — but runs the migration only on synthetic fixtures here.

## What flipping the switch actually does

Removing `"spec"` from `_ANNOTATION_REF_PREFIXES` stops
`is_metadata_reference` from short-circuiting `spec:` refs in `_add_relations`
(`graph/materialize.py`, guard consulted at lines 804, 816, 832, 863, 894, 903,
918, 942, 991, 1124, 1331). Post-flip each `spec:` pointer is handed to
`resolver.resolve(...)`:

- **Most fields** (`related`, `source_refs`, `blocked_by`, `same_as`,
  participants, …): resolves → a real graph edge materializes; does not resolve →
  silently dropped (`continue`).
- **`discusses` / membership fields** (`materialize.py:834-841`): an unresolved
  target **raises `ValueError`** ("a discusses frame must resolve to a bundle").
  This is the one **hard-fail** path — a `spec:` in a `discusses` field that does
  not resolve breaks graph build, not merely warns.

Resolution keys off the **canonical id in the alias map, not the file path**
(`graph/reference_resolution.py`; `sources.build_alias_map`,
`sources.py:715-774`). So `spec:0001-foo` resolves iff some loaded entity
declares `id: spec:0001-foo` (or lists it as an alias). A `type: spec` doc
sitting at a loose path (`doc/plans/…`) is **not loaded as an entity** and so
does not enter the alias map; its inbound refs dangle until it is imported into
`entities/specs/`.

### Visible signal for dangling refs

No graph-layer "dangling ref" gate exists — resolution failures are silent
`continue`s (except `discusses`). The visible signal is a **WARN** from
`check_cross_references` (`validate/checks/cross_references.py:377-381`,
`f"Broken reference in {path.name}: related ID '{ref}' not found"`) for any
`related: [spec:…]` not backed by a declared `id:`. `spec` is not in that
check's `LOCAL_KINDS` set, so a two-part `spec:<slug>` ref hits the `"local"`
fallthrough and is set-membership-checked against declared ids. `check_refs`
(the prose token scanner, `refs.py`) does **not** scan `spec:` tokens, so no new
prose-level findings appear. Net blast radius of the flip alone: WARNs, plus the
`discusses` hard-fail.

## Component A — flip the switch + invert the materialization guard

**`science/src/science_tool/graph/sources.py`.** Change line 809 to

```python
_ANNOTATION_REF_PREFIXES = frozenset({"meta"})
```

and refresh the surrounding comment block (lines 802-821), which currently says
`spec` "stays here in S3a … until S3b turns `spec:*` reference resolution on" —
that is now done, so the comment should describe `meta:` as the sole remaining
annotation-only namespace and note that `spec:` refs now resolve like any other
entity reference.

**`science/tests/test_spec_materialization.py`.** S3a's third guard asserts an
ordinary `spec:` metadata reference produces no edge
(`list(knowledge.triples((question_uri, None, spec_uri))) == []`). Invert it:
with `spec` no longer annotation-only, an ordinary `spec:` reference to an
**existing** spec entity now materializes an edge — assert the edge is present.
Keep the node-materializes and `spec → spec`-supersedes-edge assertions (both
unchanged from S3a). Add a companion assertion that an ordinary `spec:` reference
to a **non-existent** id materializes no edge (silent drop) and — separately —
that a `spec:` in a `discusses` field pointing at a non-existent id raises the
documented `ValueError`, pinning the hard-fail contract the migration exists to
avert.

**Audit — the flip's exact test surface.** No `spec:` token appears in any
`discusses`/membership field in the repo's test fixtures (verified), so the flip
triggers no hard-fail in the suite. Three existing tests reference the old
annotation-only behavior and must move with the switch:

- `test_meta_reference.py:26-28` **breaks** — it asserts
  `is_metadata_reference("spec:…")` is `True`. Flip those two `spec:` assertions
  to `False` (a `spec:` id is now an ordinary entity reference), keeping the
  `meta:` assertions `True`.
- `test_spec_materialization.py` — the edge-absence guard inverts to edge-presence
  (see below); this is the intended behavior change, not incidental breakage.
- `test_membership_materialize.py:111-117`
  (`test_metadata_ref_in_discusses_is_skipped_not_membership`) — its assertion
  uses a `meta:see-also` frame and so is **unaffected**; only its line-112 comment
  ("meta:/spec: are the global annotation escape hatch") goes stale and needs a
  refresh to name `meta:` alone.

The `real_projects`-marked tests
(`test_correspondence_drift_real_projects.py`, the two `validate/` parity tests)
do not materialize the KG — verified: their only `knowledge` mentions are
`knowledge_profiles:` config strings — so the flip does not disturb them.

## Component B — `science entity migrate-specs`

A new module `science/src/science_tool/migrate_specs.py` and a sibling CLI
command `science entity migrate-specs`, mirroring the shipped
`migrate-hypothesis` precedent (`entities_cli.py:327`,
`migrate_hypothesis.py`): **plan-only by default, `--apply` to write**, a
journal for interrupted-write `--resume`, a full snapshot with restore-on-failure,
and all-or-none semantics.

### What it discovers

1. **Legacy spec docs** — every file whose frontmatter declares `type: spec` or
   `kind: spec` that is **not already** a conforming `entities/specs/NNNN-slug.md`
   entity. This covers loose `doc/plans/*-design.md` / `doc/specs/*.md` docs and
   the mis-kinded singleton `entities/research-question.md` (`kind: spec`).
2. **Inbound `spec:` references** — every `spec:` reference token across
   structured surfaces: the frontmatter reference fields (`related`,
   `source_refs`, …), the `relations` block, `discusses`/membership, and the
   `spec:` frontmatter **key** used on pre-registration entities (whose *value*
   is sometimes a `spec:` id). Prose/code-fence mentions are found separately.

### What it plans

For each discovered legacy spec, propose a numeric id `spec:NNNN-slug` via
`propose_number` (the same id minting the importer uses), and build the
old-id → new-id substitution map. Classify each inbound reference into one of
four buckets:

- **structured-remappable** — the ref names a legacy spec being migrated; it is
  rewritten to the new numeric id by the drift-checked `reference_rewrite`
  engine (`reference_rewrite.plan_reference_rewrite` /
  `apply_reference_rewrite`, driven by `id_substitutions`).
- **dead** — the ref names a `spec:` id with no findable target (e.g. NS's
  `spec:2026-04-27-t349-covering-probe-design`, a placeholder like
  `spec:2026-01-01-x`). **Reported, not rewritten.**
- **cross-kind** — the ref names a `spec:` id whose real home is an entity of a
  different kind (e.g. mm's `spec:2026-04-11-bayesian-causal-dag-design`, whose
  natural target is `design:0025-bayesian-causal-dag-design`). **Reported, not
  rewritten** — retargeting to another kind is project judgment.
- **prose-manual** — a plain-prose or code-fence mention of the old identity.
  **Reported as a manual hit** (the `reference_rewrite` engine never
  auto-rewrites prose), consistent with `entities import`.

### What it applies

Under `--apply`: relocate each legacy spec into `entities/specs/NNNN-slug.md`
(reusing the `apply_import` transactional move — full snapshot, source-hash
verification, post-move audit, roll back on any failure), then repoint the
structured-remappable refs in one drift-checked `reference_rewrite` pass, and
print the **dead / cross-kind / prose-manual** report so the operator can address
those by hand. The command **never** auto-decides a dead, cross-kind, or
singleton-reconciliation case — those are the project judgments that make each
external migration its own effort.

### Reuse, not reinvention

The command composes existing, tested primitives:
`entity_import.apply_import` (per-doc move + rollback),
`reference_rewrite` (batch `id_substitutions`, drift-checked replay,
`preimage_sha256` per edit), and `migrate_hypothesis`'s journal / snapshot /
all-or-none control shape. No new transaction or rewrite engine is written.

## Component C — tests (synthetic fixtures only)

A synthetic fixture project exercises the full path without touching any real
repo. It carries:

- a loose `type: spec` doc (a migration target),
- an entity with `related: [spec:<date-slug>]` naming that doc
  (structured-remappable),
- an entity with a prose mention of the old path (prose-manual),
- an entity with `related: [spec:<dead-id>]` (dead), and
- an entity with `discusses: [spec:<id-of-the-migrated-doc>]` (proves the
  migration makes the discusses ref resolve rather than hard-fail).

Assertions: the **plan** mints `spec:0001-slug`, produces the old→new remap, and
sorts refs into the four buckets; **apply** relocates the doc to
`entities/specs/0001-slug.md`, rewrites the structured ref to the numeric id,
surfaces the dead + prose-manual buckets, and leaves the tree such that
**the KG builds** — the `related` edge and the `discusses` frame both materialize
and **no `ValueError`** is raised. Plus the inverted materialization guard from
Component A. Follow the `migrate-hypothesis` test layout
(`test_migrate_hypothesis*.py`) for plan/apply/resume coverage.

## Component D — docs + adoption contract

- A user-guide entry (`docs/user-guide/entities.md`, near the Source Entity CLI
  material) for `science entity migrate-specs` — what it discovers, the four
  report buckets, plan-then-`--apply`, and that `spec:` references now resolve
  into graph edges.
- Refreshed `sources.py` comments (Component A).
- **Adoption sequencing contract, stated explicitly** (user guide + this doc):
  flipping the global switch is safe for pinned consumers because they upgrade
  the toolkit deliberately (uv.lock pins the exact revision). But when a project
  bumps its toolkit pin past this change, it **must run `migrate-specs` first** —
  otherwise a pre-existing `spec:` in a `discusses` field will hard-fail its graph
  build, and every unmigrated `spec:` reference becomes a `check_cross_references`
  WARN. Migrate-then-bump (or bump-then-immediately-migrate) is the contract.

## Data flow (migrate-specs, apply)

discover legacy `spec`-typed docs + all inbound `spec:` refs → plan: mint numeric
ids, build old→new remap, classify refs into
{structured-remappable, dead, cross-kind, prose-manual} → snapshot → for each
legacy spec: `apply_import` move into `entities/specs/NNNN-slug.md` → one
`reference_rewrite` pass repoints the structured-remappable refs → post-move
audit → print the dead/cross-kind/prose-manual report → roll back the whole
transaction on any failure.

## Error handling

All rollback and drift machinery is existing. `apply_import` verifies the source
hash and rolls back on any post-move audit failure; `apply_reference_rewrite`
re-scans and raises `ReferenceDriftError` if the corpus changed since planning,
and re-checks each `preimage_sha256` before writing. The command refuses to
`--apply` if any legacy spec's proposed numeric id collides with an existing
entity id (fail early). Dead / cross-kind / prose-manual cases are **reported**,
never silently resolved.

## Testing summary

- **Switch** (`test_spec_materialization.py` + `test_meta_reference.py`):
  edge-absence guard inverted to edge-presence; non-existent-id ordinary ref → no
  edge; non-existent-id `discusses` ref → `ValueError`; `is_metadata_reference`
  now `False` for `spec:`, still `True` for `meta:`.
- **Migration** (`test_migrate_specs*.py`, synthetic fixtures): plan mints numeric
  ids + remap + four-bucket classification; apply relocates + repoints structured
  refs + reports the other buckets + leaves a KG-buildable tree; resume replays an
  interrupted journal; id-collision refusal.
- **Guard**: full suite green; refresh any kind-enumerating snapshot the switch
  shifts; `real_projects` tests unaffected (they do not materialize the KG).

## Out of scope / follow-ons

- **Running the migration on the three surveyed projects**, each its own per-repo
  effort on a volatile Dropbox branch:
  - **natural-systems** — 34 date-slug `doc/plans` spec docs + 3 semantic
    `doc/specs` specs + the mis-kinded `entities/research-question.md` singleton;
    ~151 references to repoint; 2 dead refs; 4 pre-registration `spec:`
    frontmatter-key values (one already dangling).
  - **cbioportal** — the trivial case: one singleton `spec:research-question`
    (13 refs), already resolvable; reconcile the singleton and repoint.
  - **multiple-myeloma** — no surviving spec-typed targets; both date-slug refs
    dangle; the 43-entity `entities/design/*` (`kind: design`) family is the
    re-import pool (`design:0025-bayesian-causal-dag-design` is the natural
    cross-kind target for one ref, `discussion:0044` for the other).
- **mm `design` → `spec` re-import** — a project migration, not a toolkit change.
- **Singleton reconciliation policy** — whether a `kind: spec` file at
  `entities/research-question.md` should become a numeric spec or be re-kinded to
  a research-question is per-project judgment; the command reports it.
- No spec template / `template_ready` (parity with `plan`, unchanged from S3a).

## Risks

The switch flip is a global constant, but consumers pin the toolkit by revision,
so it reaches a project only when that project deliberately bumps its pin — at
which point the adoption contract (migrate first) applies. The one sharp edge is
the `discusses` hard-fail; Component A pins it with a test and Component D
documents it as the reason migration must precede a pin bump. The migration
command composes only existing, rollback-safe primitives and writes nothing
without `--apply`. The heavy real-world blast radius (NS's 151 references) is
entirely behind the out-of-scope per-repo follow-ons.
