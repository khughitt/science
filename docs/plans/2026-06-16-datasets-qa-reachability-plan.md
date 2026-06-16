# `science datasets qa` Reachability — Implementation Plan (Spec 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing `science_qa` schema-driven QA engine through a new `science datasets qa <package>` command that runs QA across a datapackage's tabular resources and reports a package-level verdict.

**Architecture:** Add package-level aggregation (`run_qa_package`) + a neutral JSON/YAML descriptor loader to the `science_qa` distribution, reusing the per-resource engine unchanged behind a behavior-preserving `_evaluate`/`_run_with_config` split. A thin `science_tool` command resolves the path, calls the engine in-process (`science_tool` already depends on `science_qa`), renders text/json, and sets a build-fatal exit code. The one-way boundary — `science_qa` never imports `science_tool` — is preserved.

**Tech Stack:** Python 3.11, `science_qa` (pandas / pyarrow / pyyaml / click, NO pydantic), `science_tool` (click), Frictionless Data Package / Table Schema v2.

---

## Reference: spec

Design doc: `docs/plans/2026-06-16-datasets-qa-reachability-design.md`. Read §3 (locked
decisions), §4 (command surface + text/json output), §5.0 (neutral timestamp-safe
loader), §5.1 (the `_evaluate` split), §5.2 (`run_qa_package` + classification +
resource-scoped reports), §6 (thin command + explicit exit-2 catch list), §7 (errors),
§8 (scope boundaries). This plan implements that design; where they differ, the design
wins.

**Deferred (NOT in this plan):** §5.3's optional standalone `science_qa run --datapackage P`
(no `--resource`) package mode — the deliverable calls `run_qa_package` in-process, so the
standalone-CLI package mode is unnecessary. Leave it out (YAGNI).

## Workspace, conventions & test recipe

**Workspace:** implement in the **existing** worktree `~/d/science/.worktrees/datasets-qa-reachability`
(branch `feat/datasets-qa-reachability`) — already created and holding the two Spec-4 docs.
Do NOT create a new worktree.

**Test recipe.** The framework venv lives at the **main** checkout (`~/d/science/science/.venv`);
the worktree has no venv of its own and editable installs resolve to the *main* checkout
unless shadowed with `PYTHONPATH`. Always set `PYTHONPATH` so imports resolve to the
worktree source. Define once:

```bash
WT=~/d/science/.worktrees/datasets-qa-reachability
PY=~/d/science/science/.venv/bin/python
```

- **`science_qa` tests** (engine) — run from `science/qa`, shadow with `PYTHONPATH=src`:
  ```bash
  cd "$WT/science/qa"
  PYTHONPATH=src $PY -m pytest tests/<file>.py -v        # one file
  PYTHONPATH=src $PY -m pytest tests -q                  # whole science_qa suite
  ```
  (subprocess CLI tests inherit this `PYTHONPATH=src`, so `-m science_qa` runs worktree source.)

- **`science_tool` tests** (command) — run from `science`, shadow BOTH packages with
  `PYTHONPATH=src:qa/src` (the command imports `science_qa`):
  ```bash
  cd "$WT/science"
  PYTHONPATH=src:qa/src $PY -m pytest tests/<file>.py -v
  ```

**Commit hygiene:** `git add` only the explicit files named in each task — never `-A`/`.`
(the `.git` metadata is Dropbox-synced and a parallel workstream may advance HEAD
mid-session). If you find conflict markers or changes in files outside your task's scope,
STOP and report BLOCKED. **Before each commit, verify the branch**
(`git -C "$WT" branch --show-current`) is `feat/datasets-qa-reachability`, not `main`.

**No `Co-Authored-By` trailers.** Use `~/d/` (not absolute Dropbox paths) in any doc/code text.

## File structure

| File | Responsibility |
|---|---|
| `science/qa/src/science_qa/package.py` (**create**) | `load_package` — neutral JSON/YAML descriptor loader with the implicit-timestamp resolver removed |
| `science/qa/src/science_qa/runner.py` (**modify**) | `RunResult.rows_checked`; `_evaluate` split; `run_qa_datapackage` via `load_package`; `ResourceOutcome`, `PackageRunResult`, `run_qa_package`, `package_report_dict`, `write_package_report` |
| `science/qa/tests/test_package.py` (**create**) | `load_package` JSON/YAML + ISO-stays-string |
| `science/qa/tests/test_runner.py` (**modify**) | `rows_checked`; YAML single-resource; `run_qa_package` classification + collision + report |
| `science/src/science_tool/datasets/qa.py` (**create**) | `run_package_qa` wrapper: descriptor resolution, in-process call, exit-code policy, text renderers |
| `science/src/science_tool/cli.py` (**modify**) | register `@datasets.command("qa")` |
| `science/tests/test_datasets_qa.py` (**create**) | wrapper unit tests: resolution, exit matrix, json==file, loader drift guard |
| `science/tests/test_datasets_qa_cli.py` (**create**) | `CliRunner` end-to-end |

---

## Task 1: `RunResult.rows_checked` + behavior-preserving `_evaluate` split

