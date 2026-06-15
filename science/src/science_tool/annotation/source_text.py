"""Phase 1: the `.source.md` anchor surface.

Resolve a pmid|doi to an existing paper entity, acquire its article text
(PubTator3 BioC abstract preferred, Europe PMC abstract fallback), license-gate
full-text persistence, and render a `<citekey>.source.md` artifact carrying a
verifiable per-passage character-offset map plus provenance frontmatter.

Network I/O reuses paper_fetch's injectable httpx.Client + RateLimiter + FetchConfig
so callers (and tests) control every request.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.commons.promote import PROMOTE_KIND_PAPER
from science_tool.paper_fetch import normalize_doi, normalize_pmid


class SourceTextError(ValueError):
    """Raised for user-correctable persist-source errors (fail-loud)."""


# Sidecar artifacts that must not be mistaken for paper-entity markdown.
_SIDECAR_SUFFIXES = (".source.md",)


@dataclass(frozen=True)
class ResolvedPaper:
    citekey: str
    path: Path
    directory: Path
    doi: str | None  # normalized doi from the entity frontmatter (may differ from the input)
    pmid: str | None  # normalized pmid from the entity frontmatter


def _paper_dirs(project_root: Path) -> list[Path]:
    """Directories that may hold paper-entity markdown in this project.

    `resolve_path_policy("paper")` is NOT usable here: `paper` is a builtin kind, so
    the policy table always returns `entities/papers` (builtins win the merge in
    `entity_policies`, and a project-local `papers` home is rejected as a core-dir
    collision). Real checkouts store paper summaries under any of the canonical
    paper subdirs — this meta checkout uses `doc/background/papers/`. Reuse the one
    authoritative list (`PROMOTE_KIND_PAPER.source_subdirs`) so resolution and
    promotion never diverge.
    """
    return [project_root / sub for sub in PROMOTE_KIND_PAPER.source_subdirs]


def resolve_paper_entity(
    project_root: Path, *, doi: str | None, pmid: str | None
) -> ResolvedPaper:
    """Map a pmid|doi to the paper entity (citekey + directory).

    Scans paper-entity frontmatter under the kind's resolved home, matching a
    normalized doi/pmid. No match -> SourceTextError (actionable). Two entities
    claiming the same identifier -> SourceTextError naming both files.
    """
    want_doi = normalize_doi(doi)
    want_pmid = normalize_pmid(pmid)
    if not want_doi and not want_pmid:
        raise SourceTextError(
            "persist-source requires a DOI or PMID to resolve a paper entity."
        )

    # Each match carries the entity's own normalized identifiers so acquisition can
    # use the entity's PMID even when the user invoked persist-source with a DOI.
    paper_dirs = _paper_dirs(project_root)
    matches: list[tuple[Path, str | None, str | None]] = []
    for root in paper_dirs:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            if any(path.name.endswith(sfx) for sfx in _SIDECAR_SUFFIXES):
                continue
            fm = raw_frontmatter(path)
            entity_doi = normalize_doi(_as_str(fm.get("doi")))
            entity_pmid = normalize_pmid(_as_str(fm.get("pmid")))
            if (want_doi and entity_doi == want_doi) or (
                want_pmid and entity_pmid == want_pmid
            ):
                matches.append((path, entity_doi, entity_pmid))

    ident = want_doi or want_pmid
    if not matches:
        searched = ", ".join(str(d) for d in paper_dirs)
        raise SourceTextError(
            f"no paper entity has doi/pmid {ident!r} under any of {searched}; "
            "run `science paper-fetch` and create the paper entity first."
        )
    if len(matches) > 1:
        named = ", ".join(str(p) for p, _d, _p in matches)
        raise SourceTextError(
            f"multiple paper entities claim doi/pmid {ident!r}: {named}. "
            "This is a data error; fix the duplicate before persisting source text."
        )
    path, entity_doi, entity_pmid = matches[0]
    return ResolvedPaper(
        citekey=path.stem, path=path, directory=path.parent, doi=entity_doi, pmid=entity_pmid
    )


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return str(value)
    return None
