# Adapter-backed entity layout: owners → `entities/`, overlays → `overlays/`

**Predecessors:**
- `2026-06-03-entity-organization-and-naming-design.md` — established the v3 principle ("location tracks what a thing is"; markdown entity owners live under `entities/<kind>/`; `doc/` becomes prose-only) but left the dataset/workflow family and the post-v3 overlay home unresolved.
- `2026-04-19-dataset-entity-lifecycle-design.md` — explicitly **deferred** "should dataset/workflow/workflow-run become first-class `entities/` kinds" to a dedicated follow-up. **This is that follow-up** (the layout half only).
- `2026-05-13-multiproject-schema-and-shared-store-design.md` §5.1 — placed commons overlays at `<project>/doc/<type>/<slug>.md` on a co-location rationale that no longer holds once `doc/` is prose-only.
- `2026-06-05-local-kind-layout-migration-design.md` — the local-kind layout migration the framework already shipped.

**Status:** Draft
**Depends on:** the v3 markdown migration (already applied in science + MM30); the revived `science entities migrate` migrator (science `1f7b472c`).

---

## Purpose

Finish the v3 layout cutover for the two kinds of markdown the v3 design left behind:

1. **Adapter-backed owner entities** — the `dataset` / `workflow` / `workflow-run` family, currently stranded in `doc/<type>/` as a "transitional" home (`graph/sources.py:295-304` comment). Move their **owner** files to `entities/<kind>/`, exactly like `paper` and `topic` already do.
2. **Commons overlays** — files carrying `overlay_of:`, currently in `doc/<type>/`. Give them a real home at a new top-level **`overlays/<type>/`** root, so `doc/` becomes genuinely prose-only as the v3 design intends.

End-state: every markdown entity has exactly one structural home, and a reader can locate anything by *what it is* — an owner (`entities/`), a borrow (`overlays/`), or prose (`doc/`). No kind is special-cased into the prose grab-bag.

**Guiding principle (unchanged from 2026-06-03):** location tracks what a thing is. This design extends it to the last two holdouts rather than inventing anything new.

## Scope decomposition

**In scope**
- Wire `home` + `strategy` for `dataset`, `workflow`, `workflow-run`, `workflow-step` in the core profile.
- An **id-preserving, filename-normalizing** migrator path for these kinds (the crux — see Key decision 1).
- Introduce the `overlays/<type>/` root; relocate all overlay files (dataset, paper, topic, theme) out of `doc/<type>/`.
- Flip every `doc/<type>/`-hardcoding code path (discovery, commons-promote, catalog CLI, overlay adapter, validator) to the new roots.
- Drop the legacy `data-` filename prefix on dataset entities and retire the `data-<slug>.md` overlay-adapter hack.
- Migrate MM30 fully; produce a per-project runbook; fan out.
- Update `research-papers` / `topic-researcher` skills to write owners to `entities/`.

**Out of scope (deferred)**
- The rest of the 2026-04-19 dataset lifecycle (register-run, symmetric `produces`/`inputs` edges, `research-package` relocation to `research/packages/`, the 11 state invariants). This design is **layout only** — where files live, not how datasets are produced or reconciled. `data-package`/`research-package` are therefore **not** wired here (`research-package` already has a separate home in the lifecycle design).
- Multi-backend overlay storage. Overlays stay project-local markdown.
- Any v2 back-compat. Per the project owner: breaking changes are acceptable; no dual-read transitional layer is to be maintained beyond what a single cutover needs.

## Architecture

Target project layout (MM30 shown; `NEW` / `MOVE` / `UNCHANGED`):

