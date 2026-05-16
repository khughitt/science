# Phase E: Commons promote — papers

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§8 `science promote` shape, §9 phase E)
**Predecessors (all merged):**
- Phase B — commons scaffolding (`docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md`)
- Phase C — commons data resolver (`docs/plans/2026-05-14-commons-data-resolver-design.md`)
- Phase D1 — commons overlay merge (`docs/plans/2026-05-14-commons-overlay-merge-design.md`)
- Phase D2 — `inventory_v2` (`docs/plans/2026-05-14-commons-inventory-v2-design.md`)
- Dashboard `inventory_v2` pivot (`~/d/dashboard/docs/specs/2026-05-14-dashboard-inventory-v2-pivot-design.md`)

## 1. Goal

Add `science commons promote paper` to move paper entities from per-project `doc/papers/<slug>.md` files into the commons store at `<commons>/papers/<slug>.md`, splitting each source file into:

- **Canonical surface** (commons-side `papers/<bibkey>.md`): the paper's shared facts — title, authors, year, venue, DOI/PMID, ontology terms, dataset references, key findings, methods summary, limitations. Promote also writes the canonical-required base fields (`schema_profile`, `version`, `created`, `updated`); see §4.1.1.
- **Project overlay** (project-side `doc/papers/<bibkey>.md`, rewritten in place): `id`, `overlay_of: paper:<bibkey>`, `pin_version: <tagged semver>`, the project-side metadata fields the overlay schema adds (`status`, `source`, `related`, `source_refs`, plus the project's own `created` / `updated`), and project-only body sections (`## Project Use`, `## Relevance`, free prose). `tags` lives only on the overlay (canonical is always empty); see §4.1.2.

Multi-instance dedup is automatic where canonical fields agree or are one-sided; an interactive prompt fires only when the same canonical field has different values across projects. The dedup key is the **normalized bibkey** (filename case-insensitive, without `.md`).

**Pilot run target** (manual, post-merge): `~/d/natural-systems/`, `~/d/cancer/cancer-types/multiple-myeloma/`, `~/d/cancer/meta/`, `~/d/cancer/mechanisms/evolution/`, `~/d/protein-landscape/` — ~503 papers, ~9 known cross-project bibkey collisions (e.g., `huh2024`, `dang2023`, `lu2025`).

## 2. Scope

### In scope

- New schema profile `mixin-paper-2.0` covering the field set actually used in the wild, with `merge:` annotations classifying each field as canonical / project-only / append. Includes an `x-canonical-body-sections` annotation listing which `## ...` headings belong on the commons surface vs the overlay.
- New module `science_tool/commons/promote.py` owning the discovery → dedup → classification → write pipeline.
- New CLI subgroup `science commons promote paper` under the existing `commons_group`: single-entity form and bulk form, dry-run by default, atomic-batch `--apply`.
- New error classes: `PromoteInputError`, `PromoteCandidateError`, `PromoteConflictAbort`, `PromoteWriteError`.
- New tests covering discovery, plan, apply, CLI, and conflict-resolution paths; new fixtures under `tests/fixtures/promote/` synthesizing the dedup cases (the synthetic fixtures, not the pilot run, are what CI exercises).

### Out of scope (deferred)

- **Topic / theme promote — Phase F.** Same shape, same tooling, but a separate design slice to keep the first promote roll-out tight. The promote module is structured per-type (`promote.py` exposes paper-specific helpers; topic/theme/dataset add sibling modules later) so Phase F adds files, not refactors.
- **Dataset promote — Phase G.** Datasets carry bulk data, hash recomputation, descriptor relocation, and per-machine override management; large enough to warrant its own design.
- **`science promote rollback <op-id>` command.** Reversibility is delivered as a documented git-based procedure plus a structured audit log; a one-shot rollback command is a follow-up if the manual procedure proves error-prone.
- **Multi-type bulk promote in a single invocation.** Each `promote` invocation handles exactly one entity type. A future shape `science commons promote all --from ...` is conceivable but not in this design.
- **Schema migration of in-the-wild papers to 2.0 outside of promote.** The promote tool normalizes field shapes (e.g., string author → list of authors) on the way through; project-side files that are never promoted stay on whatever schema they happen to carry. There is no separate `science migrate-papers-to-2.0` command.
- **BibTeX cross-check.** Existing project `references.bib` files are not read by promote in Phase E; canonical fields are taken from the per-paper `.md` frontmatter. BibTeX as a source of truth is a later concern.

## 3. Architecture

The work splits into two deliverables that ship together:

1. **Schema extension (`science_model`)** — `mixin-paper-2.0.json` becomes the canonical paper profile, addressed via the new `default_profile_for_kind("paper")` helper (§4.5). `overlay-1.1.json` bumps the overlay schema to carry project-only paper fields and relax the canonical id regex (§4.4). The existing `read_merge_policy` and overlay merge pipeline (Phase D1) read the new annotations without code changes; `inventory_v2` is unaffected.
2. **Promote module (`science_tool/commons/promote.py`)** — sibling of `resolver.py` / `overlay.py`, owning discovery / dedup / classification / write. Atomic-batch transaction semantics: one `--apply` produces one commons commit, N entity tags pointing at it, N project file rewrites, one `.migrations/` audit entry. Dry-run is the default.

Project-side discovery walks `<project_root>/doc/papers/*.md` directly (not via `build_inventory`, see §5.3 for why). The classifier reads the new merge policy from the schema; conflict resolution prompts use the terminal idioms (`click.prompt`) already established in the Phase B `commons` CLI.

### 3.1 Code layout

```
science/model/src/science_model/schemas/
├── mixin-paper-1.0.json        # KEPT for compatibility; no consumers strict against it
├── mixin-paper-2.0.json        # NEW — paper-canonical fields + merge annotations
└── overlay-1.1.json            # NEW — adds the project-only paper fields the 1.0 overlay
                                #       rejects under additionalProperties:false; relaxes
                                #       canonicalId regex to permit hyphens. See §4.4.

science/model/src/science_model/entity_schema/
├── merge.py                    # MODIFIED — `read_canonical_body_sections(profile)` helper
└── profile.py                  # MODIFIED — `default_profile_for_kind(kind)` helper
                                #            returning the parsed `science-entity-base/1.0+<kind>/<ver>`

science/src/science_tool/commons/
├── promote.py                  # NEW — discovery, plan, apply
├── cli.py                      # MODIFIED — `promote paper` subgroup
├── config.py                   # MODIFIED — new `resolve_project_by_id(project_id) -> Path` helper
├── errors.py                   # MODIFIED — four new error classes
└── __init__.py                 # MODIFIED — export PromoteCandidate / Decision / FailedCandidate / DiscoveryResult / PromotePlan / Result + discover/plan/apply

science/tests/
├── test_commons_promote_discovery.py    # NEW
├── test_commons_promote_plan.py         # NEW
├── test_commons_promote_apply.py        # NEW
├── test_commons_cli_promote.py          # NEW
└── fixtures/promote/                    # NEW — synthetic 2-project corpus with engineered conflicts
```

Nothing outside `commons/` is touched in `science_tool/`. Schema work touches `science_model/schemas/`, `entity_schema/`, `entities.py`, and the existing schema tests (`test_entity_schema_mixin_paper.py`, plus a new `test_entity_schema_overlay.py` extension if not already present).

## 4. Schema work

Two schemas change together: `mixin-paper-2.0` (canonical paper fields) and `overlay-1.1` (the project-side fields and id regex). They MUST ship in the same commit — promote rewrites project files in a shape the 1.0 overlay rejects, so a 1.0/2.0 mix is broken on day one.

### 4.1 `mixin-paper-2.0` — paper-specific canonical fields and base overrides

Every canonical entity is `science-entity-base/1.0+<mixin>` (`schema_profile`, `id`, `type`, `title`, `version`, `created`, `updated` are required by the base, and it contributes `ontology_terms`, `tags`, `status`, plus optional `description` / `sources` / `licenses` / `contributors` as well). The mixin layers paper-specific fields on top of that, AND can override the base's per-field `science:merge` annotations via `read_merge_policy`'s "later component wins" lookup (`merge.py:30`). For papers we use both capabilities.

**Paper-specific fields added by the mixin** (all `merge: replace` unless noted):

| Field | Type | Merge policy | Source today |
|---|---|---|---|
| `bibkey` | string (`[A-Za-z][A-Za-z0-9-]{1,63}`, hyphens permitted) | replace | derived from `id` |
| `authors` | `list[str]` | replace | MM (string → single-element list; see §4.2) |
| `year` | int | replace | MM |
| `venue` | string | replace | MM (renamed from `journal` in 1.0) |
| `doi` | string | replace | MM |
| `pmid` | string | replace | MM |
| `url` | string | replace | rare |
| `datasets` | `list["dataset:<slug>"]` | **append** | both |
| `key_findings` | `list[str]` | replace | MM body sections |
| `methods_summary` | string | replace | rare |
| `limitations` | `list[str]` | replace | rare |

(`id`, `type`, `title`, `ontology_terms` are inherited from the base and don't need re-declaration in the mixin; `ontology_terms` keeps base's `append`.)

**Base-field overrides** in the mixin (set the mixin's `science:merge` annotation to override base's default):

| Field | Base policy | Mixin override | Why |
|---|---|---|---|
| `created` | replace (default) | **project_only** | Canonical `created` = first promote time; overlay `created` = project's first write. The two values mean different things, and per-project views want the project's value. `project_only` makes the merge use the overlay's value while keeping the canonical's value intact for the commons-view. |
| `updated` | replace (default) | **project_only** | Same reasoning as `created`. |
| `status` | replace (default) | **project_only** | Per-project status (active / archived / wip) is a project lens, not a property of the paper. Canonical's `status` is omitted (base doesn't require it). |

