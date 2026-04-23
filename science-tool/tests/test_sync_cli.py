from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_model.identity import ExternalId
from science_tool.registry.config import ensure_registered
from science_tool.cli import main


def _setup_projects(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create two minimal projects and a config."""
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    for proj, name in [(proj_a, "proj-a"), (proj_b, "proj-b")]:
        proj.mkdir()
        (proj / "science.yaml").write_text(f"name: {name}\nknowledge_profiles:\n  local: local\n")
        for d in ("doc", "specs", "tasks", "knowledge"):
            (proj / d).mkdir()

    config_path = tmp_path / "config.yaml"
    return proj_a, proj_b, config_path


def _write_entity_md(
    project_root: Path,
    filename: str,
    entity_id: str,
    entity_type: str,
    title: str,
    *,
    primary_external_id: ExternalId | None = None,
    scope: str | None = None,
) -> None:
    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    primary_block = ""
    if primary_external_id is not None:
        primary_block = (
            "primary_external_id:\n"
            f'  source: "{primary_external_id.source}"\n'
            f'  id: "{primary_external_id.id}"\n'
            f'  curie: "{primary_external_id.curie}"\n'
            f'  provenance: "{primary_external_id.provenance}"\n'
        )
    scope_block = f"scope: {scope}\n" if scope is not None else ""
    (doc_dir / filename).write_text(
        f'---\nid: "{entity_id}"\ntype: {entity_type}\ntitle: "{title}"\n'
        f"{scope_block}{primary_block}related: []\nontology_terms: []\naliases: []\n---\nBody.\n",
        encoding="utf-8",
    )


def test_sync_status_no_config(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "status", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 0
    assert "No sync" in result.output or "never" in result.output.lower()


def test_sync_projects_list(tmp_path):
    config_path = tmp_path / "config.yaml"
    ensure_registered(tmp_path / "proj-a", "proj-a", config_path)
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "projects", "--config", str(config_path)])
    assert result.exit_code == 0
    assert "proj-a" in result.output


def test_sync_run_prints_drift_warnings(tmp_path, monkeypatch):
    proj_a, proj_b, config_path = _setup_projects(tmp_path)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "science-config"))
    shared_id = ExternalId(source="HGNC", id="7157", curie="HGNC:7157", provenance="manual")
    _write_entity_md(
        proj_a,
        "tp53.md",
        "question:tp53",
        "question",
        "TP53",
        primary_external_id=shared_id,
        scope="shared",
    )
    _write_entity_md(
        proj_b,
        "p53.md",
        "question:p53",
        "question",
        "P53",
        primary_external_id=shared_id,
        scope="shared",
    )
    ensure_registered(proj_a, "proj-a", config_path)
    ensure_registered(proj_b, "proj-b", config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "run", "--config", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert "Drift warnings:" in result.output
    assert "primary_external_id collision" in result.output
