"""Triage classifier for aggregate (`entities.yaml`) owner rows (design §B5, 3a).

Reads the compiled model only — the IdentityTable and the row-level
`ProjectSources.aggregate_rows` metadata produced by load_project_sources — and
buckets every aggregate owner row by deterministic, evidence-bearing rules. The
output is read-only decision support feeding the Phase 3b `--apply`; the rules are
heuristics (design §D5: the concept-vs-tag boundary is judgment, not algorithm),
so each row carries the basis for its bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from science_tool.graph.identity_table import build_identity_table

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources


class AggregateBucket(str, Enum):
    SHADOW = "shadow"
    COINED = "coined"
    DECISION_LOG = "decision-log"
    EXTERNAL_REF = "external-ref"
    CRUFT = "cruft"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class AggregateRowTriage:
    canonical_id: str
    kind: str
    source_path: str | None
    has_real_owner: bool
    bucket: AggregateBucket
    evidence: str


_COINABLE_KINDS = frozenset({"concept", "latent"})


def _bucket(
    kind: str, source_path: str | None, has_real_owner: bool, self_sourced: bool
) -> tuple[AggregateBucket, str]:
    if has_real_owner:
        return AggregateBucket.SHADOW, "a non-aggregate owner of this id exists -> shadow"
    if source_path is not None and source_path.startswith("migration:"):
        return AggregateBucket.CRUFT, f"source_path {source_path!r} is a migration artifact -> cruft"
    if kind == "decision" and source_path == "core/decisions.md":
        return AggregateBucket.DECISION_LOG, "decision sourced from core/decisions.md -> decision-log"
    if kind == "article" or (source_path is not None and source_path.endswith(".bib")):
        return AggregateBucket.EXTERNAL_REF, f"kind={kind} / bibliographic source -> external-ref"
    if self_sourced and (kind in _COINABLE_KINDS or kind == "decision"):
        return AggregateBucket.COINED, f"self-sourced coinable kind={kind} -> coined"
    return AggregateBucket.AMBIGUOUS, f"self-sourced kind={kind}, no rule matched -> ambiguous"


def classify_aggregate_rows(sources: "ProjectSources") -> list[AggregateRowTriage]:
    """Bucket every aggregate owner row, sorted by (bucket, canonical_id)."""
    table = build_identity_table(sources)
    meta_by_ref = {(m.path, m.line): m for m in sources.aggregate_rows}

    triaged: list[AggregateRowTriage] = []
    for (_scope, canonical_id), rows in table.owners().items():
        agg_rows = [r for r in rows if r.adapter == "aggregate"]
        if not agg_rows:
            continue
        has_real_owner = any(r.adapter != "aggregate" and not r.deprecated for r in rows)
        for decl in agg_rows:
            ref = decl.source_ref
            meta = meta_by_ref.get((ref.path, ref.line)) if ref is not None else None
            kind = meta.kind if meta is not None else canonical_id.split(":", 1)[0]
            source_path = meta.source_path if meta is not None else None
            agg_path = ref.path if ref is not None else None
            # Absent OR empty source_path counts as self-sourced (design §5.2).
            self_sourced = source_path in (None, "") or source_path == agg_path
            bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced)
            triaged.append(AggregateRowTriage(canonical_id, kind, source_path, has_real_owner, bucket, evidence))
    triaged.sort(key=lambda t: (t.bucket.value, t.canonical_id))
    return triaged
