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

- **Canonical surface** (commons-side `papers/<bibkey>.md`): the paper's shared facts — title, authors, year, venue, DOI/PMID, ontology terms, dataset references, key findings, methods summary, limitations.
- **Project overlay** (project-side `doc/papers/<bibkey>.md`, rewritten in place): `id`, `overlay_of: paper:<bibkey>`, `pin_version: <tagged semver>`, plus project-only fields (`tags`, `related`, `source_refs`, `status`, `source`, `created`, `updated`) and project-only body sections (`## Project Use`, `## Relevance`, free prose).

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

1. **Schema extension (`science_model`)** — `mixin-paper-2.0.json` becomes the canonical paper profile. The existing `read_merge_policy(profile_string)` reads the new annotations; nothing in the overlay-merge pipeline (Phase D1) or `inventory_v2` builder (Phase D2) needs to change. `core_entity_type_for_kind("paper")` returns `paper/2.0`.
2. **Promote module (`science_tool/commons/promote.py`)** — sibling of `resolver.py` / `overlay.py`, owning discovery / dedup / classification / write. Atomic-batch transaction semantics: one `--apply` produces one commons commit, N entity tags pointing at it, N project file rewrites, one `.migrations/` audit entry. Dry-run is the default.

Project-side scanning **reuses** `inventory_v2` per registered project (no new file walking). The classifier reads the new merge policy from the schema; conflict resolution prompts use the terminal idioms (`click.prompt`) already established in the Phase B `commons` CLI.

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

science/model/src/science_model/entities.py
                                # MODIFIED — `default_profile_for_kind` consumer; bumps the
                                #            commons-side `schema_profile` for promoted papers
                                #            to `science-entity-base/1.0+paper/2.0`. `core_entity_type_for_kind`
                                #            keeps its existing `EntityType | None` shape — it is
                                #            unrelated to profile-string resolution.

science/src/science_tool/commons/
├── promote.py                  # NEW — discovery, plan, apply
├── cli.py                      # MODIFIED — `promote paper` subgroup
├── errors.py                   # MODIFIED — four new error classes
└── __init__.py                 # MODIFIED — export PromoteCandidate / Decision / FailedCandidate / Result + discover/plan/apply

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

### 4.1 `mixin-paper-2.0` — canonical fields only

The mixin declares ONLY the canonical paper surface — fields that live on the commons-side `papers/<bibkey>.md`. Project-only fields (`tags`, `status`, `source`, `related`, `source_refs`, `created`, `updated`) move to the overlay schema (§4.4); they never appear on the canonical surface and so do not need a `project_only` annotation on the mixin. (Declaring them with `project_only` on the mixin would also fail to change overlay-side behavior, since the merge engine reads canonical vs overlay policies from *different* schemas — `read_merge_policy` from the mixin, `read_overlay_merge_policy` from the overlay schema. Putting project-only fields on the overlay is the only place that actually wires the behavior.)

| Field | Type | Merge policy (on canonical) | Source today |
|---|---|---|---|
| `id` | `paper:<bibkey>` | (identity) | both projects |
| `type` | `"paper"` | (identity) | both |
| `bibkey` | string (`[A-Za-z][A-Za-z0-9-]{1,63}`, hyphens permitted) | replace | derived from `id` |
| `title` | string | replace | both |
| `authors` | `list[str]` | replace | MM (string → single-element list; see §4.2) |
| `year` | int | replace | MM |
| `venue` | string | replace | MM (renamed from `journal` in 1.0) |
| `doi` | string | replace | MM |
| `pmid` | string | replace | MM |
| `url` | string | replace | rare |
| `ontology_terms` | `list[str]` | **append** | both |
| `datasets` | `list["dataset:<slug>"]` | **append** | both |
| `key_findings` | `list[str]` | replace | MM body sections |
| `methods_summary` | string | replace | rare |
| `limitations` | `list[str]` | replace | rare |

