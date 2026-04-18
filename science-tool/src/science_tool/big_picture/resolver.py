"""Question→hypothesis resolver.

Resolves many-to-many associations using a fallback chain:
1. Direct: question frontmatter declares `hypothesis: <id>` or list of ids
2. Inverse: hypothesis frontmatter's `related:` lists the question
3. Transitive: interpretation frontmatter's `related:` contains both q and h
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from science_tool.big_picture.frontmatter import read_frontmatter

Confidence = Literal["direct", "inverse", "transitive"]


@dataclass(frozen=True)
class HypothesisMatch:
    id: str
    confidence: Confidence
    score: float


@dataclass(frozen=True)
class ResolverOutput:
    hypotheses: list[HypothesisMatch] = field(default_factory=list)
    primary_hypothesis: str | None = None


def resolve_questions(project_root: Path) -> dict[str, ResolverOutput]:
    """Resolve all questions in ``project_root`` to hypothesis associations."""
    questions = _load_entities(project_root / "doc" / "questions")
    hypotheses = _load_entities(project_root / "specs" / "hypotheses")  # noqa: F841 — used in Tasks 5-6

    results: dict[str, dict[str, HypothesisMatch]] = {qid: {} for qid in questions}

    # Direct: question frontmatter declares hypothesis.
    for qid, qfm in questions.items():
        for hid in _as_list(qfm.get("hypothesis")):
            results[qid][hid] = HypothesisMatch(hid, "direct", 1.0)

    return {qid: _finalize(matches) for qid, matches in results.items()}


def _load_entities(directory: Path) -> dict[str, dict]:
    if not directory.is_dir():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out[str(fm["id"])] = fm
    return out


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _finalize(matches: dict[str, HypothesisMatch]) -> ResolverOutput:
    if not matches:
        return ResolverOutput()
    ranked = sorted(
        matches.values(),
        key=lambda m: (_conf_rank(m.confidence), -m.score),
    )
    return ResolverOutput(hypotheses=ranked, primary_hypothesis=ranked[0].id)


def _conf_rank(c: Confidence) -> int:
    return {"direct": 0, "inverse": 1, "transitive": 2}[c]
