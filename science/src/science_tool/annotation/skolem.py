# science/src/science_tool/annotation/skolem.py
"""Blank-node → IRI rule for graph ingest.

The canonical graph writer (`science_tool/graph/io.py`) rejects blank
nodes. Sidecars MAY use blank nodes for compactness; the ingest step
(P3.6) calls this function to mint stable IRIs before merge.

See docs/plans/historical/2026-05-10-annotation-system-spec.md
§Skolemization for graph ingest.
"""

from __future__ import annotations

from typing import Literal

Role = Literal["target", "selector", "body"]
_VALID_ROLES: frozenset[str] = frozenset(("target", "selector", "body"))


def skolem_iri(annotation_id: str, role: Role, *, index: int = 1) -> str:
    """Return the skolemized IRI suffix for a blank-node role.

    - target  → ``<id>/target``
    - selector → ``<id>/target/selector``
    - body (1) → ``<id>/body``
    - body (N≥2) → ``<id>/body/<N>``

    ``index`` is meaningful only for ``role="body"``; passing it with
    other roles raises ``ValueError``.
    """
    if role not in _VALID_ROLES:
        raise ValueError(f"unknown role: {role!r}")
    if role != "body" and index != 1:
        raise ValueError(f"index is only valid for role='body'; got role={role!r}")
    if role == "target":
        return f"{annotation_id}/target"
    if role == "selector":
        return f"{annotation_id}/target/selector"
    # role == "body"
    if index == 1:
        return f"{annotation_id}/body"
    return f"{annotation_id}/body/{index}"
