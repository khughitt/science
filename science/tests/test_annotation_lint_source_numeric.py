from pathlib import Path
import tempfile

from science_tool.annotation.sources.lint import (
    DETECTOR_VERSIONS,
    lint_source_name,
    numeric_anchor_source,
)


def test_numeric_anchor_detector_version_bumped():
    assert DETECTOR_VERSIONS["numeric-anchor"] == "v2026-07-19"
    assert lint_source_name("numeric-anchor") == "lint:numeric-anchor-v2026-07-19"


def test_numeric_anchor_source_suppresses_bound_claims():
    """Test that bound numeric claims are not flagged by the numeric-anchor adapter."""
    # Create a temporary markdown file with a bound numeric claim
    content = """---
title: Test bound claim suppression
numeric_claims:
  claim1:
    artifact: test-data.json
    locator:
      pointer: /value
---

This is a bound claim: 42%[^claim1] with supporting data.

This is an unbound claim: 3.14 without support.
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()
        temp_path = Path(f.name)

    try:
        rows = list(numeric_anchor_source().scan(temp_path))
        matches = [r.match_text for r in rows]

        # The bound claim (42%) should NOT be flagged
        assert "42%" not in matches, "Bound claim should be suppressed"
        # The unbound claim (3.14) SHOULD be flagged
        assert "3.14" in matches, "Unbound claim should be flagged"
    finally:
        temp_path.unlink()