**Files:**
- Modify: `science/qa/src/science_qa/runner.py:29-33` (RunResult), `:73-101` (`_run_with_config`)
- Test: `science/qa/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Append to `science/qa/tests/test_runner.py`:

```python
def test_run_qa_datapackage_exposes_rows_checked(tmp_path):
    import json as _json
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "id", "type": "integer"}]}}
    pd.DataFrame({"id": [1, 2, 3, 4]}).to_parquet(tmp_path / "obs.parquet")
    (tmp_path / "datapackage.json").write_text(_json.dumps({"name": "p", "resources": [res]}))
    result = run_qa_datapackage(tmp_path / "datapackage.json", "obs", tmp_path)
    assert result.rows_checked == 4
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py::test_run_qa_datapackage_exposes_rows_checked -v`
Expected: FAIL — `AttributeError: 'RunResult' object has no attribute 'rows_checked'`.

- [ ] **Step 3: Add the field and split the core**

In `science/qa/src/science_qa/runner.py`, add `rows_checked` to the dataclass:

```python
@dataclass
class RunResult:
    flags: list[Flag]
    structural_failed: bool
    coverage: Coverage
    rows_checked: int
```

Then replace the whole `_run_with_config` function (lines 73-101) with the split — a
non-writing `_evaluate` plus a thin `_run_with_config` that writes:

```python
def _evaluate(config: QAConfig, table_path: Path) -> RunResult:
    """Compile-independent core: resolve program, read table, run checks.

    Returns a RunResult (incl. rows_checked = len(table)). Writes nothing, reconciles
    nothing — so the package runner can call it per-resource and write ONE report."""
    program = resolve_program(config.program)
    built_in_ids = {spec.check_id for spec in program.checks}
    checks = [*program.checks, *load_project_local(config.project_local, reserved_check_ids=built_in_ids)]
    table = _read_table(table_path)

    # static program <-> substrate validation, before any context is built
    for spec in checks:
        if spec.accepts is not program.substrate:
            raise RunnerError(f"check {spec.check_id} accepts {spec.accepts.__name__}, "
                              f"program {program.name} binds {program.substrate.__name__}")

    flags: list[Flag] = []
    coverage = Coverage()

    for spec in checks:
        invs = _invocations(spec, config)
        if spec.expand is not None and not invs:
            coverage.unconfigured_families.append(spec.check_id)
            continue
        for inv in invs:
            entry = _run_invocation(spec, inv, table, config, flags)
            coverage.entries.append(entry)

    structural_failed = any(f.severity == SEVERITY_STRUCTURAL for f in flags)
    return RunResult(flags=flags, structural_failed=structural_failed,
                     coverage=coverage, rows_checked=len(table))


def _run_with_config(config: QAConfig, table_path: Path, report_dir: Path) -> RunResult:
    result = _evaluate(config, table_path)
    write_reports(result.flags, report_dir=report_dir,
                  rows_checked=result.rows_checked, coverage=result.coverage)
    distribution_ids = [f.flag_id for f in result.flags if f.severity == SEVERITY_DISTRIBUTION]
    reconcile_dispositions(report_dir, distribution_ids)
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py -v`
Expected: PASS — the new test plus every existing `run_qa`/`run_qa_datapackage` test
(behavior is byte-equivalent; only the row count is now surfaced).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/runner.py science/qa/tests/test_runner.py
git commit -m "feat(qa): RunResult.rows_checked + non-writing _evaluate core"
```

---

## Task 2: neutral timestamp-safe `load_package`

**Files:**
- Create: `science/qa/src/science_qa/package.py`
- Test: `science/qa/tests/test_package.py`

- [ ] **Step 1: Write the failing tests**

Create `science/qa/tests/test_package.py`:

```python
from pathlib import Path

import pytest
from science_qa.package import load_package


def test_load_json(tmp_path):
    (tmp_path / "datapackage.json").write_text('{"name": "p", "resources": []}')
    mapping, base = load_package(tmp_path / "datapackage.json")
    assert mapping["name"] == "p" and base == tmp_path


def test_load_yaml(tmp_path):
    (tmp_path / "datapackage.yaml").write_text("name: p\nresources: []\n")
    mapping, base = load_package(tmp_path / "datapackage.yaml")
    assert mapping["name"] == "p" and base == tmp_path


def test_unquoted_iso_date_stays_string(tmp_path):
    # the false-CompileError regression: a YAML date bound must remain a str
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: r\n    path: r.csv\n    schema:\n      fields:\n"
        "        - name: d\n          type: date\n"
        "          constraints: {maximum: 2020-01-01}\n")
    mapping, _ = load_package(tmp_path / "datapackage.yaml")
    bound = mapping["resources"][0]["schema"]["fields"][0]["constraints"]["maximum"]
    assert bound == "2020-01-01" and isinstance(bound, str)


def test_unknown_extension_rejected(tmp_path):
    (tmp_path / "datapackage.txt").write_text("nope")
    with pytest.raises(ValueError, match="extension"):
        load_package(tmp_path / "datapackage.txt")


def test_malformed_yaml_rejected_as_value_error(tmp_path):
    (tmp_path / "datapackage.yaml").write_text("name: [unterminated\n")
    with pytest.raises(ValueError, match="malformed yaml descriptor"):
        load_package(tmp_path / "datapackage.yaml")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_package.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_qa.package'`.

- [ ] **Step 3: Create `package.py`**

Create `science/qa/src/science_qa/package.py`:

