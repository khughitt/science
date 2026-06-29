# Commons-Born Dataset Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-first `science commons dataset` lifecycle for commons-born dataset packages with required Snakemake workflows, status/build/validation commands, and remote-ready catalog parsing.

**Architecture:** Add focused lifecycle modules under `science_tool.commons` and wire them into the existing `science commons` CLI without replacing the current store-level `init`, registry, resolver, or `find` commands. The lifecycle writes tracked scaffolds only during `dataset init`, delegates builds to `recipe/Snakefile`, resolves payload locations through the existing commons data-root and per-slug override mechanisms, and uses the data-audit `DataPolicy` SSOT for tracked-payload checks.

**Tech Stack:** Python 3.13 stdlib, Click, PyYAML, existing `science_tool.commons` adapter/registry/resolver/config helpers, pytest, `click.testing.CliRunner`, mocked `subprocess.run` for Snakemake invocation tests.

---

## Execution Worktree

Execute this plan from an isolated feature worktree, not the main checkout. Use this exact worktree path for the commands below:

```bash
cd ~/d/science
rtk git fetch
rtk git worktree add -b commons-born-dataset-lifecycle .worktrees/commons-born-dataset-lifecycle plans-cleanup-first-pass
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
```

Expected: a new `commons-born-dataset-lifecycle` branch checked out at `~/d/science/.worktrees/commons-born-dataset-lifecycle`, starting from the branch that contains this plan. When resuming an existing execution worktree, run `cd ~/d/science/.worktrees/commons-born-dataset-lifecycle` and confirm `rtk git branch --show-current` prints `commons-born-dataset-lifecycle`.

## Precondition

This plan depends on the data-audit SSOT from `docs/plans/2026-06-28-data-audit-design.md` for tracked-package payload classification:

- `science/src/science_tool/data_policy.py`
- `DataPolicy.payload_extensions`
- `DEFAULT_DATA_POLICY`
- `classify(rel_path: Path, size_bytes: int, policy: DataPolicy) -> FileClass`

Before executing Task 4, verify that module exists. Stop condition: when this command has no matches, land the data-audit classifier plan first rather than adding a parallel classifier here.

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk rg -n "class DataPolicy|DEFAULT_DATA_POLICY|def classify" src/science_tool/data_policy.py
```

Expected after the prerequisite lands: matches for all three names.

## File Map

Science repo (`~/d/science`):

- Create: `science/src/science_tool/commons/dataset_lifecycle.py`
  - Slug validation, dataset package paths, scaffold rendering/writing, data-output directory resolution, Snakemake command construction/execution, status reporting, and package validation.
- Create: `science/src/science_tool/commons/catalog.py`
  - Parse and validate reserved remote-ready `commons.yaml` catalog source declarations without executing remote operations.
- Modify: `science/src/science_tool/commons/cli.py`
  - Add `science commons dataset init|build|validate|status` subgroup and reuse existing `science commons find`.
- Modify: `docs/user-guide/cross-project-work.md`
  - Document the commons-born dataset lifecycle and distinguish `science commons init` from `science commons dataset init`.
- Test: `science/tests/test_commons_dataset_lifecycle.py`
  - Pure lifecycle unit tests.
- Test: `science/tests/test_commons_cli_dataset.py`
  - CLI tests for `dataset init`, `dataset status`, `dataset build`, and `dataset validate`.
- Test: `science/tests/test_commons_catalog.py`
  - Catalog parser tests for `path`, `git`, `github`, and `zenodo` source entries.
- Modify: `science/tests/test_commons_cli.py`
  - Add a regression proving stale-index warnings on shared `find` apply to non-dataset entity types too.

---

### Task 1: Pure Commons Dataset Lifecycle Scaffold

**Files:**
- Create: `science/src/science_tool/commons/dataset_lifecycle.py`
- Test: `science/tests/test_commons_dataset_lifecycle.py`

- [ ] **Step 1: Write failing scaffold tests**

Create `science/tests/test_commons_dataset_lifecycle.py`:

```python
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.commons.dataset_lifecycle import (
    DatasetLifecycleError,
    dataset_paths,
    resolve_dataset_output_dir,
    scaffold_dataset_package,
    validate_dataset_slug,
    validate_dataset_version,
)


def test_validate_dataset_slug_rejects_bad_values() -> None:
    for value in ["", "Bad_Name", "bad name", "dataset:bad", "../bad", "bad/slug"]:
        with pytest.raises(DatasetLifecycleError):
            validate_dataset_slug(value)


def test_validate_dataset_version_rejects_non_semver_values() -> None:
    for value in ["", "foo", "1", "1.0", "v1.0.0", "1.0.0-beta"]:
        with pytest.raises(DatasetLifecycleError, match="semver"):
            validate_dataset_version(value)


def test_dataset_paths_are_under_commons_dataset_dir(tmp_path: Path) -> None:
    paths = dataset_paths(tmp_path / "commons", "dbsnp-human")

    assert paths.dataset_dir == tmp_path / "commons" / "datasets" / "dbsnp-human"
    assert paths.entity_path == paths.dataset_dir / "entity.md"
    assert paths.datapackage_path == paths.dataset_dir / "datapackage.yaml"
    assert paths.snakefile_path == paths.dataset_dir / "recipe" / "Snakefile"
    assert paths.readme_path == paths.dataset_dir / "recipe" / "README.md"


def test_scaffold_dataset_package_writes_required_files(tmp_path: Path) -> None:
    root = tmp_path / "commons"

    result = scaffold_dataset_package(
        root,
        "dbsnp-human",
        title="Human dbSNP labels",
        version="0.1.0",
        today="2026-06-29",
    )

    assert result.dataset_dir == root / "datasets" / "dbsnp-human"
    assert result.created == [
        root / "datasets" / "dbsnp-human" / "entity.md",
        root / "datasets" / "dbsnp-human" / "datapackage.yaml",
        root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile",
        root / "datasets" / "dbsnp-human" / "recipe" / "README.md",
    ]

    entity_text = result.paths.entity_path.read_text(encoding="utf-8")
    assert "id: dataset:dbsnp-human" in entity_text
    assert 'version: "0.1.0"' in entity_text
    assert "origin: external" in entity_text
    assert "datapackage: datapackage.yaml" in entity_text

    datapackage = yaml.safe_load(result.paths.datapackage_path.read_text(encoding="utf-8"))
    assert datapackage == {
        "name": "dbsnp-human",
        "profile": "data-package",
        "resources": [],
    }

    snakefile = result.paths.snakefile_path.read_text(encoding="utf-8")
    assert 'rule all:' in snakefile
    assert 'DATASET_SLUG = "dbsnp-human"' in snakefile
    assert "dataset_output_dir" in snakefile