```
<project>/
  entities/
    datasets/          NEW    250 owner descriptors  (was doc/datasets/data-*.md owners)
      ctrpv2.md               id: dataset:ctrpv2     (filename = id local part; no data- prefix)
      ...
    workflows/         NEW    workflow owners        (was doc/workflows/)
    workflow-runs/     NEW    workflow-run owners    (where present)
    papers/  topics/  ...     UNCHANGED  (already migrated owners)
  overlays/            NEW    commons-borrow surface
    datasets/                 4 overlay_of files     (was doc/datasets/data-*.md overlays)
    papers/  topics/  themes/ overlay_of files       (was doc/papers, doc/topics, doc/themes)
  doc/                 MOVE→  prose ONLY now
    reports/ guides/ figures/ background/ approach/...  UNCHANGED
    datasets/ papers/ topics/ themes/   REMOVED (emptied by the move)
```

Framework changes (`~/d/science`):

```
science/model/src/science_model/profiles/
    schema.py:12                  MODIFY  add "id-local" to EntityFilenameStrategy Literal
    core.py                       MODIFY  dataset/workflow/workflow-run/workflow-step → home + strategy="id-local"
science/src/science_tool/
    entity_layout_migration.py    MODIFY  id-local path (preserve id) + overlay-relocation pass + collision gate
    graph/sources.py:306          MODIFY  owner discovery → entities/<kind>/ (drop doc/ roots)
    graph/commons_sources.py:75   MODIFY  overlay scan gate → overlays/
    commons/overlay.py:39-44,92-107  MODIFY  overlay root → overlays/; drop data- hack (93-94)
    commons/promote.py:204-218    MODIFY  PROMOTE_KIND_DATASET.source_subdirs → entities/datasets
    datasets_catalog.py:92        MODIFY  new-candidate writes → entities/datasets/<slug>.md
    validate/_helpers.py:143      MODIFY  MarkdownAdapter(scan_roots=["doc/datasets"]) → entities/datasets
    graph/health.py:1279          MODIFY  datasets_dir doc/datasets → entities/datasets
    graph/health.py:1626          MODIFY  runs_dir doc/workflow-runs → entities/workflow-runs
    validate/checks/entity_conformance.py:195-223  MODIFY  generalize overlay-placement check
```

> The `_helpers.py` and `health.py` reads are easy to miss and **silent**: if left
> pointing at `doc/datasets`/`doc/workflow-runs` after the move, `science validate`
> and `science health` lose all migrated dataset/workflow-run coverage with no error.
> Phase 3 guards this with an explicit hardcoded-path audit (see Phase 3 DoD).

## Key decisions

### Key decision 1 — new `id-local` strategy (the crux)
- **Chosen approach:** Add a **new strategy value `id-local`** to `EntityFilenameStrategy` (`profiles/schema.py:12`, currently `numeric|citekey|singleton|slug|verbatim`). Its contract: **the frontmatter `id:` is authoritative and preserved verbatim; the destination filename is the id's local part** (`dataset:ctrpv2` → `entities/datasets/ctrpv2.md`). A file of an `id-local` kind that lacks an explicit `id:` is a hard error during planning (no stem fallback). The `data-` filename prefix is dropped as a side effect of filename-follows-id.
- **Rejected alternatives:** (a) reuse `slug`/`verbatim`, which derive the **id from the filename stem** (`entity_layout_migration.py:464`: `local = Path(rel_path).stem; new_id = f"{kind}:{local}"`) — on MM30's `data-<slug>.md` files this mints `dataset:data-<slug>`, rewriting ~250 ids and ~632 refs and diverging every overlay from its commons canonical; (b) an unnamed "migrator mode" toggled per-kind outside the strategy vocabulary — invisible to the policy contract and untestable as a kind property.
- **Reason:** A first-class strategy value makes the id-preservation an explicit, validated kind contract (not migrator-internal magic). Preserving the id means **zero reference rewrites** — only file paths change. Filename-follows-id is the correct long-term invariant (filename reflects identity, not defines it).
- **Sequencing implication:** the `id-local` strategy must exist and be tested before `core.py` sets it on any kind, or any stray `migrate` dry-run corrupts ids via the old slug path.

