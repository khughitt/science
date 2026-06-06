# Project-local kinds in the v2→v3 entity-layout migration — design

**Status:** Draft / design — follow-up to Plan 3 (entity-organization cutover).
**Created:** 2026-06-05
**Origin:** Surfaced while attempting the v2→v3 layout migration on the MM30
project (`~/d/cancer/cancer-types/multiple-myeloma`). The Plan 3 Task 10 cutover
(`564aee95`) made `entities/` the only scanned home and enforced
`layout_version: 3`, but the migrator and policy layer only know the 21 built-in
markdown kinds. MM30 registers 18 **project-local** kinds in its local knowledge
profile (`latent`, `design`, `analysis-plan`, `rq`, `paper-synthesis`, `note`,
`audit`, `meta`, `decision`, …). Markdown-authored entities of those kinds are
never assigned a home, never migrated, and — left in `doc/` — are no longer
loaded, so references to them from migrated core entities fail the post-move
graph audit and block the `layout_version` bump.

## Scope & relationship to sibling work

This design covers **project-local kinds registered in a project's local
knowledge profile** (`knowledge/sources/<profile>/manifest.yaml`,
`entity_kinds:`) that are authored as markdown. It is distinct from
`2026-06-05-dataset-first-class-entity-design.md`, which covers the
`dataset`/`workflow`/`workflow-run` family (typed model entities on the closed
non-epistemic list). The two are independent: a project can need either, both,
or neither.

