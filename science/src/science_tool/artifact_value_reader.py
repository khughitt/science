"""Typed, symlink-safe artifact resolver (Part B of the numeric-provenance redesign).

`resolve_artifact` turns an artifact reference string into a `ResolvedArtifact`
(a real regular file under `project_root` or `data_root`, canonicalized) or an
`ArtifactError`. It is a security-sensitive path resolver: absolute paths and
`..` traversal are rejected up front, symlinks that escape the chosen root are
rejected after `realpath` resolution, and ambiguity is judged on canonicalized
paths (not raw candidate strings) so that `project_root == data_root` never
produces a false ambiguity.

See docs/plans/2026-07-18-numeric-provenance-check-design.md (Part B).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

_JSON_KIND = "json"
_FEATHER_KIND = "feather"
_OPAQUE_KIND = "opaque"

_KIND_BY_SUFFIX = {
    ".json": _JSON_KIND,
    ".feather": _FEATHER_KIND,
}


@dataclass(frozen=True)
class ResolvedArtifact:
    path: Path
    kind: str  # "json" | "feather" | "opaque"


@dataclass(frozen=True)
class ArtifactError:
    detail: str


def resolve_artifact(
    ref: str,
    project_root: Path,
    data_root: Path,
    *,
    max_json_bytes: int,
    max_feather_bytes: int,
    content: bool = True,
) -> ResolvedArtifact | ArtifactError:
    # Reject non-relative paths outright: `Path(base) / ref` silently discards
    # `base` when `ref` is absolute, and `..` segments can escape the chosen
    # root — a fabricated/malicious absolute or traversal ref must never
    # resolve. Mirrors the guard in `ResolutionIndex.resolve`
    # (numeric_provenance.py:224).
    candidate = Path(ref)
    if candidate.is_absolute() or ".." in candidate.parts:
        return ArtifactError(detail=f"artifact reference rejected (absolute or traversal): {ref!r}")

    # Collect the containing resolved path for each root that actually
    # contains a resolvable file, then dedupe by the canonical resolved Path
    # so equal/overlapping roots collapse to a single candidate rather than a
    # false ambiguity.
    resolved_candidates: dict[Path, Path] = {}
    for base in (project_root, data_root):
        raw = base / ref
        if not raw.exists():
            continue
        try:
            real = raw.resolve(strict=True)
        except OSError:
            # Intentional fail-closed swallow: resolution can raise for a
            # broken symlink, a permission error, or a same-instant removal.
            # Treat it as "missing/inaccessible under this root" and try the
            # next root, rather than surfacing the exception.
            continue
        resolved_candidates.setdefault(real, base.resolve())

    if not resolved_candidates:
        return ArtifactError(detail=f"artifact not found under project_root or data_root: {ref!r}")
    if len(resolved_candidates) >= 2:
        return ArtifactError(detail=f"artifact reference is ambiguous across roots: {ref!r}")

    (real,) = resolved_candidates.keys()
    (chosen_root,) = resolved_candidates.values()

    if not real.is_relative_to(chosen_root):
        return ArtifactError(detail=f"artifact escapes its root via symlink: {ref!r}")
    if not real.is_file():
        return ArtifactError(detail=f"artifact is not a regular file: {ref!r}")

    if not content:
        return ResolvedArtifact(path=real, kind=_OPAQUE_KIND)

    kind = _KIND_BY_SUFFIX.get(real.suffix)
    if kind is None:
        return ArtifactError(detail=f"artifact has unsupported extension for content read: {ref!r}")

    size = real.stat().st_size
    cap = max_json_bytes if kind == _JSON_KIND else max_feather_bytes
    if size > cap:
        return ArtifactError(detail=f"artifact exceeds size cap for kind {kind!r}: {ref!r} ({size} > {cap})")

    return ResolvedArtifact(path=real, kind=kind)


@dataclass(frozen=True)
class ReaderError:
    detail: str


# RFC-6901 pointer path-segment tokens are unescaped ~1 -> "/" then ~0 -> "~",
# in that order (escaping ~0 first would turn a literal "~1" in the source
# key into "/" instead of leaving it as "~1"-decoded-to-"~1"). A segment
# indexing into a list must be "0" or a non-zero digit run (no leading
# zeros, no sign) per the spec; anything else is treated as a miss rather
# than silently truncated/parsed leniently.
_LIST_INDEX_RE = re.compile(r"0|[1-9][0-9]*")


class _NonFiniteLiteral(Exception):
    """Raised by `_reject_nonfinite` when json.load hits NaN/Infinity/-Infinity."""


def _reject_nonfinite(literal: str) -> Any:
    raise _NonFiniteLiteral(f"non-finite JSON literal is not a valid numeric scalar: {literal!r}")


def _unescape_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _json_pointer(doc: Any, pointer: str) -> Any:
    """Resolve an RFC-6901 JSON pointer against `doc`.

    Raises `LookupError` (or a subclass) or `TypeError` on any miss --
    unknown key, out-of-range/malformed list index, or indexing through a
    scalar. The empty-string pointer resolves to the whole document.
    """
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise LookupError(f"JSON pointer must start with '/' or be empty: {pointer!r}")

    node = doc
    for raw_token in pointer.split("/")[1:]:
        token = _unescape_pointer_token(raw_token)
        if isinstance(node, list):
            if _LIST_INDEX_RE.fullmatch(token) is None:
                raise LookupError(f"not a valid list index token: {token!r}")
            index = int(token)
            if index >= len(node):
                raise IndexError(f"list index out of range: {index}")
            node = node[index]
        elif isinstance(node, dict):
            if token not in node:
                raise KeyError(token)
            node = node[token]
        else:
            raise TypeError(f"cannot index into a non-container node with token {token!r}")
    return node


def read_scalar(resolved: ResolvedArtifact, locator: Any) -> Decimal | ReaderError:
    """Read a single numeric scalar out of a resolved JSON or feather artifact.

    JSON reads parse straight to `Decimal` (no `float` in the path, so full
    literal fidelity is preserved) and resolve an RFC-6901 pointer to
    exactly one numeric-scalar node. Feather reads column-select the union
    of the value column and any `where` filter columns, apply an equality
    filter, require exactly one surviving row, and convert the cell to
    `Decimal` via `str()`.
    """
    if resolved.kind == _JSON_KIND:
        return _read_json_scalar(resolved.path, locator)
    if resolved.kind == _FEATHER_KIND:
        return _read_feather_scalar(resolved.path, locator)
    return ReaderError(detail=f"unsupported artifact kind for scalar read: {resolved.kind!r}")


def _read_json_scalar(path: Path, locator: Any) -> Decimal | ReaderError:
    pointer = getattr(locator, "pointer", None)
    if pointer is None:
        return ReaderError(detail=f"json artifact requires a PointerLocator, got {type(locator).__name__}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            doc = json.load(
                fh,
                parse_float=Decimal,
                parse_int=Decimal,
                parse_constant=_reject_nonfinite,
            )
    except _NonFiniteLiteral as exc:
        return ReaderError(detail=str(exc))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        return ReaderError(detail=f"failed to parse JSON artifact {path}: {exc}")

    try:
        node = _json_pointer(doc, pointer)
    except (LookupError, TypeError) as exc:
        return ReaderError(detail=f"JSON pointer {pointer!r} did not resolve in {path}: {exc}")

    # JSON true/false decode straight to Python bool (never routed through
    # parse_int/parse_float, so never a Decimal) -- reject explicitly rather
    # than relying on that, since bool is a subclass of int and a naive
    # `isinstance(node, (int, float, Decimal))` check would silently admit it.
    if isinstance(node, bool):
        return ReaderError(detail=f"JSON pointer {pointer!r} resolved to a bool, not a numeric scalar")
    if isinstance(node, Decimal):
        return node
    return ReaderError(
        detail=f"JSON pointer {pointer!r} resolved to a non-numeric node ({type(node).__name__}): {node!r}"
    )


def _read_feather_scalar(path: Path, locator: Any) -> Decimal | ReaderError:
    column = getattr(locator, "column", None)
    if column is None:
        return ReaderError(detail=f"feather artifact requires a ColumnLocator, got {type(locator).__name__}")
    where: dict[str, Any] = getattr(locator, "where", None) or {}

    # Load the union of [column] + where.keys() -- the where-filter columns
    # must be present in the frame to filter on, even though only `column`
    # is ultimately extracted.
    cols = [column] + [k for k in where if k != column]
    try:
        frame = pd.read_feather(path, columns=cols)
    except Exception as exc:  # pyarrow raises its own error types for a missing column
        return ReaderError(detail=f"failed to read feather columns {cols!r} from {path}: {exc}")

    for key, expected in where.items():
        frame = frame[frame[key] == expected]

    if len(frame) != 1:
        return ReaderError(
            detail=f"expected exactly one matching row in {path} for where={where!r}, got {len(frame)}"
        )

    cell = frame[column].iloc[0]
    value = cell.item() if hasattr(cell, "item") else cell

    if isinstance(value, bool):
        return ReaderError(detail=f"feather column {column!r} cell is a bool, not a numeric scalar")
    if isinstance(value, float) and not math.isfinite(value):
        return ReaderError(detail=f"feather column {column!r} cell is non-finite (NaN/inf): {value!r}")
    try:
        return Decimal(str(value))
    except Exception as exc:
        return ReaderError(detail=f"feather column {column!r} cell {value!r} is not a numeric scalar: {exc}")
