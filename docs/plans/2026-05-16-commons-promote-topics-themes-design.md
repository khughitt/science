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
- **Schema fixes for pre-existing mismatches.** Real `mm` themes carry `theme_kind: "biological"` (not in the current enum). Phase F surfaces these as loud validation failures with atomic rollback; it does **not** widen the enum or rewrite project files.
- **Compatibility shims for old function names.** Per the project's "no legacy layers" rule, `discover_paper_candidates` is renamed (or absorbed into a kind-parametric `discover_candidates`) in the same PR — no transitional alias survives merge.

## 3. Architecture

### 3.1 Kind pluggability — `PromoteKindConfig`

Frozen, slotted dataclass; pure data plus one optional callable hook. Composition over inheritance.

```python
@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    kind: Literal["paper", "topic", "theme"]
    source_subdir: str                         # "doc/papers" | "doc/topics" | "doc/themes"
    commons_subdir: str                        # "papers"     | "topics"     | "themes"
    id_prefix: str                             # "paper:" | "topic:" | "theme:"
    slug_regex: re.Pattern[str]                # paper hyphen-permissive; topic/theme lowercase-kebab
    slug_match: Literal["casefold", "exact"]   # paper=casefold; topic/theme=exact
    mixin_schema_id: str                       # mixin-paper-2.0 | mixin-topic-2.0 | mixin-theme-2.0
    default_profile: ProfileString             # "science-entity-base/1.0+<kind>/2.0"
    eligibility_filter: Callable[[Mapping[str, Any]], EligibilityVerdict] | None
```

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
| `prompt_resolve(conflict)` | `prompt_resolve(conflict)` *(unchanged signature)* |

`PromotePlan` and `PromoteResult` dataclasses carry the kind so the apply path doesn't need a separate parameter.

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
2. Walk `project_root / kind.source_subdir / *.md`.
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

Unchanged from Phase E except that conflict-detection iterates per kind:

- Single-candidate slug → trivial plan entry (no prompt).
- Multi-candidate slug → `_merge_canonical_fields` produces `FieldConflict`s; each runs through `prompt_resolve` for the interactive N-way diff (Click prompt with manual-value entry + abort).

