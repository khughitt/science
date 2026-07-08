"""Local-first lifecycle helpers for commons-born dataset packages."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import load_data_overrides, resolve_commons_data_root
from science_tool.commons.datapackage import (
    parse_resource_hash,
    validate_logical_path,
    validate_source,
)
from science_tool.commons.errors import (
    CommonsError,
    CommonsEntityError,
    CommonsLayoutError,
    DataLogicalPathError,
)
from science_tool.data_policy import DEFAULT_DATA_POLICY, FileClass, classify
from science_tool.identity_authoring import (
    BASE_DATASET_SCHEMA_PROFILE,
    IdentityAuthoringError,
    require_profile_identity,
)
from science_tool.markdown_utils import parse_frontmatter


_DATASET_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_DATASET_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class DatasetLifecycleError(ValueError):
    """Raised when a commons dataset lifecycle operation is invalid."""


BuildRunner = Callable[[list[str]], int]


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


def snakemake_build_command(commons_root: Path, slug: str, *, cores: int = 1) -> list[str]:
    slug = validate_dataset_slug(slug)
    paths = dataset_paths(Path(commons_root), slug)
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


def validate_dataset_package(commons_root: Path, slug: str) -> DatasetPackageValidationReport:
    slug = validate_dataset_slug(slug)
    root = Path(commons_root)
    paths = dataset_paths(root, slug)
    findings: list[DatasetPackageFinding] = []

    if not paths.entity_path.is_file():
        findings.append(
            DatasetPackageFinding(
                "missing-entity",
                "dataset package is missing entity.md",
                paths.entity_path,
            )
        )
        frontmatter: dict[str, Any] = {}
    else:
        frontmatter, _ = parse_frontmatter(paths.entity_path)
        _validate_entity_frontmatter(findings, paths, slug, frontmatter)

    if not paths.datapackage_path.is_file():
        findings.append(
            DatasetPackageFinding(
                "missing-datapackage",
                "dataset package is missing datapackage.yaml",
                paths.datapackage_path,
            )
        )
    else:
        try:
            _validate_datapackage_shape(paths.datapackage_path)
            _validate_declared_resource_state(findings, paths.datapackage_path, slug)
        except DatasetLifecycleError as exc:
            findings.append(
                DatasetPackageFinding(
                    "datapackage-invalid",
                    str(exc),
                    paths.datapackage_path,
                )
            )

    if not paths.snakefile_path.is_file():
        findings.append(
            DatasetPackageFinding(
                "missing-workflow",
                "dataset package is missing recipe/Snakefile",
                paths.snakefile_path,
            )
        )
    else:
        _validate_snakefile_paths(findings, paths.snakefile_path)

    if paths.entity_path.is_file() and paths.datapackage_path.is_file():
        try:
            CommonsEntityAdapter(root).load(f"dataset:{slug}")
        except CommonsEntityError as exc:
            findings.append(
                DatasetPackageFinding(
                    "entity-invalid",
                    str(exc.cause),
                    exc.path,
                )
            )
        except CommonsLayoutError as exc:
            findings.append(
                DatasetPackageFinding(
                    "entity-invalid",
                    str(exc),
                    exc.path,
                )
            )

    if paths.dataset_dir.is_dir():
        _validate_tracked_payloads(findings, paths.dataset_dir)

    return DatasetPackageValidationReport(
        slug=slug,
        valid=not findings,
        findings=findings,
    )


def scaffold_dataset_package(
    commons_root: Path,
    slug: str,
    *,
    title: str | None = None,
    version: str = "0.1.0",
    schema_profile: str = BASE_DATASET_SCHEMA_PROFILE,
    identity_context: dict[str, Any] | None = None,
    today: str | None = None,
) -> ScaffoldResult:
    slug = validate_dataset_slug(slug)
    version = validate_dataset_version(version)
    paths = dataset_paths(Path(commons_root), slug)
    if paths.dataset_dir.exists():
        raise DatasetLifecycleError(f"dataset {slug!r} already exists at {paths.dataset_dir}")
    identity_context = identity_context or {}
    try:
        require_profile_identity(schema_profile, identity_context)
    except IdentityAuthoringError as exc:
        raise DatasetLifecycleError(str(exc)) from exc

    paths.snakefile_path.parent.mkdir(parents=True)
    created_date = today or date.today().isoformat()
    dataset_title = title or slug

    files = (
        (paths.entity_path, _entity_text(slug, dataset_title, version, created_date, schema_profile, identity_context)),
        (paths.datapackage_path, _datapackage_text(slug)),
        (paths.snakefile_path, _snakefile_text(slug)),
        (paths.readme_path, _readme_text(slug)),
    )
    for path, text in files:
        path.write_text(text, encoding="utf-8")

    return ScaffoldResult(paths=paths, created=tuple(path for path, _ in files))


def _validate_entity_frontmatter(
    findings: list[DatasetPackageFinding],
    paths: DatasetPackagePaths,
    slug: str,
    frontmatter: dict[str, Any],
) -> None:
    entity_id = frontmatter.get("id")
    if entity_id != f"dataset:{slug}":
        findings.append(
            DatasetPackageFinding(
                "id-mismatch",
                f"frontmatter id must be dataset:{slug}",
                paths.entity_path,
            )
        )

    entity_kind = frontmatter.get("kind")
    if entity_kind != "dataset":
        findings.append(
            DatasetPackageFinding(
                "type-mismatch",
                "frontmatter kind must be dataset",
                paths.entity_path,
            )
        )

    version = frontmatter.get("version")
    if version is None:
        findings.append(
            DatasetPackageFinding(
                "missing-version",
                "frontmatter version is required",
                paths.entity_path,
            )
        )
    elif not isinstance(version, str) or not _DATASET_VERSION_RE.fullmatch(version):
        findings.append(
            DatasetPackageFinding(
                "version-invalid",
                "frontmatter version must be semver MAJOR.MINOR.PATCH",
                paths.entity_path,
            )
        )

    datapackage = frontmatter.get("datapackage")
    if datapackage != "datapackage.yaml":
        findings.append(
            DatasetPackageFinding(
                "datapackage-field",
                "frontmatter datapackage must be datapackage.yaml",
                paths.entity_path,
            )
        )


def _validate_snakefile_paths(
    findings: list[DatasetPackageFinding],
    snakefile_path: Path,
) -> None:
    """Flag parent-project data paths in commons recipe Snakefiles.

    This check is commons-recipe-scoped. It does not inspect project workflows
    and intentionally does not flag the commons output layout
    /data/science-commons/<slug>/...
    """
    try:
        text = snakefile_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(
            DatasetPackageFinding(
                "workflow-unreadable",
                str(exc),
                snakefile_path,
            )
        )
        return

    markers = ("/data/proj/", "/data/raw/", "/data/clean/", "/data/processed/")
    for marker in markers:
        if marker in text:
            findings.append(
                DatasetPackageFinding(
                    "parent-project-path",
                    f"recipe/Snakefile references parent project path marker {marker}",
                    snakefile_path,
                )
            )
            return


def _validate_tracked_payloads(
    findings: list[DatasetPackageFinding],
    dataset_dir: Path,
) -> None:
    metadata_paths = {
        Path("entity.md"),
        Path("datapackage.yaml"),
        Path("recipe/Snakefile"),
        Path("recipe/README.md"),
        Path("recipe/lockfile.yaml"),
    }

    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(dataset_dir)
        if rel_path in metadata_paths:
            continue
        size_bytes = path.stat().st_size
        file_class = classify(rel_path, size_bytes)
        if file_class is FileClass.PAYLOAD or (
            file_class is FileClass.FLAG
            and size_bytes > DEFAULT_DATA_POLICY.size_threshold
        ):
            findings.append(
                DatasetPackageFinding(
                    "tracked-payload",
                    "payload-like file is tracked inside the dataset package",
                    path,
                )
            )


def _validate_declared_resource_state(
    findings: list[DatasetPackageFinding],
    datapackage_path: Path,
    slug: str,
) -> None:
    resources = _read_datapackage_resources(datapackage_path)
    if not resources:
        return

    try:
        output_dir = resolve_dataset_output_dir(slug)
    except CommonsError as exc:
        findings.append(
            DatasetPackageFinding(
                "data-root-invalid",
                str(exc),
                datapackage_path,
            )
        )
        return

    for resource in resources:
        resource_path = resource.get("path")
        if not isinstance(resource_path, str):
            continue
        if _is_placeholder_resource(resource):
            findings.append(
                DatasetPackageFinding(
                    "placeholder-resource",
                    f"resource {resource_path!r} still has placeholder hash or byte metadata",
                    datapackage_path,
                )
            )
        output_path = output_dir / validate_logical_path(resource_path)
        if not output_path.is_file():
            findings.append(
                DatasetPackageFinding(
                    "missing-output",
                    f"declared resource output is missing: {resource_path}",
                    output_path,
                )
            )


def _validate_datapackage_shape(path: Path) -> None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DatasetLifecycleError(f"invalid datapackage {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise DatasetLifecycleError(f"invalid datapackage {path}: top-level YAML must be a mapping")

    resources = raw.get("resources")
    if resources is None:
        return
    if not isinstance(resources, list):
        raise DatasetLifecycleError(f"invalid datapackage {path}: resources must be a list")

    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise DatasetLifecycleError(
                f"invalid datapackage {path}: resources[{index}] must be a mapping"
            )
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise DatasetLifecycleError(
                f"invalid datapackage {path}: resources[{index}] has no usable path"
            )
        try:
            logical_path = validate_logical_path(resource_path)
        except DataLogicalPathError as exc:
            raise DatasetLifecycleError(
                f"invalid datapackage {path}: {exc}"
            ) from exc

        resource_hash = resource.get("hash")
        if resource_hash is not None:
            if not isinstance(resource_hash, str):
                raise DatasetLifecycleError(
                    f"invalid datapackage {path}: resource {logical_path!r} hash must be a string"
                )
            try:
                parse_resource_hash(resource_hash)
            except ValueError as exc:
                raise DatasetLifecycleError(
                    f"invalid datapackage {path}: resource {logical_path!r} has malformed hash: {exc}"
                ) from exc

        source = resource.get("source")
        if source is not None:
            try:
                validate_source(source)
            except ValueError as exc:
                raise DatasetLifecycleError(
                    f"invalid datapackage {path}: resource {logical_path!r} has malformed source: {exc}"
                ) from exc


def _read_datapackage_resources(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DatasetLifecycleError(f"invalid datapackage {path}: {exc}") from exc
    if not isinstance(raw, dict):
        return []
    resources = raw.get("resources")
    if not isinstance(resources, list):
        return []

    valid_resources: list[dict[str, object]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        resource_map = cast(dict[str, object], resource)
        resource_path = resource_map.get("path")
        if isinstance(resource_path, str):
            try:
                validate_logical_path(resource_path)
            except DataLogicalPathError as exc:
                raise DatasetLifecycleError(
                    f"invalid datapackage {path}: {exc}"
                ) from exc
        valid_resources.append(resource_map)
    return valid_resources


def _is_placeholder_resource(resource: dict[str, object]) -> bool:
    return (
        resource.get("hash") == f"sha256:{'0' * 64}"
        or resource.get("bytes") == 0
    )


def _entity_text(
    slug: str,
    title: str,
    version: str,
    today: str,
    schema_profile: str,
    identity_context: dict[str, Any],
) -> str:
    schema_profile_text = yaml.safe_dump(
        {"schema_profile": schema_profile},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    yaml_title = yaml.safe_dump(title, default_style='"').strip()
    yaml_today = yaml.safe_dump(today, default_style='"').strip()
    identity_text = ""
    if identity_context:
        identity_text = yaml.safe_dump(
            {"identity_context": identity_context},
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    return f"""---
{schema_profile_text}id: dataset:{slug}
kind: dataset
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
{identity_text}---

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