### Key decision 2 — `overlays/` top-level root (not `doc/<type>/`, not under `entities/`)
- **Chosen approach:** A new sibling root `overlays/<type>/<slug>.md` for all `overlay_of:` files.
- **Rejected alternatives:** (a) keep overlays in `doc/<type>/` — contradicts the v3 "doc/ is prose-only" rule and re-mixes machine surface with prose; (b) put overlays under `entities/` — forbidden by `check_overlay_of_in_owner_root` because `MarkdownAdapter` would mint them as spurious owners colliding with the commons canonical.
- **Reason:** A dedicated root gives the borrow-surface symmetry with `entities/` (own vs. borrow), turns the validator rule from negative ("not in entities/") into positive ("overlays live in overlays/"), and lets `doc/` finally be pure prose.

### Key decision 3 — drop the `data-` prefix; retire the overlay-adapter hack
- **Chosen approach:** Migrate `doc/datasets/data-ctrpv2.md` → `entities/datasets/ctrpv2.md` (owner) / `overlays/datasets/ctrpv2.md` (overlay). Remove the `data-<slug>.md` special-case in `commons/overlay.py:93-94`.
- **Rejected alternative:** keep the `data-` prefix and special-case the strategy forever.
- **Reason:** The prefix is the legacy artifact that *caused* the id/stem mismatch; the adapter hack only existed to disambiguate overlays from canonicals inside the shared `doc/datasets/` dir — once overlays have their own root, the collision is structurally impossible.

### Key decision 4 — layout only; lifecycle stays deferred
- **Chosen approach:** Wire `home`/`strategy` and move files. Do not touch register-run, symmetric edges, `research-package` relocation, or the state invariants.
- **Rejected alternative:** resolve the full 2026-04-19 lifecycle in one slice.
- **Reason:** The inconsistency being fixed is purely *where files live*. Bundling production/reconciliation semantics multiplies risk and review surface for no gain to the normalization goal.

### Key decision 5 — owner vs. overlay relocation are two passes
- **Chosen approach:** The migrator's owner pass moves `entities/`-bound owners; a distinct **overlay-relocation pass** (same `--apply`, separate logic) moves `overlay_of:` files to `overlays/`. Today the migrator *skips* overlays (`entity_layout_migration.py:91`); that skip becomes "relocate to overlays/" for these types.
- **Rejected alternative:** a separate standalone `science overlays relocate` command.
- **Reason:** One audited, atomic cutover per project is safer than two commands a user can run out of order; the audit gate already guards the whole apply.

## Phases

### Phase 1 — Framework: `id-local` strategy (TDD)
- **Depends on:** nothing (migrator already revived).
- **Entry point:** `profiles/schema.py:12` (add `id-local`); `entity_layout_migration.py` strategy dispatch + `test_entity_layout_migration.py`.
- **Definition of done:** `id-local` is a valid `EntityFilenameStrategy`; failing-then-passing tests prove `doc/datasets/data-ctrpv2.md` (frontmatter `id: dataset:ctrpv2`) → planned move to `entities/datasets/ctrpv2.md` with id **unchanged** and **no ref rewrites**; a synthetic owner whose stem ≠ id is renamed to match the id; an `id-local` file with **no explicit `id:`** raises a planning error (no stem fallback); existing slug/citekey/verbatim/numeric behavior for other kinds is untouched (regression tests green).

### Phase 2 — Framework: wire `home`/`strategy` (owners) + owner-collision gate (TDD)
- **Depends on:** Phase 1.
- **Entry point:** `core.py` kind definitions; `test_migrate_*`.
- **Scope note (sequencing correction):** overlay relocation was originally bundled here but **moved to Phase 3** — relocating overlays to `overlays/` requires the `OverlayAdapter` to read `overlays/` in the *same* step, or the migrator's post-move audit reports borrowed entities as unresolved and aborts `--apply`. Owner migration has no such coupling (`MarkdownAdapter` already scans `entities/`), so Phase 2 stays clean and atomic with owners only.
- **Definition of done:**
  - `dataset`→`entities/datasets`, `workflow`→`entities/workflows`, `workflow-run`→`entities/workflow-runs`, `workflow-step`→`entities/workflow-steps`, all `strategy="id-local"`.
  - Test: a dataset **owner** `doc/datasets/data-x.md` (`id: dataset:x`) migrates to `entities/datasets/x.md`, id preserved, no ref rewrites, post-move audit passes.
  - **Owner target-collision gate:** `doc/datasets/data-x.md` + `doc/datasets/x.md` (both `id: dataset:x`) → both target `entities/datasets/x.md`; existing `_detect_collisions` (path + id) populates `plan.collisions` and `--apply` aborts (`entity_layout_migration.py:1207`). Test proves the abort.

