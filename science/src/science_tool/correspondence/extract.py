"""Extract probeable claims from a plan body.

Deliverables are **read from a declaration, not guessed from the prose**. A plan
body names paths for at least four different reasons -- what it will build, what
it will delete, what it must read as a precondition, and what it merely cites as
background -- and only the first two are deliverables. Harvesting every backticked
path conflated them, so citing existing code as context registered as completed
work (fb-2026-07-26-015): `0037-provenance-schema-integration-plan.md` has a
`## Suggested deliverables` section containing no paths at all, and the screen
adjudicated it from its `## Recommended reading order` instead.

So extraction is scoped to a declared region: a heading that names deliverables,
outputs, artifacts, or targets. A plan without one has declared nothing probeable,
which collapses to `indeterminate` and stays silent (design §6.3). That trades
recall for precision deliberately -- an advisory screen whose only remedy for a
false positive is a permanent per-file suppression has to be right when it speaks,
and recall is recoverable by adding the section.

The declaration also carries **polarity** (fb-2026-07-26-014). A retirement plan's
exit criterion is that its targets are *gone*, so scoring `absent` as "not built"
reads such a plan exactly backwards. A declared heading naming removal inverts its
probes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_EXTENSIONS = "py|ts|tsx|js|jsx|md|yaml|yml|json|sh|R|toml|cfg|ini|sql|trig"

# Requires at least one "/" -- a bare `foo.py` names no location.
_PATH_RE = re.compile(rf"`([\w.-]+(?:/[\w.-]+)+\.(?:{_EXTENSIONS}))`")
_TASK_RE = re.compile(r"task:(t\d+)")

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# A declared region is a heading that *is* the declaration, not one that mentions
# it: qualifier words then the noun, and nothing after. This admits the forms the
# corpus actually uses ("Deliverables", "Suggested deliverables", "Required Output
# Artifacts", "Workflow Outputs", "t552 Deliverables") while rejecting headings
# that merely contain the word ("Task 7: regenerate artifacts + final verification",
# "What the output is and is not", "Regenerated output (no manual edits)").
# The optional tail admits "Deliverables to remove" alongside "Removed artifacts";
# it is deliberately restricted to removal phrasing, because a free tail would
# re-admit "What the output is and is not".
_DECLARED_HEADING_RE = re.compile(
    r"^(?:[\w][\w \-]*[ \-])?(?:deliverables?|outputs?|artifacts?|targets?)"
    r"(?: (?:to )?(?:remove|retire|delete)d?)?$",
    re.IGNORECASE,
)
_REMOVAL_RE = re.compile(
    r"\b(?:retire|retired|retirement|remove|removed|removal|delete|deleted|deletion)\b",
    re.IGNORECASE,
)


class Polarity(StrEnum):
    """What the plan claims about a declared path's existence at completion."""

    CREATE = "create"
    REMOVE = "remove"


@dataclass(frozen=True)
class Deliverable:
    path: str
    polarity: Polarity


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _declared_regions(body: str) -> list[tuple[Polarity, str]]:
    """Every declared deliverables region, as (polarity, text) pairs.

    A region runs from its heading to the next heading at the same or a higher
    level, so subsections of a `## Deliverables` block are part of it.
    """
    regions: list[tuple[Polarity, str]] = []
    open_level: int | None = None
    polarity = Polarity.CREATE
    collected: list[str] = []
    for line in body.splitlines():
        heading = _HEADING_RE.match(line)
        if heading is None:
            if open_level is not None:
                collected.append(line)
            continue
        level, text = len(heading.group(1)), heading.group(2)
        if open_level is not None and level <= open_level:
            regions.append((polarity, "\n".join(collected)))
            open_level, collected = None, []
        if _DECLARED_HEADING_RE.match(text):
            open_level = level
            polarity = Polarity.REMOVE if _REMOVAL_RE.search(text) else Polarity.CREATE
            collected = []
    if open_level is not None:
        regions.append((polarity, "\n".join(collected)))
    return regions


def extract_deliverables(body: str) -> list[Deliverable]:
    """Paths declared as this plan's deliverables, with their polarity.

    Empty when the plan declares no deliverables region, or declares one that
    names no probeable path -- both mean the plan declared nothing probeable.
    """
    by_path: dict[str, Polarity] = {}
    for polarity, text in _declared_regions(body):
        for path in _PATH_RE.findall(text):
            # First declaration wins, so a path named in both a build and a
            # removal region is not silently re-polarized by document order.
            by_path.setdefault(path, polarity)
    return [Deliverable(path=path, polarity=polarity) for path, polarity in by_path.items()]


def extract_task_refs(body: str) -> list[str]:
    return _dedupe(_TASK_RE.findall(body))
