"""Seed-representativeness diagnostic for `science explore-ideas`.

Phase 1 of the command assembles a deliberately blind domain brief, and the
scope boundary is the single most anchoring-relevant input to it. Until
fb-2026-07-25-004 that boundary was resolved by orchestrator prose reading
`specs/scope-boundaries.md` and "skipping any that are absent" -- a path that
cannot report the difference between a project with no declared scope and a
project whose scope it simply failed to find.

It fails to find it routinely. `science entity migrate-specs` canonicalizes
loose spec docs to `entities/specs/NNNN-slug.md`, and where that migration has
run the boundary exists under the canonical layout while the legacy path is
gone. The declared scope was present and unreachable, and `out-of-scope` --
one of the four novelty buckets -- was judged against a file that no longer
existed there.

This module resolves the boundary through the canonical layout first, then the
legacy path, and reports WHICH, so the brief's provenance is a structured fact
in the report rather than something a reader has to trust.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.spec_paths import resolve_spec
from science_tool.topic_coverage import TopicCoverage, compute_topic_coverage

#: The boundary was found and read; the brief carries the project's own words.
SCOPE_DECLARED = "declared"
#: No boundary document exists anywhere. The orchestrator must infer scope from
#: `science.yaml` and AGENTS.md, and the report says so rather than implying
#: the brief was grounded in a declaration.
SCOPE_ABSENT = "absent"
#: Written by the ORCHESTRATOR into the report, never emitted by this module: it
#: records that scope was reconstructed from `science.yaml`/AGENTS.md after this
#: diagnostic reported `absent`. Kept in the vocabulary here because the report
#: field has one meaning across both writers, and a reader distinguishing "no
#: declared scope" from "scope reconstructed by an agent" needs both tokens.
SCOPE_INFERRED = "inferred"

VALID_SCOPE_SOURCES = {SCOPE_DECLARED, SCOPE_INFERRED, SCOPE_ABSENT}

_SCOPE_SLUG = "scope-boundaries"
_QUESTION_SLUG = "research-question"


@dataclass(frozen=True)
class BriefSource:
    """Where one Phase-1 brief input was found, if anywhere."""

    #: ``scope-boundaries`` or ``research-question``.
    name: str
    #: ``declared`` or ``absent``.
    source: str
    #: Project-root-relative POSIX path, or ``None`` when absent.
    path: str | None
    #: ``canonical`` (``entities/specs/``) or ``legacy`` (``specs/``); ``None``
    #: when absent. Recorded because a legacy hit means the project has not been
    #: migrated, which is actionable in a way "found it" alone is not.
    layout: str | None

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "source": self.source, "path": self.path, "layout": self.layout}


@dataclass(frozen=True)
class SeedCoverage:
    """The full `seed_coverage` block the Phase-4 report header emits."""

    coverage: TopicCoverage
    sources: tuple[BriefSource, ...]

    @property
    def scope_source(self) -> str:
        for source in self.sources:
            if source.name == _SCOPE_SLUG:
                return source.source
        return SCOPE_ABSENT

    def to_dict(self) -> dict[str, object]:
        out = dict(self.coverage.to_dict())
        out["scope_source"] = self.scope_source
        out["brief_sources"] = [source.to_dict() for source in self.sources]
        return out


def _resolve_source(project_root: Path, name: str) -> BriefSource:
    """One brief input, resolved through the shared spec resolver.

    Layout resolution lives in `spec_paths`, not here: five other commands read
    the same documents, and a second copy of the canonical-then-legacy rule is
    how the readers came to disagree in the first place (fb-2026-07-26-020).
    """
    location = resolve_spec(project_root, name)
    if location.found:
        return BriefSource(name, SCOPE_DECLARED, location.path, location.layout)
    return BriefSource(name, SCOPE_ABSENT, None, None)


def compute_seed_coverage(project_root: Path) -> SeedCoverage:
    project_root = project_root.resolve()
    return SeedCoverage(
        coverage=compute_topic_coverage(project_root),
        sources=(
            _resolve_source(project_root, _SCOPE_SLUG),
            _resolve_source(project_root, _QUESTION_SLUG),
        ),
    )
