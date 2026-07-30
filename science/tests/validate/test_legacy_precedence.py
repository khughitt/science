from pathlib import Path

from science_tool.validate.runner import run


def _project(root: Path) -> Path:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")
    return root


def test_no_sidecar_emits_no_removed_finding(tmp_path: Path) -> None:
    result = run(_project(tmp_path), strict=False, verbose=False)
    assert not [item for item in result.results if item.rule_id == "validate.sidecar-removed"]


def test_legacy_bash_sidecar_is_reported_and_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    sidecar = tmp_path / "validate.local.sh"
    sidecar.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    sidecar.chmod(0o755)
    result = run(_project(tmp_path), strict=False, verbose=False)
    findings = [item for item in result.results if item.rule_id == "validate.sidecar-removed"]
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert not marker.exists()
