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
from science_tool.annotation.model import Sidecar


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
