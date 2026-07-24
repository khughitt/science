# Gen-3 Dataset Write-Path Fix + Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the two project dataset writers persist a `schema_profile` that honors the project's declared `entity_schema_version`, so a gen-3 project writes `dataset/3.0` (not the frozen gen-2 default), and add a ratchet that keeps future writers from regressing.

**Architecture:** A single path-based pin reader (`project_entity_schema_version`) routes the write path through the same authority the loader uses. A dataset-profile resolver (`project_dataset_schema_profile`) maps the pin to `dataset/3.0` only at generation 3 (unpinned/1/2 keep `dataset/2.0`). Both writers default through the resolver instead of the import-time constant `BASE_DATASET_SCHEMA_PROFILE`, which is left in place only for commons callers where a fixed gen-2 default is correct. An AST reference-scan test forbids any non-commons module from referencing that constant (in any import, name, or attribute-access form).

**Tech Stack:** Python 3, Pydantic v2, Click, `pytest`, `ruff`, `pyright`, stdlib `ast`.

**Design:** [`2026-07-23-skill-coverage-writepath-design.md`](2026-07-23-skill-coverage-writepath-design.md).

## Global Constraints

- All `uv` commands run from the package directory: `cd science` for the CLI package, `cd science/model` for the model package. **Never** run `uv run` from the repo root.
- Use `uv run --frozen pytest` for tests; `uv run ruff check` and `uv run pyright` for lint/types (pyright from `science/`).
- Resolution rule (verbatim): `generation = 3 if pin == 3 else 2`. Unpinned (`None`), `1`, and `2` all keep `dataset/2.0`; only a pin of exactly `3` yields `dataset/3.0`.
- The gen-2/gen-3 dataset profile strings are `science-entity-base/1.0+dataset/2.0` and `science-entity-base/1.0+dataset/3.0` respectively (rendered by `default_profile_for_kind("dataset", generation=…).render()`).
- Explicit caller-provided `schema_profile` values must continue to win; only the *default* becomes generation-aware.
- `BASE_DATASET_SCHEMA_PROFILE` must remain untouched for commons callers (`commons/dataset_lifecycle.py`, `commons/cli.py`) — gen-2 is correct there.
- No AI-attribution trailers on commits. Composition over inheritance; explicit over defensive; fail early over silent fallback.

---

### Task 1: Pin reader `project_entity_schema_version`

**Files:**
- Modify: `science/src/science_tool/project_config.py` (add function after `load_project_config`, ~line 411)
- Test: `science/tests/test_project_config.py`

**Interfaces:**
- Consumes: existing module-level `validated_entity_schema_version(raw)`, `project_config_path(project_root)`, and the module's `yaml` import — all already present in `project_config.py`.
- Produces: `project_entity_schema_version(project_root: Path) -> int | None` — returns the validated pin (`1`/`2`/`3`) or `None` when the pin key is absent.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_project_config.py`. Fold any new names into the existing top-of-file import block (the file already imports `Path`, `pytest`, and from `science_tool.project_config`); add `project_entity_schema_version` to the existing `from science_tool.project_config import (...)` group.

```python
def test_project_entity_schema_version_reads_pin(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: p\nentity_schema_version: 3\nknowledge_profiles: {}\n", encoding="utf-8"
    )
    assert project_entity_schema_version(tmp_path) == 3


def test_project_entity_schema_version_absent_is_none(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: p\nknowledge_profiles: {}\n", encoding="utf-8"
    )
    assert project_entity_schema_version(tmp_path) is None


def test_project_entity_schema_version_missing_config_is_none(tmp_path):
    # A bare directory with no science.yaml is unpinned, not an error -- mirrors how the
    # graph loader treats a missing config. Existing dataset-add tests pass bare tmp_path
    # dirs through add_dataset, which now routes here.
    assert project_entity_schema_version(tmp_path) is None