```python
# science/qa/src/science_qa/package.py
"""Neutral datapackage descriptor loader for science_qa (JSON or YAML).

Kept inside science_qa so the QA engine owns descriptor loading without depending on the
main CLI package. The implicit *timestamp* resolver is removed so an unquoted ISO-8601
scalar stays a str — otherwise a YAML date bound (e.g. `maximum: 2020-01-01`) would parse
to a datetime.date and the Spec 2 compiler (which accepts only str|int|float bound values)
would raise a false CompileError.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

_FMT_BY_SUFFIX = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


class _TimestampSafeLoader(yaml.SafeLoader):
    """SafeLoader with the implicit timestamp resolver removed (ISO scalars stay str)."""


_TimestampSafeLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_package(path: Path) -> tuple[dict, Path]:
    """Load a datapackage descriptor mapping + its base directory.

    `path` is the descriptor file (datapackage.json / .yaml / .yml). Returns
    (mapping, base_dir) where base_dir is the descriptor's parent (resource `path`s
    resolve against it). Raises ValueError on an unsupported extension.
    """
    path = Path(path)
    fmt = _FMT_BY_SUFFIX.get(path.suffix.lower())
    if fmt is None:
        raise ValueError(f"unsupported descriptor extension {path.suffix!r} (want .json/.yaml/.yml)")
    text = path.read_text(encoding="utf-8")
    try:
        mapping = json.loads(text) if fmt == "json" else yaml.load(text, Loader=_TimestampSafeLoader)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed json descriptor {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed yaml descriptor {path}: {exc}") from exc
    if not isinstance(mapping, dict):
        raise ValueError(f"descriptor {path} did not parse to a mapping")
    return mapping, path.parent
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_package.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/package.py science/qa/tests/test_package.py
git commit -m "feat(qa): neutral timestamp-safe load_package (json+yaml)"
```

---

## Task 3: `run_qa_datapackage` loads via `load_package` (JSON + YAML)

**Files:**
- Modify: `science/qa/src/science_qa/runner.py:58-70` (`run_qa_datapackage`), imports
- Test: `science/qa/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Append to `science/qa/tests/test_runner.py`:

```python
def test_run_qa_datapackage_reads_yaml(tmp_path):
    from science_qa.runner import run_qa_datapackage
    pd.DataFrame({"id": [1, 2, 3]}).to_parquet(tmp_path / "obs.parquet")
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: obs\n    path: obs.parquet\n    schema:\n      fields:\n"
        "        - name: id\n          type: integer\n          constraints: {required: true}\n")
    result = run_qa_datapackage(tmp_path / "datapackage.yaml", "obs", tmp_path)
    assert result.structural_failed is False and result.rows_checked == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py::test_run_qa_datapackage_reads_yaml -v`
Expected: FAIL — `json.loads` chokes on YAML (`json.decoder.JSONDecodeError`).

- [ ] **Step 3: Switch the loader**

In `science/qa/src/science_qa/runner.py`, add the import (next to the other `science_qa`
imports, e.g. after line 19):

```python
from science_qa.package import load_package
```

Replace the body of `run_qa_datapackage` (lines 58-70) so it uses `load_package` instead
of `json.loads` (the `import json` at line 4 stays — it is still used elsewhere):

```python
def run_qa_datapackage(datapackage_path: Path, resource_name: str, report_dir: Path,
                       runknobs_path: Path | None = None) -> RunResult:
    package, pkg_dir = load_package(Path(datapackage_path))
    resource = next((r for r in package.get("resources", []) if r.get("name") == resource_name), None)
    if resource is None:
        raise CompileError(f"resource {resource_name!r} not found in {datapackage_path}")
    config = schema_to_config(resource, pkg_dir, package)
    if runknobs_path is not None:
        config = merge_configs(config, QAConfig.from_file(runknobs_path, require_program=False))
    if not config.program:
        config.program = "tabular"
    return _run_with_config(config, pkg_dir / resource["path"], report_dir)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py -v`
Expected: PASS — the YAML test plus every existing JSON `run_qa_datapackage` test
(`load_package` reads JSON identically to the old `json.loads`).

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/runner.py science/qa/tests/test_runner.py
git commit -m "feat(qa): run_qa_datapackage reads json or yaml via load_package"
```

---

## Task 4: `run_qa_package` + classification (no report writing yet)

**Files:**
- Modify: `science/qa/src/science_qa/runner.py` (append dataclasses + functions)
- Test: `science/qa/tests/test_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_runner.py`:

```python
def _yaml_pkg(tmp_path, body: str) -> Path:
    (tmp_path / "datapackage.yaml").write_text(body)
    return tmp_path / "datapackage.yaml"


def test_package_clean_multi_resource_ok(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"v": [0.1, 0.2]}).to_parquet(tmp_path / "b.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n"
        "  - name: b\n    path: b.parquet\n    schema: {fields: [{name: v, type: number}]}\n")
    result = run_qa_package(dp)
    assert result.package_structural_failed is False
    assert {o.name: o.status for o in result.outcomes} == {"a": "ok", "b": "ok"}


def test_package_structural_violation_fails_package(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "a.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n          constraints: {minimum: 0}\n")
    result = run_qa_package(dp)
    assert result.package_structural_failed is True
    assert result.outcomes[0].status == "fail"


def test_package_absent_data_is_blocked_not_fatal(tmp_path):
    from science_qa.runner import run_qa_package
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: missing.parquet\n    schema: {fields: [{name: id, type: integer}]}\n")
    result = run_qa_package(dp)
    assert result.package_structural_failed is False
    assert result.outcomes[0].status == "blocked" and result.outcomes[0].reason == "data file absent"


def test_package_non_tabular_is_not_applicable(tmp_path):
    from science_qa.runner import run_qa_package
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: v\n    path: v.qa_verdict.json\n")
    result = run_qa_package(dp)
    assert result.outcomes[0].status == "not-applicable" and result.outcomes[0].reason == "non-tabular"


def test_package_schemaless_tabular_is_skipped(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"x": [1]}).to_parquet(tmp_path / "a.parquet")
    dp = _yaml_pkg(tmp_path, "name: p\nresources:\n  - name: a\n    path: a.parquet\n")
    result = run_qa_package(dp)
    assert result.outcomes[0].status == "skipped" and result.outcomes[0].reason == "no schema"


def test_package_resource_selection_and_unknown(tmp_path):
    from science_qa.compile import CompileError
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"v": [1.0]}).to_parquet(tmp_path / "b.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n"
        "  - name: b\n    path: b.parquet\n    schema: {fields: [{name: v, type: number}]}\n")
    result = run_qa_package(dp, resources=["a"])
    assert [o.name for o in result.outcomes] == ["a"]
    with pytest.raises(CompileError, match="not found"):
        run_qa_package(dp, resources=["ghost"])


def test_package_report_dir_none_writes_nothing(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n")
    run_qa_package(dp)  # report_dir=None
    assert not (tmp_path / "qa_report.json").exists()
    assert not (tmp_path / "a").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py -v -k package`
