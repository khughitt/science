# Phase G — `science commons promote dataset` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate one dataset end-to-end from project-local to commons-canonical, exercising the full v1 surface (multi-file canonical, real-byte hashing, per-machine override side-channel, recipe stubbing) by extending the kind-pluggable promote framework introduced in Phase F.

**Architecture:** Replace `PromoteDecision.canonical_path`/`.canonical_content` (singular) with `canonical_artifacts: list[CanonicalArtifact]` so the dataset kind can emit three files (entity.md, datapackage.yaml, recipe/README.md) without forking the apply pipeline. Add `PROMOTE_KIND_DATASET` alongside the existing paper/topic/theme constants. Add a dataset-only side-channel hook on `PromoteKindConfig` so apply can write `~/.config/science/data.yaml` between the commons tag step and the project overlay rewrite — keeping the resolver chain coherent at all times. All rollback stays path-limited (Phase F precedent: `_restore_paths_to_head`, `_rollback_step5`); no `git reset --hard`, no `git clean -fd`.

**Tech Stack:** Python 3.11+, Click (CLI), PyYAML, jsonschema, hashlib (sha256), pytest, subprocess for git. Existing science/ monorepo at `~/d/science/science/`.

**Design spec:** `~/d/science/docs/plans/2026-05-18-commons-promote-datasets-design.md` (commit `0b829b7`).

**Pilot target:** `dataset:ccle-proteomics-nusinow-2020` in `multiple-myeloma`.

---

## File Structure

### Files modified (existing)

| File | Reason |
|---|---|
| `~/d/science/science/src/science_tool/commons/promote.py` | Add `CanonicalArtifact`, `PROMOTE_KIND_DATASET`, dataset discovery/plan/apply paths, override side-channel hook, multi-artifact rollback. Replace singular `canonical_path` with `canonical_artifacts`/`canonical_paths` everywhere (paper/topic/theme switch to 1-element lists). |
| `~/d/science/science/src/science_tool/commons/cli.py` | Add `promote_dataset_cmd` parallel to `promote_topic_cmd`. |
| `~/d/science/science/src/science_tool/commons/errors.py` | Add `PromoteResourceMissingError`, `PromoteOverrideConflictError`. |
| `~/d/science/science/src/science_tool/commons/datapackage.py` | Helpers may grow: streaming-hash function over a resource; dataset-side rendering helpers for canonical `datapackage.yaml`. |
| `~/d/science/science/src/science_tool/commons/config.py` | Add `load_data_overrides_atomic_write` helper if not already present; or extend the existing override-read API with a paired upsert. |
| `~/d/science/science/tests/test_commons_promote_kind_config.py` | Cover the new `canonical_artifacts` list model and the dataset kind constant. |
| `~/d/science/science/tests/test_commons_promote_apply.py` | Regression — confirm paper-kind still passes after the list refactor. |
| `~/d/science/science/tests/test_commons_promote_topic_apply.py` | Regression — confirm topic-kind still passes. |
| `~/d/science/science/tests/test_commons_promote_theme_apply.py` | Regression — confirm theme-kind still passes. |
| `~/d/science/science/tests/test_commons_promote_discovery.py` | Append dataset-discovery cases (id-prefix rejection, missing `datapackage:` field, etc.). |
| `~/d/science/science/tests/test_commons_promote_validation.py` | Append dataset-plan validation cases. |
| `~/d/science/science/tests/test_commons_resolver.py` | If override-write changes affect existing resolver tests, regress them. |

### Files created (new)

| File | Responsibility |
|---|---|
| `~/d/science/science/tests/test_commons_promote_dataset_discovery.py` | Dataset discovery: `datapackage:` field check, datapackage parse, resource files exist, slug-stem mismatch, override-conflict on existing entry. |
| `~/d/science/science/tests/test_commons_promote_dataset_plan.py` | Hash determinism (golden 12-byte fixture); canonical `datapackage.yaml` rendering; canonical `entity.md` rendering; recipe stub; field-routing buckets; `tier:` verbatim preservation; `recipe_stubbed: true` audit flag. |
| `~/d/science/science/tests/test_commons_promote_dataset_apply.py` | Multi-artifact write; commons commit + tag; override upsert (new file / merge with existing / conflict path); overlay rewrite; dropped_fields in audit log; 5 fault-injection rollback paths (a–e); audit-log failure carve-out. |
| `~/d/science/science/tests/test_commons_promote_dataset_integration.py` | End-to-end synthetic-project run under `tmp_path` with `XDG_CONFIG_HOME` sandbox. |
| `~/d/science/science/tests/fixtures/promote/proj-dataset/` | Minimal synthetic project: `doc/datasets/data-fixture-ds.md` + `data/fixture-ds/datapackage.json` + `r1.txt` (12 bytes "hello world\n") + `r2.txt` (37 bytes). |
| `~/d/science/science/tests/fixtures/promote_dataset/hello.txt` | Golden 12-byte hash fixture: `"hello world\n"` → sha256 `a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447`. |
| `~/d/science/docs/plans/2026-05-18-commons-promote-datasets-pilot.md` | Pilot runbook companion. |

---

## Task Index

- **G.1 — Canonical artifact list model** (Tasks 1–6)
- **G.2 — Dataset discovery** (Tasks 7–10)
- **G.3 — Hash compute + plan rendering** (Tasks 11–16)
- **G.4 — Per-machine override side-channel** (Tasks 17–19)
- **G.5 — Apply ordering + audit log shape** (Tasks 20–23)
- **G.6 — CLI** (Task 24)
- **G.7 — Integration + pilot runbook** (Tasks 25–28)

---

## G.1 — Canonical artifact list model

### Task 1: Add `CanonicalArtifact` dataclass

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (top of file, near other dataclasses)
- Test: `~/d/science/science/tests/test_commons_promote_kind_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_kind_config.py — append
from pathlib import Path

def test_canonical_artifact_is_frozen_and_holds_three_fields():
    from science_tool.commons.promote import CanonicalArtifact
    art = CanonicalArtifact(
        path=Path("datasets/foo/entity.md"),
        content="---\nid: dataset:foo\n---\n",
        validator="entity-mixin",
    )
    assert art.path == Path("datasets/foo/entity.md")
    assert art.content.startswith("---")
    assert art.validator == "entity-mixin"
    import dataclasses
    assert dataclasses.is_dataclass(art)
    # frozen — direct attr assignment should raise
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        art.content = "mutated"

def test_canonical_artifact_validator_literal_rejects_unknown():
    # Literal typing isn't runtime-enforced, but document accepted values:
    from science_tool.commons.promote import CanonicalArtifact
    for v in ("entity-mixin", "frictionless-datapackage", "plain"):
        CanonicalArtifact(path=Path("x.md"), content="", validator=v)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_promote_kind_config.py::test_canonical_artifact_is_frozen_and_holds_three_fields -v`
Expected: FAIL — `ImportError: cannot import name 'CanonicalArtifact'`.

- [ ] **Step 3: Add the dataclass**

Add to `promote.py` near the other `@dataclass(frozen=True, slots=True)` definitions (search for `class PromoteDecision` and add just above it):

```python
@dataclass(frozen=True, slots=True)
class CanonicalArtifact:
    """One file under <commons_root>/<commons_subdir>/<slug>/.

    `path` is stored relative to the commons root (e.g.
    `datasets/foo/entity.md`). Apply resolves it against `commons_root` once
    at write time and records the absolute resolved path in the per-op
    rollback context so existing helpers (`_restore_paths_to_head`,
    `_rollback_step5`) keep their absolute-path signatures.
    """
    path: Path
    content: str
    validator: Literal["entity-mixin", "frictionless-datapackage", "plain"]
```

Ensure `Literal` is imported from `typing`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_promote_kind_config.py -v -k canonical_artifact`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_kind_config.py
git commit -m "commons(promote): add CanonicalArtifact dataclass for multi-file canonicals"
```

---

### Task 2: Replace `PromoteDecision.canonical_path`/`.canonical_content` with `canonical_artifacts`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`PromoteDecision`, `plan_promote`, every reader)
- Test: `~/d/science/science/tests/test_commons_promote_kind_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_kind_config.py — append
def test_promote_decision_uses_canonical_artifacts_list():
    """Paper/topic/theme decisions carry a one-element artifact list (regression)."""
    from pathlib import Path
    from science_tool.commons.promote import CanonicalArtifact, PromoteDecision

    art = CanonicalArtifact(
        path=Path("papers/Adams2025.md"),
        content="---\nid: paper:Adams2025\n---\nbody\n",
        validator="entity-mixin",
    )
    d = PromoteDecision(
        slug="Adams2025",
        canonical_artifacts=[art],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    assert len(d.canonical_artifacts) == 1
    assert d.canonical_artifacts[0].path == Path("papers/Adams2025.md")
    # The old singular attrs must be gone:
    assert not hasattr(d, "canonical_path")
    assert not hasattr(d, "canonical_content")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_promote_kind_config.py::test_promote_decision_uses_canonical_artifacts_list -v`
Expected: FAIL — TypeError on unexpected keyword `canonical_artifacts`, or AttributeError.

- [ ] **Step 3: Refactor `PromoteDecision` and `plan_promote`**

Replace the `PromoteDecision` definition in `promote.py`:

```python
@dataclass(frozen=True, slots=True)
class PromoteDecision:
    slug: str
    canonical_artifacts: list[CanonicalArtifact]   # ≥1 entry
    canonical_version: str
    overlays: dict[str, OverlayRewrite]
    resolved_conflicts: tuple[ConflictResolution, ...]
```

In `plan_promote`, wherever a `PromoteDecision` is constructed, replace:
```python
canonical_path=<path>,
canonical_content=<content>,
```
with:
```python
canonical_artifacts=[
    CanonicalArtifact(
        path=<path>.relative_to(commons_root),
        content=<content>,
        validator="entity-mixin",
    )
],
```

The path stored on the artifact must be commons-relative.

- [ ] **Step 4: Update every reader inside `plan_promote` and `apply_promote`**

In `apply_promote` (search for `decision.canonical_path`), replace each access. The Phase F apply currently has (around `promote.py:824-829`):

```python
written_canonical_paths: list[Path] = []
try:
    for decision in plan.decisions:
        decision.canonical_path.parent.mkdir(parents=True, exist_ok=True)
        decision.canonical_path.write_text(decision.canonical_content, encoding="utf-8")
        written_canonical_paths.append(decision.canonical_path)
```

Change to:

```python
written_canonical_paths: list[Path] = []
try:
    for decision in plan.decisions:
        for artifact in decision.canonical_artifacts:
            abs_path = commons_root / artifact.path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(artifact.content, encoding="utf-8")
            written_canonical_paths.append(abs_path)
```

Note: `written_canonical_paths` still holds **absolute** paths so `_restore_paths_to_head` (which expects absolute) keeps working unchanged.

In the commit step (around `promote.py:838`), the `rel_paths` derivation already calls `.relative_to(commons_root)` — that path stays the same.

- [ ] **Step 5: Run the regression suite**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_apply.py tests/test_commons_promote_topic_apply.py tests/test_commons_promote_theme_apply.py tests/test_commons_promote_kind_config.py -v
```
Expected: all passing. If any Phase F test still references `decision.canonical_path` directly, fix the test to read `decision.canonical_artifacts[0].path` (or `commons_root / decision.canonical_artifacts[0].path` for absolute).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/
git commit -m "commons(promote): replace canonical_path/content with canonical_artifacts list"
```

---

### Task 3: Replace `PromoteResult.canonical_path` references (if any) with `canonical_paths` list

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`PromoteResult`, audit-log renderer)

- [ ] **Step 1: Check whether `PromoteResult` has a singular canonical_path field**

