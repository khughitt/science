from pathlib import Path

from science_tool.plan_gate import check_reproducibility
from science_tool.project_config import ReproducibilityPolicyConfig, ReproducibilityWaiver


def _write_dataset(root: Path, slug: str, reproducibility: dict | None, *, origin="external"):
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    access = {"level": "controlled", "verified": True}
    if reproducibility is not None:
        access["reproducibility"] = reproducibility
    lines = [
        "---",
        f"id: dataset:{slug}",
        "type: dataset",
        f"title: {slug}",
        f"origin: {origin}",
        "access:",
        f"  level: {access['level']}",
        f"  verified: {str(access['verified']).lower()}",
    ]
    if reproducibility is not None:
        lines.append("  reproducibility:")
        for k, v in reproducibility.items():
            lines.append(f"    {k}: {v}")
    lines += ["---", "", "body", ""]
    (d / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


N3C = {"obtainability": "approved-project", "execution": "trusted-environment", "extractability": "aggregate-reviewed"}
OPEN = {"obtainability": "public", "execution": "local", "extractability": "full-dataset"}
BAR = ReproducibilityPolicyConfig(bar="third-party-reproducible", unknown="halt", below_bar="halt")


def test_absent_policy_emits_nudge_no_enforcement(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    ok, halts, warns = check_reproducibility(tmp_path, ["dataset:n3c"], policy=None)
    assert ok is True and halts == []
    assert any("reproducibility-policy-missing" in w for w in warns)


def test_below_bar_halts(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:n3c"], policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)


def test_meets_bar_passes(tmp_path):
    _write_dataset(tmp_path, "geo", OPEN)
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:geo"], policy=BAR)
    assert ok is True and halts == []


def test_unknown_halts_by_default(tmp_path):
    _write_dataset(tmp_path, "bare", None)
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:bare"], policy=BAR)
    assert ok is False and any("unknown" in h for h in halts)


def test_matching_waiver_passes(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    waiver = ReproducibilityWaiver(dataset="dataset:n3c", accepted_class="trust-based-output")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:n3c"], policy=BAR, waivers=[waiver])
    assert ok is True and halts == []


def test_waiver_for_wrong_class_does_not_apply(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    waiver = ReproducibilityWaiver(dataset="dataset:n3c", accepted_class="insider-only")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:n3c"], policy=BAR, waivers=[waiver])
    assert ok is False  # derived class is trust-based-output, waiver accepted insider-only


def _write_derived(root: Path, slug: str, upstreams: str | list[str]):
    """Write a VALID origin:derived dataset (full DerivationBlock) + its workflow-run."""
    upstream_slugs = [upstreams] if isinstance(upstreams, str) else upstreams
    upstream_ids = [f"dataset:{upstream}" for upstream in upstream_slugs]
    upstreams_yaml = "[" + ", ".join(f'"{upstream_id}"' for upstream_id in upstream_ids) + "]"
    ds = root / "entities" / "datasets"
    wr = root / "entities" / "workflow-runs"
    ds.mkdir(parents=True, exist_ok=True)
    wr.mkdir(parents=True, exist_ok=True)
    run_slug = f"{slug}-r1"
    (wr / f"{run_slug}.md").write_text(
        f'---\nid: "workflow-run:{run_slug}"\ntype: "workflow-run"\ntitle: "WF {slug}"\n'
        f'workflow: "workflow:wf"\nproduces: ["dataset:{slug}"]\ninputs: {upstreams_yaml}\n---\n',
        encoding="utf-8",
    )
    (ds / f"{slug}.md").write_text(
        f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\norigin: "derived"\n'
        'datapackage: "results/wf/r1/out/datapackage.yaml"\n'
        "derivation:\n"
        '  workflow: "workflow:wf"\n'
        f'  workflow_run: "workflow-run:{run_slug}"\n'
        '  git_commit: "abc"\n'
        '  config_snapshot: "c"\n'
        '  produced_at: "2026-04-19T00:00:00Z"\n'
        f"  inputs: {upstreams_yaml}\n---\n",
        encoding="utf-8",
    )


def test_derived_input_inherits_weakest_upstream(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    _write_derived(tmp_path, "derived_ok", "n3c")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:derived_ok"], policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)


def test_convergent_derived_graph_does_not_treat_shared_upstream_as_cycle(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)
    _write_derived(tmp_path, "branch_a", "n3c")
    _write_derived(tmp_path, "branch_b", "n3c")
    _write_derived(tmp_path, "merged", ["branch_a", "branch_b"])

    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:merged"], policy=BAR)

    assert ok is False
    assert any("trust-based-output" in h for h in halts)
    assert not any("cycle" in h for h in halts)
