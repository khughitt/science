# Code-file Entity Model & Topology (Spec 1, Plan A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make source-code files under declared roots first-class `code-file` entities carrying a content-derived `updated` date, declare `code_roots`/`app_roots`/`code_excludes` in `science.yaml`, and add the `implements`/`defines` relation vocabulary.

**Architecture:** Add a `code-file` kind across the three synced touch points the registry requires (the `EntityType` enum, the core profile manifest, and the `EntityRegistry`), backed by a small `CodeFileEntity` subclass. Topology is read in the single `paths.py` chokepoint. A new `CodeAdapter` storage adapter discovers code files, parses a co-located `# science:code … # science:end` block, derives the entity id/title from the path, and sets `updated` to the file's last content-changing git commit date — which the freshness engine consumes with **zero engine changes** (it reads `entity.updated`, a `date`). This plan does **not** create `bears_on` edges, so code edits do not yet propagate to findings — that is Plan C. Plan A's freshness deliverable is solely that the entity carries the correct content-derived `updated`. Task ids are stored as a `CodeFileEntity` field (not in `related`) so a typo cannot hard-fail `graph materialize`; validating them is a Plan B concern. `updated` uses **commit-only semantics**: it is the date of the last commit that touched the file, so uncommitted working-tree edits are not reflected until committed (the graph reflects committed state); a blocked-but-uncommitted file yields `updated=None`, which Plan B flags rather than letting it silently drop from freshness. **`app_roots` is topology-only here** — declared so the research/non-research boundary is known (exempting `app/` from legacy-root warnings and getting it existence-validated), but it is *not* scanned and its files do not become entities. The metadata-block parser returns a three-state result (absent / valid / invalid-with-error), parsing the body as YAML after stripping `#` prefixes, so Plan B can tell a ghost from a malformed block; non-`#` comment languages are out of scope while `app_roots` is unscanned.

**Tech Stack:** Python 3.12+, pydantic v2, two `uv` packages — `science-model` (in `science/model/`, tests in `science/model/tests/`) and `science_tool` (in `science/`, tests in `science/tests/`). Entities flow `StorageAdapter.discover() → load_raw() (raw dict) → registry.resolve(kind).model_validate(raw)`; records returning no `kind` are silently skipped (`sources.py:238-243`). `git` CLI is available. Run model tests with `cd science/model && uv run pytest …`; tool tests with `cd science && uv run pytest …`.

**Conventions observed:** `Result(severity, path, line, message, rule, task)` is a frozen positional dataclass. Model tests use a `_minimal(kind, id_)` helper (`science/model/tests/test_typed_entities.py`); validate tests use `_ctx(tmp_path, profile=…, extra_manifest=…)` and `_messages(results)` helpers (`science/tests/validate/test_checks_basic.py`).

---

## File Structure

**Model layer (`science/model/`):**
- `src/science_model/entities.py` — add `EntityType.CODE_FILE`, mechanism-disallow + review-state-forbidden entries, and the `CodeFileEntity` subclass.
- `src/science_model/profiles/core.py` — add the `code-file` `EntityKind` and the `implements`/`defines` `RelationKind`s.

**Tool layer (`science/`):**
- `src/science_tool/graph/entity_registry.py` — classify `code-file` as `OPERATIONAL` and register `CodeFileEntity`.
- `src/science_tool/paths.py` — read `code_roots`/`app_roots`/`code_excludes`; surface them on `ProjectPaths`.
- `src/science_tool/validate/context.py` — convert a malformed-root `ValueError` from `resolve_paths` into a clean `ValidateContextError` (so `validate` reports, not crashes).
- `src/science_tool/validate/checks/directory_structure.py` — suppress legacy-root warnings for declared roots.
- `src/science_tool/code/__init__.py` *(new package)*
- `src/science_tool/code/metadata.py` *(new)* — the `# science:code` block parser.
- `src/science_tool/code/git.py` *(new)* — last content-change date helper.
- `src/science_tool/graph/storage_adapters/code.py` *(new)* — `CodeAdapter`.
- `src/science_tool/graph/sources.py` — register `CodeAdapter` in `load_project_sources`.

Each file has one responsibility: `metadata.py` parses, `git.py` dates, `code.py` discovers/builds, `paths.py` resolves topology, the checks validate. They are independently testable.

---

## Task 1: Add the `code-file` entity type

**Files:**
- Modify: `science/model/src/science_model/entities.py` (`EntityType` enum ~line 95; `_DISALLOWED_MECHANISM_PARTICIPANT_KINDS` ~lines 152-188; `_validate_review_state_kind` set ~line 245)
- Test: `science/model/tests/test_entities.py`

- [ ] **Step 1: Write the failing test**

Add to `science/model/tests/test_entities.py`:

```python
from science_model.entities import EntityType, core_entity_type_for_kind


def test_code_file_entity_type_exists() -> None:
    assert EntityType.CODE_FILE.value == "code-file"
    assert core_entity_type_for_kind("code-file") is EntityType.CODE_FILE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_entities.py::test_code_file_entity_type_exists -q`