`bibkey` regex permits hyphens (2.0 change vs 1.0's `[A-Za-z0-9]` only). At least one real paper carries a hyphenated bibkey (`categorical-composition-trio-2023-2025`); excluding it would mean renaming source files. `bibkey:` is a derived canonical field (always equal to the suffix of `id:`); it is denormalized onto the surface so consumers can query by bibkey directly without parsing `id`.

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

Loader updates: `read_overlay_merge_policy` already reads from `ProfileComponent(name="overlay", version="1.0")` (hardcoded in `merge.py:37`). That string bumps to `"1.1"`. Phase E tests verify the new fields validate cleanly on real overlay files written by promote.

The `overlay-1.0.json` file stays in tree for the small number of overlay fixtures that pin 1.0 explicitly; new overlays written by promote always declare `schema_profile: science-entity-base/1.0+overlay/1.1` (or omit `schema_profile` and rely on the loader default — but emitting it explicitly is the safer choice).

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
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]   # soft-failed at discovery / classification

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
) -> dict[str, list[PromoteCandidate]]:
    """Scan each project via inventory_v2; group candidates by normalized bibkey.
    Skip files whose frontmatter already has `overlay_of:` (already promoted)."""

def plan_promote(
    candidates_by_bibkey: dict[str, list[PromoteCandidate]],
    commons_root: Path,
    *,
    resolve_conflict: Callable[[FieldConflict], Any] = prompt_resolve,
) -> PromotePlan:
    """Apply merge-policy classification + auto-union + conflict resolution.
    Pure modulo the resolver callback. One decision per bibkey, plus a list of
    soft-failed candidates that couldn't be classified."""

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

- `_classify_entity(entity, merge_policy, canonical_body_sections) -> (canonical_fields, project_only_fields, canonical_body, project_only_body)` — single-file classifier.
- `_merge_canonical_fields(candidates, merge_policy) -> (canonical_dict, conflicts)` — auto-union for replace fields when one-sided or identical; raises conflicts only on differing values. Append fields union deterministically (sorted, deduped).
- `_render_canonical(decision) -> str` — markdown writer for the commons surface file.
- `_render_overlay(decision, project_slug) -> str` — markdown writer for the rewritten project file.
- `_write_audit_log(result, commons_root) -> Path` — YAML writer for the `.migrations/` entry.
- `_normalize_bibkey(raw: str) -> str` — strips `.md`, lowercases; rejects empty / whitespace / non-alphanumeric strings with `PromoteCandidateError`.

### 5.3 Dependencies

The module imports from:
- `science_tool.entities_inventory` (`build_inventory`) — per-project scan.
- `science_tool.commons.config` (`resolve_commons_root`).
- `science_tool.commons.adapter` — only to short-circuit on already-promoted bibkeys.
- `science_model.entity_schema` (`read_merge_policy`, `read_canonical_body_sections`, `MergePolicy`).
- `science_model.contracts.inventory_v2` — for the inventory shape.

It does NOT import from the dashboard, from `science_tool.graph`, or from any project-specific module.

## 6. Data flow

### 6.1 CLI surface

Under `commons_group`:

```
science commons promote paper <paper:bibkey> --from <slug> [--apply]
science commons promote paper --from <slug>... [--apply] [--limit N]
```

