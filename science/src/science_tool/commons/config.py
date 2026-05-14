"""Commons-store configuration: settings model + root resolver."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class CommonsSettings(BaseModel):
    """Settings for the shared knowledge store."""

    root: Path | None = None  # None means "use built-in default"


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