Expected: FAIL — `AttributeError: CODE_FILE`.

- [ ] **Step 3: Implement the enum member + disallow/forbidden entries**

In `EntityType`, add immediately before the `UNKNOWN = "unknown"` member:

```python
    CODE_FILE = "code-file"
```

In the `_DISALLOWED_MECHANISM_PARTICIPANT_KINDS` list, add an entry alongside the other operational kinds:

```python
        EntityType.CODE_FILE.value,
```

In `_validate_review_state_kind`, add `"code-file"` to the non-epistemic set so review-state is forbidden on code files (they are operational):

```python
        non_epistemic = {"task", "dataset", "workflow-run", "data-package", "paper", "experiment", "code-file"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_entities.py::test_code_file_entity_type_exists -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_entities.py
git commit -m "feat(model): add code-file entity type"
```

---

## Task 2: Add the `CodeFileEntity` subclass

**Files:**
- Modify: `science/model/src/science_model/entities.py` (after `ResearchPackageEntity`, ~line 621)
- Test: `science/model/tests/test_typed_entities.py`

- [ ] **Step 1: Write the failing test**

Add to `science/model/tests/test_typed_entities.py` (the `_minimal` helper and `EntityType`, `ProjectEntity` imports already exist there):

```python
def test_code_file_entity_defaults_and_fields() -> None:
    from science_model.entities import CodeFileEntity

    cf = CodeFileEntity(**_minimal(EntityType.CODE_FILE, "code-file:stages/run.py"))
    assert isinstance(cf, ProjectEntity)
    assert cf.decision_bearing is False
    assert cf.task_ids == []

    cf2 = CodeFileEntity(
        **_minimal(EntityType.CODE_FILE, "code-file:stages/run.py"),
        decision_bearing=True,
        task_ids=["t491"],
    )
    assert cf2.decision_bearing is True
    assert cf2.task_ids == ["t491"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_typed_entities.py::test_code_file_entity_defaults_and_fields -q`
Expected: FAIL — `ImportError: cannot import name 'CodeFileEntity'`.

- [ ] **Step 3: Implement the subclass**

In `entities.py`, after the `ResearchPackageEntity` class:

```python
class CodeFileEntity(ProjectEntity):
    """A source-code file registered as a first-class entity.

    Operational: carries no continuous belief. `updated` is set by the
    CodeAdapter to the file's last content-changing commit date so code
    edits feed freshness once provenance edges exist (Plan C). `task_ids`
    are stored here rather than in `related` so an unresolved task id
    cannot hard-fail graph materialization (validated in Plan B).
    """

    decision_bearing: bool = False
    task_ids: list[str] = Field(default_factory=list)
```