```bash
cd ~/d/science/science
rg "canonical_path" src/science_tool/commons/promote.py
```
Per the Phase F digest, `PromoteResult` does NOT expose canonical paths at the top level (they're stored on `decisions[].canonical_artifacts[]`). If this search returns only references inside `decisions` iteration, skip to Step 5 of this task (no change needed).

- [ ] **Step 2: If a top-level canonical_path attribute exists, write a failing test**

```python
# tests/test_commons_promote_kind_config.py — append
def test_promote_result_exposes_canonical_paths_via_decisions():
    """canonical paths are reachable via result.decisions[*].canonical_artifacts."""
    # Skip if not exposed at top level (current Phase F shape)
    from science_tool.commons.promote import PromoteResult
    assert "canonical_path" not in PromoteResult.__dataclass_fields__
```

- [ ] **Step 3: Make the assertion true**

If a singular field exists, remove it from `PromoteResult`; any caller that needs the list per decision iterates `result.decisions[*].canonical_artifacts`. Update `_render_audit_log_yaml` to emit `canonical_paths` per decision in the new audit shape (Task 22 finalizes this — for now, just preserve current behavior).

- [ ] **Step 4: Run the audit-shape regression**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_apply.py -v -k "audit"
```
Expected: passing.

- [ ] **Step 5: Commit (only if files changed)**

```bash
cd ~/d/science/science
git add -u src/science_tool/commons/promote.py tests/
git diff --staged --quiet || git commit -m "commons(promote): align PromoteResult with canonical_artifacts model"
```

---

### Task 4: Plan-time validation dispatches by `CanonicalArtifact.validator`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (validation block at end of `plan_promote`)
- Test: `~/d/science/science/tests/test_commons_promote_validation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_validation.py — append
def test_plan_validation_dispatches_by_artifact_validator(tmp_path, monkeypatch):
    """An artifact with validator='plain' is skipped; 'entity-mixin' runs EntityValidator()."""
    from pathlib import Path
    from science_tool.commons.promote import (
        CanonicalArtifact, _validate_artifact,
    )

    plain = CanonicalArtifact(
        path=Path("datasets/x/recipe/README.md"),
        content="# Recipe back-fill needed\n",
        validator="plain",
    )
    # Should NOT raise:
    _validate_artifact(plain, decision_slug="x", project_id=None)

    # Minimal mixin artifact: still missing required dataset-mixin fields
    # (origin/tier/access), so the science_model EntityValidator will reject it.
    mixin = CanonicalArtifact(
        path=Path("datasets/x/entity.md"),
        content=(
            "---\n"
            "schema_profile: science-entity-base/1.0+dataset/1.0\n"
            "id: dataset:x\n"
            "type: dataset\n"
            "title: x\n"
            "version: 1.0.0\n"
            "created: '2026-05-18'\n"
            "updated: '2026-05-18'\n"
            "---\n"
        ),
        validator="entity-mixin",
    )
    import pytest
    from science_tool.commons.errors import PromoteValidationError
    with pytest.raises(PromoteValidationError):
        _validate_artifact(mixin, decision_slug="x", project_id=None)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_promote_validation.py::test_plan_validation_dispatches_by_artifact_validator -v`
Expected: FAIL — `ImportError: cannot import name '_validate_artifact'`.

- [ ] **Step 3: Add the dispatch helper to `promote.py`**

The real entity validator is `science_model.entity_schema.EntityValidator` with `.validate(entity_dict)` (consumes parsed frontmatter, not raw markdown). Use the existing `_parse_frontmatter_only(text)` helper from `promote.py` to split frontmatter from body, then call the validator on the dict.

```python
def _validate_artifact(
    artifact: CanonicalArtifact,
    *,
    decision_slug: str,
    project_id: str | None,
) -> None:
    """Plan-time validation dispatch by artifact.validator."""
    if artifact.validator == "plain":
        return
    if artifact.validator == "entity-mixin":
        from science_model.entity_schema import EntityValidator
        from science_model.entity_schema.validator import EntityValidationError
        fm = _parse_frontmatter_only(artifact.content)
        try:
            EntityValidator().validate(fm)
        except EntityValidationError as exc:
            raise PromoteValidationError(
                decision_slug=decision_slug,
                target_kind="canonical",
                project_id=project_id,
                schema_message=str(exc),
            ) from exc
        return
    if artifact.validator == "frictionless-datapackage":
        from science_tool.commons.datapackage import parse_canonical_datapackage_yaml
        try:
            parse_canonical_datapackage_yaml(artifact.content)
        except Exception as exc:
            raise PromoteValidationError(
                decision_slug=decision_slug,
                target_kind="canonical",
                project_id=project_id,
                schema_message=str(exc),
            ) from exc
        return
    raise AssertionError(f"unknown artifact validator: {artifact.validator!r}")
```

`_parse_frontmatter_only` already exists in `promote.py` (it's how discovery reads candidate frontmatter); reuse it directly. `parse_canonical_datapackage_yaml` is added in Task 12 — the `frictionless-datapackage` branch is unreachable until then (paper/topic/theme decisions never produce that validator).

Wire the helper into `plan_promote`'s final validation loop: replace the existing `EntityValidator.validate_canonical_markdown(decision.canonical_content)` call with:

```python
for decision in plan.decisions:
    for artifact in decision.canonical_artifacts:
        _validate_artifact(
            artifact,
            decision_slug=decision.slug,
            project_id=<existing project_id ref>,
        )
```

- [ ] **Step 4: Run the new test plus regressions**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_validation.py tests/test_commons_promote_apply.py tests/test_commons_promote_topic_apply.py tests/test_commons_promote_theme_apply.py -v
```
Expected: all passing.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_validation.py
git commit -m "commons(promote): dispatch plan-time validation by artifact.validator"
```

---

### Task 5: Audit-log rendering uses `canonical_paths` per decision

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`_render_audit_log_yaml`)
- Test: `~/d/science/science/tests/test_commons_promote_apply.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_apply.py — append (or new test_commons_promote_audit_shape.py)
def test_audit_log_records_canonical_paths_per_decision(tmp_path, monkeypatch):
    """Each decision contributes one canonical_paths entry, list-form."""
    # ...full setup mirroring existing topic apply tests; after apply_promote returns:
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    assert "decisions" in log
    for entry in log["decisions"]:
        assert "canonical_paths" in entry
        assert isinstance(entry["canonical_paths"], list)
        assert len(entry["canonical_paths"]) >= 1
```

(Use existing topic fixture setup verbatim.)

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `decisions` key missing or `canonical_paths` is singular `canonical_path`.

- [ ] **Step 3: Extend `_render_audit_log_yaml`**

In `_render_audit_log_yaml`, replace the existing per-decision rendering to emit:

```python
"decisions": [
    {
        "slug": d.slug,
        "canonical_version": d.canonical_version,
        "canonical_paths": [
            str(a.path) for a in d.canonical_artifacts  # commons-relative
        ],
    }
    for d in result.decisions
],
```

Keep all other existing keys (`op_id`, `commons_commit`, `commons_tags`, `projects_touched`, `failed_candidates`, `rollback`) unchanged.

- [ ] **Step 4: Run the regression suite**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_apply.py tests/test_commons_promote_topic_apply.py tests/test_commons_promote_theme_apply.py -v
```
Expected: all passing. Fix any test that asserts the old singular shape.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/
git commit -m "commons(promote): audit log emits per-decision canonical_paths list"
```

---

### Task 6: Full Phase F regression sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the entire commons test surface**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_*.py -v
```
Expected: every test passing. The CanonicalArtifact refactor is a structural change — Phase F kinds now thread through the list-of-one codepath. Any failure here indicates the refactor missed a call-site.

- [ ] **Step 2: Investigate and fix any failures inline**

For each failure: read the test, identify whether it (a) asserts the old singular API (update the test to read `canonical_artifacts[0]`) or (b) exposes a real bug in the refactor (fix the code).

- [ ] **Step 3: Confirm clean run**

Re-run Step 1. Expected: all tests pass.

- [ ] **Step 4: Commit fixes**

```bash
cd ~/d/science/science
git add -u
git diff --staged --quiet || git commit -m "commons(tests): align Phase F tests with canonical_artifacts list shape"
```

---

## G.2 — Dataset discovery

### Task 7: Define `PROMOTE_KIND_DATASET` constant

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (kind constants block)
- Test: `~/d/science/science/tests/test_commons_promote_kind_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_kind_config.py — append
def test_promote_kind_dataset_constant_shape():
    from science_tool.commons.promote import PROMOTE_KIND_DATASET
    assert PROMOTE_KIND_DATASET.kind == "dataset"
    assert PROMOTE_KIND_DATASET.source_subdirs == ("doc/datasets",)
    assert PROMOTE_KIND_DATASET.overlay_dest_subdir == "doc/datasets"
    assert PROMOTE_KIND_DATASET.commons_subdir == "datasets"
    assert PROMOTE_KIND_DATASET.id_prefix == "dataset:"
    # Dataset slug rule: lowercase-kebab
    assert PROMOTE_KIND_DATASET.slug_regex.match("ccle-proteomics-nusinow-2020")
    assert not PROMOTE_KIND_DATASET.slug_regex.match("NotKebab")
    assert PROMOTE_KIND_DATASET.slug_match == "exact"
    assert "mixin-dataset" in PROMOTE_KIND_DATASET.mixin_schema_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_promote_kind_config.py::test_promote_kind_dataset_constant_shape -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the constant**

In `promote.py`, near `PROMOTE_KIND_THEME`:

```python
PROMOTE_KIND_DATASET = PromoteKindConfig(
    kind="dataset",
    source_subdirs=("doc/datasets",),
    overlay_dest_subdir="doc/datasets",
    commons_subdir="datasets",
    id_prefix="dataset:",
    slug_regex=re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$"),
    slug_match="exact",
    mixin_schema_id="https://schemas.science/mixin-dataset-1.0.json",
    default_profile=default_profile_for_kind("dataset"),
    eligibility_filter=None,
)
```

Extend the `kind: Literal[...]` field on `PromoteKindConfig` to include `"dataset"`. Update `default_profile_for_kind` if it has a kind-table; otherwise add a `"dataset"` branch with the appropriate default profile string (mirror the topic/theme defaults).

- [ ] **Step 4: Run the test plus regressions**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_kind_config.py -v
```
Expected: all passing.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_kind_config.py
git commit -m "commons(promote): add PROMOTE_KIND_DATASET constant"
```

---

### Task 7b: Add `filename_prefix` (filter) + `slug_from_id` (slug derivation) to `PromoteKindConfig`

**Background:** Existing `_scan_project` derives the slug from `source_path.stem` and cross-checks it against the id slug (`promote.py:1145, :1203`). For paper/topic/theme this works because the filename equals the slug. For datasets the real convention is `data-<short>.md` where `<short>` is often a truncation of the full id slug (e.g., `data-ccle-proteomics.md` carries id `dataset:ccle-proteomics-nusinow-2020`). Forcing equality breaks every real dataset file. Fix by decoupling discovery into two concerns:

1. **`filename_prefix`** (new field, default `""`): a kind-membership filter. The file stem must start with this prefix to be considered a candidate for the kind. Datasets set `"data-"`.
2. **`slug_from_id`** (new field, default `False`): controls slug derivation. When `True`, the canonical slug comes from the `id:` frontmatter field (after stripping the `kind.id_prefix`), and the filename-vs-id cross-check is skipped. Datasets set `True`. Paper/topic/theme keep `False` and the existing stem-equals-slug semantics.

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`PromoteKindConfig`, `_normalize_slug_for_match`, `_scan_project`, `PROMOTE_KIND_DATASET`)
- Test: `~/d/science/science/tests/test_commons_promote_kind_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_commons_promote_kind_config.py — append
def test_promote_kind_dataset_filter_and_slug_source():
    from science_tool.commons.promote import PROMOTE_KIND_DATASET
    assert PROMOTE_KIND_DATASET.filename_prefix == "data-"
    assert PROMOTE_KIND_DATASET.slug_from_id is True


def test_paper_topic_theme_keep_filename_slug_semantics():
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC, PROMOTE_KIND_THEME,
    )
    for k in (PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC, PROMOTE_KIND_THEME):
        assert k.filename_prefix == ""
        assert k.slug_from_id is False


def test_dataset_discovery_uses_id_slug_when_filename_stem_differs(tmp_path, monkeypatch):
    """data-ccle-proteomics.md with id dataset:ccle-proteomics-nusinow-2020 → slug 'ccle-proteomics-nusinow-2020'."""
    import shutil, subprocess
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    # Rename the fixture file + tweak id so stem != id slug:
    (proj / "doc/datasets/data-fixture-ds.md").rename(
        proj / "doc/datasets/data-fixture.md"
    )
    f = proj / "doc/datasets/data-fixture.md"
    text = f.read_text(encoding="utf-8")
    text = text.replace(
        "id: dataset:fixture-ds", "id: dataset:fixture-ds-2026-01"
    )
    f.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", lambda s: proj,
    )
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    # Discovery key is the id slug, NOT the filename stem after data- strip:
    assert "fixture-ds-2026-01" in discovery.candidates_by_slug
    assert "fixture" not in discovery.candidates_by_slug   # stem-derived would be wrong


