from pathlib import Path

import pytest

from science_tool.graph.io import build_input_manifest


def _seed_project(root: Path, science_yaml: str) -> None:
    (root / "science.yaml").write_text(science_yaml, encoding="utf-8")
    (root / "doc" / "reports").mkdir(parents=True)
    (root / "doc" / "reports" / "health-report.json").write_text('{"generated": true}\n', encoding="utf-8")
    (root / "doc" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (root / "knowledge").mkdir()


def test_build_input_manifest_excludes_configured_generated_report(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - doc/reports/health-report.json\n",
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "doc/notes.md" in manifest
    assert "doc/reports/health-report.json" not in manifest


def test_build_input_manifest_excludes_configured_wildcard_report_pattern(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - doc/reports/*.json\n",
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "doc/notes.md" in manifest
    assert "doc/reports/health-report.json" not in manifest


def test_build_input_manifest_keeps_report_without_configured_exclude(tmp_path: Path) -> None:
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "doc/reports/health-report.json" in manifest


def test_build_input_manifest_rejects_absolute_exclude_pattern(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - /tmp/outside.json\n",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")


@pytest.mark.parametrize(
    "entry",
    [
        '    - ""\n',
        "    - 12\n",
        "    - ../outside.json\n",
    ],
)
def test_build_input_manifest_rejects_invalid_exclude_pattern_entries(tmp_path: Path, entry: str) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        f"{entry}",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")


def test_build_input_manifest_rejects_falsy_non_list_exclude_config(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes: false\n",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")
