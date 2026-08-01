"""Replay an evidence exposure and check location citations against its coverage."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from science_model.audit import Evidence, LocationEvidence
from science_model.correspondence import Correspondence
from science_model.evidence_broker import (
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    ExposureEntry,
    InlineInput,
    Outcome,
)

from science_tool.autonomy.git import history_traversal_error
from science_tool.evidence_broker.hits import parse_hits
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import ServeError, Served, serve, verify_commit


@dataclass(frozen=True)
class Full:
    line_count: int


@dataclass(frozen=True)
class Lines:
    numbers: frozenset[int]


@dataclass(frozen=True)
class PathOnly:
    pass


@dataclass(frozen=True)
class Absent:
    pass


Coverage = Full | Lines | PathOnly | Absent


def _line_count(payload: bytes) -> int:
    return payload.count(b"\n") + int(bool(payload) and not payload.endswith(b"\n"))


def _merge_coverage(left: Coverage, right: Coverage) -> Coverage:
    if isinstance(left, Full) and isinstance(right, Full):
        return Full(min(left.line_count, right.line_count))
    if isinstance(left, Full):
        return left
    if isinstance(right, Full):
        return right
    if isinstance(left, Lines) and isinstance(right, Lines):
        return Lines(left.numbers | right.numbers)
    if (isinstance(left, Lines) and isinstance(right, Absent)) or (
        isinstance(left, Absent) and isinstance(right, Lines)
    ):
        raise ValueError("a path cannot be both matched and absent at one commit")
    if isinstance(left, Lines):
        return left
    if isinstance(right, Lines):
        return right
    if isinstance(left, Absent):
        return left
    if isinstance(right, Absent):
        return right
    return PathOnly()


def _add_coverage(served: dict[str, Coverage], path: str, coverage: Coverage) -> None:
    current = served.get(path)
    served[path] = coverage if current is None else _merge_coverage(current, coverage)


def _cited_lines(citation: LocationEvidence) -> range | tuple[int, ...]:
    if citation.line is not None:
        return (citation.line,)
    if citation.span is not None:
        return range(citation.span.start_line, citation.span.end_line + 1)
    return ()


def _corresponds(citation: LocationEvidence, coverage: Coverage) -> bool:
    cited = _cited_lines(citation)
    if citation.pointer is not None and not isinstance(coverage, Full):
        return False
    if isinstance(coverage, Full):
        if citation.span is not None:
            return citation.span.end_line <= coverage.line_count
        return all(line <= coverage.line_count for line in cited)
    if isinstance(coverage, Lines):
        if (
            citation.span is not None
            and citation.span.end_line - citation.span.start_line + 1 > len(coverage.numbers)
        ):
            return False
        return all(line in coverage.numbers for line in cited)
    return not cited and citation.pointer is None


def _request(entry: ExposureEntry) -> EvidenceRequest:
    return EvidenceRequest(EvidenceOp(entry.op), target=entry.target, pathspec=entry.pathspec)


def _build_served_map(
    replayed: list[tuple[ExposureEntry, Served | InlineInput]], commit: str
) -> dict[str, Coverage]:
    served_map: dict[str, Coverage] = {}
    search_lines: dict[str, set[int]] = {}
    for entry, answer in replayed:
        if isinstance(answer, InlineInput):
            _add_coverage(served_map, answer.target, Full(answer.lines))
        elif answer.outcome is Outcome.REFUSED:
            continue
        elif entry.op == "read":
            if answer.outcome is Outcome.SERVED:
                _add_coverage(served_map, answer.target, Full(_line_count(answer.payload)))
            elif answer.outcome is Outcome.MISS_ABSENT:
                _add_coverage(served_map, answer.target, Absent())
        elif entry.op == "search" and answer.outcome is Outcome.SERVED:
            for path, line in parse_hits(answer.payload, commit):
                search_lines.setdefault(path, set()).add(line)
        elif entry.op == "history" and answer.outcome is Outcome.SERVED:
            _add_coverage(served_map, answer.target, PathOnly())
    for path, numbers in search_lines.items():
        _add_coverage(served_map, path, Lines(frozenset(numbers)))
    return served_map


def check_correspondence(
    evidence: Sequence[Evidence], exposure: EvidenceExposure | None, *, repo: Path
) -> Correspondence:
    if exposure is None:
        return Correspondence(
            status="unwired", code="NO_EXPOSURE", reason="run record carries no evidence exposure"
        )
    if exposure.replay_protocol != REPLAY_PROTOCOL_VERSION:
        return Correspondence(
            status="unwired",
            code="REPLAY_PROTOCOL_MISMATCH",
            reason=(
                f"exposure protocol {exposure.replay_protocol} differs from "
                f"checker protocol {REPLAY_PROTOCOL_VERSION}"
            ),
        )
    try:
        verify_commit(repo, exposure.commit)
    except ServeError as exc:
        return Correspondence(status="unwired", code="EXPOSURE_UNREACHABLE", reason=str(exc))
    traversal_error = history_traversal_error(repo, exposure.commit)
    if traversal_error is not None:
        return Correspondence(
            status="unwired", code="EXPOSURE_UNREACHABLE", reason=traversal_error
        )

    inline_entries = Counter(
        (entry.target, entry.sha256) for entry in exposure.entries if entry.op == "inline"
    )
    inline_manifest = Counter((item.target, item.sha256) for item in exposure.inline)
    if inline_entries != inline_manifest:
        return Correspondence(
            status="violated",
            code="EXPOSURE_UNREPRODUCIBLE",
            reason="inline entries disagree with the sealed manifest",
        )

    inline: dict[tuple[str, str], InlineInput] = {}
    for item in exposure.inline:
        key = (item.target, item.sha256)
        previous = inline.get(key)
        if previous is not None and previous.lines != item.lines:
            return Correspondence(
                status="violated",
                code="EXPOSURE_UNREPRODUCIBLE",
                reason=f"inline manifest has contradictory line counts for {item.target!r}",
            )
        inline[key] = item

    cache: dict[EvidenceRequest, Served] = {}
    replayed: list[tuple[ExposureEntry, Served | InlineInput]] = []
    for entry in exposure.entries:
        if entry.op == "inline":
            replayed.append((entry, inline[(entry.target, entry.sha256)]))
            continue

        request = _request(entry)
        answer = cache.get(request)
        if answer is None:
            answer = serve(repo, exposure.commit, request, exposure.surface_policy)
            cache[request] = answer
        if hashlib.sha256(answer.payload).hexdigest() != entry.sha256 or answer.outcome is not entry.outcome:
            return Correspondence(
                status="violated",
                code="EXPOSURE_UNREPRODUCIBLE",
                reason=f"{entry.op} entry {entry.target!r} did not replay identically",
            )
        replayed.append((entry, answer))

    served_map = _build_served_map(replayed, exposure.commit)
    locations = [item for item in evidence if isinstance(item, LocationEvidence)]
    for citation in locations:
        coverage = served_map.get(citation.path)
        if coverage is None or not _corresponds(citation, coverage):
            return Correspondence(
                status="violated",
                code="CITATION_UNSERVED",
                reason=f"citation to {citation.path!r} was not covered by the replayed exposure",
            )
    return Correspondence(
        status="verified",
        reason=None if locations else "review carries no path-bearing citations",
    )
