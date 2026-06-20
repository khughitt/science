"""Tests for sibling <patch>.layout.yaml separation (Task 5e).

Verifies:
- LayoutFile / NodeLayout data round-trips via load_layout + its own YAML serialize.
- WorkbenchRow / WorkbenchFile reject layout keys (x, y, layout, position) via
  extra="forbid" — layout cannot leak into epistemic content.
- serialize_canonical(compile(W)) is identical whether or not a sibling layout
  file exists / regardless of its contents — layout is not an input to
  compile/serialize.
- load_layout on a missing file returns an empty LayoutFile (no crash).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from science_tool.dag.workbench import (
    LayoutFile,
    NodeLayout,
    WorkbenchFile,
    WorkbenchRow,
    compile_workbench,
    load_layout,
    serialize_canonical,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: layout-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


def _minimal_workbench() -> WorkbenchFile:
    return WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:CCND1",
                predicate="affects",
                object="outcome:proliferation",
                polarity="positive",
                patch="p-layout",
            )
        ]
    )


# ---------------------------------------------------------------------------
# 1. Layout data round-trip via load_layout
# ---------------------------------------------------------------------------


def test_layout_roundtrip(tmp_path: Path) -> None:
    """Write a <patch>.layout.yaml, load_layout returns the correct positions."""
    layout_path = tmp_path / "p-layout.layout.yaml"
    data = {
        "nodes": {
            "proposition:ccnd1-affects-outcome-proliferation": {"x": 120.5, "y": -30.0},
            "proposition:some-other": {"x": 0.0, "y": 200.0, "pinned": True},
        }
    }
    layout_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    lf = load_layout(layout_path)

    assert isinstance(lf, LayoutFile)
    node1 = lf.nodes["proposition:ccnd1-affects-outcome-proliferation"]
    assert node1.x == pytest.approx(120.5)
    assert node1.y == pytest.approx(-30.0)
    assert node1.pinned is False  # default

    node2 = lf.nodes["proposition:some-other"]
    assert node2.x == pytest.approx(0.0)
    assert node2.y == pytest.approx(200.0)
    assert node2.pinned is True


def test_layout_own_roundtrip(tmp_path: Path) -> None:
    """LayoutFile serialized back to YAML and re-parsed survives intact."""
    layout_path = tmp_path / "test.layout.yaml"
    lf = LayoutFile(
        nodes={
            "proposition:abc": NodeLayout(x=1.0, y=2.0, pinned=True),
            "proposition:def": NodeLayout(x=-5.5, y=99.9),
        }
    )
    # Serialize to YAML and write
    layout_path.write_text(
        yaml.safe_dump(lf.model_dump(mode="python"), sort_keys=False),
        encoding="utf-8",
    )
    # Re-parse
    lf2 = load_layout(layout_path)
    assert lf2.nodes["proposition:abc"].x == pytest.approx(1.0)
    assert lf2.nodes["proposition:abc"].pinned is True
    assert lf2.nodes["proposition:def"].y == pytest.approx(99.9)


# ---------------------------------------------------------------------------
# 2. Layout keys are rejected from WorkbenchRow / WorkbenchFile
# ---------------------------------------------------------------------------


def test_workbench_row_rejects_x() -> None:
    """x (cosmetic coord) must be rejected by WorkbenchRow.extra='forbid'."""
    with pytest.raises(ValidationError):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:CCND1",
                "predicate": "affects",
                "object": "outcome:proliferation",
                "patch": "p001",
                "x": 42.0,
            }
        )


def test_workbench_row_rejects_y() -> None:
    with pytest.raises(ValidationError):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:CCND1",
                "predicate": "affects",
                "object": "outcome:proliferation",
                "patch": "p001",
                "y": -10.0,
            }
        )


def test_workbench_row_rejects_layout_key() -> None:
    """A 'layout' mapping at row level must be rejected."""
    with pytest.raises(ValidationError):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:CCND1",
                "predicate": "affects",
                "object": "outcome:proliferation",
                "patch": "p001",
                "layout": {"x": 1.0, "y": 2.0},
            }
        )


def test_workbench_row_rejects_position_key() -> None:
    """A 'position' key at row level must be rejected."""
    with pytest.raises(ValidationError):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:CCND1",
                "predicate": "affects",
                "object": "outcome:proliferation",
                "patch": "p001",
                "position": {"x": 1.0, "y": 2.0},
            }
        )


def test_workbench_file_rejects_layout_top_level() -> None:
    """A 'layout' key at the WorkbenchFile level must be rejected."""
    with pytest.raises(ValidationError):
        WorkbenchFile.model_validate(
            {
                "patch": "p001",
                "rows": [],
                "layout": {"proposition:abc": {"x": 1.0, "y": 2.0}},
            }
        )


# ---------------------------------------------------------------------------
# 3. Canonical text is unaffected by presence/absence/content of layout file
# ---------------------------------------------------------------------------


def test_canonical_unaffected_by_layout_presence(tmp_path: Path) -> None:
    """compile+serialize gives identical text with or without a sibling layout file."""
    _seed_project(tmp_path)

    wb = _minimal_workbench()

    # Compile with no layout file present
    result_no_layout = compile_workbench(wb, project_root=tmp_path)
    text_no_layout = serialize_canonical(result_no_layout)

    # Write a sibling layout file (different location — layout is a sibling
    # conceptually but compile/serialize are layout-blind; just prove text is same)
    layout_path = tmp_path / "p-layout.layout.yaml"
    layout_path.write_text(
        yaml.safe_dump(
            {"nodes": {"proposition:ccnd1-affects-outcome-proliferation": {"x": 99.0, "y": -5.0}}}
        ),
        encoding="utf-8",
    )
    # Layout file now exists — compile+serialize must still produce identical text
    result_with_layout = compile_workbench(wb, project_root=tmp_path)
    text_with_layout = serialize_canonical(result_with_layout)

    assert text_no_layout == text_with_layout


def test_canonical_unaffected_by_layout_content(tmp_path: Path) -> None:
    """Changing layout content does not change canonical workbench text."""
    _seed_project(tmp_path)

    wb = _minimal_workbench()

    layout_path = tmp_path / "p-layout.layout.yaml"

    # Layout A
    layout_path.write_text(
        yaml.safe_dump({"nodes": {"proposition:ccnd1-affects-outcome-proliferation": {"x": 1.0, "y": 1.0}}}),
        encoding="utf-8",
    )
    result_a = compile_workbench(wb, project_root=tmp_path)
    text_a = serialize_canonical(result_a)

    # Layout B — completely different positions
    layout_path.write_text(
        yaml.safe_dump({"nodes": {"proposition:ccnd1-affects-outcome-proliferation": {"x": 999.0, "y": -999.0, "pinned": True}}}),
        encoding="utf-8",
    )
    result_b = compile_workbench(wb, project_root=tmp_path)
    text_b = serialize_canonical(result_b)

    assert text_a == text_b


# ---------------------------------------------------------------------------
# 4. Missing layout file → empty LayoutFile (no crash)
# ---------------------------------------------------------------------------


def test_load_layout_missing_file(tmp_path: Path) -> None:
    """load_layout on a non-existent path returns an empty LayoutFile."""
    missing = tmp_path / "does-not-exist.layout.yaml"
    lf = load_layout(missing)
    assert isinstance(lf, LayoutFile)
    assert lf.nodes == {}


# ---------------------------------------------------------------------------
# 5. NodeLayout rejects unknown keys via extra="forbid"
# ---------------------------------------------------------------------------


def test_node_layout_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        NodeLayout.model_validate({"x": 1.0, "y": 2.0, "color": "red"})


def test_layout_file_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        LayoutFile.model_validate({"nodes": {}, "zoom": 1.5})
