"""Where a project's authored spec documents actually live.

`science entity migrate-specs` canonicalizes loose spec docs to
`entities/specs/NNNN-<slug>.md`, preserving the pre-migration id as an alias.
The pre-migration home was `specs/<slug>.md`.

Both layouts are live, and the reason is not that migration is incomplete:
`create-project` still scaffolds the legacy path, so new projects are created
into the layout the migrator moves away from (fb-2026-07-26-020). Six commands
read these documents. Before this module each named a path literally, so a
migrated project silently read nothing where the document existed and was
reachable -- `out-of-scope`, one of `explore-ideas`' four novelty buckets, was
judged against a file that was no longer there.

One resolver, so the readers cannot disagree with each other or with the
scaffolder. It reports WHICH layout answered, because a legacy hit means the
project has not been migrated -- actionable in a way "found it" is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_model.frontmatter import parse_frontmatter

#: Canonical home, post `science entity migrate-specs`.
CANONICAL_SPECS_DIR = ("entities", "specs")
#: Pre-migration home. A live case, not a historical one.
LEGACY_SPECS_DIR = ("specs",)

LAYOUT_CANONICAL = "canonical"
LAYOUT_LEGACY = "legacy"


@dataclass(frozen=True)
class SpecLocation:
    """The resolved home of one spec document, or the fact that it has none."""

    #: Slug as requested, e.g. ``scope-boundaries``.
    slug: str
    #: Project-root-relative POSIX path, or ``None`` when the document is absent.
    path: str | None
    #: ``canonical``, ``legacy``, or ``None`` when absent.
    layout: str | None

    @property
    def found(self) -> bool:
        return self.path is not None

    def to_dict(self) -> dict[str, object]:
        return {"slug": self.slug, "path": self.path, "layout": self.layout}


def _canonical_spec(project_root: Path, slug: str) -> Path | None:
    """Find a migrated spec by slug.

    Migration renames to `NNNN-<slug>.md` and preserves the old id as an alias,
    so the slug is matched against both the filename tail and the frontmatter
    `id`/`aliases` -- a project that renamed the title would otherwise read as
    absent while the document sits in plain view.
    """
    specs_dir = project_root.joinpath(*CANONICAL_SPECS_DIR)
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


def resolve_spec(project_root: Path, slug: str) -> SpecLocation:
    """Resolve one spec document, canonical layout winning over legacy.

    Canonical first: where migration has run, the legacy path is gone, and where
    it has not, the canonical directory does not exist. A project mid-migration
    can hold both, and the canonical copy is the one the migrator wrote.
    """
    project_root = project_root.resolve()
    canonical = _canonical_spec(project_root, slug)
    if canonical is not None:
        return SpecLocation(slug, canonical.relative_to(project_root).as_posix(), LAYOUT_CANONICAL)

    legacy = project_root.joinpath(*LEGACY_SPECS_DIR, f"{slug}.md")
    if legacy.is_file():
        return SpecLocation(slug, legacy.relative_to(project_root).as_posix(), LAYOUT_LEGACY)

    return SpecLocation(slug, None, None)
