# v2→v3 migration robustness — design

**Status:** Design / approved decisions — ready for implementation plan.
**Created:** 2026-06-06
**Origin:** Multi-project readiness audit
(`docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md`) ran the v2→v3
`science entities migrate` dry-run across all 19 non-transient registered projects. Only 5
(small leaf) projects migrate cleanly; the other 14 are blocked almost entirely by **migrator
false-positives**, not project content — i.e. the migrator was overfit to MM30's conventions.
Two projects (natural-systems, protein-landscape) **hard-crash** on validation introduced by the
just-merged local-kind work. This design makes the migrator and conformance robust to the real
conventions other projects use.

## Goal

Make `science entities migrate` (v2→v3) and the entity-conformance check treat real-world
project conventions correctly, so every audited project except the one with genuine content debt
(seq-feats) can complete a clean migration with **zero project-side edits** beyond a tiny
mechanical set, and the two crashes are eliminated.

## Non-goals (out of scope)

- The actual per-project `--apply` runs (separate follow-up once tooling lands).
- Cross-project reference **resolution** (a federation resolver). We stop *blocking* on
  cross-project pointers; we do not resolve them.
- seq-feats content debt (competing id variants) and health-cycles near-match topic refs — these
  are genuine project-side decisions left to the owners.
- Rewriting how the graph layer validates link health; that remains the graph validator's job.

## Approved decisions (keystones)

1. **Blocking model — only structural refs block.** Unresolved references in **structural
   positions** block `--apply`; unresolved tokens in **prose body** (including code fences, inline
   code, `[[wikilinks]]`, cross-project mentions, short-forms, placeholders) become **non-fatal
   warnings**, reported but not blocking. Rationale: the layout migration moves files and rewrites
   *resolvable* ids; dead prose links are pre-existing content issues the graph validator already
   reports separately, and must not gate a mechanical move.

   **Structural positions = whatever the graph audit validates.** Rather than hand-enumerate
   audited fields (a brittle list that drifts), the pre-mutation blocking check **runs
   graph-audit-equivalent validation over a *simulated post-move* `ProjectSources`** (see Unit A):
   apply the planned moves + id rewrites in-memory, then call the existing
   `audit_project_sources` and block on any `fail` row. This mirrors the post-mutation backstop by
   construction — no ref can pass the guard and then fail the audit — and automatically covers the
   **entire** audited surface, which includes (non-exhaustively) entity `related`, `source_refs`,
   `evidence_refs`, `commits_to`, `blocked_by`, `dataset_usage`, paper `datasets`,
   `derivation.inputs`, `chain`, `audits`, `proposition_refs`, `same_as`; **task** `related`/
   `blocked_by` (tasks are graph entities — `graph/storage_adapters/task.py`); **relation** and
   **binding** endpoints; `.edges.yaml` `evidence:`/`anchor:`; and `mappings.yaml` alias targets
   (`graph/migrate.py:398,634`). The graph audit only inspects **structured** sources, never free
   prose body — so body tokens are inherently outside the blocking set and become warnings.
2. **Manifest loading — graceful skip.** A malformed/vestigial local entity kind is skipped with
   an accumulated warning instead of aborting the whole migration. Validation logic is unchanged;
   only the failure mode changes (raise → skip+warn).
3. **Undated fallback — explicit keys only, still blocks.** Extend the creation-date fallback to
   consult `generated_at:` and `committed:`, but a file with genuinely no date anywhere still
   blocks (preserves the "entities must be dated" forcing function). No git-date fallback.