def test_dataset_discovery_skips_files_without_filename_prefix(tmp_path, monkeypatch):
    """A file under doc/datasets/ without the 'data-' prefix is silently skipped."""
    import shutil, subprocess
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    # Add a bare-named file (no data- prefix):
    (proj / "doc/datasets/notes.md").write_text(
        "---\nid: misc:ignore-me\ntype: note\n---\n", encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", lambda s: proj,
    )
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    # notes.md was filtered out (not "data-"-prefixed); not in candidates or failures:
    assert "ignore-me" not in discovery.candidates_by_slug
    assert all(
        "notes.md" not in str(fc.source_path) for fc in discovery.failed_candidates
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_kind_config.py -v -k "filter_and_slug_source or filename_slug_semantics or uses_id_slug or skips_files_without"
```
Expected: 4 failures.

- [ ] **Step 3: Extend `PromoteKindConfig` + update `_scan_project`**

In `promote.py`:

```python
@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    # ...existing fields...
    filename_prefix: str = ""        # NEW — file stem must start with this prefix (filter)
    slug_from_id: bool = False        # NEW — when True, slug comes from id frontmatter, not stem
```

Update `_scan_project`:

1. **Filename filter** (early in the per-file loop, before existing slug-from-stem logic):
   ```python
   if kind.filename_prefix and not source_path.stem.startswith(kind.filename_prefix):
       continue   # silently skip — not a candidate for this kind
   ```

2. **Slug derivation** when `slug_from_id=True`: after the existing `id` parsing (around `promote.py:1189`), use the id-derived slug as the authoritative slug and skip the cross-check. Concretely, change the existing block:
   ```python
   if id_slug_normalized != slug_normalized:
       failures.append(FailedCandidate(... "id does not match filename stem" ...))
       continue
   ```
   to:
   ```python
   if kind.slug_from_id:
       # Filename is filter-only for this kind. Authoritative slug = id slug.
       slug_normalized = id_slug_normalized
   elif id_slug_normalized != slug_normalized:
       failures.append(FailedCandidate(... existing ...))
       continue
   ```

   And handle the case where `slug_from_id=True` but the file has no `id:` field — fail-fast with a clear FailedCandidate, since there's no way to derive a slug:
   ```python
   if kind.slug_from_id and not isinstance(id_val, str):
       failures.append(FailedCandidate(
           slug=None, project_slug=project_slug,
           source_path=source_path,
           error_class="PromoteCandidateError",
           error_message=(
               f"dataset entity at {source_path} requires explicit 'id:' field "
               f"(kind {kind.kind!r} derives slug from id, not filename)"
           ),
       ))
       continue
   ```

3. `_normalize_slug_for_match` stays unchanged for paper/topic/theme. For dataset, when called on the **filename stem**, it doesn't need to know about `filename_prefix` because the filter check above already enforced membership. However, if a downstream caller passes a stem like `data-something`, the regex (lowercase-kebab-only) will reject it because `data-something` contains the literal prefix. So extend `_normalize_slug_for_match` to also strip `kind.filename_prefix` for safety (paper/topic/theme are unaffected since their prefix is `""`):
   ```python
   def _normalize_slug_for_match(raw: str, kind: PromoteKindConfig) -> str:
       stripped = raw.removesuffix(".md").strip()
       if kind.filename_prefix and stripped.startswith(kind.filename_prefix):
           stripped = stripped[len(kind.filename_prefix):]
       if not stripped:
           raise PromoteCandidateError(f"slug {raw!r} is empty after strip")
       if not kind.slug_regex.match(stripped):
           raise PromoteCandidateError(f"slug {raw!r} does not match {kind.slug_regex.pattern}")
       if kind.slug_match == "casefold":
           return stripped.casefold()
       return stripped
   ```

Update `PROMOTE_KIND_DATASET` to set both new fields:

```python
PROMOTE_KIND_DATASET = PromoteKindConfig(
    # ...existing fields...
    filename_prefix="data-",
    slug_from_id=True,
)
```

- [ ] **Step 4: Run tests + regressions**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_kind_config.py tests/test_commons_promote_apply.py tests/test_commons_promote_topic_apply.py tests/test_commons_promote_theme_apply.py tests/test_commons_promote_discovery.py -v
```
Expected: all passing. The paper/topic/theme regressions confirm the new fields with their defaults (`""` / `False`) preserve existing behavior.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_kind_config.py
git commit -m "commons(promote): filename_prefix filter + slug_from_id for datasets"
```

---

### Task 8: Add `PromoteResourceMissingError`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/errors.py`
- Test: `~/d/science/science/tests/test_commons_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_errors.py — append
def test_promote_resource_missing_error_carries_slug_and_paths():
    from pathlib import Path
    from science_tool.commons.errors import PromoteResourceMissingError
    err = PromoteResourceMissingError(
        slug="fixture-ds",
        resource_name="r1.txt",
        resource_path=Path("/abs/path/r1.txt"),
    )
    assert err.slug == "fixture-ds"
    assert err.resource_name == "r1.txt"
    assert err.resource_path == Path("/abs/path/r1.txt")
    assert "fixture-ds" in str(err)
    assert "r1.txt" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `ImportError`.

- [ ] **Step 3: Add the error class to `errors.py`**

```python
class PromoteResourceMissingError(CommonsError):
    """A resources[].path entry in a project datapackage doesn't resolve.

    Recorded as a FailedCandidate during discovery; does not abort the run.
    """
    def __init__(
        self,
        *,
        slug: str,
        resource_name: str,
        resource_path: Path,
    ) -> None:
        self.slug = slug
        self.resource_name = resource_name
        self.resource_path = resource_path
        super().__init__(
            f"dataset {slug!r}: resource {resource_name!r} at "
            f"{resource_path} does not exist"
        )
```

- [ ] **Step 4: Run the test**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_errors.py::test_promote_resource_missing_error_carries_slug_and_paths -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/errors.py tests/test_commons_errors.py
git commit -m "commons(errors): add PromoteResourceMissingError for dataset discovery"
```

---

### Task 9: Build dataset discovery fixture

**Files:**
- Create: `~/d/science/science/tests/fixtures/promote/proj-dataset/doc/datasets/data-fixture-ds.md`
- Create: `~/d/science/science/tests/fixtures/promote/proj-dataset/data/fixture-ds/datapackage.json`
- Create: `~/d/science/science/tests/fixtures/promote/proj-dataset/data/fixture-ds/r1.txt`
- Create: `~/d/science/science/tests/fixtures/promote/proj-dataset/data/fixture-ds/r2.txt`

- [ ] **Step 1: Create the fixture project structure**

```bash
cd ~/d/science/science/tests/fixtures/promote
mkdir -p proj-dataset/doc/datasets proj-dataset/data/fixture-ds
```

- [ ] **Step 2: Write `data-fixture-ds.md`**

```markdown
---
id: dataset:fixture-ds
type: dataset
title: "Fixture dataset"
description: "Synthetic fixture for Phase G tests."
datapackage: data/fixture-ds/datapackage.json
origin: external
tier: evaluate-next
access:
  level: public
  verified: true
created: "2026-05-18"
updated: "2026-05-18"
tags:
  - test
ontologies:
  - test-ontology
---

# Fixture dataset

Project-only body content goes here.
```

(`ontologies` is intentionally present so the field-routing tests can assert it lands in `dropped_fields`.)

- [ ] **Step 3: Write `r1.txt` and `r2.txt`**

```bash
cd ~/d/science/science/tests/fixtures/promote/proj-dataset/data/fixture-ds
printf 'hello world\n' > r1.txt        # 12 bytes
printf '0123456789012345678901234567890123456\n' > r2.txt   # 37 bytes
```

Verify byte counts:
```bash
wc -c r1.txt r2.txt
```
Expected: `12 r1.txt`, `37 r2.txt`.

- [ ] **Step 4: Write `datapackage.json`**

```json
{
  "name": "fixture-ds",
  "resources": [
    {
      "name": "r1",
      "path": "r1.txt",
      "format": "txt",
      "mediatype": "text/plain"
    },
    {
      "name": "r2",
      "path": "r2.txt",
      "format": "txt",
      "mediatype": "text/plain"
    }
  ]
}
```

Note: project sidecar deliberately omits `hash:` and `bytes:` — promote computes those.

- [ ] **Step 5: Commit fixture**

```bash
cd ~/d/science/science
git add tests/fixtures/promote/proj-dataset/
git commit -m "commons(tests): add proj-dataset fixture for Phase G discovery tests"
```

---

### Task 10: Dataset discovery: classify + validate `datapackage:` + check resources exist

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`discover_candidates`)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_discovery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_dataset_discovery.py — new file
from pathlib import Path
import shutil
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _copy(tmp_path: Path) -> Path:
    dest = tmp_path / "proj-dataset"
    shutil.copytree(FIXTURES / "proj-dataset", dest)
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(dest), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        check=True,
    )
    return dest


