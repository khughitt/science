import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.qa_audit.cli import qa_audit_command


def _setup(tmp_path: Path):
    runs_dir = tmp_path / "entities" / "workflow-runs"
    runs_dir.mkdir(parents=True)
    run_dir = tmp_path / "results" / "wf-a"
    run_dir.mkdir(parents=True)
    (run_dir / "qa_report.json").write_text(json.dumps(
        {"flags": [{"flag_id": "scrna/threshold/pct_counts_mt/max", "severity": "distribution"}]}))
    (run_dir / "datapackage.yaml").write_text(yaml.safe_dump(
        {"name": "run", "resources": [{"name": "qa_report", "path": "qa_report.json"}]}))
    (runs_dir / "r1.md").write_text(
        '---\nid: "workflow-run:r1"\ntype: "workflow-run"\nworkflow: "wf-a"\n'
        f'manifest_path: "{run_dir / "datapackage.yaml"}"\n---\nbody\n')


def test_cli_prints_table_and_exits_zero(tmp_path):
    _setup(tmp_path)
    result = CliRunner().invoke(
        qa_audit_command,
        ["--runs-dir", str(tmp_path / "entities" / "workflow-runs"), "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "wf-a" in result.output
    assert "IGNORED" in result.output


def test_cli_json_output(tmp_path):
    _setup(tmp_path)
    result = CliRunner().invoke(
        qa_audit_command,
        ["--runs-dir", str(tmp_path / "entities" / "workflow-runs"), "--repo-root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert rows[0]["workflow"] == "wf-a"
