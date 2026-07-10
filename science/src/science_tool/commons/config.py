"""Commons-store configuration: settings model + root resolvers."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel

from science_tool.commons.errors import (
    CommonsError,
    ProjectNotRegisteredError,
    PromoteOverrideConflictError,
)


class CommonsSettings(BaseModel):
    """Settings for the shared knowledge store."""

    root: Path | None = None  # None means "use built-in default"
    data_root: Path | None = None  # None means "use built-in default"


def resolve_commons_root() -> Path:
    """Resolve the commons store root.

    Discovery order:
    1. `$SCIENCE_COMMONS_ROOT` environment variable.
    2. `commons.root` in the global config file.
    3. Default: `~/d/science-commons/`.
    """
    if env := os.environ.get("SCIENCE_COMMONS_ROOT"):
        return Path(env).expanduser()

    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    if cfg.commons.root is not None:
        return Path(cfg.commons.root).expanduser()

    return Path.home() / "d" / "science-commons"


def resolve_commons_data_root() -> Path:
    """Resolve the bulk-data root for commons datasets.

    Discovery order:
    1. `$SCIENCE_COMMONS_DATA_ROOT` environment variable.
    2. `commons.data_root` in the global config file.
    3. Default: `/data/science-commons/`.

    Note: like the Phase B `resolve_commons_root()`, this does not assert that
    the env/config value is absolute — a relative value resolves against the
    process CWD, and the built-in default is absolute. Only the per-machine
    `data.yaml` override values are required to be absolute (a relative entry
    there is almost certainly a user mistake; see `load_data_overrides`).
    """
    if env := os.environ.get("SCIENCE_COMMONS_DATA_ROOT"):
        return Path(env).expanduser()

    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    if cfg.commons.data_root is not None:
        return Path(cfg.commons.data_root).expanduser()

    return Path("/data/science-commons")


def _data_yaml_path() -> Path:
    """Return the per-machine data override config path."""
    from science_tool.registry.config import get_science_config_dir

    return get_science_config_dir() / "data.yaml"


def load_data_overrides() -> dict[str, Path]:
    """Load the per-machine data-override map from `~/.config/science/data.yaml`.

    Maps `<dataset-slug>` to an absolute directory. Returns `{}` if the file is
    missing. Raises `CommonsError` if the file exists but is malformed YAML, is
    not a mapping, or maps a string slug to anything other than an absolute-path
    string.
    """
    overrides_path = _data_yaml_path()
    return {
        slug: Path(value).expanduser()
        for slug, value in _load_data_yaml_mapping(overrides_path).items()
    }


def _load_data_yaml_mapping(yaml_path: Path) -> dict[str, str]:
    if not yaml_path.exists():
        return {}
    if not yaml_path.is_file():
        raise CommonsError(f"{yaml_path}: expected a file")
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommonsError(f"{yaml_path}: cannot read data overrides: {exc}") from exc
    if not text.strip():
        return {}
    try:
        node = yaml.compose(text)
        if isinstance(node, yaml.MappingNode):
            seen_keys: set[str] = set()
            for key_node, _ in node.value:
                if not isinstance(key_node, yaml.ScalarNode):
                    raise CommonsError(
                        f"{yaml_path}: data override keys must be strings"
                    )
                key = key_node.value
                if key in seen_keys:
                    raise CommonsError(f"{yaml_path}: duplicate key {key!r}")
                seen_keys.add(key)
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CommonsError(f"{yaml_path}: malformed YAML: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CommonsError(f"{yaml_path}: expected a mapping of slug -> absolute path")

    result: dict[str, str] = {}
    for slug, value in raw.items():
        if not isinstance(slug, str) or not isinstance(value, str):
            raise CommonsError(
                f"{yaml_path}: entry {slug!r} -> {value!r} must be "
                f"a string slug mapped to a string path"
            )
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise CommonsError(
                f"{yaml_path}: override for {slug!r} must be an absolute "
                f"path, got {value!r}"
            )
        result[slug] = value
    return result


def upsert_data_override(*, slug: str, absolute_path: Path, op_id: str) -> Path:
    """Atomically upsert a per-machine dataset data override."""
    return _upsert_data_override(
        slug=slug,
        absolute_path=absolute_path,
        op_id=op_id,
        allow_existing_backup=False,
    )


def _upsert_data_override(
    *,
    slug: str,
    absolute_path: Path,
    op_id: str,
    allow_existing_backup: bool,
) -> Path:
    """Implementation shared by one-shot and same-operation batch upserts."""
    if not absolute_path.is_absolute():
        raise CommonsError(f"data override path must be absolute, got {absolute_path}")

    yaml_path = _data_yaml_path()
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = yaml_path.parent / f"data.yaml.bak.{op_id}"
    absent_sentinel_path = yaml_path.parent / f"data.yaml.bak.{op_id}.absent"
    backup_exists = backup_path.exists()
    sentinel_exists = absent_sentinel_path.exists()
    if backup_exists and sentinel_exists:
        raise CommonsError(
            f"ambiguous data override backup state for op_id {op_id!r}"
        )
    if (backup_exists or sentinel_exists) and not allow_existing_backup:
        raise CommonsError(
            f"data override backup already exists for op_id {op_id!r}"
        )

    existing = _load_data_yaml_mapping(yaml_path)

    if not (backup_exists or sentinel_exists):
        if yaml_path.is_file():
            shutil.copyfile(yaml_path, backup_path)
        else:
            absent_sentinel_path.write_text("", encoding="utf-8")

    existing[slug] = str(absolute_path)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=yaml_path.parent,
            prefix="data.yaml.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            yaml.safe_dump(existing, temp_file, sort_keys=True)
        os.replace(temp_name, yaml_path)
    finally:
        if temp_name is not None:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()

    return backup_path


def check_override_conflict(*, slug: str, planned_path: Path) -> None:
    """Raise if `data.yaml` already maps `slug` to a different path."""
    existing = _load_data_yaml_mapping(_data_yaml_path()).get(slug)
    if existing is None:
        return
    existing_path = Path(existing).expanduser()
    if existing_path.resolve(strict=False) != planned_path.expanduser().resolve(
        strict=False
    ):
        raise PromoteOverrideConflictError(
            slug=slug,
            existing_path=existing_path,
            planned_path=planned_path,
        )


def restore_data_override_from_backup(*, op_id: str) -> None:
    """Restore `data.yaml` from the backup written for `op_id`."""
    yaml_path = _data_yaml_path()
    backup_path = yaml_path.parent / f"data.yaml.bak.{op_id}"
    absent_sentinel_path = yaml_path.parent / f"data.yaml.bak.{op_id}.absent"

    if backup_path.is_file() and absent_sentinel_path.is_file():
        raise CommonsError(
            f"ambiguous data override backup state for op_id {op_id!r}"
        )
    if absent_sentinel_path.is_file():
        if yaml_path.exists():
            if not yaml_path.is_file():
                raise CommonsError(f"{yaml_path}: expected a file")
            yaml_path.unlink()
        absent_sentinel_path.unlink()
        return

    if not backup_path.is_file():
        raise CommonsError(f"backup not found: {backup_path}")
    os.replace(backup_path, yaml_path)


def registry_root_for_name(name: str) -> Path:
    """Look up a registered project by name and return its root path.

    Reads `projects[]` from the global config. Raises ProjectNotRegisteredError
    if no entry matches `name`. Does not assert the path exists on disk - that
    is checked by callers (resolve_entity / validate_project_overlays), which
    raise ProjectDirectoryMissingError instead.
    """
    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    for project in cfg.projects:
        if project.name == name:
            return Path(project.path).expanduser()
    # Fall back to id so the same identifier works with both validate --project
    # (name) and promote --from (id) (fb-2026-05-29-003). Name takes precedence.
    for project in cfg.projects:
        if project.id == name:
            return Path(project.path).expanduser()
    raise ProjectNotRegisteredError(name)


def registry_root_for_id(project_id: str) -> Path:
    """Look up a registered project by `id:` (not `name:`) and return its root path.

    Reads `projects[]` from the global config. Distinguishes three failure modes:

    - id is null on a matching entry → CommonsError("id is null") — caller (promote)
      maps this to "this registration has no id; assign one or deregister"
    - more than one entry shares the id → CommonsError("ambiguous") — project ids
      must be unique; silently picking the first would promote the wrong corpus
    - no entry matches the given id → CommonsError("no registered project with id")
    - all good → return the path (expanded `~`).

    Used by `science commons promote --from <id>` to enforce the id-based
    `--from` contract. The legacy `registry_root_for_name(name)` matches by name and
    is left alone for callers that still want name-based lookup.
    """
    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    matches = [project for project in cfg.projects if project.id == project_id]
    if len(matches) > 1:
        paths = ", ".join(str(project.path) for project in matches)
        raise CommonsError(
            f"project id {project_id!r} is ambiguous: {len(matches)} registered "
            f"projects share it ({paths}). Project ids must be unique — "
            "disambiguate them in ~/.config/science/config.yaml before promoting."
        )
    if matches:
        return Path(matches[0].path).expanduser()
    # No match by id; check whether any registration uses the same name and
    # has a null id, which is the legacy-registration failure mode we want
    # to diagnose specifically.
    for project in cfg.projects:
        if project.name == project_id and project.id is None:
            raise CommonsError(
                f"project {project_id!r} has id: null; assign an id "
                "in ~/.config/science/config.yaml or deregister the entry"
            )
    # Fall back to name so the same identifier works with both promote --from
    # (id) and validate --project (name) (fb-2026-05-29-003). Id takes precedence;
    # the null-id diagnostic above still fires first for legacy registrations.
    for project in cfg.projects:
        if project.name == project_id:
            return Path(project.path).expanduser()
    raise CommonsError(f"no registered project with id {project_id!r}")
