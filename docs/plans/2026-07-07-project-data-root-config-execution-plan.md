# Project Data-Root Configuration Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable per-project bulk data roots while preserving logical `data/...` paths for manifests, docs, and repo hygiene tooling.

**Architecture:** Add `science_tool.data_root` as the single owner of project data-root resolution and project-root discovery. Keep `DEFAULT_DATA_DIRS` as logical names, map them to physical directories only at CLI and package-inventory boundaries, and keep `science data audit` repo-relative. Reproducibility manifests record logical payload paths so local storage location does not change identity.

**Tech Stack:** Python 3.12, Click, Pydantic v2, pytest, existing `science/` package layout, markdown docs, and `scripts/generate_codex_skills.py`.

## Global Constraints

- Run package commands from `science/`, not the repository root.
- Use `uv run --frozen pytest` for tests from `science/`.
- Use `uv run ruff check` and `uv run pyright` from `science/` for final validation.
- Follow composition over inheritance, explicit over defensive, and fail early instead of silent fallbacks.
- Do not create legacy or compatibility layers.
- Do not add a `Unified` prefix to component names.
- Do not include AI attribution trailers in commits.
- Keep docs under existing `docs/` conventions; do not create `docs/superpowers/`.
- Use `~/d/` in docs and code examples rather than machine-specific absolute checkout paths.

---

## File Structure

- Create `science/src/science_tool/data_root.py`: `DataRootConfigError`, `discover_project_root()`, `resolve_data_root()`, `logical_data_dir_to_physical()`.
- Modify `science/src/science_tool/project_config.py`: `ProjectDataConfig`, `ProjectConfig.data`.
- Modify `science/src/science_tool/registry/config.py`: `DataSettings`, `GlobalConfig.data`.
- Modify `science/src/science_tool/cli.py`: lazy data-root defaults for `datasets download` and `datasets validate`.
- Modify `science/src/science_tool/data_audit.py` and `science/src/science_tool/data_cli.py`: audit notes, external-root info, tracked-root warning.
- Modify `science/src/science_tool/project_package/payload.py`, `serialize.py`, `verify.py`: physical walk with logical payload paths.
- Modify `science/src/science_tool/commons/dataset_lifecycle.py`: docstring and guard tests only.
- Modify docs and skills: `docs/user-guide/entities.md`, `skills/data/frictionless.md`, `skills/pipelines/snakemake.md`, `commands/create-project.md`.

## Task 1: Config Models And Resolver

**Files:**
- Create: `science/src/science_tool/data_root.py`
- Modify: `science/src/science_tool/project_config.py`
- Modify: `science/src/science_tool/registry/config.py`
- Test: `science/tests/test_data_root.py`

**Interfaces:**
- Produces: `class DataRootConfigError(ValueError)`
- Produces: `discover_project_root(start: Path | None = None) -> Path`
- Produces: `resolve_data_root(project_root: Path, config: ProjectConfig | None = None) -> Path`
- Produces: `logical_data_dir_to_physical(data_root: Path, logical_dir: Path) -> Path`

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_data_root.py` with these tests:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from science_tool.data_root import (
    DataRootConfigError,
    discover_project_root,
    logical_data_dir_to_physical,
    resolve_data_root,
)
from science_tool.project_config import ProjectConfig, load_project_config


def _write_project(root: Path, extra: dict | None = None) -> None:
    payload = {"name": "Demo", "id": "demo"}
    if extra:
        payload.update(extra)
    (root / "science.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_default_root_is_project_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    assert resolve_data_root(tmp_path) == tmp_path.resolve() / "data"


def test_env_root_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path, {"data": {"root": str(tmp_path / "project-data")}})
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("SCIENCE_DATA_ROOT", str(tmp_path / "env-data"))
    assert resolve_data_root(tmp_path) == tmp_path / "env-data"


def test_relative_env_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    monkeypatch.setenv("SCIENCE_DATA_ROOT", "relative-data")
    with pytest.raises(DataRootConfigError, match="SCIENCE_DATA_ROOT.*absolute"):
        resolve_data_root(tmp_path)


def test_project_relative_root_is_project_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_project(project, {"data": {"root": "bulk"}})
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    assert resolve_data_root(project) == project.resolve() / "bulk"


def test_global_root_is_parent_plus_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path, {"id": "project-id"})
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(
        yaml.safe_dump({"data": {"root": str(tmp_path / "bulk-parent")}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    assert resolve_data_root(tmp_path) == tmp_path / "bulk-parent" / "project-id"


def test_relative_global_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(yaml.safe_dump({"data": {"root": "relative"}}), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("SCIENCE_DATA_ROOT", raising=False)
    with pytest.raises(DataRootConfigError, match="global data.root.*absolute"):
        resolve_data_root(tmp_path)


def test_project_data_config_forbids_typos_but_top_level_extra_survives() -> None:
    config = ProjectConfig.model_validate({"name": "Demo", "unknown": "kept"})
    assert config.model_extra == {"unknown": "kept"}
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"name": "Demo", "data": {"rot": "/tmp/x"}})


def test_load_project_config_parses_data_root(tmp_path: Path) -> None:
    _write_project(tmp_path, {"data": {"root": "bulk"}})
    config = load_project_config(tmp_path)
    assert config.data is not None
    assert config.data.root == Path("bulk")


def test_logical_data_dir_to_physical_uses_leaf_name(tmp_path: Path) -> None:
    assert logical_data_dir_to_physical(tmp_path / "bulk", Path("data/processed")) == (
        tmp_path / "bulk" / "processed"
    )


def test_discover_project_root_env_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_project(project)
    monkeypatch.setenv("SCIENCE_PROJECT_ROOT", str(project))
    assert discover_project_root() == project.resolve()


def test_discover_project_root_walks_up(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "a" / "b"
    nested.mkdir(parents=True)
    _write_project(project)
    assert discover_project_root(nested) == project.resolve()


def test_discover_project_root_falls_back_without_science_yaml(tmp_path: Path) -> None:
    assert discover_project_root(tmp_path) == tmp_path.resolve()
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd science && uv run --frozen pytest science/tests/test_data_root.py -q`