def test_dataset_discovery_finds_well_formed_candidate(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates,
    )
    proj = _copy(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert "fixture-ds" in discovery.candidates_by_slug
    assert discovery.failed_candidates == []


def test_dataset_discovery_fails_when_datapackage_field_missing(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates,
    )
    proj = _copy(tmp_path)
    # Strip the datapackage line from the frontmatter
    f = proj / "doc/datasets/data-fixture-ds.md"
    f.write_text(
        f.read_text(encoding="utf-8").replace(
            "datapackage: data/fixture-ds/datapackage.json\n", ""
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.candidates_by_slug == {}
    assert len(discovery.failed_candidates) == 1
    fc = discovery.failed_candidates[0]
    assert fc.slug == "fixture-ds"
    assert "datapackage" in fc.error_message.lower()


def test_dataset_discovery_fails_when_resource_path_missing(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates,
    )
    proj = _copy(tmp_path)
    (proj / "data/fixture-ds/r1.txt").unlink()
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.candidates_by_slug == {}
    fc = discovery.failed_candidates[0]
    assert "r1.txt" in fc.error_message
    assert fc.error_class == "PromoteResourceMissingError"


@pytest.mark.parametrize("missing_field", ["origin", "tier", "access"])
def test_dataset_discovery_fails_on_missing_required_mixin_field(
    tmp_path, monkeypatch, missing_field,
):
    """Design §3.5: discovery fail-fast on missing required mixin fields."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates,
    )
    proj = _copy(tmp_path)
    f = proj / "doc/datasets/data-fixture-ds.md"
    text = f.read_text(encoding="utf-8")
    if missing_field == "origin":
        text = text.replace("origin: external\n", "")
    elif missing_field == "tier":
        text = text.replace("tier: evaluate-next\n", "")
    elif missing_field == "access":
        text = "\n".join(
            ln for ln in text.splitlines()
            if not ln.startswith("access:")
            and not ln.startswith("  level:")
            and not ln.startswith("  verified:")
        ) + "\n"
    f.write_text(text, encoding="utf-8")
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.candidates_by_slug == {}
    assert any(missing_field in fc.error_message for fc in discovery.failed_candidates)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_discovery.py -v
```
Expected: 6 failures (3 base + 3 parametrized) — discovery doesn't yet implement dataset-specific checks.

- [ ] **Step 3: Extend `discover_candidates` with dataset-specific checks**

In `promote.py`, the per-file discovery loop currently extracts frontmatter and runs slug/id checks. Add a dataset-kind branch after the existing checks (key off `kind.kind == "dataset"`):

```python
if kind.kind == "dataset":
    # Required mixin fields (design §3.5):
    origin_value = frontmatter.get("origin")
    missing_mixin: list[str] = []
    for required in ("origin", "tier"):
        if required not in frontmatter:
            missing_mixin.append(required)
    if origin_value == "external" and "access" not in frontmatter:
        missing_mixin.append("access")
    elif origin_value == "derived" and "derivation" not in frontmatter:
        missing_mixin.append("derivation")
    if missing_mixin:
        for mf in missing_mixin:
            failed_candidates.append(FailedCandidate(
                slug=slug, project_slug=project_slug,
                source_path=md_path,
                error_class="PromoteCandidateError",
                error_message=f"dataset entity missing required mixin field {mf!r}",
            ))
        continue

    dp_rel = frontmatter.get("datapackage")
    if not dp_rel:
        failed_candidates.append(FailedCandidate(
            slug=slug, project_slug=project_slug,
            source_path=md_path,
            error_class="PromoteCandidateError",
            error_message=f"dataset entity missing required 'datapackage:' field",
        ))
        continue
    dp_abs = (project_root / dp_rel).resolve()
    if not dp_abs.is_file():
        failed_candidates.append(FailedCandidate(
            slug=slug, project_slug=project_slug,
            source_path=md_path,
            error_class="PromoteCandidateError",
            error_message=f"datapackage path {dp_rel!r} does not resolve to a file",
        ))
        continue
    # Parse and check resource files:
    import json
    try:
        dp_doc = json.loads(dp_abs.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failed_candidates.append(FailedCandidate(
            slug=slug, project_slug=project_slug,
            source_path=dp_abs,
            error_class="PromoteCandidateError",
            error_message=f"datapackage.json parse failed: {exc}",
        ))
        continue
    dp_parent = dp_abs.parent
    missing_resource = None
    for r in dp_doc.get("resources", []):
        rp = (dp_parent / r["path"]).resolve()
        if not rp.is_file():
            missing_resource = (r.get("name", r["path"]), rp)
            break
    if missing_resource is not None:
        failed_candidates.append(FailedCandidate(
            slug=slug, project_slug=project_slug,
            source_path=md_path,
            error_class="PromoteResourceMissingError",
            error_message=(
                f"resource {missing_resource[0]!r} at {missing_resource[1]} "
                f"does not exist"
            ),
        ))
        continue
```

Stash `dp_abs` and `dp_doc` on the `PromoteCandidate` for downstream plan use. Extend `PromoteCandidate` with two optional fields:

```python
datapackage_source_path: Path | None = None
datapackage_doc: dict[str, Any] | None = None
```

(Default `None` so paper/topic/theme remain unchanged.)

- [ ] **Step 4: Run the tests**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_discovery.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_discovery.py
git commit -m "commons(promote): dataset discovery — datapackage field + resource existence"
```

---

## G.3 — Hash compute + plan rendering

### Task 11: Streaming sha256 helper + golden fixture

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/datapackage.py`
- Create: `~/d/science/science/tests/fixtures/promote_dataset/hello.txt`
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the golden fixture**

```bash
cd ~/d/science/science
mkdir -p tests/fixtures/promote_dataset
printf 'hello world\n' > tests/fixtures/promote_dataset/hello.txt
wc -c tests/fixtures/promote_dataset/hello.txt
# expect: 12 tests/fixtures/promote_dataset/hello.txt
sha256sum tests/fixtures/promote_dataset/hello.txt
# expect: a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_commons_promote_dataset_plan.py — new file
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote_dataset"


def test_streaming_sha256_matches_golden_fixture():
    from science_tool.commons.datapackage import stream_sha256_and_bytes
    h, n = stream_sha256_and_bytes(FIXTURES / "hello.txt")
    assert h == "sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    assert n == 12


def test_streaming_sha256_uses_1MiB_chunks(tmp_path):
    """Determinism check on a multi-chunk file."""
    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00" * (1024 * 1024 + 7))   # one full chunk + 7 bytes
    from science_tool.commons.datapackage import stream_sha256_and_bytes
    h, n = stream_sha256_and_bytes(big)
    assert n == 1024 * 1024 + 7
    import hashlib
    expected = hashlib.sha256(b"\x00" * n).hexdigest()
    assert h == f"sha256:{expected}"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py -v -k sha256
```
Expected: `ImportError`.

- [ ] **Step 4: Add `stream_sha256_and_bytes` to `datapackage.py`**

```python
def stream_sha256_and_bytes(path: Path) -> tuple[str, int]:
    """Return (`sha256:<hex>`, byte_count) streaming the file in 1 MiB chunks."""
    import hashlib
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            n += len(chunk)
    return f"sha256:{h.hexdigest()}", n
```

- [ ] **Step 5: Run tests + commit**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py -v -k sha256
# expect: 2 passed
git add src/science_tool/commons/datapackage.py tests/fixtures/promote_dataset/ tests/test_commons_promote_dataset_plan.py
git commit -m "commons(datapackage): add stream_sha256_and_bytes helper + golden fixture"
```

---

### Task 12: Canonical `datapackage.yaml` rendering

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/datapackage.py` (add render + parse helpers)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_dataset_plan.py — append
def test_render_canonical_datapackage_strips_project_fields_and_injects_hashes():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml
    project_doc = {
        "name": "mm30-external-ccle-proteomics-2020-01",
        "conformsTo": "mm30",                              # project-only, must strip
        "mm30": {"external_source": "Nusinow 2020"},       # project-only, must strip
        "resources": [
            {
                "name": "r1",
                "path": "r1.txt",
                "format": "txt",
                "schema": {"fields": []},                  # opaque, preserved
            }
        ],
    }
    hashes = {"r1": ("sha256:abc123", 42)}
    yaml_text = render_canonical_datapackage_yaml(
        project_doc=project_doc,
        canonical_slug="fixture-ds",
        per_resource=hashes,
    )
    import yaml as pyyaml
    parsed = pyyaml.safe_load(yaml_text)
    assert parsed["name"] == "fixture-ds"
    assert "conformsTo" not in parsed
    assert "mm30" not in parsed
    r = parsed["resources"][0]
    assert r["hash"] == "sha256:abc123"
    assert r["bytes"] == 42
    assert r["schema"] == {"fields": []}        # opaque pass-through


def test_parse_canonical_datapackage_yaml_round_trip():
    """parse_canonical_datapackage_yaml validates the required dataset fields."""
    from science_tool.commons.datapackage import parse_canonical_datapackage_yaml
    yaml_text = """\
name: fixture-ds
resources:
  - name: r1
    path: r1.txt
    hash: sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447
    bytes: 12
"""
    desc = parse_canonical_datapackage_yaml(yaml_text)
    assert desc["name"] == "fixture-ds"
    assert desc["resources"][0]["hash"].startswith("sha256:")
    assert desc["resources"][0]["bytes"] == 12


def test_parse_canonical_datapackage_yaml_rejects_missing_hash():
    from science_tool.commons.datapackage import parse_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest
    yaml_text = """\
name: fixture-ds
resources:
  - name: r1
    path: r1.txt
"""
    with pytest.raises(CommonsError, match="hash"):
        parse_canonical_datapackage_yaml(yaml_text)
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: `ImportError` or AttributeError on `render_canonical_datapackage_yaml` / `parse_canonical_datapackage_yaml`.

- [ ] **Step 3: Add render + parse helpers to `datapackage.py`**

```python
import re
import yaml as _yaml

_PROJECT_ONLY_DATAPACKAGE_KEYS = frozenset({
    "conformsTo", "mm30", "derivedFrom",   # project-specific extensions
})

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def render_canonical_datapackage_yaml(
    *,
    project_doc: dict,
    canonical_slug: str,
    per_resource: dict[str, tuple[str, int]],
) -> str:
    """Render the canonical datapackage.yaml from a project datapackage.json.

    - Strips project-only keys (conformsTo, mm30, derivedFrom in path form).
    - Resets name to canonical_slug.
    - Injects hash + bytes per resource using per_resource[resource_name].
    - Preserves all other resource fields (schema, dialect, etc.) opaquely.
    """
    out: dict = {"name": canonical_slug}
    for k, v in project_doc.items():
        if k in _PROJECT_ONLY_DATAPACKAGE_KEYS or k in {"name", "resources"}:
            continue
        out[k] = v
    resources = []
    for r in project_doc.get("resources", []):
        merged = dict(r)
        rname = r.get("name") or r.get("path")
        if rname in per_resource:
            h, n = per_resource[rname]
            merged["hash"] = h
            merged["bytes"] = n
        resources.append(merged)
    out["resources"] = resources
    return _yaml.safe_dump(out, sort_keys=False, allow_unicode=True)


def parse_canonical_datapackage_yaml(yaml_text: str) -> dict:
    """Parse + validate a canonical datapackage.yaml.

    Required: name, resources[].path, resources[].hash matching sha256:<64hex>,
    resources[].bytes is a non-negative int. Unknown fields preserved.
    Raises CommonsError on validation failure.
    """
    from science_tool.commons.errors import CommonsError
    try:
        doc = _yaml.safe_load(yaml_text)
    except _yaml.YAMLError as exc:
        raise CommonsError(f"datapackage YAML parse failed: {exc}") from exc
    if not isinstance(doc, dict):
        raise CommonsError("datapackage YAML root must be a mapping")
    if "name" not in doc:
        raise CommonsError("datapackage missing 'name'")
    resources = doc.get("resources")
    if not isinstance(resources, list) or not resources:
        raise CommonsError("datapackage resources must be a non-empty list")
    seen_paths = set()
    for r in resources:
        if not isinstance(r, dict):
            raise CommonsError("resource entry must be a mapping")
        p = r.get("path")
        if not p or not isinstance(p, str):
            raise CommonsError("resource missing 'path'")
        if p in seen_paths:
            raise CommonsError(f"duplicate resource path {p!r}")
        seen_paths.add(p)
        h = r.get("hash")
        if not isinstance(h, str) or not _SHA256_RE.match(h):
            raise CommonsError(
                f"resource {p!r} hash must match sha256:<64 hex>, got {h!r}"
            )
        b = r.get("bytes")
        if not isinstance(b, int) or b < 0:
            raise CommonsError(f"resource {p!r} bytes must be non-negative int")
    return doc
```

- [ ] **Step 4: Run the tests**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py -v -k "datapackage"
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/datapackage.py tests/test_commons_promote_dataset_plan.py
git commit -m "commons(datapackage): canonical datapackage.yaml render + parse helpers"
```

---

### Task 13: Canonical `entity.md` rendering — reuse `_render_canonical` with dataset post-process

**Design decision:** Do NOT write a parallel `_render_dataset_canonical_entity`. The existing `_render_canonical` (`promote.py:1519`) already emits the required base fields — `schema_profile`, `id`, `type`, `title`, `version`, `created`, `updated` — and routes the rest from `canonical_fields`. For datasets, the only delta is: inject `datapackage: "datapackage.yaml"` (the sibling pointer) and ensure dataset-allowed fields make it through `_classify_entity`'s split. Add a tiny post-process step that overrides the `datapackage:` value in the rendered canonical frontmatter and verify `schema_profile`/`version` come through.

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (small post-process injection in the dataset plan branch — wired up in Task 16)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the failing tests** (these are integration-level — assert on the artifact produced by `plan_promote`, since rendering reuses existing infrastructure)

```python
# tests/test_commons_promote_dataset_plan.py — append
def _plan_one(tmp_path, monkeypatch):
    """Helper: discover + plan the fixture project. Returns the single decision."""
    import shutil, subprocess
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", lambda s: proj,
    )
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates, plan_promote,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    return plan.decisions[0], plan, commons


def test_dataset_canonical_entity_emits_required_base_fields(tmp_path, monkeypatch):
    """schema_profile + version come from _render_canonical; never project frontmatter."""
    import yaml as pyyaml
    d, _, _ = _plan_one(tmp_path, monkeypatch)
    entity = next(a for a in d.canonical_artifacts if a.path.name == "entity.md")
    head, _, _ = entity.content.partition("---\n")[2].partition("\n---\n")
    fm = pyyaml.safe_load(head)
    assert fm["schema_profile"] == "science-entity-base/1.0+dataset/1.0"
    assert fm["version"] == "1.0.0"
    assert fm["id"] == "dataset:fixture-ds"
    assert fm["type"] == "dataset"


def test_dataset_canonical_entity_datapackage_points_at_sibling(tmp_path, monkeypatch):
    """canonical datapackage: points at the sibling 'datapackage.yaml', not the project path."""
    import yaml as pyyaml
    d, _, _ = _plan_one(tmp_path, monkeypatch)
    entity = next(a for a in d.canonical_artifacts if a.path.name == "entity.md")
    head, _, _ = entity.content.partition("---\n")[2].partition("\n---\n")
    fm = pyyaml.safe_load(head)
    assert fm["datapackage"] == "datapackage.yaml"


def test_dataset_canonical_entity_preserves_tier_verbatim(tmp_path, monkeypatch):
    """tier is user-authored; promote never overwrites."""
    d, _, _ = _plan_one(tmp_path, monkeypatch)
    entity = next(a for a in d.canonical_artifacts if a.path.name == "entity.md")
    assert "tier: evaluate-next" in entity.content


def test_dataset_canonical_entity_body_is_preserved(tmp_path, monkeypatch):
    """Body content from project entity (intro paragraph) survives into canonical."""
    d, _, _ = _plan_one(tmp_path, monkeypatch)
    entity = next(a for a in d.canonical_artifacts if a.path.name == "entity.md")
    # Fixture data-fixture-ds.md body is "# Fixture dataset\n\nProject-only body content goes here.\n"
    # _classify_entity will route the H1 line + intro paragraph to canonical_body[""]
    # and _render_body will emit them back. At minimum, the prose line survives:
    _, _, body = entity.content.partition("---\n")[2].partition("\n---\n")
    assert "Project-only body content goes here" in body or "Fixture dataset" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py -v -k "canonical_entity or canonical_dataset or body_is_preserved"
```
Expected: failures (the dataset plan branch hasn't yet wired the canonical render — that's Task 16).

- [ ] **Step 3: No code in this task**

This task defines the assertions. The implementation lands in Task 16 (which wires `_render_canonical` plus the `datapackage: "datapackage.yaml"` post-process). Leave the tests in place — they'll pass after Task 16.

- [ ] **Step 4: Mark tests xfail temporarily**

If running the full suite during G.3, mark these four tests `@pytest.mark.xfail(reason="lands in Task 16")` until Task 16 lands. Remove the marker in Task 16's commit.

- [ ] **Step 5: Commit the test scaffolding**

```bash
cd ~/d/science/science
git add tests/test_commons_promote_dataset_plan.py
git commit -m "commons(tests): scaffold dataset canonical entity render assertions (Task 16 wires)"
```

---

### Task 14: Recipe stub content (v1: always stubbed)

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`_render_dataset_recipe_stub`)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_dataset_plan.py — append
def test_render_dataset_recipe_stub_content():
    from science_tool.commons.promote import _render_dataset_recipe_stub
    text = _render_dataset_recipe_stub(
        slug="fixture-ds",
        source_hint="Nusinow 2020 CCLE proteomics",
    )
    assert "Recipe back-fill needed" in text
    assert "Nusinow 2020" in text
    assert "<source>" not in text   # no template placeholders


def test_render_dataset_recipe_stub_handles_missing_source_hint():
    from science_tool.commons.promote import _render_dataset_recipe_stub
    text = _render_dataset_recipe_stub(slug="fixture-ds", source_hint=None)
    assert "Recipe back-fill needed" in text
    assert "unspecified" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: `ImportError`.

- [ ] **Step 3: Implement the renderer**

```python
def _render_dataset_recipe_stub(*, slug: str, source_hint: str | None) -> str:
    src_line = f"Acquisition: {source_hint}." if source_hint else "Acquisition: unspecified."
    return (
        "# Recipe back-fill needed\n\n"
        f"{src_line}\n\n"
        "Promote stubbed this README because no project recipe was detected. "
        "Replace with the acquisition or preprocessing workflow.\n"
    )
```

- [ ] **Step 4: Run + commit**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py -v -k recipe_stub
# expect: 2 passed
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_plan.py
git commit -m "commons(promote): dataset recipe stub renderer"
```

---

### Task 15: Compute `dropped_fields` from existing `_classify_entity` output

**Design decision:** Reuse the existing `_classify_entity` (`promote.py:1303`), which already routes fields into `(canonical_fields, project_only_fields, canonical_body, project_only_body)` using the merge-policy table for the kind. For datasets we need one extra output: the names of project frontmatter keys that ended up in neither bucket (because they're not in any schema). That set goes into the audit log under `dropped_fields`. Compute it as a derivation from `_classify_entity`'s output rather than a parallel classifier.

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (add `_dataset_dropped_fields` helper)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_dataset_plan.py — append
def test_dataset_dropped_fields_records_unrouted_keys():
    """Project keys not in canonical or overlay buckets are recorded as dropped."""
    from science_tool.commons.promote import _dataset_dropped_fields
    raw_fm = {
        "id": "dataset:x", "type": "dataset", "title": "T",
        "datapackage": "data/x/datapackage.json",
        "origin": "external", "tier": "track",
        "access": {"level": "public", "verified": True},
        "tags": ["a"],
        "ontologies": ["bio"],            # not in any schema → dropped
        "datasets": ["dataset:y"],         # not allowed on a dataset entity → dropped
        "pin_version": "1.0.0",            # overlay
        "relevance": "high",               # overlay
    }
    canonical_fields = {"id": "dataset:x", "type": "dataset", "title": "T",
                        "datapackage": "data/x/datapackage.json",
                        "origin": "external", "tier": "track",
                        "access": {"level": "public", "verified": True},
                        "tags": ["a"]}
    project_only_fields = {"pin_version": "1.0.0", "relevance": "high"}
    dropped = _dataset_dropped_fields(
        raw_fm,
        canonical_fields=canonical_fields,
        project_only_fields=project_only_fields,
    )
    assert set(dropped) == {"ontologies", "datasets"}
```

- [ ] **Step 2: Run test — should fail**

Expected: `ImportError`.

- [ ] **Step 3: Implement `_dataset_dropped_fields`**

```python
def _dataset_dropped_fields(
    raw_frontmatter: dict,
    *,
    canonical_fields: dict,
    project_only_fields: dict,
) -> list[str]:
    """Return project frontmatter keys that landed in neither bucket.

    These are keys not recognized by base, dataset mixin, or overlay-1.1 schemas;
    promote drops them silently from the output but records them in the audit
    log so users can audit pre-migration cleanups (design §3.3 'dropped with
    audit' bucket).

    Convention: any key starting with `_` is treated as intentional metadata
    and not reported (e.g. `_raw_frontmatter__` sentinel).
    """
    routed = set(canonical_fields) | set(project_only_fields)
    return sorted(
        k for k in raw_frontmatter
        if k not in routed and not k.startswith("_")
    )
```

- [ ] **Step 4: Run + commit**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py::test_dataset_dropped_fields_records_unrouted_keys -v
# expect: PASS
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_plan.py
git commit -m "commons(promote): _dataset_dropped_fields helper for audit log"
```

---

### Task 16: Wire dataset plan_promote — build artifacts + overlay + dropped_fields audit data

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`plan_promote` — dataset branch)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the failing integration-style test (still plan-only — no apply)**

```python
# tests/test_commons_promote_dataset_plan.py — append
def test_plan_promote_dataset_produces_three_artifacts(tmp_path, monkeypatch):
    """A planned dataset decision carries 3 artifacts: entity.md, datapackage.yaml, recipe/README.md."""
    import shutil, subprocess
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates, plan_promote,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    assert len(plan.decisions) == 1
    d = plan.decisions[0]
    paths = sorted(str(a.path) for a in d.canonical_artifacts)
    assert paths == [
        "datasets/fixture-ds/datapackage.yaml",
        "datasets/fixture-ds/entity.md",
        "datasets/fixture-ds/recipe/README.md",
    ]
    by_path = {str(a.path): a for a in d.canonical_artifacts}
    assert by_path["datasets/fixture-ds/entity.md"].validator == "entity-mixin"
    assert by_path["datasets/fixture-ds/datapackage.yaml"].validator == "frictionless-datapackage"
    assert by_path["datasets/fixture-ds/recipe/README.md"].validator == "plain"
    # tier verbatim
    assert "tier: evaluate-next" in by_path["datasets/fixture-ds/entity.md"].content
    # hash injected on real bytes
    dp_text = by_path["datasets/fixture-ds/datapackage.yaml"].content
    assert "sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447" in dp_text
    # bytes injected
    assert "bytes: 12" in dp_text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py::test_plan_promote_dataset_produces_three_artifacts -v
```
Expected: FAIL — plan_promote doesn't yet branch on dataset.

- [ ] **Step 3: Add dataset branch to `plan_promote` — reuse `_render_canonical` and `_render_overlay`**

In `plan_promote`, the existing path for paper/topic/theme runs through `_render_canonical` (which already emits `schema_profile`, `id`, `type`, `title`, `version`, `created`, `updated`) and `_render_overlay`. For datasets, reuse both. The dataset delta is:
- Three artifacts instead of one (entity.md + datapackage.yaml + recipe/README.md).
- Post-process the entity canonical content to override `datapackage:` with the sibling pointer `"datapackage.yaml"` (the project's value is the project-relative project sidecar path).
- Stash `dropped_fields`, `per_resource`, and `recipe_stubbed` on a side-channel `PromotePlan.dataset_audit_extras` keyed by slug (since `PromoteDecision` is frozen).

```python
if kind.kind == "dataset":
    # 1. Compute hashes per resource
    from science_tool.commons.datapackage import (
        stream_sha256_and_bytes,
        render_canonical_datapackage_yaml,
    )
    dp_doc = candidate.datapackage_doc
    dp_parent = candidate.datapackage_source_path.parent
    per_resource: dict[str, tuple[str, int]] = {}
    for r in dp_doc["resources"]:
        rp = dp_parent / r["path"]
        h, n = stream_sha256_and_bytes(rp)
        per_resource[r.get("name") or r["path"]] = (h, n)

    # 2. Use existing infrastructure for canonical entity + overlay rendering.
    # _classify_entity already split fields/body for the candidate. Build the
    # canonical artifact path via the existing _render_canonical, then
    # post-process to swap the project-relative datapackage path for the
    # sibling pointer 'datapackage.yaml'.
    canonical_path_singleton = (
        commons_root / kind.commons_subdir / candidate.slug / "entity.md"
    )
    # Temporary singular decision to feed _render_canonical (which expects a
    # PromoteDecision shape for slug + version). We rebuild artifacts after.
    tmp_decision = PromoteDecision(
        slug=candidate.slug,
        canonical_artifacts=[],   # filled below
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    entity_text = _render_canonical(
        tmp_decision,
        canonical_fields=candidate.canonical_fields,
        canonical_body=candidate.canonical_body,
        created=_extract_date_for_canonical(candidate, "created"),
        updated=_extract_date_for_canonical(candidate, "updated"),
        kind=kind,
    )
    # Override datapackage: -> 'datapackage.yaml' (sibling pointer)
    entity_text = _override_canonical_datapackage_pointer(entity_text)

    datapackage_text = render_canonical_datapackage_yaml(
        project_doc=dp_doc,
        canonical_slug=candidate.slug,
        per_resource=per_resource,
    )
    recipe_text = _render_dataset_recipe_stub(
        slug=candidate.slug,
        source_hint=candidate.canonical_fields.get("source") or (
            candidate.canonical_fields.get("access") or {}
        ).get("source_url"),
    )

    artifacts = [
        CanonicalArtifact(
            path=Path(f"{kind.commons_subdir}/{candidate.slug}/entity.md"),
            content=entity_text,
            validator="entity-mixin",
        ),
        CanonicalArtifact(
            path=Path(f"{kind.commons_subdir}/{candidate.slug}/datapackage.yaml"),
            content=datapackage_text,
            validator="frictionless-datapackage",
        ),
        CanonicalArtifact(
            path=Path(f"{kind.commons_subdir}/{candidate.slug}/recipe/README.md"),
            content=recipe_text,
            validator="plain",
        ),
    ]

    # 3. Overlay rewrite via existing _render_overlay (reuses project_only_*).
    overlay_text = _render_overlay(
        tmp_decision,
        project_only_fields=candidate.project_only_fields,
        project_only_body=candidate.project_only_body,
        kind=kind,
    )
    overlay_rewrite = OverlayRewrite(
        project_slug=candidate.project_slug,
        path=candidate.overlay_source_path,
        before_sha=_existing_helper_for_before_sha(candidate),
        after_content=overlay_text,
        pin_version="1.0.0",
    )

    decision = PromoteDecision(
        slug=candidate.slug,
        canonical_artifacts=artifacts,
        canonical_version="1.0.0",
        overlays={candidate.project_slug: overlay_rewrite},
        resolved_conflicts=(),
    )

    # 4. Stash audit extras on the plan (frozen decisions can't carry them).
    raw_fm = candidate.canonical_fields | candidate.project_only_fields
    dropped = _dataset_dropped_fields(
        raw_fm,
        canonical_fields=candidate.canonical_fields,
        project_only_fields=candidate.project_only_fields,
    )
    plan.dataset_audit_extras[candidate.slug] = {
        "per_resource": per_resource,
        "dropped_fields": dropped,
        "recipe_stubbed": True,   # v1 always stubs
        "override_path": str(dp_parent),
    }
```

Add the two small helpers used above to `promote.py`:

```python
def _override_canonical_datapackage_pointer(entity_text: str) -> str:
    """Replace the datapackage: line in the rendered canonical frontmatter
    with the sibling pointer 'datapackage.yaml'."""
    head, sep_open, rest = entity_text.partition("---\n")
    if not sep_open:
        return entity_text
    fm_text, sep_close, body = rest.partition("\n---\n")
    if not sep_close:
        return entity_text
    fm = _yaml.safe_load(fm_text) or {}
    fm["datapackage"] = "datapackage.yaml"
    new_fm = _render_frontmatter(fm)
    return f"---\n{new_fm}---\n{body}"


def _extract_date_for_canonical(candidate: PromoteCandidate, key: str) -> "date":
    """Pull a 'created'/'updated' value off the candidate. Reuses the existing
    _coerce_date_for_yaml / _classify_entity routing (created/updated are
    schema-tagged project_only but appear on canonical too — see _render_canonical)."""
    from datetime import date as _date
    raw = (
        candidate.canonical_fields.get(key)
        or candidate.project_only_fields.get(key)
        or _date.today().isoformat()
    )
    if isinstance(raw, str):
        return _date.fromisoformat(raw)
    return raw   # assume datetime.date
```

`_existing_helper_for_before_sha(candidate)` is whatever helper Phase F already uses to compute `OverlayRewrite.before_sha` — locate it in `promote.py` (search for `before_sha=` in the existing plan branch) and reuse.

Extend `PromotePlan` with the side-channel:

```python
@dataclass(slots=True)   # NOT frozen — we mutate dataset_audit_extras
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    kind: PromoteKindConfig
    dataset_audit_extras: dict[str, dict] = field(default_factory=dict)
```

(If unfreezing the dataclass breaks the immutability invariant elsewhere, alternative: keep frozen but use `object.__setattr__` to set the attribute once at construction. Pick whichever causes fewer cascade test failures — the existing test suite will tell you.)

- [ ] **Step 4: Run the test + remove Task 13's xfail markers**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py::test_plan_promote_dataset_produces_three_artifacts -v
```
Expected: PASS.

Then remove the `@pytest.mark.xfail(reason="lands in Task 16")` decorators added in Task 13 Step 4 (four tests: `test_dataset_canonical_entity_emits_required_base_fields`, `_datapackage_points_at_sibling`, `_preserves_tier_verbatim`, `_body_is_preserved`). Re-run:

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_plan.py
git commit -m "commons(promote): dataset plan_promote — 3 artifacts via _render_canonical + sibling datapackage pointer"
```

---

## G.4 — Per-machine override side-channel

### Task 17: Add `PromoteOverrideConflictError`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/errors.py`
- Test: `~/d/science/science/tests/test_commons_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_errors.py — append
def test_promote_override_conflict_error_carries_slug_and_paths():
    from pathlib import Path
    from science_tool.commons.errors import PromoteOverrideConflictError
    err = PromoteOverrideConflictError(
        slug="fixture-ds",
        existing_path=Path("/data/old"),
        planned_path=Path("/data/new"),
    )
    assert err.slug == "fixture-ds"
    assert err.existing_path == Path("/data/old")
    assert err.planned_path == Path("/data/new")
    assert "fixture-ds" in str(err)
    assert "/data/old" in str(err)
    assert "/data/new" in str(err)
```

- [ ] **Step 2: Run test — should fail**

Expected: `ImportError`.

- [ ] **Step 3: Add the error class**

```python
class PromoteOverrideConflictError(CommonsError):
    """~/.config/science/data.yaml already maps this slug to a different path."""

    def __init__(
        self,
        *,
        slug: str,
        existing_path: Path,
        planned_path: Path,
    ) -> None:
        self.slug = slug
        self.existing_path = existing_path
        self.planned_path = planned_path
        super().__init__(
            f"override for dataset {slug!r}: existing {existing_path} "
            f"≠ planned {planned_path}"
        )
```

- [ ] **Step 4: Run + commit**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_errors.py::test_promote_override_conflict_error_carries_slug_and_paths -v
# expect: PASS
git add src/science_tool/commons/errors.py tests/test_commons_errors.py
git commit -m "commons(errors): add PromoteOverrideConflictError"
```

---

### Task 18: Atomic upsert + backup helpers for `~/.config/science/data.yaml`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/config.py`
- Test: `~/d/science/science/tests/test_commons_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_commons_config.py — append
def test_upsert_data_override_creates_file_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from science_tool.commons.config import upsert_data_override
    backup_path = upsert_data_override(
        slug="x", absolute_path=tmp_path / "fakedata", op_id="op123",
    )
    yaml_path = tmp_path / "science" / "data.yaml"
    assert yaml_path.is_file()
    import yaml
    parsed = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert parsed == {"x": str(tmp_path / "fakedata")}
    # When no prior file existed, an "absent" sentinel is written
    # (so restore can unlink data.yaml rather than recreate it empty):
    sentinel = tmp_path / "science" / "data.yaml.bak.op123.absent"
    assert sentinel.is_file()
    # The .bak.<op-id> file itself is NOT created in the absent-before case:
    assert not (tmp_path / "science" / "data.yaml.bak.op123").exists()


def test_restore_data_override_unlinks_when_absent_sentinel_present(tmp_path, monkeypatch):
    """Round-trip: upsert into absent data.yaml, then restore → data.yaml gone."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from science_tool.commons.config import (
        upsert_data_override, restore_data_override_from_backup,
    )
    yaml_path = tmp_path / "science" / "data.yaml"
    assert not yaml_path.exists()
    upsert_data_override(
        slug="x", absolute_path=tmp_path / "fakedata", op_id="opABS",
    )
    assert yaml_path.is_file()
    restore_data_override_from_backup(op_id="opABS")
    # Byte-identical restore: file must be gone, sentinel cleaned up:
    assert not yaml_path.exists()
    assert not (tmp_path / "science" / "data.yaml.bak.opABS.absent").exists()


def test_upsert_data_override_preserves_existing_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "science").mkdir()
    yaml_path = tmp_path / "science" / "data.yaml"
    yaml_path.write_text("other: /other/path\n", encoding="utf-8")
    from science_tool.commons.config import upsert_data_override
    upsert_data_override(slug="x", absolute_path=tmp_path / "newdata", op_id="op999")
    import yaml
    parsed = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert parsed == {"other": "/other/path", "x": str(tmp_path / "newdata")}
    # Backup retains pre-upsert content:
    bak = tmp_path / "science" / "data.yaml.bak.op999"
    assert bak.read_text(encoding="utf-8") == "other: /other/path\n"


def test_check_override_conflict_raises_on_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "science").mkdir()
    (tmp_path / "science" / "data.yaml").write_text(
        "x: /existing/path\n", encoding="utf-8"
    )
    from science_tool.commons.config import check_override_conflict
    from science_tool.commons.errors import PromoteOverrideConflictError
    import pytest
    with pytest.raises(PromoteOverrideConflictError):
        check_override_conflict(slug="x", planned_path=tmp_path / "different")
    # Same path: no raise
    check_override_conflict(slug="x", planned_path=Path("/existing/path"))


def test_restore_data_override_from_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "science").mkdir()
    yaml_path = tmp_path / "science" / "data.yaml"
    bak_path = tmp_path / "science" / "data.yaml.bak.opABC"
    bak_path.write_text("before: state\n", encoding="utf-8")
    yaml_path.write_text("after: state\n", encoding="utf-8")
    from science_tool.commons.config import restore_data_override_from_backup
    restore_data_override_from_backup(op_id="opABC")
    assert yaml_path.read_text(encoding="utf-8") == "before: state\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: `ImportError` on the three new helpers.

