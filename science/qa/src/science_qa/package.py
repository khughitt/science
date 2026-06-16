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