### Phase 3 — Framework: flip readers/writers + overlay relocation + audit gate (TDD)
- **Depends on:** Phase 2.
- **Entry point:** `sources.py:306`, `commons_sources.py:75`, `overlay.py:39-44,92-107`, `promote.py:204`, `datasets_catalog.py:92`, `validate/_helpers.py:143`, `graph/health.py:1279`, `graph/health.py:1626`, `entity_conformance.py:195`; migrator overlay-relocation pass.
- **Definition of done:**
  - discovery finds dataset/workflow **owners** under `entities/`; `OverlayAdapter` scans `overlays/` (root constant, lines 92/107); commons-promote candidate scan + catalog writes target `entities/datasets/`; the `_helpers.py` validate-discovery scan_root and both `health.py` reads point at `entities/`; the `data-` hack (45, 93-94) is removed; `check_overlay_of_in_owner_root` is generalized to "overlays belong in `overlays/`" (ERROR at v3 if an `overlay_of:` file is found under `entities/` **or** `doc/<type>/`).
  - **Migrator overlay-relocation pass** (coupled with the OverlayAdapter flip above): `overlay_of:` files of all 4 federated types relocate `doc/<type>/` → `overlays/<type>/`, filename = `overlay_of` local part (drops `data-`), id preserved. Routed through `plan.moves` so `_detect_collisions` covers overlay→same-destination clashes for free. Test: an owner+overlay pair lands in the two distinct roots and the post-move audit (now reading `overlays/`) passes.
  - **Hardcoded-path audit (gate):** a repo grep proves no remaining source-tree literal of `doc/datasets`, `doc/workflows`, `doc/workflow-runs`, `doc/papers`, `doc/topics`, or `doc/themes` outside tests/fixtures and explicitly-justified legacy comments. This is the backstop against silently-stranded readers like `_helpers.py`/`health.py`.
  - Full science test suite green.

> **Phase 3 implementation notes (deviations from the original sketch):**
> 1. **Audit gate scoped to the three moved kinds.** The gate (`test_no_doc_owner_path_literals.py`) policies only `doc/datasets`, `doc/workflows`, `doc/workflow-runs` — the owner kinds this slice actually moved. The federated `doc/papers`/`doc/topics`/`doc/themes` **owner-discovery** readers (`PROMOTE_KIND_*.source_subdirs`, reused by `annotation/source_text._paper_dirs` and meta-checkouts that store papers under `doc/background/papers/`) carry pre-existing v2/v3 dual-layout support from the earlier paper/topic migration and are **out of this slice** — narrowing them broke `annotation` paper resolution, so only their **overlay dest** moved to `overlays/`. Owner-discovery dual-layout cleanup for papers/topics is a separate follow-up.
> 2. **`dataset_frontmatters` scans both roots.** Owners are in `entities/datasets/`; pinned overlays are in `overlays/datasets/`. The validate helper scans both (an owner and its overlay never coexist for one id, so id-dedup is safe), and `dataset_promotion_contract._is_dataset_descriptor` accepts both prefixes — otherwise pinned-overlay contract validation would silently lose coverage.
> 3. **Latent promote double-unlink bug fixed.** Once owners (`entities/`) and overlay dest (`overlays/`) live in different dirs, a case-rename candidate set BOTH `rename_from` and `unlinked_source` to the same source path, double-unlinking it. Guarded `apply_promote` against re-unlinking what `rename_from` already removed.

