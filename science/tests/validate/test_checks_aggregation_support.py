from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from science_tool.validate.result import Severity


def _workflow(outputs: list[dict]) -> dict:
    return {
        "id": "workflow:meta",
        "kind": "workflow",
        "_path": "entities/workflows/meta.md",
        "outputs": outputs,
    }


def _dataset(slug: str = "combined", **kw) -> dict:
    base = {
        "id": f"dataset:wf-r1-{slug}",
        "kind": "dataset",
        "_path": f"entities/datasets/wf-r1-{slug}.md",
        "derivation": {"workflow": "workflow:meta", "workflow_run": "workflow-run:wf-r1"},
        "datapackage": f"results/meta/r1/{slug}/datapackage.yaml",
    }
    base.update(kw)
    return base


def _output(slug: str = "combined", **support_kw) -> dict:
    out = {"slug": slug, "title": "Combined", "resource_names": ["gene"]}
    if support_kw:
        out["support"] = support_kw
    return out


def _evaluate(entities: list[dict], packages: dict[str, dict | None]):
    from science_tool.validate.checks.aggregation_support import evaluate_aggregation_support

    return list(evaluate_aggregation_support(entities, lambda rel: packages.get(rel)))


def _rules(entities, packages):
    return [(r.severity, r.rule) for r in _evaluate(entities, packages)]


DP = "results/meta/r1/combined/datapackage.yaml"
BAD_DP = "results/meta/r1/bad/datapackage.yaml"


def test_no_support_block_is_not_evaluated() -> None:
    assert _rules([_workflow([_output()]), _dataset()], {DP: {"science": {}}}) == []


def test_observed_at_or_above_expected_is_clean() -> None:
    entities = [_workflow([_output(unit="dataset", min=3, expected=5)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 5}}}}
    assert _rules(entities, pkgs) == []


def test_below_floor_is_error() -> None:
    entities = [_workflow([_output(unit="dataset", min=3, expected=5)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 1}}}}
    assert (Severity.ERROR, "aggregation-support.below-floor") in _rules(entities, pkgs)


def test_zero_observed_is_below_floor_error() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 0}}}}
    assert (Severity.ERROR, "aggregation-support.below-floor") in _rules(entities, pkgs)


def test_below_floor_requires_valid_floor_min() -> None:
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 0}}}}

    for floor_min in (None, "3", True, 0, -1):
        output = _output(unit="dataset")
        if floor_min is not None:
            output["support"]["min"] = floor_min
        entities = [_workflow([output]), _dataset()]

        assert (Severity.ERROR, "aggregation-support.below-floor") not in _rules(entities, pkgs)


def test_below_expected_is_warn() -> None:
    entities = [_workflow([_output(unit="dataset", min=3, expected=5)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 4}}}}
    assert _rules(entities, pkgs) == [(Severity.WARN, "aggregation-support.below-expected")]


def test_below_expected_requires_valid_floor_min() -> None:
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 4}}}}

    for floor_min in (None, "3", True, 0, -1):
        output = _output(unit="dataset", expected=5)
        if floor_min is not None:
            output["support"]["min"] = floor_min
        entities = [_workflow([output]), _dataset()]

        assert (Severity.WARN, "aggregation-support.below-expected") not in _rules(entities, pkgs)


def test_below_expected_requires_valid_expected() -> None:
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": 0}}}}

    for expected in (True, 0, -1):
        entities = [_workflow([_output(unit="dataset", min=1, expected=expected)]), _dataset()]

        assert (Severity.WARN, "aggregation-support.below-expected") not in _rules(entities, pkgs)


def test_stamp_missing_when_observed_null() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": None}}}}
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in _rules(entities, pkgs)


def test_stamp_missing_when_no_support_stamp() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"identity_context": {}}}}
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in _rules(entities, pkgs)


def test_stamp_missing_when_datapackage_absent() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in _rules(entities, {DP: None})


def test_datapackage_read_error_reports_stamp_missing_and_continues() -> None:
    from science_tool.validate.checks.aggregation_support import evaluate_aggregation_support

    entities = [
        _workflow([_output("bad", unit="dataset", min=3), _output(unit="dataset", min=3)]),
        _dataset("bad"),
        _dataset(),
    ]

    def read_datapackage(rel: str) -> dict | None:
        if rel == BAD_DP:
            raise ValueError("bad yaml")
        return {"science": {"support": {"unit": "dataset", "observed": 1}}}

    results = list(evaluate_aggregation_support(entities, read_datapackage))
    rules = [(r.severity, r.rule) for r in results]

    assert (Severity.ERROR, "aggregation-support.stamp-missing") in rules
    assert (Severity.ERROR, "aggregation-support.below-floor") in rules
    assert any(r.path == Path("entities/datasets/wf-r1-bad.md") and BAD_DP in r.message for r in results)
    assert any("bad yaml" in r.message for r in results)


def test_unsafe_absolute_datapackage_path_reports_stamp_missing_without_reading() -> None:
    from science_tool.validate.checks.aggregation_support import evaluate_aggregation_support

    absolute_dp = "/tmp/combined/datapackage.yaml"
    entities = [
        _workflow([_output(unit="dataset", min=3)]),
        _dataset(datapackage=absolute_dp),
    ]

    def read_datapackage(rel: str) -> dict | None:
        raise AssertionError(f"unsafe path was read: {rel}")

    results = list(evaluate_aggregation_support(entities, read_datapackage))
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in [(r.severity, r.rule) for r in results]
    assert absolute_dp in results[0].message


