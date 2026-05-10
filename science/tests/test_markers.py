"""Unit tests for science_tool.markers."""
from pathlib import Path

import pytest

from science_tool.markers import (
    DEFAULT_SEVERITY,
    LEGACY_ALIASES,
    TOKENS,
    MarkerHit,
    severity_for,
)


def test_tokens_are_the_four_canonical_names() -> None:
    assert TOKENS == ("UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE")


def test_default_severity_table() -> None:
    assert DEFAULT_SEVERITY == {
        "UNVERIFIED": "warn",
        "MISSING_CITATION": "warn",
        "SPECULATION": "info",
        "INACCESSIBLE": "info",
    }


def test_legacy_alias_maps_needs_citation_to_missing_citation() -> None:
    assert LEGACY_ALIASES == {"NEEDS CITATION": "MISSING_CITATION"}


def test_severity_for_warn_token_default() -> None:
    assert severity_for("UNVERIFIED", strict=False) == "warn"
    assert severity_for("MISSING_CITATION", strict=False) == "warn"


def test_severity_for_info_token_default() -> None:
    assert severity_for("SPECULATION", strict=False) == "info"
    assert severity_for("INACCESSIBLE", strict=False) == "info"


def test_severity_for_strict_promotes_info_to_warn() -> None:
    assert severity_for("SPECULATION", strict=True) == "warn"
    assert severity_for("INACCESSIBLE", strict=True) == "warn"


def test_severity_for_strict_keeps_warn_as_warn() -> None:
    assert severity_for("UNVERIFIED", strict=True) == "warn"


def test_marker_hit_is_frozen_dataclass() -> None:
    hit = MarkerHit(
        file=Path("doc/x.md"),
        line=10,
        token="UNVERIFIED",
        severity="warn",
        in_documentation=False,
        legacy=False,
    )
    with pytest.raises(Exception):
        hit.line = 11  # type: ignore[misc]
