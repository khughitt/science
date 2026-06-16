"""cluster-digest is an accepted synthesis report_kind (P4)."""
from __future__ import annotations

from science_tool.validate.checks.discussions import _VALID_SYNTHESIS_KINDS


def test_cluster_digest_is_a_valid_report_kind() -> None:
    assert "cluster-digest" in _VALID_SYNTHESIS_KINDS
