# Commons promote: topics & themes (Phase F) — Design

> **Status:** Design. Captures the brainstorm of 2026-05-16. Implementation plan to follow via `superpowers:writing-plans`.
>
> **Scope:** Phase F of the multi-project roadmap (`docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` §9 Phase F). Adds `science commons promote topic` and `science commons promote theme`, generalising the Phase E `commons/promote.py` module to a kind-pluggable shape.
>
> **Predecessor (must be merged):** Phase E — `commons promote paper` (merged 2026-05-16, head `a61a45d`).

## 1. Goal

Promote topic and theme entities from one or more pilot projects into `~/d/science-commons/`, rewriting each project's source file as a minimal overlay — atomic batch, dry-run by default, reversible. Generalise the Phase E machinery so paper / topic / theme share one code path.

## 2. Motivation & non-goals

### Why generalise rather than copy

Three migration kinds remaining (topic, theme, dataset) each need:

- Discovery walk over a per-kind subdirectory
- Frontmatter parse, classify, group, dedup
- Per-field merge policy (canonical vs. project_only vs. append)
- Per-section body split (canonical vs. project-only)
- Eight-step atomic apply with rollback + audit log

Copying the ~1437-line Phase E module three times produces drift. A kind-pluggable refactor — one module, three kind instances, kind passed as a parameter — keeps the orchestration single-source-of-truth. Phase G (datasets) is significantly larger but reuses the same skeleton with a kind-config covering the `entity.md` + `datapackage.yaml` pair.

### Non-goals

- **Datasets (Phase G).** Single-file entities only; pair-handling logic stays out.
- **Schema fixes for pre-existing mismatches.** Real `mm` themes carry `theme_kind: "biological"` (not in the current enum). All currently-inspected `theme_kind: "biological"` themes are also `theme_scope: "project"`, so they're skipped silently by the eligibility filter and never reach validation in practice. If a future project marks a `theme_kind: "biological"` theme as `theme_scope: "cross-project"`, plan-time validation surfaces the enum mismatch as a `PromoteValidationError` before any I/O. Phase F neither widens the enum nor rewrites project files.
- **Compatibility shims for old function names.** Per the project's "no legacy layers" rule, `discover_paper_candidates` is renamed (or absorbed into a kind-parametric `discover_candidates`) in the same PR — no transitional alias survives merge.

## 3. Architecture

### 3.1 Kind pluggability — `PromoteKindConfig`

Frozen, slotted dataclass; pure data plus one optional callable hook. Composition over inheritance.

```python
@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    kind: Literal["paper", "topic", "theme"]
    source_subdirs: tuple[str, ...]            # paper=("doc/papers",); topic=("doc/topics", "doc/background/topics");
                                               #   theme=("doc/themes",)
    overlay_dest_subdir: str                   # where overlay rewrites land. paper="doc/papers";
                                               #   topic="doc/topics" (flatten background/topics → topics on rewrite);
                                               #   theme="doc/themes"
    commons_subdir: str                        # "papers"     | "topics"     | "themes"
    id_prefix: str                             # "paper:" | "topic:" | "theme:"
    slug_regex: re.Pattern[str]                # paper hyphen-permissive; topic/theme lowercase-kebab
    slug_match: Literal["casefold", "exact"]   # paper=casefold; topic/theme=exact
    mixin_schema_id: str                       # mixin-paper-2.0 | mixin-topic-2.0 | mixin-theme-2.0
    default_profile: ProfileString             # "science-entity-base/1.0+<kind>/2.0"
    eligibility_filter: Callable[[Mapping[str, Any]], EligibilityVerdict] | None
```

`source_subdirs` is plural to accommodate topic's two source locations (`doc/topics/` and the legacy `doc/background/topics/`). `overlay_dest_subdir` is the single directory overlay rewrites land in — for topic, an overlay sourced from `doc/background/topics/foo.md` is rewritten to `doc/topics/foo.md` and the original `doc/background/topics/foo.md` is `Path.unlink()`-ed in the project working tree (no `git rm`, no project-side commit; matches Phase E's "rewrite working tree only, user reviews and commits" contract — see §4.4.1). If both `doc/topics/<slug>.md` and `doc/background/topics/<slug>.md` exist within one project, that's a single-project intra-kind collision → `PromoteCandidateError` at discovery.

