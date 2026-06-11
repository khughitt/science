from pathlib import Path

from science_tool.qa_audit.runs import load_runs, chain_depth


def _run(dirpath: Path, slug, workflow, supersedes=None, manifest_path="results/x/datapackage.yaml"):
    fm = [
        "---",
        f'id: "workflow-run:{slug}"',
        'type: "workflow-run"',
        f'workflow: "{workflow}"',
        f'manifest_path: "{manifest_path}"',
    ]
    if supersedes:
        fm.append(f'supersedes: ["workflow-run:{supersedes}"]')
    fm += ["---", "", "body"]
    (dirpath / f"{slug}.md").write_text("\n".join(fm))


def test_load_runs_parses_frontmatter(tmp_path):
    _run(tmp_path, "r1", "wf-a")
    runs = load_runs(tmp_path)
    assert runs[0].run_id == "workflow-run:r1"
    assert runs[0].workflow == "wf-a"
    assert runs[0].manifest_path == "results/x/datapackage.yaml"
    assert runs[0].error is None


def test_missing_manifest_path_marks_error(tmp_path):
    (tmp_path / "bad.md").write_text('---\nid: "workflow-run:bad"\ntype: "workflow-run"\nworkflow: "wf-a"\n---\n')
    runs = load_runs(tmp_path)
    assert runs[0].error is not None


def test_chain_depth_counts_supersession(tmp_path):
    _run(tmp_path, "r1", "wf-a")
    _run(tmp_path, "r2", "wf-a", supersedes="r1")
    _run(tmp_path, "r3", "wf-a", supersedes="r2")
    runs = load_runs(tmp_path)
    assert chain_depth(runs, "wf-a") == 3


def test_chain_depth_single_run(tmp_path):
    _run(tmp_path, "r1", "wf-a")
    assert chain_depth(load_runs(tmp_path), "wf-a") == 1