4. **Entity discovery — exact-root path AND an entity signal; else skip+warn.** A file is a
   migratable entity only if (a) its parent path equals a registered entity root (`doc/papers`,
   `doc/questions`, `specs/hypotheses`, `entities/<kind>`, and each local kind's declared home),
   **and** (b) it carries an entity signal: frontmatter `id:`, or explicit `type:`/`kind:`. A file
   at a root lacking the signal is **skipped with a warning** (non-silent) — not discovered as an
   entity, not a blocker. Exact-root alone is insufficient: direct-child prose docs at a real root
   (pan-disease's `specs/hypotheses/cohort-adjudication-h01.md`, `h01-cohort.md`) have no `id:` and
   must not be treated as hypotheses. Empirically safe: every real entity sampled (MM30 466/466,
   pan-disease papers 56/56, real hypotheses 5/5) carries `id:`; only genuinely un-typed prose
   lacks it. (Note: a file with an explicit `id:`/`type:` of a known kind is still discovered via
   the existing id-prefix / type inference regardless of directory — the exact-root requirement
   governs only the directory-name fallback path.)

## Architecture

The migrator keeps its current shape (`discover_legacy_entities` → `plan_migration` →
`migrate_layout`, with `rewrite_references` doing the id rewrite). Changes are localized to four
seams, each an independently-testable unit:

- **Reference classification** (`migrate_layout`): blocking is decided by running
  graph-audit-equivalent validation over a *simulated post-move* `ProjectSources` (Unit A) — **not**
  by partitioning `rewrite_references` leftovers. `rewrite_references` still rewrites resolvable
  ids whole-text; its prose-body leftovers (the surface the audit never inspects) become warnings.
- **Local-kind loading** (`entities.py::load_local_entity_policies`): skip+warn vs raise.
- **Discovery** (`entity_layout_migration.py::_infer_kind` / `_project_dir_to_kind` /
  `_DIR_TO_KIND`): exact-root-path keying.
- **Date fallback** (`_fallback_created` / `synthesize_frontmatter`): extra explicit keys.

Plus two smaller seams: structural `mappings.yaml` parsing (Unit E) and date-dir-scoped alias
generation (Unit F).

## Units

### Unit A — Position-aware blocking (resolves G1–G6 blocking)

**What:** stop treating every non-conforming token anywhere in a file as a `--apply` blocker.

**How:**
- **Blocking = graph-audit-equivalent validation over a simulated post-move source set.** This is
  the primary mechanism, not an enumerated field list. Steps:
  1. Build a simulated post-move `ProjectSources`: load the project sources and apply the planned
     moves + id rewrites (`plan.id_map`) and generated aliases in-memory, so every structured
     source carries its post-migration identity. (No disk mutation — the same transform `--apply`
     will perform, computed in memory.)
  2. Run the existing `audit_project_sources` on that simulated set and **block on any `fail`
     row**. This inherits the audit's *entire* field surface (entity `related`/`source_refs`/
     `evidence_refs`/`commits_to`/`blocked_by`/`dataset_usage`/`datasets`/`derivation.inputs`/
     `chain`/`audits`/`proposition_refs`/`same_as`, task `related`/`blocked_by`, relation & binding
     endpoints, edges, mappings) **and** its acceptance exceptions (`is_bibliography_reference` for
     `source_refs`/`evidence_refs`, `is_external_reference` for URLs/paths/`go:`/`mesh:`/`doi:`,
     `is_metadata_reference` for `meta:*`) — with zero re-implementation and zero drift.
  - Why not intersect `rewrite_references` leftovers: it deliberately skips already-*conformant*
    tokens (`local_part_conforms`, `entity_layout_migration.py:576`), so a dangling-but-conformant
    ref like `hypothesis:9999-nope` never surfaces as a leftover. Today that case is caught only by
    the **post-mutation** audit (`tests/test_entity_layout_migration.py:417`); running the audit on
    the simulated post-move set moves the identical check **pre-mutation**, honoring the guard.
- `rewrite_references` keeps performing the whole-text old→new rewrite (unchanged). Its leftover
  tokens — which live in **prose body**, the surface the graph audit never inspects — feed the
  **warnings** bucket only (they are non-structural by definition).
- When building the warnings bucket, strip fenced code blocks (```` ``` ````) and inline code
  spans (`` ` ``) from the text first, so example ids in documentation don't generate noise.
- `migrate_layout` report: `unresolved_references` carries **blocking** structural refs only
  (preserving its existing "this blocks `--apply`" meaning); add
  `unresolved_warnings: dict[str, list[str]]` for the prose tail. The pre-mutation guard raises
  only on `unresolved_references`.

**Effect:** wikilinks (G1), code-fence/inline examples (G2/G3), placeholders (G4), cross-project
pointers (G5), and bare short-forms in prose (G6) no longer block — provided they are not also
sitting in a structural `related:`/`source_refs:` list. A genuinely dangling **structural** ref
still blocks, as it should.

### Unit B — Graceful local-kind loading (G7)

**What:** one malformed local kind must not abort the entire migration.

**How (API-stable):** keep `load_local_entity_policies(project_root) -> dict[str, EntityPathPolicy]`
exactly as-is in signature and caching, so its callers — notably `entity_policies`, which splats
`{**load_local_entity_policies(...), **builtins}` (`entities.py:158`) — are untouched. Change only
the failure mode: a kind that fails a validation predicate (`name != canonical_prefix`, home
collides with a core directory, bad strategy, bad home) is **skipped** instead of raising
`EntityCommandError`. Factor the validation pass into an internal
`_load_local_policies_and_warnings(project_root) -> tuple[dict, list[tuple[str, str]]]` (cached);
`load_local_entity_policies` returns its dict half, and a new public
`local_kind_warnings(project_root) -> list[tuple[str, str]]` returns the `(kind, reason)` half for
`migrate_layout`/conformance reports. The validation predicates themselves are unchanged.

The four existing "must raise" tests
(`tests/test_entities_local_policies.py`: name≠prefix, bad-home, core-dir collision, bad-strategy)
are rewritten to assert **skip + warning** instead of `pytest.raises`, reflecting decision 2.

**Companion project-side fixes (separate, outside the science-tool change):**
- natural-systems `knowledge/sources/project_specific/manifest.yaml`: `meta` kind
  `canonical_prefix: doc` → `meta`.
- protein-landscape `manifest.yaml`: remove vestigial `methods` and `paper-synthesis` kinds (0
  entities each; `methods` home collides with core `method`).

### Unit C — Entity-discovery tightening (G8)

**What:** stop sweeping frontmatter-less files under nested non-root dirs into the entity set.

**How:** the dir→kind fallback in `_infer_kind` currently keys on `Path(rel_path).parent.name`
(bare segment), so `doc/background/papers/X.md` matches `papers`→`paper`. Replace with an
exact-relative-**path** map and match `Path(rel_path).parent` against full paths.

The map must enumerate both **legacy source roots** and **destination roots** per kind, because
policy roots are the *new* `entities/<kind>` destinations — `resolve_path_policy(kind).root` yields
`entities/questions`, **not** the `doc/questions` the migrator scans (`_INPLACE_ROOTS` covers
`doc/`, `specs/`; `entity_layout_migration.py:34,62`). Keying only off policy roots would discover
**zero** legacy core entities. So build:
- an explicit **legacy-root → kind** map for the pre-v3 source locations: `doc/papers`→paper,
  `doc/questions`→question, `doc/topics`→topic, `doc/interpretations`→interpretation,
  `doc/reports`→report, `doc/methods`→method, `doc/plans`→plan,
  `doc/pre-registrations`→pre-registration, `specs/hypotheses`→hypothesis,
  `specs/propositions`→proposition, … (one entry per numeric/citekey core kind, derived from the
  pre-v3 layout, **separate** from destination policies);
- plus the **destination** `entities/<dir>`→kind paths (for re-running on a partly-migrated tree);
- plus each **local kind's declared home** path.

Match `Path(rel_path).parent` against the union of those full paths. `id`-prefix and explicit
`type:`/`kind:` inference (which run before the dir fallback) are unchanged — a file with an
explicit id/type is still discovered regardless of directory.

**Entity-signal gate (decision 4).** For files that reach the directory-name fallback (no explicit
`type:`/`kind:`, no known id-prefix), require an entity signal — frontmatter `id:` (or `type:`/
`kind:`) — in addition to the exact-root match. A file at a root **without** the signal is
**skipped with a warning** (added to a `skipped_untyped` report list), not discovered as an entity.
This is what excludes pan-disease's `specs/hypotheses/{cohort-adjudication-h01,h01-cohort}.md`
(no `id:`), which exact-root alone cannot (`h01-cohort` is id-shaped by filename). It is safe for
real entities, which universally carry `id:`.

**Effect:** 3d-attention-bias `doc/background/papers|topics` + `doc/discussions`, seq-feats
`doc/background/**` (excluded by exact-root), and pan-disease's non-entity `specs/hypotheses/*`
prose docs (excluded by the entity-signal gate) are no longer discovered as undated entities. Note
the cats `doc/plans/kg-project-migration-guide.md` (no frontmatter) is now `skipped_untyped` rather
than an undated blocker — the project adds frontmatter to include it.

### Unit D — Date-fallback extension (G9)

**What:** recognize author-supplied dates stored under non-`created:` keys.

**How:** `_fallback_created` chain becomes `frontmatter.created` → `frontmatter.generated_at` →
`frontmatter.committed` → (body `**Date:**` header, already handled in `synthesize_frontmatter`)
→ filename `YYYY-MM-DD` prefix → `_UNDATED_SENTINEL`. Sentinel still blocks (decision 3).

**Normalize to a date.** `generated_at:` is an ISO **timestamp**
(`2026-04-28T12:00:00Z`, per big-picture output), but entity `created:` is modeled as a **date**
(`science_model/entities.py`). Each non-`created:` source must have its leading `YYYY-MM-DD`
component extracted and validated as a real date before use; if a candidate value has no parseable
leading date, fall through to the next link rather than copying the raw string. (`created:` and the
filename prefix are already date-shaped.)

**Effect:** `/science:big-picture` synthesis files (`generated_at:`) across protein-landscape,
science-meta, pan-disease, health-cycles, cancer-therapeutics, cbioportal stop reading as undated;
3d-attention-bias pre-registrations (`committed:`) too.

### Unit E — Knowledge-source YAML handling (G10)

**What:** stop flagging `mappings.yaml` alias-source keys as unresolved references.

**How:** parse `mappings.yaml` structurally rather than scanning it as free text. The alias
*source* (LHS key) is a definition and is never a ref. The alias *target* (RHS value) is a
structural ref that must resolve (feeds Unit A's blocking set). Comments and graph-only
`entities.yaml` id definitions are not refs. Under the Unit A model, any remaining YAML-body
tokens are non-structural → warnings, so this unit mainly ensures alias *targets* are still
checked while alias *sources* are exempt.

### Unit F — Date-dir-scoped alias generation (G-novel collisions)

**What:** four pan-disease `doc/probes/2026-05-*/interpretation.md` files collide on the
back-compat alias `interpretation:interpretation` because the alias is built from the bare
filename stem.

**How:** when the filename stem alone is ambiguous (bare kind word, or shared across multiple
date-prefixed parent dirs), scope the generated alias with the date-prefixed parent directory
(e.g. `interpretation:2026-05-14-interpretation`) so each file gets a distinct alias. Removes the
4 false collisions.

### Unit G — Placeholder guard for warnings (minor; G4/G-novel polish)

**What:** keep the prose warnings signal-rich.

**How:** when emitting warnings, skip tokens that are obviously not real ids: wildcard/glob
(`*`, `…`), angle-bracket placeholders (`<id>`), bare `hNN`/`qNN`-style schema placeholders, and
numeric line-range notations (`report:198-210`). Purely cosmetic — these are already non-blocking
under Unit A.

## Error handling

- Blocking guards (`collisions`, structural `unresolved_references`, `undated_entities`) still
  raise pre-mutation with no tree modification, exactly as today. The structural
  `unresolved_references` set now resolves refs **directly against the final identity+alias set**
  (Unit A) and spans the same field surface (entity + task + edges + mappings) the post-mutation
  audit validates — so a ref can no longer pass the pre-mutation guard and then fail the audit.
- Local-kind warnings and prose-ref warnings are **reported, never raised**.
- Post-mutation graph audit is unchanged and remains the backstop: it still runs after `--apply`
  and blocks the `layout_version` bump on any structured-source failure.

## Testing

TDD per unit against a synthetic fixture project exercising every seam:
- local kinds incl. one **malformed** kind (Unit B: must skip+warn, tool still produces a report);
- a code-fenced example id and an inline-code id (Unit A: warn, not block);
- a `[[Wikilink]]` to an existing `paper:` (Unit A: warn, not block);
- a cross-project `hypothesis:h00-working-model` in prose (Unit A: warn) **and** a genuinely
  dangling ref in a frontmatter `related:` list (Unit A: still **blocks**);
- a **conformant-but-dangling** structural ref (`hypothesis:9999-nope` in a `related:` list):
  must block **pre-mutation** via the simulated post-move audit — the case `rewrite_references`
  leftovers can't see (regression guard for round-1 High finding);
- a dangling ref in a **non-`related` audited field** (e.g. proposition `commits_to:` or paper
  `datasets:`): must also block — proving the blocking surface tracks the *whole* graph audit, not
  an enumerated subset (regression guard for round-3 High finding);
- a **task** (in `tasks/active.md`) whose `related:`/`blocked_by:` points to a dangling id
  (Unit A: **blocks**) vs one pointing at a migrated id (rewritten, does not block);
- structural refs the graph audit accepts without resolution — `cite:Key2024` in `source_refs:`,
  an external `go:0008150` / `./data/x.parquet` path, and a `meta:*` ref — must **not** block
  (Unit A acceptance-semantics parity with `_audit_reference`);
- a frontmatter-less file under `doc/background/papers` (Unit C: excluded by exact-root) **and** a
  frontmatter-less prose doc directly under `specs/hypotheses` (Unit C: excluded by the
  entity-signal gate → `skipped_untyped`, not an entity, not a blocker), vs a sibling with `id:`
  (discovered normally);
- a synthesis file with only `generated_at:` (Unit D: not undated) and a truly date-less file
  (Unit D: still blocks);
- a `mappings.yaml` with an alias whose source key looks like a ref (Unit E: source exempt,
  dangling target blocks);
- two same-named files in distinct date-dirs (Unit F: distinct aliases, no collision).

**Integration check:** re-run the live 19-project dry-run from the audit. Expected: natural-systems
and protein-landscape no longer crash; every project except seq-feats reaches `ready` (0
collisions, 0 structural-unresolved, 0 undated) with **zero project-side edits**; warnings
(`unresolved_warnings`, local-kind warnings, `skipped_untyped`) are populated but non-blocking.
**Regression guard:** the 5 currently-clean leaf projects (cancer-ovarian/-head-and-neck/-prostate/
-breast, health-immunity) must still migrate every entity — none of their real entities may land in
`skipped_untyped` (confirms the entity-signal gate drops nothing real). seq-feats remains blocked on
its genuine content debt.

## Affected files (science/)

- `science/src/science_tool/entity_layout_migration.py` — Units A, C, D, F, G (legacy+destination
  root map, date fallback + normalization, structural-ref resolution against the final identity
  set, prose-warning classification with code-span stripping, alias generation, report keys).
- `science/src/science_tool/entities.py` — Unit B: `load_local_entity_policies` keeps its dict
  signature; add internal `_load_local_policies_and_warnings` + public `local_kind_warnings`.
- `science/src/science_tool/graph/migrate.py` + `graph/sources.py` (read-only reuse) — the
  pre-mutation blocking check builds a simulated post-move `ProjectSources` (`load_project_sources`
  + in-memory move/id-rewrite) and runs the existing `audit_project_sources`; no bespoke per-field
  structural extractor is written, so task/relation/binding/edge/mapping surfaces and acceptance
  exceptions are inherited, not re-implemented.
- `science/src/science_tool/validate/checks/entity_conformance.py` — surface local-kind warnings;
  align with the position-aware model where it inspects refs.
- A small new helper for the simulated-post-move transform + code-span stripping (for the prose
  warnings bucket) is expected, to keep `entity_layout_migration.py` focused.
- Tests under `science/tests/` (per-unit) + the multi-project integration check. The four
  "must raise" tests in `tests/test_entities_local_policies.py` are rewritten to assert skip+warn.

## Remediation order (matches plan task order)

1. Unit B (G7) — unblock the two crashes (smallest change, highest unblock).
2. Unit D (G9) — clears most "undated" counts.
3. Unit A (G1–G6) — the keystone reclassification; largest false-positive class.
4. Unit C (G8), Unit E (G10), Unit F (G-novel), Unit G (polish).
5. Re-run the audit as the integration gate.