(`Field` is already imported in `entities.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_typed_entities.py::test_code_file_entity_defaults_and_fields -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_typed_entities.py
git commit -m "feat(model): add CodeFileEntity subclass"
```

---

## Task 3: Declare the `code-file` kind and `implements`/`defines` relations

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (`entity_kinds` list ~before line 139; `relation_kinds` list ~before line 357)
- Test: `science/model/tests/test_profile_manifests.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/model/tests/test_profile_manifests.py` (it already imports `CORE_PROFILE`):

```python
def test_code_file_kind_declared() -> None:
    kind = next(k for k in CORE_PROFILE.entity_kinds if k.name == "code-file")
    assert kind.canonical_prefix == "code-file"
    assert kind.layer == "layer/core"


def test_implements_relation_targets_step_and_method() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "implements")
    assert rel.source_kinds == ["code-file"]
    assert rel.target_kinds == ["workflow-step", "method"]
    assert rel.predicate == "sci:implements"


def test_defines_relation_targets_workflow() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "defines")
    assert rel.source_kinds == ["code-file"]
    assert rel.target_kinds == ["workflow"]
    assert rel.predicate == "sci:defines"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run pytest tests/test_profile_manifests.py -k "code_file or implements or defines" -q`
Expected: FAIL — `StopIteration` (no such kind/relation).

- [ ] **Step 3: Implement the kind and relations**

In the `entity_kinds=[...]` list of `CORE_PROFILE`, add:

```python
        EntityKind(
            name="code-file",
            canonical_prefix="code-file",
            layer="layer/core",
            description="Source-code file implementing workflow steps and methods.",
        ),
```

In the `relation_kinds=[...]` list, add:

```python
        RelationKind(
            name="implements",
            predicate="sci:implements",
            source_kinds=["code-file"],
            target_kinds=["workflow-step", "method"],
            layer="layer/core",
            description="A code file implements a workflow step or method.",
        ),
        RelationKind(
            name="defines",
            predicate="sci:defines",
            source_kinds=["code-file"],
            target_kinds=["workflow"],
            layer="layer/core",
            description="A code file defines a workflow.",
        ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run pytest tests/test_profile_manifests.py -k "code_file or implements or defines" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/tests/test_profile_manifests.py
git commit -m "feat(model): declare code-file kind and implements/defines relations"
```

---

## Task 4: Classify `code-file` as OPERATIONAL and register `CodeFileEntity`

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py` (`_CORE_KIND_CLASSES` ~lines 55-85; imports ~lines 15-28; `with_core_types()` typed block ~lines 104-122)
- Test: `science/tests/test_kind_class.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_kind_class.py`:

```python
def test_code_file_is_operational_and_resolves_to_subclass() -> None:
    from science_model.entities import CodeFileEntity

    r = EntityRegistry.with_core_types()
    assert r.kind_class("code-file") == EntityClass.OPERATIONAL
    assert r.resolve("code-file") is CodeFileEntity
```

(`EntityRegistry` and `EntityClass` are already imported in this test module.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_kind_class.py::test_code_file_is_operational_and_resolves_to_subclass -q`
Expected: FAIL — `KeyError`/`EntityKindNotRegisteredError` for `"code-file"`. The exhaustiveness test `test_with_core_types_classifies_every_kind` will also fail once the next step adds the class only to one map, so add to both in Step 3.

- [ ] **Step 3: Implement the classification and registration**

Add `CodeFileEntity` to the typed-entity imports at the top of `entity_registry.py`:

```python
    CodeFileEntity,
```

Add to `_CORE_KIND_CLASSES`, in the alphabetized generic block (between the `"chain-audit"` and `"concept"` entries):

```python
    "code-file": EntityClass.OPERATIONAL,
```

In `with_core_types()`, in the explicit typed-entity block (alongside the `register_core_kind("workflow-run", WorkflowRunEntity, …)` calls):

```python
        r.register_core_kind("code-file", CodeFileEntity, entity_class=_CORE_KIND_CLASSES["code-file"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_kind_class.py tests/test_entity_registry.py -q`
Expected: PASS (including `test_with_core_types_classifies_every_kind`).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/entity_registry.py science/tests/test_kind_class.py
git commit -m "feat(graph): register code-file as an OPERATIONAL kind"
```

---

## Task 5: Read `code_roots`/`app_roots`/`code_excludes` from `science.yaml`

**Files:**
- Modify: `science/src/science_tool/paths.py`
- Test: `science/tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_paths.py`:

```python
def test_code_roots_default_to_profile_code_dir(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\nprofile: research\n", encoding="utf-8")
    paths = resolve_paths(tmp_path)
    assert paths.code_roots == (tmp_path / "code",)
    assert paths.app_roots == ()
    assert paths.code_excludes == ()
    assert paths.code_dir == tmp_path / "code"


def test_declared_code_app_roots_and_excludes(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\n"
        "code_roots:\n  - code\n  - scripts\n"
        "app_roots:\n  - app\n"
        "code_excludes:\n  - '**/vendor/**'\n",
        encoding="utf-8",
    )
    paths = resolve_paths(tmp_path)
    assert paths.code_roots == (tmp_path / "code", tmp_path / "scripts")
    assert paths.app_roots == (tmp_path / "app",)
    assert paths.code_excludes == ("**/vendor/**",)
    assert paths.code_dir == tmp_path / "code"  # first declared root is canonical


def test_code_roots_must_be_list_of_strings(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots: code\n", encoding="utf-8")
    with pytest.raises(ValueError, match="code_roots must be a list of strings"):
        resolve_paths(tmp_path)


def test_absolute_or_escaping_roots_rejected(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - /etc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="relative paths inside the project"):
        resolve_paths(tmp_path)


def test_empty_root_rejected(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - ''\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        resolve_paths(tmp_path)


def test_duplicate_roots_deduplicated(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - code\n  - code\n", encoding="utf-8")
    assert resolve_paths(tmp_path).code_roots == (tmp_path / "code",)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_paths.py -q` (run the whole file so every new guardrail test executes)
Expected: FAIL — `AttributeError: 'ProjectPaths' object has no attribute 'code_roots'`.

- [ ] **Step 3: Implement the topology fields**

In `paths.py`, add three fields with defaults at the **end** of the `ProjectPaths` dataclass (defaults keep every existing `ProjectPaths(...)` construction valid):

```python
    code_roots: tuple[Path, ...] = ()
    app_roots: tuple[Path, ...] = ()
    code_excludes: tuple[str, ...] = ()
```

Replace the file-reading helpers and `resolve_paths` body. Add above `_resolve_profile`:

```python
def _load_manifest(project_root: Path) -> dict:
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        return {}
    with open(yaml_path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _str_list(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"science.yaml {key} must be a list of strings")
    return value


def _normalize_root_names(data: dict, key: str) -> list[str]:
    """Validate root entries are non-empty, relative, project-contained, de-duplicated."""
    normalized: list[str] = []
    for name in _str_list(data, key):
        if not name.strip():
            raise ValueError(f"science.yaml {key} entries must be non-empty relative paths")
        candidate = Path(name)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"science.yaml {key} entries must be relative paths inside the project: {name!r}")
        if name not in normalized:
            normalized.append(name)
    return normalized
```

Change `_resolve_profile` to take parsed data instead of re-reading the file:

```python
def _resolve_profile(data: dict) -> ProjectProfile:
    raw_profile = data.get("profile") or "research"
    if raw_profile not in _CODE_DIR_BY_PROFILE:
        raise ValueError(f"Unsupported project profile: {raw_profile!r}")
    return raw_profile
```

Rewrite `resolve_paths`:

```python
def resolve_paths(project_root: Path) -> ProjectPaths:
    """Resolve canonical paths and declared code/app roots from science.yaml."""

    data = _load_manifest(project_root)
    profile = _resolve_profile(data)
    declared_code = _normalize_root_names(data, "code_roots")
    code_root_names = declared_code or [_CODE_DIR_BY_PROFILE[profile]]
    app_root_names = _normalize_root_names(data, "app_roots")
    return ProjectPaths(
        root=project_root,
        profile=profile,
        doc_dir=project_root / _COMMON_DEFAULTS["doc_dir"],
        code_dir=project_root / code_root_names[0],
        data_dir=project_root / _COMMON_DEFAULTS["data_dir"],
        models_dir=project_root / _COMMON_DEFAULTS["models_dir"],
        specs_dir=project_root / _COMMON_DEFAULTS["specs_dir"],
        papers_dir=project_root / _COMMON_DEFAULTS["papers_dir"],
        knowledge_dir=project_root / _COMMON_DEFAULTS["knowledge_dir"],
        tasks_dir=project_root / _COMMON_DEFAULTS["tasks_dir"],
        templates_dir=project_root / _COMMON_DEFAULTS["templates_dir"],
        prompts_dir=project_root / _COMMON_DEFAULTS["prompts_dir"],
        code_roots=tuple(project_root / name for name in code_root_names),
        app_roots=tuple(project_root / name for name in app_root_names),
        code_excludes=tuple(_str_list(data, "code_excludes")),
    )
```

- [ ] **Step 4: Run the full paths suite to verify no regression**

Run: `cd science && uv run pytest tests/test_paths.py -q`
Expected: PASS (new tests plus the existing profile/default tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/paths.py science/tests/test_paths.py
git commit -m "feat(paths): resolve code_roots/app_roots/code_excludes from science.yaml"
```

---

## Task 6: Surface malformed roots as a clean context error

**Files:**
- Modify: `science/src/science_tool/validate/context.py` (`from_project_root`, line 42)
- Test: `science/tests/validate/test_checks_basic.py`

`resolve_paths` now raises `ValueError` on malformed roots (Task 5). But `ValidateContext.from_project_root` calls `resolve_paths` *before any check runs*, and the runner does not wrap canonical checks in try/except — so an unconverted `ValueError` crashes `science validate`, and `check_manifest` never runs. Convert it to `ValidateContextError`, which the CLI already renders as a clean error (`cli.py`). This is the right single chokepoint: it supersedes a manifest-check validator (which would be unreachable here), and it also fixes the pre-existing latent crash on an invalid `profile`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_checks_basic.py` (it defines `_write_manifest`; ensure `import pytest` is present at the top — add it if absent):

```python
def test_context_rejects_absolute_code_root(tmp_path: Path) -> None:
    from science_tool.validate.context import ValidateContext, ValidateContextError

    _write_manifest(tmp_path, extra="code_roots:\n  - /etc")
    with pytest.raises(ValidateContextError, match="relative paths inside the project"):
        ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def test_context_rejects_non_list_code_roots(tmp_path: Path) -> None:
    from science_tool.validate.context import ValidateContext, ValidateContextError

    _write_manifest(tmp_path, extra="code_roots: code")
    with pytest.raises(ValidateContextError, match="must be a list of strings"):
        ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_checks_basic.py -k context_rejects -q`
Expected: FAIL — `resolve_paths` raises a bare `ValueError`, so `pytest.raises(ValidateContextError)` does not catch it and the test errors.

- [ ] **Step 3: Implement the conversion**

In `context.py`, wrap the `resolve_paths` call in `from_project_root` (replacing the bare `paths = resolve_paths(root)` at line 42):

```python
        try:
            paths = resolve_paths(root)
        except ValueError as exc:
            raise ValidateContextError(str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_basic.py -k context_rejects -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/context.py science/tests/validate/test_checks_basic.py
git commit -m "fix(validate): surface malformed code/app roots as a clean context error"
```

---

## Task 7: Suppress legacy-root warnings for declared roots

**Files:**
- Modify: `science/src/science_tool/validate/checks/directory_structure.py` (`_check_legacy_roots`, ~lines 145-153)
- Test: `science/tests/validate/test_checks_basic.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/validate/test_checks_basic.py`:

```python
def test_declared_code_root_not_flagged_as_legacy(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", extra_manifest="code_roots:\n  - code\n  - scripts")
    (tmp_path / "scripts").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert not any("Legacy top-level execution root detected: scripts" in m for m in messages)


def test_undeclared_scripts_still_flagged_as_legacy(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research")
    (tmp_path / "scripts").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert any("Legacy top-level execution root detected: scripts" in m for m in messages)


def test_missing_declared_code_root_is_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", extra_manifest="code_roots:\n  - code\n  - scripst")
    (tmp_path / "code").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert any("Declared code_roots directory missing: scripst/" in m for m in messages)
```

- [ ] **Step 2: Run tests to verify the first fails**

Run: `cd science && uv run pytest tests/validate/test_checks_basic.py -k "legacy or declared_code_root" -q`
Expected: `test_declared_code_root_not_flagged_as_legacy` FAILS (the warning is still emitted); the second passes.

- [ ] **Step 3: Implement the suppression**

At the top of `_check_legacy_roots`, resolve declared roots and skip any that match. Add `from science_tool.paths import resolve_paths` to the imports if not already present, then near the start of the function body:

```python
    paths = resolve_paths(ctx.project_root)
    declared_root_names = {p.name for p in (*paths.code_roots, *paths.app_roots)}
```

In the research-profile legacy loop, skip declared names:

```python
    if profile == "research":
        for dirname in ("scripts", "notebooks", "workflow"):
            if dirname in declared_root_names:
                continue
            if (ctx.project_root / dirname).is_dir():
                yield _result(
                    Severity.WARN,
                    dirname,
                    f"Legacy top-level execution root detected: {dirname}/ — consolidate under {code_dir_name}/",
                )
```

Also add a **declared-roots existence** check so a typo'd root is a hard error rather than silent absence (no entities, no failure). In `check_directory_structure`, after the existing required-dirs loop, add:

```python
    yield from _check_declared_roots_exist(ctx)
```

and define the helper (the canonical code dir is skipped because the required-dirs loop already reports it):

```python
def _check_declared_roots_exist(ctx: ValidateContext) -> Iterator[Result]:
    paths = resolve_paths(ctx.project_root)
    for label, roots in (("code_roots", paths.code_roots), ("app_roots", paths.app_roots)):
        for root in roots:
            if root == paths.code_dir:
                continue
            if not root.is_dir():
                rel = root.relative_to(ctx.project_root).as_posix()
                yield _result(Severity.ERROR, rel, f"Declared {label} directory missing: {rel}/")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_basic.py -k "legacy or declared_code_root" -q`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/directory_structure.py science/tests/validate/test_checks_basic.py
git commit -m "feat(validate): exempt declared code_roots/app_roots from legacy-root warnings"
```

---

## Task 8: The `# science:code` metadata block parser

**Files:**
- Create: `science/src/science_tool/code/__init__.py`
- Create: `science/src/science_tool/code/metadata.py`
- Test: `science/tests/test_code_metadata.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_code_metadata.py`:

```python
from science_tool.code.metadata import parse_code_metadata


def test_absent_when_no_block() -> None:
    result = parse_code_metadata("print('hi')\n")
    assert result.present is False
    assert result.fields is None
    assert result.valid is False


def test_parses_valid_block_with_yaml_types() -> None:
    text = (
        "# science:code\n"
        "# task_ids: [t491, t528]\n"
        "# decision_bearing: true\n"
        "# status: workflow-owned\n"
        "# science:end\n"
        "print(1)\n"
    )
    result = parse_code_metadata(text)
    assert result.valid is True
    assert result.fields == {
        "task_ids": ["t491", "t528"],
        "decision_bearing": True,
        "status": "workflow-owned",
    }


def test_empty_block_is_valid_empty_mapping() -> None:
    result = parse_code_metadata("# science:code\n# science:end\n")
    assert result.valid is True
    assert result.fields == {}


def test_unterminated_block_is_invalid_with_error() -> None:
    result = parse_code_metadata("# science:code\n# status: library\n")
    assert result.present is True
    assert result.fields is None
    assert "unterminated" in (result.error or "")


def test_non_mapping_block_is_invalid() -> None:
    text = "# science:code\n# - just\n# - a list\n# science:end\n"
    result = parse_code_metadata(text)
    assert result.present is True
    assert result.fields is None
    assert result.error is not None


def test_sentinel_substring_in_code_is_not_a_block() -> None:
    result = parse_code_metadata('msg = "science:code"\nx = 1\n')
    assert result.present is False


def test_end_marker_before_start_is_ignored() -> None:
    text = 'note = "science:end"\n# science:code\n# status: library\n# science:end\n'
    result = parse_code_metadata(text)
    assert result.valid is True
    assert result.fields == {"status": "library"}


def test_double_hash_comment_delimiters() -> None:
    result = parse_code_metadata("## science:code\n## status: library\n## science:end\n")
    assert result.valid is True
    assert result.fields == {"status": "library"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_code_metadata.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.code.metadata`.

- [ ] **Step 3: Implement the parser**

Create `science/src/science_tool/code/__init__.py`:

```python
"""Code-artifact registration support (metadata blocks, git dating)."""
```

Create `science/src/science_tool/code/metadata.py`:

```python
"""Parser for the co-located `# science:code … # science:end` block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

_START = "science:code"
_END = "science:end"


@dataclass(frozen=True)
class CodeMetadata:
    """Three-state result of parsing a code file's metadata block.

    - absent: `present is False` (no block at all) — a ghost in Plan B.
    - invalid: `present is True` and `fields is None` with `error` set
      (unterminated, non-mapping, or malformed YAML) — a malformed block in Plan B.
    - valid: `present is True` and `fields` is the parsed mapping.
    """

    present: bool
    fields: dict[str, Any] | None
    error: str | None

    @property
    def valid(self) -> bool:
        return self.present and self.fields is not None and self.error is None


def _strip_comment(line: str) -> str:
    body = line.lstrip().lstrip("#")
    return body[1:] if body.startswith(" ") else body


def parse_code_metadata(text: str) -> CodeMetadata:
    """Parse the `# science:code … # science:end` block into a CodeMetadata.

    Delimiters are matched only after stripping the `#` comment prefix and must
    equal `science:code` / `science:end` exactly, so a sentinel inside a string
    or code (e.g. `print("science:code")`) never triggers parsing, and an
    earlier `science:end` cannot terminate before a real start. The body is
    parsed as YAML (after stripping a leading run of `#` and one space per line)
    so values get proper types (lists, bools). Works for any `#`-comment
    language in scope (Python, R, shell, Snakemake); non-`#` languages are out
    of scope while app_roots is unscanned.
    """
    started = False
    terminated = False
    body_lines: list[str] = []
    for raw_line in text.splitlines():
        marker = _strip_comment(raw_line).strip()
        if not started:
            if marker == _START:
                started = True
            continue
        if marker == _END:
            terminated = True
            break
        body_lines.append(_strip_comment(raw_line))
    if not started:
        return CodeMetadata(present=False, fields=None, error=None)
    if not terminated:
        return CodeMetadata(present=True, fields=None, error="unterminated science:code block (missing science:end)")
    try:
        loaded = yaml.safe_load("\n".join(body_lines)) if body_lines else {}
    except yaml.YAMLError as exc:
        return CodeMetadata(present=True, fields=None, error=f"invalid YAML in science:code block: {exc}")
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        return CodeMetadata(present=True, fields=None, error="science:code block must be a mapping of fields")
    return CodeMetadata(present=True, fields={str(k): v for k, v in loaded.items()}, error=None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_code_metadata.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/code/__init__.py science/src/science_tool/code/metadata.py science/tests/test_code_metadata.py
git commit -m "feat(code): add science:code metadata block parser"
```

---

## Task 9: Last content-change date helper

**Files:**
- Create: `science/src/science_tool/code/git.py`
- Test: `science/tests/test_code_git.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_code_git.py`:

```python
import os
import subprocess
from datetime import date
from pathlib import Path

from science_tool.code.git import last_content_change_date


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_returns_last_commit_date(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "f.py")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-03-15T12:00:00", "GIT_AUTHOR_DATE": "2026-03-15T12:00:00"}
    _git(tmp_path, "commit", "-m", "add f", env=env)
    assert last_content_change_date("f.py", repo_root=tmp_path) == date(2026, 3, 15)


def test_returns_none_for_untracked_file(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
    assert last_content_change_date("f.py", repo_root=tmp_path) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_code_git.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.code.git`.

- [ ] **Step 3: Implement the helper**

Create `science/src/science_tool/code/git.py`:

```python
"""Content-derived change dates for code files, via git."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path


def last_content_change_date(rel_path: str, *, repo_root: Path) -> date | None:
    """Date of the last commit that changed `rel_path` (committer date).

    Commit-only semantics: uncommitted working-tree edits are NOT reflected
    until committed (the graph reflects committed state). Returns None when
    the file is untracked, has no commits, or git is unavailable; rather than
    letting such a registered file silently vanish from freshness, Plan B
    validates that every registered code-file has a committed content date.
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cs", "--", rel_path],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    out = completed.stdout.strip()
    if not out:
        return None
    try:
        return date.fromisoformat(out)
    except ValueError:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_code_git.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/code/git.py science/tests/test_code_git.py
git commit -m "feat(code): add git last-content-change date helper"
```

---

## Task 10: The `CodeAdapter`

**Files:**
- Create: `science/src/science_tool/graph/storage_adapters/code.py`
- Test: `science/tests/test_code_adapter.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_code_adapter.py`:

```python
from pathlib import Path

from science_tool.graph.storage_adapters.code import CodeAdapter


def _adapter(root: Path, **kw) -> CodeAdapter:
    return CodeAdapter(code_roots=(root / "code",), repo_root=root, excludes=kw.get("excludes", ()))


def test_discover_finds_code_files_and_applies_excludes(tmp_path: Path) -> None:
    (tmp_path / "code" / "stages").mkdir(parents=True)
    (tmp_path / "code" / "stages" / "run.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "code" / "notes.md").write_text("not code\n", encoding="utf-8")
    (tmp_path / "code" / "vendor").mkdir()
    (tmp_path / "code" / "vendor" / "lib.py").write_text("y=2\n", encoding="utf-8")

    refs = _adapter(tmp_path, excludes=("**/vendor/**",)).discover(tmp_path)
    paths = {ref.path for ref in refs}
    assert "code/stages/run.py" in paths
    assert "code/notes.md" not in paths       # not a code suffix
    assert "code/vendor/lib.py" not in paths   # excluded


def test_load_raw_blockless_file_returns_no_kind(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    f = tmp_path / "code" / "x.py"
    f.write_text("print(1)\n", encoding="utf-8")
    import os

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        from science_model.source_ref import SourceRef

        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/x.py"))
    finally:
        os.chdir(prev)
    assert "kind" not in raw


def test_load_raw_builds_code_file_record(tmp_path: Path) -> None:
    import os

    from science_model.source_ref import SourceRef

    (tmp_path / "code" / "stages").mkdir(parents=True)
    f = tmp_path / "code" / "stages" / "run.py"
    f.write_text(
        "# science:code\n# task_ids: [t491]\n# decision_bearing: true\n# status: workflow-owned\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/stages/run.py"))
    finally:
        os.chdir(prev)
    assert raw["kind"] == "code-file"
    assert raw["id"] == "code-file:stages/run.py"
    assert raw["title"] == "stages/run.py"
    assert raw["status"] == "workflow-owned"
    assert raw["decision_bearing"] is True
    assert raw["task_ids"] == ["t491"]
    assert raw["file_path"] == "code/stages/run.py"


def test_load_raw_invalid_block_returns_no_kind(tmp_path: Path) -> None:
    import os

    from science_model.source_ref import SourceRef

    (tmp_path / "code").mkdir()
    # unterminated block -> invalid -> skipped (Plan B diagnoses the malformed block)
    (tmp_path / "code" / "x.py").write_text("# science:code\n# status: library\nprint(1)\n", encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/x.py"))
    finally:
        os.chdir(prev)
    assert "kind" not in raw
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_code_adapter.py -q`
Expected: FAIL — `ModuleNotFoundError: …storage_adapters.code`.

- [ ] **Step 3: Implement the adapter**

Create `science/src/science_tool/graph/storage_adapters/code.py`:

```python
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.code.git import last_content_change_date
from science_tool.code.metadata import parse_code_metadata
from science_tool.graph.storage_adapters.base import StorageAdapter

_CODE_SUFFIXES = {".py", ".R", ".r", ".sh", ".smk"}


class CodeAdapter(StorageAdapter):
    """Register code files under declared roots as `code-file` entities.

    A file with a `# science:code` block becomes a code-file entity whose
    `updated` is its last content-changing commit date. A file with no block
    returns a record with no `kind` and is skipped by the loader (it is a
    ghost, flagged in Plan B).
    """

    name = "code-file"

    def __init__(self, *, code_roots: tuple[Path, ...], repo_root: Path, excludes: tuple[str, ...] = ()) -> None:
        self._code_roots = tuple(code_roots)
        self._repo_root = repo_root
        self._excludes = tuple(excludes)

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for root in self._code_roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or not self._is_code_file(path):
                    continue
                rel = path.relative_to(project_root).as_posix()
                if any(fnmatch(rel, pattern) for pattern in self._excludes):
                    continue
                refs.append(SourceRef(adapter_name=self.name, path=rel))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        abs_path = path if path.is_absolute() else Path.cwd() / path
        metadata = parse_code_metadata(abs_path.read_text(errors="replace"))
        if not metadata.valid:
            # absent OR invalid block -> no kind -> skipped by the loader.
            # Plan B distinguishes the two (ghost vs malformed) via metadata.error.
            return {"file_path": ref.path}
        fields = metadata.fields or {}
        local_id = self._local_id(ref.path)
        canonical_id = f"code-file:{local_id}"
        raw_task_ids = fields.get("task_ids")
        return {
            "id": canonical_id,
            "canonical_id": canonical_id,
            "kind": "code-file",
            "title": local_id,
            "status": str(fields.get("status") or ""),
            "decision_bearing": bool(fields.get("decision_bearing", False)),
            "task_ids": [str(t) for t in raw_task_ids] if isinstance(raw_task_ids, list) else [],
            "updated": last_content_change_date(ref.path, repo_root=self._repo_root),
            "content_preview": "",
            "file_path": ref.path,
        }

    def _is_code_file(self, path: Path) -> bool:
        return path.suffix in _CODE_SUFFIXES or path.name == "Snakefile"

    def _local_id(self, rel_path: str) -> str:
        for root in self._code_roots:
            root_rel = root.relative_to(self._repo_root).as_posix()
            if rel_path == root_rel:
                return Path(rel_path).name
            if rel_path.startswith(root_rel + "/"):
                return rel_path[len(root_rel) + 1 :]
        return rel_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_code_adapter.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/storage_adapters/code.py science/tests/test_code_adapter.py
git commit -m "feat(graph): add CodeAdapter for code-file entities"
```

---

## Task 11: Register `CodeAdapter` in the source-loading flow

**Files:**
- Modify: `science/src/science_tool/graph/sources.py` (`load_project_sources`, the `adapters` list ~lines 207-213)
- Test: `science/tests/test_code_sources_integration.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_code_sources_integration.py`:

```python
import os
import subprocess
from datetime import date
from pathlib import Path

from science_tool.graph.sources import load_project_sources

_MANIFEST = (
    "name: demo\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: demo\n"
    "profile: research\n"
    "layout_version: 1\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_load_project_sources_registers_code_file_entity(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    stages = tmp_path / "code" / "stages"
    stages.mkdir(parents=True)
    (stages / "run_fassoc.py").write_text(
        "# science:code\n# task_ids: [t491]\n# decision_bearing: true\n# status: workflow-owned\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )

    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)

    sources = load_project_sources(tmp_path, include_commons=False)
    code_file = next(e for e in sources.entities if e.id == "code-file:stages/run_fassoc.py")
    assert code_file.kind == "code-file"
    assert code_file.decision_bearing is True
    assert code_file.status == "workflow-owned"
    assert code_file.task_ids == ["t491"]
    assert code_file.updated == date(2026, 4, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_code_sources_integration.py -q`
Expected: FAIL — `StopIteration` (no `code-file:` entity is produced).

- [ ] **Step 3: Register the adapter**

In `sources.py`, add the imports near the other storage-adapter imports:

```python
from science_tool.graph.storage_adapters.code import CodeAdapter
from science_tool.paths import resolve_paths
```

In `load_project_sources`, just before the `adapters: list[StorageAdapter] = [` literal (line ~207), resolve topology:

```python
    project_paths = resolve_paths(project_root)
```

Append `CodeAdapter` to the `adapters` list:

```python
    adapters: list[StorageAdapter] = [
        MarkdownAdapter(virtual_files=markdown_overrides),
        AggregateAdapter(local_profile=local_profile),
        DatapackageAdapter(),
        WorkflowRunAdapter(),
        TaskAdapter(),
        CodeAdapter(
            code_roots=project_paths.code_roots,
            repo_root=project_root,
            excludes=project_paths.code_excludes,
        ),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_code_sources_integration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/tests/test_code_sources_integration.py
git commit -m "feat(graph): register CodeAdapter in load_project_sources"
```

---

## Task 12: Full-suite regression + docs

**Files:**
- Test: both packages
- Modify: `docs/plans/2026-05-21-code-file-entity-model-and-topology-plan.md` (mark complete) — optional

- [ ] **Step 1: Run the model suite**

Run: `cd science/model && uv run pytest -q`
Expected: PASS (no regressions from the new kind/relation/subclass).

- [ ] **Step 2: Run the tool suite**

Run: `cd science && uv run pytest -q`
Expected: PASS. Pay attention to `tests/test_kind_class.py::test_with_core_types_classifies_every_kind` (exhaustiveness) and `tests/validate/` (manifest + directory_structure).

- [ ] **Step 3: Commit any fixups**

```bash
git add -A
git commit -m "test: green full suite for code-file entity model + topology (Plan A)"
```

---

## What Plan A deliberately leaves to Plan B

- Ghost vs. malformed-block detection: a tree-walk `@Check` using the parser's three states — a file with `present is False` is a ghost; `present is True, fields is None` is a malformed block reported with its `error`. Plus classification (workflow-owned / orphaned / library / test / package-marker), the ported Snakemake reference parser (cross-file symbol table, rule-block splitting, wildcard glob), and hardcoded-path / metadata-gap detection.
- The staged `--fail-on` gate ladder at the CLI exit layer (keyed on `Result.rule`, leaving the `Result` dataclass and JSON schema untouched).
- Validating `code-file.task_ids` resolve to real tasks (a gateable Result, per the fragility firewall).
- Validating that every registered code-file has a committed content date — flagging files with a block but `updated is None` (untracked / never committed), so commit-only semantics never silently drop a source from freshness.

Plan A treats a Snakefile as a code-file and establishes the `defines`/`implements` relation *vocabulary*, but creates no edges; it also leaves the existing `workflow`/`workflow-step`/`workflow-run` kinds unchanged (they need no new fields to serve as relation targets).

And to Plan C: any field *enrichment* of the workflow kinds that edge materialization turns out to need; materializing `implements`/`defines`/`executes`/`produces`/`consumed_by` as graph edges; and the propagation contract (which derive `bears_on`, how OPERATIONAL nodes traverse closure) — i.e. actually making a code edit flip a downstream finding to `needs-review`.