def test_unsafe_traversal_datapackage_path_reports_stamp_missing_without_reading() -> None:
    traversal_dp = "results/meta/r1/../combined/datapackage.yaml"
    entities = [
        _workflow([_output(unit="dataset", min=3)]),
        _dataset(datapackage=traversal_dp),
    ]

    def read_datapackage(rel: str) -> dict | None:
        raise AssertionError(f"unsafe path was read: {rel}")

    from science_tool.validate.checks.aggregation_support import evaluate_aggregation_support

    results = list(evaluate_aggregation_support(entities, read_datapackage))
    assert (Severity.ERROR, "aggregation-support.stamp-missing") in [
        (r.severity, r.rule) for r in results
    ]
    assert traversal_dp in results[0].message


def test_malformed_observed_is_error() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    for bad in ("5", True, -1, 5.0):
        pkgs = {DP: {"science": {"support": {"unit": "dataset", "observed": bad}}}}
        assert (Severity.ERROR, "aggregation-support.malformed-stamp") in _rules(entities, pkgs), bad


def test_unit_mismatch_is_error_and_suppresses_floor() -> None:
    entities = [_workflow([_output(unit="dataset", min=3)]), _dataset()]
    pkgs = {DP: {"science": {"support": {"unit": "cohort", "observed": 1}}}}
    rules = _rules(entities, pkgs)
    assert (Severity.ERROR, "aggregation-support.unit-mismatch") in rules
    assert (Severity.ERROR, "aggregation-support.below-floor") not in rules


def test_module_is_registered() -> None:
    import sys

    import science_tool.validate.checks as checks

    original_checks = list(checks.CANONICAL_CHECKS)
    original_module = sys.modules.get("science_tool.validate.checks.aggregation_support")
    try:
        checks.clear_checks_for_tests()
        sys.modules.pop("science_tool.validate.checks.aggregation_support", None)
        checks._load_canonical_checks()
        assert any(entry.fn.__module__.endswith("aggregation_support") for entry in checks.CANONICAL_CHECKS)
    finally:
        checks.CANONICAL_CHECKS[:] = original_checks
        if original_module is not None:
            sys.modules["science_tool.validate.checks.aggregation_support"] = original_module
        else:
            sys.modules.pop("science_tool.validate.checks.aggregation_support", None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_mm30_shape(root: Path, observed) -> None:
    _write(root / "science.yaml", "name: t\nlayout_version: 3\n")
    _write(
        root / "entities/workflows/meta.md",
        "---\n"
        'id: "workflow:meta"\n'
        'kind: "workflow"\n'
        'title: "Meta"\n'
        "outputs:\n"
        "  - slug: combined\n"
        "    title: Combined\n"
        "    resource_names: [gene]\n"
        "    support:\n"
        "      unit: dataset\n"
        "      min: 3\n"
        "      expected: 5\n"
        "---\n",
    )
    _write(
        root / "entities/datasets/wf-r1-combined.md",
        "---\n"
        'id: "dataset:wf-r1-combined"\n'
        'kind: "dataset"\n'
        'title: "Combined"\n'
        'datapackage: "results/meta/r1/combined/datapackage.yaml"\n'
        "derivation:\n"
        '  workflow: "workflow:meta"\n'
        '  workflow_run: "workflow-run:wf-r1"\n'
        "---\n",
    )
    _write(
        root / "results/meta/r1/combined/datapackage.yaml",
        "profiles: [science-pkg-runtime-1.0]\n"
        "name: meta-r1-combined\n"
        "resources: []\n"
        "science:\n"
        "  support:\n"
        "    unit: dataset\n"
        f"    observed: {observed}\n",
    )


@contextmanager
def _only_aggregation_support_check():
    import science_tool.validate.checks as checks
    from science_tool.validate.checks import CheckEntry
    from science_tool.validate.checks.aggregation_support import check_aggregation_support

    original_checks = list(checks.CANONICAL_CHECKS)
    checks.CANONICAL_CHECKS[:] = [
        CheckEntry(section="aggregation support", order=34, fn=check_aggregation_support)
    ]
    try:
        yield
    finally:
        checks.CANONICAL_CHECKS[:] = original_checks


def test_only_aggregation_support_check_does_not_depend_on_current_registry() -> None:
    import science_tool.validate.checks as checks

    original_checks = list(checks.CANONICAL_CHECKS)
    try:
        checks.CANONICAL_CHECKS[:] = []
        with _only_aggregation_support_check():
            assert len(checks.CANONICAL_CHECKS) == 1
            assert checks.CANONICAL_CHECKS[0].fn.__module__.endswith("aggregation_support")
    finally:
        checks.CANONICAL_CHECKS[:] = original_checks


def test_e2e_below_floor_reports_error(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _seed_mm30_shape(tmp_path, observed=1)
    with _only_aggregation_support_check():
        result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)
    assert any(r.rule == "aggregation-support.below-floor" for r in result.results)
    assert result.errors >= 1


def test_e2e_at_floor_is_warn_not_error(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _seed_mm30_shape(tmp_path, observed=4)
    with _only_aggregation_support_check():
        result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)
    rules = [r.rule for r in result.results]
    assert "aggregation-support.below-expected" in rules
    assert "aggregation-support.below-floor" not in rules
    assert result.errors == 0


def test_cli_exit_one_on_below_floor(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from science_tool.cli import main

    _seed_mm30_shape(tmp_path, observed=1)
    with _only_aggregation_support_check():
        res = CliRunner().invoke(
            main,
            ["validate", "--project-root", str(tmp_path)],
            catch_exceptions=False,
        )
    assert res.exit_code == 1, res.output
    assert "aggregation-support.below-floor" in res.output
