from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity, ValidateContext


def _ctx(root: Path, committed_id: str | None) -> ValidateContext:
    root.mkdir(parents=True, exist_ok=True)
    lines = ["name: demo", "profile: research"]
    if committed_id is not None:
        lines.append(f"id: {committed_id}")
    root.joinpath("science.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_registry(config_dir: Path, *, path: Path, registry_id: str | None) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    entry = [
        f"    - path: {path}",
        "      name: demo",
        '      registered: "2026-01-01"',
    ]
    if registry_id is not None:
        entry.append(f"      id: {registry_id}")
    config_dir.joinpath("config.yaml").write_text(
        "projects:\n" + "\n".join(line[2:] for line in entry) + "\n",
        encoding="utf-8",
    )


def _warnings(results: Iterable[Result]) -> list[str]:
    return [r.message for r in results if r.severity is Severity.WARN]


def test_divergent_registry_id_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A committed id that differs from the registry entry must warn (fb-2026-05-29-005)."""
    from science_tool.validate.checks.registration_consistency import check_registration_consistency

    project = tmp_path / "project"
    config_dir = tmp_path / "cfg"
    ctx = _ctx(project, committed_id="meta")
    _write_registry(config_dir, path=project.resolve(), registry_id="cancer-meta")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    warnings = _warnings(check_registration_consistency(ctx))
    assert len(warnings) == 1
    assert "meta" in warnings[0] and "cancer-meta" in warnings[0]


def test_matching_registry_id_does_not_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.registration_consistency import check_registration_consistency

    project = tmp_path / "project"
    config_dir = tmp_path / "cfg"
    ctx = _ctx(project, committed_id="meta")
    _write_registry(config_dir, path=project.resolve(), registry_id="meta")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    assert _warnings(check_registration_consistency(ctx)) == []


def test_unregistered_project_does_not_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.registration_consistency import check_registration_consistency

    project = tmp_path / "project"
    config_dir = tmp_path / "cfg"
    ctx = _ctx(project, committed_id="meta")
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.joinpath("config.yaml").write_text("projects: []\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    assert _warnings(check_registration_consistency(ctx)) == []


def test_no_committed_id_does_not_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.registration_consistency import check_registration_consistency

    project = tmp_path / "project"
    config_dir = tmp_path / "cfg"
    ctx = _ctx(project, committed_id=None)
    _write_registry(config_dir, path=project.resolve(), registry_id="cancer-meta")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    assert _warnings(check_registration_consistency(ctx)) == []
