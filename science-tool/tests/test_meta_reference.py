"""Contract tests for the meta: ref prefix.

A `meta:<anything>` ref is intentional metadata: preserved in source files,
ignored by audit (no error if no matching entity), and never materialized
as a KG edge.
"""

from __future__ import annotations

from science_tool.graph.sources import is_metadata_reference


class TestIsMetadataReference:
    def test_meta_prefix_recognized(self) -> None:
        assert is_metadata_reference("meta:phase3b") is True
        assert is_metadata_reference("meta:cycle1") is True
        assert is_metadata_reference("meta:") is True

    def test_other_prefixes_not_metadata(self) -> None:
        assert is_metadata_reference("topic:genomics") is False
        assert is_metadata_reference("hypothesis:h01") is False
        assert is_metadata_reference("task:t001") is False

    def test_no_prefix_not_metadata(self) -> None:
        assert is_metadata_reference("genomics") is False
        assert is_metadata_reference("") is False

    def test_meta_in_middle_not_metadata(self) -> None:
        # The prefix check must be at the start
        assert is_metadata_reference("topic:meta:foo") is False