**Fields NOT overridden in the mixin:**
- `tags` keeps base's `append` policy. The behavior we want — each project's view shows only that project's tags — is achieved by promote always writing canonical `tags: []` (or omitting the field), so the merge `canonical.tags + overlay.tags = overlay.tags`. This is `project_only`-equivalent without overriding the policy. See §4.1.2.
- `version` keeps base's `forbidden` policy (overlay must not override; promote sets canonical version from the semver tag).

### 4.1.1 Canonical-required base fields — what promote generates

For each promoted paper, the canonical file carries these base-required values, generated by promote:

| Field | Value source |
|---|---|
| `schema_profile` | `"science-entity-base/1.0+paper/2.0"` (built via `default_profile_for_kind("paper").render()`) |
| `version` | `"1.0.0"` on a first promote; bumped on each re-promote (semver minor on field changes, patch on body-only changes) |
| `created` | UTC date of first promote |
| `updated` | UTC date of this promote run |
| `id`, `type`, `title` | from the source paper |

On the overlay, `created` / `updated` carry the project's original values (preserved verbatim from the pre-rewrite file), and `version` is **not** written (overlay schema doesn't declare it). `schema_profile` is also **not** written on overlays (see §4.4).

### 4.1.2 `tags` behavior — canonical empty, overlay carries the value