@pytest.mark.skipif(shutil.which("snakemake") is None, reason="snakemake executable is not installed")
def test_scaffold_snakefile_parses_with_snakemake_dry_run(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    result = scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    output_dir = tmp_path / "science-commons-data" / "dbsnp-human"

    completed = subprocess.run(
        [
            "snakemake",
            "-n",
            "-s",
            str(result.paths.snakefile_path),
            "--cores",
            "1",
            "--config",
            "dataset_slug=dbsnp-human",
            f"dataset_output_dir={output_dir}",
            f"commons_data_root={tmp_path / 'science-commons-data'}",
            f"output_root={tmp_path / 'science-commons-data'}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_scaffold_dataset_package_refuses_existing_dataset(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    (root / "datasets" / "dbsnp-human").mkdir(parents=True)

    with pytest.raises(DatasetLifecycleError, match="already exists"):
        scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")


def test_resolve_dataset_output_dir_prefers_data_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    override = tmp_path / "science-commons-data" / "dbsnp-human"
    (cfg / "data.yaml").write_text(f"dbsnp-human: {override}\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "fallback-data"))

    assert resolve_dataset_output_dir("dbsnp-human") == override


def test_resolve_dataset_output_dir_uses_commons_data_root_without_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "data.yaml").write_text("", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data-root"))

    assert resolve_dataset_output_dir("dbsnp-human") == tmp_path / "data-root" / "dbsnp-human"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.dataset_lifecycle'`.

- [ ] **Step 3: Implement scaffold primitives**

Create `science/src/science_tool/commons/dataset_lifecycle.py`:

```python
"""Local-first lifecycle helpers for commons-born dataset packages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from science_tool.commons.config import load_data_overrides, resolve_commons_data_root

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class DatasetLifecycleError(ValueError):
    """Raised when a commons-born dataset lifecycle operation is invalid."""


@dataclass(frozen=True, slots=True)
class DatasetPackagePaths:
    dataset_dir: Path
    entity_path: Path
    datapackage_path: Path
    recipe_dir: Path
    snakefile_path: Path
    readme_path: Path


@dataclass(frozen=True, slots=True)
class ScaffoldResult:
    slug: str
    dataset_dir: Path
    paths: DatasetPackagePaths
    created: list[Path]


def validate_dataset_slug(slug: str) -> str:
    value = slug.strip()
    if not _SLUG_RE.fullmatch(value):
        raise DatasetLifecycleError(
            f"invalid dataset slug {slug!r}; use lowercase letters, digits, and hyphens"
        )
    return value


def validate_dataset_version(version: str) -> str:
    value = version.strip()
    if not _SEMVER_RE.fullmatch(value):
        raise DatasetLifecycleError(f"invalid dataset version {version!r}; expected semver like 0.1.0")
    return value


def dataset_paths(commons_root: Path, slug: str) -> DatasetPackagePaths:
    slug = validate_dataset_slug(slug)
    dataset_dir = commons_root / "datasets" / slug
    recipe_dir = dataset_dir / "recipe"
    return DatasetPackagePaths(
        dataset_dir=dataset_dir,
        entity_path=dataset_dir / "entity.md",
        datapackage_path=dataset_dir / "datapackage.yaml",
        recipe_dir=recipe_dir,
        snakefile_path=recipe_dir / "Snakefile",
        readme_path=recipe_dir / "README.md",
    )


def resolve_dataset_output_dir(slug: str, *, data_root: Path | None = None) -> Path:
    slug = validate_dataset_slug(slug)
    override = load_data_overrides().get(slug)
    if override is not None:
        return override
    return (data_root or resolve_commons_data_root()) / slug


def scaffold_dataset_package(
    commons_root: Path,
    slug: str,
    *,
    title: str | None = None,
    version: str = "0.1.0",
    today: str | None = None,
) -> ScaffoldResult:
    slug = validate_dataset_slug(slug)
    version = validate_dataset_version(version)
    paths = dataset_paths(commons_root, slug)
    if paths.dataset_dir.exists():
        raise DatasetLifecycleError(f"commons dataset {slug!r} already exists at {paths.dataset_dir}")

    title = title or slug.replace("-", " ").title()
    today = today or date.today().isoformat()
    paths.recipe_dir.mkdir(parents=True)
    writes = [
        (paths.entity_path, _render_entity(slug, title=title, version=version, today=today)),
        (paths.datapackage_path, _render_datapackage(slug)),
        (paths.snakefile_path, _render_snakefile(slug)),
        (paths.readme_path, _render_readme(slug, title=title)),
    ]
    for path, text in writes:
        path.write_text(text, encoding="utf-8")
    return ScaffoldResult(
        slug=slug,
        dataset_dir=paths.dataset_dir,
        paths=paths,
        created=[path for path, _ in writes],
    )


def _render_entity(slug: str, *, title: str, version: str, today: str) -> str:
    class QuotedString(str):
        pass

    class EntityDumper(yaml.SafeDumper):
        pass

    def quoted_string_representer(dumper: yaml.SafeDumper, data: QuotedString):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')

    EntityDumper.add_representer(QuotedString, quoted_string_representer)
    body = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": f"dataset:{slug}",
        "type": "dataset",
        "title": title,
        "version": QuotedString(version),
        "created": today,
        "updated": today,
        "status": "active",
        "origin": "external",
        "source_class": "reference",
        "tier": "track",
        "access": {"level": "public", "availability": "available", "verified": False},
        "datapackage": "datapackage.yaml",
    }
    return "---\n" + yaml.dump(body, Dumper=EntityDumper, sort_keys=False) + "---\n\nDescribe the commons dataset wrapper here.\n"


def _render_datapackage(slug: str) -> str:
    return yaml.safe_dump(
        {"name": slug, "profile": "data-package", "resources": []},
        sort_keys=False,
    )


def _render_snakefile(slug: str) -> str:
    return (
        "from pathlib import Path\n\n"
        f'DATASET_SLUG = "{slug}"\n'
        'if "dataset_output_dir" not in config:\n'
        '    raise ValueError("dataset_output_dir config is required; run through science commons dataset build")\n'
        'DATASET_OUTPUT_DIR = Path(config["dataset_output_dir"])\n\n'
        "rule all:\n"
        "    input:\n"
        "        []\n"
    )


def _render_readme(slug: str, *, title: str) -> str:
    return (
        f"# {title}\n\n"
        f"This recipe builds `dataset:{slug}`.\n\n"
        "Run through Science so the standard commons data roots are passed into Snakemake:\n\n"
        "```bash\n"
        f"science commons dataset build {slug}\n"
        "```\n"
        "\n"
        "Use the `dataset_output_dir` Snakemake config value for all generated outputs.\n"
        "Do not reconstruct it as `output_root/<slug>` because per-machine `data.yaml`\n"
        "overrides can point a dataset slug outside the default commons data root.\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/src/science_tool/commons/dataset_lifecycle.py science/tests/test_commons_dataset_lifecycle.py
rtk git commit -m "feat: add commons dataset lifecycle scaffolds"
```

---

### Task 2: `science commons dataset init`

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_cli_dataset.py`

- [ ] **Step 1: Write failing CLI init tests**

Create `science/tests/test_commons_cli_dataset.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def test_dataset_init_creates_package(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "dbsnp-human",
            "--title",
            "Human dbSNP labels",
            "--date",
            "2026-06-29",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["slug"] == "dbsnp-human"
    assert payload["dataset_dir"] == "datasets/dbsnp-human"
    assert payload["created"] == [
        "datasets/dbsnp-human/entity.md",
        "datasets/dbsnp-human/datapackage.yaml",
        "datasets/dbsnp-human/recipe/Snakefile",
        "datasets/dbsnp-human/recipe/README.md",
    ]
    assert (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").is_file()


def test_dataset_init_human_output_names_next_steps(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    assert result.exit_code == 0, result.output
    assert "created commons dataset dataset:dbsnp-human" in result.output
    assert "science commons dataset build dbsnp-human" in result.output
    assert "science commons dataset validate dbsnp-human" in result.output


def test_dataset_init_refuses_existing_package(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets" / "dbsnp-human").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_dataset_init_refuses_non_semver_version(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human", "--version", "foo"])

    assert result.exit_code == 1
    assert "invalid dataset version" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_cli_dataset.py -q
```

Expected: FAIL because `science commons dataset` does not exist.

- [ ] **Step 3: Wire the CLI subgroup and `init` command**

Modify `science/src/science_tool/commons/cli.py`.

Add imports near the existing commons imports:

```python
from science_tool.commons.dataset_lifecycle import (
    DatasetLifecycleError,
    scaffold_dataset_package,
)
```

Add this group before the existing `data_group`:

```python
@commons_group.group("dataset")
def dataset_group() -> None:
    """Manage commons-born dataset packages."""
```

Add this command below `dataset_group`:

```python
@dataset_group.command("init")
@click.argument("slug")
@click.option("--title", default=None, help="Dataset title. Defaults to title-cased slug.")
@click.option("--version", default="0.1.0", show_default=True, help="Wrapper package version.")
@click.option("--date", "today", default=None, help="Creation/update date override for tests.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def dataset_init_cmd(
    slug: str,
    title: str | None,
    version: str,
    today: str | None,
    as_json: bool,
) -> None:
    """Create a commons-born dataset package skeleton."""
    root = _require_root()
    try:
        result = scaffold_dataset_package(
            root,
            slug,
            title=title,
            version=version,
            today=today,
        )
    except DatasetLifecycleError as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(
            json.dumps(
                {
                    "slug": result.slug,
                    "dataset_dir": str(result.dataset_dir.relative_to(root)),
                    "created": [str(path.relative_to(root)) for path in result.created],
                    "next": [
                        f"science commons dataset build {result.slug}",
                        f"science commons dataset validate {result.slug}",
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    click.echo(f"created commons dataset dataset:{result.slug} at {result.dataset_dir.relative_to(root)}")
    click.echo(f"next: science commons dataset build {result.slug}")
    click.echo(f"next: science commons dataset validate {result.slug}")
```

- [ ] **Step 4: Run CLI init tests**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_cli_dataset.py -q
```

Expected: PASS.

- [ ] **Step 5: Run existing commons CLI smoke tests**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_cli.py::test_init_creates_store tests/test_commons_cli.py::test_find_default_output -q
```

Expected: PASS. This proves `dataset init` did not collide with store-level `commons init` or existing `find`.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli_dataset.py
rtk git commit -m "feat: scaffold commons-born datasets"
```

---

### Task 3: Dataset Status

**Files:**
- Modify: `science/src/science_tool/commons/dataset_lifecycle.py`
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_dataset_lifecycle.py`
- Test: `science/tests/test_commons_cli_dataset.py`

- [ ] **Step 1: Write failing status unit tests**

Append to `science/tests/test_commons_dataset_lifecycle.py`:

```python
from science_tool.commons.dataset_lifecycle import dataset_status


def test_dataset_status_reports_unbuilt_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")

    status = dataset_status(root, "dbsnp-human")

    assert status.exists is True
    assert status.workflow_exists is True
    assert status.lockfile_exists is False
    assert status.datapackage_exists is True
    assert status.datapackage_placeholder_hashes is False
    assert status.output_dir == tmp_path / "data" / "dbsnp-human"
    assert status.outputs_present == []
    assert status.outputs_missing == []


def test_dataset_status_reports_real_and_missing_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    override = tmp_path / "science-commons-data" / "dbsnp-human"
    (cfg / "data.yaml").write_text(f"dbsnp-human: {override}\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "fallback"))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    override.mkdir(parents=True)
    (override / "built.txt").write_text("ok", encoding="utf-8")
    (root / "datasets" / "dbsnp-human" / "datapackage.yaml").write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: built\n"
        "  path: built.txt\n"
        "  hash: sha256:0000000000000000000000000000000000000000000000000000000000000001\n"
        "- name: missing\n"
        "  path: missing.txt\n"
        "  hash: sha256:0000000000000000000000000000000000000000000000000000000000000002\n",
        encoding="utf-8",
    )

    status = dataset_status(root, "dbsnp-human")

    assert status.output_dir == override
    assert status.outputs_present == ["built.txt"]
    assert status.outputs_missing == ["missing.txt"]
```

- [ ] **Step 2: Write failing status CLI tests**

Append to `science/tests/test_commons_cli_dataset.py`:

```python
def test_dataset_status_json_reports_unbuilt_scaffold(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    init = runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    assert init.exit_code == 0, init.output

    result = runner.invoke(commons_group, ["dataset", "status", "dbsnp-human", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["slug"] == "dbsnp-human"
    assert payload["exists"] is True
    assert payload["workflow_exists"] is True
    assert payload["lockfile_exists"] is False
    assert payload["output_dir"] == str(tmp_path / "data" / "dbsnp-human")


def test_dataset_status_human_does_not_fail_for_missing_payloads(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    result = runner.invoke(commons_group, ["dataset", "status", "dbsnp-human"])

    assert result.exit_code == 0, result.output
    assert "dataset:dbsnp-human" in result.output
    assert "workflow: present" in result.output
```

- [ ] **Step 3: Run status tests to verify they fail**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py::test_dataset_status_reports_unbuilt_scaffold tests/test_commons_dataset_lifecycle.py::test_dataset_status_reports_real_and_missing_resources tests/test_commons_cli_dataset.py::test_dataset_status_json_reports_unbuilt_scaffold tests/test_commons_cli_dataset.py::test_dataset_status_human_does_not_fail_for_missing_payloads -q
```

Expected: FAIL because `dataset_status` and CLI `status` are missing.

- [ ] **Step 4: Implement status model and reader**

Append to `science/src/science_tool/commons/dataset_lifecycle.py`:

```python
@dataclass(frozen=True, slots=True)
class DatasetStatus:
    slug: str
    exists: bool
    dataset_dir: Path
    workflow_exists: bool
    lockfile_exists: bool
    datapackage_exists: bool
    datapackage_placeholder_hashes: bool
    output_dir: Path
    outputs_present: list[str]
    outputs_missing: list[str]


def dataset_status(commons_root: Path, slug: str) -> DatasetStatus:
    slug = validate_dataset_slug(slug)
    paths = dataset_paths(commons_root, slug)
    output_dir = resolve_dataset_output_dir(slug)
    resources = _read_datapackage_resources(paths.datapackage_path)
    outputs_present: list[str] = []
    outputs_missing: list[str] = []
    for resource in resources:
        rel = resource.get("path")
        if not isinstance(rel, str):
            continue
        if (output_dir / rel).is_file():
            outputs_present.append(rel)
        else:
            outputs_missing.append(rel)
    return DatasetStatus(
        slug=slug,
        exists=paths.dataset_dir.is_dir(),
        dataset_dir=paths.dataset_dir,
        workflow_exists=paths.snakefile_path.is_file(),
        lockfile_exists=(paths.recipe_dir / "lockfile.yaml").is_file(),
        datapackage_exists=paths.datapackage_path.is_file(),
        datapackage_placeholder_hashes=any(_is_placeholder_resource(r) for r in resources),
        output_dir=output_dir,
        outputs_present=outputs_present,
        outputs_missing=outputs_missing,
    )


def _read_datapackage_resources(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    resources = raw.get("resources")
    return [r for r in resources if isinstance(r, dict)] if isinstance(resources, list) else []


def _is_placeholder_resource(resource: dict) -> bool:
    raw_hash = resource.get("hash")
    raw_bytes = resource.get("bytes")
    return raw_hash == "sha256:" + ("0" * 64) or raw_bytes == 0
```

- [ ] **Step 5: Wire `dataset status` CLI**

Modify imports in `science/src/science_tool/commons/cli.py`:

```python
from science_tool.commons.dataset_lifecycle import (
    DatasetLifecycleError,
    dataset_status,
    scaffold_dataset_package,
)
```

Add below `dataset_init_cmd`:

```python
@dataset_group.command("status")
@click.argument("slug")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def dataset_status_cmd(slug: str, as_json: bool) -> None:
    """Report commons-born dataset package and build state."""
    root = _require_root()
    try:
        status = dataset_status(root, slug)
    except DatasetLifecycleError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(
            json.dumps(
                {
                    "slug": status.slug,
                    "exists": status.exists,
                    "dataset_dir": str(status.dataset_dir.relative_to(root)),
                    "workflow_exists": status.workflow_exists,
                    "lockfile_exists": status.lockfile_exists,
                    "datapackage_exists": status.datapackage_exists,
                    "datapackage_placeholder_hashes": status.datapackage_placeholder_hashes,
                    "output_dir": str(status.output_dir),
                    "outputs_present": status.outputs_present,
                    "outputs_missing": status.outputs_missing,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    click.echo(f"dataset:{status.slug}")
    click.echo(f"  package: {'present' if status.exists else 'missing'}")
    click.echo(f"  workflow: {'present' if status.workflow_exists else 'missing'}")
    click.echo(f"  lockfile: {'present' if status.lockfile_exists else 'missing'}")
    click.echo(f"  datapackage: {'present' if status.datapackage_exists else 'missing'}")
    click.echo(f"  output_dir: {status.output_dir}")
    click.echo(f"  outputs_present: {len(status.outputs_present)}")
    click.echo(f"  outputs_missing: {len(status.outputs_missing)}")
```

- [ ] **Step 6: Run status tests**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py::test_dataset_status_reports_unbuilt_scaffold tests/test_commons_dataset_lifecycle.py::test_dataset_status_reports_real_and_missing_resources tests/test_commons_cli_dataset.py::test_dataset_status_json_reports_unbuilt_scaffold tests/test_commons_cli_dataset.py::test_dataset_status_human_does_not_fail_for_missing_payloads -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/src/science_tool/commons/dataset_lifecycle.py science/src/science_tool/commons/cli.py science/tests/test_commons_dataset_lifecycle.py science/tests/test_commons_cli_dataset.py
rtk git commit -m "feat: report commons dataset lifecycle status"
```

---

### Task 4: Dataset Package Validation

**Files:**
- Modify: `science/src/science_tool/commons/dataset_lifecycle.py`
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_dataset_lifecycle.py`
- Test: `science/tests/test_commons_cli_dataset.py`

- [ ] **Step 1: Verify data-policy prerequisite**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk rg -n "class DataPolicy|DEFAULT_DATA_POLICY|def classify" src/science_tool/data_policy.py
```

Expected: matches for `DataPolicy`, `DEFAULT_DATA_POLICY`, and `classify`. Stop condition: no matches means the data-audit classifier must land before Task 4.

- [ ] **Step 2: Write failing package validation tests**

Append to `science/tests/test_commons_dataset_lifecycle.py`:

```python
from science_tool.commons.dataset_lifecycle import validate_dataset_package


def test_validate_dataset_package_accepts_unbuilt_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is True
    assert report.findings == []


def test_validate_dataset_package_reports_missing_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "missing-workflow" for f in report.findings)


def test_validate_dataset_package_reports_non_semver_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    entity = root / "datasets" / "dbsnp-human" / "entity.md"
    entity.write_text(
        entity.read_text(encoding="utf-8").replace('version: "0.1.0"', 'version: "foo"'),
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "version-invalid" for f in report.findings)


def test_validate_dataset_package_reports_tracked_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "bulk.feather"
    payload.write_bytes(b"x" * 10)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)


def test_validate_dataset_package_respects_tracked_payload_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    entity = root / "datasets" / "dbsnp-human" / "entity.md"
    text = entity.read_text(encoding="utf-8")
    text = text.replace(
        "datapackage: datapackage.yaml\n",
        "datapackage: datapackage.yaml\ntracked_payload_allowlist:\n- path: bulk.feather\n  reason: tiny fixture\n",
    )
    entity.write_text(text, encoding="utf-8")
    (root / "datasets" / "dbsnp-human" / "bulk.feather").write_bytes(b"x" * 10)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is True
    assert report.findings == []


def test_validate_dataset_package_reports_parent_project_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").write_text(
        "rule all:\n"
        "    input:\n"
        "        '/data/proj/example/data/raw/x.csv'\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "parent-project-path" for f in report.findings)


def test_validate_dataset_package_reports_payload_inside_recipe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "recipe" / "big.parquet"
    payload.write_bytes(b"x" * 10)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)


def test_validate_dataset_package_reports_large_record_pattern_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "dbsnp-report.json"
    payload.write_bytes(b"x" * 200_000)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)


def test_validate_dataset_package_reports_large_recipe_lookup_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "recipe" / "lookup.json"
    payload.write_bytes(b"x" * 200_000)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)
```

- [ ] **Step 3: Write failing validation CLI tests**

Append to `science/tests/test_commons_cli_dataset.py`:

```python
def test_dataset_validate_json_accepts_unbuilt_scaffold(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    result = runner.invoke(commons_group, ["dataset", "validate", "dbsnp-human", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["findings"] == []


def test_dataset_validate_exits_1_for_missing_workflow(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    result = runner.invoke(commons_group, ["dataset", "validate", "dbsnp-human"])

    assert result.exit_code == 1
    assert "missing-workflow" in result.output
```

- [ ] **Step 4: Run validation tests to verify they fail**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_accepts_unbuilt_scaffold tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_missing_workflow tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_non_semver_version tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_tracked_payload tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_respects_tracked_payload_allowlist tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_parent_project_paths tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_payload_inside_recipe tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_large_record_pattern_file tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_large_recipe_lookup_json tests/test_commons_cli_dataset.py::test_dataset_validate_json_accepts_unbuilt_scaffold tests/test_commons_cli_dataset.py::test_dataset_validate_exits_1_for_missing_workflow -q
```

Expected: FAIL because `validate_dataset_package` and CLI `validate` are missing.

- [ ] **Step 5: Implement package validation**

Append imports to `science/src/science_tool/commons/dataset_lifecycle.py`:

```python
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.errors import CommonsEntityError
from science_tool.data_policy import DEFAULT_DATA_POLICY, FileClass, classify
from science_tool.markdown_utils import parse_frontmatter
```

Append validation types and helpers:

```python
@dataclass(frozen=True, slots=True)
class DatasetPackageFinding:
    code: str
    message: str
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class DatasetPackageValidationReport:
    slug: str
    valid: bool
    findings: list[DatasetPackageFinding]


def validate_dataset_package(commons_root: Path, slug: str) -> DatasetPackageValidationReport:
    slug = validate_dataset_slug(slug)
    paths = dataset_paths(commons_root, slug)
    findings: list[DatasetPackageFinding] = []

    if not paths.entity_path.is_file():
        findings.append(DatasetPackageFinding("missing-entity", "missing entity.md", paths.entity_path))
    if not paths.datapackage_path.is_file():
        findings.append(DatasetPackageFinding("missing-datapackage", "missing datapackage.yaml", paths.datapackage_path))
    if not paths.snakefile_path.is_file():
        findings.append(DatasetPackageFinding("missing-workflow", "missing recipe/Snakefile", paths.snakefile_path))

    frontmatter = _frontmatter_or_empty(paths.entity_path)
    if frontmatter:
        if frontmatter.get("id") != f"dataset:{slug}":
            findings.append(DatasetPackageFinding("id-mismatch", f"entity id must be dataset:{slug}", paths.entity_path))
        if frontmatter.get("type") != "dataset":
            findings.append(DatasetPackageFinding("type-mismatch", "entity type must be dataset", paths.entity_path))
        if not frontmatter.get("version"):
            findings.append(DatasetPackageFinding("missing-version", "entity version is required", paths.entity_path))
        elif not isinstance(frontmatter.get("version"), str) or not _SEMVER_RE.fullmatch(frontmatter["version"]):
            findings.append(
                DatasetPackageFinding("version-invalid", "entity version must be semver like 0.1.0", paths.entity_path)
            )
        if frontmatter.get("datapackage") != "datapackage.yaml":
            findings.append(DatasetPackageFinding("datapackage-field", "datapackage must be datapackage.yaml", paths.entity_path))

    try:
        CommonsEntityAdapter(commons_root).load(f"dataset:{slug}")
    except CommonsEntityError as exc:
        findings.append(DatasetPackageFinding("entity-invalid", str(exc.cause), exc.path))

    allowlist = _tracked_payload_allowlist(frontmatter)
    if paths.dataset_dir.is_dir():
        for path in sorted(p for p in paths.dataset_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(paths.dataset_dir).as_posix()
            if rel in allowlist:
                continue
            if _is_canonical_metadata_path(rel):
                continue
            size_bytes = path.stat().st_size
            file_class = classify(Path(rel), size_bytes)
            is_large_flag = file_class is FileClass.FLAG and size_bytes > DEFAULT_DATA_POLICY.size_threshold
            if file_class is FileClass.PAYLOAD or is_large_flag:
                findings.append(DatasetPackageFinding("tracked-payload", f"tracked package contains payload-like file {rel}", path))

    if paths.snakefile_path.is_file():
        snakefile_text = paths.snakefile_path.read_text(encoding="utf-8")
        parent_project_markers = ("/data/proj/", "/data/raw/", "/data/clean/", "/data/processed/")
        if any(marker in snakefile_text for marker in parent_project_markers):
            findings.append(
                DatasetPackageFinding(
                    "parent-project-path",
                    "workflow must not depend on parent project data/results paths",
                    paths.snakefile_path,
                )
            )

    return DatasetPackageValidationReport(slug=slug, valid=not findings, findings=findings)


def _frontmatter_or_empty(path: Path) -> dict:
    if not path.is_file():
        return {}
    frontmatter, _ = parse_frontmatter(path)
    return frontmatter if isinstance(frontmatter, dict) else {}


def _tracked_payload_allowlist(frontmatter: dict) -> set[str]:
    raw = frontmatter.get("tracked_payload_allowlist")
    if not isinstance(raw, list):
        return set()
    result: set[str] = set()
    for row in raw:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            result.add(row["path"])
    return result


def _is_canonical_metadata_path(rel: str) -> bool:
    return rel in {"entity.md", "datapackage.yaml", "recipe/Snakefile", "recipe/README.md", "recipe/lockfile.yaml"}
```

- [ ] **Step 6: Wire `dataset validate` CLI**

Modify imports in `science/src/science_tool/commons/cli.py`:

```python
from science_tool.commons.dataset_lifecycle import (
    DatasetLifecycleError,
    dataset_status,
    scaffold_dataset_package,
    validate_dataset_package,
)
```

Add below `dataset_status_cmd`:

```python
@dataset_group.command("validate")
@click.argument("slug")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def dataset_validate_cmd(slug: str, as_json: bool) -> None:
    """Validate one commons-born dataset package."""
    root = _require_root()
    try:
        report = validate_dataset_package(root, slug)
    except DatasetLifecycleError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(
            json.dumps(
                {
                    "slug": report.slug,
                    "valid": report.valid,
                    "findings": [
                        {
                            "code": finding.code,
                            "message": finding.message,
                            "path": str(finding.path.relative_to(root)) if finding.path and finding.path.is_relative_to(root) else (str(finding.path) if finding.path else None),
                        }
                        for finding in report.findings
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        click.echo(f"dataset:{report.slug} {'valid' if report.valid else 'invalid'}")
        for finding in report.findings:
            path = f" {finding.path}" if finding.path else ""
            click.echo(f"  {finding.code}:{path} {finding.message}", err=True)
    if not report.valid:
        raise click.exceptions.Exit(1)
```

- [ ] **Step 7: Run validation tests**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_accepts_unbuilt_scaffold tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_missing_workflow tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_non_semver_version tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_tracked_payload tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_respects_tracked_payload_allowlist tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_parent_project_paths tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_payload_inside_recipe tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_large_record_pattern_file tests/test_commons_dataset_lifecycle.py::test_validate_dataset_package_reports_large_recipe_lookup_json tests/test_commons_cli_dataset.py::test_dataset_validate_json_accepts_unbuilt_scaffold tests/test_commons_cli_dataset.py::test_dataset_validate_exits_1_for_missing_workflow -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/src/science_tool/commons/dataset_lifecycle.py science/src/science_tool/commons/cli.py science/tests/test_commons_dataset_lifecycle.py science/tests/test_commons_cli_dataset.py
rtk git commit -m "feat: validate commons-born dataset packages"
```

---

### Task 5: Snakemake Build Command

**Files:**
- Modify: `science/src/science_tool/commons/dataset_lifecycle.py`
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_dataset_lifecycle.py`
- Test: `science/tests/test_commons_cli_dataset.py`

- [ ] **Step 1: Write failing build unit tests**

Append to `science/tests/test_commons_dataset_lifecycle.py`:

```python
from science_tool.commons.dataset_lifecycle import build_dataset_package, snakemake_build_command


def test_snakemake_build_command_uses_workflow_and_override_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    override = tmp_path / "science-commons-data" / "dbsnp-human"
    (cfg / "data.yaml").write_text(f"dbsnp-human: {override}\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "fallback"))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")

    command = snakemake_build_command(root, "dbsnp-human", cores=2)

    assert command[:4] == ["snakemake", "-s", str(root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile")]
    assert "--cores" in command
    assert "2" in command
    assert "--config" in command
    assert f"dataset_slug=dbsnp-human" in command
    assert f"dataset_output_dir={override}" in command
    assert f"source_root={override / '_src'}" in command


def test_build_dataset_package_invokes_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    calls: list[list[str]] = []

    def fake_runner(command: list[str]) -> int:
        calls.append(command)
        return 0

    exit_code = build_dataset_package(root, "dbsnp-human", cores=1, runner=fake_runner)

    assert exit_code == 0
    assert calls
    assert calls[0][0] == "snakemake"


def test_build_dataset_package_refuses_missing_snakefile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    with pytest.raises(DatasetLifecycleError, match="missing recipe/Snakefile"):
        snakemake_build_command(root, "dbsnp-human")
```

- [ ] **Step 2: Write failing build CLI test**

Append to `science/tests/test_commons_cli_dataset.py`:

```python
def test_dataset_build_invokes_snakemake(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    calls: list[list[str]] = []

    def fake_run(command, check=False):
        calls.append(list(command))
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr("science_tool.commons.dataset_lifecycle.subprocess.run", fake_run)

    result = runner.invoke(commons_group, ["dataset", "build", "dbsnp-human", "--cores", "2"])

    assert result.exit_code == 0, result.output
    assert "snakemake exited 0" in result.output
    assert calls
    assert calls[0][0] == "snakemake"
    assert "--cores" in calls[0]
    assert "2" in calls[0]


def test_dataset_build_reports_missing_snakefile_as_click_error(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    result = runner.invoke(commons_group, ["dataset", "build", "dbsnp-human"])

    assert result.exit_code == 1
    assert "missing recipe/Snakefile" in result.output
```

- [ ] **Step 3: Run build tests to verify they fail**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py::test_snakemake_build_command_uses_workflow_and_override_output_dir tests/test_commons_dataset_lifecycle.py::test_build_dataset_package_invokes_runner tests/test_commons_dataset_lifecycle.py::test_build_dataset_package_refuses_missing_snakefile tests/test_commons_cli_dataset.py::test_dataset_build_invokes_snakemake tests/test_commons_cli_dataset.py::test_dataset_build_reports_missing_snakefile_as_click_error -q
```

Expected: FAIL because build helpers and CLI command are missing.

- [ ] **Step 4: Implement build helpers**

Add imports to `science/src/science_tool/commons/dataset_lifecycle.py`:

```python
import subprocess
from collections.abc import Callable
```

Append:

```python
BuildRunner = Callable[[list[str]], int]


def snakemake_build_command(commons_root: Path, slug: str, *, cores: int = 1) -> list[str]:
    slug = validate_dataset_slug(slug)
    paths = dataset_paths(commons_root, slug)
    if not paths.snakefile_path.is_file():
        raise DatasetLifecycleError(f"missing recipe/Snakefile: {paths.snakefile_path}")
    data_root = resolve_commons_data_root()
    dataset_output_dir = resolve_dataset_output_dir(slug, data_root=data_root)
    return [
        "snakemake",
        "-s",
        str(paths.snakefile_path),
        "--cores",
        str(cores),
        "--config",
        f"dataset_slug={slug}",
        f"commons_data_root={data_root}",
        f"output_root={data_root}",
        f"source_root={dataset_output_dir / '_src'}",
        f"dataset_output_dir={dataset_output_dir}",
    ]


def build_dataset_package(
    commons_root: Path,
    slug: str,
    *,
    cores: int = 1,
    runner: BuildRunner | None = None,
) -> int:
    command = snakemake_build_command(commons_root, slug, cores=cores)
    if runner is not None:
        return runner(command)
    result = subprocess.run(command, check=False)
    return int(result.returncode)
```

- [ ] **Step 5: Wire `dataset build` CLI**

Modify imports in `science/src/science_tool/commons/cli.py`:

```python
from science_tool.commons.dataset_lifecycle import (
    DatasetLifecycleError,
    build_dataset_package,
    dataset_status,
    scaffold_dataset_package,
    validate_dataset_package,
)
```

Add below `dataset_init_cmd`:

```python
@dataset_group.command("build")
@click.argument("slug")
@click.option("--cores", type=int, default=1, show_default=True, help="Snakemake core count.")
def dataset_build_cmd(slug: str, cores: int) -> None:
    """Build a commons-born dataset through recipe/Snakefile."""
    if cores < 1:
        raise click.UsageError("--cores must be >= 1")
    root = _require_root()
    try:
        code = build_dataset_package(root, slug, cores=cores)
    except DatasetLifecycleError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"snakemake exited {code}")
    if code != 0:
        raise click.exceptions.Exit(code)
```

- [ ] **Step 6: Run build tests**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_dataset_lifecycle.py::test_snakemake_build_command_uses_workflow_and_override_output_dir tests/test_commons_dataset_lifecycle.py::test_build_dataset_package_invokes_runner tests/test_commons_dataset_lifecycle.py::test_build_dataset_package_refuses_missing_snakefile tests/test_commons_cli_dataset.py::test_dataset_build_invokes_snakemake tests/test_commons_cli_dataset.py::test_dataset_build_reports_missing_snakefile_as_click_error -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/src/science_tool/commons/dataset_lifecycle.py science/src/science_tool/commons/cli.py science/tests/test_commons_dataset_lifecycle.py science/tests/test_commons_cli_dataset.py
rtk git commit -m "feat: build commons datasets through snakemake"
```

---

### Task 6: Remote-Ready Catalog Parser

**Files:**
- Create: `science/src/science_tool/commons/catalog.py`
- Test: `science/tests/test_commons_catalog.py`

- [ ] **Step 1: Write failing catalog parser tests**

Create `science/tests/test_commons_catalog.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.catalog import CatalogSource, CommonsCatalog, CatalogError, load_commons_catalog


def test_load_commons_catalog_accepts_reserved_source_types(tmp_path: Path) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\n"
        "sources:\n"
        "  local:\n"
        "    type: path\n"
        "    uri: ~/d/science-commons\n"
        "  bio:\n"
        "    type: git\n"
        "    uri: https://github.com/org/science-bio-commons.git\n"
        "  github-main:\n"
        "    type: github\n"
        "    repo: org/science-bio-commons\n"
        "  dbsnp:\n"
        "    type: zenodo\n"
        "    doi: 10.5281/zenodo.12345\n",
        encoding="utf-8",
    )

    catalog = load_commons_catalog(path)

    assert catalog == CommonsCatalog(
        catalog_version=1,
        sources={
            "local": CatalogSource(type="path", uri="~/d/science-commons", repo=None, doi=None),
            "bio": CatalogSource(type="git", uri="https://github.com/org/science-bio-commons.git", repo=None, doi=None),
            "github-main": CatalogSource(type="github", uri=None, repo="org/science-bio-commons", doi=None),
            "dbsnp": CatalogSource(type="zenodo", uri=None, repo=None, doi="10.5281/zenodo.12345"),
        },
    )


def test_load_commons_catalog_rejects_unknown_source_type(tmp_path: Path) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\nsources:\n  bad:\n    type: ftp\n    uri: ftp://example.org\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="unsupported source type"):
        load_commons_catalog(path)


@pytest.mark.parametrize(
    ("source_type", "field"),
    [
        ("path", "uri"),
        ("git", "uri"),
        ("github", "repo"),
        ("zenodo", "doi"),
    ],
)
def test_load_commons_catalog_rejects_missing_required_source_fields(
    tmp_path: Path,
    source_type: str,
    field: str,
) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\n"
        "sources:\n"
        "  bad:\n"
        f"    type: {source_type}\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match=f"{source_type} source 'bad' requires {field!r}"):
        load_commons_catalog(path)


def test_load_commons_catalog_missing_file_returns_empty_catalog(tmp_path: Path) -> None:
    assert load_commons_catalog(tmp_path / "commons.yaml") == CommonsCatalog(catalog_version=1, sources={})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_catalog.py -q
```

Expected: FAIL because `science_tool.commons.catalog` does not exist.

- [ ] **Step 3: Implement catalog parser**

Create `science/src/science_tool/commons/catalog.py`:

```python
"""Remote-ready commons catalog metadata parser.

V1 parses and validates source declarations only. It does not fetch or update
remote catalogs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

SourceType = Literal["path", "git", "github", "zenodo"]
_SOURCE_TYPES = {"path", "git", "github", "zenodo"}
_REQUIRED_FIELD_BY_TYPE: dict[SourceType, str] = {
    "path": "uri",
    "git": "uri",
    "github": "repo",
    "zenodo": "doi",
}


class CatalogError(ValueError):
    """Raised when commons.yaml is malformed."""


@dataclass(frozen=True, slots=True)
class CatalogSource:
    type: SourceType
    uri: str | None = None
    repo: str | None = None
    doi: str | None = None


@dataclass(frozen=True, slots=True)
class CommonsCatalog:
    catalog_version: int
    sources: dict[str, CatalogSource]


def load_commons_catalog(path: Path) -> CommonsCatalog:
    if not path.exists():
        return CommonsCatalog(catalog_version=1, sources={})
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise CatalogError(f"{path}: expected mapping")
    version = raw.get("catalog_version", 1)
    if version != 1:
        raise CatalogError(f"{path}: catalog_version must be 1")
    raw_sources = raw.get("sources", {})
    if not isinstance(raw_sources, dict):
        raise CatalogError(f"{path}: sources must be a mapping")
    sources: dict[str, CatalogSource] = {}
    for name, entry in raw_sources.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise CatalogError(f"{path}: source entries must be mappings keyed by name")
        source_type_raw = entry.get("type")
        if not isinstance(source_type_raw, str) or source_type_raw not in _SOURCE_TYPES:
            raise CatalogError(f"{path}: unsupported source type {source_type_raw!r} for {name!r}")
        source_type = cast(SourceType, source_type_raw)
        required_field = _REQUIRED_FIELD_BY_TYPE[source_type]
        if not isinstance(entry.get(required_field), str) or not entry[required_field]:
            raise CatalogError(f"{path}: {source_type} source {name!r} requires {required_field!r}")
        sources[name] = CatalogSource(
            type=source_type,
            uri=entry.get("uri") if isinstance(entry.get("uri"), str) else None,
            repo=entry.get("repo") if isinstance(entry.get("repo"), str) else None,
            doi=entry.get("doi") if isinstance(entry.get("doi"), str) else None,
        )
    return CommonsCatalog(catalog_version=1, sources=sources)
```

- [ ] **Step 4: Run catalog tests**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_catalog.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/src/science_tool/commons/catalog.py science/tests/test_commons_catalog.py
rtk git commit -m "feat: parse commons catalog sources"
```

---

### Task 7: Shared `find` Staleness Regression

**Files:**
- Modify: `science/tests/test_commons_cli.py`
- Modify only if needed: `science/src/science_tool/commons/query.py`

- [ ] **Step 1: Add a regression test for global `find` stale warnings**

Append to `science/tests/test_commons_cli.py`:

```python
def test_find_warns_on_stale_registry_for_all_entity_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.delenv("SCIENCE_COMMONS_QUIET_STALE", raising=False)
    runner = CliRunner()
    rebuild = runner.invoke(commons_group, ["index", "rebuild"])
    assert rebuild.exit_code == 0, rebuild.output

    paper = root / "papers" / "Adams2025.md"
    paper.write_text(paper.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = runner.invoke(commons_group, ["find", "paper"])

    assert result.exit_code == 0, result.output
    assert "warning: commons registry is stale" in result.stderr
```

- [ ] **Step 2: Run the regression test**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest tests/test_commons_cli.py::test_find_warns_on_stale_registry_for_all_entity_types -q
```

Expected: PASS. Existing `CommonsQuery.find()` calls `_warn_if_stale()` after requiring the registry, and the warning is not scoped to dataset records.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add science/tests/test_commons_cli.py
rtk git commit -m "test: cover commons find stale warning"
```

---

### Task 8: User Guide Update

**Files:**
- Modify: `docs/user-guide/cross-project-work.md`
- Test: docs-only review commands

- [ ] **Step 1: Add commons-born lifecycle documentation**

In `docs/user-guide/cross-project-work.md`, add a section near the existing commons root/data-root discussion:

~~~markdown
## Commons-Born Dataset Packages

Reusable reference wrappers can start directly in commons instead of being
promoted from a project:

```bash
science commons dataset init <slug>
science commons dataset build <slug>
science commons dataset validate <slug>
science commons dataset status <slug> --json
```

`science commons init` initializes the commons store. `science commons dataset
init <slug>` initializes one dataset package under `datasets/<slug>/`.

Every commons-born dataset package has a tracked `recipe/Snakefile`.
`science commons dataset build <slug>` runs that workflow and passes standard
commons roots, including the per-dataset output directory. The workflow owns
downloads, source lockfiles, generated payloads, summaries, and datapackage hash
refreshes.

Tracked package metadata and recipes live under `~/d/science-commons/datasets/<slug>/`.
Generated payload bytes live under `$SCIENCE_COMMONS_DATA_ROOT/<slug>/` unless
`~/.config/science/data.yaml` maps the slug to a machine-local override such as
`~/d/science-commons-data/<slug>/`.

Projects continue to reference commons datasets by id, for example
`dataset:<slug>`. Project-local dependency locks and remote pulls are reserved
for a later package-manager phase.
~~~

- [ ] **Step 2: Check for formatting issues**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk rg -n "Commons-Born Dataset Packages|science commons dataset init|science commons init" docs/user-guide/cross-project-work.md
rtk git diff --check
```

Expected: `rg` finds the new section and `git diff --check` prints no errors.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git add docs/user-guide/cross-project-work.md
rtk git commit -m "docs: describe commons-born dataset lifecycle"
```

---

### Task 9: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest \
  tests/test_commons_dataset_lifecycle.py \
  tests/test_commons_cli_dataset.py \
  tests/test_commons_catalog.py \
  tests/test_commons_cli.py::test_find_warns_on_stale_registry_for_all_entity_types \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run existing commons regressions**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen pytest \
  tests/test_commons_cli.py \
  tests/test_commons_cli_data.py \
  tests/test_commons_public_api.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run static checks**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle/science
rtk uv run --frozen ruff check src/science_tool/commons tests/test_commons_dataset_lifecycle.py tests/test_commons_cli_dataset.py tests/test_commons_catalog.py
rtk uv run --frozen pyright src/science_tool/commons
```

Expected: PASS.

- [ ] **Step 4: Check git status**

Run:

```bash
cd ~/d/science/.worktrees/commons-born-dataset-lifecycle
rtk git status --short
```

Expected: clean worktree.

---

## Design Coverage Checklist

- Local-first lifecycle commands: Tasks 2, 3, 4, 5.
- Required `recipe/Snakefile`: Tasks 1, 4, 5.
- Snakemake-only build boundary: Task 5.
- Existing `find` instead of new `search`: Task 7.
- Existing data-root and `data.yaml` override resolution: Tasks 1, 3, 5.
- Wrapper-version semantics: Tasks 1 and 4 via scaffold/validation.
- Tracked payload file policy using data-audit SSOT: Task 4.
- `status --json`: Task 3.
- YAML commons datapackage path: Tasks 1, 3, 4.
- Store-level `commons init` vs package-level `dataset init`: Tasks 2 and 8.
- Remote-ready catalog source model without remote execution: Task 6.
