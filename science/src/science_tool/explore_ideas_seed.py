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

from science_model.frontmatter import parse_frontmatter

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

#: Canonical home, post `science entity migrate-specs`.
_CANONICAL_SPECS_DIR = ("entities", "specs")
#: Pre-migration location. Still scaffolded by `create-project`, so it is a
#: live case rather than a historical one.
_LEGACY_SCOPE_PATH = ("specs", "scope-boundaries.md")
_LEGACY_QUESTION_PATH = ("specs", "research-question.md")

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


def _canonical_spec(project_root: Path, slug: str) -> Path | None:
    """Find a migrated spec by slug.

    Migration renames to `NNNN-<slug>.md` and preserves the old id as an alias,
    so the slug is matched against both the filename tail and the frontmatter
    `id`/`aliases` -- a project that renamed the title would otherwise read as
    absent while the document sits in plain view.
    """
    specs_dir = project_root.joinpath(*_CANONICAL_SPECS_DIR)
    if not specs_dir.is_dir():
        return None
    for path in sorted(specs_dir.glob("*.md")):
        stem = path.stem
        if stem == slug or (stem[:4].isdigit() and stem[5:] == slug):
            return path
        parsed = parse_frontmatter(path)
        if parsed is None:
            continue
        data, _ = parsed
        identifiers = [data.get("id"), *(data.get("aliases") or [])]
        if any(isinstance(value, str) and value.split(":")[-1] == slug for value in identifiers):
            return path
    return None


def _resolve_source(project_root: Path, name: str, legacy: tuple[str, ...]) -> BriefSource:
    canonical = _canonical_spec(project_root, name)
    if canonical is not None:
        return BriefSource(name, SCOPE_DECLARED, canonical.relative_to(project_root).as_posix(), "canonical")
    legacy_path = project_root.joinpath(*legacy)
    if legacy_path.is_file():
        return BriefSource(name, SCOPE_DECLARED, legacy_path.relative_to(project_root).as_posix(), "legacy")
    return BriefSource(name, SCOPE_ABSENT, None, None)


def compute_seed_coverage(project_root: Path) -> SeedCoverage:
    project_root = project_root.resolve()
    return SeedCoverage(
        coverage=compute_topic_coverage(project_root),
        sources=(
            _resolve_source(project_root, _SCOPE_SLUG, _LEGACY_SCOPE_PATH),
            _resolve_source(project_root, _QUESTION_SLUG, _LEGACY_QUESTION_PATH),
        ),
    )
