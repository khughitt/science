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

from dataclasses import dataclass
from pathlib import Path

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
