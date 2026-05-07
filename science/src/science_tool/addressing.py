"""Cross-project addressing convention: <project-id>:<artifact-id>."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ADDRESS_RE = re.compile(r"^(?P<project>[a-z][a-z0-9-]{1,63}):(?P<artifact>[^@\s]+)$")
_BARE_TASK_RE = re.compile(r"^t[0-9]{3,}$")
_URI_SCHEME = "cancer"


@dataclass(frozen=True)
class Address:
    project_id: str
    artifact_id: str


@dataclass(frozen=True)
class RefShape:
    raw: str
    shape: str
    project_id: str = ""
    kind: str = ""
    slug: str = ""


def parse_address(raw: str) -> Address:
    match = _ADDRESS_RE.match(raw)
    if not match:
        raise ValueError(f"not a valid cross-project address: {raw!r}")
    return Address(project_id=match["project"], artifact_id=match["artifact"])


def is_address(raw: str) -> bool:
    return _ADDRESS_RE.match(raw) is not None


def render_uri(address: Address) -> str:
    """Render the address as a URI suitable for graph triples."""
    return f"<{_URI_SCHEME}://{address.project_id}/{address.artifact_id}>"


def classify_entity_ref(
    raw: str,
    *,
    local_kinds: set[str] | frozenset[str],
    project_ids: set[str] | frozenset[str],
) -> RefShape:
    value = raw.strip()
    if _BARE_TASK_RE.match(value):
        return RefShape(raw=value, shape="bare-task", kind="task", slug=value)

    parts = value.split(":")
    if len(parts) == 2:
        first, slug = parts
        if "@" in slug:
            return RefShape(raw=value, shape="non-entity")
        if first in local_kinds:
            return RefShape(raw=value, shape="local-entity", kind=first, slug=slug)
        if first in project_ids:
            return RefShape(raw=value, shape="legacy-cross-project", project_id=first, slug=slug)
        return RefShape(raw=value, shape="unresolved-local-kind", kind=first, slug=slug)

    if len(parts) == 3:
        project_id, kind, slug = parts
        if "@" in slug:
            return RefShape(raw=value, shape="non-entity")
        if project_id in project_ids:
            return RefShape(
                raw=value,
                shape="cross-project-entity",
                project_id=project_id,
                kind=kind,
                slug=slug,
            )
        return RefShape(
            raw=value,
            shape="unknown-namespace",
            project_id=project_id,
            kind=kind,
            slug=slug,
        )

    return RefShape(raw=value, shape="non-entity")
