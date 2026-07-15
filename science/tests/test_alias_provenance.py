"""Alias provenance precedence (D5 / design rev 9).

The auto-derivation mints a compact short token for numbered hypothesis/question/task
files -- `question:0004-mega-cluster-split` derives `q04` (strip the leading zeros off
`0004`, prefix `q`). A project that RENUMBERED its questions and kept the old numbers as
authored aliases in `mappings.yaml` (`q04 -> question:0003-...`, because 0003 used to be
Q4) then has two claimants for `q04`: the authored mapping and 0004's derived token.

The authored mapping is an explicit human declaration of what `q04` means in this
project's vocabulary; the derived token is a convenience. So the authored one WINS and
the derived one is omitted -- the graph builds, and `q04` still means what the prose says
it means. Every OTHER cross-target collision still raises `AliasCollisionError`:
canonical-vs-canonical, authored-vs-authored, and archive-token-vs-anything. An archive
token never wins silently, so an archived id can never shadow a live entity's derived
token.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.sources import (
    AliasCollisionError,
    build_alias_map,
    load_project_sources,
)


def _write_question(root: Path, slug: str, *, aliases: list[str] | None = None) -> None:
    frontmatter: dict[str, object] = {
        "id": f"question:{slug}",
        "kind": "question",
        "title": slug,
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "status": "active",
    }
    if aliases:
        frontmatter["aliases"] = aliases
    path = root / "entities" / "questions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n# {slug}\n", encoding="utf-8"
    )


def _write_mappings(root: Path, aliases: dict[str, str]) -> None:
    path = root / "knowledge" / "sources" / "local" / "mappings.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"aliases": aliases}), encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "id": "demo"}), encoding="utf-8"
    )
    return tmp_path


def test_an_AUTHORED_mapping_WINS_over_a_colliding_DERIVED_alias(project: Path) -> None:
    # The protein-landscape shape: 0004 derives q04, mappings.yaml authored q04 -> 0003.
    _write_question(project, "0003-esm2-cath-disagreement")
    _write_question(project, "0004-mega-cluster-split")
    _write_mappings(project, {"q04": "question:0003-esm2-cath-disagreement"})

    sources = load_project_sources(project)
    alias_map = build_alias_map(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
    )

    # authored declaration wins -- q04 means the ESM-2/CATH question, per the prose
    assert alias_map["q04"] == "question:0003-esm2-cath-disagreement"
    # 0004 is NOT lost: it keeps its canonical id and its non-conflicting derived token
    assert alias_map["question:0004-mega-cluster-split"] == "question:0004-mega-cluster-split"
    assert alias_map["q0004"] == "question:0004-mega-cluster-split"


def test_the_whole_renumbered_RANGE_builds_not_just_the_first_collision(project: Path) -> None:
    # The manual map is off-by-one across a range; fixing only q04 would surface q05 next.
    for slug in [
        "0003-esm2-cath-disagreement",
        "0004-mega-cluster-split",
        "0005-dark-protein-novelty-type",
        "0006-dark-protein-rate-drivers",
    ]:
        _write_question(project, slug)
    _write_mappings(
        project,
        {
            "q04": "question:0003-esm2-cath-disagreement",
            "q05": "question:0004-mega-cluster-split",
            "q06": "question:0005-dark-protein-novelty-type",
            "q07": "question:0006-dark-protein-rate-drivers",
        },
    )

    sources = load_project_sources(project)
    alias_map = build_alias_map(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
    )

    assert alias_map["q04"] == "question:0003-esm2-cath-disagreement"
    assert alias_map["q05"] == "question:0004-mega-cluster-split"
    assert alias_map["q06"] == "question:0005-dark-protein-novelty-type"
    assert alias_map["q07"] == "question:0006-dark-protein-rate-drivers"


def test_AUTHORED_vs_AUTHORED_still_RAISES(project: Path) -> None:
    # Two entities each explicitly authoring the SAME frontmatter alias is a real
    # collision -- provenance is equal, so it must NOT be silently resolved.
    _write_question(project, "0001-a", aliases=["question:shared"])
    _write_question(project, "0002-b", aliases=["question:shared"])

    sources = load_project_sources(project)
    with pytest.raises(AliasCollisionError):
        build_alias_map(sources.entities, manual_aliases=sources.manual_aliases)


def test_a_FRONTMATTER_alias_does_NOT_beat_a_colliding_DERIVED_short_id(project: Path) -> None:
    # Only a mappings.yaml mapping suppresses a derived alias. An ENTITY claiming another
    # entity's derived short id via its own `aliases:` is a real ambiguity -> RAISE. This
    # is the line between the two authored sources: external mapping vs self-declaration.
    _write_question(project, "0001-a")  # derives q01
    _write_question(project, "0002-b", aliases=["q01"])  # frontmatter claims q01

    sources = load_project_sources(project)
    with pytest.raises(AliasCollisionError):
        build_alias_map(sources.entities, manual_aliases=sources.manual_aliases)


def test_a_COINCIDENT_authored_token_keeps_FRONTMATTER_provenance_vs_a_mapping(
    project: Path,
) -> None:
    # The provenance hole: `0001-a` derives `q01` AND explicitly authors `q01` in its
    # frontmatter, while mappings.yaml maps `q01` -> a DIFFERENT entity. Reconstructing
    # provenance by token equality would see `q01 in derived(0001-a)` and misclassify the
    # authored token as DERIVED, letting the mapping silently win. Carried provenance keeps
    # it FRONTMATTER, so this is authored-vs-authored -> RAISE.
    _write_question(project, "0001-a", aliases=["q01"])
    _write_question(project, "0002-b")
    _write_mappings(project, {"q01": "question:0002-b"})

    sources = load_project_sources(project)
    with pytest.raises(AliasCollisionError):
        build_alias_map(
            sources.entities,
            manual_aliases=sources.manual_aliases,
            archive_alias_tokens=sources.archive_alias_tokens,
        )


def test_a_MAPPINGS_entry_DOES_beat_the_SAME_derived_short_id(project: Path) -> None:
    # The mirror of the test above: the identical collision, but declared in mappings.yaml
    # instead of frontmatter, resolves silently to the mapping's target.
    _write_question(project, "0001-a")  # derives q01
    _write_question(project, "0002-b")
    _write_mappings(project, {"q01": "question:0002-b"})

    sources = load_project_sources(project)
    alias_map = build_alias_map(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
    )
    assert alias_map["q01"] == "question:0002-b"


def test_an_ARCHIVE_token_NEVER_silently_wins_over_a_DERIVED_alias(project: Path) -> None:
    # An archive token colliding with a live entity's derived alias must RAISE, not be
    # silently overridden either way -- an archived id shadowing a live token is exactly
    # the masking the provenance split guards against.
    _write_question(project, "0004-mega-cluster-split")
    sources = load_project_sources(project)

    with pytest.raises(AliasCollisionError):
        build_alias_map(
            sources.entities,
            manual_aliases={"q04": "question:9999-archived-thing"},
            archive_alias_tokens=frozenset({"q04"}),
        )


def test_an_ARCHIVE_token_vs_an_incompatible_AUTHORED_alias_RAISES(project: Path) -> None:
    # Rule 3: archive token vs incompatible authored alias -> ERROR.
    _write_question(project, "0004-mega-cluster-split", aliases=["legacy-q4"])
    sources = load_project_sources(project)

    with pytest.raises(AliasCollisionError):
        build_alias_map(
            sources.entities,
            manual_aliases={"legacy-q4": "question:9999-archived-thing"},
            archive_alias_tokens=frozenset({"legacy-q4"}),
        )