Promote always writes canonical paper files with `tags: []` (or omits the field entirely; the loader treats both the same). The overlay carries the project's `tags` list. The base's `tags: append` annotation then produces `[] + overlay_tags = overlay_tags` in per-project merge views — each project sees only its own tags. There is no cross-project tag union: the merge is per-project (one overlay at a time), and the canonical contributes nothing.

This is functionally what we want from "tags as project-only metadata," achieved within the existing append semantics rather than by overriding the policy. The cost is one always-empty field on the canonical; the benefit is that the rule lives in one place (promote's writer) rather than at every reader.

### 4.2 Author coercion

Source frontmatter sometimes carries a string `authors: "Wang et al."` (MM) and sometimes a list (`authors: [Wang, Smith, Lee]`). The 2.0 schema requires `list[str]`. Coercion rule: **wrap a non-list value as a single-element list** (`["Wang et al."]`); do NOT attempt to parse a comma-separated string into individual names. String parsing is fragile (commas in "Smith, J. Jr.", localization, "et al."), and a single-element list preserves the original text losslessly. A surface that wants individual author names can be improved by hand later.

**Field rename:** `journal` → `venue`. The 1.0 mixin used `journal`; the field name in the wild is `venue`. 1.0 has no strict consumers, so the rename is the cleanest move. The promote tool reads `venue` from the source frontmatter; if a source happens to carry `journal`, it is coerced to `venue` with a one-time warning in the dry-run summary.

### 4.3 Body sections

JSON Schema has no good slot for prose-section semantics, so the body classification lives in a top-level annotation on the **mixin**:

```json
"x-canonical-body-sections": [
  "Key Findings",
  "Methods Summary",
  "Limitations",
  "Summary",
  "One-Sentence Summary"
]
```

Read via a thin helper `read_canonical_body_sections(profile: ProfileString) -> list[str]` added to `science_model.entity_schema.merge` alongside the existing `read_merge_policy`. Headings are matched case-insensitively and after stripping leading `## `; subheadings (`###`) are out of scope.

Anything not on this list (e.g., `## Project Use`, `## Relevance`, `## Notes`, untitled prose) is project-only body and stays on the overlay.

### 4.4 `overlay-1.1.json` — project-only paper fields + relaxed id regex

The current `overlay-1.0.json` has `additionalProperties: false` and only declares overlay-management fields (`relevance`, `hypothesis_links`, `project_tags`, plus the always-appended `tags` / `ontology_terms`). Rewriting a project paper file as a 1.0 overlay would drop `status`, `source`, `related`, `source_refs`, `created`, `updated` on the floor at validation time. `overlay-1.1` is a minor bump adding the missing fields as named properties (each defaulting to `merge: project_only`, which is `read_overlay_merge_policy`'s default for un-annotated fields) and relaxing the canonical id regex to permit hyphens.

Changes vs 1.0 (all additive):

- **`canonicalId` regex.** The `paper:` arm becomes `^paper:[A-Za-z][A-Za-z0-9-]{1,63}$`. Datasets, topics, themes already use a hyphen-permissive regex and are unchanged. This is the same change as §4.1's `bibkey` regex relaxation, applied on the id-reference side.
- **New properties** (all optional, default merge policy is `project_only` per `read_overlay_merge_policy`):
  - `status: string` — `## Status` lifecycle on the project file (NS convention).
  - `source: string` — provenance marker, e.g. `"web search + LLM knowledge"` (MM convention).
  - `related: list[str]` — project-internal cross-refs to questions / hypotheses / concepts.
  - `source_refs: list[str]` — secondary citation refs (NS convention).
  - `created: date`, `updated: date` — project-side metadata.
- **`additionalProperties` stays `false`.** Strictness is a feature; we add named fields, we don't open the door.

**Loader and validator updates** — three small, coordinated changes:

- `read_overlay_merge_policy` currently loads `ProfileComponent(name="overlay", version="1.0")` (hardcoded in `merge.py:37`). The version literal bumps to `"1.1"`.
- `EntitySchemaValidator.validate_overlay` currently hardcodes `ProfileComponent(name="overlay", version="1.0")` (`validator.py:65`). The version literal bumps to `"1.1"`. The validator stays "hardcoded version" — it never reads a per-file profile field.
- The `parse_profile`-based profile-string surface is **not** touched: `parse_profile` accepts only the type mixins `{dataset, paper, topic, theme}` (`profile.py:16`), and "overlay" is deliberately not in that set. Overlays do not become first-class parsed profile components in Phase E.

**Promote does NOT emit `schema_profile:` on rewritten overlays.** The validator's hardcoded version is the single source of truth for overlay schema selection; an emitted `schema_profile` would be either ignored (current validator behavior) or, if naively passed to `parse_profile`, would raise. The earlier draft proposed `schema_profile: science-entity-base/1.0+overlay/1.1`; that is incompatible with the profile model and is dropped. If overlay versioning ever needs to be per-file (e.g., to support a 1.0/1.1 mix during a future migration), that becomes its own design slice — either a separate `overlay_schema_version:` field with a dedicated reader, or extending `parse_profile` to treat "overlay" as a fourth special component.

The `overlay-1.0.json` file stays in tree for the small number of overlay fixtures that pin 1.0 explicitly; new overlays written by promote validate against 1.1 via the hardcoded path above.

### 4.5 Profile string

A new helper `default_profile_for_kind(kind: str) -> ProfileString` (in `science_model.entity_schema.profile`) returns the **parsed** full profile string for a kind — e.g. `default_profile_for_kind("paper")` returns `parse_profile("science-entity-base/1.0+paper/2.0")`. The promote tool and tests use this helper rather than constructing raw strings; tests call `read_merge_policy(default_profile_for_kind("paper"))`.

The existing `core_entity_type_for_kind(kind) -> EntityType | None` (in `entities.py`) is unrelated to profile-string resolution and is NOT modified. It returns the typed-entity projection (e.g. `EntityType.PAPER`); profile strings are a separate concept.

## 5. Promote module: `science_tool/commons/promote.py`

### 5.1 Public surface

Exported from `commons/__init__.py`:

```python
@dataclass(frozen=True, slots=True)
class PromoteCandidate:
    bibkey: str                          # normalized, lowercase
    project_slug: str                    # registered project id
    project_root: Path
    overlay_source_path: Path            # the existing project paper file
    canonical_fields: dict[str, Any]
    project_only_fields: dict[str, Any]
    canonical_body: dict[str, str]       # heading → body text
    project_only_body: dict[str, str]

@dataclass(frozen=True, slots=True)
class FieldConflict:
    bibkey: str
    field: str
    candidates: dict[str, Any]           # project_slug → value

@dataclass(frozen=True, slots=True)
class ConflictResolution:
    bibkey: str
    field: str
    candidates: dict[str, Any]
    resolved_to: Any
    source_project: str | None           # None if user entered a manual value

@dataclass(frozen=True, slots=True)
class OverlayRewrite:
    project_slug: str
    path: Path
    before_sha: str
    after_content: str
    pin_version: str

@dataclass(frozen=True, slots=True)
class PromoteDecision:
    bibkey: str
    canonical_entity: Entity             # what gets written to <commons>/papers/<bibkey>.md
    canonical_version: str               # semver tag suffix (1.0.0 for a first promote)
    overlays: dict[str, OverlayRewrite]  # project_slug → rewrite plan
    resolved_conflicts: list[ConflictResolution]

@dataclass(frozen=True, slots=True)
class FailedCandidate:
    bibkey: str | None                   # None if normalization itself failed
    project_slug: str
    source_path: Path
    error_class: str                     # "PromoteCandidateError" etc.
    error_message: str

@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates_by_bibkey: dict[str, list[PromoteCandidate]]
    failed_candidates: list[FailedCandidate]   # parse / kind failures encountered during scan

@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]   # discovery failures + any plan-time soft failures

@dataclass(frozen=True, slots=True)
class PromoteResult:
    op_id: str
    started_at: datetime
    finished_at: datetime
    commons_commit: str | None           # None on pre-commit failure
    tags_created: list[str]              # "paper/<bibkey>/<semver>"
    decisions: list[PromoteDecision]     # what was (or would have been) applied
    failed_candidates: list[FailedCandidate]   # carried from plan, surfaced in audit log
    audit_log_path: Path | None          # None on failure-before-audit-write
    status: Literal["ok", "failed"]
    failure_stage: Literal["preflight", "validate", "discover", "plan", "write_commons", "rewrite_projects", "audit"] | None
    failure_detail: str | None

def discover_paper_candidates(
    project_slugs: list[str],
) -> DiscoveryResult:
    """Scan each project's `<project_root>/doc/papers/*.md` directly (not via
    `build_inventory` — see §5.3 for why). For each file: parse frontmatter,
    skip if `overlay_of:` present (already promoted), skip with a logger warning
    if kind/type ≠ "paper", construct a PromoteCandidate otherwise. Parse failures
    are wrapped as FailedCandidate, never raised. Returns candidates grouped by
    normalized bibkey plus the failure list."""

def plan_promote(
    discovery: DiscoveryResult,
    commons_root: Path,
    *,
    resolve_conflict: Callable[[FieldConflict], Any] = prompt_resolve,
) -> PromotePlan:
    """Apply merge-policy classification + auto-union + conflict resolution.
    `discovery.failed_candidates` is carried into `plan.failed_candidates` and
    extended with any plan-time soft failures. Pure modulo the resolver callback.
    One decision per bibkey."""

def apply_promote(
    plan: PromotePlan,
    commons_root: Path,
    *,
    invocation: str,                     # for the audit log
) -> PromoteResult:
    """Atomic batch write per Approach A. See §6.4 for failure handling.
    `plan.failed_candidates` is carried through verbatim to `result.failed_candidates`
    and surfaced in the audit log; apply never re-discovers."""
```

### 5.2 Internal helpers (not exported)

- `_scan_project_papers(project_root: Path, project_slug: str) -> tuple[list[PromoteCandidate], list[FailedCandidate]]` — walks `<project_root>/doc/papers/*.md`, parses frontmatter, classifies each file. Per-file failure (parse error, schema-failing frontmatter, malformed `id`) produces a `FailedCandidate`; the walk continues.
- `_parse_paper_file(path: Path) -> tuple[dict, str]` — frontmatter + body split. Raises `PromoteCandidateError` on parse failure; callers wrap to `FailedCandidate`.
- `_classify_entity(frontmatter, body, merge_policy, canonical_body_sections) -> (canonical_fields, project_only_fields, canonical_body, project_only_body)` — single-file classifier.
- `_merge_canonical_fields(candidates, merge_policy) -> (canonical_dict, conflicts)` — auto-union for replace fields when one-sided or identical; produces `FieldConflict` only on differing values. Append fields union deterministically (sorted, deduped).
- `_render_canonical(decision) -> str` — markdown writer for the commons surface file.
- `_render_overlay(decision, project_slug) -> str` — markdown writer for the rewritten project file.
- `_write_audit_log(result, commons_root) -> Path` — YAML writer for the `.migrations/` entry.
- `_normalize_bibkey(raw: str) -> str` — strips `.md`, lowercases; rejects empty / whitespace / regex-failing strings with `PromoteCandidateError`.

### 5.3 Dependencies

The module imports from:
- `science_tool.commons.config` (`resolve_commons_root`, plus a **new** `resolve_project_by_id` helper — see below).
- `science_tool.commons.adapter` — only to short-circuit on already-promoted bibkeys (commons-side existence check).
- `science_model.entity_schema` (`read_merge_policy`, `read_canonical_body_sections`, `default_profile_for_kind`, `MergePolicy`).
- A minimal YAML frontmatter splitter (likely the existing one in `science_tool.graph.sources` or a small local helper — see below).

**New helper: `resolve_project_by_id(project_id: str) -> Path`** (added to `science_tool/commons/config.py`). The existing `resolve_project_root(name)` matches on `project.name`, which is the legacy human-readable name (e.g. `"natural-systems-guide"`). Phase B introduced a separate `id:` field (e.g. `"natural-systems"`), and promote's `--from` contract is **id-based**, not name-based. The new helper:

1. Loads the global config via `load_global_config`.
2. Iterates `cfg.projects` looking for an entry whose `id` equals `project_id` AND whose `id` is non-null.
3. Returns the entry's path (expanded `~`); raises `PromoteInputError` if no match, with a message that distinguishes "no such id" (typo) from "id is null" (legacy registration — point the user at deregistering or assigning an id).

`resolve_project_root(name)` is left alone for any callers that still match by name.

It does NOT import from `science_tool.entities_inventory`. `build_inventory` was an attractive reuse target but is the wrong tool for promote: it delegates to `load_project_sources`, which raises hard `ValueError`s on malformed core entities (`sources.py:257`) and silently drops files missing identity markdown with only a logger warning (`sources.py:262`). Promote needs **structured per-file failure objects** so the audit log and dry-run can name each bad file; turning the inventory's mix of raise/warn/skip into that shape is messier than scanning `doc/papers/*.md` directly. Direct scan also keeps promote's discovery independent of inventory contract churn.

If the frontmatter splitter currently used by `load_project_sources` is suitable, promote reuses it via a narrow import; otherwise promote defines `_parse_paper_file` locally using the standard YAML reader. Either way, no `build_inventory` dependency.

The module does NOT import from the dashboard or from `science_tool.graph` (beyond a possible frontmatter helper).

## 6. Data flow

### 6.1 CLI surface

Under `commons_group`:

```
science commons promote paper <paper:bibkey> --from <slug> [--apply]
science commons promote paper --from <slug>... [--apply] [--limit N]
```

- **`--from <slug>`** is required and repeatable. Slugs resolve via `resolve_project_by_id` (§5.3) — they MUST match a registered project's `id:` (the Phase B registry field), not `name:`. Registrations with `id: null` (legacy entries) are rejected with a clear message — the user fixes the registry first. This sidesteps content-identical legacy registrations (`r/mm30` vs `multiple-myeloma`) mechanically: only one of them carries an `id`.
- **Single-entity form** (`promote paper <paper:bibkey>`) accepts exactly one `--from`. Surgical, not bulk; the user must drop into bulk form to dedup across projects.
- **Bulk form** discovers all paper candidates across the `--from` set, groups by normalized bibkey, runs plan + apply.
- **`--limit N`** (bulk only) stops after N papers in deterministic (bibkey-sorted) order; the rest are reported but not planned. Lets a 503-paper pilot be incrementally exercised.
- **Dry-run is the default**; `--apply` is required to write. **Dry-run prompts on conflicts** — the resolver callback is the same in dry-run and `--apply`. This is the only way for dry-run to produce a faithful preview of the apply (and to surface conflicts to the user without forcing a write). The cost is that a no-attention dry-run hangs at the first conflict; `--limit 0` produces a discovery-only summary with no prompts for that case.
- Both forms refuse to run if `<commons_root>` is missing; the error message points the user at `science commons init`.
- Both forms refuse to run if any **target file** (commons-side `papers/<bibkey>.md` for each in-plan bibkey, or any project's `doc/papers/<bibkey>.md` slated for rewrite) has uncommitted changes, OR if the containing repo is in a merge / rebase / cherry-pick state. See §6.3 step 0 — this preflight check is what protects user work from `git checkout HEAD --` rollbacks.

### 6.2 Sample dry-run output (abbreviated)

```
$ science commons promote paper --from natural-systems --from multiple-myeloma --from cancer-meta
Discovered 334 paper candidates across 3 projects (NS 17 + MM 232 + cancer-meta 85).
  • 325 single-instance (auto-promote)
  • 9 multi-instance (dedup)
    huh2024:    2 instances — auto-merge (no field conflicts)
    dang2023:   2 instances — 1 conflict (year)
      [prompting here in both dry-run and --apply]
Conflict for paper:dang2023, field "year":
  [1] natural-systems:  2023
  [2] multiple-myeloma: 2024
  [3] enter value manually
  [a] abort batch
Choose [1/2/3/a]: 1
  ...
Preflight (target paths only): 334 commons-side + 334 project-side files clean,
  3 project repos and 1 commons repo not mid-merge/rebase. ✓
Would create:
  • 334 commons entities at ~/d/science-commons/papers/<bibkey>.md
  • 1 commons commit, 334 tags
  • 334 project file rewrites
  • 1 audit log: ~/d/science-commons/.migrations/20260515T143011Z-7a3f2c91.yaml
Failed candidates: 0

Re-run with --apply to execute.
```

Note the ordering: discovery and planning come first because the preflight check needs the in-plan target set to decide which files matter (any file outside the in-plan set may be dirty without blocking). §6.3 step 0 codifies this — "step 0" is its label for being the gate before any write, not for running first chronologically.

### 6.3 Apply steps

0. **Preflight cleanliness check** — for every repo that will be touched (the commons store and each `--from` project), require that:
   - The working tree has **no uncommitted changes** to any in-plan target file (commons-side `<commons>/papers/<bibkey>.md` for each bibkey in the plan, and project-side `doc/papers/<bibkey>.md` for each candidate). Files outside the in-plan set may be dirty without blocking — promote never touches them.
   - The repo is NOT in a merge / rebase / cherry-pick / bisect state.
   The check runs **after** discovery (step 2) and **after** the plan is built (step 3), because the in-plan target set is only known then. If any target file is dirty or any repo is mid-operation, the run aborts with a `PromoteInputError` listing every offending path; nothing has been written. This is what makes the §6.4 `git checkout HEAD --` rollback safe.
1. **Validate inputs** — every `--from` slug resolves to a non-null registered id; `<commons_root>` exists.
2. **Discover** — for each project, walk `<project_root>/doc/papers/*.md` directly via `_scan_project_papers` (NOT `build_inventory` — see §5.3). For each file: split frontmatter; if `overlay_of:` is present, skip (idempotency); if `kind`/`type` ≠ `"paper"`, log a warning and skip; otherwise construct a `PromoteCandidate`. A per-file parse failure or schema-failing frontmatter produces a `FailedCandidate` for that path, recorded in `DiscoveryResult.failed_candidates`; the walk continues. Group surviving candidates by normalized bibkey.
3. **Plan** — for each bibkey group, run `plan_promote`. Conflicts fire prompts here, before any disk write. User Ctrl-C → `PromoteConflictAbort`, nothing on disk has changed yet.
4. **Write commons (staged)** — for each decision, write canonical `papers/<bibkey>.md` into the commons working tree.
5. **Commit + tag** — `git -C <commons> add papers/ && git commit -m "promote: N papers via op <op-id>"`; for each decision, `git -C <commons> tag paper/<bibkey>/<semver>`. All tags point at the single batch commit.
6. **Rewrite projects** — for each project, rewrite each overlay file in place. **Project commits are NOT made by `promote`** — the user reviews + commits per project. The audit log records the suggested commit command (§6.5).
7. **Write audit log** — final step on the success path. Written to `<commons>/.migrations/<op-id>.yaml` and committed to commons in a follow-up commit (`audit: op <op-id>`). The log carries `failed_candidates` from the plan so the user sees soft failures alongside successes.

   On the failure path (any failure at steps 0–6), the same log file is written **best-effort, uncommitted**, with `status: failed`, `failure_stage:` set, and whatever partial state is known (commons commit hash if step 5 landed, list of projects whose rewrites were rolled back, etc.). The CLI surfaces the log path in the error message. If even the best-effort log write fails (disk full, permissions), the CLI prints the would-have-been log content to stderr instead. The user can `git add .migrations/<op-id>.yaml && git commit` afterwards if they want the failed-run log versioned.

### 6.4 Failure handling

The preflight check at step 0 is what makes `git checkout HEAD --` safe to use on rollback: by that point every target file is known to match HEAD, so `checkout HEAD -- <path>` restores exactly the pre-promote content. Without preflight, a `checkout` could discard pre-existing uncommitted user edits.

- **Step 0 (preflight) failure** — nothing on disk has been touched. Result: `status: failed`, `failure_stage: "preflight"`. The best-effort audit log lists the dirty paths so the user knows what to clean / stash. No commons or project rollback needed.
- **Before step 5 (commons commit)** — any failure means nothing committed: `git -C <commons> checkout -- papers/` resets the staged files (safe because step 0 verified `papers/<bibkey>.md` targets were clean); no project files were touched. Result: `status: failed`, `failure_stage: "validate" | "discover" | "plan" | "write_commons"`.
- **After step 5, mid-step 6** — commons commit is durable. Touched project files are rolled back via `git -C <project> checkout HEAD -- <paths>` for each project that has any rewrite. The user is left with a commons commit and clean project trees. Result: `status: failed`, `failure_stage: "rewrite_projects"`. The audit log records the commons commit hash and the partial-rewrite list for forensics. Recovery is **manual and explicit**: the user reverts the commons commit (`git -C <commons> revert <hash>`) to restore disk-wide consistency, then re-runs `--apply` with the issue (typically a project's dirty working tree) resolved. The audit log's `rollback:` block is the documented procedure. This is the only failure mode where the on-disk state is not self-consistent — keeping recovery manual avoids encoding subtle "partial promote resume" logic that would be exercised only on rare failures.
- **After step 6, mid-step 7** — extremely unlikely (writing one YAML file), but if the audit-log commit fails, the audit log path exists on disk uncommitted; everything else is fine. Result: `status: failed`, `failure_stage: "audit"`. Manual recovery: `git -C <commons> add .migrations/ && git commit -m "audit: op <op-id>"`.

`PromoteWriteError` carries `failure_stage` so callers (CLI, tests) can branch.

### 6.5 Audit log format

Path: `<commons_root>/.migrations/<UTC-YYYYMMDDTHHMMSSZ>-<op-id>.yaml`. `op-id` is the short hex of a random 32-bit value.

```yaml
op_id: 7a3f2c91
type: paper
invocation: "science commons promote paper --from natural-systems --from multiple-myeloma --apply"
status: ok
started_at: 2026-05-15T14:30:11Z
finished_at: 2026-05-15T14:30:47Z
commons_commit: "8f9a1b2"
commons_tags:
  - paper/kornblith2019/1.0.0
  - paper/liu2024/1.0.0
  # ...
projects_touched:
  natural-systems:
    overlay_rewrites:
      - bibkey: kornblith2019
        path: ~/d/natural-systems/doc/papers/Kornblith2019.md
        before_sha: "a1b2c3d"
        after_sha: "e5f6789"
        pin_version: "1.0.0"
    project_commit_hint: "cd ~/d/natural-systems && git add doc/papers/ && git commit -m 'promote papers to commons'"
  multiple-myeloma: { ... }
conflict_resolutions:
  - bibkey: dang2023
    field: year
    candidates: { natural-systems: 2023, multiple-myeloma: 2024 }
    resolved_to: 2023
    source_project: natural-systems
failed_candidates:
  - bibkey: malformedpaper2022
    project_slug: cancer-meta
    source_path: ~/d/cancer/meta/doc/papers/malformedpaper2022.md
    error_class: PromoteCandidateError
    error_message: "frontmatter parse error at line 7: unexpected token"
rollback:
  commons: "git -C ~/d/science-commons revert 8f9a1b2"
  projects:
    natural-systems: "git -C ~/d/natural-systems checkout HEAD -- doc/papers/Kornblith2019.md ..."
    multiple-myeloma: "..."
```

The `rollback:` block is **documentation, not script** — the values are exact commands the user can copy. No `science promote rollback` command is shipped in Phase E (see §2 out-of-scope).

**Failure-path variant.** On any failure (preflight, discovery, plan, write, audit), the same file is written best-effort (uncommitted) with `status: failed`, a populated `failure_stage:` and `failure_detail:`, `commons_commit:` either `null` or the short sha if step 5 landed, and `projects_touched:` reflecting whatever was rolled back. The `failed_candidates:` block always reflects discovery-time soft failures regardless of overall status.

## 7. Error model

New classes in `commons/errors.py`, under `CommonsError`:

```python
class PromoteInputError(CommonsError):
    """--from slug missing/unregistered/null-id; commons store missing; required arg absent."""

class PromoteCandidateError(CommonsError):
    """A paper file is malformed (parse error in frontmatter, unreadable, schema-failing).
    Constructed per-candidate; the bibkey + path are named in the message. NOT raised
    out of `discover_paper_candidates` — instead it is wrapped as a `FailedCandidate`
    in the plan, so a single bad file doesn't abort discovery. Raised directly only by
    `apply_promote` if an in-plan decision turns out to be unparseable at write time
    (file deleted between plan and apply); that's a hard-stop case."""

class PromoteConflictAbort(CommonsError):
    """User aborted at a conflict prompt (Ctrl-C, or 'abort' answer).
    Batch stops cleanly before any commons or project write."""

class PromoteWriteError(CommonsError):
    """IO/git failure during steps 4–7. Carries failure_stage + partial-state info."""
    def __init__(self, *, stage: str, detail: str,
                 commons_commit: str | None = None,
                 projects_touched: list[str] | None = None) -> None: ...
```

`PromoteInputError`, `PromoteConflictAbort`, and `PromoteWriteError` are hard-stop. `PromoteCandidateError` is the only soft-failure path: at discovery it's wrapped as a `FailedCandidate` and the batch proceeds with the rest; the user sees the failure list in dry-run and decides whether to fix and re-run. Anywhere else (e.g., apply-time write of an in-plan decision), `PromoteCandidateError` is raised directly and aborts the batch.

### 7.1 Conflict prompt UX

```
Conflict for paper:dang2023, field "year":
  [1] natural-systems:  2023
  [2] multiple-myeloma: 2024
  [3] enter value manually
  [a] abort batch
Choose [1/2/3/a]:
```

The resolver callback (`resolve_conflict` parameter on `plan_promote`) defaults to `prompt_resolve` (the interactive prompt above) but is injectable for tests. Tests supply a deterministic callback that returns a fixed answer per `FieldConflict`.

## 8. Testing strategy

Per-module unit tests + fixture-driven end-to-end tests, all under `science/tests/`:

| File | Coverage |
|---|---|
| `test_entity_schema_mixin_paper.py` (extend) | 2.0 schema validates against fixture papers from both project styles; canonical entities carry the base-required `schema_profile` / `version` / `created` / `updated`; `read_merge_policy(default_profile_for_kind("paper"))` returns the documented classification AND shows the mixin's `created` / `updated` / `status` overrides winning over base's defaults (via last-wins composition); `read_merge_policy` reports `tags: append` from base (mixin does NOT override); `read_canonical_body_sections(default_profile_for_kind("paper"))` returns the documented heading list; `journal` → `venue` rename surfaces a deprecation warning when 1.0 papers are read through the 2.0 reader |
| `test_entity_schema_overlay.py` (new or extend) | 1.1 schema validates overlays carrying `status`, `source`, `related`, `source_refs`, `created`, `updated`; `additionalProperties: false` still rejects unknown fields; `read_overlay_merge_policy()` returns `project_only` for the new fields and keeps `append` for `tags` / `ontology_terms`; the relaxed `canonicalId` regex accepts hyphenated paper ids |
| `test_commons_promote_discovery.py` (new) | direct `doc/papers/*.md` walk across N projects; group-by normalized bibkey; `resolve_project_by_id` matches `.id` (not `.name`), rejects null-id entries with a clear message, rejects unregistered ids with a different message; skip files with `overlay_of:` set (already promoted); skip files whose `kind`/`type` ≠ `"paper"` with a warning; per-file parse failure / schema-failing frontmatter produces a `FailedCandidate` and does not abort discovery; `DiscoveryResult.failed_candidates` flows into `PromotePlan.failed_candidates` |
| `test_commons_promote_plan.py` (new) | classification places only canonical fields on the canonical entity (project-only fields never appear); auto-union on disjoint canonical fields; auto-union on identical values; `FieldConflict` raised on differing values; resolver callback is honored; body-section split respects `x-canonical-body-sections`; append fields union deterministically; `failed_candidates` carried into the plan |
| `test_commons_promote_apply.py` (new) | preflight blocks dirty target files with a `PromoteInputError` naming them; preflight allows dirty non-target files; canonical paper files include `schema_profile`, `version`, `created`, `updated` set by promote; canonical paper files always carry `tags: []` (or no tags field); single commit + N tags pointing at it; project file rewrites with pin to tagged version; rewritten overlays validate against `overlay-1.1`; rewritten overlays preserve the project's original `created` / `updated`; audit log shape (success path: committed; failure path: best-effort uncommitted); **failure-mid-rewrite rolls back project files but leaves commons commit**; **failure-before-commit leaves nothing on disk**; idempotent re-apply (an already-overlayed file is skipped, no-op); `failed_candidates` surfaces in the audit log |
| `test_commons_cli_promote.py` (new) | dry-run output format including conflict prompts and failed-candidates summary; `--apply` end-to-end happy path; `--limit`; `--limit 0` produces discovery-only output with no prompts; null-id slug → non-zero exit with clear message; missing commons → non-zero exit; dirty target file → non-zero exit with preflight diagnostic; conflict + interactive resolver via test-injected callback; single-entity form vs bulk form path divergence |
| `tests/fixtures/promote/` (new) | minimal commons store seed; two synthetic projects with 4 papers each (2 single-instance, 2 cross-project dupes — one auto-mergeable, one with a real `year` conflict). Doubles as the dev bed for the dedup flow |

**Pilot run is NOT in the automated suite.** The synthetic fixtures cover the algorithm; the actual five-project pilot is a manual operational step after merge, documented separately in the implementation plan's roll-out section.

The full `science` suite and the `science_model` suite must stay green.

## 9. Deliverables checklist

1. `science_model/schemas/mixin-paper-2.0.json` — canonical paper fields + `merge:` annotations + `x-canonical-body-sections`.
2. `science_model/schemas/overlay-1.1.json` — adds `status`, `source`, `related`, `source_refs`, `created`, `updated` as named properties (default `merge: project_only` via `read_overlay_merge_policy`); relaxes `canonicalId` paper regex to permit hyphens.
3. `science_model/entity_schema/merge.py` — `read_canonical_body_sections(profile)` helper; bumps the loader's hardcoded overlay component to `1.1`. `science_model/entity_schema/validator.py` — bumps `validate_overlay`'s hardcoded overlay component to `1.1` (matching change; both must move together).
4. `science_model/entity_schema/profile.py` — `default_profile_for_kind(kind: str) -> ProfileString` helper.
5. `science_model/entity_schema/__init__.py` — export new helpers.
6. `science_tool/commons/promote.py` — module per §5.
7. `science_tool/commons/errors.py` — four new error classes.
8. `science_tool/commons/cli.py` — `promote paper` subgroup.
9. `science_tool/commons/__init__.py` — public surface exports (incl. `FailedCandidate`, `DiscoveryResult`, `PromotePlan`, `PromoteResult`).
10. `science_tool/commons/config.py` — new `resolve_project_by_id(project_id) -> Path` helper (id-based registry lookup, rejects null-id and unregistered entries).
11. Test files (five new) + extension of `test_entity_schema_overlay*` for 1.1 + fixtures per §8.

## 10. Follow-on phases

- **Phase F — Promote: topics, themes.** Same architecture, sibling modules / schemas. Likely simpler than papers (no body-section nuance, less frontmatter variance).
- **Phase G — Promote: datasets.** Adds hash recomputation, descriptor relocation, per-machine override management; large enough to warrant its own design slice.
- **Phase H — Bio extensions.** RNA-seq / scRNA-seq / CNA mixin schemas applied to promoted datasets.
- **Followup: `science promote rollback <op-id>`.** Becomes worthwhile if the documented manual procedure proves error-prone in practice.
- **Followup: BibTeX integration.** `references.bib` becomes a third merge source alongside frontmatter, with conflict resolution against it.
