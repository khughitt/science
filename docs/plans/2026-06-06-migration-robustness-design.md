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
   positions** (entity frontmatter `related:`/`source_refs:`, `.edges.yaml` evidence/anchor refs,
   `mappings.yaml` alias *targets*) block `--apply`. Unresolved tokens in **prose body**
   (including code fences, inline code, `[[wikilinks]]`, cross-project mentions, short-forms,
   placeholders) become **non-fatal warnings**, reported but not blocking. Rationale: the layout
   migration moves files and rewrites *resolvable* ids; dead prose links are pre-existing content
   issues the graph validator already reports separately, and must not gate a mechanical move.
2. **Manifest loading — graceful skip.** A malformed/vestigial local entity kind is skipped with
   an accumulated warning instead of aborting the whole migration. Validation logic is unchanged;
   only the failure mode changes (raise → skip+warn).
3. **Undated fallback — explicit keys only, still blocks.** Extend the creation-date fallback to
   consult `generated_at:` and `committed:`, but a file with genuinely no date anywhere still
   blocks (preserves the "entities must be dated" forcing function). No git-date fallback.
4. **Entity discovery — exact-root-path match.** A file is a migratable entity only if its parent
   path equals a registered entity root (`doc/papers`, `doc/questions`, `specs/hypotheses`,
   `entities/<kind>`, and each local kind's declared home). Nested non-root dirs
   (`doc/background/**`, `doc/archive/**`, …) are left in place, not swept in.

## Architecture

The migrator keeps its current shape (`discover_legacy_entities` → `plan_migration` →
`migrate_layout`, with `rewrite_references` doing the id rewrite). Changes are localized to four
seams, each an independently-testable unit:

- **Reference classification** (`rewrite_references` + a new structural-ref extractor in
  `migrate_layout`): partition leftovers into blocking (structural) vs warning (prose).
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
- Add a structural-reference extractor. For each markdown entity, parse its frontmatter and
  collect ref tokens from `related:` and `source_refs:` list values; for `.edges.yaml` collect
  `evidence:`/`anchor:` interpretation refs; for `mappings.yaml` collect alias *target* values
  (Unit E). These are the **blocking** ref set.
- `rewrite_references` keeps performing the whole-text old→new rewrite (unchanged), but its
  unresolved output is reclassified: a leftover token is **blocking** only if it also appears in
  the structural set for that file; otherwise it goes to a **warnings** bucket.
- When building the warnings bucket, strip fenced code blocks (```` ``` ````) and inline code
  spans (`` ` ``) from the text first, so example ids in documentation don't generate noise.
- `migrate_layout` report: `unresolved_references` carries **blocking** refs only (preserving its
  existing "this blocks `--apply`" meaning); add `unresolved_warnings: dict[str, list[str]]` for
  the prose tail. The pre-mutation guard raises only on `unresolved_references`.

**Effect:** wikilinks (G1), code-fence/inline examples (G2/G3), placeholders (G4), cross-project
pointers (G5), and bare short-forms in prose (G6) no longer block — provided they are not also
sitting in a structural `related:`/`source_refs:` list. A genuinely dangling **structural** ref
still blocks, as it should.

### Unit B — Graceful local-kind loading (G7)

**What:** one malformed local kind must not abort the entire migration.

**How:** `load_local_entity_policies` collects `(kind_name, reason)` warnings for kinds that fail
validation (`name != canonical_prefix`, home collides with a core directory, bad strategy, bad
home) and **skips** them, returning the valid policies plus the warning list. `migrate_layout`
and the conformance check surface these warnings in their reports. The existing validation
predicates are unchanged — only `raise EntityCommandError` becomes `warn + continue`.

**Companion project-side fixes (separate, outside the science-tool change):**
- natural-systems `knowledge/sources/project_specific/manifest.yaml`: `meta` kind
  `canonical_prefix: doc` → `meta`.
- protein-landscape `manifest.yaml`: remove vestigial `methods` and `paper-synthesis` kinds (0
  entities each; `methods` home collides with core `method`).

### Unit C — Entity-discovery tightening (G8)

**What:** stop sweeping frontmatter-less files under nested non-root dirs into the entity set.

**How:** the dir→kind fallback in `_infer_kind` currently keys on `Path(rel_path).parent.name`
(bare segment), so `doc/background/papers/X.md` matches `papers`→`paper`. Replace with an
exact-relative-path map: build `{root_path: kind}` from each kind's policy root
(`resolve_path_policy(kind).root`, e.g. `doc/papers`, `entities/papers`) and local-kind homes,
and match `Path(rel_path).parent` against those full paths. Files whose parent path is not a
registered root are not entities (left in place).

**Effect:** 3d-attention-bias `doc/background/papers|topics` + `doc/discussions`, seq-feats
`doc/background/**`, and pan-disease's non-entity `specs/hypotheses/*` prose docs are no longer
discovered as undated entities.

### Unit D — Date-fallback extension (G9)

**What:** recognize author-supplied dates stored under non-`created:` keys.

**How:** `_fallback_created` chain becomes `frontmatter.created` → `frontmatter.generated_at` →
`frontmatter.committed` → (body `**Date:**` header, already handled in `synthesize_frontmatter`)
→ filename `YYYY-MM-DD` prefix → `_UNDATED_SENTINEL`. Sentinel still blocks (decision 3).

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
  raise pre-mutation with no tree modification, exactly as today.
- Local-kind warnings and prose-ref warnings are **reported, never raised**.
- Post-mutation graph audit (Unit-A-independent) is unchanged: it still runs after `--apply` and
  blocks the `layout_version` bump on any structured-source failure.

## Testing

TDD per unit against a synthetic fixture project exercising every seam:
- local kinds incl. one **malformed** kind (Unit B: must skip+warn, tool still produces a report);
- a code-fenced example id and an inline-code id (Unit A: warn, not block);
- a `[[Wikilink]]` to an existing `paper:` (Unit A: warn, not block);
- a cross-project `hypothesis:h00-working-model` in prose (Unit A: warn) **and** a genuinely
  dangling ref in a frontmatter `related:` list (Unit A: still **blocks**);
- a frontmatter-less file under `doc/background/papers` (Unit C: not discovered as an entity);
- a synthesis file with only `generated_at:` (Unit D: not undated) and a truly date-less file
  (Unit D: still blocks);
- a `mappings.yaml` with an alias whose source key looks like a ref (Unit E: source exempt,
  dangling target blocks);
- two same-named files in distinct date-dirs (Unit F: distinct aliases, no collision).

**Integration check:** re-run the live 19-project dry-run from the audit. Expected: natural-systems
and protein-landscape no longer crash; every project except seq-feats reaches `ready` (0
collisions, 0 structural-unresolved, 0 undated) with **zero project-side edits**; warnings are
populated but non-blocking. seq-feats remains blocked on its genuine content debt.

## Affected files (science/)

- `science/src/science_tool/entity_layout_migration.py` — Units A, C, D, F, G (discovery,
  date fallback, ref classification, alias generation, report keys).
- `science/src/science_tool/entities.py` — Unit B (`load_local_entity_policies` skip+warn).
- `science/src/science_tool/validate/checks/entity_conformance.py` — surface local-kind warnings;
  align with the position-aware model where it inspects refs.
- Possibly a small new helper module for structural-ref extraction + code-span stripping if
  `entity_layout_migration.py` grows unwieldy.
- Tests under `science/tests/` (per-unit) + the multi-project integration check.

## Remediation order (matches plan task order)

1. Unit B (G7) — unblock the two crashes (smallest change, highest unblock).
2. Unit D (G9) — clears most "undated" counts.
3. Unit A (G1–G6) — the keystone reclassification; largest false-positive class.
4. Unit C (G8), Unit E (G10), Unit F (G-novel), Unit G (polish).
5. Re-run the audit as the integration gate.
