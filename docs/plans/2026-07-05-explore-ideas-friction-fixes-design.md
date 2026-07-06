# explore-ideas friction fixes — design

**Date:** 2026-07-05
**Targets:** fb-2026-07-05-001 (report-path collision), fb-2026-07-05-003 (related_existing resolution)
**Surface:** `command:explore-ideas` and its supporting `science` CLI + `explore_ideas.py`.

Two independent friction fixes filed against `explore-ideas`, bundled because they
touch the same command flow.

---

## Slice A — relocate the Phase-4 report out of `entities/` (fb-2026-07-05-001)

### Problem

Phase 4 writes `entities/meta/explorations/explore-<YYYY-MM-DD>.md` with `kind: meta`
frontmatter. `meta` is a numeric registered entity kind, so the entity-conformance
check `check_entity_stray_files` (`validate/checks/entity_conformance.py:174`) flags the
`explorations/` subdirectory as an "unexpected subdirectory in entities/meta/" — an
ERROR at layout_version ≥ 3. Every explore-ideas run leaves the project failing
`science validate` until the report is moved.

The root cause is not the validator: the framework does **not** treat
`entities/meta/explorations/` as a valid entity home (the MarkdownAdapter mints only
top-level `entities/meta/*.md`). The report has `kind: meta` frontmatter but is really a
journal-style **process artifact**, not a graph entity — a non-entity file masquerading
under `entities/`.

### Decision

**Relocate reports to `doc/explorations/explore-<YYYY-MM-DD>.md`** and drop the
`kind: meta` frontmatter. This fixes the collision at its source rather than teaching the
generic validator to tolerate a non-entity subdirectory under an entity kind (which would
weaken the check for every project). It also aligns with the project Documentation State
Model, under which journal-style/report material belongs in `doc/`, not `entities/`.

Rejected alternative — allowlisting `explorations/` in `check_entity_stray_files`: smaller
change, but keeps a non-entity file under `entities/` and special-cases the shared
validator.

### Changes

- `explore_ideas.py:resolve_report_path` — base directory `entities/meta/explorations/`
  → `doc/explorations/` (candidate path at :117 and the error string at :123). The
  `--from <id>` resolution form (stem `explore-<date>`, `explore-` prefix) is unchanged.
- `commands/explore-ideas.md` Phase 4 (:184) — new write path; remove the `kind: meta`
  instruction. The report keeps a lightweight human header, no entity frontmatter.
- Regenerate `codex-skills/science-explore-ideas/SKILL.md` (generated mirror).
- Test fixtures that copy a report into `entities/meta/explorations/…` → `doc/explorations/…`.

No back-compat shim for the old path (per the no-legacy-layers rule): the field is one day
old with exactly one real report.

### Downstream (separate, in the MM30 repo — not this science change)

Migrate MM30's existing `entities/meta/explorations/explore-2026-07-05.md` →
`doc/explorations/`, remove the emptied `entities/meta/explorations/` dir, and confirm
`science validate` clears the ERROR. Done as a follow-up commit in the MM30 repo after the
science change lands.

---

## Slice B — deterministic `related_existing` resolution + apply wiring (fb-2026-07-05-003)

### Problem

Two distinct defects:

1. **Recall.** In Phase 3 the orchestrator authors `related_existing` by eyeballing
   existing entity **titles**. Matches whose shared keyword lives only in the **id-slug**
   are missed — e.g. a novel m6A candidate was not linked to
   `question:0037-m6a-proliferation-axis` because "m6a" appears only in that id-slug, not
   its title.
2. **Correctness + dead field.** `related_existing` ids are authored as free strings;
   ~11 in one report were wrong slugs, caught only by hand-validating against the loaded
   index. Worse, `related_existing` is **never consumed at apply time** —
   `build_create_plan` handles origins/source_refs/lens_views only — so even correct
   values produce **zero graph edges** today. The field is effectively dead.

