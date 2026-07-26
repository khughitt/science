"""The entity-kind vocabulary a project accepts, as data.

Downstream projects have to name kinds in places the toolkit does not write --
a `commitlint.config.mjs` `type-enum`, a docs table, a shell completion. With no
way to ask, each one transcribes the list by hand and it goes stale the moment a
kind is added: natural-systems' hand-written enum was missing eleven kinds, and a
legitimate `dataset:` commit was rejected at commit time (fb-2026-07-26-017).

Derived from `kind_descriptors.KIND_DESCRIPTORS` -- the Kind Descriptor is the
sole SSOT for what a kind is called -- plus the project's own local profile, so
what this prints is what the project actually accepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.kind_descriptors import KIND_DESCRIPTORS


@dataclass(frozen=True)
class KindRow:
    name: str
    origin: str  # "shipped" | "project"
    canonical_prefix: str
    home: str
    statuses: tuple[str, ...]


def _row(kind: object, origin: str) -> KindRow:
    return KindRow(
        name=getattr(kind, "name", ""),
        origin=origin,
        canonical_prefix=getattr(kind, "canonical_prefix", "") or "",
        home=getattr(kind, "home", "") or "",
        statuses=tuple(getattr(kind, "statuses", None) or ()),
    )


def project_kind_vocabulary(project_root: Path | None) -> list[KindRow]:
    """Every kind name this project accepts, shipped kinds first, then its own.

    `project_root=None` reports the shipped vocabulary alone. A project whose
    local profile manifest is unreadable raises rather than silently reporting a
    short list -- a truncated vocabulary is exactly the failure this exists to end.
    """
    rows = [_row(kind, "shipped") for kind in KIND_DESCRIPTORS]
    if project_root is None:
        return sorted(rows, key=lambda r: r.name)

    from science_tool.entity_kinds import _local_profile_name  # noqa: PLC0415
    from science_tool.graph.sources import (  # noqa: PLC0415
        load_profile_manifest,
        local_profile_sources_dir,
    )

    local_dir = local_profile_sources_dir(project_root, local_profile=_local_profile_name(project_root))
    manifest = load_profile_manifest(local_dir / "manifest.yaml")
    if manifest is not None:
        shipped = {row.name for row in rows}
        rows.extend(
            _row(kind, "project") for kind in manifest.entity_kinds if kind.name not in shipped
        )
    return sorted(rows, key=lambda r: r.name)
