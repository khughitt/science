"""End-to-end: plan-pipeline Step 2b with mixed-origin inputs."""

from __future__ import annotations

from pathlib import Path

from science_tool.plan_gate import check_inputs


def _seed_mixed_inputs(root: Path) -> None:
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "ext_ok.md").write_text(
        '---\nid: "dataset:ext_ok"\ntype: "dataset"\ntitle: "OK"\norigin: "external"\n'
        'datapackage: "data/ext_ok/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        "---\n",
        encoding="utf-8",
    )
    (root / "doc" / "datasets" / "ext_bad.md").write_text(
        '---\nid: "dataset:ext_bad"\ntype: "dataset"\ntitle: "BAD"\norigin: "external"\n'
        'access: {level: "controlled", verified: false}\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "WF r1"\n'
        'workflow: "workflow:wf"\nproduces: ["dataset:der_ok"]\ninputs: ["dataset:ext_ok"]\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "datasets" / "der_ok.md").write_text(
        '---\nid: "dataset:der_ok"\ntype: "dataset"\ntitle: "DerOK"\norigin: "derived"\n'
        'datapackage: "results/wf/r1/out/datapackage.yaml"\n'
        "derivation:\n"
        '  workflow: "workflow:wf"\n'
        '  workflow_run: "workflow-run:wf-r1"\n'
        '  git_commit: "abc"\n'
        '  config_snapshot: "c"\n'
        '  produced_at: "2026-04-19T00:00:00Z"\n'
        '  inputs: ["dataset:ext_ok"]\n---\n',
        encoding="utf-8",
    )


def test_step2b_passes_for_verified_inputs(tmp_path: Path) -> None:
    """Ext-OK + Der-OK with clean upstream both PASS the gate."""
    _seed_mixed_inputs(tmp_path)
    pass_, halts = check_inputs(tmp_path, ["dataset:ext_ok", "dataset:der_ok"])
    assert pass_ is True, halts
    assert halts == []


def test_step2b_halts_on_unverified_external(tmp_path: Path) -> None:
    _seed_mixed_inputs(tmp_path)
    pass_, halts = check_inputs(tmp_path, ["dataset:ext_bad"])
    assert pass_ is False
    assert any("ext_bad" in h for h in halts)