- [ ] **Step 3: Add the helpers to `config.py`**

```python
import os
import shutil
import tempfile

def _data_yaml_path() -> Path:
    return get_science_config_dir() / "data.yaml"


def upsert_data_override(
    *,
    slug: str,
    absolute_path: Path,
    op_id: str,
) -> Path:
    """Backup current data.yaml, then upsert `slug: <absolute_path>`.

    Returns the backup path (always written, even for first-time creation).
    Uses atomic temp-file + rename for the upsert.
    """
    if not absolute_path.is_absolute():
        raise CommonsError(
            f"data override path must be absolute, got {absolute_path}"
        )
    yaml_path = _data_yaml_path()
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    bak = yaml_path.parent / f"data.yaml.bak.{op_id}"
    sentinel = yaml_path.parent / f"data.yaml.bak.{op_id}.absent"
    if yaml_path.is_file():
        shutil.copy2(yaml_path, bak)
    else:
        # Encode "missing before" so restore can unlink rather than recreate empty:
        sentinel.write_text("", encoding="utf-8")
    # Load existing:
    existing: dict[str, str] = {}
    if yaml_path.is_file():
        text = yaml_path.read_text(encoding="utf-8")
        if text.strip():
            loaded = _yaml.safe_load(text)
            if isinstance(loaded, dict):
                existing = {str(k): str(v) for k, v in loaded.items()}
    existing[slug] = str(absolute_path)
    # Atomic rewrite:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(yaml_path.parent),
        prefix="data.yaml.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp_name = tmp.name
        tmp.write("# managed by science commons promote\n")
        _yaml.safe_dump(existing, tmp, sort_keys=True, allow_unicode=True)
    os.replace(tmp_name, yaml_path)
    return bak


def check_override_conflict(*, slug: str, planned_path: Path) -> None:
    """Raise PromoteOverrideConflictError if data.yaml maps slug to another path."""
    from science_tool.commons.errors import PromoteOverrideConflictError
    yaml_path = _data_yaml_path()
    if not yaml_path.is_file():
        return
    text = yaml_path.read_text(encoding="utf-8").strip()
    if not text:
        return
    parsed = _yaml.safe_load(text) or {}
    if not isinstance(parsed, dict):
        return
    existing = parsed.get(slug)
    if existing is None:
        return
    if Path(existing) != planned_path:
        raise PromoteOverrideConflictError(
            slug=slug,
            existing_path=Path(existing),
            planned_path=planned_path,
        )


def restore_data_override_from_backup(*, op_id: str) -> None:
    """Restore data.yaml to its pre-upsert byte-identical state.

    Two cases (encoded by upsert_data_override):
    - data.yaml.bak.<op_id>.absent exists → data.yaml was absent before; unlink
      data.yaml and remove the sentinel.
    - data.yaml.bak.<op_id> exists → atomic-rename it back over data.yaml.
    """
    yaml_path = _data_yaml_path()
    sentinel = yaml_path.parent / f"data.yaml.bak.{op_id}.absent"
    bak = yaml_path.parent / f"data.yaml.bak.{op_id}"
    if sentinel.is_file():
        if yaml_path.exists():
            yaml_path.unlink()
        sentinel.unlink()
        return
    if not bak.is_file():
        raise CommonsError(f"backup not found: {bak}")
    os.replace(bak, yaml_path)
```

