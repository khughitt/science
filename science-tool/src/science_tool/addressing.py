"""Cross-project addressing convention: <project-id>:<artifact-id>."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ADDRESS_RE = re.compile(r"^(?P<project>[a-z][a-z0-9-]{1,63}):(?P<artifact>\S+)$")
_URI_SCHEME = "cancer"


@dataclass(frozen=True)
class Address:
    project_id: str
    artifact_id: str


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