Expected: FAIL — `ImportError: cannot import name 'run_qa_package'`.

- [ ] **Step 3: Append the dataclasses + `run_qa_package` (no writing)**

Append to `science/qa/src/science_qa/runner.py`:

```python
_TABULAR_SUFFIXES = {".parquet", ".csv", ".tsv"}


@dataclass(frozen=True)
class ResourceOutcome:
    name: str
    status: str            # "ok" | "fail" | "blocked" | "skipped" | "not-applicable"
    reason: str            # "" for ok/fail; else "data file absent" | "no schema" | "non-tabular"
    result: RunResult | None   # None for blocked/skipped/not-applicable


@dataclass(frozen=True)
class PackageRunResult:
    package: str
    outcomes: list[ResourceOutcome]
    package_structural_failed: bool


def _qa_one_resource(resource: dict, pkg_dir: Path, package: dict,
                     runknobs_path: Path | None) -> ResourceOutcome:
    name = resource.get("name", "?")
    path = resource.get("path")
    suffix = Path(path).suffix.lower() if path else ""
    if suffix not in _TABULAR_SUFFIXES:
        return ResourceOutcome(name, "not-applicable", "non-tabular", None)
    schema = resource.get("schema") or {}
    if not schema.get("fields"):
        return ResourceOutcome(name, "skipped", "no schema", None)
    table_path = pkg_dir / path
    if not table_path.exists():
        return ResourceOutcome(name, "blocked", "data file absent", None)
    config = schema_to_config(resource, pkg_dir, package)
    if runknobs_path is not None:
        config = merge_configs(config, QAConfig.from_file(runknobs_path, require_program=False))
    if not config.program:
        config.program = "tabular"
    result = _evaluate(config, table_path)
    return ResourceOutcome(name, "fail" if result.structural_failed else "ok", "", result)


def run_qa_package(datapackage_path: Path, report_dir: Path | None = None,
                   resources: list[str] | None = None,
                   runknobs_path: Path | None = None) -> PackageRunResult:
    """Run QA across a datapackage's tabular resources (package-level, §5.2).

    Each resource is classified (not-applicable / skipped / blocked) or evaluated; a
    malformed schema raises CompileError (fail early). The package is structurally failed
    iff any evaluated resource is. When `report_dir` is given, writes per-resource subdir
    reports + a package rollup (Task 5); otherwise writes nothing.
    """
    package, pkg_dir = load_package(Path(datapackage_path))
    all_res = package.get("resources", [])
    by_name = {r.get("name"): r for r in all_res}
    if resources is not None:
        missing = [n for n in resources if n not in by_name]
        if missing:
            raise CompileError(f"resource(s) not found in {datapackage_path}: {missing}")
        selected = [by_name[n] for n in resources]
    else:
        selected = all_res
    outcomes = [_qa_one_resource(r, pkg_dir, package, runknobs_path) for r in selected]
    package_structural_failed = any(o.status == "fail" for o in outcomes)
    result = PackageRunResult(package=package.get("name") or pkg_dir.name,
                              outcomes=outcomes,
                              package_structural_failed=package_structural_failed)
    if report_dir is not None:
        write_package_report(result, Path(report_dir))
    return result
```

