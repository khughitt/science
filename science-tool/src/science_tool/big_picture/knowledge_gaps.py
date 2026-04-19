"""Knowledge-gap computation for `/science:big-picture` synthesis.

Identifies topics where the project's question demand exceeds its reading
coverage. See docs/specs/2026-04-19-knowledge-gaps-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.literature_prefix import (
    canonical_paper_id,
    is_external_paper_id,
)


_TOPIC_DIRS = ("doc/topics", "doc/background/topics")
_PAPER_DIRS = ("doc/papers", "doc/background/papers")


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
                raise ValueError(
                    f"Duplicate topic id {eid!r}: {origins[eid]} vs {md}"
                )
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
                raise ValueError(
                    f"Duplicate paper id {canonical!r} (via {raw_id}): "
                    f"{origins[canonical]} vs {md}"
                )
            papers[canonical] = fm
            origins[canonical] = md
    return papers
