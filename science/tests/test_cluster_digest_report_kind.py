"""Accepted synthesis report_kind values include generated and batch roles."""
from __future__ import annotations

from science_tool.validate.checks.discussions import _VALID_SYNTHESIS_KINDS


def test_cluster_digest_is_a_valid_report_kind() -> None:
    assert "cluster-digest" in _VALID_SYNTHESIS_KINDS


def test_paper_batch_synthesis_is_a_valid_report_kind() -> None:
    assert "paper-batch-synthesis" in _VALID_SYNTHESIS_KINDS
