"""science datasets infer-schema: a safe schema-authoring scaffold (Spec 3).

Infers a resource's observed shape (field names + coarse Frictionless types) from its
produced table. Emits a diff-vs-existing plus a human review report; with --write applies
ONLY the names+types patch under strict guards. It never infers build-fatal invariants
(constraints, keys, foreignKeys, qa) — those are recommended in the report, authored by a
human. See docs/plans/2026-06-14-infer-schema-scaffold-design.md.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml
from pandas.api import types as pdt
from pydantic import ValidationError

from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues

_DESCRIPTOR_NAMES = ("datapackage.json", "datapackage.yaml", "datapackage.yml")
_FMT_BY_SUFFIX = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


class InferSchemaError(Exception):
    """Any user-facing infer-schema failure (the CLI maps it to a clean error exit)."""


def load_descriptor(path: Path) -> tuple[dict, str]:
    """Load a datapackage descriptor mapping + its format ('json'|'yaml').

    `path` may be the descriptor file or a directory containing one. The descriptor is read
    as a plain mapping (json.load / yaml.safe_load), independent of the commons
    canonical-datapackage parser.
    """
    if path.is_dir():
        for name in _DESCRIPTOR_NAMES:
            candidate = path / name
            if candidate.exists():
                path = candidate
                break
        else:
            raise InferSchemaError(f"no datapackage descriptor found in {path}")
    fmt = _FMT_BY_SUFFIX.get(path.suffix)
    if fmt is None:
        raise InferSchemaError(
            f"unsupported descriptor extension {path.suffix!r} (want .json/.yaml/.yml)"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InferSchemaError(f"cannot read descriptor {path}: {exc}") from exc
    try:
        mapping = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise InferSchemaError(f"malformed {fmt} descriptor {path}: {exc}") from exc
    if not isinstance(mapping, dict):
        raise InferSchemaError(f"descriptor {path} top level is not a mapping")
    return mapping, fmt


def _render_descriptor(mapping: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(mapping, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(mapping, sort_keys=True, default_flow_style=False, allow_unicode=True)


def dump_descriptor(mapping: dict, path: Path, fmt: str) -> None:
    """Atomically write the descriptor, canonically re-rendered in its own format.

    Canonical = sorted keys, deterministic output. Formatting/comments are not preserved.
    """
    text = _render_descriptor(mapping, fmt)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".infer-schema-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def resolve_resource(pkg: dict, resource: str) -> tuple[dict, int]:
    """Resolve `resource` against resources[]: by name first, then by path.

    Ambiguity (a name matching >1 resource, or a path-fallback matching >1 resource) is an
    error — never a silent pick. A name match is primary and short-circuits path matching.
    """
    resources = pkg.get("resources")
    if not isinstance(resources, list) or not resources:
        raise InferSchemaError("descriptor has no resources[] to resolve against")
    by_name = [(i, r) for i, r in enumerate(resources) if r.get("name") == resource]
    if len(by_name) > 1:
        raise InferSchemaError(f"resource name {resource!r} is ambiguous (matches {len(by_name)})")
    if len(by_name) == 1:
        i, r = by_name[0]
        return r, i
    by_path = [(i, r) for i, r in enumerate(resources) if r.get("path") == resource]
    if len(by_path) > 1:
        raise InferSchemaError(f"resource path {resource!r} is ambiguous (matches {len(by_path)})")
    if len(by_path) == 1:
        i, r = by_path[0]
        return r, i
    raise InferSchemaError(f"no resource named or pathed {resource!r} in descriptor")
