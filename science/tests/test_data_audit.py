# science/tests/test_data_audit.py
"""Detection pass for `science data audit`."""
import json
import subprocess
from pathlib import Path

from science_tool.data_audit import (
    Quadrant,
    audit_project,
    location,
    propose_results_target,
    render_json,
)
from science_tool.data_worktree import DEFAULT_DATA_DIRS


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_location_classification():
    assert location(Path("data/processed/x/a.md"), DEFAULT_DATA_DIRS) == "DATA"
    assert location(Path("results/exp/a.md"), DEFAULT_DATA_DIRS) == "RESULTS"
    assert location(Path("entities/datasets/a.md"), DEFAULT_DATA_DIRS) == "ENTITIES"
    assert location(Path("doc/x.md"), DEFAULT_DATA_DIRS) == "TRACKED_OTHER"


def test_propose_target_uses_first_segment(tmp_path: Path):
    target = propose_results_target(
        tmp_path, Path("data/processed/exp1/RESULTS.md"), DEFAULT_DATA_DIRS
    )
    assert target == "results/exp1/RESULTS.md"


def test_propose_target_prefers_datapackage_workflow(tmp_path: Path):
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           b"workflow: workflow:myflow\nname: x\n")
    target = propose_results_target(
        tmp_path, Path("data/processed/exp1/RESULTS.md"), DEFAULT_DATA_DIRS
    )
    assert target == "results/myflow/RESULTS.md"


def test_stranded_record_detected(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# results\n")  # untracked
    violations = audit_project(tmp_path)
    stranded = [v for v in violations if v.quadrant is Quadrant.STRANDED_RECORD]
    assert len(stranded) == 1
    assert stranded[0].path == "data/processed/exp1/RESULTS.md"
    assert stranded[0].proposed_target == "results/exp1/RESULTS.md"


def test_leaked_payload_detected_only_when_tracked(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "entities/x/big.feather", b"\x00" * 32)
    # Untracked → not yet a violation.
    assert not [v for v in audit_project(tmp_path)
                if v.quadrant is Quadrant.LEAKED_PAYLOAD]
    subprocess.run(["git", "add", "-f", "entities/x/big.feather"], cwd=tmp_path, check=True)
    leaked = [v for v in audit_project(tmp_path) if v.quadrant is Quadrant.LEAKED_PAYLOAD]
    assert len(leaked) == 1
    assert leaked[0].path == "entities/x/big.feather"


def test_unknown_small_is_flag_quadrant(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/scratch.csv", b"a,b\n1,2\n")
    flags = [v for v in audit_project(tmp_path) if v.quadrant is Quadrant.FLAG]
    assert any(v.path.endswith("scratch.csv") for v in flags)


def test_compliant_files_yield_no_violation(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "results/exp1/RESULTS.md", b"# ok\n")          # record, tracked-side
    _write(tmp_path, "data/processed/exp1/m.feather", b"\x00" * 16)  # payload, ignored-side
    assert audit_project(tmp_path) == []


def test_render_json_shape(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    payload = json.loads(render_json(audit_project(tmp_path)))
    assert payload["version"] == 1
    v = payload["violations"][0]
    assert v["quadrant"] == "stranded_record"
    assert v["target"] == "results/exp1/RESULTS.md"
    assert v["action"] == "move"  # planned action reported in read-only mode
    assert v["performed"] is False


def test_render_json_datapackage_planned_action(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           b"name: x\nresources:\n- {name: m, path: matrix.feather}\n")
    payload = json.loads(render_json(audit_project(tmp_path)))
    dp_row = [r for r in payload["violations"] if r["path"].endswith("datapackage.yaml")][0]
    assert dp_row["action"] == "move+rewrite-resources"
    assert dp_row["performed"] is False


def test_record_directly_under_data_dir_has_no_target(tmp_path: Path):
    # No experiment subfolder under data/processed → ambiguous → no proposed target.
    target = propose_results_target(
        tmp_path, Path("data/processed/RESULTS.md"), DEFAULT_DATA_DIRS
    )
    assert target is None


def test_single_segment_with_workflow_sibling_resolves(tmp_path: Path):
    _write(tmp_path, "data/processed/datapackage.yaml", b"workflow: workflow:flowX\n")
    target = propose_results_target(
        tmp_path, Path("data/processed/datapackage.yaml"), DEFAULT_DATA_DIRS
    )
    assert target == "results/flowX/datapackage.yaml"


def test_stranded_record_directly_under_data_dir_flag_action(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/README.md", b"# top\n")
    import json as _json
    payload = _json.loads(render_json(audit_project(tmp_path)))
    row = [r for r in payload["violations"] if r["path"] == "data/processed/README.md"][0]
    assert row["quadrant"] == "stranded_record"
    assert row["target"] is None
    assert row["action"] == "flag"  # read-only parity: fixer can't propose a target


def test_tracked_payload_inside_data_flagged(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/big.feather", b"\x00" * 32)  # PAYLOAD by ext
    # Untracked payload under data/ → no violation (the normal, healthy case).
    assert not [v for v in audit_project(tmp_path)
                if v.quadrant is Quadrant.TRACKED_PAYLOAD]
    # Track it → TRACKED_PAYLOAD violation, report-only (no move target).
    subprocess.run(["git", "add", "-f", "data/processed/exp1/big.feather"],
                   cwd=tmp_path, check=True)
    tracked = [v for v in audit_project(tmp_path)
               if v.quadrant is Quadrant.TRACKED_PAYLOAD]
    assert len(tracked) == 1
    assert tracked[0].path == "data/processed/exp1/big.feather"
    assert tracked[0].proposed_target is None
    # Stable JSON contract surfaces it as a report-only "flag" action.
    payload = json.loads(render_json(tracked))
    assert payload["violations"][0]["quadrant"] == "tracked_payload"
    assert payload["violations"][0]["action"] == "flag"
    assert payload["violations"][0]["performed"] is False


def test_audit_notes_report_external_data_root(monkeypatch, tmp_path: Path) -> None:
    from science_tool.data_audit import audit_project, audit_project_notes

    external = tmp_path / "external-data"
    (tmp_path / "science.yaml").write_text(
        f"name: Demo\nid: demo\ndata:\n  root: {external}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert audit_project(tmp_path) == []
    notes = audit_project_notes(tmp_path)
    assert [note.code for note in notes] == ["external-data-root"]
    assert str(external) in notes[0].message


def test_render_json_includes_notes_only_when_present() -> None:
    from science_tool.data_audit import AuditNote, render_json

    assert "notes" not in json.loads(render_json([]))
    payload = json.loads(
        render_json(
            [],
            notes=[
                AuditNote(
                    "info",
                    "external-data-root",
                    "external data root: /tmp/x",
                )
            ],
        )
    )
    assert payload["notes"] == [
        {
            "severity": "info",
            "code": "external-data-root",
            "message": "external data root: /tmp/x",
        }
    ]
