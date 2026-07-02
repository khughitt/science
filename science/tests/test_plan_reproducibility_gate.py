from pathlib import Path

from science_tool.plan_gate import check_inputs, check_plan_data_gate, check_reproducibility
from science_tool.project_config import (
    ReproducibilityPolicyConfig,
    ReproducibilityWaiver,
    effective_reproducibility_policy,
    load_plan_reproducibility_policy,
    load_project_config,
)


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


def _write_recipe_derived(root: Path, slug: str, upstreams: str | list[str]):
    """Write a VALID origin:derived dataset using the RECIPE derivation form
    (WorkflowRecipeDerivationBlock: workflow_recipe + inputs, no workflow-run)."""
    upstream_slugs = [upstreams] if isinstance(upstreams, str) else upstreams
    upstream_ids = [f"dataset:{upstream}" for upstream in upstream_slugs]
    upstreams_yaml = "[" + ", ".join(f'"{upstream_id}"' for upstream_id in upstream_ids) + "]"
    ds = root / "entities" / "datasets"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / f"{slug}.md").write_text(
        f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\norigin: "derived"\n'
        'datapackage: "results/wf/r1/out/datapackage.yaml"\n'
        "derivation:\n"
        '  kind: "workflow"\n'
        '  workflow_recipe: "workflow:wf"\n'
        '  recipe_lockfile: "code/workflows/config.yaml"\n'
        f"  inputs: {upstreams_yaml}\n---\n",
        encoding="utf-8",
    )


def test_recipe_derived_input_inherits_upstream_not_unknown(tmp_path):
    # Regression: recipe-provenance (WorkflowRecipeDerivationBlock) derived
    # datasets must inherit their upstream class through the closure, not collapse
    # to `unknown`. Upstream is third-party-reproducible -> the derived dataset
    # inherits it and PASSES (before the fix it halted as unknown).
    _write_dataset(tmp_path, "geo", OPEN)
    _write_recipe_derived(tmp_path, "recipe_derived", "geo")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:recipe_derived"], policy=BAR)
    assert ok is True and halts == []


def test_recipe_derived_inherits_weakest_below_bar_upstream(tmp_path):
    # And when the recipe upstream is below-bar, the derived dataset inherits the
    # below-bar class and halts for that reason (not for `unknown`).
    _write_dataset(tmp_path, "n3c", N3C)
    _write_recipe_derived(tmp_path, "recipe_from_n3c", "n3c")
    ok, halts, _ = check_reproducibility(tmp_path, ["dataset:recipe_from_n3c"], policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)


def test_recipe_derived_passes_access_gate_via_inputs(tmp_path):
    # check_inputs must treat a recipe-provenance derived dataset as ready when
    # its transitive inputs are ready (no workflow-run symmetry required).
    _write_dataset(tmp_path, "geo", OPEN)  # verified=True
    _write_recipe_derived(tmp_path, "recipe_derived_access", "geo")
    ok, halts = check_inputs(tmp_path, ["dataset:recipe_derived_access"])
    assert ok is True and halts == []


def test_verified_but_nonreproducible_passes_access_fails_combined(tmp_path):
    _write_dataset(tmp_path, "n3c", N3C)  # access.verified=True, class trust-based-output
    access_ok, _ = check_inputs(tmp_path, ["dataset:n3c"])
    assert access_ok is True  # access gate ALONE passes a verified dataset
    ok, halts, _ = check_plan_data_gate(tmp_path, ["dataset:n3c"], reproducibility_policy=BAR)
    assert ok is False and any("trust-based-output" in h for h in halts)  # combined gate FAILS


def test_combined_gate_passes_when_reproducible(tmp_path):
    _write_dataset(tmp_path, "geo", OPEN)
    ok, halts, _ = check_plan_data_gate(tmp_path, ["dataset:geo"], reproducibility_policy=BAR)
    assert ok is True and halts == []


def test_end_to_end_plan_waiver_from_frontmatter(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nreproducibility_policy:\n  bar: third-party-reproducible\n",
        encoding="utf-8",
    )
    _write_dataset(tmp_path, "n3c", N3C)
    plans = tmp_path / "entities" / "plans"
    plans.mkdir(parents=True)
    (plans / "p.md").write_text(
        '---\nid: "plan:p"\ntype: "plan"\ntitle: "P"\n'
        "reproducibility_policy:\n"
        "  waivers:\n"
        '    - dataset: "dataset:n3c"\n'
        '      accepted_class: "trust-based-output"\n'
        '      decision_date: "2026-07-01"\n'
        '      rationale: "prototype only"\n'
        '      mitigation: "no interpretable estimate"\n---\n',
        encoding="utf-8",
    )
    project_pol = load_project_config(tmp_path).reproducibility_policy
    plan_pol = load_plan_reproducibility_policy(plans / "p.md")
    eff = effective_reproducibility_policy(project_pol, plan_pol)
    ok, halts, warns = check_plan_data_gate(
        tmp_path, ["dataset:n3c"], reproducibility_policy=eff, waivers=plan_pol.waivers
    )
    assert ok is True and halts == []           # waiver rescues the below-bar input
    assert any("waiver" in w for w in warns)