Out of scope: structurally-defined local entities (declared in
`knowledge/sources/<profile>/entities.yaml`, e.g. MM30's `latent:` nodes). These
have no markdown files, already load regardless of layout, and are a no-op here.

Also out of scope: the **interactive entity-creation path**
(`science entities create --kind <local-kind>`). `generate_entity_id`,
`validate_entity_id`, and `create_entity` keep using the no-context policy/status
accessors, so creating a *new* local-kind entity through `create` stays
unsupported. This design only needs migration + conformance to be local-kind
aware; local kinds are authored as markdown and relocated by the migrator, not
minted by `create`. Making `create` local-kind aware is a clean follow-up (it
reuses the same project-aware accessors) but is not required to migrate a project
to v3.

## Decisions (settled with the user, 2026-06-05)

1. **Identity:** migrated local-kind entities are **renumbered to `NNNN-slug`**,
   exactly like core kinds (not slug-preserved). All existing references are
   rewritten by the migrator.
2. **Scope:** **every kind registered under `entity_kinds:`** in the active local
   profile is treated as a first-class entity. Registration *is* the intent.
   Markdown files of those kinds are migrated; frontmatter is synthesized for
   prose-only files (reusing the existing synthesis path).
3. **Home:** derived as `entities/<kind-name-verbatim>/` (singular, no
   pluralization guessing) with the **`numeric`** strategy, plus an **optional
   per-kind manifest override** (`home:` / `strategy:`). Overrides are
   **validated fail-loud**: `home` must be a *relative* path of at least two
   segments rooted at `entities/` (i.e. `entities/<segment>/…`) with no `..`
   traversal — a malformed value, or the bare `entities` root (which would make
   the kind scan top-level `entities/*.md` and swallow core singleton markdown),
   is rejected. `strategy` must be `numeric` or `citekey`; **`singleton` is
   core-only** and forbidden for local kinds (the migrator has no
   local-singleton move semantics — `_plan_singletons` is hard-coded to the two
   core singleton paths).
4. **Kind identity:** the `EntityKind.name` *is* the kind, the id prefix, and the
   directory segment. `canonical_prefix` is required to equal `name` (the
   registry keys on `name` — `graph/sources.py:218,229` — and `register-kind`
   always writes them equal). The policy loader **validates `name ==
   canonical_prefix` and fails loud** on divergence rather than guessing which
   one is authoritative.
5. **Status:** local kinds **default to `active`** and accept any status unless
   the manifest declares a controlled set. Optional per-kind manifest metadata
   `default_status:` / `statuses:` overrides this.

## Current state (investigation, 2026-06-05)

- **Policy table is static & core-only.** `_BUILTIN_MARKDOWN_POLICIES`
  (`science/src/science_tool/entities.py:35`) is a hard-coded dict of the 21
  core kinds. `resolve_path_policy(kind)` raises
  `EntityCommandError("Unsupported source-authored entity kind: …")` for anything
  else. `markdown_entity_kinds()`, `is_markdown_entity_kind()`, and
  `local_part_conforms()` all read only this dict. None take project context.
- **Migrator inherits the core-only view.** `discover_legacy_entities`
  (`entity_layout_migration.py`) filters on `is_markdown_entity_kind(kind)`;
  `_DIR_TO_KIND` is derived from the builtin policy roots; `plan_migration`
  resolves homes via `resolve_path_policy`. Local-kind files are therefore
  silently skipped, and local-kind reference tokens are treated as external
  (ignored) by `rewrite_references` — so they pass the dry-run's
  `unresolved_references` gate but later hit the post-move graph audit.
- **Kind inference ignores the `id:` prefix.** `_infer_kind` uses frontmatter
  `type:`/`kind:`, then a by-path override, then the parent directory name. But
  local-kind files in MM30 live in **heterogeneous legacy dirs**
  (`doc/design/`, `doc/plans/`, `doc/specs/`) and frequently identify their kind
  via the **`id:` prefix** (e.g. `id: design:2026-05-22-…`) with **no `type:`
  field**. Directory-name fallback then misclassifies them (a `design`-id file in
  `doc/plans/` would be read as `plan`). Verified counts: `design` 14,
  `analysis-plan` 16, `meta` 8, `paper-synthesis` 3, `critique` 3, `review` 2,
  plus singletons.
- **Status accessors are core-only and crash on local kinds.**
  `default_status(kind)` and `valid_statuses(kind)` (`entities.py:138,143`)
  directly index `_DEFAULT_STATUS[kind]` / `_STATUS_VALUES[kind]`, so they raise
  `KeyError` for any local kind. `synthesize_frontmatter`
  (`entity_layout_migration.py:158`) calls both, so a frontmatterless local-kind
  file (prose-only `design`/`analysis-plan`/…) crashes the migrator before any
  move. This must be fixed for the "synthesize frontmatter for prose files"
  decision to hold.
- **`rewrite_references` is core-only too.** Its unresolved-token scan
  (`entity_layout_migration.py:534`) skips any `kind` failing core-only
  `is_markdown_entity_kind`, and calls `resolve_path_policy` / `local_part_conforms`
  (`:538,:540`) without project context. Mapped local-kind ids still rewrite (via
  `id_map`), but an **unmapped stale** `design:old-slug` is treated as external
  and slips past the dry-run `unresolved_references` gate — only to fail the
  post-move audit. A `policed_kinds` parameter already exists and is the hook to
  extend.
- **Profile resolution has a legacy fallback the loader must reuse.**
  `_read_project_config` (`graph/sources.py:872`) reads
  `knowledge_profiles.local`, falls back to legacy `profiles: {local: …}`, and
  defaults to `"local"`. A new policy loader that parses `science.yaml` directly
  would silently miss local kinds on older projects while graph loading still
  sees them.
- **Conformance checks are core-only.** `_entity_dirs`
  (`validate/checks/entity_conformance.py:51`) iterates `markdown_entity_kinds()`;
  the stranded-in-`doc`/`specs` scan filters on `is_markdown_entity_kind`. Local
  kinds are neither checked nor flagged as stranded. Severity is gated on
  `layout_version >= 3` (ERROR) vs `< 3` (WARN).
- **The cutover adapter already loads local kinds — if they are under
  `entities/`.** `MarkdownAdapter.discover`
  (`graph/storage_adapters/markdown.py:20`) `rglob`s `["entities",
  "research/packages"]` and loads every `*.md`, inferring kind from frontmatter
  `type:`. `load_project_sources` (`graph/sources.py`) registers profile kinds
  and accepts any kind in `known_kinds(core ∪ active profiles)`. So a relocated,
  schema-valid local-kind file under `entities/<kind>/` loads with **no adapter
  change**.
- **A project-aware profile loader already exists.**
  `science_model.profiles.load_profile_manifest`, `local_profile_sources_dir`,
  and `known_kinds` already enumerate a project's registered kinds. The gap is
  purely that the *policy/migration* layer does not consult them.
- **The `EntityKind` schema is small and extensible.**
  `model/src/science_model/profiles/schema.py:10` —
  `name, canonical_prefix, layer, description, entity_class?`. Adding optional
  `home`, `strategy`, `default_status`, `statuses` fields (all `None`-defaulted)
  is a clean, backward-compatible addition.

## Design

### A. Project-aware policy layer (load-bearing)

Make the four policy functions **additively** project-aware. The no-argument
behavior is unchanged (core-only), preserving every existing caller and every
project with no local kinds.

- New `EntityPathPolicy` is reused as-is (`root: Path`, `strategy`).
- New `load_local_entity_policies(project_root) -> dict[str, EntityPathPolicy]`:
  1. resolve the active local profile by **reusing `_read_project_config`'s
     normalization** (`graph/sources.py:872`) — `knowledge_profiles.local`, the
     legacy `profiles: {local: …}` fallback, and the `"local"` default — rather
     than re-parsing `science.yaml`. (Refactor `_read_project_config`, or its
     profile-name resolution, into a shared helper both call.)
  2. load that manifest via `load_profile_manifest(local_profile_sources_dir(...) /
     "manifest.yaml")`;
  3. **validate `entry.name == entry.canonical_prefix`** per Decision 4; raise a
     clear error on divergence;
  4. for each `entity_kinds` entry: `root = Path(entry.home or
     f"entities/{entry.name}")`, `strategy = entry.strategy or "numeric"`;
  5. **drop any kind already in `_BUILTIN_MARKDOWN_POLICIES`** (core kinds win;
     a local kind may never shadow a builtin);
  6. cache per `project_root` (cheap; manifest is small).
- Project-aware accessors (preferred shape — an explicit resolver object to avoid
  re-reading the manifest on every call):
  - `entity_policies(project_root=None) -> Mapping[str, EntityPathPolicy]` returns
    builtins, or `builtins ∪ local` when `project_root` is given.
  - `resolve_path_policy(kind, *, project_root=None)`,
    `markdown_entity_kinds(project_root=None)`,
    `is_markdown_entity_kind(kind, *, project_root=None)`,
    `local_part_conforms(kind, local, *, project_root=None)` all consult
    `entity_policies(project_root)`.

Local kinds get **verbatim singular dirs** (`entities/design/`,
`entities/analysis-plan/`) so there is no pluralization rule to get wrong; core
kinds keep their existing plural dirs untouched.

**Status policy (also project-aware).** `default_status` / `valid_statuses`
gain the same optional `project_root` and consult the local profile. For a local
kind: `default_status` returns the manifest `default_status` if set, else
`"active"`; `valid_statuses` returns the manifest `statuses` set if declared,
else an **open set** (any status accepted — local kinds are not forced into a
controlled vocabulary unless the project opts in). `synthesize_frontmatter` and
`ensure_frontmatter` thread `project_root` so prose-only local-kind files
synthesize a valid `status` instead of raising `KeyError`.

### B. Migrator threads project context

`entity_layout_migration.py` already has `project_root` everywhere. Thread it
into kind resolution:

- `discover_legacy_entities(project_root)` accepts files whose kind is known for
  this project. **Kind inference order becomes: frontmatter `type:`/`kind:` →
  `id:` prefix → by-path override → directory name.** Promoting the `id:` prefix
  ahead of directory name is required because local-kind files live in mixed
  legacy dirs and reliably carry a kind-prefixed `id:` but often no `type:`; the
  `core ∪ local`-derived `_DIR_TO_KIND` remains the last-resort fallback for
  truly frontmatterless prose files.
- `plan_migration(project_root)` assigns local kinds numeric `NNNN` by `created`
  date and homes them at `entities/<kind>/`, identical to core numeric kinds.
- `_add_move` already records `old_id -> new_id` in `id_map`; because local-kind
  ids now change, their refs enter `id_map` and `rewrite_references` rewrites
  them across **all** project markdown **and** the YAML registries already in
  scope (`knowledge/sources/<profile>/*.yaml`, etc.).
- **`rewrite_references` becomes project-aware.** It takes `project_root` (or a
  resolved policy set) so its unresolved-token scan uses
  `is_markdown_entity_kind` / `resolve_path_policy` / `local_part_conforms` over
  `core ∪ local`, and `policed_kinds` includes the migrated local kinds.
  Consequence: an **unmapped** stale local-kind ref (`design:old-slug` with no
  `id_map` entry, in markdown or YAML) is correctly reported in
  `unresolved_references` and **blocks `--apply`** at the dry-run gate instead of
  failing the post-move audit.
- Existing gates apply unchanged to local kinds: `collisions`,
  `undated_entities`, `unresolved_references`, then post-move graph audit, then
  the `layout_version: 3` bump on a clean audit only.

### C. Conformance threads project context

`entity_conformance.py` has `ctx.project_root`. Change `_entity_dirs` and the
stranded-in-`doc`/`specs` scan to iterate `markdown_entity_kinds(ctx.project_root)`
and use `is_markdown_entity_kind(kind, project_root=ctx.project_root)`. Local
kinds are then (a) flagged when stranded in legacy roots, and (b) checked for
filename/number/frontmatter conformance under `entities/<kind>/`, with the same
`layout_version`-gated severity as core kinds.

### D. Adapter

No change. Verified above.

## Data flow (local kinds ride the existing pipeline)

`discover` (now incl. local kinds) → `synthesize_frontmatter` (fills
`id/type/title/status/created/updated` for prose files) → `plan` (numeric NNNN,
`entities/<kind>/`) → `rewrite_references` (old local-kind id →
`kind:NNNN-slug`, all markdown + YAML) → `git mv` + write → post-move graph
audit → bump `layout_version: 3` on clean audit only.

## Edge cases & risks

- **Dual-defined kinds.** A kind defined structurally (`entities.yaml`) *and* as
  markdown would produce two entities sharing identity. The migrator's existing
  id/path collision detection surfaces it; documented as a manual fix. Low
  likelihood (MM30's structural kinds have no markdown files).
- **Schema validation on load.** `graph/sources.py` rejects a registered-profile
  kind whose file fails its typed-extension schema. Synthesized frontmatter must
  satisfy that schema. The plan must include a fixture proving a renumbered
  local-kind file loads cleanly (and, if a local kind requires fields beyond the
  six synthesized, either extend synthesis or document the requirement).
- **Stricter conformance for already-migrated projects.** A project already at
  v3 that intentionally keeps local-kind markdown in `doc/` would newly get
  ERRORs. This is correct under the "registration = entity" semantics; v2
  projects only see WARN (severity is `layout_version`-gated). Rollout note, not
  a blocker.
- **Profile resolution variants.** The active local profile may be named via
  `knowledge_profiles.local`, the legacy `profiles: {local: …}`, or defaulted to
  `"local"` — all handled by reusing the shared `_read_project_config` resolver
  (Design A.1). Shared/imported profiles whose kinds are core remain core;
  shared-profile *non-core* kinds being markdown-homed is out of scope unless a
  project uses them (confirm during implementation).
- **`research/packages`** (the other cutover scan root) is unaffected.

## Backward compatibility

Purely additive. Callers that pass no `project_root` see identical behavior.
Projects with no local kinds, and the science repo's own test suite, are
unaffected. The only behavior change is for projects that register local
`entity_kinds:` — which is exactly the intended fix.

## Testing strategy

- **Unit (`tmp_path`):** project-aware `resolve_path_policy` (local kind →
  `entities/<name>`; `home`/`strategy` override honored; core kind never
  shadowed; unknown kind still raises). `load_local_entity_policies` parsing,
  **including a manifest with `name != canonical_prefix` → raises**, an invalid
  **`home`** (absolute / `../` / non-`entities/` / bare `entities`) → raises, an
  invalid or **`singleton`** `strategy` → raises, and a **legacy
  `profiles: {local: …}`** manifest resolving correctly.
- **Status:** project-aware `default_status`/`valid_statuses` for a local kind →
  `active` default and open set; manifest `default_status`/`statuses` override
  honored.
- **Migrator:** discovery/plan/rewrite for a local kind, including a **prose-only
  (frontmatterless)** file → synthesized frontmatter (valid `status`, no
  `KeyError`) + numeric id; reference rewrite of an old local-kind id across a
  markdown body and a YAML registry; an **unmapped `design:old-slug`** is
  reported in `unresolved_references` and **blocks `--apply`**.
  **Kind inference:** a local-kind file with `id:` prefix but no `type:` in a
  *foreign* directory (e.g. `doc/plans/x.md` with `id: design:x`) resolves to
  `design`, not `plan`; an explicit `type:` still wins over a divergent `id:`
  prefix.
- **Conformance:** fixture project with a local profile — a stranded
  `doc/<x>.md` of a local kind is flagged; a non-conforming
  `entities/<kind>/bad.md` filename is flagged while a conforming
  `entities/<kind>/NNNN-*.md` is clean; severity flips WARN→ERROR with
  `layout_version` (assert `Severity.WARN` at v2, `Severity.ERROR` at v3).
- **Integration:** migrate a fixture project containing one core + one local
  kind end-to-end → files moved & renumbered, refs rewritten, post-move audit
  green, `layout_version` bumped to 3.

## Documentation

Update `docs/entity-layout-migration-guide.md` with a short "Project-local kinds"
subsection: registered local kinds are migrated to `entities/<kind>/NNNN-slug.md`
like core kinds; optional `home:`/`strategy:` manifest overrides; prose files get
synthesized frontmatter.