(`write_package_report` is added in Task 5; with `report_dir=None`, the branch that calls
it is not reached, so these tests pass now. Do NOT call it elsewhere yet.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py -v`
Expected: PASS — all `-k package` tests plus the existing suite.

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/runner.py science/qa/tests/test_runner.py
git commit -m "feat(qa): run_qa_package package-level classification + aggregation"
```

---

## Task 5: package report writer (per-resource subdirs + rollup)

**Files:**
- Modify: `science/qa/src/science_qa/runner.py` (append `package_report_dict`, `write_package_report`, `_package_md`)
- Test: `science/qa/tests/test_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/qa/tests/test_runner.py`:

```python
def test_package_report_writes_subdirs_and_rollup(tmp_path):
    import json as _json
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "b.parquet")
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n"
        "  - name: b\n    path: b.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n          constraints: {minimum: 0}\n")
    out = tmp_path / "out"
    result = run_qa_package(tmp_path / "datapackage.yaml", report_dir=out)
    # per-resource subdir reports exist
    assert (out / "a" / "qa_report.json").exists()
    assert (out / "b" / "qa_report.json").exists()
    # package rollup
    rollup = _json.loads((out / "qa_report.json").read_text())
    assert rollup["package"] == "p" and rollup["package_structural_failed"] is True
    sections = {s["resource"]: s for s in rollup["resources"]}
    assert sections["b"]["status"] == "fail" and sections["b"]["flags"]
    assert sections["a"]["status"] == "ok" and sections["a"]["flags"] == []


def test_package_same_flag_id_two_resources_does_not_merge(tmp_path):
    # collision regression: identical flag_id in two resources -> separate subdir ledgers
    import json as _json
    from science_qa.runner import run_qa_package
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"p": [-2.0, 1.0]}).to_parquet(tmp_path / "b.parquet")
    field = ("        - name: p\n          type: number\n"
             "          constraints: {minimum: 0}\n")
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        f"  - name: a\n    path: a.parquet\n    schema:\n      fields:\n{field}"
        f"  - name: b\n    path: b.parquet\n    schema:\n      fields:\n{field}")
    out = tmp_path / "out"
    run_qa_package(tmp_path / "datapackage.yaml", report_dir=out)
    a_ids = {f["flag_id"] for f in _json.loads((out / "a" / "qa_report.json").read_text())["flags"]}
    b_ids = {f["flag_id"] for f in _json.loads((out / "b" / "qa_report.json").read_text())["flags"]}
    # same flag_id present in BOTH, each in its own resource-scoped report (not merged)
    assert "numeric-column/bounds/p/minimum" in a_ids
    assert "numeric-column/bounds/p/minimum" in b_ids
    # each resource gets its OWN disposition ledger (proves no shared/merged ledger)
    assert (out / "a" / "qa_dispositions.yaml").exists()
    assert (out / "b" / "qa_dispositions.yaml").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py -v -k "report_writes or two_resources"`
Expected: FAIL — `NameError: name 'write_package_report' is not defined` (referenced in
`run_qa_package` but not yet implemented).

- [ ] **Step 3: Append the report functions**

Append to `science/qa/src/science_qa/runner.py`:

```python
def package_report_dict(result: PackageRunResult) -> dict:
    """Serializable package rollup — the SAME schema persisted to qa_report.json and
    emitted by `science datasets qa --format json`. Each Flag via its existing to_dict()."""
    return {
        "package": result.package,
        "package_structural_failed": result.package_structural_failed,
        "resources": [
            {
                "resource": o.name,
                "status": o.status,
                "reason": o.reason,
                "flags": [f.to_dict() for f in (o.result.flags if o.result else [])],
                "coverage": o.result.coverage.to_dict() if o.result else None,
            }
            for o in result.outcomes
        ],
    }


def _package_md(result: PackageRunResult) -> str:
    lines = [f"# QA report — package `{result.package}`", "",
             f"- Package status: **{'FAIL' if result.package_structural_failed else 'ok'}**", ""]
    for o in result.outcomes:
        n_struct = sum(1 for f in o.result.flags if f.severity == SEVERITY_STRUCTURAL) if o.result else 0
        suffix = f" — {o.reason}" if o.reason else ""
        lines.append(f"- `{o.name}`: {o.status} ({n_struct} structural){suffix}")
    return "\n".join(lines) + "\n"


def write_package_report(result: PackageRunResult, report_dir: Path) -> None:
    """Persist per-resource reports into resource-scoped subdirs (reusing the exact
    single-resource writer + disposition ledger, so no cross-resource flag_id collision),
    plus one package rollup at report_dir/qa_report.{json,md} (§5.2)."""
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    for o in result.outcomes:
        if o.result is None:
            continue
        sub = report_dir / o.name
        write_reports(o.result.flags, report_dir=sub,
                      rows_checked=o.result.rows_checked, coverage=o.result.coverage)
        reconcile_dispositions(
            sub, [f.flag_id for f in o.result.flags if f.severity == SEVERITY_DISTRIBUTION])
    payload = package_report_dict(result)
    (report_dir / "qa_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (report_dir / "qa_report.md").write_text(_package_md(result), encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests/test_runner.py -v`
Expected: PASS — the two new report tests plus the whole suite.

- [ ] **Step 5: Run the full `science_qa` suite (no regressions)**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests -q`
Expected: green (existing baseline + all new tests from Tasks 1-5).

- [ ] **Step 6: Commit**

```bash
git add science/qa/src/science_qa/runner.py science/qa/tests/test_runner.py
git commit -m "feat(qa): resource-scoped package report + rollup (no flag_id collision)"
```

---

## Task 6: `science_tool` command wrapper `datasets/qa.py`

**Files:**
- Create: `science/src/science_tool/datasets/qa.py`
- Test: `science/tests/test_datasets_qa.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_datasets_qa.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from science_tool.datasets import qa as _qa


def _pkg(tmp_path: Path, *, minimum: int | None = None) -> Path:
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "a.parquet")
    constraints = f"          constraints: {{minimum: {minimum}}}\n" if minimum is not None else ""
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n" + constraints)
    return tmp_path


def test_resolve_directory_to_descriptor(tmp_path):
    _pkg(tmp_path)
    assert _qa._resolve_descriptor(tmp_path).name == "datapackage.yaml"


def test_resolve_descriptor_file_directly(tmp_path):
    _pkg(tmp_path)
    desc = tmp_path / "datapackage.yaml"
    assert _qa._resolve_descriptor(desc) == desc


def test_resolve_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="descriptor"):
        _qa._resolve_descriptor(tmp_path)


