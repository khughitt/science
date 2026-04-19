from __future__ import annotations

from science_model.aspects import KNOWN_ASPECTS


def test_known_aspects_matches_science_yaml_schema() -> None:
    assert KNOWN_ASPECTS == frozenset(
        {
            "causal-modeling",
            "hypothesis-testing",
            "computational-analysis",
            "software-development",
        }
    )
