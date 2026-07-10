"""Seed-binding and stochasticity checks (umbrella Spec 1, task:t079)."""

from pathlib import Path

from science_tool.validate.checks.methods import check_method_seed_params
from science_tool.validate.checks.workflow_steps import check_workflow_step_seed_bindings
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(
    root: Path,
    *,
    method_frontmatter: str,
    step_frontmatter: str,
) -> Path:
    (root / "science.yaml").write_text(
        "name: seed-check-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    methods = root / "entities" / "methods"
    methods.mkdir(parents=True, exist_ok=True)
    (methods / "leiden.md").write_text(
        f"---\nid: method:leiden\nkind: method\ntitle: Leiden\n{method_frontmatter}---\n",
        encoding="utf-8",
    )
    steps = root / "entities" / "workflow-steps"
    steps.mkdir(parents=True, exist_ok=True)
    (steps / "cluster.md").write_text(
        f"---\nid: workflow-step:cluster\nkind: workflow-step\ntitle: Cluster\n{step_frontmatter}---\n",
        encoding="utf-8",
    )
    return root


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _rules(results) -> list[tuple[str, Severity]]:
    return [(r.rule, r.severity) for r in results]


def test_step_applying_unclassified_method_is_an_error(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="method: method:leiden\n")
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.method-stochasticity-missing", Severity.ERROR)]


def test_seedable_method_with_unbound_param_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [random_state]\n",
        step_frontmatter="method: method:leiden\n",
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.seed-binding-missing", Severity.WARN)]
    assert "random_state" in results[0].message


def test_seedable_method_with_bound_param_is_clean(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [random_state]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  random_state: "config.seed"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_partial_binding_warns_once_per_unbound_param(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [a, b, c]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  a: "literal:1"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [
        ("workflow-step.seed-binding-missing", Severity.WARN),
        ("workflow-step.seed-binding-missing", Severity.WARN),
    ]


def test_nondeterministic_method_without_rationale_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: nondeterministic\n",
        step_frontmatter="method: method:leiden\n",
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.rationale-missing", Severity.WARN)]


def test_nondeterministic_method_with_rationale_is_clean(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: nondeterministic\n",
        step_frontmatter='method: method:leiden\nrationale: "GPU atomics"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_binding_on_deterministic_method_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: deterministic\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  random_state: "literal:42"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [
        ("workflow-step.seed-binding-on-deterministic-method", Severity.WARN)
    ]


def test_binding_naming_an_unknown_param_warns(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\nseed_params: [random_state]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  random_state: "literal:1"\n  typo: "literal:2"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.seed-binding-unknown-param", Severity.WARN)]
    assert "typo" in results[0].message


def test_unknown_param_is_suppressed_when_method_declares_no_seed_params(tmp_path: Path) -> None:
    # method.seed-params-missing already owns this defect; do not report it twice.
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: seedable\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  whatever: "literal:1"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_unresolvable_method_ref_is_skipped(tmp_path: Path) -> None:
    # The compiler and `graph audit` own the unresolved-reference defect.
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="method: method:nope\n")
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_step_without_a_method_is_skipped(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="")
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_nondeterministic_method_reports_rationale_and_unknown_param_together(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: nondeterministic\nseed_params: [random_state]\n",
        step_frontmatter='method: method:leiden\nseed_bindings:\n  typo: "literal:2"\n',
    )
    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [
        ("workflow-step.rationale-missing", Severity.WARN),
        ("workflow-step.seed-binding-unknown-param", Severity.WARN),
    ]
    assert "typo" in results[1].message


def test_nondeterministic_method_does_not_warn_about_unbound_params(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        method_frontmatter="stochasticity: nondeterministic\nseed_params: [random_state]\n",
        step_frontmatter='method: method:leiden\nrationale: "GPU atomics"\n',
    )
    assert list(check_workflow_step_seed_bindings(_ctx(root))) == []


def test_method_resolved_through_same_as_is_checked(tmp_path: Path) -> None:
    # Pins Finding 1: the check must resolve a step's `method:` ref through the
    # same `ReferenceResolver` machinery the compiler uses -- including project
    # `manual_aliases` (knowledge/sources/<profile>/mappings.yaml), which an
    # entity's own `canonical_id`/`aliases:` frontmatter can never satisfy. (Not
    # `same_as`: the compiler's `_add_applies_edge` calls `resolver.resolve(entity.method)`
    # with no `allow_cross_kind_fallback`, so `same_as` -- which only feeds the
    # cross-kind slug-index fallback -- never actually participates in resolving
    # a step's method reference. See the fix report for the full trace.)
    root = _project(
        tmp_path,
        method_frontmatter="",
        step_frontmatter="method: method:leidenalg\n",
    )
    mappings = root / "knowledge" / "sources" / "local" / "mappings.yaml"
    mappings.parent.mkdir(parents=True)
    mappings.write_text('aliases:\n  "method:leidenalg": "method:leiden"\n', encoding="utf-8")

    results = list(check_workflow_step_seed_bindings(_ctx(root)))
    assert _rules(results) == [("workflow-step.method-stochasticity-missing", Severity.ERROR)]


def test_seedable_method_without_seed_params_warns(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="stochasticity: seedable\n", step_frontmatter="")
    results = list(check_method_seed_params(_ctx(root)))
    assert _rules(results) == [("method.seed-params-missing", Severity.WARN)]


def test_unclassified_method_does_not_warn_about_seed_params(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="", step_frontmatter="")
    assert list(check_method_seed_params(_ctx(root))) == []


def test_deterministic_method_does_not_warn_about_seed_params(tmp_path: Path) -> None:
    root = _project(tmp_path, method_frontmatter="stochasticity: deterministic\n", step_frontmatter="")
    assert list(check_method_seed_params(_ctx(root))) == []