def test_exit_zero_when_clean(tmp_path):
    _pkg(tmp_path)  # no minimum -> no structural flag
    result, code = _qa.run_package_qa(tmp_path)
    assert code == 0 and result.package_structural_failed is False


def test_exit_one_on_structural(tmp_path):
    _pkg(tmp_path, minimum=0)  # -1.0 violates minimum 0
    result, code = _qa.run_package_qa(tmp_path)
    assert code == 1 and result.package_structural_failed is True


def test_no_strict_suppresses_exit_one(tmp_path):
    _pkg(tmp_path, minimum=0)
    _result, code = _qa.run_package_qa(tmp_path, no_strict=True)
    assert code == 0


def test_unknown_resource_raises_compile_error(tmp_path):
    from science_qa.compile import CompileError
    _pkg(tmp_path)
    with pytest.raises(CompileError):
        _qa.run_package_qa(tmp_path, resource="ghost")


def test_json_dict_matches_persisted_report(tmp_path):
    from science_qa.runner import package_report_dict
    _pkg(tmp_path, minimum=0)
    out = tmp_path / "out"
    result, _code = _qa.run_package_qa(tmp_path, report_dir=out)
    stdout_json = json.dumps(package_report_dict(result), indent=2, sort_keys=True) + "\n"
    assert stdout_json == (out / "qa_report.json").read_text()


def test_loader_drift_guard_iso_bound(tmp_path):
    # science_qa.load_package and science_tool.infer_schema.load_descriptor must parse an
    # unquoted ISO bound to the identical str (no PyYAML timestamp coercion drift).
    from science_qa.package import load_package
    from science_tool.datasets.infer_schema import load_descriptor
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n  - name: r\n    path: r.csv\n    schema:\n      fields:\n"
        "        - name: d\n          type: date\n          constraints: {maximum: 2020-01-01}\n")
    qa_map, _ = load_package(tmp_path / "datapackage.yaml")
    tool_map, _ = load_descriptor(tmp_path / "datapackage.yaml")
    qa_bound = qa_map["resources"][0]["schema"]["fields"][0]["constraints"]["maximum"]
    tool_bound = tool_map["resources"][0]["schema"]["fields"][0]["constraints"]["maximum"]
    assert qa_bound == tool_bound == "2020-01-01"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "$WT/science" && PYTHONPATH=src:qa/src $PY -m pytest tests/test_datasets_qa.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.datasets.qa'`.

- [ ] **Step 3: Create the wrapper**

Create `science/src/science_tool/datasets/qa.py`:

```python
# science/src/science_tool/datasets/qa.py
"""Thin `science datasets qa` wrapper: resolve a package path, run the science_qa engine
in-process, and apply the build-fatal exit-code policy. No QA logic lives here."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from science_tool.datasets.validate import DESCRIPTOR_NAMES

if TYPE_CHECKING:
    from science_qa.runner import PackageRunResult


def _resolve_descriptor(path: Path) -> Path:
    """A package directory or a descriptor file → the descriptor file. Fail early."""
    path = Path(path)
    if path.is_file() and path.name in DESCRIPTOR_NAMES:
        return path
    if path.is_dir():
        for name in DESCRIPTOR_NAMES:
            candidate = path / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"no datapackage descriptor at {path}")


def run_package_qa(path: Path, *, resource: str | None = None,
                   report_dir: Path | None = None, runknobs: Path | None = None,
                   no_strict: bool = False) -> tuple["PackageRunResult", int]:
    """Resolve, run, and compute the exit code. Raises (CompileError / RunnerError /
    ValueError / FileNotFoundError) on bad input — the CLI maps those to exit 2."""
    from science_qa.runner import run_qa_package

    descriptor = _resolve_descriptor(Path(path))
    resources = [resource] if resource else None
    result = run_qa_package(descriptor, report_dir=report_dir, resources=resources,
                            runknobs_path=runknobs)
    code = 1 if (result.package_structural_failed and not no_strict) else 0
    return result, code


def render_resource_line(outcome) -> str:
    n_struct = (sum(1 for f in outcome.result.flags if f.severity == "structural")
                if outcome.result else 0)
    n_dist = (sum(1 for f in outcome.result.flags if f.severity == "distribution")
              if outcome.result else 0)
    label = "FAIL" if outcome.status == "fail" else outcome.status
    detail = outcome.reason if outcome.reason else f"{n_struct} structural, {n_dist} distribution"
    return f"{outcome.name:<28} {label:<8} {detail}"


def render_package_summary(result: PackageRunResult) -> str:
    n_fail = sum(1 for o in result.outcomes if o.status == "fail")
    n_blocked = sum(1 for o in result.outcomes if o.status == "blocked")
    n_skipped = sum(1 for o in result.outcomes if o.status == "skipped")
    verdict = "FAIL" if result.package_structural_failed else "ok"
    return (f"--\npackage: {verdict}  "
            f"({n_fail} structural; {n_blocked} blocked, {n_skipped} skipped)")
```

