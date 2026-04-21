from pathlib import Path

import pytest

from science_tool.verdict.registry import load_registry
from science_tool.verdict.rollup import group_by, tally_polarities, walk_interpretations
from science_tool.verdict.tokens import Token


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "verdict"
REGISTRY_PATH = FIXTURE_DIR / "claim-registry.yaml"


def test_walk_interpretations_finds_top_level_happy_path_fixtures() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))

    assert len(results) == 6
    assert "interpretation:fixture-and" in {result.interpretation_id for result in results}


def test_walk_interpretations_is_flat_not_recursive() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))

    interpretation_ids = {result.interpretation_id for result in results}
    assert "interpretation:fixture-malformed" not in interpretation_ids
    assert "interpretation:fixture-unresolved" not in interpretation_ids


def test_walk_interpretations_propagates_malformed_errors() -> None:
    with pytest.raises(ValueError, match="Malformed verdict block"):
        list(walk_interpretations(FIXTURE_DIR / "extras"))


def test_walk_interpretations_skips_frontmatter_without_verdict(tmp_path: Path) -> None:
    path = tmp_path / "without-verdict.md"
    path.write_text(
        """---
id: "interpretation:without-verdict"
---

## Verdict

**Verdict:** [+] This file has frontmatter but no verdict block.
""",
        encoding="utf-8",
    )

    assert list(walk_interpretations(tmp_path)) == []


def test_group_by_all_returns_single_bucket() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))

    groups = group_by(results, scope="all")

    assert list(groups) == ["all"]
    assert len(groups["all"]) == 6


def test_group_by_claim_uses_canonical_claim_ids() -> None:
    registry = load_registry(REGISTRY_PATH)
    results = list(walk_interpretations(FIXTURE_DIR))

    groups = group_by(results, scope="claim", registry=registry)

    assert "h1#edge5-ifn-arm" in groups
    assert [result.interpretation_id for result in groups["h1#edge5-ifn-arm"]] == ["interpretation:fixture-and"]


def test_group_by_claim_requires_registry() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))

    with pytest.raises(ValueError, match="registry"):
        group_by(results, scope="claim", registry=None)


def test_tally_polarities_counts_composites() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))

    tally = tally_polarities(results)

    assert tally[Token.POSITIVE] == 2
    assert tally[Token.MIXED] == 3
    assert tally[Token.NON_ADJUDICATING] == 1
    assert tally[Token.NEGATIVE] == 0