Ensure `_yaml` (or `yaml`) is imported at module level.

- [ ] **Step 4: Run all four tests**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_config.py -v -k "override or upsert or restore"
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/config.py tests/test_commons_config.py
git commit -m "commons(config): atomic data.yaml upsert/backup/restore + conflict check"
```

---

### Task 19: Plan-time override-conflict detection wired into dataset plan

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`plan_promote` dataset branch)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_dataset_plan.py — append
def test_plan_dataset_raises_override_conflict(tmp_path, monkeypatch):
    import shutil, subprocess
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    (tmp_path / ".config" / "science").mkdir(parents=True)
    (tmp_path / ".config" / "science" / "data.yaml").write_text(
        "fixture-ds: /wrong/path\n", encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, discover_candidates, plan_promote,
    )
    from science_tool.commons.errors import PromoteOverrideConflictError
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    import pytest
    with pytest.raises(PromoteOverrideConflictError) as exc_info:
        plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    assert exc_info.value.slug == "fixture-ds"
```

- [ ] **Step 2: Run test — should fail**

Expected: FAIL — plan doesn't check the override yet.

- [ ] **Step 3: Wire `check_override_conflict` into the dataset plan branch**

In the `plan_promote` dataset branch added in Task 16, after computing per-resource hashes and before building artifacts:

```python
from science_tool.commons.config import check_override_conflict
planned_override_path = candidate.datapackage_source_path.parent
check_override_conflict(slug=candidate.slug, planned_path=planned_override_path)
```

- [ ] **Step 4: Run test**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_plan.py::test_plan_dataset_raises_override_conflict -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_plan.py
git commit -m "commons(promote): plan-time override-conflict detection for datasets"
```

---

## G.5 — Apply ordering + audit log shape

### Task 20: Add `side_channel_apply` hook to `PromoteKindConfig`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py`
- Test: `~/d/science/science/tests/test_commons_promote_kind_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_kind_config.py — append
def test_paper_topic_theme_have_no_side_channel():
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC, PROMOTE_KIND_THEME,
    )
    for k in (PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC, PROMOTE_KIND_THEME):
        assert k.side_channel_apply is None


def test_dataset_kind_has_side_channel_callable():
    from science_tool.commons.promote import PROMOTE_KIND_DATASET
    assert PROMOTE_KIND_DATASET.side_channel_apply is not None
    assert callable(PROMOTE_KIND_DATASET.side_channel_apply)
```

- [ ] **Step 2: Run test — should fail**

Expected: AttributeError — `side_channel_apply` doesn't exist on the config.

- [ ] **Step 3: Extend `PromoteKindConfig` with the hook**

```python
@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    # ...existing fields...
    side_channel_apply: Callable[
        ["SideChannelContext"], "SideChannelResult"
    ] | None = None
```

Add the support types:

```python
@dataclass(frozen=True, slots=True)
class SideChannelContext:
    decision: "PromoteDecision"
    plan: "PromotePlan"
    commons_root: Path
    op_id: str


@dataclass(frozen=True, slots=True)
class SideChannelResult:
    """Per-decision result for the side-channel apply step."""
    artifact_paths: list[Path]      # absolute paths touched outside commons
    backup_paths: list[Path]        # absolute paths to recovery backups


def _dataset_side_channel_apply(ctx: SideChannelContext) -> SideChannelResult:
    """Write the per-machine override after commons tag, before overlay rewrite."""
    from science_tool.commons.config import (
        upsert_data_override, _data_yaml_path,
    )
    extras = ctx.plan.dataset_audit_extras.get(ctx.decision.slug, {})
    planned_path = Path(extras["override_path"])     # set during plan
    upsert_data_override(
        slug=ctx.decision.slug,
        absolute_path=planned_path,
        op_id=ctx.op_id,
    )
    # Determine which backup marker was actually written:
    yaml_path = _data_yaml_path()
    bak = yaml_path.parent / f"data.yaml.bak.{ctx.op_id}"
    sentinel = yaml_path.parent / f"data.yaml.bak.{ctx.op_id}.absent"
    actual_backup = bak if bak.is_file() else sentinel
    return SideChannelResult(
        artifact_paths=[yaml_path],
        backup_paths=[actual_backup],
    )
```

Update `PROMOTE_KIND_DATASET` to set `side_channel_apply=_dataset_side_channel_apply`.

In `plan_promote`'s dataset branch (Task 16), stash `override_path` in `dataset_audit_extras[slug]["override_path"] = str(planned_override_path)`.

- [ ] **Step 4: Run tests**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_kind_config.py -v -k "side_channel"
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_kind_config.py
git commit -m "commons(promote): add side_channel_apply hook for dataset override write"
```

---

### Task 21: Wire side-channel step + new ordering into `apply_promote`

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`apply_promote`)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_apply.py`

- [ ] **Step 1: Write the failing test (success path)**

```python
# tests/test_commons_promote_dataset_apply.py — new file
from pathlib import Path
import shutil
import subprocess

import pytest


def _setup(tmp_path, monkeypatch):
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)
    (commons / ".migrations").mkdir()
    (commons / "datasets").mkdir()
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(commons), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    return proj, commons


def test_dataset_apply_writes_three_artifacts_commit_tag_override_overlay(
    tmp_path, monkeypatch,
):
    proj, commons = _setup(tmp_path, monkeypatch)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    result = apply_promote(plan, commons_root=commons, invocation="test")

    # Three artifacts written:
    assert (commons / "datasets/fixture-ds/entity.md").is_file()
    assert (commons / "datasets/fixture-ds/datapackage.yaml").is_file()
    assert (commons / "datasets/fixture-ds/recipe/README.md").is_file()

    # Commit + tag:
    assert result.commons_commit is not None
    assert "dataset/fixture-ds/1.0.0" in result.tags_created

    # Per-machine override:
    yaml_path = tmp_path / ".config" / "science" / "data.yaml"
    assert yaml_path.is_file()
    import yaml as pyyaml
    parsed = pyyaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert parsed["fixture-ds"] == str(proj / "data/fixture-ds")
    # Backup OR absent-sentinel retained (fixture had no prior data.yaml, so
    # we expect the .absent sentinel — not a content backup):
    backups = list((tmp_path / ".config" / "science").glob("data.yaml.bak.*"))
    assert len(backups) == 1
    assert backups[0].name.endswith(".absent")

    # Project overlay rewritten:
    overlay = (proj / "doc/datasets/data-fixture-ds.md").read_text(encoding="utf-8")
    assert "overlay_of: dataset:fixture-ds" in overlay
    assert "pin_version" in overlay
```

