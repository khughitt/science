from science_tool.annotation.sources.lint import DETECTOR_VERSIONS, lint_source_name


def test_numeric_anchor_detector_version_bumped():
    assert DETECTOR_VERSIONS["numeric-anchor"] == "v2026-07-18"
    assert lint_source_name("numeric-anchor") == "lint:numeric-anchor-v2026-07-18"
