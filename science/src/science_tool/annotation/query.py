# science/src/science_tool/annotation/query.py
"""Read-side annotation query module.

Public surface (built up across P3.3 tasks 6–9):
- iter_sidecars(root)        — Task 6 (this file)
- resolve_id(root, id_arg)   — Task 7
- filter_annotations(...)    — Task 8
- compute_stats(sidecars)    — Task 9
- git_changed_markdown(...)  — Task 8

See spec docs/plans/2026-05-11-annotation-system-p3.3-spec.md
§"Read concerns: query.py".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Annotation, Sidecar


# ---- Errors ----------------------------------------------------------

class SidecarParseError(Exception):
    """Raised by iter_sidecars when a sidecar fails to parse.

    Carries the offending file path and the underlying exception so
    the CLI can produce a useful ClickException message.
    """

    def __init__(self, sidecar_path: Path, cause: Exception) -> None:
        self.sidecar_path = sidecar_path
        self.cause = cause
        super().__init__(
            f"failed to parse sidecar {sidecar_path}: "
            f"{type(cause).__name__}: {cause}"
        )


# ---- Single-sidecar read with parse-error wrapping -----------------

def read_sidecar_strict(path: Path) -> Sidecar:
    """Read one sidecar; wrap any parse exception in SidecarParseError.

    Used by every code path in this module that loads a sidecar
    (iter_sidecars, resolve_id qualified lookups, etc.) and by
    cli._scope_to_sidecars when PATH names a single .md or
    .anno.trig file. Centralising the wrap means callers only ever
    need to catch SidecarParseError, not the underlying rdflib /
    ValueError / FileNotFoundError zoo.
    """
    try:
        return read_sidecar(path)
    except Exception as exc:
        raise SidecarParseError(path, exc) from exc


# ---- Walk ------------------------------------------------------------

def iter_sidecars(root: Path) -> Iterator[tuple[Path, Sidecar]]:
    """Yield (sidecar_path, parsed Sidecar) for every *.anno.trig under root.

    Walks recursively. Parse failures propagate as SidecarParseError
    via `read_sidecar_strict`; iteration stops at the first failure.
    """
    for path in sorted(root.rglob("*.anno.trig")):
        yield path, read_sidecar_strict(path)


# ---- Lookup result + errors -----------------------------------------

@dataclass(frozen=True)
class ResolvedAnnotation:
    sidecar_path: Path
    sidecar: Sidecar
    annotation: Annotation
    entity_stem: str       # bare markdown stem ("foo")
    entity_relpath: str    # rel-to-root, no suffix ("notes/foo")


class AnnotationLookupError(Exception):
    """Base class for resolve_id errors."""


class AnnotationNotFound(AnnotationLookupError):
    """No annotation matched the given handle."""


class AmbiguousAnnotationId(AnnotationLookupError):
    """Bare frag or bare-stem qualifier matched more than one sidecar.

    `candidates` is always populated with rel-path-qualified IDs so
    the user has unambiguous handles to retry with.
    """

    def __init__(self, message: str, candidates: tuple[str, ...]) -> None:
        super().__init__(message)
        self.candidates = candidates


# ---- Resolution -----------------------------------------------------

def entity_relpath_for_sidecar(sidecar_path: Path, root: Path) -> str:
    """Public helper: rel-path-without-suffix for a sidecar under `root`.

    `<root>/notes/foo.anno.trig`, `<root>` → `"notes/foo"`. Used by
    `cli.py:list_cmd` to render qualified IDs in table/JSON output.
    """
    rel = sidecar_path.resolve().relative_to(root.resolve())
    name = rel.name
    if name.endswith(".anno.trig"):
        name = name[: -len(".anno.trig")]
    return rel.with_name(name).as_posix()


def entity_stem_for_sidecar(sidecar_path: Path) -> str:
    """Public helper: bare stem for a sidecar (filename minus .anno.trig)."""
    name = sidecar_path.name
    if name.endswith(".anno.trig"):
        return name[: -len(".anno.trig")]
    return sidecar_path.stem


def _qualified(sidecar_path: Path, root: Path, frag: str) -> str:
    return f"{entity_relpath_for_sidecar(sidecar_path, root)}:{frag}"


def _build_resolved(
    sidecar_path: Path,
    sidecar: Sidecar,
    annotation: Annotation,
    root: Path,
) -> ResolvedAnnotation:
    return ResolvedAnnotation(
        sidecar_path=sidecar_path,
        sidecar=sidecar,
        annotation=annotation,
        entity_stem=entity_stem_for_sidecar(sidecar_path),
        entity_relpath=entity_relpath_for_sidecar(sidecar_path, root),
    )


def resolve_id(root: Path, id_arg: str) -> ResolvedAnnotation:
    """Resolve `a-7f3a`, `foo:a-7f3a`, or `notes/foo:a-7f3a` to a sidecar+row.

    See spec §"ID resolution algorithm" for the full contract.
    """
    if ":" in id_arg:
        entity_key, frag = id_arg.split(":", 1)
        if "/" in entity_key:
            return _resolve_rel_path(root, entity_key, frag)
        return _resolve_bare_stem(root, entity_key, frag)
    return _resolve_bare_frag(root, id_arg)


def _resolve_rel_path(
    root: Path, entity_key: str, frag: str,
) -> ResolvedAnnotation:
    sidecar_path = (root / f"{entity_key}.anno.trig").resolve()
    if not sidecar_path.exists():
        raise AnnotationNotFound(
            f"no sidecar at {sidecar_path}"
        )
    sidecar = read_sidecar_strict(sidecar_path)
    for ann in sidecar.annotations:
        if ann.id == frag:
            return _build_resolved(sidecar_path, sidecar, ann, root)
    raise AnnotationNotFound(
        f"sidecar {sidecar_path.name} has no annotation {frag!r}"
    )


def _resolve_bare_stem(
    root: Path, entity_key: str, frag: str,
) -> ResolvedAnnotation:
    matches: list[Path] = sorted(
        root.rglob(f"{entity_key}.anno.trig"),
    )
    if not matches:
        raise AnnotationNotFound(
            f"no sidecar with stem {entity_key!r} under {root}"
        )
    if len(matches) > 1:
        candidates = tuple(
            sorted(_qualified(p, root, frag) for p in matches)
        )
        raise AmbiguousAnnotationId(
            f"ambiguous: {entity_key!r}:{frag} matches multiple sidecars; "
            "retry with one of the rel-path-qualified forms in .candidates",
            candidates=candidates,
        )
    sidecar_path = matches[0]
    sidecar = read_sidecar_strict(sidecar_path)
    for ann in sidecar.annotations:
        if ann.id == frag:
            return _build_resolved(sidecar_path, sidecar, ann, root)
    raise AnnotationNotFound(
        f"sidecar {sidecar_path.name} has no annotation {frag!r}"
    )


def _resolve_bare_frag(root: Path, frag: str) -> ResolvedAnnotation:
    hits: list[tuple[Path, Sidecar, Annotation]] = []
    for path, sidecar in iter_sidecars(root):
        for ann in sidecar.annotations:
            if ann.id == frag:
                hits.append((path, sidecar, ann))
    if not hits:
        raise AnnotationNotFound(
            f"no annotation matching {frag!r} under {root}"
        )
    if len(hits) > 1:
        candidates = tuple(
            sorted(_qualified(p, root, frag) for p, _s, _a in hits)
        )
        raise AmbiguousAnnotationId(
            f"ambiguous: {frag!r} matches multiple sidecars; "
            "retry with one of the rel-path-qualified forms in .candidates",
            candidates=candidates,
        )
    path, sidecar, ann = hits[0]
    return _build_resolved(path, sidecar, ann, root)
