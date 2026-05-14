"""Commons-store configuration: settings model + root resolvers."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

from science_tool.commons.errors import CommonsError


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


def load_data_overrides() -> dict[str, Path]:
    """Load the per-machine data-override map from `~/.config/science/data.yaml`.

    Maps `<dataset-slug>` to an absolute directory. Returns `{}` if the file is
    missing. Raises `CommonsError` if the file exists but is malformed YAML, is
    not a mapping, or maps a string slug to anything other than an absolute-path
    string.
    """
    from science_tool.registry.config import get_science_config_dir

    overrides_path = get_science_config_dir() / "data.yaml"
    if not overrides_path.is_file():
        return {}

    try:
        text = overrides_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommonsError(f"{overrides_path}: cannot read data overrides: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CommonsError(f"{overrides_path}: malformed YAML: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CommonsError(
            f"{overrides_path}: expected a mapping of slug -> absolute path"
        )

    result: dict[str, Path] = {}
    for slug, value in raw.items():
        if not isinstance(slug, str) or not isinstance(value, str):
            raise CommonsError(
                f"{overrides_path}: entry {slug!r} -> {value!r} must be "
                f"a string slug mapped to a string path"
            )
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise CommonsError(
                f"{overrides_path}: override for {slug!r} must be an absolute "
                f"path, got {value!r}"
            )
        result[slug] = path
    return result
