# science/src/science_tool/annotation/audit.py
"""Audit orchestration: per-source merge with deterministic ID minting.

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md §audit.py.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from science_tool.annotation.hash import content_hash
from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Sidecar,
    Status,
)
from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
    SourceAdapter,
)


@dataclass(frozen=True)
class AuditFileReport:
    md_path: Path
    sidecar_path: Path
    rows_written: int
    duplicates_skipped: int
    written_per_source: dict[str, int]


def _annotation_tuple(
    a: Annotation,
) -> tuple[str, str, Optional[str], Optional[str]]:
    return (a.source, a.target.selector.exact, a.lifted_from, a.match_text)


def _planned_tuple(
    p: PlannedAnnotation,
) -> tuple[str, str, Optional[str], str]:
    return (p.source_name, p.target.selector.exact, p.lifted_from, p.match_text)


def _mint_base_id(p: PlannedAnnotation) -> str:
    h = hashlib.sha256()
    h.update(p.source_name.encode("utf-8"))
    h.update(b"\x1e")
    h.update(p.target.selector.exact.encode("utf-8"))
    h.update(b"\x1e")
    h.update((p.lifted_from or "").encode("utf-8"))
    h.update(b"\x1e")
    h.update(p.match_text.encode("utf-8"))
    return f"a-{h.hexdigest()[:6]}"


def mint_id(sidecar: Sidecar, p: PlannedAnnotation) -> str:
    """Mint the on-disk ID for a planned row.

    Same-finding superseded predecessor → suffix `-N`.
    Same-finding non-superseded match → unreachable (caller must
    have run merge_planned dedupe first; assert guards).
    Unrelated 4-tuple at same base_id → IdCollisionError.
    """
    base_id = _mint_base_id(p)
    existing_at_base = next(
        (a for a in sidecar.annotations if a.id == base_id), None,
    )
    if existing_at_base is None:
        return base_id

    if (
        _annotation_tuple(existing_at_base)[:3] == _planned_tuple(p)[:3]
        and existing_at_base.match_text == p.match_text
    ):
        assert existing_at_base.status is Status.SUPERSEDED, (
            "merge_planned should have skipped a non-superseded match"
        )
        existing_ids = {a.id for a in sidecar.annotations}
        n = 2
        while f"{base_id}-{n}" in existing_ids:
            n += 1
        return f"{base_id}-{n}"

    raise IdCollisionError(
        f"base_id {base_id!r} occupied by unrelated 4-tuple "
        f"(existing source={existing_at_base.source!r}, "
        f"planned source={p.source_name!r}); bump hash slice length"
    )


def merge_planned(
    sidecar: Sidecar,
    planned: Sequence[PlannedAnnotation],
    *,
    actor: str,
    now: datetime,
) -> tuple[Sidecar, list[Annotation]]:
    """Merge planned rows into sidecar; return (new_sidecar, written_rows).

    All planned rows MUST share `source_name`. Skip rule: any
    non-superseded annotation matching the 4-tuple suppresses the
    planned row. Superseded matches are ignored for skip but
    influence ID minting.
    """
    if not planned:
        return sidecar, []
    source_name = planned[0].source_name
    assert all(p.source_name == source_name for p in planned), (
        "merge_planned requires single-source planned rows"
    )

    existing = list(sidecar.annotations)
    existing_keys: dict[
        tuple[str, str, Optional[str], Optional[str]], Annotation
    ] = {_annotation_tuple(a): a for a in existing}

    written: list[Annotation] = []
    seen_planned_keys: set[tuple[str, str, Optional[str], str]] = set()
    seen_planned_base_ids: dict[str, PlannedAnnotation] = {}

    for p in planned:
        key = _planned_tuple(p)
        if key in seen_planned_keys:
            continue
        seen_planned_keys.add(key)

        existing_match = existing_keys.get(
            (p.source_name, p.target.selector.exact, p.lifted_from, p.match_text)
        )
        if existing_match is not None and existing_match.status is not Status.SUPERSEDED:
            continue

        base_id = _mint_base_id(p)
        prior_planned = seen_planned_base_ids.get(base_id)
        if prior_planned is not None:
            raise IdCollisionError(
                f"two distinct planned rows hash to base_id {base_id!r} "
                f"in one merge call; bump hash slice length"
            )
        seen_planned_base_ids[base_id] = p

        new_id = mint_id(
            Sidecar(annotations=tuple(existing + written)),
            p,
        )
        new_ann = Annotation(
            id=new_id,
            target=p.target,
            bodies=(p.body,),
            motivation=p.motivation,
            annotation_type=p.annotation_type,
            source=p.source_name,
            status=Status.OPEN,
            creator=actor,
            created=now,
            content_hash=content_hash(p.target.selector.exact, p.source_name),
            lifted_from=p.lifted_from,
            match_text=p.match_text,
        )
        written.append(new_ann)

    new_sidecar = replace(
        sidecar,
        annotations=tuple(existing + written),
    )
    return new_sidecar, written


def audit_file(
    md_path: Path,
    sidecar_path: Path,
    sources: Sequence[SourceAdapter],
    *,
    actor: str,
    now: datetime,
) -> AuditFileReport:
    """Per-file audit: read sidecar, run sources sequentially, persist."""
    if sidecar_path.exists():
        sidecar = read_sidecar(sidecar_path)
    else:
        sidecar = Sidecar()

    total_written = 0
    total_skipped = 0
    per_source: dict[str, int] = {}
    any_writes = False

    for source in sources:
        plans = list(source.scan(md_path))
        if not plans:
            per_source[source.short_name] = 0
            continue
        sidecar, written = merge_planned(
            sidecar, plans, actor=actor, now=now,
        )
        per_source[source.short_name] = len(written)
        total_written += len(written)
        total_skipped += len(plans) - len(written)
        if written:
            any_writes = True

    if any_writes:
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        write_sidecar(sidecar_path, sidecar)

    return AuditFileReport(
        md_path=md_path,
        sidecar_path=sidecar_path,
        rows_written=total_written,
        duplicates_skipped=total_skipped,
        written_per_source=per_source,
    )
