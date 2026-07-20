"""Promoting a paper must not silently break other registered projects.

Two failure modes, both silent at promote time and only surfacing later in a
different repo:

- fb-2026-07-11-018 (collision). The commons id namespace is global. Promoting
  science-meta's Liu2025 ("drug synergy") minted `paper:Liu2025`, which then
  shadowed natural-systems' Liu2025 (a GNN paper) and multiple-myeloma's Liu2025
  (single-cell 3D genomes). The other projects' refs stopped resolving.

- fb-2026-07-16-004 (orphan). Promoting from `--from meta` while cbioportal
  independently OWNED the same three papers turned cbioportal's 22 bare refs
  into ambiguous_reference errors — 22 hard errors in a project the operator
  never touched.

The distinction is the paper's identity: a DIFFERENT paper under the same
citekey is a collision (disambiguate); the SAME paper owned elsewhere is an
orphan (add it to --from, which converts it to an overlay).
"""

from __future__ import annotations

from pathlib import Path

from science_tool.commons.federation_guard import (
    ForeignOwner,
    classify_foreign_owner,
    read_owned_paper_frontmatter,
    scan_foreign_owners,
)


def _write_paper(root: Path, slug: str, *, doi: str = "", title: str = "", overlay: bool = False) -> None:
    papers = root / "entities" / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"id: paper:{slug}", "kind: paper", f"title: {title or slug}"]
    if doi:
        lines.append(f"doi: {doi}")
    if overlay:
        lines.append(f"overlay_of: paper:{slug}")
        lines.append("pin_version: 1.0.0")
    lines += ["---", "", "## Key Findings", "", "x"]
    papers.joinpath(f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


# ---- classify (pure) -------------------------------------------------------


def test_matching_doi_is_the_same_paper() -> None:
    verdict = classify_foreign_owner(
        promoted={"doi": "10.1/liu", "title": "Drug synergy"},
        foreign={"doi": "10.1/liu", "title": "drug synergy analysis"},
    )
    assert verdict == "orphans-local-owner"


def test_differing_doi_is_a_distinct_paper() -> None:
    verdict = classify_foreign_owner(
        promoted={"doi": "10.1/synergy", "title": "Drug synergy"},
        foreign={"doi": "10.2/gnn", "title": "A GNN model"},
    )
    assert verdict == "shadows-distinct-paper"


def test_doi_comparison_ignores_resolver_prefix_and_case() -> None:
    verdict = classify_foreign_owner(
        promoted={"doi": "https://doi.org/10.1/LIU"},
        foreign={"doi": "10.1/liu"},
    )
    assert verdict == "orphans-local-owner"


def test_falls_back_to_title_when_a_doi_is_absent() -> None:
    assert (
        classify_foreign_owner(
            promoted={"title": "Drug synergy analysis"},
            foreign={"title": "  drug   synergy   analysis "},
        )
        == "orphans-local-owner"
    )
    assert (
        classify_foreign_owner(
            promoted={"title": "Drug synergy"},
            foreign={"title": "A GNN model"},
        )
        == "shadows-distinct-paper"
    )


def test_doi_is_authoritative_over_a_coincidentally_similar_title() -> None:
    """Two different papers can share a title; the DOI settles it."""
    verdict = classify_foreign_owner(
        promoted={"doi": "10.1/a", "title": "Cancer genomics"},
        foreign={"doi": "10.2/b", "title": "Cancer genomics"},
    )
    assert verdict == "shadows-distinct-paper"


def test_insufficient_metadata_is_treated_as_distinct() -> None:
    """Cannot confirm same-paper → the conservative instruction is disambiguate."""
    assert classify_foreign_owner(promoted={}, foreign={}) == "shadows-distinct-paper"


# ---- scan (frontmatter I/O) ------------------------------------------------


def test_scan_flags_a_distinct_paper_under_the_same_citekey(tmp_path: Path) -> None:
    other = tmp_path / "natural-systems"
    _write_paper(other, "Liu2025", doi="10.2/gnn", title="A GNN model")

    owners = scan_foreign_owners(
        promoted={"paper:Liu2025": {"doi": "10.1/synergy", "title": "Drug synergy"}},
        other_projects=[("natural-systems", other)],
    )

    assert owners == [
        ForeignOwner(
            canonical_id="paper:Liu2025",
            project_name="natural-systems",
            conflict="shadows-distinct-paper",
        )
    ]


def test_scan_flags_the_same_paper_owned_elsewhere(tmp_path: Path) -> None:
    other = tmp_path / "cbioportal"
    _write_paper(other, "Haigis2019", doi="10.1/haigis", title="Haigis")

    owners = scan_foreign_owners(
        promoted={"paper:Haigis2019": {"doi": "10.1/haigis", "title": "Haigis"}},
        other_projects=[("cbioportal", other)],
    )

    assert owners == [
        ForeignOwner(
            canonical_id="paper:Haigis2019",
            project_name="cbioportal",
            conflict="orphans-local-owner",
        )
    ]


def test_scan_ignores_overlays_they_already_borrow(tmp_path: Path) -> None:
    """A project that already overlays the commons canonical is not at risk."""
    other = tmp_path / "cbioportal"
    _write_paper(other, "Haigis2019", doi="10.1/haigis", overlay=True)

    owners = scan_foreign_owners(
        promoted={"paper:Haigis2019": {"doi": "10.1/haigis"}},
        other_projects=[("cbioportal", other)],
    )

    assert owners == []


def test_scan_ignores_projects_that_do_not_own_the_id(tmp_path: Path) -> None:
    other = tmp_path / "evolution"
    _write_paper(other, "SomethingElse2020", doi="10.9/other")

    owners = scan_foreign_owners(
        promoted={"paper:Liu2025": {"doi": "10.1/synergy"}},
        other_projects=[("evolution", other)],
    )

    assert owners == []


def test_scan_matches_citekey_case_insensitively(tmp_path: Path) -> None:
    """A bystander owning `paper:liu2025` still collides with a minted `paper:Liu2025`."""
    other = tmp_path / "mm"
    _write_paper(other, "liu2025", doi="10.3/mm", title="3D genomes")

    owners = scan_foreign_owners(
        promoted={"paper:Liu2025": {"doi": "10.1/synergy", "title": "Drug synergy"}},
        other_projects=[("mm", other)],
    )

    assert [o.conflict for o in owners] == ["shadows-distinct-paper"]


def test_scan_reports_every_affected_project(tmp_path: Path) -> None:
    ns = tmp_path / "natural-systems"
    mm = tmp_path / "mm"
    _write_paper(ns, "Liu2025", doi="10.2/gnn")
    _write_paper(mm, "Liu2025", doi="10.3/mm")

    owners = scan_foreign_owners(
        promoted={"paper:Liu2025": {"doi": "10.1/synergy"}},
        other_projects=[("mm", mm), ("natural-systems", ns)],
    )

    assert [o.project_name for o in owners] == ["mm", "natural-systems"]


def test_read_owned_paper_frontmatter_skips_overlays(tmp_path: Path) -> None:
    root = tmp_path / "meta"
    _write_paper(root, "Haigis2019", doi="10.1/haigis", overlay=True)
    assert read_owned_paper_frontmatter(root, "paper:Haigis2019") is None

    _write_paper(root, "Owned2020", doi="10.5/owned", title="Owned")
    fm = read_owned_paper_frontmatter(root, "paper:Owned2020")
    assert fm is not None and fm["doi"] == "10.5/owned"
