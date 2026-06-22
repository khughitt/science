import json
from pathlib import Path

import yaml

from science_tool.qa_audit.audit import audit_workflows, render_markdown


def _run(dirpath: Path, slug, workflow, manifest_path, supersedes=None):
    fm = ["---", f'id: "workflow-run:{slug}"', 'type: "workflow-run"',
          f'workflow: "{workflow}"', f'manifest_path: "{manifest_path}"']
    if supersedes:
        fm.append(f'supersedes: ["workflow-run:{supersedes}"]')
    fm += ["---", "", "body"]
    (dirpath / f"{slug}.md").write_text("\n".join(fm))


def _manifest_with_open_flag(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "qa_report.json").write_text(json.dumps(
        {"flags": [{"flag_id": "scrna/threshold/pct_counts_mt/max", "severity": "distribution"}]}))
    (run_dir / "datapackage.yaml").write_text(yaml.safe_dump(
        {"name": "run", "resources": [{"name": "qa_report", "path": "qa_report.json"}]}))
    return run_dir / "datapackage.yaml"


def test_single_run_ignored_is_headline(tmp_path):
    runs_dir = tmp_path / "entities" / "workflow-runs"
    runs_dir.mkdir(parents=True)
    manifest = _manifest_with_open_flag(tmp_path / "results" / "wf-a")
    _run(runs_dir, "r1", "wf-a", str(manifest))
    rows = audit_workflows(runs_dir=runs_dir, repo_root=tmp_path)
    row = next(r for r in rows if r["workflow"] == "wf-a")
    assert row["iteration"] == "SINGLE-RUN"
    assert row["engagement"] == "IGNORED"


def test_missing_manifest_yields_error_row(tmp_path):
    runs_dir = tmp_path / "entities" / "workflow-runs"
    runs_dir.mkdir(parents=True)
    _run(runs_dir, "r1", "wf-a", str(tmp_path / "nope" / "datapackage.yaml"))
    rows = audit_workflows(runs_dir=runs_dir, repo_root=tmp_path)
    assert rows[0]["engagement"] == "ERROR"


def test_render_markdown_has_header_and_rows(tmp_path):
    rows = [{"workflow": "wf-a", "runs": 1, "chain_depth": 1,
             "open_flags": 1, "dispositioned_flags": 0,
             "iteration": "SINGLE-RUN", "engagement": "IGNORED"}]
    md = render_markdown(rows)
    assert "| Workflow |" in md
    assert "wf-a" in md


def test_render_markdown_includes_breadth_column():
    out = render_markdown([{
        "workflow": "wf", "runs": 1, "chain_depth": 1, "open_flags": 0, "dispositioned_flags": 0,
        "iteration": "SINGLE-RUN", "engagement": "NO-FLAGS", "breadth": "5/7",
    }])
    assert "Breadth" in out and "5/7" in out
