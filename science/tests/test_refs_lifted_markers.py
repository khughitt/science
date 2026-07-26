"""`science refs check` honours a lifted marker, like `validate` already did.

fb-2026-07-26-012: the same marker was adjudicated on one surface and still
counted on the other, so the two reported different totals for one tree.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.refs import check_refs

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


def _project(root: Path) -> None:
    (root / "doc").mkdir(parents=True, exist_ok=True)
    shutil.copy(FX / "mixed-tokens.md", root / "doc" / "mixed-tokens.md")
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")


def _marker_issues(root: Path) -> list:
    return [i for i in check_refs(root) if i.ref_type == "marker"]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    _project(tmp_path)
    return tmp_path


def test_markers_are_reported_before_they_are_lifted(workspace: Path) -> None:
    assert _marker_issues(workspace), "the fixture must actually carry markers"


def test_lifted_markers_are_not_counted_by_refs_check(workspace: Path) -> None:
    before = len(_marker_issues(workspace))
    CliRunner().invoke(
        annotate_group, ["lift-tokens", "--root", str(workspace), "--actor", "tester"]
    )
    after = len(_marker_issues(workspace))
    assert before > 0
    assert after < before, "lifting adjudicated these markers; refs check must stop counting them"


def test_refs_check_and_validate_agree_on_the_same_tree(workspace: Path) -> None:
    """The point of the filing: whichever number is right, one number."""
    from science_tool.markers import scan_markers
    from science_tool.markers_lifted import filter_lifted

    CliRunner().invoke(
        annotate_group, ["lift-tokens", "--root", str(workspace), "--actor", "tester"]
    )
    validate_side = filter_lifted(scan_markers(workspace, strict=False, include_documentation=False))
    refs_side = _marker_issues(workspace)
    assert len(refs_side) == len(validate_side)