- [ ] **Step 2: Run test — should fail**

Expected: FAIL — apply doesn't yet call the side-channel hook.

- [ ] **Step 3: Insert the side-channel step in `apply_promote`**

In `apply_promote`, after the tag step (Step 5.3) and before the project rewrite (Step 6), insert:

```python
# ---------- Step 5.4: side-channel apply (datasets only) ----------
side_channel_results: dict[str, SideChannelResult] = {}
if plan.kind.side_channel_apply is not None:
    try:
        for decision in plan.decisions:
            ctx = SideChannelContext(
                decision=decision, plan=plan,
                commons_root=commons_root, op_id=op_id,
            )
            side_channel_results[decision.slug] = plan.kind.side_channel_apply(ctx)
    except (OSError, CommonsError) as exc:
        # Restore any side-channel backups already written, then unwind commons.
        # Note: backup_paths may contain a .bak.<op_id> file (file existed before)
        # OR a .bak.<op_id>.absent sentinel (file did not exist before).
        # `restore_data_override_from_backup` accepts the op_id and handles both.
        from science_tool.commons.config import restore_data_override_from_backup
        for slug in side_channel_results:
            try:
                restore_data_override_from_backup(op_id=op_id)
            except CommonsError:
                pass
        _rollback_step5(commons_root, tags_created, written_canonical_paths)
        rolled_back_commit = commons_commit
        commons_commit = None
        tags_created.clear()
        raise PromoteWriteError(
            stage="side_channel",
            detail=f"side-channel write failed (rolled back {rolled_back_commit}): {exc}",
        ) from exc
```

Add `"side_channel"` to the `failure_stage` Literal on `PromoteResult` and `_write_failure_audit_log`'s `failure_stage` param.

- [ ] **Step 4: Run the test**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_apply.py::test_dataset_apply_writes_three_artifacts_commit_tag_override_overlay -v
```
Expected: PASS.

- [ ] **Step 5: Run full regression**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_*.py -v
```
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_apply.py
git commit -m "commons(promote): wire side-channel step between tag and overlay rewrite"
```

---

### Task 22: Extend audit log with dataset-specific fields

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (`_render_audit_log_yaml`)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_apply.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commons_promote_dataset_apply.py — append
def test_dataset_apply_audit_log_records_extras(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    result = apply_promote(plan, commons_root=commons, invocation="test")

    import yaml as pyyaml
    log = pyyaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    # Top-level dataset extras:
    decisions = log["decisions"]
    fix = next(d for d in decisions if d["slug"] == "fixture-ds")
    assert fix["per_resource_hashes"]["r1"]["hash"].startswith("sha256:")
    assert fix["per_resource_hashes"]["r1"]["bytes"] == 12
    assert fix["recipe_stubbed"] is True
    # Dropped fields per §3.3:
    assert "ontologies" in fix["dropped_fields"]
    # Override metadata:
    assert "override_file" in fix
    assert fix["override_file"].endswith("data.yaml")
    assert "override_backup" in fix
    # Backup path may be the content backup or the absent-sentinel:
    op = log["op_id"]
    assert (
        fix["override_backup"].endswith(f"data.yaml.bak.{op}")
        or fix["override_backup"].endswith(f"data.yaml.bak.{op}.absent")
    )
```

- [ ] **Step 2: Run test — should fail**

Expected: KeyError on the new keys.

- [ ] **Step 3: Extend `_render_audit_log_yaml` for datasets**

For each decision rendered in the audit log, if `result.kind.kind == "dataset"`, attach the extras from `plan.dataset_audit_extras[slug]`:

```python
if result.kind.kind == "dataset":
    extras = result.plan_audit_extras.get(d.slug, {})
    entry["per_resource_hashes"] = {
        name: {"hash": h, "bytes": n}
        for name, (h, n) in extras.get("per_resource", {}).items()
    }
    entry["recipe_stubbed"] = extras.get("recipe_stubbed", False)
    entry["dropped_fields"] = list(extras.get("dropped_fields", []))
    sc = result.side_channel_results.get(d.slug)
    if sc is not None:
        entry["override_file"] = str(sc.artifact_paths[0]) if sc.artifact_paths else None
        entry["override_backup"] = str(sc.backup_paths[0]) if sc.backup_paths else None
```

This requires `PromoteResult` to carry `plan_audit_extras: dict[str, dict]` and `side_channel_results: dict[str, SideChannelResult]`. Add those fields and populate from `apply_promote`.

- [ ] **Step 4: Run test**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_apply.py::test_dataset_apply_audit_log_records_extras -v
```
Expected: PASS.

- [ ] **Step 5: Run regression sweep**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_*.py -v
```
Expected: all passing. (Paper/topic/theme audit logs do not include the dataset-extra keys.)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_apply.py
git commit -m "commons(promote): audit log records dataset hashes, recipe_stubbed, dropped, override"
```

---

### Task 23: Fault-injection rollback tests (paths a–e + audit-failure carve-out)

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/promote.py` (overlay-step rollback restores override)
- Test: `~/d/science/science/tests/test_commons_promote_dataset_apply.py`

- [ ] **Step 1: Write the five failing rollback tests + audit-failure test**

Each test follows the same shape: monkeypatch one method to raise an `OSError` at the named transition, run `apply_promote`, assert `PromoteWriteError`, then assert pre-apply state byte-identical (commons HEAD SHA, tag list, per-artifact paths, `data.yaml`).

```python
# tests/test_commons_promote_dataset_apply.py — append

def _snapshot_state(commons: Path, data_yaml: Path) -> dict:
    """Capture pre-apply state for byte-identity rollback assertions."""
    head = subprocess.run(
        ["git", "-C", str(commons), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    tags = subprocess.run(
        ["git", "-C", str(commons), "tag", "-l"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    data_yaml_bytes = (
        data_yaml.read_bytes() if data_yaml.is_file() else None
    )
    return {"head": head, "tags": tags, "data_yaml": data_yaml_bytes}


def _assert_rolled_back(commons: Path, data_yaml: Path, before: dict) -> None:
    after = _snapshot_state(commons, data_yaml)
    assert after == before


# (a) commons artifact write failure
def test_rollback_artifact_write_failure(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    from science_tool.commons.errors import PromoteWriteError
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    target = commons / "datasets/fixture-ds/datapackage.yaml"
    real = Path.write_text
    def sabotage(self, *a, **k):
        if self == target:
            raise OSError("sim artifact write fail")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "write_text", sabotage)
    with pytest.raises(PromoteWriteError, match="write_commons|canonical write"):
        apply_promote(plan, commons_root=commons, invocation="test")
    _assert_rolled_back(commons, data_yaml, before)


# (b) commit failure: simulate by aborting commit hook
def test_rollback_commit_failure(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote, _git,
    )
    from science_tool.commons.errors import PromoteWriteError
    real_git = _git
    def sabotage(commons_root, *args, **kwargs):
        if args[:1] == ("commit",):
            raise subprocess.CalledProcessError(1, args, stderr=b"sim commit fail")
        return real_git(commons_root, *args, **kwargs)
    monkeypatch.setattr("science_tool.commons.promote._git", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    with pytest.raises(PromoteWriteError, match="commit"):
        apply_promote(plan, commons_root=commons, invocation="test")
    _assert_rolled_back(commons, data_yaml, before)


# (c) tag failure after commit succeeds
def test_rollback_tag_failure(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote, _git,
    )
    from science_tool.commons.errors import PromoteWriteError
    real_git = _git
    def sabotage(commons_root, *args, **kwargs):
        if args[:1] == ("tag",) and len(args) > 1 and "dataset/" in args[1]:
            raise subprocess.CalledProcessError(1, args, stderr=b"sim tag fail")
        return real_git(commons_root, *args, **kwargs)
    monkeypatch.setattr("science_tool.commons.promote._git", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    with pytest.raises(PromoteWriteError, match="tag"):
        apply_promote(plan, commons_root=commons, invocation="test")
    _assert_rolled_back(commons, data_yaml, before)


# (d) override-write failure after tag succeeds
def test_rollback_override_failure(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    from science_tool.commons.errors import PromoteWriteError
    monkeypatch.setattr(
        "science_tool.commons.config.upsert_data_override",
        lambda **kw: (_ for _ in ()).throw(OSError("sim override fail")),
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    with pytest.raises(PromoteWriteError, match="side_channel|override"):
        apply_promote(plan, commons_root=commons, invocation="test")
    _assert_rolled_back(commons, data_yaml, before)


# (e) overlay-write failure after override succeeds
def test_rollback_overlay_failure(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    from science_tool.commons.errors import PromoteWriteError
    overlay_target = proj / "doc/datasets/data-fixture-ds.md"
    real = Path.write_text
    def sabotage(self, *a, **k):
        if self == overlay_target:
            raise OSError("sim overlay fail")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "write_text", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    with pytest.raises(PromoteWriteError, match="overlay|rewrite_projects"):
        apply_promote(plan, commons_root=commons, invocation="test")
    _assert_rolled_back(commons, data_yaml, before)
    # Project overlay restored to HEAD:
    assert "overlay_of: dataset:fixture-ds" not in overlay_target.read_text(encoding="utf-8")


# Carve-out: audit-log failure does NOT roll back the migration
def test_audit_failure_leaves_migration_landed(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path, monkeypatch)
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    from science_tool.commons.errors import PromoteWriteError
    monkeypatch.setattr(
        "science_tool.commons.promote._write_audit_log",
        lambda *a, **k: (_ for _ in ()).throw(OSError("sim audit fail")),
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    with pytest.raises(PromoteWriteError, match="audit") as exc_info:
        apply_promote(plan, commons_root=commons, invocation="test")
    # Migration stayed landed:
    assert (commons / "datasets/fixture-ds/entity.md").is_file()
    tags = subprocess.run(
        ["git", "-C", str(commons), "tag", "-l"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "dataset/fixture-ds/1.0.0" in tags
    # Failure exception carries the success-shape audit payload (NOT a
    # failure-shape audit). The migration landed, so the rendered yaml
    # should describe the successful state.
    assert hasattr(exc_info.value, "failure_audit_yaml")
    payload = exc_info.value.failure_audit_yaml
    assert payload
    import yaml as pyyaml
    parsed = pyyaml.safe_load(payload)
    assert parsed["status"] == "ok"
    assert parsed["op_id"]
    assert parsed["commons_commit"]            # commit landed
    assert "dataset/fixture-ds/1.0.0" in parsed["commons_tags"]
    assert "failure_stage" not in parsed       # success-shape: no failure key
    # Hand-placement round-trip: writing it under .migrations/ + parsing back
    # produces an equivalent dict to a normal success audit.
    migrations = commons / ".migrations"
    migrations.mkdir(exist_ok=True)
    target = migrations / f"manual-{parsed['op_id']}.yaml"
    target.write_text(payload, encoding="utf-8")
    assert pyyaml.safe_load(target.read_text(encoding="utf-8")) == parsed
```

- [ ] **Step 2: Run tests — should fail**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_apply.py -v -k "rollback or audit_failure"
```
Expected: 6 failures (or partial — depends on which transitions are already wired).

- [ ] **Step 3: Fill rollback gaps**

For each failing test, identify the missing rollback wiring in `apply_promote` and fix:

- **(a) artifact write**: should already work from Task 2 refactor (calls `_restore_paths_to_head` on `written_canonical_paths`).
- **(b) commit failure**: should already work from Phase F precedent.
- **(c) tag failure**: should already work from `_rollback_step5`.
- **(d) override write failure**: from Task 21 — the side-channel except clause must restore from `.bak.<op-id>` AND call `_rollback_step5`.
- **(e) overlay rewrite failure**: must extend Phase F's overlay-failure handler to ALSO restore override from `.bak.<op-id>` and call `_rollback_step5`. Find the existing overlay-except block (Phase F around `promote.py:896-905`) and add:

```python
# After existing _restore_project_rewrites_to_head call:
if plan.kind.side_channel_apply is not None and side_channel_results:
    from science_tool.commons.config import restore_data_override_from_backup
    try:
        restore_data_override_from_backup(op_id=op_id)
    except CommonsError:
        pass
    _rollback_step5(commons_root, tags_created, written_canonical_paths)