`EligibilityVerdict` is a small enum:

```python
class EligibilityVerdict(Enum):
    ELIGIBLE = "eligible"
    SKIP_SILENT = "skip_silent"        # debug-log + skip (e.g. theme_scope: project)
    FAIL = "fail"                       # record as FailedCandidate (e.g. missing/malformed marker)
```

Three module-level constants are exported:

- `PROMOTE_KIND_PAPER`
- `PROMOTE_KIND_TOPIC`
- `PROMOTE_KIND_THEME`

The theme eligibility filter is the only non-`None` value at Phase F:

```python
def _theme_eligibility(fm: Mapping[str, Any]) -> EligibilityVerdict:
    scope = fm.get("theme_scope")
    if scope == "cross-project":
        return EligibilityVerdict.ELIGIBLE
    if scope == "project":
        return EligibilityVerdict.SKIP_SILENT
    return EligibilityVerdict.FAIL   # missing, None, or any other value
```

### 3.2 Public surface

All entry points gain a `kind: PromoteKindConfig` parameter. Names that previously embedded "paper" are renamed:

| Phase E (paper-only) | Phase F (kind-parametric) |
|---|---|
| `discover_paper_candidates(project_ids)` | `discover_candidates(project_ids, kind)` |
| `plan_promote(discovery, resolutions)` | `plan_promote(discovery, resolutions, kind)` |
| `apply_promote(plan)` | `apply_promote(plan)` *(carries kind in `PromotePlan`)* |
| `prompt_resolve(conflict)` | `prompt_resolve(conflict)` *(signature unchanged; uses `conflict.kind` for display)* |

`PromotePlan` and `PromoteResult` dataclasses carry the kind so the apply path doesn't need a separate parameter.

#### 3.2.1 Dataclass field renames (bibkey → slug)

The Phase E dataclasses use `bibkey` field naming throughout. That term is paper-specific. Phase F renames the field to `slug` across:

- `PromoteCandidate.bibkey` → `.slug`
- `FieldConflict.bibkey` → `.slug` (and adds `.kind: Literal["paper", "topic", "theme"]` for prompt display)
- `ConflictResolution.bibkey` → `.slug`
- `PromoteDecision.bibkey` → `.slug` (still used to build `{id_prefix}{slug}` strings, but the field itself is kind-agnostic)
- `DiscoveryResult.candidates_by_bibkey` → `.candidates_by_slug`

The `_normalize_bibkey_for_match` helper is renamed `_normalize_slug_for_match` and gains a `kind` parameter (paper casefolds; topic/theme returns the stem unchanged and asserts the regex).

The audit log `type:` field reads from `kind.kind` (replacing the hardcoded `"paper"` at `promote.py:1332`).

### 3.3 New schemas

Two new mixin files mirror the paper-2.0 shape:

**`mixin-topic-2.0.json`** (additive over 1.0):

```json
{
  "$id": "https://schemas.science/mixin-topic-2.0.json",
  "title": "science entity topic mixin",
  "$comment": "2.0 adds x-canonical-body-sections + project_only annotations on status/created/updated.",
  "type": "object",
  "required": ["id", "type"],
  "x-canonical-body-sections": [
    "Summary",
    "Key Concepts",
    "Current State of Knowledge",
    "Controversies & Open Questions",
    "Key References"
  ],
  "properties": {
    "id":   {"type": "string", "pattern": "^topic:[a-z0-9][a-z0-9-]{1,63}$"},
    "type": {"const": "topic"},
    "datasets":    {"type": "array", "items": {"type": "string", "pattern": "^dataset:"},
                    "science:merge": "append"},
    "source_refs": {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "related":     {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "status":      {"type": "string", "science:merge": "project_only"},
    "created":     {"type": "string", "format": "date", "science:merge": "project_only"},
    "updated":     {"type": "string", "format": "date", "science:merge": "project_only"}
  }
}
```

**`mixin-theme-2.0.json`**:

```json
{
  "$id": "https://schemas.science/mixin-theme-2.0.json",
  "title": "science entity theme mixin",
  "$comment": "2.0 adds x-canonical-body-sections + project_only annotations. theme_scope stays canonical.",
  "type": "object",
  "required": ["id", "type", "theme_kind", "theme_scope"],
  "x-canonical-body-sections": [
    "Definition",
    "Why It Matters",
    "Boundaries",
    "Guardrails",
    "Open Questions",
    "Update Triggers"
  ],
  "properties": {
    "id":   {"type": "string", "pattern": "^theme:[a-z0-9][a-z0-9-]{1,63}$"},
    "type": {"const": "theme"},
    "theme_kind":  {"enum": ["methodological", "conceptual", "empirical", "domain"]},
    "theme_scope": {"enum": ["project", "cross-project"]},
    "source_refs":   {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "evidence_refs": {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "related":       {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "status":  {"type": "string", "science:merge": "project_only"},
    "created": {"type": "string", "format": "date", "science:merge": "project_only"},
    "updated": {"type": "string", "format": "date", "science:merge": "project_only"}
  }
}
```

Overlay schema 1.1 already covers topic and theme overlay IDs (`oneOf` includes both prefixes); no overlay schema bump.

### 3.4 CLI

Mirrors Phase E, added to the existing `promote_group`:

```
science commons promote topic <topic:slug> --from <proj> [--apply] [--limit N]
science commons promote topic                --from <proj> [--from <proj2> ...] [--apply] [--limit N]

science commons promote theme <theme:slug> --from <proj> [--apply] [--limit N]
science commons promote theme                --from <proj> [--from <proj2> ...] [--apply] [--limit N]
```

Both subcommands share a single implementation function parametrised by kind. Error mapping (`PromoteConflictAbort` / `PromoteInputError` around plan; `PromoteInputError` / `PromoteWriteError` around apply) is identical to Phase E.

## 4. Data flow

### 4.1 Discovery

For each `--from <project>`:

1. `resolve_project_by_id(project_id)` → project root (or `CommonsError` for unregistered/null-id projects).
2. For each entry in `kind.source_subdirs`, walk `project_root / <subdir> / *.md`. (For paper/theme this is a single directory; for topic this is two.) If a slug appears in more than one source subdir within a single project, raise `PromoteCandidateError` for that file (cannot resolve which is canonical).
3. Parse frontmatter (`_parse_paper_file` → renamed `_parse_entity_file`, unchanged behavior).
4. Classify via `_classify_file_kind(fm, kind)` returning:
   - `"match"` — proceed to step 5
   - `"skip-already-promoted"` — silent skip (`overlay_of:` present)
   - `"skip-other-kind"` — warn + skip (explicit `kind:`/`type:` disagrees with this kind)
   - `"skip-other-id"` — silent skip (explicit `id:` has another prefix)
   - `"fail-id-mismatch"` — record `FailedCandidate` (id stem disagrees with filename — design §4.1.3 from Phase E)
5. Run `kind.eligibility_filter(fm)` if set:
   - `ELIGIBLE` → continue
   - `SKIP_SILENT` → debug-log and skip (theme `theme_scope: project`)
   - `FAIL` → record `FailedCandidate` (theme missing/malformed `theme_scope`)
6. Normalise the slug via `_normalize_slug_for_match(stem, kind)`:
   - `slug_match == "casefold"` → casefolded (paper)
   - `slug_match == "exact"` → stem as-is (topic/theme); must satisfy `kind.slug_regex` or `FailedCandidate`
7. Group by normalised slug; emit `DiscoveryResult(candidates_by_slug, failed_candidates, kind)`.

### 4.2 Plan

Unchanged from Phase E except that conflict-detection iterates per kind, and **all per-kind schema lookups happen at the top of `plan_promote` against `kind.default_profile`** (not the hardcoded paper profile at `promote.py:228`):

- `merge_policy = read_merge_policy(kind.default_profile)` — drives `_classify_entity` (canonical vs. project_only vs. forbidden field routing) and `_merge_canonical_fields` (append vs. replace per array field). Without this, topic-only fields like `datasets` / `source_refs` / `related` and theme-only fields like `evidence_refs` would be misclassified under the paper policy.
- `body_sections = read_canonical_body_sections(kind.default_profile)` — drives `_split_body_by_headings` (canonical vs. overlay body section routing).