Expected: FAIL because `science_tool.data_root` does not exist.

- [ ] **Step 3: Add config model code**

In `science/src/science_tool/project_config.py`, add:

```python
class ProjectDataConfig(BaseModel):
    """Per-project bulk-data root configuration."""

    model_config = ConfigDict(extra="forbid")

    root: Path | None = None
```

Add this field to `ProjectConfig`:

```python
    data: ProjectDataConfig | None = None
```

In `science/src/science_tool/registry/config.py`, change the pydantic import:

```python
from pydantic import BaseModel, ConfigDict, Field
```

Add:

```python
class DataSettings(BaseModel):
    """Global shared parent for per-project bulk data roots."""

    model_config = ConfigDict(extra="forbid")

    root: Path | None = None
```

Add this field to `GlobalConfig`:

```python
    data: DataSettings = Field(default_factory=DataSettings)
```

- [ ] **Step 4: Add resolver code**

Create `science/src/science_tool/data_root.py`:

```python
"""Project bulk-data root resolution."""

from __future__ import annotations

import os
from pathlib import Path

from science_tool.project_config import ProjectConfig, load_project_config
from science_tool.registry.config import load_global_config


class DataRootConfigError(ValueError):
    """Raised when a data-root configuration value is invalid."""


def discover_project_root(start: Path | None = None) -> Path:
    """Resolve a project root from env, nearest science.yaml ancestor, or cwd."""
    if start is None:
        if env := os.environ.get("SCIENCE_PROJECT_ROOT"):
            return Path(env).expanduser().resolve()
        start = Path.cwd()
    candidate = start.expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for root in (candidate, *candidate.parents):
        if (root / "science.yaml").is_file():
            return root
    return candidate


def logical_data_dir_to_physical(data_root: Path, logical_dir: Path) -> Path:
    """Map logical data/raw to physical <data_root>/raw."""
    return data_root / logical_dir.name


def resolve_data_root(project_root: Path, config: ProjectConfig | None = None) -> Path:
    """Resolve a project's physical bulk-data root."""
    project_root = project_root.expanduser().resolve()
    if env := os.environ.get("SCIENCE_DATA_ROOT"):
        return _require_absolute(Path(env).expanduser(), "SCIENCE_DATA_ROOT")

    project_config = config or _load_project_config_if_present(project_root)
    if project_config is not None and project_config.data is not None and project_config.data.root is not None:
        return _resolve_project_path(project_root, project_config.data.root)

    global_config = load_global_config()
    if global_config.data.root is not None:
        parent = _require_absolute(Path(global_config.data.root).expanduser(), "global data.root")
        project_id = project_config.id if project_config is not None and project_config.id else project_root.name
        return parent / project_id

    return project_root / "data"


def _load_project_config_if_present(project_root: Path) -> ProjectConfig | None:
    if not (project_root / "science.yaml").is_file():
        return None
    return load_project_config(project_root)


def _resolve_project_path(project_root: Path, value: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def _require_absolute(path: Path, source: str) -> Path:
    if not path.is_absolute():
        raise DataRootConfigError(f"{source} must be absolute, got {path}")
    return path
```

- [ ] **Step 5: Run tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_data_root.py -q`

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/data_root.py science/src/science_tool/project_config.py science/src/science_tool/registry/config.py science/tests/test_data_root.py
git commit -m "feat: add project data-root resolver"
```

## Task 2: Dataset CLI Lazy Defaults

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_datasets_data_root_cli.py`

**Interfaces:**
- Consumes: `discover_project_root(start: Path | None = None) -> Path`
- Consumes: `resolve_data_root(project_root: Path, config: ProjectConfig | None = None) -> Path`

- [ ] **Step 1: Write failing CLI tests**

Create `science/tests/test_datasets_data_root_cli.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main


