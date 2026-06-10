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
    CURIE_EXTERNAL_REF = "curie-external-ref"
    CRUFT = "cruft"
    REFERENCED_ORPHAN = "referenced-orphan"
    QUESTION_DEFERRED = "question-deferred"
    AMBIGUOUS = "ambiguous"


# Mirrors graph.health._IDENTITY_REFERENCE_FIELDS — the structural reference
# surface whose dangling targets the validator reports as errors. Kept local so
# this low-level classifier does not import the heavy `health` module (which sits
# above it in the dependency order). Keep the two lists in sync.
_REFERENCE_FIELDS = ("related", "commits_to", "source_refs", "evidence_refs", "same_as", "blocked_by", "consumed_by")


def _reference_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if isinstance(item, str)]
    return []


def inbound_reference_counts(sources: "ProjectSources") -> dict[str, int]:
    """Count distinct entities that structurally reference each id.

    Walks every owner entity's reference-bearing frontmatter fields (the same
    surface whose dangling targets the validator flags) and tallies, per target
    id, how many distinct entities point at it. Referenced tokens are resolved
    through `manual_aliases` so a referrer using a pre-migration id still counts
    toward the renamed canonical id. Used to protect structurally-referenced
    migration-audit rows from cruft deletion: deleting such a row would leave a
    real `related:`/`source_refs:` link dangling.

    Pass a commons-INCLUSIVE `sources` to capture cross-store referrers: a commons
    entity can reference a project-owned id (e.g. a commons topic's `related:`
    pointing at a locally-owned topic), and deleting that local owner would dangle
    the commons reference. The caller controls the reference surface by choosing
    how it loads `sources` here, independently of the ownership/bucketing surface.
    """
    aliases = sources.manual_aliases
    referrers: dict[str, set[str]] = {}
    for entity in sources.entities:
        for field in _REFERENCE_FIELDS:
            for raw in _reference_strings(getattr(entity, field, None)):
                target = aliases.get(raw, raw)
                referrers.setdefault(target, set()).add(entity.file_path)
                if target != raw:
                    referrers.setdefault(raw, set()).add(entity.file_path)
    return {target: len(paths) for target, paths in referrers.items()}


@dataclass(frozen=True, slots=True)
class AggregateRowTriage:
    canonical_id: str
    kind: str
    source_path: str | None
    has_real_owner: bool
    bucket: AggregateBucket
    evidence: str
    path: str | None  # aggregate file (entities.yaml/terms.yaml), project-root-relative
    line: int | None  # row index within that file


_COINABLE_KINDS = frozenset({"concept", "latent"})

# 4c: bare project vocabulary kinds that promote as slug owners (method/topic
# became slug identity kinds in 4c). `question` is epistemic and is NOT here —
# it routes to QUESTION_DEFERRED for deliberate authoring.
_COINABLE_VOCAB_KINDS = frozenset({"method", "topic"})


def _bucket(
    kind: str,
    source_path: str | None,
    has_real_owner: bool,
    self_sourced: bool,
    has_primary_external_id: bool,
    inbound_ref_count: int = 0,
) -> tuple[AggregateBucket, str]:
    if has_real_owner:
        return AggregateBucket.SHADOW, "a non-aggregate owner of this id exists -> shadow"
    if source_path is not None and source_path.startswith("migration:"):
        # A migration artifact is only safe to delete if nothing structurally
        # references it. When live entities point at the id (and no real owner
        # exists to absorb them), deleting the row would dangle those references —
        # route it to REFERENCED_ORPHAN for resolution (promote to an owner, or
        # clean the stale refs) instead of silently deleting.
        if inbound_ref_count > 0:
            return (
                AggregateBucket.REFERENCED_ORPHAN,
                f"migration artifact with {inbound_ref_count} live referrer(s) -> resolve, do not delete",
            )
        return AggregateBucket.CRUFT, f"source_path {source_path!r} is a migration artifact, no referrers -> cruft"
    if kind == "decision" and source_path == "core/decisions.md":
        return AggregateBucket.DECISION_LOG, "decision sourced from core/decisions.md -> decision-log"
    if kind == "article" or (source_path is not None and source_path.endswith(".bib")):
        return AggregateBucket.EXTERNAL_REF, f"kind={kind} / bibliographic source -> external-ref"
    if self_sourced and (kind in _COINABLE_KINDS or kind == "decision"):
        return AggregateBucket.COINED, f"self-sourced coinable kind={kind} -> coined"
    # 4c terminal fan-out (replaces the old single `return AMBIGUOUS`):
    if has_primary_external_id:
        return AggregateBucket.CURIE_EXTERNAL_REF, f"{kind} carries primary_external_id -> curie external ref"
    if self_sourced and kind == "question":
        return AggregateBucket.QUESTION_DEFERRED, "bare question stub -> requires epistemic authoring (deferred)"
    if self_sourced and kind in _COINABLE_VOCAB_KINDS:
        return AggregateBucket.COINED, f"self-sourced vocabulary kind={kind} -> coined"
    return AggregateBucket.AMBIGUOUS, f"{kind} without primary_external_id -> requires human identity decision"


def classify_aggregate_rows(
    sources: "ProjectSources",
    *,
    inbound_ref_counts: dict[str, int] | None = None,
) -> list[AggregateRowTriage]:
    """Bucket every aggregate owner row, sorted by (bucket, canonical_id).

    `inbound_ref_counts` lets the caller supply the reference surface separately
    from the ownership surface — e.g. a commons-inclusive index that sees cross-
    store referrers, while `sources` stays commons-exclusive so commons ownership
    does not perturb shadow/coined bucketing. When omitted, the index is derived
    from `sources` itself (sufficient for self-contained projects and tests).
    """
    table = build_identity_table(sources)
    meta_by_ref = {(m.path, m.line): m for m in sources.aggregate_rows}
    inbound = inbound_ref_counts if inbound_ref_counts is not None else inbound_reference_counts(sources)

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
            ref_line = ref.line if ref is not None else None
            # Absent OR empty source_path counts as self-sourced (design §5.2).
            self_sourced = source_path in (None, "") or source_path == agg_path
            has_pei = meta is not None and meta.primary_external_id is not None
            inbound_count = inbound.get(canonical_id, 0)
            bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced, has_pei, inbound_count)
            triaged.append(
                AggregateRowTriage(
                    canonical_id, kind, source_path, has_real_owner, bucket, evidence, agg_path, ref_line
                )
            )
    triaged.sort(key=lambda t: (t.bucket.value, t.canonical_id))
    return triaged