```

- **(audit failure)**: catch `OSError` / `CommonsError` from `_write_audit_log` separately from earlier failures; do NOT call any rollback. The migration is still landed, so the payload the user receives must be the **success-shape** audit YAML (the same content `_write_audit_log` would have written), not a failure-shape one. Construct the PromoteResult with `status="ok"`, render it via `_render_audit_log_yaml(result, commons_root, invocation=invocation)`, and attach that string to the exception as `failure_audit_yaml`:

```python
except (OSError, CommonsError) as audit_exc:
    # Migration is landed. Render the success-shape audit yaml in memory
    # so the user can hand-place it into .migrations/<ts>-<op_id>.yaml.
    landed_result = PromoteResult(
        op_id=op_id,
        started_at=started_at,
        finished_at=datetime.now(tz=timezone.utc),
        commons_commit=commons_commit,
        tags_created=list(tags_created),
        decisions=list(plan.decisions),
        failed_candidates=list(plan.failed_candidates),
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=projects_touched,
        kind=plan.kind,
        plan_audit_extras=plan.dataset_audit_extras,
        side_channel_results=side_channel_results,
    )
    rendered = _render_audit_log_yaml(
        landed_result, commons_root, invocation=invocation,
    )
    err = PromoteWriteError(
        stage="audit",
        detail=f"audit log write/commit failed (migration LANDED): {audit_exc}",
        commons_commit=commons_commit,
        projects_touched=projects_touched,
    )
    err.failure_audit_yaml = rendered
    raise err from audit_exc
```

- [ ] **Step 4: Run all 6 tests**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_apply.py -v -k "rollback or audit_failure"
```
Expected: 6 passed.

- [ ] **Step 5: Full regression**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_*.py -v
```
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/promote.py tests/test_commons_promote_dataset_apply.py
git commit -m "commons(promote): dataset rollback paths a-e + audit-failure carve-out"
```

---

## G.6 — CLI

### Task 24: Add `science commons promote dataset` command

**Files:**
- Modify: `~/d/science/science/src/science_tool/commons/cli.py`
- Test: `~/d/science/science/tests/test_commons_cli_promote.py` (or new `test_commons_cli_promote_dataset.py`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_commons_cli_promote_dataset.py — new file
from pathlib import Path
import shutil, subprocess

from click.testing import CliRunner


def _setup(tmp_path):
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)
    return proj, commons


def test_cli_promote_dataset_requires_slug(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.resolve_project_by_id", lambda s: proj,
    )
    from science_tool.commons.cli import commons_group
    r = CliRunner().invoke(commons_group, ["promote", "dataset", "--from", "proj-dataset"])
    assert r.exit_code != 0
    assert "slug" in r.output.lower() or "slug" in (r.stderr or "").lower()


def test_cli_promote_dataset_dry_run_completes(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.resolve_project_by_id", lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", lambda s: proj,
    )
    from science_tool.commons.cli import commons_group
    r = CliRunner().invoke(commons_group, [
        "promote", "dataset", "--from", "proj-dataset",
        "--slug", "fixture-ds",
    ])
    assert r.exit_code == 0, r.output
    assert "fixture-ds" in r.output
    # Dry-run did NOT write to commons:
    assert not (commons / "datasets/fixture-ds").exists()


def test_cli_promote_dataset_apply_writes_artifacts(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.resolve_project_by_id", lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", lambda s: proj,
    )
    from science_tool.commons.cli import commons_group
    r = CliRunner().invoke(commons_group, [
        "promote", "dataset", "--from", "proj-dataset",
        "--slug", "fixture-ds", "--apply",
    ])
    assert r.exit_code == 0, r.output
    assert (commons / "datasets/fixture-ds/entity.md").is_file()
```

- [ ] **Step 2: Run tests — should fail**

Expected: `Error: No such command 'dataset'`.

- [ ] **Step 3: Add `promote_dataset_cmd` to `cli.py`**

Locate `promote_topic_cmd` in `cli.py` and add a parallel command. The dataset command needs a required `--slug` option that paper/topic/theme don't:

```python
@promote_group.command(
    "dataset",
    params=_promote_from_options(PROMOTE_KIND_DATASET) + [
        click.Option(
            ["--slug"],
            required=True,
            help="Dataset slug to promote (required in v1; batch deferred to v1.1).",
        ),
    ],
)
def promote_dataset_cmd(
    entity_id: str | None,        # unused for dataset (kept for CLI shape parity)
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
    slug: str,
) -> None:
    """Promote one dataset entity into the commons store."""
    _promote_kind_cmd(
        kind=PROMOTE_KIND_DATASET,
        entity_id=f"dataset:{slug}",
        from_=from_,
        apply_=apply_flag,
        limit=limit,
    )
```

Within `_promote_kind_cmd`, the `entity_id` filter should already restrict discovery to a single slug — verify by tracing the existing helper. If it doesn't, add a post-discovery filter that prunes `discovery.candidates_by_slug` to only the requested slug when `entity_id` is set.

- [ ] **Step 4: Run tests**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_cli_promote_dataset.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run full regression**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_*.py -v
```
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/cli.py tests/test_commons_cli_promote_dataset.py
git commit -m "commons(cli): add 'commons promote dataset --slug <slug>' command"
```

---

## G.7 — Integration + pilot runbook

### Task 25: End-to-end integration test under `tmp_path`

**Files:**
- Create: `~/d/science/science/tests/test_commons_promote_dataset_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_commons_promote_dataset_integration.py — new file
"""End-to-end integration test for `science commons promote dataset`.

Drives discover → plan → apply over a synthetic project under tmp_path with
XDG_CONFIG_HOME sandboxed. Asserts the full pilot surface.
"""
from pathlib import Path
import shutil, subprocess
import yaml as pyyaml


def test_promote_dataset_end_to_end(tmp_path, monkeypatch):
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )

    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)
    (commons / "datasets").mkdir()
    (commons / ".migrations").mkdir()
    (commons / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(commons), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True,
    )

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET, apply_promote, discover_candidates, plan_promote,
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    result = apply_promote(plan, commons_root=commons, invocation="integration")

    # Commons artifacts:
    assert (commons / "datasets/fixture-ds/entity.md").is_file()
    dp = (commons / "datasets/fixture-ds/datapackage.yaml").read_text(encoding="utf-8")
    parsed_dp = pyyaml.safe_load(dp)
    assert parsed_dp["name"] == "fixture-ds"
    assert all(
        r["hash"].startswith("sha256:") and isinstance(r["bytes"], int)
        for r in parsed_dp["resources"]
    )
    r1 = next(r for r in parsed_dp["resources"] if r["name"] == "r1")
    assert r1["hash"] == (
        "sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    )
    assert r1["bytes"] == 12

    assert (commons / "datasets/fixture-ds/recipe/README.md").is_file()

    # 1 commons commit (promote) + 1 commons commit (audit) above the init:
    log = subprocess.run(
        ["git", "-C", str(commons), "log", "--oneline"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert len(log) == 3   # init + promote + audit

    # 1 dataset tag:
    tags = subprocess.run(
        ["git", "-C", str(commons), "tag", "-l"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert tags == ["dataset/fixture-ds/1.0.0"]

    # Project overlay rewritten in working tree:
    overlay = (proj / "doc/datasets/data-fixture-ds.md").read_text(encoding="utf-8")
    assert "overlay_of: dataset:fixture-ds" in overlay
    assert "pin_version: 1.0.0" in overlay or "pin_version: '1.0.0'" in overlay

    # Override side-channel:
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    assert data_yaml.is_file()
    parsed_yaml = pyyaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    assert parsed_yaml["fixture-ds"] == str(proj / "data/fixture-ds")
    # Backup retained:
    backups = list((tmp_path / ".config" / "science").glob("data.yaml.bak.*"))
    assert len(backups) == 1
```

- [ ] **Step 2: Run the test**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_promote_dataset_integration.py -v
```
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science/science
git add tests/test_commons_promote_dataset_integration.py
git commit -m "commons(tests): end-to-end integration test for dataset promote"
```

---

### Task 26: Update inventory/resolver tests to handle dataset kind

**Files:**
- Modify: `~/d/science/science/tests/test_commons_inventory.py` (if needed)
- Modify: `~/d/science/science/tests/test_commons_resolver.py` (if needed)

- [ ] **Step 1: Run inventory + resolver tests against the new dataset kind**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_inventory.py tests/test_commons_resolver.py -v
```

- [ ] **Step 2: If a test asserts only paper/topic/theme are discoverable, update it to acknowledge dataset**

For example, if `test_inventory_lists_all_kinds` enumerates kinds: add `"dataset"`.

- [ ] **Step 3: Re-run**

```bash
cd ~/d/science/science
uv run pytest tests/test_commons_inventory.py tests/test_commons_resolver.py -v
```
Expected: all passing.

- [ ] **Step 4: Commit (only if files changed)**

```bash
cd ~/d/science/science
git add -u tests/
git diff --staged --quiet || git commit -m "commons(tests): inventory/resolver acknowledge dataset kind"
```

---

### Task 27: Full test sweep + lint

**Files:** none (verification)

- [ ] **Step 1: Run the entire science test suite**

```bash
cd ~/d/science/science
uv run pytest -x -q
```
Expected: all passing. If failures emerge in unrelated tests, triage: real regression vs. flake.

- [ ] **Step 2: Run any project lint / type-check**

```bash
cd ~/d/science/science
uv run ruff check src/science_tool/commons/ tests/test_commons_*.py 2>&1 | tail -30
uv run mypy src/science_tool/commons/promote.py 2>&1 | tail -30  # if mypy is configured
```
Fix any new warnings/errors introduced by Phase G code.

- [ ] **Step 3: Commit any lint fixes**

```bash
cd ~/d/science/science
git add -u
git diff --staged --quiet || git commit -m "commons: lint fixes from Phase G sweep"
```

---

### Task 28: Pilot runbook companion document

**Files:**
- Create: `~/d/science/docs/plans/2026-05-18-commons-promote-datasets-pilot.md`

- [ ] **Step 1: Write the runbook**

Mirror the shape of `docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md` (Phase F's runbook). Sections:

1. **Goal** — exercise the full Phase G surface end-to-end on `dataset:ccle-proteomics-nusinow-2020` in `multiple-myeloma`.
2. **Preconditions** — repeat the 5 preconditions from the design spec §7 (commons clean, project registered, working tree clean, pre-migration prep frontmatter committed, override map has no conflicting entry for this slug).
3. **Pre-migration prep commit** — exact frontmatter block to add to `~/d/cancer/cancer-types/multiple-myeloma/doc/datasets/data-ccle-proteomics.md`:
   ```yaml
   datapackage: data/external/ccle_proteomics/2020-01/datapackage.json
   origin: external
   tier: evaluate-next
   access:
     level: public
     verified: true
     source_url: "https://gygi.hms.harvard.edu/publications/ccle.html"
   ```
   Commit message: `docs(datasets): add Phase G prep frontmatter for ccle-proteomics`.
4. **Dry-run command + expected output** — copy from spec §7.
5. **Apply command + expected effects** — 1 commons commit + 1 audit commit + 1 tag + 1 line in `~/.config/science/data.yaml`, plus uncommitted project overlay.
6. **User-side commit of project overlay** — `git add doc/datasets/data-ccle-proteomics.md && git commit -m "docs(datasets): promote ccle-proteomics to commons (Phase G pilot)"`.
7. **Verify** — `science commons inventory`, `science commons show dataset:ccle-proteomics-nusinow-2020 --project multiple-myeloma`, `science commons data resolve dataset:ccle-proteomics-nusinow-2020 mm-cell-lines.parquet`.
8. **Rollback hints** — path-limited per design §7.

Use `~/d/` (not `/home/keith/d/`) per CLAUDE.md.

- [ ] **Step 2: Commit**

```bash
cd ~/d/science
git add docs/plans/2026-05-18-commons-promote-datasets-pilot.md
git commit -m "docs(plans): Phase G pilot runbook companion"
```

- [ ] **Step 3: Confirm pilot runbook is reachable**

```bash
ls -la ~/d/science/docs/plans/2026-05-18-commons-promote-datasets-pilot.md
```
Expected: file exists.

---

## Acceptance criteria (carry over from design §10)

The implementation is complete when, in addition to all 28 tasks committed:

1. `uv run pytest tests/test_commons_*.py` is green.
2. `science commons promote dataset --from multiple-myeloma --slug ccle-proteomics-nusinow-2020` (dry-run) prints the expected plan summary (3 canonical artifact paths, 2 per-resource hashes, 1 override line, the dropped-fields list).
3. The same command with `--apply` produces: 1 commons commit + 1 audit commit, 1 `dataset/ccle-proteomics-nusinow-2020/1.0.0` tag, 1 rewritten project overlay (uncommitted), and 1 upserted line in `~/.config/science/data.yaml` with `.bak.<op-id>` retained.
4. `science commons inventory`, `science commons show … --project …`, and `science commons data resolve <dataset-id> <logical-path>` all succeed against the migrated dataset.
5. Fault-injected failure at every transition through step 6 leaves the commons repo (HEAD SHA, tags, per-artifact working-tree paths) and `~/.config/science/data.yaml` byte-identical to pre-apply, with unrelated commons working-tree state untouched. Audit-log failure (steps 7–8) is excluded — migration remains landed; user receives the rendered audit YAML to hand-place.

---