class _File:
    filename = "x.csv"
    format = "csv"
    size_bytes = 1
    checksum = None


class _Adapter:
    def __init__(self) -> None:
        self.destinations: list[Path] = []

    def files(self, dataset_id: str) -> list[_File]:
        assert dataset_id == "abc"
        return [_File()]

    def download(self, file_info: _File, dest_dir: Path) -> Path:
        self.destinations.append(dest_dir)
        return dest_dir / file_info.filename


def _write_project(root: Path, extra: dict | None = None) -> None:
    payload = {"name": "Demo", "id": "demo"}
    if extra:
        payload.update(extra)
    (root / "science.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_datapackage(root: Path) -> None:
    raw = root / "raw"
    raw.mkdir(parents=True)
    (raw / "x.csv").write_text("a\n1\n", encoding="utf-8")
    (raw / "datapackage.json").write_text(
        json.dumps({"name": "p", "resources": [{"name": "x", "path": "x.csv", "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}),
        encoding="utf-8",
    )


def test_download_default_uses_project_data_raw(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(main, ["datasets", "download", "--project-root", str(tmp_path), "zenodo:abc"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [tmp_path.resolve() / "data" / "raw"]


def test_download_default_uses_configured_project_root(monkeypatch, tmp_path: Path) -> None:
    bulk = tmp_path / "bulk"
    _write_project(tmp_path, {"data": {"root": str(bulk)}})
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(main, ["datasets", "download", "--project-root", str(tmp_path), "zenodo:abc"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [bulk / "raw"]


def test_download_from_subdirectory_discovers_project_root(monkeypatch, tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    _write_project(tmp_path)
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    monkeypatch.chdir(nested)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(main, ["datasets", "download", "zenodo:abc"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [tmp_path.resolve() / "data" / "raw"]


def test_download_explicit_dest_is_used_verbatim(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path, {"data": {"root": str(tmp_path / "bulk")}})
    explicit = tmp_path / "chosen"
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    result = CliRunner().invoke(main, ["datasets", "download", "--project-root", str(tmp_path), "--dest", str(explicit), "zenodo:abc"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [explicit]


def test_validate_default_uses_configured_data_root(monkeypatch, tmp_path: Path) -> None:
    bulk = tmp_path / "bulk"
    _write_project(tmp_path, {"data": {"root": str(bulk)}})
    _write_datapackage(bulk)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(main, ["datasets", "validate", "--project-root", str(tmp_path)], catch_exceptions=False)
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd science && uv run --frozen pytest science/tests/test_datasets_data_root_cli.py -q`

Expected: FAIL because `--project-root` is not accepted.

- [ ] **Step 3: Modify CLI**

In `science/src/science_tool/cli.py`, import:

```python
from science_tool.data_root import discover_project_root, resolve_data_root
```

Change `datasets_download` options and signature to:

```python
@datasets.command("download")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--file", "file_pattern", default=None, help="Download only files matching this pattern")
@click.option("--project-root", default=None, type=click.Path(path_type=Path), help="Project root for resolving the configured data root.")
@click.option("--dest", "dest_dir", default=None, show_default="resolved data root / raw", type=click.Path(path_type=Path))
def datasets_download(source_id: str, file_pattern: str | None, project_root: Path | None, dest_dir: Path | None) -> None:
```

Before the download loop, add:

```python
    if dest_dir is None:
        dest_dir = resolve_data_root(discover_project_root(project_root)) / "raw"
```

Change `datasets_validate` options and signature to:

```python
@datasets.command("validate")
@click.option("--project-root", default=None, type=click.Path(path_type=Path), help="Project root for resolving the configured data root.")
@click.option("--path", "data_path", default=None, show_default="resolved data root", type=click.Path(path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_validate(project_root: Path | None, data_path: Path | None, output_format: str) -> None:
    """Validate Frictionless Data Packages in raw/ and processed/ directories."""
    if data_path is None:
        data_path = resolve_data_root(discover_project_root(project_root))
    results = validate_path(data_path)
```

- [ ] **Step 4: Run tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_datasets_data_root_cli.py science/tests/test_datasets_validate_cli.py -q`

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/cli.py science/tests/test_datasets_data_root_cli.py
git commit -m "feat: resolve dataset CLI data-root defaults"
```

## Task 3: Data Audit Notes And Repo Boundary

**Files:**
- Modify: `science/src/science_tool/data_audit.py`
- Modify: `science/src/science_tool/data_cli.py`
- Test: `science/tests/test_data_audit.py`
- Test: `science/tests/test_data_audit_cli.py`

**Interfaces:**
- Produces: `AuditNote(severity: Literal["info", "warning"], code: str, message: str)`
- Produces: `audit_project_notes(project_root: Path) -> list[AuditNote]`
- Extends: `render_json(..., notes: list[AuditNote] | None = None) -> str`

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_data_audit.py`:

```python
def test_audit_notes_report_external_data_root(monkeypatch, tmp_path: Path) -> None:
    from science_tool.data_audit import audit_project, audit_project_notes

    external = tmp_path / "external-data"
    (tmp_path / "science.yaml").write_text(f"name: Demo\nid: demo\ndata:\n  root: {external}\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert audit_project(tmp_path) == []
    notes = audit_project_notes(tmp_path)
    assert [note.code for note in notes] == ["external-data-root"]
    assert str(external) in notes[0].message


def test_render_json_includes_notes_only_when_present() -> None:
    from science_tool.data_audit import AuditNote, render_json
    import json

    assert "notes" not in json.loads(render_json([]))
    payload = json.loads(render_json([], notes=[AuditNote("info", "external-data-root", "external data root: /tmp/x")]))
    assert payload["notes"] == [{"severity": "info", "code": "external-data-root", "message": "external data root: /tmp/x"}]
```

Append to `science/tests/test_data_audit_cli.py`:

```python
def test_audit_json_reports_external_data_root_note(monkeypatch, tmp_path: Path):
    _init_repo(tmp_path)
    external = tmp_path / "external-data"
    _write(tmp_path, "science.yaml", f"name: Demo\nid: demo\ndata:\n  root: {external}\n".encode())
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    res = _run(tmp_path, "--json")
    payload = json.loads(res.output)
    assert res.exit_code == 0
    assert payload["violations"] == []
    assert payload["notes"][0]["code"] == "external-data-root"
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd science && uv run --frozen pytest science/tests/test_data_audit.py::test_audit_notes_report_external_data_root science/tests/test_data_audit.py::test_render_json_includes_notes_only_when_present science/tests/test_data_audit_cli.py::test_audit_json_reports_external_data_root_note -q`

Expected: FAIL because `AuditNote` and `audit_project_notes` do not exist.

- [ ] **Step 3: Add note code**

In `science/src/science_tool/data_audit.py`, import:

```python
from typing import Literal

from science_tool.data_root import resolve_data_root
```

Add after `Violation`:

```python
@dataclass(frozen=True)
class AuditNote:
    severity: Literal["info", "warning"]
    code: str
    message: str
```

Add before `_DATAPACKAGE_NAMES`:

```python
def audit_project_notes(project_root: Path) -> list[AuditNote]:
    project_root = project_root.resolve()
    data_root = resolve_data_root(project_root).resolve(strict=False)
    notes: list[AuditNote] = []
    if not _is_relative_to(data_root, project_root):
        notes.append(
            AuditNote(
                "info",
                "external-data-root",
                f"external data root: {data_root} (not walked by repo-boundary audit)",
            )
        )
    return notes


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
```

Update `render_json` signature:

```python
def render_json(
    violations: list[Violation],
    outcomes: "list | None" = None,
    notes: list[AuditNote] | None = None,
) -> str:
```

At the end of `render_json`, replace the direct return with:

```python
    payload = {"version": 1, "violations": rows}
    if notes:
        payload["notes"] = [
            {"severity": note.severity, "code": note.code, "message": note.message}
            for note in notes
        ]
    return json.dumps(payload, indent=2) + "\n"
```

- [ ] **Step 4: Render notes from CLI**

In `science/src/science_tool/data_cli.py`, import:

```python
from science_tool.data_audit import audit_project, audit_project_notes, render_json
```

After `violations = audit_project(project_path, policy)`, add:

```python
    notes = audit_project_notes(project_path)
```

Pass notes to JSON rendering:

```python
click.echo(render_json(violations, outcomes, notes), nl=False)
click.echo(render_json(violations, notes=notes), nl=False)
```

In text mode before the clean message, add:

```python
            for note in notes:
                click.echo(f"  [{note.severity}:{note.code}] {note.message}")
```

- [ ] **Step 5: Run tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_data_audit.py science/tests/test_data_audit_cli.py -q`

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/data_audit.py science/src/science_tool/data_cli.py science/tests/test_data_audit.py science/tests/test_data_audit_cli.py
git commit -m "feat: report external data roots in data audit"
```

## Task 4: Payload Inventory Physical Walk With Logical Paths

**Files:**
- Modify: `science/src/science_tool/project_package/payload.py`
- Modify: `science/src/science_tool/project_package/serialize.py`
- Modify: `science/src/science_tool/project_package/verify.py`
- Test: `science/tests/test_project_package_payload.py`
- Test: `science/tests/test_project_serialize.py`

**Interfaces:**
- Extends: `payload_inventory(project_root, data_dirs, tracked_set, data_root=None) -> list[dict]`
- Extends: `_payload_inventory(project_root, data_dirs, tracked_set, data_root=None) -> list[dict]`

- [ ] **Step 1: Add failing payload tests**

Append to `science/tests/test_project_package_payload.py`:

```python
def test_payload_inventory_records_logical_path_for_out_of_tree_root(tmp_path: Path):
    import hashlib
    project = tmp_path / "project"
    project.mkdir()
    data_root = tmp_path / "bulk"
    _write(data_root, "processed/exp/a.parquet", b"payload")
    inv = payload_inventory(project, DEFAULT_DATA_DIRS, tracked_set=set(), data_root=data_root)
    assert inv == [{"path": "data/processed/exp/a.parquet", "sha256": hashlib.sha256(b"payload").hexdigest(), "bytes": 7, "git_tracked": False}]


def test_payload_inventory_logical_paths_match_in_repo_and_out_of_tree(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _write(project, "data/processed/exp/a.parquet", b"payload")
    in_repo = payload_inventory(project, DEFAULT_DATA_DIRS, tracked_set=set())
    out_root = tmp_path / "bulk"
    _write(out_root, "processed/exp/a.parquet", b"payload")
    out_of_tree = payload_inventory(project, DEFAULT_DATA_DIRS, tracked_set=set(), data_root=out_root)
    assert out_of_tree == in_repo
```

Append to `science/tests/test_project_serialize.py`:

```python
def test_serialize_inventories_out_of_tree_payloads_with_logical_paths(tmp_path: Path, monkeypatch):
    import tarfile
    from science_tool.project_package.serialize import serialize_project
    from science_tool.project_package.verify import verify_project

    project = tmp_path / "project"
    project.mkdir()
    bulk = tmp_path / "bulk"
    _write(project, "science.yaml", f"id: demo\nname: Demo\ndata:\n  root: {bulk}\n".encode())
    _write(project, "entities/questions/q1.md", b"# q\n")
    _init_repo(project)
    _commit_all(project)
    _write(bulk, "processed/big.parquet", b"\x09" * 16)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    out = tmp_path / "bundle.tar.gz"
    result = serialize_project(project, out, force=False)
    assert result.payload_count == 1
    with tarfile.open(out, "r:gz") as tar:
        manifest = json.loads(tar.extractfile("demo/manifest.json").read())
    assert manifest["payloads"][0]["path"] == "data/processed/big.parquet"
    assert manifest["payloads"][0]["git_tracked"] is False
    verified = verify_project(out, against=project)
    assert verified.ok is True
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd science && uv run --frozen pytest science/tests/test_project_package_payload.py::test_payload_inventory_records_logical_path_for_out_of_tree_root science/tests/test_project_serialize.py::test_serialize_inventories_out_of_tree_payloads_with_logical_paths -q`

Expected: FAIL because `payload_inventory` does not accept `data_root`.

- [ ] **Step 3: Replace payload inventory implementation**

In `science/src/science_tool/project_package/payload.py`, replace `payload_inventory` and `_walk_payload_dir` with:

```python
def payload_inventory(
    project_root: Path,
    data_dirs: tuple[Path, ...],
    tracked_set: set[str],
    data_root: Path | None = None,
) -> list[dict]:
    data_root = data_root or project_root / "data"
    payloads: list[dict] = []
    seen_dirs: set[str] = set()
    for logical_dir in data_dirs:
        base = data_root / logical_dir.name
        if not base.exists():
            continue
        _walk_payload_dir(logical_dir, base, base, tracked_set, seen_dirs, payloads)
    payloads.sort(key=lambda p: p["path"])
    return payloads


def _walk_payload_dir(
    logical_dir: Path,
    physical_base: Path,
    directory: Path,
    tracked_set: set[str],
    seen_dirs: set[str],
    payloads: list[dict],
) -> None:
    real = os.path.realpath(directory)
    if real in seen_dirs:
        raise PayloadError(f"symlink cycle under data dir: {directory}")
    seen_dirs.add(real)
    for entry in sorted(os.scandir(directory), key=lambda e: e.name):
        path = Path(entry.path)
        if entry.is_dir(follow_symlinks=True):
            _walk_payload_dir(logical_dir, physical_base, path, tracked_set, seen_dirs, payloads)
        elif entry.is_file(follow_symlinks=True):
            data = path.read_bytes()
            logical_path = (logical_dir / path.relative_to(physical_base)).as_posix()
            payloads.append({"path": logical_path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "git_tracked": logical_path in tracked_set})
        else:
            raise PayloadError(f"non-regular file under data dir: {entry.path}")
```

- [ ] **Step 4: Thread data root through serialize and verify**

In `science/src/science_tool/project_package/serialize.py`, import:

```python
from science_tool.data_root import resolve_data_root
```

Extend `_payload_inventory` with `data_root: Path | None = None`, call:

```python
return payload_inventory(project_root, data_dirs, tracked_set, data_root=data_root)
```

In `serialize_project`, replace the payload call with:

```python
payloads = _payload_inventory(project_root, DEFAULT_DATA_DIRS, set(tracked), data_root=resolve_data_root(project_root))
```

In `science/src/science_tool/project_package/verify.py`, import:

```python
from science_tool.data_root import resolve_data_root
```

Replace the payload comparison call with:

```python
actual_payloads = payload_inventory(root, DEFAULT_DATA_DIRS, tracked, data_root=resolve_data_root(root))
```

- [ ] **Step 5: Run tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_project_package_payload.py science/tests/test_project_serialize.py science/tests/test_project_verify.py -q`

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/project_package/payload.py science/src/science_tool/project_package/serialize.py science/src/science_tool/project_package/verify.py science/tests/test_project_package_payload.py science/tests/test_project_serialize.py
git commit -m "feat: inventory payloads through logical data paths"
```

## Task 5: Tracked Data-Root Guardrail

**Files:**
- Modify: `science/src/science_tool/data_audit.py`
- Modify: `commands/create-project.md`
- Test: `science/tests/test_data_audit.py`
- Test: `science/tests/test_command_docs.py`

**Interfaces:**
- Extends: `audit_project_notes(project_root)` with warning code `tracked-data-root`.

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_data_audit.py`:

```python
def test_audit_notes_warn_on_tracked_file_under_data_root(tmp_path: Path) -> None:
    import subprocess
    from science_tool.data_audit import audit_project_notes

    (tmp_path / "science.yaml").write_text("name: Demo\nid: demo\n", encoding="utf-8")
    payload = tmp_path / "data" / "processed" / "tracked.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"x")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "science.yaml", "data/processed/tracked.bin"], cwd=tmp_path, check=True)
    notes = audit_project_notes(tmp_path)
    warnings = [note for note in notes if note.code == "tracked-data-root"]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert "data/processed/tracked.bin" in warnings[0].message
```

Append to `science/tests/test_command_docs.py`:

```python
def test_create_project_docs_keep_data_payload_dirs_gitignored() -> None:
    text = _read("commands/create-project.md")
    assert "data/raw/*" in text
    assert "!data/raw/.gitkeep" in text
    assert "data/processed/*" in text
    assert "!data/processed/.gitkeep" in text
    assert "data/external/*" in text
    assert "!data/external/.gitkeep" in text
    assert "provenance/" in text
    assert "data/provenance/" in text
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd science && uv run --frozen pytest science/tests/test_data_audit.py::test_audit_notes_warn_on_tracked_file_under_data_root science/tests/test_command_docs.py::test_create_project_docs_keep_data_payload_dirs_gitignored -q`

Expected: FAIL because the warning and docs are absent.

- [ ] **Step 3: Add warning code**

In `audit_project_notes`, after the external-root note block, add:

```python
    tracked_under_root = _tracked_paths_under_data_root(project_root, data_root)
    if tracked_under_root:
        shown = ", ".join(tracked_under_root[:5])
        suffix = "" if len(tracked_under_root) <= 5 else f", +{len(tracked_under_root) - 5} more"
        notes.append(AuditNote("warning", "tracked-data-root", f"git-tracked file(s) under data root: {shown}{suffix}"))
```

Add helper:

```python
def _tracked_paths_under_data_root(project_root: Path, data_root: Path) -> list[str]:
    if not _is_relative_to(data_root, project_root):
        return []
    data_rel = data_root.relative_to(project_root)
    return sorted(rel for rel in git_tracked_set(project_root) if Path(rel) == data_rel or data_rel in Path(rel).parents)
```

- [ ] **Step 4: Update create-project docs**

In `commands/create-project.md`, ensure this `.gitignore` block exists:

```gitignore
data/raw/*
!data/raw/.gitkeep
data/processed/*
!data/processed/.gitkeep
data/external/*
!data/external/.gitkeep
```

Add this paragraph:

```markdown
Keep version-controlled provenance outside the configured data root. Prefer `provenance/` or `research/packages/` for lightweight manifests, QA reports, and small summary frames. Do not use `data/provenance/` when the project uses the default `./data` data root, because that puts committed provenance inside the non-version-controlled root.
```

- [ ] **Step 5: Run tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_data_audit.py science/tests/test_data_audit_cli.py science/tests/test_command_docs.py::test_create_project_docs_keep_data_payload_dirs_gitignored -q`

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/data_audit.py science/tests/test_data_audit.py commands/create-project.md science/tests/test_command_docs.py
git commit -m "feat: warn on tracked files under data root"
```

## Task 6: Commons Recipe Lint Guard

**Files:**
- Modify: `science/src/science_tool/commons/dataset_lifecycle.py`
- Test: `science/tests/test_commons_dataset_lifecycle.py`

**Interfaces:**
- Keeps `_validate_snakefile_paths(findings, snakefile_path)` signature unchanged.

- [ ] **Step 1: Add guard tests**

Append to `science/tests/test_commons_dataset_lifecycle.py`:

```python
def test_validate_snakefile_paths_allows_commons_data_root_output(tmp_path: Path) -> None:
    from science_tool.commons.dataset_lifecycle import DatasetPackageFinding, _validate_snakefile_paths

    snakefile = tmp_path / "Snakefile"
    snakefile.write_text('output = "/data/science-commons/demo/built.csv"\n', encoding="utf-8")
    findings: list[DatasetPackageFinding] = []
    _validate_snakefile_paths(findings, snakefile)
    assert findings == []


def test_validate_snakefile_paths_still_flags_parent_project_processed_path(tmp_path: Path) -> None:
    from science_tool.commons.dataset_lifecycle import _validate_snakefile_paths

    snakefile = tmp_path / "Snakefile"
    snakefile.write_text('input = "/data/processed/run/table.csv"\n', encoding="utf-8")
    findings = []
    _validate_snakefile_paths(findings, snakefile)
    assert [finding.code for finding in findings] == ["parent-project-path"]
```

- [ ] **Step 2: Run tests**

Run: `cd science && uv run --frozen pytest science/tests/test_commons_dataset_lifecycle.py::test_validate_snakefile_paths_allows_commons_data_root_output science/tests/test_commons_dataset_lifecycle.py::test_validate_snakefile_paths_still_flags_parent_project_processed_path -q`

Expected: PASS.

- [ ] **Step 3: Add docstring**

Add this docstring to `_validate_snakefile_paths`:

```python
    """Flag parent-project data paths in commons recipe Snakefiles.

    This check is commons-recipe-scoped. It does not inspect project workflows
    and intentionally does not flag the commons output layout
    /data/science-commons/<slug>/...
    """
```

- [ ] **Step 4: Run tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_commons_dataset_lifecycle.py::test_validate_snakefile_paths_allows_commons_data_root_output science/tests/test_commons_dataset_lifecycle.py::test_validate_snakefile_paths_still_flags_parent_project_processed_path -q`

Expected: PASS.

Commit:

```bash
git add science/src/science_tool/commons/dataset_lifecycle.py science/tests/test_commons_dataset_lifecycle.py
git commit -m "test: pin commons recipe path-lint boundary"
```

## Task 7: User Docs, Skills, And Mirrors

**Files:**
- Modify: `docs/user-guide/entities.md`
- Modify: `skills/data/frictionless.md`
- Modify: `skills/pipelines/snakemake.md`
- Modify: `commands/create-project.md`
- Modify: `science/tests/test_user_guide_docs.py`
- Modify: `science/tests/test_command_docs.py`
- Modify: `science/tests/test_codex_skills.py`
- Generated: files changed by `scripts/generate_codex_skills.py`

**Interfaces:**
- Documents precedence: `SCIENCE_DATA_ROOT`, project `science.yaml data.root`, global `data.root/<project-id>`, default `./data`.
- Documents logical dirs: `data/raw`, `data/processed`, `data/external`.

- [ ] **Step 1: Add failing docs tests**

Add to `science/tests/test_user_guide_docs.py`:

```python
def test_entities_doc_documents_split_storage_data_root() -> None:
    text = (ROOT / "docs/user-guide/entities.md").read_text(encoding="utf-8")
    assert "## Split storage: version-controlled provenance vs out-of-tree bulk" in text
    assert "SCIENCE_DATA_ROOT" in text
    assert "science.yaml" in text
    assert "data.root" in text
    assert "./data" in text
    assert "Never commit files under the resolved data root" in text
    assert "provenance/" in text
```

Add to `science/tests/test_codex_skills.py`:

```python
def test_data_skills_document_configured_data_root() -> None:
    frictionless = (ROOT / "skills/data/frictionless.md").read_text(encoding="utf-8")
    snakemake = (ROOT / "skills/pipelines/snakemake.md").read_text(encoding="utf-8")
    for text in (frictionless, snakemake):
        assert "SCIENCE_DATA_ROOT" in text
        assert "data.root" in text
        assert "Never commit files under the resolved data root" in text
```

- [ ] **Step 2: Run docs tests and confirm failure**

Run: `cd science && uv run --frozen pytest science/tests/test_user_guide_docs.py::test_entities_doc_documents_split_storage_data_root science/tests/test_codex_skills.py::test_data_skills_document_configured_data_root -q`

Expected: FAIL because the new docs are absent.

- [ ] **Step 3: Add user-guide section**

In `docs/user-guide/entities.md`, add:

```markdown
## Split storage: version-controlled provenance vs out-of-tree bulk

Science separates lightweight, version-controlled provenance from bulk data that should stay off git and out of synced folders.

The resolved project data root uses this precedence:

1. `SCIENCE_DATA_ROOT`
2. `science.yaml` `data.root`
3. global `~/.config/science/config.yaml` `data.root` plus the project id
4. `./data`

`SCIENCE_DATA_ROOT` and global `data.root` must be absolute paths after `~` expansion. A project `science.yaml` value may be absolute or relative to the project root:

```yaml
data:
  root: /data/proj/natural-systems
```

Payload directories keep their logical names even when the physical root moves. Logical `data/raw`, `data/processed`, and `data/external` map to `<resolved-root>/raw`, `<resolved-root>/processed`, and `<resolved-root>/external`.

Never commit files under the resolved data root. Keep version-controlled provenance outside that root, using `provenance/` or `research/packages/` for manifests, QA reports, and small frames. Do not use `data/provenance/` when the resolved root is the default `./data`.
```

- [ ] **Step 4: Update skills**

In `skills/data/frictionless.md`, add:

```markdown
Use `science datasets validate` to validate the resolved project data root, or `science datasets validate --path data/raw/` when intentionally checking an explicit in-repo path. Respect `SCIENCE_DATA_ROOT` and `science.yaml` `data.root`. Never commit files under the resolved data root.
```

In `skills/pipelines/snakemake.md`, add:

```markdown
For project pipelines, write bulk outputs under the resolved data root. The resolver honors `SCIENCE_DATA_ROOT`, then `science.yaml` `data.root`, then global `data.root`, then `./data`. Keep logical references as relative `data/raw`, `data/processed`, or `data/external` paths in manifests, and never commit files under the resolved data root.
```

- [ ] **Step 5: Regenerate mirrors**

Run: `cd science && uv run --frozen python scripts/generate_codex_skills.py`

Expected: exits 0. Stage generated skill mirror changes reported by `git status --short`.

- [ ] **Step 6: Run docs tests and commit**

Run: `cd science && uv run --frozen pytest science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py -q`

Expected: PASS.

Commit:

```bash
git add docs/user-guide/entities.md skills/data/frictionless.md skills/pipelines/snakemake.md commands/create-project.md science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py skills commands
git commit -m "docs: document project data-root split storage"
```

## Task 8: Final Verification

**Files:**
- Review all changed files from Tasks 1-7.

**Interfaces:**
- Verifies default projects still use `<project_root>/data`.
- Verifies out-of-tree payload manifests use logical `data/...` paths.
- Verifies docs and generated mirrors are in sync.

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd science && uv run --frozen pytest \
  science/tests/test_data_root.py \
  science/tests/test_datasets_data_root_cli.py \
  science/tests/test_datasets_validate_cli.py \
  science/tests/test_data_audit.py \
  science/tests/test_data_audit_cli.py \
  science/tests/test_project_package_payload.py \
  science/tests/test_project_serialize.py \
  science/tests/test_project_verify.py \
  science/tests/test_commons_dataset_lifecycle.py \
  science/tests/test_user_guide_docs.py \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run lint and types**

Run:

```bash
cd science && uv run ruff check
cd science && uv run pyright
```

Expected: both commands exit 0.

- [ ] **Step 3: Search for leaked absolute local paths**

Run:

```bash
env -u RIPGREP_CONFIG_PATH rg -n 'path: /data|"/data/proj|/home/.*/d/|/mnt/.*/Dropbox' science/src science/tests docs skills commands
```

Expected: no manifest examples or docs instruct users to store descriptor resource paths as absolute `/data/...` paths, and docs use `~/d/` rather than machine-specific absolute checkout paths.

- [ ] **Step 4: Inspect cumulative diff**

Run:

```bash
git diff --stat
git diff -- science/src/science_tool/data_root.py science/src/science_tool/project_package/payload.py science/src/science_tool/data_audit.py
```

Expected: diff is scoped to resolver, CLI, payload inventory, audit notes, docs, and tests.

## Self-Review

Spec coverage:
- Resolver precedence, absolute global/env validation, project-relative roots, and physical leaf mapping are covered by Task 1.
- CLI lazy defaults, subdirectory discovery, and explicit override behavior are covered by Task 2.
- Repo-boundary-only audit behavior and external-root visibility are covered by Task 3.
- Logical payload manifest paths and out-of-tree serialize/verify behavior are covered by Task 4.
- The no-tracked-files guardrail and scaffolding docs are covered by Task 5.
- Commons recipe-lint scope is covered by Task 6.
- User docs, skills, command docs, and mirrors are covered by Task 7.
- Cumulative verification is covered by Task 8.

Placeholder scan:
- This plan contains no deferred implementation markers.
- Every code-changing step names exact files and concrete snippets.

Type consistency:
- `resolve_data_root(project_root, config=None)` is introduced in Task 1 and consumed by Tasks 2, 3, and 4.
- `discover_project_root(start=None)` is introduced in Task 1 and consumed by Task 2.
- `AuditNote` is introduced in Task 3 and extended in Task 5 with the same fields.
- `payload_inventory(..., data_root=None)` is introduced in Task 4 and consumed by serialize and verify with the same keyword name.
