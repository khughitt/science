"""Local-first lifecycle helpers for commons-born dataset packages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from science_tool.commons.config import load_data_overrides, resolve_commons_data_root


_DATASET_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_DATASET_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class DatasetLifecycleError(ValueError):
    """Raised when a commons dataset lifecycle operation is invalid."""


@dataclass(frozen=True, slots=True)
class DatasetPackagePaths:
    dataset_dir: Path
    entity_path: Path
    datapackage_path: Path
    snakefile_path: Path
    readme_path: Path


@dataclass(frozen=True, slots=True)
class ScaffoldResult:
    paths: DatasetPackagePaths
    created: tuple[Path, ...]


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


def validate_dataset_slug(slug: str) -> str:
    if not _DATASET_SLUG_RE.fullmatch(slug):
        raise DatasetLifecycleError(
            "dataset slug must use lowercase letters, digits, and hyphens, "
            "and must start and end with a letter or digit"
        )
    return slug


def validate_dataset_version(version: str) -> str:
    if not _DATASET_VERSION_RE.fullmatch(version):
        raise DatasetLifecycleError("dataset version must be semver MAJOR.MINOR.PATCH")
    return version


def dataset_paths(commons_root: Path, slug: str) -> DatasetPackagePaths:
    slug = validate_dataset_slug(slug)
    dataset_dir = Path(commons_root) / "datasets" / slug
    recipe_dir = dataset_dir / "recipe"
    return DatasetPackagePaths(
        dataset_dir=dataset_dir,
        entity_path=dataset_dir / "entity.md",
        datapackage_path=dataset_dir / "datapackage.yaml",
        snakefile_path=recipe_dir / "Snakefile",
        readme_path=recipe_dir / "README.md",
    )


def resolve_dataset_output_dir(slug: str, data_root: Path | None = None) -> Path:
    slug = validate_dataset_slug(slug)
    override = load_data_overrides().get(slug)
    if override is not None:
        return override
    if data_root is not None:
        return Path(data_root) / slug
    return resolve_commons_data_root() / slug


def dataset_status(commons_root: Path, slug: str) -> DatasetStatus:
    slug = validate_dataset_slug(slug)
    paths = dataset_paths(Path(commons_root), slug)
    output_dir = resolve_dataset_output_dir(slug)
    resources = _read_datapackage_resources(paths.datapackage_path)
    outputs_present: list[str] = []
    outputs_missing: list[str] = []

    for resource in resources:
        resource_path = resource.get("path")
        if not isinstance(resource_path, str):
            continue
        if (output_dir / resource_path).is_file():
            outputs_present.append(resource_path)
        else:
            outputs_missing.append(resource_path)

    return DatasetStatus(
        slug=slug,
        exists=paths.dataset_dir.is_dir(),
        dataset_dir=paths.dataset_dir,
        workflow_exists=paths.snakefile_path.is_file(),
        lockfile_exists=(paths.snakefile_path.parent / "lockfile.yaml").is_file(),
        datapackage_exists=paths.datapackage_path.is_file(),
        datapackage_placeholder_hashes=any(
            _is_placeholder_resource(resource) for resource in resources
        ),
        output_dir=output_dir,
        outputs_present=outputs_present,
        outputs_missing=outputs_missing,
    )


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
    paths = dataset_paths(Path(commons_root), slug)
    if paths.dataset_dir.exists():
        raise DatasetLifecycleError(
            f"dataset {slug!r} already exists at {paths.dataset_dir}"
        )

    paths.snakefile_path.parent.mkdir(parents=True)
    created_date = today or date.today().isoformat()
    dataset_title = title or slug

    files = (
        (paths.entity_path, _entity_text(slug, dataset_title, version, created_date)),
        (paths.datapackage_path, _datapackage_text(slug)),
        (paths.snakefile_path, _snakefile_text(slug)),
        (paths.readme_path, _readme_text(slug)),
    )
    for path, text in files:
        path.write_text(text, encoding="utf-8")

    return ScaffoldResult(paths=paths, created=tuple(path for path, _ in files))


def _read_datapackage_resources(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(raw, dict):
        return []
    resources = raw.get("resources")
    if not isinstance(resources, list):
        return []
    return [resource for resource in resources if isinstance(resource, dict)]


def _is_placeholder_resource(resource: dict[str, object]) -> bool:
    return (
        resource.get("hash") == f"sha256:{'0' * 64}"
        or resource.get("bytes") == 0
    )


def _entity_text(slug: str, title: str, version: str, today: str) -> str:
    yaml_title = yaml.safe_dump(title, default_style='"').strip()
    yaml_today = yaml.safe_dump(today, default_style='"').strip()
    return f"""---
schema_profile: science-entity-base/1.0+dataset/1.0
id: dataset:{slug}
type: dataset
title: {yaml_title}
version: "{version}"
created: {yaml_today}
updated: {yaml_today}
status: active
origin: external
source_class: reference
tier: track
access:
  level: public
  availability: available
  verified: false
datapackage: datapackage.yaml
---

Commons-born dataset package scaffold.
"""


def _datapackage_text(slug: str) -> str:
    return yaml.safe_dump(
        {"name": slug, "profile": "data-package", "resources": []},
        sort_keys=False,
    )


def _snakefile_text(slug: str) -> str:
    return f"""from pathlib import Path


DATASET_SLUG = "{slug}"

if "dataset_output_dir" not in config:
    raise ValueError("dataset_output_dir is required")

DATASET_OUTPUT_DIR = Path(config["dataset_output_dir"])


rule all:
    input: []
"""


def _readme_text(slug: str) -> str:
    return f"""# {slug} recipe

Run this dataset with:

```bash
science commons dataset build {slug}
```

Write generated outputs under the configured `dataset_output_dir`. Do not
reconstruct `output_root/{slug}` in this recipe because `data.yaml` overrides
can point dataset outputs outside the default commons data root.
"""