### Decision

Add a **deterministic resolver** and **wire resolved refs into apply-time edges.**

#### 1. Resolver: `science project resolve-refs`

Sibling to `project index` / `project topic-coverage` — resolving free-string refs to
canonical ids is a generic project fact, not explore-ideas-specific.

- **Input:** one or more query strings (`--query`, repeatable) — an approximate id, a
  slug, or a keyword/title fragment. `--project-root` (default `.`), `--format text|json`.
- **Match set:** the same question + hypothesis entities `project index` exposes. The
  resolver takes index rows as input, so extending to other kinds later is a one-line
  change; topics/papers are out of scope for this slice.
- **Matching (deterministic).** For each entity precompute
  `(canonical_id, id_local_slug, title_slug)`. Slugify the query, then rank candidates by
  the first tier that fires: `id-exact` (query equals a canonical id) → `id-slug` (the
  query slug is contained in the entity's `id_local_slug`) → `title-slug` (the query slug
  is contained in the entity's `title_slug`). "Contained in" = the query slug is a
  substring of the entity slug. The id-slug tier is what closes the m6A miss.
- **Output (JSON):** per query
  `{query, resolved: <id>|null, match_kind, candidates: [<id>...]}` where `match_kind ∈
  {id-exact, id-slug, title-slug, ambiguous, unresolved}`. A single best-ranked match →
  `resolved`; multiple equally-ranked → `ambiguous` with `candidates`, `resolved: null`;
  none → `unresolved`, `resolved: null`. Deterministic tie-break by id. Text format prints
  one line per query.

#### 2. Apply-time validation + wiring

- `build_create_plan` reads `related_existing`. Each entry must resolve to a **real
  canonical id present in the index**: exact ids pass through; non-exact entries run
  through the resolver — unambiguous → canonicalized; ambiguous/unresolved →
  **fail-early** `ApplyValidationError` naming the bad ref and any candidates (explicit >
  defensive; fail early, no silent drop). Dedup preserved order.
- Resolved ids flow into `create_entity(related=...)` (already supported,
  `entities.py:830`) → they land as `related:` frontmatter on the created entity and
  become real graph edges.
- Only **kept** candidates are created, so only their `related_existing` becomes edges.
  `already-covered` candidates are dropped (not created); their `related_existing` stays a
  report-only annotation.

#### 3. Command wiring (`commands/explore-ideas.md` Phase 3)

Replace the manual "slug pre-pass" prose with a step that calls
`science project resolve-refs` to canonicalize each `related_existing` before writing the
report, and note that apply hard-validates the ids. Regenerate the codex mirror.

---

## Testing

- **`test_resolve_refs.py`** (new): id-exact; id-slug-only (m6A regression — query
  resolves `question:0037-m6a-proliferation-axis` though its title lacks "m6a");
  title-slug; ambiguous → candidates + `resolved:null`; unresolved → null; deterministic
  ordering; CLI JSON shape; text-format shape.
- **`test_explore_ideas.py`** (extend): `build_create_plan` canonicalizes a slightly-off
  `related_existing` id; fails-early on unresolvable/ambiguous refs; `apply_report` writes
  resolved ids into the created entity's `related:` frontmatter; report-path tests
  repointed to `doc/explorations/` (new base + updated error string).
- **Regression:** `test_codex_skills.py` green after mirror regeneration.
- **Smoke:** `resolve-refs` against MM30's real index for the m6A case; end-to-end
  `explore-ideas apply` on a fixture confirming `related:` edges land.
- Full suite green; `ruff check` / `ruff format --check` clean before merge.

## Non-goals

- Extending `resolve-refs` / `project index` to topics, papers, or propositions.
- Any back-compat alias for the old `entities/meta/explorations/` path.
- Changing Phase-1/Phase-2 blindness or the seed-coverage diagnostic (prior slice).
- Auto-migrating other projects' historical exploration reports (only MM30's one report).