### Phase 4 — MM30 cutover (proving ground)
- **Depends on:** Phase 3.
- **Entry point:** `cd ~/d/r/mm30 && science entities migrate --apply` (after a clean dry-run + audit gate).
- **Definition of done:** 250 dataset owners in `entities/datasets/` (no `data-` prefix), 1 workflow in `entities/workflows/`, 4 dataset overlays + all paper/topic/theme overlays in `overlays/<type>/`, `doc/{datasets,workflows,papers,topics,themes}/` emptied/removed; `science validate` clean; `git diff` shows **path renames only, zero `dataset:`-id ref changes**.

### Phase 5 — Skills/agents + docs
- **Depends on:** Phase 3.
- **Entry point:** the stale **agent** docs `agents/paper-researcher.md:95` and `agents/topic-researcher.md:34` (these still write owners to `doc/papers/`/`doc/topics/`); `graph/sources.py:295-304` transitional comment. Note `commands/research-papers.md:110` already targets `entities/papers` — verify, don't rewrite.
- **Definition of done:** the two agent docs write paper/topic **owners** to `entities/<kind>/`; a grep confirms no remaining agent/command doc instructs writing owners to `doc/<type>/`; the "deferred" comment in `sources.py` is replaced with a pointer to this design; user-guide layout docs mention `overlays/`.

### Phase 6 — Fan-out
- **Depends on:** Phase 4 (runbook proven on MM30).
- **Entry point:** per-project `migrate --apply` using the MM30 runbook.
- **Definition of done:** every active project at `layout_version: 3` with owners in `entities/`, overlays in `overlays/`, `doc/` prose-only, and a clean `science validate` (modulo pre-existing data-debt blockers tracked separately).

## Open questions

1. **`workflow-run` / `workflow-step` confirmation** — all four kinds use `id-local`; confirm existing instances across projects all carry explicit `id:` (required by `id-local`) before wiring. Sparse today, so low risk.
2. **`doc/<type>/` empty-dir cleanup** — remove the now-empty dirs in the same commit, or leave `.gitkeep`-free for git to drop? (Lean: remove.)
3. **Commons-side awareness** — does anything in `~/d/science-commons` read project `doc/<type>/` overlay paths? (Explore found project-side coupling only; verify before Phase 6.)

*(Overlay target-collision detection, formerly an open question, is promoted to a Phase 2 acceptance criterion — it must block `--apply`, not be checked after the fact.)*

## Non-Goals

- No dataset *production* semantics (register-run, reconcile, symmetric edges).
- No `research-package`/`data-package` relocation.
- No v2 dual-read compatibility layer.
- No change to commons canonical storage layout.

## Acceptance criteria

- [ ] `id-local` strategy exists; preserves ids for adapter-backed kinds; errors on missing `id:`; zero ref rewrites on MM30 (Phase 1/4).
- [ ] `dataset`/`workflow`/`workflow-run`/`workflow-step` have `home`+`strategy="id-local"`; owners discoverable under `entities/` (Phase 2/3).
- [ ] Target-collision gate blocks `--apply` on any two sources sharing a destination (Phase 2).
- [ ] `overlays/<type>/` is the sole overlay home; `doc/` contains no `overlay_of:` files anywhere (Phase 3/4).
- [ ] Hardcoded-path audit: no source-tree literal of `doc/{datasets,workflows,workflow-runs,papers,topics,themes}` outside tests/justified comments (Phase 3).
- [ ] `data-` prefix and `data-<slug>.md` adapter hack are gone (Phase 3/4).
- [ ] MM30 `science validate` + `science health` clean; `git diff` is renames-only (Phase 4).
- [ ] Agent docs write owners to `entities/` (Phase 5).
- [ ] Fan-out projects at `layout_version: 3` with the three-root layout (Phase 6).