- **`--from <slug>`** is required and repeatable. Slugs must resolve to **registered project ids with non-null `id:`** (the Phase B registry field, not `name:`). Registrations with `id: null` (legacy entries) are rejected by name with a clear message — the user fixes the registry first. This sidesteps content-identical legacy registrations (`r/mm30` vs `multiple-myeloma`) mechanically: only one of them carries an `id`.
- **Single-entity form** (`promote paper <paper:bibkey>`) accepts exactly one `--from`. Surgical, not bulk; the user must drop into bulk form to dedup across projects.
- **Bulk form** discovers all paper candidates across the `--from` set, groups by normalized bibkey, runs plan + apply.
- **`--limit N`** (bulk only) stops after N papers in deterministic (bibkey-sorted) order; the rest are reported but not planned. Lets a 503-paper pilot be incrementally exercised.
- **Dry-run is the default**; `--apply` is required to write. **Dry-run prompts on conflicts** — the resolver callback is the same in dry-run and `--apply`. This is the only way for dry-run to produce a faithful preview of the apply (and to surface conflicts to the user without forcing a write). The cost is that a no-attention dry-run hangs at the first conflict; `--limit 0` produces a discovery-only summary with no prompts for that case.
- Both forms refuse to run if `<commons_root>` is missing; the error message points the user at `science commons init`.
- Both forms refuse to run if any **target file** (commons-side `papers/<bibkey>.md` for each in-plan bibkey, or any project's `doc/papers/<bibkey>.md` slated for rewrite) has uncommitted changes, OR if the containing repo is in a merge / rebase / cherry-pick state. See §6.3 step 0 — this preflight check is what protects user work from `git checkout HEAD --` rollbacks.

### 6.2 Sample dry-run output (abbreviated)

```
$ science commons promote paper --from natural-systems --from multiple-myeloma --from cancer-meta
Preflight: 3 project working trees clean, commons working tree clean. ✓
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
Would create:
  • 334 commons entities at ~/d/science-commons/papers/<bibkey>.md
  • 1 commons commit, 334 tags
  • 334 project file rewrites
  • 1 audit log: ~/d/science-commons/.migrations/20260515T143011Z-7a3f2c91.yaml
Failed candidates: 0

Re-run with --apply to execute.
```

### 6.3 Apply steps

0. **Preflight cleanliness check** — for every repo that will be touched (the commons store and each `--from` project), require that:
   - The working tree has **no uncommitted changes** to any in-plan target file (commons-side `<commons>/papers/<bibkey>.md` for each bibkey in the plan, and project-side `doc/papers/<bibkey>.md` for each candidate). Files outside the in-plan set may be dirty without blocking — promote never touches them.
   - The repo is NOT in a merge / rebase / cherry-pick / bisect state.
   The check runs **after** discovery (step 2) and **after** the plan is built (step 3), because the in-plan target set is only known then. If any target file is dirty or any repo is mid-operation, the run aborts with a `PromoteInputError` listing every offending path; nothing has been written. This is what makes the §6.4 `git checkout HEAD --` rollback safe.
1. **Validate inputs** — every `--from` slug resolves to a non-null registered id; `<commons_root>` exists.
2. **Discover** — for each project, `build_inventory(project_root)` → filter `kind == "paper"` → build `PromoteCandidate`. Skip files whose frontmatter has `overlay_of:` (idempotency). A per-candidate parse failure produces a `FailedCandidate` *for that bibkey only*, recorded in the plan's `failed_candidates` list; the batch continues with the rest. Group surviving candidates by normalized bibkey.
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
| `test_entity_schema_mixin_paper.py` (extend) | 2.0 schema validates against fixture papers from both project styles; `read_merge_policy(default_profile_for_kind("paper"))` returns the documented canonical-field classification; `read_canonical_body_sections(default_profile_for_kind("paper"))` returns the documented heading list; `journal` → `venue` rename surfaces a deprecation warning when 1.0 papers are read through the 2.0 reader |
| `test_entity_schema_overlay.py` (new or extend) | 1.1 schema validates overlays carrying `status`, `source`, `related`, `source_refs`, `created`, `updated`; `additionalProperties: false` still rejects unknown fields; `read_overlay_merge_policy()` returns `project_only` for the new fields and keeps `append` for `tags` / `ontology_terms`; the relaxed `canonicalId` regex accepts hyphenated paper ids |
| `test_commons_promote_discovery.py` (new) | discovery across N projects via `inventory_v2`; group-by normalized bibkey; reject null-id `--from`; skip overlay candidates (already promoted); per-candidate parse failure produces a `FailedCandidate` and does not abort discovery |
| `test_commons_promote_plan.py` (new) | classification places only canonical fields on the canonical entity (project-only fields never appear); auto-union on disjoint canonical fields; auto-union on identical values; `FieldConflict` raised on differing values; resolver callback is honored; body-section split respects `x-canonical-body-sections`; append fields union deterministically; `failed_candidates` carried into the plan |
| `test_commons_promote_apply.py` (new) | preflight blocks dirty target files with a `PromoteInputError` naming them; preflight allows dirty non-target files; single commit + N tags pointing at it; project file rewrites with pin to tagged version; rewritten overlays validate against `overlay-1.1`; audit log shape (success path: committed; failure path: best-effort uncommitted); **failure-mid-rewrite rolls back project files but leaves commons commit**; **failure-before-commit leaves nothing on disk**; idempotent re-apply (an already-overlayed file is skipped, no-op); `failed_candidates` surfaces in the audit log |
| `test_commons_cli_promote.py` (new) | dry-run output format including conflict prompts and failed-candidates summary; `--apply` end-to-end happy path; `--limit`; `--limit 0` produces discovery-only output with no prompts; null-id slug → non-zero exit with clear message; missing commons → non-zero exit; dirty target file → non-zero exit with preflight diagnostic; conflict + interactive resolver via test-injected callback; single-entity form vs bulk form path divergence |
| `tests/fixtures/promote/` (new) | minimal commons store seed; two synthetic projects with 4 papers each (2 single-instance, 2 cross-project dupes — one auto-mergeable, one with a real `year` conflict). Doubles as the dev bed for the dedup flow |

**Pilot run is NOT in the automated suite.** The synthetic fixtures cover the algorithm; the actual five-project pilot is a manual operational step after merge, documented separately in the implementation plan's roll-out section.

The full `science` suite and the `science_model` suite must stay green.

## 9. Deliverables checklist

1. `science_model/schemas/mixin-paper-2.0.json` — canonical paper fields + `merge:` annotations + `x-canonical-body-sections`.
2. `science_model/schemas/overlay-1.1.json` — adds `status`, `source`, `related`, `source_refs`, `created`, `updated` as named properties (default `merge: project_only` via `read_overlay_merge_policy`); relaxes `canonicalId` paper regex to permit hyphens.
3. `science_model/entity_schema/merge.py` — `read_canonical_body_sections(profile)` helper; bumps the loader's hardcoded overlay component to `1.1`.
4. `science_model/entity_schema/profile.py` — `default_profile_for_kind(kind: str) -> ProfileString` helper.
5. `science_model/entity_schema/__init__.py` — export new helpers.
6. `science_tool/commons/promote.py` — module per §5.
7. `science_tool/commons/errors.py` — four new error classes.
8. `science_tool/commons/cli.py` — `promote paper` subgroup.
9. `science_tool/commons/__init__.py` — public surface exports (incl. `FailedCandidate`, `PromotePlan`).
10. Test files (five new) + extension of `test_entity_schema_overlay*` for 1.1 + fixtures per §8.

## 10. Follow-on phases

- **Phase F — Promote: topics, themes.** Same architecture, sibling modules / schemas. Likely simpler than papers (no body-section nuance, less frontmatter variance).
- **Phase G — Promote: datasets.** Adds hash recomputation, descriptor relocation, per-machine override management; large enough to warrant its own design slice.
- **Phase H — Bio extensions.** RNA-seq / scRNA-seq / CNA mixin schemas applied to promoted datasets.
- **Followup: `science promote rollback <op-id>`.** Becomes worthwhile if the documented manual procedure proves error-prone in practice.
- **Followup: BibTeX integration.** `references.bib` becomes a third merge source alongside frontmatter, with conflict resolution against it.
