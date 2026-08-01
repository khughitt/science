"""Replay an evidence exposure and check location citations against its coverage."""

from __future__ import annotations

from dataclasses import dataclass

from science_model.audit import LocationEvidence


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
        return all(line <= coverage.line_count for line in cited)
    if isinstance(coverage, Lines):
        return all(line in coverage.numbers for line in cited)
    return not cited and citation.pointer is None
