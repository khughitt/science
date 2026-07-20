"""Promoting a paper mints a canonical id in a GLOBAL namespace. Before that
mint, look at what else already owns the id in other registered projects.

Two silent failure modes this closes, both invisible at promote time and only
surfacing later as errors in a repo the operator never touched:

- Collision (fb-2026-07-11-018). A DIFFERENT paper already owns the citekey
  elsewhere. Promoting science-meta's Liu2025 ("drug synergy") minted
  `paper:Liu2025` and shadowed natural-systems' Liu2025 (a GNN paper) and
  multiple-myeloma's Liu2025 (single-cell 3D genomes); their refs then resolved
  to the wrong paper's content. Author+year citekeys collide by construction
  (Liu, Wang, Zhang), so this recurs.

- Orphan (fb-2026-07-16-004). The SAME paper is owned locally elsewhere and was
  not named in --from. Promoting from `--from meta` while cbioportal
  independently owned the same three papers turned 22 of cbioportal's bare refs
  into ambiguous_reference errors.

The two are told apart by the paper's identity, DOI first (authoritative) and
title second: a differing identity is a collision (disambiguate the citekey); a
matching one is an orphan (add the project to --from, which converts its local
owner to an overlay in the same operation).

This module only observes. It reads frontmatter and classifies; the caller
decides whether to refuse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from science_tool.markdown_utils import frontmatter_span

FederationConflictKind = Literal["shadows-distinct-paper", "orphans-local-owner"]


@dataclass(frozen=True)
class ForeignOwner:
    canonical_id: str
    project_name: str
    conflict: FederationConflictKind


_DOI_PREFIX = re.compile(r"^(?:https?://)?(?:dx\.)?doi\.org/", re.IGNORECASE)
_WS = re.compile(r"\s+")


def _norm_doi(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _DOI_PREFIX.sub("", value.strip()).casefold()


def _norm_title(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _WS.sub(" ", value.strip()).casefold()


def classify_foreign_owner(
    *,
    promoted: Mapping[str, Any],
    foreign: Mapping[str, Any],
) -> FederationConflictKind:
    """Decide whether a same-id foreign owner is the same paper or a distinct one.

    DOI is authoritative when both sides carry one; otherwise fall back to the
    (always-present, per the base schema) title. When neither can be compared,
    return the conservative verdict — a distinct paper the operator should
    disambiguate rather than silently converge.
    """
    promoted_doi, foreign_doi = _norm_doi(promoted.get("doi")), _norm_doi(foreign.get("doi"))
    if promoted_doi and foreign_doi:
        return "orphans-local-owner" if promoted_doi == foreign_doi else "shadows-distinct-paper"

    promoted_title, foreign_title = _norm_title(promoted.get("title")), _norm_title(foreign.get("title"))
    if promoted_title and foreign_title:
        return "orphans-local-owner" if promoted_title == foreign_title else "shadows-distinct-paper"

    return "shadows-distinct-paper"


def _iter_local_paper_owners(root: Path) -> Iterable[tuple[str, dict]]:
    """Yield (canonical_id, frontmatter) for each locally-OWNED paper.

    A file carrying `overlay_of` borrows a commons canonical; it is not an owner
    and is not at risk from a mint, so it is skipped.
    """
    papers = root / "entities" / "papers"
    if not papers.is_dir():
        return
    for path in sorted(papers.glob("*.md")):
        frontmatter, _ = frontmatter_span(path)
        if not frontmatter or "overlay_of" in frontmatter:
            continue
        canonical_id = frontmatter.get("id")
        if isinstance(canonical_id, str) and canonical_id:
            yield canonical_id, frontmatter


def read_owned_paper_frontmatter(root: Path, canonical_id: str) -> dict | None:
    """The frontmatter of the paper this project OWNS under `canonical_id`, if any."""
    wanted = canonical_id.strip().casefold()
    for owned_id, frontmatter in _iter_local_paper_owners(root):
        if owned_id.strip().casefold() == wanted:
            return frontmatter
    return None


def scan_foreign_owners(
    *,
    promoted: Mapping[str, Mapping[str, Any]],
    other_projects: Iterable[tuple[str, Path]],
) -> list[ForeignOwner]:
    """Find projects that locally own an id being minted.

    `promoted` maps each canonical id about to be MINTED to the promoted paper's
    frontmatter (for the same-vs-distinct comparison). `other_projects` is the
    registered set MINUS the --from projects — the bystanders that a mint can
    break. Matching is case-insensitive on the id.
    """
    wanted = {canonical_id.strip().casefold(): canonical_id for canonical_id in promoted}
    owners: list[ForeignOwner] = []
    for project_name, root in other_projects:
        for owned_id, foreign_fm in _iter_local_paper_owners(root):
            canonical_id = wanted.get(owned_id.strip().casefold())
            if canonical_id is None:
                continue
            owners.append(
                ForeignOwner(
                    canonical_id=canonical_id,
                    project_name=project_name,
                    conflict=classify_foreign_owner(
                        promoted=promoted[canonical_id], foreign=foreign_fm
                    ),
                )
            )
    owners.sort(key=lambda owner: (owner.canonical_id, owner.project_name))
    return owners


def format_foreign_owners(owners: Iterable[ForeignOwner]) -> list[str]:
    """Render the finding as display lines. Presentation-only; no click dependency."""
    owners = list(owners)
    shadow = [owner for owner in owners if owner.conflict == "shadows-distinct-paper"]
    orphan = [owner for owner in owners if owner.conflict == "orphans-local-owner"]
    lines: list[str] = []
    if shadow:
        lines.append(
            "! promote would MINT canonical ids that shadow DIFFERENT papers already owned elsewhere:"
        )
        for owner in shadow:
            lines.append(f"    {owner.canonical_id}  is a different paper in  {owner.project_name}")
        lines.append("  Minting these makes that project's refs resolve to the wrong paper.")
        lines.append("  Fix: disambiguate the citekey (rename one side) before promoting.")
    if orphan:
        lines.append("! promote would orphan local owners in projects not in --from:")
        for owner in orphan:
            lines.append(f"    {owner.canonical_id}  also owned by  {owner.project_name}")
        lines.append("  Their bare refs become ambiguous once commons owns these ids.")
        lines.append(
            "  Fix: add each project to --from (converts its owner to an overlay in this same "
            "operation), or convert it first."
        )
    return lines