Note: `render_resource_line` compares `f.severity` to the string literals `"structural"`/
`"distribution"` — these are the values of `SEVERITY_STRUCTURAL`/`SEVERITY_DISTRIBUTION`
in `science_qa.flags` (verify once: `grep SEVERITY_ science/qa/src/science_qa/flags.py`).
The wrapper intentionally imports `run_qa_package` inside `run_package_qa`, so merely
importing `science_tool.datasets.qa` does not require importing the QA engine; this keeps
the command's dependency on `science_qa` at call time as specified by the design.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science" && PYTHONPATH=src:qa/src $PY -m pytest tests/test_datasets_qa.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/qa.py science/tests/test_datasets_qa.py
git commit -m "feat(datasets): science_tool datasets-qa wrapper (resolve + exit policy)"
```

---

## Task 7: CLI wiring `science datasets qa`

**Files:**
- Modify: `science/src/science_tool/cli.py` (register the command after `datasets_validate`, ~line 3227)
- Test: `science/tests/test_datasets_qa_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_datasets_qa_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from science_tool.cli import main


def _pkg(tmp_path: Path, *, minimum: int | None = None) -> Path:
    d = tmp_path / "pkg"
    d.mkdir()
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(d / "a.parquet")
    constraints = f"          constraints: {{minimum: {minimum}}}\n" if minimum is not None else ""
    (d / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n" + constraints)
    return d


def test_cli_clean_exits_zero(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path))])
    assert res.exit_code == 0, res.output
    assert "package: ok" in res.output


def test_cli_structural_exits_one(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0))])
    assert res.exit_code == 1
    assert "package: FAIL" in res.output


def test_cli_no_strict_exits_zero(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0)), "--no-strict"])
    assert res.exit_code == 0


def test_cli_bad_path_exits_two(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(tmp_path / "nope")])
    assert res.exit_code == 2


def test_cli_json_format_is_rollup(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0)), "--format", "json"])
    payload = json.loads(res.output)
    assert payload["package_structural_failed"] is True
    assert payload["resources"][0]["resource"] == "a"


def test_cli_report_dir_persists(tmp_path):
    out = tmp_path / "out"
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0)),
                                    "--report-dir", str(out)])
    assert res.exit_code == 1
    assert (out / "qa_report.json").exists() and (out / "a" / "qa_report.json").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "$WT/science" && PYTHONPATH=src:qa/src $PY -m pytest tests/test_datasets_qa_cli.py -v`
Expected: FAIL — `No such command 'qa'` (exit_code 2 from click for an unknown subcommand,
but the assertions on output/`package: ok` fail).

- [ ] **Step 3: Register the command**

In `science/src/science_tool/cli.py`, immediately after the `datasets_validate` function
(it ends at line 3226 with `raise click.exceptions.Exit(1)`), insert:

```python
@datasets.command("qa")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--resource", "resource", default=None, help="Restrict QA to one resource (default: all tabular).")
@click.option("--report-dir", "report_dir", default=None, type=click.Path(path_type=Path),
              help="Persist qa_report.{json,md} (+ per-resource subdirs). Default: print only.")