def test_project_entity_schema_version_rejects_illegal_pin(tmp_path):
    # A present-but-illegal pin must raise, not degrade to unpinned.
    (tmp_path / "science.yaml").write_text(
        'name: p\nentity_schema_version: "3"\nknowledge_profiles: {}\n', encoding="utf-8"
    )
    with pytest.raises(ValueError):
        project_entity_schema_version(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k project_entity_schema_version -v`
Expected: FAIL / ERROR — `project_entity_schema_version` is not defined (ImportError).

- [ ] **Step 3: Write minimal implementation**

Add to `science/src/science_tool/project_config.py` immediately after `load_project_config` (~line 412):

```python
def project_entity_schema_version(project_root: Path) -> int | None:
    """The project's declared entity_schema_version pin (1/2/3), or None if unpinned.

    Reads the raw science.yaml mapping and validates through the single authority
    (`validated_entity_schema_version`) -- no full ProjectConfig required, exactly as the
    graph loader reads the pin (`graph/sources.py`). This keeps the write path and the load
    path reading the generation through one function, so they can never disagree. A missing
    science.yaml is unpinned (None), not an error, mirroring the loader -- write sites like
    `add_dataset` are exercised against bare directories that have no config.
    """
    path = project_config_path(project_root)
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return validated_entity_schema_version(raw)
```

Step 4's run must include the missing-config test (`-k project_entity_schema_version` covers all four).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k project_entity_schema_version -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "feat(config): add path-based entity_schema_version pin reader"
```

---

### Task 2: Dataset-profile resolver `project_dataset_schema_profile`

**Files:**
- Modify: `science/src/science_tool/identity_authoring.py` (add function near `BASE_DATASET_SCHEMA_PROFILE`, ~line 19)
- Test: `science/tests/test_identity_authoring.py`

**Interfaces:**
- Consumes: `project_entity_schema_version` (Task 1) from `science_tool.project_config`; existing `default_profile_for_kind` (already imported in `identity_authoring.py`).
- Produces: `project_dataset_schema_profile(project_root: Path) -> str` — the default dataset `schema_profile` string honoring the pin: `science-entity-base/1.0+dataset/3.0` when the pin is exactly `3`, else `science-entity-base/1.0+dataset/2.0`.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_identity_authoring.py` (fold `project_dataset_schema_profile` into the existing import from `science_tool.identity_authoring`; add `from pathlib import Path` only if not already present):

```python
def _write_science_yaml(root, pin_line=""):
    (root / "science.yaml").write_text(
        f"name: p\n{pin_line}knowledge_profiles: {{}}\n", encoding="utf-8"
    )


def test_project_dataset_schema_profile_gen3(tmp_path):
    _write_science_yaml(tmp_path, "entity_schema_version: 3\n")
    assert (
        project_dataset_schema_profile(tmp_path)
        == "science-entity-base/1.0+dataset/3.0"
    )


def test_project_dataset_schema_profile_gen2(tmp_path):
    _write_science_yaml(tmp_path, "entity_schema_version: 2\n")
    assert (
        project_dataset_schema_profile(tmp_path)
        == "science-entity-base/1.0+dataset/2.0"
    )


def test_project_dataset_schema_profile_unpinned_is_gen2(tmp_path):
    _write_science_yaml(tmp_path)
    assert (
        project_dataset_schema_profile(tmp_path)
        == "science-entity-base/1.0+dataset/2.0"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_identity_authoring.py -k project_dataset_schema_profile -v`
Expected: FAIL / ERROR — `project_dataset_schema_profile` is not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `science/src/science_tool/identity_authoring.py` immediately after the `BASE_DATASET_SCHEMA_PROFILE` definition (~line 19). Add the import at the top-of-file import block:

```python
from science_tool.project_config import project_entity_schema_version
```

```python
def project_dataset_schema_profile(project_root: Path) -> str:
    """Default schema_profile for a PROJECT dataset record, honoring the project's pin.

    Only generation 3 changes the dataset shape, so any project not pinned generation 3
    (unpinned, 1, or 2) keeps `dataset/2.0` -- no regression for existing projects, and no
    attempt to resolve a generation-1 mixin row (which does not exist).
    """
    pin = project_entity_schema_version(project_root)
    return default_profile_for_kind("dataset", generation=3 if pin == 3 else 2).render()
```

If `Path` is not already imported in `identity_authoring.py`, add `from pathlib import Path` to the import block.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_identity_authoring.py -k project_dataset_schema_profile -v`
Expected: PASS (3 tests).

Confirm no import cycle was introduced:
Run: `cd science && uv run --frozen python -c "import science_tool.identity_authoring"`
Expected: exits 0 (no ImportError).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/identity_authoring.py science/tests/test_identity_authoring.py
git commit -m "feat(identity): add generation-aware dataset schema_profile resolver"
```

---

### Task 3: `add_dataset` defaults through the resolver

**Files:**
- Modify: `science/src/science_tool/datasets_catalog.py` (`add_dataset`, ~line 93-135; import block ~line 23-27)
- Modify: `science/src/science_tool/datasets/cli.py` (~line 370, ~line 394)
- Test: `science/tests/test_dataset_add_cli.py`

**Interfaces:**
- Consumes: `project_dataset_schema_profile` (Task 2).
- Produces: `add_dataset(project_root, slug, *, ..., schema_profile: str | None = None, ...)` — when `schema_profile is None`, the persisted default is resolved from the project's pin.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_dataset_add_cli.py`. Reuse the file's existing project-scaffolding fixture/helper if present; otherwise construct a minimal project. The test calls `add_dataset` directly (the library surface) against a gen-3 project and asserts the written frontmatter:

```python
import yaml


def _dataset_profile(dest) -> str:
    # add_dataset writes frontmatter via yaml.safe_dump; parse it rather than string-match
    # so the assertion is independent of quoting.
    return yaml.safe_load(dest.read_text(encoding="utf-8").split("---", 2)[1])["schema_profile"]


def test_add_dataset_uses_gen3_profile_when_pinned(tmp_path):
    from science_tool.datasets_catalog import add_dataset

    (tmp_path / "science.yaml").write_text(
        "name: p\nentity_schema_version: 3\nknowledge_profiles: {}\n", encoding="utf-8"
    )
    (tmp_path / "entities" / "datasets").mkdir(parents=True)

    _id, dest, _warnings = add_dataset(
        tmp_path, "my-set", title="My Set", origin="external", dataset_class="deposit"
    )
    assert _dataset_profile(dest) == "science-entity-base/1.0+dataset/3.0"


def test_add_dataset_defaults_gen2_when_unpinned(tmp_path):
    from science_tool.datasets_catalog import add_dataset

    (tmp_path / "science.yaml").write_text(
        "name: p\nknowledge_profiles: {}\n", encoding="utf-8"
    )
    (tmp_path / "entities" / "datasets").mkdir(parents=True)

    _id, dest, _warnings = add_dataset(
        tmp_path, "my-set", title="My Set", origin="external", dataset_class="deposit"
    )
    assert _dataset_profile(dest) == "science-entity-base/1.0+dataset/2.0"
```

Note: if `add_dataset`'s `_validate_prospective_write` rejects a minimal candidate under a gen-3 project (rather than warning), that is a real interaction to **surface**, not paper over — report it as a blocker rather than weakening the pin or skipping validation.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_dataset_add_cli.py -k gen3_profile_when_pinned -v`
Expected: FAIL — the written profile is `dataset/2.0` (the frozen constant), not `dataset/3.0`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/datasets_catalog.py`:

Change the `add_dataset` signature default (~line 105):

```python
    schema_profile: str | None = None,
```

Resolve the default inside `add_dataset`, before the `require_profile_identity` call (~line 125-127). Insert after `identity_context = identity_context or {}`:

```python
    if schema_profile is None:
        schema_profile = project_dataset_schema_profile(project_root)
```

Update the `from science_tool.identity_authoring import (...)` group (~line 23-27): remove `BASE_DATASET_SCHEMA_PROFILE`, add `project_dataset_schema_profile`. If `BASE_DATASET_SCHEMA_PROFILE` is used nowhere else in this module (confirm with a grep), its import must be removed so the Task 5 guard passes.

In `science/src/science_tool/datasets/cli.py`:

Remove `BASE_DATASET_SCHEMA_PROFILE` from the import at ~line 370. Change the `add_dataset(...)` call at ~line 394 from:

```python
            schema_profile=BASE_DATASET_SCHEMA_PROFILE if schema_profile is None else schema_profile,
```

to:

```python
            schema_profile=schema_profile,
```

(`schema_profile` is the CLI's `str | None` option; `add_dataset` now resolves `None` itself.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_dataset_add_cli.py -v`
Expected: PASS — new tests plus all pre-existing `add`-cli tests (regression check for the CLI wiring change).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets_catalog.py science/src/science_tool/datasets/cli.py science/tests/test_dataset_add_cli.py
git commit -m "feat(dataset): add resolves schema_profile default from project generation"
```

---

### Task 4: `register-run` writers default through the resolver

**Files:**
- Modify: `science/src/science_tool/datasets_register.py` (`_entity_yaml_block` ~line 217-232; `_output_schema_profile` ~line 281-287; `preflight_register_run_identity` ~line 752-774; `write_derived_dataset_entities` ~line 777-822; import block ~line 31)
- Test: `science/tests/test_dataset_register_run.py`
- Test: `science/tests/test_authoring_emitted_profile.py` (its `_entity_yaml_block` renderer test must adapt to the now-required `schema_profile` argument)

**Interfaces:**
- Consumes: `project_dataset_schema_profile` (Task 2).
- Produces: `_output_schema_profile(out: dict, default_profile: str) -> str` (now takes the resolved default explicitly); `_entity_yaml_block(..., schema_profile: str, ...)` (default removed — always passed explicitly). `write_derived_dataset_entities` persists `dataset/3.0` in a gen-3 project when an output omits `schema_profile`.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_dataset_register_run.py`, using the file's existing idiom: `_seed_workflow_and_run` (writes an unpinned `science.yaml`, workflow outputs that omit `schema_profile`), `_seed_resource_files`, the CLI-driven `_run_register`, and `_frontmatter` (yaml-parses the written entity). The derived entity for run `workflow-run:wf-r1` and output slug `kappa` lands at `entities/datasets/wf-r1-kappa.md`. The test pins the seeded project to generation 3 (the seed leaves it unpinned), then asserts the persisted `schema_profile`:

```python
def test_register_run_writes_gen3_profile_when_pinned(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv", "bytes": 100, "hash": "sha256:a"},
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])
    # The seed writes an unpinned science.yaml; pin it to generation 3.
    sci = tmp_path / "science.yaml"
    sci.write_text(sci.read_text(encoding="utf-8") + "entity_schema_version: 3\n", encoding="utf-8")

    res = _run_register(tmp_path)
    assert res.exit_code == 0, res.output

    fm = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md")
    assert fm["schema_profile"] == "science-entity-base/1.0+dataset/3.0"
```

This exercises the default path because the inferred workflow output omits `schema_profile`, so `_output_schema_profile` returns the resolved default.

Also add a **persisted unpinned/gen-2 witness** in the same file — the existing `test_register_run_writes_dataset_entities` (~line 573) asserts id/origin/datapackage but **not** `schema_profile`, so nothing currently pins the persisted register-run default:

```python
def test_register_run_writes_gen2_profile_when_unpinned(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv", "bytes": 100, "hash": "sha256:a"},
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])
    # _seed_workflow_and_run leaves science.yaml unpinned.
    res = _run_register(tmp_path)
    assert res.exit_code == 0, res.output

    fm = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md")
    assert fm["schema_profile"] == "science-entity-base/1.0+dataset/2.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_dataset_register_run.py -k gen3_profile_when_pinned -v`
Expected: FAIL — written profile is `dataset/2.0`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/datasets_register.py`:

Update `_output_schema_profile` (~line 281) to take the resolved default:

```python
def _output_schema_profile(out: dict, default_profile: str) -> str:
    if "schema_profile" not in out:
        return default_profile
    value = out["schema_profile"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"output {out.get('slug')!r} has blank schema_profile")
    return value
```

Remove the default from `_entity_yaml_block` (~line 230): change `schema_profile: str = BASE_DATASET_SCHEMA_PROFILE,` to `schema_profile: str,`. The renderer is now a pure function of its argument — a project-aware default belongs to the write path (`_output_schema_profile` + the resolver), not the renderer.

This breaks `test_register_run_renderer_emits_the_default_profile` in `science/tests/test_authoring_emitted_profile.py:46`, which calls `_entity_yaml_block` with no `schema_profile`. Update that test to pass the argument explicitly and assert the renderer emits exactly what it is given (it no longer has a "default" to witness):

```python
def test_register_run_renderer_emits_the_given_profile() -> None:
    block = _entity_yaml_block(
        slug="mock-derived",
        title="Mock derived",
        workflow_id="workflow:mock",
        workflow_run_id="run-1",
        git_commit="abc1234",
        config_snapshot="{}",
        produced_at="2026-07-16T00:00:00Z",
        inputs=["dataset:mock-cohort"],
        transformations=None,
        dp_path_rel="data/mock-derived/datapackage.yaml",
        ontology_terms=[],
        schema_profile=EXPECTED,
    )

    assert f'schema_profile: "{EXPECTED}"' in block
```

Leave the other two tests in that file unchanged: `test_expected_profile_tracks_the_shared_default` (the gen-2 anchor) and `test_project_dataset_authoring_emits_the_default_profile` (which calls `add_dataset` on a bare `tmp_path`; with the Task 1 `is_file` guard, missing config → unpinned → gen-2 = `EXPECTED`, so it still passes and remains the add-path default witness for fb-2026-07-12-006).

In `write_derived_dataset_entities` (~line 777), compute the resolved default once after `inputs = ...` (~line 789) and pass it into `_output_schema_profile`:

```python
    default_profile = project_dataset_schema_profile(project_root)
```

Change line ~807 from `_output_schema_profile(out)` to `_output_schema_profile(out, default_profile)`.

In `preflight_register_run_identity` (~line 752), compute the same default once after `outputs = ...` (~line 757) and pass it into both `_output_schema_profile` calls (~line 759, 773):

```python
    default_profile = project_dataset_schema_profile(project_root)
```

Change line ~759 `_output_schema_profile(out)` → `_output_schema_profile(out, default_profile)` and line ~773 `_output_schema_profile(out)` → `_output_schema_profile(out, default_profile)`.

Update the import at ~line 31: remove `BASE_DATASET_SCHEMA_PROFILE`, keeping `ASSEMBLY_REGISTRY_ID` and `require_profile_identity`, and add `project_dataset_schema_profile`:

```python
from science_tool.identity_authoring import ASSEMBLY_REGISTRY_ID, project_dataset_schema_profile, require_profile_identity
```

Confirm `BASE_DATASET_SCHEMA_PROFILE` is referenced nowhere else in `datasets_register.py` (grep) before removing the import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_dataset_register_run.py tests/test_authoring_emitted_profile.py -v`
Expected: PASS — the new gen-3 and gen-2 register-run tests, the adapted renderer test, all pre-existing register-run tests (regression check for the `_output_schema_profile`/`_entity_yaml_block` signature changes and the preflight path), and the two unchanged `test_authoring_emitted_profile.py` witnesses.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets_register.py science/tests/test_dataset_register_run.py science/tests/test_authoring_emitted_profile.py
git commit -m "feat(dataset): register-run resolves schema_profile default from project generation"
```

---

### Task 5: Import-choke regression guard

**Files:**
- Create: `science/tests/test_dataset_profile_boundary.py`

**Interfaces:**
- Consumes: the post-Task-3/4 source tree, in which only commons modules import `BASE_DATASET_SCHEMA_PROFILE`.
- Produces: a boundary test asserting that invariant.

- [ ] **Step 1: Write the failing-if-violated test**

Create `science/tests/test_dataset_profile_boundary.py`:

```python
"""Dataset-profile reference boundary guard.

`BASE_DATASET_SCHEMA_PROFILE` is the FIXED generation-2 dataset profile. It is correct only
for commons dataset callers, whose `dataset` mixin stays `dataset/2.0` across generations.
Every PROJECT dataset writer must instead default through `project_dataset_schema_profile`,
which honors the project's `entity_schema_version` pin.

This scans EVERY reference to the constant, not just `from ... import` edges: a from-import
plus its `Name` uses, an aliased module attribute
(`import ... as ia; ia.BASE_DATASET_SCHEMA_PROFILE`), and a star import from the defining
module. Detecting only `ImportFrom` would miss the attribute-access and star-import spellings.
Deny-by-default: the whole `science_tool` tree is scanned and only the commons package is
allowlisted, so a future project-side writer that reaches for the raw gen-2 constant fails
here and is forced through the resolver.

The defining module is scanned too. Only the constant's top-level assignment target is
exempt; any load of the constant there remains forbidden.

Known limit, stated rather than hidden: matching the bare name as an attribute would also flag
an unrelated symbol that happened to share the exact name `BASE_DATASET_SCHEMA_PROFILE`. No such
collision exists in this tree, and the name is specific enough that one is implausible.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_CONSTANT = "BASE_DATASET_SCHEMA_PROFILE"
_DEFINING_MODULE = _SCIENCE_SRC / "identity_authoring.py"

# Only commons callers may reference the fixed gen-2 constant (gen-2 is correct for commons).
_ALLOWED_DIR = _SCIENCE_SRC / "commons"


def _references_constant(path: Path) -> bool:
    """True if the module contains a forbidden constant binding or access."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defining_assignment_target = None
    if path == _DEFINING_MODULE:
        defining_assignment_target = next(
            (
                target
                for statement in tree.body
                if isinstance(statement, ast.Assign)
                for target in statement.targets
                if isinstance(target, ast.Name) and target.id == _CONSTANT
            ),
            None,
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == _CONSTANT:
                    return True
                if alias.name == "*" and module.endswith("identity_authoring"):
                    return True
        elif isinstance(node, ast.Name) and node.id == _CONSTANT:
            if node is defining_assignment_target:
                continue
            return True
        elif isinstance(node, ast.Attribute) and node.attr == _CONSTANT:
            return True
    return False


def test_defining_module_assignment_target_is_allowed():
    assert not _references_constant(_DEFINING_MODULE)


def test_defining_module_constant_load_is_forbidden(tmp_path: Path, monkeypatch):
    defining_module = tmp_path / "identity_authoring.py"
    defining_module.write_text(
        f'{_CONSTANT} = "fixed-default"\nresolved = {_CONSTANT}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "_DEFINING_MODULE", defining_module)

    assert _references_constant(defining_module)


def test_base_dataset_schema_profile_reference_is_commons_only():
    offenders = []
    for path in _SCIENCE_SRC.rglob("*.py"):
        if _ALLOWED_DIR in path.parents:
            continue
        if _references_constant(path):
            offenders.append(str(path.relative_to(_SCIENCE_SRC)))
    assert offenders == [], (
        f"{_CONSTANT} is the fixed gen-2 dataset profile; these non-commons modules reference it "
        f"instead of defaulting through project_dataset_schema_profile: {offenders}"
    )
```

- [ ] **Step 2: Run test to verify current state**

Run: `cd science && uv run --frozen pytest tests/test_dataset_profile_boundary.py -v`
Expected: PASS — all three focused/boundary tests pass. Tasks 3 and 4 already removed the `datasets_catalog.py`, `datasets/cli.py`, and `datasets_register.py` references, so only `commons/**` references and the exempt top-level defining assignment remain. If it FAILS, the offenders list names a module whose reference was missed in Task 3/4 — fix that module, then re-run.

- [ ] **Step 3: Prove the guard bites inside the defining module**

The stronger rule scans `identity_authoring.py` rather than excluding it wholesale. Temporarily
add a real load immediately after the constant's assignment:
```python
_BOUNDARY_GUARD_MUTATION = BASE_DATASET_SCHEMA_PROFILE  # temp
```
Run: `cd science && uv run --frozen pytest tests/test_dataset_profile_boundary.py -v` → FAIL,
with `identity_authoring.py` in the offenders list. Revert the temporary load.

- [ ] **Step 4: Re-run to confirm green after revert**

Run: `cd science && uv run --frozen pytest tests/test_dataset_profile_boundary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_dataset_profile_boundary.py
git commit -m "test(dataset): guard BASE_DATASET_SCHEMA_PROFILE references to commons only"
```

---

### Final verification gate

Run the full suites, lint, and types before finishing the branch:

```bash
cd science/model && uv run --frozen pytest && uv run ruff check
cd .. && uv run --frozen pytest && uv run ruff check && uv run pyright
```

Expected: all green. The `science` suite exercises the changed writers, the CLI wiring, and the boundary guard; `pyright` (configured once at the repo root, covering all three source trees) confirms the signature changes typecheck.