Conflict-detection flow:

- Single-candidate slug → trivial plan entry (no prompt).
- Multi-candidate slug → `_merge_canonical_fields` produces `FieldConflict`s; each runs through `prompt_resolve` for the interactive N-way diff (Click prompt with manual-value entry + abort).

Body sections split via `_split_body_by_headings(body, body_sections)`:
- Headings whose text matches `body_sections` → canonical body.
- Anything else → overlay body (prepended to the overlay's `## Project-Specific Notes` section, same convention as Phase E).

### 4.3 Plan-time validation (new)

After building each `PromoteDecision` (canonical content + overlay rewrites) and before returning the `PromotePlan`, run schema validation:

- Canonical content validates against `base/1.0 + <kind>/2.0` profile.
- Each overlay validates against `overlay-1.1`.

Any failure raises `PromoteValidationError` (new error class, extending `CommonsError`; carries `decision_slug`, `target_kind` ∈ {"canonical", "overlay"}, `project_id` (overlay only), and the underlying `jsonschema.ValidationError` message). Plan-time validation is the **only** structural-validation stage; apply never touches a partially-valid plan.

Rationale: Phase E's design referenced an apply-stage "step 7 validation" that is not actually implemented in `apply_promote`. Validating at plan time is structurally cleaner — the canonical content is fully built at the end of `plan_promote`, failure produces a clear error before any I/O, and the apply path stays disk-only. This catches the pre-existing `theme_kind: "biological"` mismatch (§5) at plan time, surfaced with the jsonschema message verbatim.

### 4.4 Apply (atomic batch) — de-hardcoding

The 8-step transaction from Phase E §6.3 is reused, but multiple sites in `apply_promote` and its helpers currently hard-code `"paper"` / `"papers"` / `"doc/papers/"` / `bibkey`. These must be parametrised via `PromotePlan.kind`:

| Site (current code) | Hardcoded value | Replacement |
|---|---|---|
| `promote.py:315` | `commons_root / "papers" / ...` | `commons_root / kind.commons_subdir / ...` |
| `promote.py:393` | `path.startswith("papers/")` in `_commons_is_clean` | `path.startswith(f"{kind.commons_subdir}/")` |
| `promote.py:403,407` | `f"doc/papers/{name}"` in `_project_target_files_clean` | `f"{kind.overlay_dest_subdir}/{name}"` — plus an additional scan over `kind.source_subdirs` for renamed-away source files (the flatten case for topic) |
| `promote.py:577` (preflight) and `promote.py:626-627` (tag creation + sort) | `f"paper/{decision.bibkey}/..."` and `sorted(..., key=lambda d: d.bibkey)` | `f"{kind.kind}/{decision.slug}/..."` and sort by `.slug`. Both preflight and creation must use the same kind-derived tag prefix |
| `promote.py:609` | `f"promote: {len(plan.decisions)} papers via op {op_id}"` commons commit message | `f"promote: {len(plan.decisions)} {kind.commons_subdir} via op {op_id}"` (or equivalently `kind.kind + "s"`) |
| `promote.py:1214-1223` `_render_canonical` | `default_profile_for_kind("paper")`, `f"paper:{decision.bibkey}"`, `"type": "paper"`, unconditional `"bibkey": decision.bibkey` field | `kind.default_profile.render()`, `f"{kind.id_prefix}{decision.slug}"`, `"type": kind.kind`, and emit `"bibkey": decision.slug` **only when** `kind.kind == "paper"` (topic/theme canonicals must not carry a `bibkey` field — it isn't in their mixins) |
| `promote.py:1246,1247` `_render_overlay` head | `f"paper:{decision.bibkey}"` | `f"{kind.id_prefix}{decision.slug}"` |
| `promote.py:1289` `_build_project_rollback_command` | `first_path.parents[2]` (assumes 2-segment `doc/papers/` suffix) | Compute parent count from `len(Path(kind.overlay_dest_subdir).parts)` so the project root is recovered correctly for any kind |
| `promote.py:1319` | `"bibkey": decision.bibkey` in audit-log overlay-rewrite entry | `"slug": decision.slug` (rename; the field was misnamed for non-paper kinds anyway) |
| `promote.py:1332` | `"type": "paper"` in audit log root | `"type": kind.kind` |

Every site above gets a dedicated regression test that exercises both paper and topic kinds through it.

#### 4.4.1 Topic overlay flatten

For topic kind, `apply_promote` must also handle the source-relocation case (overlay sourced from `doc/background/topics/foo.md` lands at `doc/topics/foo.md`). Phase E's project-side contract (design §6.3 step 5) is that promote **rewrites project files in the working tree only**, leaving review and commit to the user — there are no project-side commits and no `git rm` staging. Phase F preserves that contract:

1. Build the target overlay path as `project_root / kind.overlay_dest_subdir / f"{slug}.md"`.
2. If the source path differs from target (source was in `doc/background/topics/`): write the new overlay file at the target path, then `Path.unlink()` the source file (filesystem delete, no git staging). The user sees both changes in `git status` (untracked or modified target + deleted source) and commits them together when reviewing.
3. Both source and target paths are included in `_project_target_files_clean` preflight (the same-project collision case from §5 — both can't already exist before the operation runs).
4. Rollback hint covers both paths: `git -C <project> checkout HEAD -- <source-rel> <target-rel>` restores the source file and discards the new target. The rollback command builder (`_build_project_rollback_command`) now derives multiple per-decision paths instead of one.

The audit YAML's `overlay_rewrites` entry for a flatten case records both `path` (the target) and `unlinked_source` (the source path that was removed), so a manual rollback has all the information needed.

#### 4.4.2 Theme-specific behaviour

The eligibility filter runs at discovery, so apply never sees a project-scoped theme. The canonical / overlay write rules:

- **Canonical** preserves `theme_kind` and `theme_scope: "cross-project"`.
- **Overlay** strips both `theme_kind` and `theme_scope` (overlay schema 1.1 doesn't allow them, and they're redundant with canonical).

This is handled by the merge-policy default routing — both fields are canonical (no `project_only` annotation), so they don't flow to overlay automatically. No special-case code needed beyond the existing `_classify_entity` field splitter.

## 5. Error handling

Reuses Phase E's four error classes (`PromoteInputError`, `PromoteCandidateError`, `PromoteConflictAbort`, `PromoteWriteError`) and **adds one new class**:

- `PromoteValidationError(CommonsError)` — raised at the end of `plan_promote` when the constructed canonical content or any overlay fails its schema. Carries `decision_slug: str`, `target_kind: Literal["canonical", "overlay"]`, `project_id: str | None` (overlay only), `schema_message: str`.

| Scenario | Class | Stage | Notes |
|---|---|---|---|
| Theme `theme_scope` missing / malformed / not in enum | `PromoteCandidateError` | discovery | Records `FailedCandidate`; discovery continues for other files |
| Topic appears in both `doc/topics/` and `doc/background/topics/` in one project | `PromoteCandidateError` | discovery | Cannot resolve canonical source; user must remove one |
| Topic / theme `id:` stem mismatch | `PromoteCandidateError` | discovery | Same rule as paper (design §4.1.3, Phase E) |
| Topic without `type:`, valid `id: topic:...` | inferred, no error | discovery | Canonical write normalises by emitting `type: topic` |
| **Eligible** theme (`theme_scope: cross-project`) with `theme_kind: "biological"` (out-of-enum) | `PromoteValidationError` | end of `plan_promote` | **No rollback needed — fails before any I/O.** User gets the jsonschema message verbatim. Project-scoped biological themes are filtered out earlier and never reach this check |
| Canonical fails any schema check | `PromoteValidationError` | end of `plan_promote` | Same — pre-I/O fail |
| Overlay fails overlay-1.1 schema | `PromoteValidationError` | end of `plan_promote` | Same — pre-I/O fail |
| User aborts conflict prompt | `PromoteConflictAbort` | plan | Pre-`--apply` so no rollback needed |
| Slug regex fails | `PromoteCandidateError` | discovery | `FailedCandidate` |
| All other git / write failures | `PromoteWriteError` | per-stage | Atomic rollback, `failure_audit_yaml` attached to exception |

The `theme_kind: "biological"` case is a **pre-existing schema mismatch** that Phase F does not fix. The mismatch surfaces at plan time (before any disk writes); resolving it (widening the enum, restructuring `theme_kind`, or rewriting project files) is a separate task tracked outside this design.

The CLI catches `PromoteValidationError` alongside `PromoteInputError` and `PromoteConflictAbort` in the plan-time error block (existing pattern in Phase E `cli.py`).

## 6. Testing

### 6.1 Refactor regression

All existing Phase E paper tests pass against the kind-pluggable rewrite. `PROMOTE_KIND_PAPER` via the new abstraction must behave bit-identically to the prior paper-specific code. This is enforced by **not changing any existing test** during the refactor task — if a test breaks, the refactor is wrong, not the test.

### 6.2 Schema tests

- `mixin-topic-2.0.json` and `mixin-theme-2.0.json` round-trip through the validator.
- `read_canonical_body_sections(kind.default_profile)` returns the declared lists for each new mixin.
- `read_merge_policy(kind.default_profile)` reads `project_only` annotations for `status` / `created` / `updated` on each new mixin. (`read_overlay_merge_policy` reads overlay-1.1 only — wrong API for mixin annotations.)
- `read_merge_policy(kind.default_profile)` reads `append` annotations for the array fields (`datasets`/`source_refs`/`related` on topic; `source_refs`/`evidence_refs`/`related` on theme).

### 6.3 Per-kind discovery / plan / apply / CLI

For each of topic and theme, a parallel suite of:

- `test_commons_promote_<kind>_discovery.py` — single-instance, dedup-no-conflict, dedup-with-conflict, eligibility-filter (theme), failure modes from §5.
- `test_commons_promote_<kind>_plan.py` — happy path; field-conflict prompt path (mocked input); abort path.
- `test_commons_promote_<kind>_apply.py` — happy path; atomic rollback on write failure; failure audit YAML attached on exception.
- `test_commons_cli_promote_<kind>.py` — smoke test, `--apply`, `--limit`, `--from` validation, single-entity form.

### 6.4 Fixtures

Extend `science/tests/fixtures/promote/` (existing 2-project corpus `proj-alpha`, `proj-beta`) with:

- `proj-alpha/doc/topics/` and `proj-beta/doc/topics/` — covering single-instance, no-conflict dedup, and field-conflict dedup shapes.
- `proj-alpha/doc/background/topics/` — at least one entry to exercise the flatten-to-`doc/topics/` overlay-rewrite path (§4.4.1). Plus a same-project-collision pair (`doc/topics/foo.md` + `doc/background/topics/foo.md`) for the error case.
- `proj-alpha/doc/themes/` and `proj-beta/doc/themes/` — same shapes, plus one `theme_scope: project` (eligibility skip), one with malformed `theme_scope` (eligibility FAIL), and one **`theme_scope: cross-project` + `theme_kind: "biological"`** (eligible-but-fails-validation: exercises `PromoteValidationError` at the end of `plan_promote`; a `theme_scope: project + theme_kind: biological` fixture would be skipped and never reach validation, which would not test the path).
- ~5 topics and ~5 themes total.

### 6.5 Apply-stage refactor regression

For each row in the §4.4 de-hardcoding table, a regression test that:

1. Exercises the site with `PROMOTE_KIND_PAPER` (must match the prior Phase E behaviour byte-for-byte).
2. Exercises the same site with `PROMOTE_KIND_TOPIC` (must produce `topics/` / `topic/` / `topic:` outputs).

These are the gate that proves the refactor is correct, not just present.

## 7. Pilot rollout

A `docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md` runbook ships with the implementation, following the Phase E template:

- Preconditions (commons clean, pilot projects clean, `commons` config registered).
- Dry-run (`commons promote topic --from <p1> --from <p2>` and `commons promote theme --from <p1> --from <p2>`).
- `--apply` for each kind, per-project commit, verification (`commons inventory` shows new canonicals + overlays).
- Rollback hints (drawn from the failure audit YAML in case of write error).

Pilot project choice is **not** baked into the design — selected at runbook-write time, based on which projects have eligible candidates **at that moment**.

Important caveat surfaced during design review: every real theme inspected at design time (`cancer/meta/doc/themes/*.md`, `cancer/cancer-types/multiple-myeloma/doc/themes/*.md`) currently carries `theme_scope: "project"`. Under the eligibility filter (§3.1), those themes are silently skipped — discovery returns zero theme candidates. This means the theme pilot has one of three possible shapes, picked at runbook-write time:

1. **Curated pre-pilot work.** Identify a small set of themes that are genuinely cross-cutting (e.g. methodological themes in `cancer/meta`) and rewrite their `theme_scope` to `"cross-project"` in a dedicated project-side PR *before* the pilot runs. The pilot then promotes them.
2. **Pilot deferral.** If no project currently has cross-project themes ready, the theme pilot waits — the `commons promote theme` machinery still ships and is exercised purely by fixture-based tests. Production rollout happens when a project actually marks themes as cross-project.
3. **Topic-only pilot.** Run the pilot for topics only; defer themes until option 1 or 2 is resolved.

Topics have no equivalent gating — every project-side topic file is a candidate by default, so a topic pilot can run immediately on projects like `natural-systems` (~14 topics, plus background-topic entries via the flatten path).

The runbook documents which of the three shapes the actual pilot takes.

## 8. Implementation phases

Single combined plan. Roughly:

1. **Refactor scaffolding.** Introduce `PromoteKindConfig` (with `source_subdirs` plural + `overlay_dest_subdir`), `EligibilityVerdict`, `PROMOTE_KIND_PAPER` constant. Rename `bibkey` → `slug` across dataclasses (§3.2.1). Existing functions take `kind` parameter; paper path threads it through. No new kinds yet; all existing tests pass.
2. **Apply-stage de-hardcoding.** One task per row in the §4.4 table. Each task adds the parametrisation **and** the dual-kind regression test (gate that proves correctness for both paper and topic).
3. **Plan-time validation.** Introduce `PromoteValidationError`; add the validation pass at end of `plan_promote`. CLI catches it in the plan-error block.
4. **Schemas.** `mixin-topic-2.0.json` + `mixin-theme-2.0.json`. Validator round-trip tests.
5. **Topic kind.** `PROMOTE_KIND_TOPIC` constant (two source subdirs, single overlay dest). Discovery / plan / apply tests including the background-topics flatten path and the same-project intra-kind collision. CLI subcommand. Fixtures.
6. **Theme kind.** `PROMOTE_KIND_THEME` constant + eligibility filter. Discovery / plan / apply tests with theme-specific cases (eligibility skip, eligibility FAIL, `theme_kind: "biological"` validation failure). CLI subcommand. Fixtures.
7. **Pilot runbook** + final integration test.

Approximate task count: 26–32 (grew from 22–26 to cover the de-hardcoding sites and plan-time validation as explicit tasks). Plan to be written by `superpowers:writing-plans`.

## 9. Open questions

Deferred — non-load-bearing for the design.

- **Topic body-section vocabulary.** Real `natural-systems` topics use ad-hoc section names ("Scope", "Note"). The proposed canonical list (Summary, Key Concepts, Current State of Knowledge, Controversies & Open Questions, Key References) captures the template intent; ad-hoc sections route to overlay body automatically. Future templates may converge — but Phase F does not enforce that.
- **`theme_kind` enum widening.** Real `mm` themes use `"biological"`, blocking promotion under the current schema. The enum likely needs to grow (or `theme_kind` needs to become free-form with a recommended vocabulary) — separate task.
- **Topic / theme version pinning behaviour.** The overlay schema 1.1 supports `pin_version:` and `pin_effective_version:` on topic / theme IDs. Phase F writes overlays without pins (always-latest). Pinning policy is a Phase D follow-on, not Phase F.
- **Future kind: dataset.** Phase G will add a fourth kind. The `PromoteKindConfig` shape may need to grow a "paired-file" hook (entity.md + datapackage.yaml) — confirmed during Phase G design, not pre-judged here.
