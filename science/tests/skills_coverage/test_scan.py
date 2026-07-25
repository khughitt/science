from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.skills_coverage.scan import (
    SkillCoverageScanError,
    scan_portfolio,
    write_report_atomically,
)


def _enrolled_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project

    root.mkdir()
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nentity_schema_version: 3\nskill_coverage:\n  domains:\n    molecular-measurement: enrolled\n",
        encoding="utf-8",
    )


def _out_of_domain_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project

    root.mkdir()
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nskill_coverage:\n  domains:\n    molecular-measurement: out-of-domain\n",
        encoding="utf-8",
    )


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"projects": entries}), encoding="utf-8")
    return config_path


def test_scan_classifies_and_skips(tmp_path: Path) -> None:
    enrolled = tmp_path / "enrolled"
    _enrolled_project(enrolled)
    ood = tmp_path / "ood"
    _out_of_domain_project(ood)
    config_path = _registry(tmp_path, [
        {"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"},
        {"path": str(ood), "name": "ood", "id": "ood", "registered": "2026-07-25"},
        {"path": str(tmp_path / "gone"), "name": "gone", "id": "gone", "registered": "2026-07-25"},
    ])
    report = scan_portfolio(config_path)
    states = {o.to_dict().get("state") for o in report.coverage_occurrences}
    assert "out-of-domain" in states
    assert [s.path for s in report.skipped_projects] == [str(tmp_path / "gone")]
    assert report.scope.mode == "portfolio"


def test_scan_skips_registered_directory_without_science_yaml(tmp_path: Path) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    config_path = _registry(tmp_path, [
        {"path": str(bare), "name": "bare", "id": "bare", "registered": "2026-07-25"},
    ])

    report = scan_portfolio(config_path)

    assert [skipped.to_dict() for skipped in report.skipped_projects] == [
        {"path": str(bare), "reason": "path missing or no science.yaml"}
    ]


def test_scan_empty_registry_is_hard_error(tmp_path: Path) -> None:
    config_path = _registry(tmp_path, [])
    with pytest.raises(SkillCoverageScanError, match="no registered projects"):
        scan_portfolio(config_path)


def test_scan_duplicate_identifier_is_hard_error(tmp_path: Path) -> None:
    a = tmp_path / "a"
    _enrolled_project(a)
    b = tmp_path / "b"
    _enrolled_project(b)
    config_path = _registry(tmp_path, [
        {"path": str(a), "name": "dup", "id": "dup", "registered": "2026-07-25"},
        {"path": str(b), "name": "dup", "id": "dup", "registered": "2026-07-25"},
    ])
    with pytest.raises(SkillCoverageScanError, match="duplicate project identifier"):
        scan_portfolio(config_path)


def test_scan_single_project_scope(tmp_path: Path) -> None:
    enrolled = tmp_path / "enrolled"
    _enrolled_project(enrolled)
    broken = tmp_path / "broken"
    _enrolled_project(broken)
    (broken / "science.yaml").write_text("entity_schema_version: not-an-int\n", encoding="utf-8")
    config_path = _registry(tmp_path, [
        {"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"},
        {"path": str(broken), "name": "broken", "id": "broken", "registered": "2026-07-25"},
    ])
    # --project isolates the good project even though 'broken' has invalid config
    report = scan_portfolio(config_path, only="enrolled")
    assert report.scope.mode == "single-project" and report.scope.project == "enrolled"
    with pytest.raises(SkillCoverageScanError, match="matched no registered project"):
        scan_portfolio(config_path, only="nope")


def test_atomic_write_leaves_target_untouched_on_prior_content(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    target.write_text("PRIOR", encoding="utf-8")
    write_report_atomically(target, "NEW\n")
    assert target.read_text(encoding="utf-8") == "NEW\n"


def test_atomic_write_preserves_preexisting_sibling_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    sibling_temp = tmp_path / "out.json.tmp"
    sibling_temp.write_text("SENTINEL", encoding="utf-8")

    write_report_atomically(target, "NEW\n")

    assert target.read_text(encoding="utf-8") == "NEW\n"
    assert sibling_temp.read_text(encoding="utf-8") == "SENTINEL"


def test_atomic_write_cleans_temp_when_replacement_fails(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    target.mkdir()

    with pytest.raises(OSError):
        write_report_atomically(target, "NEW\n")

    assert target.is_dir()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["out.json"]
