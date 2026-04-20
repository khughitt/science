"""Knowledge-gap computation for `/science:big-picture` synthesis.

Identifies topics where the project's question demand exceeds its reading
coverage. See docs/specs/2026-04-19-knowledge-gaps-design.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.literature_prefix import (
    canonical_paper_id,
    is_external_paper_id,
)
from science_tool.big_picture.resolver import ResolverOutput


_TOPIC_DIRS = ("doc/topics", "doc/background/topics")
_PAPER_DIRS = ("doc/papers", "doc/background/papers")

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicGap:
    """A topic where reading lags investigation.

    Attributes
    ----------
    topic_id:
        Canonical entity ID (``topic:<slug>``).
    coverage:
        Count of distinct papers covering the topic (union of
        entity-linked + bibtex-referenced, deduplicated by bibkey).
    demand:
        Count of aspect-filtered questions whose ``related:`` field
        references this topic.
    gap_score:
        ``max(0, demand - coverage)``. Topics with ``gap_score == 0``
        are not emitted.
    demanding_questions:
        Sorted (alphabetical) list of question IDs driving the demand.
    hypotheses:
        Sorted list of hypothesis IDs whose bucket contains at least
        one demanding question.
    """

    topic_id: str
    coverage: int
    demand: int
    gap_score: int
    demanding_questions: list[str]
    hypotheses: list[str]


def _load_topics(project_root: Path) -> dict[str, dict]:
    """Return ``{topic_id: frontmatter_dict}`` for every topic in the project.

    Raises ``ValueError`` if two topic files share an entity ID.
    """
    topics: dict[str, dict] = {}
    origins: dict[str, Path] = {}
    for rel in _TOPIC_DIRS:
        root = project_root / rel
        if not root.is_dir():
            continue
        for md in sorted(root.glob("*.md")):
            fm = read_frontmatter(md) or {}
            eid = fm.get("id")
            if not eid:
                continue
            if eid in topics:
                raise ValueError(f"Duplicate topic id {eid!r}: {origins[eid]} vs {md}")
            topics[eid] = fm
            origins[eid] = md
    return topics


def _load_papers(project_root: Path) -> dict[str, dict]:
    """Return ``{canonical_paper_id: frontmatter_dict}`` for every paper.

    External-literature IDs are normalized via
    :func:`literature_prefix.canonical_paper_id` before use as keys. A raw
    ``article:X`` file and a raw ``paper:X`` file across the scanned
    directories would collide at the canonical form — that collision raises.
    """
    papers: dict[str, dict] = {}
    origins: dict[str, Path] = {}
    for rel in _PAPER_DIRS:
        root = project_root / rel
        if not root.is_dir():
            continue
        for md in sorted(root.glob("*.md")):
            fm = read_frontmatter(md) or {}
            raw_id = fm.get("id")
            if not raw_id or not is_external_paper_id(raw_id):
                continue
            canonical = canonical_paper_id(raw_id)
            if canonical in papers:
                raise ValueError(f"Duplicate paper id {canonical!r} (via {raw_id}): {origins[canonical]} vs {md}")
            papers[canonical] = fm
            origins[canonical] = md
    return papers


def _bibkey_of(entity_id: str) -> str | None:
    """Return the bibkey substring (after first colon) or None."""
    _, _, rest = entity_id.partition(":")
    return rest or None


def _compute_coverage(
    topic_id: str,
    topics: dict[str, dict],
    papers: dict[str, dict],
) -> int:
    """Compute |related_papers(T) ∪ inverse_papers(T) ∪ bibtex_refs(T)|.

    Dedup uses bibkey-based comparison per the canonical rule in the
    manuscript+paper rename spec (§Canonical bibkey extraction).
    """
    topic_fm = topics.get(topic_id)
    if topic_fm is None:
        return 0

    covering_bibkeys: set[str] = set()

    # related_papers(T): T.related entries that are external paper IDs.
    for ref in topic_fm.get("related", []) or []:
        if is_external_paper_id(ref):
            canonical = canonical_paper_id(ref)
            bibkey = _bibkey_of(canonical)
            if bibkey:
                covering_bibkeys.add(bibkey)

    # inverse_papers(T): papers whose .related lists T.
    for canonical_pid, paper_fm in papers.items():
        for ref in paper_fm.get("related", []) or []:
            if ref == topic_id:
                bibkey = _bibkey_of(canonical_pid)
                if bibkey:
                    covering_bibkeys.add(bibkey)

    # bibtex_refs(T): T.source_refs entries of the form cite:<key>.
    for ref in topic_fm.get("source_refs", []) or []:
        if not isinstance(ref, str):
            _logger.warning(
                "topic %s has non-string source_refs entry %r; ignoring",
                topic_id,
                ref,
            )
            continue
        if ref.startswith("cite:"):
            bibkey = ref[len("cite:") :]
            if bibkey:
                covering_bibkeys.add(bibkey)
        else:
            _logger.warning(
                "topic %s has malformed source_refs entry %r (expected cite:<key>); ignoring",
                topic_id,
                ref,
            )

    return len(covering_bibkeys)


def _compute_demand(
    project_root: Path,
    topic_id: str,
    included_question_ids: set[str],
    *,
    known_topic_ids: set[str] | None = None,
) -> tuple[int, list[str]]:
    """Return ``(count, sorted_list)`` of aspect-filtered questions
    referencing ``topic_id`` in their ``related:`` field.

    Only considers questions present in ``included_question_ids`` (aspect
    filter already applied by the caller).

    If ``known_topic_ids`` is provided, any question's ``related:`` entry
    of the form ``topic:<X>`` that is not in ``known_topic_ids`` is logged
    as a warning (once per unknown topic ID across this call).
    """
    questions_dir = project_root / "doc" / "questions"
    if not questions_dir.is_dir():
        return 0, []

    demanders: list[str] = []
    warned: set[str] = set()
    for md in sorted(questions_dir.glob("*.md")):
        fm = read_frontmatter(md) or {}
        qid = fm.get("id")
        if not qid or qid not in included_question_ids:
            continue
        related = fm.get("related", []) or []
        if topic_id in related:
            demanders.append(qid)
        if known_topic_ids is not None:
            for ref in related:
                if (
                    isinstance(ref, str)
                    and ref.startswith("topic:")
                    and ref not in known_topic_ids
                    and ref not in warned
                ):
                    _logger.warning(
                        "question %s references unknown %s; excluded from demand",
                        qid,
                        ref,
                    )
                    warned.add(ref)
    return len(demanders), sorted(demanders)


def compute_topic_gaps(
    project_root: Path,
    resolved_questions: dict[str, ResolverOutput],
    included_question_ids: set[str],
) -> list[TopicGap]:
    """Return all topics with demand > 0 and coverage < demand.

    Sorted by ``gap_score`` descending; ties broken by ``topic_id`` ascending.

    The caller (typically the Opus orchestrator) is responsible for computing
    ``included_question_ids`` via the big-picture aspect filter before
    invoking this function. See the knowledge-gaps spec §Aspect Integration.
    """
    topics = _load_topics(project_root)
    papers = _load_papers(project_root)

    gaps: list[TopicGap] = []
    for topic_id in topics:
        demand, demanders = _compute_demand(
            project_root,
            topic_id,
            included_question_ids,
            known_topic_ids=set(topics),
        )
        if demand == 0:
            continue
        coverage = _compute_coverage(topic_id, topics, papers)
        if coverage >= demand:
            continue
        hypotheses = _hypotheses_for(demanders, resolved_questions)
        gaps.append(
            TopicGap(
                topic_id=topic_id,
                coverage=coverage,
                demand=demand,
                gap_score=max(0, demand - coverage),
                demanding_questions=demanders,
                hypotheses=hypotheses,
            )
        )

    gaps.sort(key=lambda g: (-g.gap_score, g.topic_id))
    return gaps


def _hypotheses_for(
    demander_question_ids: list[str],
    resolved: dict[str, ResolverOutput],
) -> list[str]:
    """Return sorted hypothesis IDs associated with any demanding question."""
    ids: set[str] = set()
    for qid in demander_question_ids:
        out = resolved.get(qid)
        if out is None:
            continue
        for match in out.hypotheses:
            ids.add(match.id)
    return sorted(ids)