Body sections split via `_split_body_by_headings(body, kind)`:
- Headings whose text matches `kind.canonical_body_sections` (looked up via `read_canonical_body_sections(kind.default_profile)`) → canonical body.
- Anything else → overlay body (prepended to the overlay's `## Project-Specific Notes` section, same convention as Phase E).

### 4.3 Apply (atomic batch)

The 8-step transaction from Phase E §6.3 is reused verbatim. The kind-pluggable refactor changes **no** apply-stage code paths — kind is read from `PromotePlan.kind` to pick `commons_subdir` and which schemas to validate against in step 7.

Per-kind validation in step 7:
- Canonical validates against `base/1.0 + <kind>/2.0` profile.
- Overlay validates against `overlay-1.1`.

Rollback (`reset --soft HEAD~1` + per-path `checkout HEAD --` / unlink) is unchanged.

### 4.4 Theme-specific apply behaviour

The eligibility filter runs at discovery, so apply never sees a project-scoped theme. But the canonical / overlay write needs two theme-only rules:

- **Canonical** preserves `theme_kind` and `theme_scope: "cross-project"`.
- **Overlay** strips both `theme_kind` and `theme_scope` (overlay schema 1.1 doesn't allow them, and they're redundant with canonical).

This is handled by the merge-policy default routing — both fields are canonical (no `project_only` annotation), so they don't flow to overlay automatically. No special-case code needed beyond the existing `_classify_entity` field splitter.

## 5. Error handling

Reuses Phase E's four error classes (`PromoteInputError`, `PromoteCandidateError`, `PromoteConflictAbort`, `PromoteWriteError`). Phase F adds these failure scenarios, all routed through existing classes:

| Scenario | Class | Stage | Notes |
|---|---|---|---|
| Theme `theme_scope` missing / malformed / not in enum | `PromoteCandidateError` | discovery | Records `FailedCandidate`; discovery continues for other files |
| Topic / theme `id:` stem mismatch | `PromoteCandidateError` | discovery | Same rule as paper (design §4.1.3, Phase E) |
| Topic without `type:`, valid `id: topic:...` | inferred, no error | discovery | Canonical write normalises by emitting `type: topic` |
| Theme with `theme_kind: "biological"` (out-of-enum) | `PromoteWriteError` | step 7 `validate_canonical` | Atomic rollback fires; user gets the jsonschema error message verbatim |
| User aborts conflict prompt | `PromoteConflictAbort` | plan | Pre-`--apply` so no rollback needed |
| Slug regex fails | `PromoteCandidateError` | discovery | `FailedCandidate` |
| All other git / write failures | `PromoteWriteError` | per-stage | Atomic rollback, `failure_audit_yaml` attached to exception |

The `theme_kind: "biological"` case is a **pre-existing schema mismatch** that Phase F does not fix. The mismatch surfaces as a loud failure with rollback; resolving it (widening the enum, restructuring `theme_kind`, or rewriting project files) is a separate task tracked outside this design.

## 6. Testing

### 6.1 Refactor regression

All existing Phase E paper tests pass against the kind-pluggable rewrite. `PROMOTE_KIND_PAPER` via the new abstraction must behave bit-identically to the prior paper-specific code. This is enforced by **not changing any existing test** during the refactor task — if a test breaks, the refactor is wrong, not the test.

### 6.2 Schema tests

- `mixin-topic-2.0.json` and `mixin-theme-2.0.json` round-trip through the validator.
- `read_canonical_body_sections` returns the declared lists for each new mixin.
- `read_overlay_merge_policy` reads `project_only` annotations for `status` / `created` / `updated` on both new mixins.

### 6.3 Per-kind discovery / plan / apply / CLI

For each of topic and theme, a parallel suite of:

- `test_commons_promote_<kind>_discovery.py` — single-instance, dedup-no-conflict, dedup-with-conflict, eligibility-filter (theme), failure modes from §5.
- `test_commons_promote_<kind>_plan.py` — happy path; field-conflict prompt path (mocked input); abort path.
- `test_commons_promote_<kind>_apply.py` — happy path; atomic rollback on write failure; failure audit YAML attached on exception.
- `test_commons_cli_promote_<kind>.py` — smoke test, `--apply`, `--limit`, `--from` validation, single-entity form.

### 6.4 Fixtures

Extend `science/tests/fixtures/promote/` (existing 2-project corpus `proj-alpha`, `proj-beta`) with:

- `proj-alpha/doc/topics/` and `proj-beta/doc/topics/` — covering single-instance, no-conflict dedup, and field-conflict dedup shapes.
- `proj-alpha/doc/themes/` and `proj-beta/doc/themes/` — same shapes, plus one `theme_scope: project` (eligibility skip) and one with malformed `theme_scope` (eligibility FAIL).
- ~4 topics and ~4 themes total.

## 7. Pilot rollout

A `docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md` runbook ships with the implementation, following the Phase E template:

- Preconditions (commons clean, pilot projects clean, `commons` config registered).
- Dry-run (`commons promote topic --from <p1> --from <p2>` and `commons promote theme --from <p1> --from <p2>`).
- `--apply` for each kind, per-project commit, verification (`commons inventory` shows new canonicals + overlays).
- Rollback hints (drawn from the failure audit YAML in case of write error).

Pilot projects are selected at runbook-write time based on which projects have eligible candidates. Likely choices:

- **Topics:** `natural-systems` (~14 topics) + `cancer/cancer-types/multiple-myeloma` (1 topic) — good cross-project test even if dedup count is small.
- **Themes:** `cancer/meta` (~12 themes, several plausibly `theme_scope: cross-project`) + `cancer/cancer-types/multiple-myeloma` (10 themes — most currently `project`-scoped, will be skipped silently).

Pilot project choice does not affect the design; this section is informational.

## 8. Implementation phases

Single combined plan. Roughly:

1. **Refactor scaffolding.** Introduce `PromoteKindConfig`, `EligibilityVerdict`, `PROMOTE_KIND_PAPER` constant. Existing functions take `kind` parameter, paper path threads it through. No new kinds yet; all existing tests pass.
2. **Schemas.** `mixin-topic-2.0.json` + `mixin-theme-2.0.json`. Validator round-trip tests.
3. **Topic kind.** `PROMOTE_KIND_TOPIC` constant. Discovery / plan / apply tests. CLI subcommand. Fixtures.
4. **Theme kind.** `PROMOTE_KIND_THEME` constant + eligibility filter. Discovery / plan / apply tests with theme-specific cases. CLI subcommand. Fixtures.
5. **Pilot runbook** + final integration test.

Approximate task count: 22–26. Plan to be written by `superpowers:writing-plans`.

## 9. Open questions

Deferred — non-load-bearing for the design.

- **Topic body-section vocabulary.** Real `natural-systems` topics use ad-hoc section names ("Scope", "Note"). The proposed canonical list (Summary, Key Concepts, Current State of Knowledge, Controversies & Open Questions, Key References) captures the template intent; ad-hoc sections route to overlay body automatically. Future templates may converge — but Phase F does not enforce that.
- **`theme_kind` enum widening.** Real `mm` themes use `"biological"`, blocking promotion under the current schema. The enum likely needs to grow (or `theme_kind` needs to become free-form with a recommended vocabulary) — separate task.
- **Topic / theme version pinning behaviour.** The overlay schema 1.1 supports `pin_version:` and `pin_effective_version:` on topic / theme IDs. Phase F writes overlays without pins (always-latest). Pinning policy is a Phase D follow-on, not Phase F.
- **Future kind: dataset.** Phase G will add a fourth kind. The `PromoteKindConfig` shape may need to grow a "paired-file" hook (entity.md + datapackage.yaml) — confirmed during Phase G design, not pre-judged here.