@click.option("--config", "runknobs", default=None,
              type=click.Path(path_type=Path, exists=True, dir_okay=False),
              help="Optional operational run-knobs YAML overlaid on the schema-derived config.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option("--no-strict", is_flag=True, default=False, help="Suppress the build-fatal exit 1 (local inspection).")
def datasets_qa(path: Path, resource: str | None, report_dir: Path | None,
                runknobs: Path | None, output_format: str, no_strict: bool) -> None:
    """Run schema-driven QA over a datapackage's tabular resources (package-level).

    Exit codes: 0 ok · 1 structural flag fired (build-fatal; --no-strict forces 0) ·
    2 bad input (missing descriptor / unknown resource / unreadable data).
    """
    from science_qa.compile import CompileError
    from science_qa.runner import RunnerError, package_report_dict

    from science_tool.datasets import qa as _qa

    try:
        result, code = _qa.run_package_qa(
            path, resource=resource, report_dir=report_dir, runknobs=runknobs, no_strict=no_strict)
    except (CompileError, RunnerError, ValueError, FileNotFoundError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(2) from exc

    if output_format == "json":
        click.echo(json.dumps(package_report_dict(result), indent=2, sort_keys=True))
    else:
        for outcome in result.outcomes:
            if outcome.status == "not-applicable":
                continue
            click.echo(_qa.render_resource_line(outcome))
        click.echo(_qa.render_package_summary(result))

    if code:
        raise click.exceptions.Exit(code)
```

Confirm `json` is already imported at the top of `cli.py` (it is used elsewhere); if a
`grep -n "^import json" science/src/science_tool/cli.py` returns nothing, add `import json`
with the other stdlib imports.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$WT/science" && PYTHONPATH=src:qa/src $PY -m pytest tests/test_datasets_qa_cli.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_datasets_qa_cli.py
git commit -m "feat(datasets): wire science datasets qa command"
```

---

## Task 8: boundary guard + full-suite verification

**Files:**
- Test: `science/qa/tests/` (locate the existing one-way-dependency guard test)

- [ ] **Step 1: Confirm the non-importing boundary still holds**

The new `science_qa` code (`package.py`, the `runner.py` additions) must not import
`science_tool`. Run:

```bash
cd "$WT/science/qa"
grep -rnE --exclude-dir=__pycache__ "^[[:space:]]*(from[[:space:]]+science_tool([.][A-Za-z0-9_]+)*[[:space:]]+import|import[[:space:]]+science_tool([.]|[[:space:]]|$))" src/ && echo "LEAK" || echo "clean (no science_tool import)"
```
Expected: `clean (no science_tool import)`.

If an existing guard test asserts this (search: `grep -rln "science_tool" tests/`), run it:
```bash
PYTHONPATH=src $PY -m pytest tests -q -k "boundary or import or dependency"
```
Expected: PASS (or "no tests ran" if the guard is the grep above — then the grep is the gate).

- [ ] **Step 2: Run the whole `science_qa` suite**

Run: `cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests -q`
Expected: green — baseline + all Task 1-5 additions.

- [ ] **Step 3: Run the `science datasets` slice of the `science_tool` suite**

Run:
```bash
cd "$WT/science"
PYTHONPATH=src:qa/src $PY -m pytest tests/test_datasets_qa.py tests/test_datasets_qa_cli.py \
    tests/test_datasets_validate.py tests/test_datasets_validate_cli.py tests/test_infer_schema.py -q
```
Expected: green — the new qa tests plus the sibling datasets tests (no regressions from the
shared `validate`/`infer_schema` surfaces).

- [ ] **Step 4: Smoke-test against a real campaign package**

Run (read-only; a YAML package from the adoption campaign):
```bash
cd "$WT/science"
PYTHONPATH=src:qa/src $PY -m science_tool datasets qa ~/d/cancer/therapeutics/data/raw/drugcomb || echo "exit=$?"
```
Expected: a per-resource table + `package:` summary line. Exit 0 or 1 (a real verdict), NOT
a traceback. (If the package's data files are absent locally, resources show `blocked` and
the package is `ok` — also acceptable.)

- [ ] **Step 5: Commit (if the guard test needed a new assertion)**

If Step 1 added or extended a guard test, commit it:
```bash
git add science/qa/tests/<guard_test>.py
git commit -m "test(qa): assert package.py keeps the one-way boundary"
```
Otherwise no commit — the slice is already committed per task.

---

## Final verification (after all tasks)

- [ ] Whole `science_qa` suite green:
```bash
cd "$WT/science/qa" && PYTHONPATH=src $PY -m pytest tests -q
```

- [ ] New `science_tool` datasets-qa tests green:
```bash
cd "$WT/science" && PYTHONPATH=src:qa/src $PY -m pytest tests/test_datasets_qa.py tests/test_datasets_qa_cli.py -q
```

- [ ] One-way dependency intact:
```bash
cd "$WT/science/qa" && grep -rnE --exclude-dir=__pycache__ "^[[:space:]]*(from[[:space:]]+science_tool([.][A-Za-z0-9_]+)*[[:space:]]+import|import[[:space:]]+science_tool([.]|[[:space:]]|$))" src/ && echo "LEAK" || echo "clean"
```
Expected: `clean`.

- [ ] Branch check before any merge: `git -C "$WT" branch --show-current` → `feat/datasets-qa-reachability`.

---

## Self-review (filled in by plan author)

**1. Spec coverage** (design § → task):
- §3.1 package granularity + `--resource` narrowing → Task 4 (`run_qa_package` + `resources=`), Task 6/7 (`--resource`). ✓
- §3.2 transient report only → Task 4 (`report_dir=None` writes nothing), Task 5 (writes only when given). ✓
- §3.3 build-fatal exit 0/1/2 + `--no-strict` → Task 6 (`run_package_qa` code), Task 7 (CLI Exit + exit-2 catch). ✓
- §4 command surface + text/json output → Task 6 (renderers), Task 7 (options, `--format`). ✓
- §4.1 hide `not-applicable` in text → Task 7 (`continue` on not-applicable), Task 4 (status). ✓
- §5.0 neutral timestamp-safe loader → Task 2; reused in Task 3 + Task 4. Drift guard → Task 6 test. ✓
- §5.1 `_evaluate` split + `RunResult.rows_checked` → Task 1. ✓
- §5.2 classification (not-applicable/skipped/blocked/ok/fail), CompileError on unknown/ malformed, resource-scoped subdir reports, no flag_id collision → Tasks 4 & 5 (+ collision regression test). ✓
- §6 thin command, explicit exit-2 catch `(CompileError, RunnerError, ValueError, FileNotFoundError)` → Task 7. ✓
- §7 errors (bad path, unknown resource, corrupt data) → Task 6 tests + Task 7 catch. ✓
- §8 scope boundaries (no verdict materialization, not wired into validate, tabular only, no new checks, non-importing) → not built (correct); boundary asserted Task 8. ✓
- §9 testing (YAML loader, not-applicable, collision, json==file) → Tasks 2,4,5,6. ✓
- §5.3 standalone CLI package mode → explicitly deferred (plan preamble). ✓

**2. Placeholder scan:** none — every code step shows complete code. The Task 4 forward
reference to `write_package_report` is an explicit, named two-step build (called only under
`report_dir is not None`, which those tests don't trigger; implemented in Task 5), not a TODO.

**3. Type consistency:** `RunResult(flags, structural_failed, coverage, rows_checked)` —
field added Task 1, consumed Tasks 1/5. `ResourceOutcome(name, status, reason, result)` and
`PackageRunResult(package, outcomes, package_structural_failed)` — defined Task 4, consumed
Tasks 5/6/7. `run_qa_package(datapackage_path, report_dir=None, resources=None, runknobs_path=None)`
— stable Tasks 4/5/6. `load_package(path) -> (dict, Path)` — Task 2, used Tasks 3/4/6.
`package_report_dict(result)` / `write_package_report(result, report_dir)` — Task 5, used
Tasks 5/6/7. `run_package_qa(path, *, resource, report_dir, runknobs, no_strict) -> (PackageRunResult, int)`
— Task 6, used Task 7. Exit-2 catch list identical in Task 6 docstring and Task 7 code.
Status vocabulary `ok|fail|blocked|skipped|not-applicable` identical across Tasks 4/6/7.
