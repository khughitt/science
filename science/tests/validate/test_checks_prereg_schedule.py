from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

import science_tool.validate.checks as checks
from science_tool.validate.checks import CANONICAL_CHECK_MODULES
from science_tool.validate.checks.prereg_schedule import check_prereg_schedule
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result


_SCHEDULE = """\
burn-in = 5 x ones.
Apply thinning every 10 draws.
Require ESS >= 400.
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: f\nprofile: research\n",
        encoding="utf-8",
    )
    (tmp_path / "entities" / "pre-registrations").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def prereg_schedule_registered() -> Generator[None]:
    """Re-register `prereg_schedule` through the real loader, then RESTORE the registry.

    Without the `sys.modules.pop`, `_load_canonical_checks()` re-imports an
    already-imported module -- a no-op, because `@Check` fires only on first
    import -- and the test passes whether or not the module is in
    CANONICAL_CHECK_MODULES. Teardown reloads every canonical module, because a
    cleared registry is PERMANENT for the session and every later `runner.run`
    would otherwise iterate a near-empty check list and silently report nothing.
    """
    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.prereg_schedule", None)
    checks._load_canonical_checks()
    yield
    checks.clear_checks_for_tests()
    for module_name in CANONICAL_CHECK_MODULES:
        importlib.reload(
            importlib.import_module(f"science_tool.validate.checks.{module_name}")
        )


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_prereg(root: Path, *, body: str, status: str = "committed") -> None:
    text = "\n".join(
        [
            "---",
            "kind: pre-registration",
            f"status: {status}",
            "---",
            "",
            "## Hypotheses Under Test",
            body,
        ]
    )
    root.joinpath("entities", "pre-registrations", "0001-a.md").write_text(
        text,
        encoding="utf-8",
    )


def _cost_gate(
    *,
    target_geometry: str | None = "A sparse 10,000-node substrate.",
    calibration_domain: str | None = "Calibrated on sparse graphs of this scale.",
) -> str:
    rows = [
        "## Cost Gate",
        "",
        "| Field | Declaration | Rationale |",
        "|---|---|---|",
    ]
    if target_geometry is not None:
        rows.append(f"| Target geometry | {target_geometry} | Fixed before fitting. |")
    if calibration_domain is not None:
        rows.append(f"| Calibration domain | {calibration_domain} | Matches the target. |")
    return "\n".join(rows)


def _results(root: Path) -> list[Result]:
    return list(check_prereg_schedule(_ctx(root)))


def _assert_schedule_warning(results: list[Result]) -> Result:
    assert len(results) == 1
    assert results[0].severity.value == "warn"
    assert results[0].rule == "prereg.schedule-calibration-domain"
    return results[0]


def test_schedule_without_cost_gate_warns(project: Path) -> None:
    _write_prereg(project, body=_SCHEDULE)

    result = _assert_schedule_warning(_results(project))

    assert "Cost Gate" in result.message


@pytest.mark.parametrize("row", ["Target geometry", "Calibration domain"])
@pytest.mark.parametrize("state", ["absent", "empty", "placeholder"])
def test_unfilled_required_row_warns(project: Path, row: str, state: str) -> None:
    """Both required rows, all three unfilled states, one verdict.

    The other row is FILLED in every case, so the finding can only come from the
    row under test -- otherwise a check that ignores `Target geometry` entirely
    would still pass, carried by its sibling.
    """
    value_by_state = {
        "absent": None,
        "empty": "",
        "placeholder": "<the substrate size and sparsity>",
    }
    gate_values = {
        "target_geometry": "A sparse 10,000-node substrate.",
        "calibration_domain": "Calibrated on sparse graphs of this scale.",
    }
    argument = row.lower().replace(" ", "_")
    gate_values[argument] = value_by_state[state]
    gate = _cost_gate(**gate_values)
    _write_prereg(project, body=f"{_SCHEDULE}\n{gate}")

    result = _assert_schedule_warning(_results(project))

    assert row in result.message
    assert state in result.message


def test_filled_cost_gate_passes(project: Path) -> None:
    _write_prereg(project, body=f"{_SCHEDULE}\n{_cost_gate()}")

    assert _results(project) == []


def test_no_schedule_declared_emits_nothing(project: Path) -> None:
    _write_prereg(project, body="Compare the registered models after fitting.")

    assert _results(project) == []


def test_ordinary_prose_does_not_trip_the_antecedent(project: Path) -> None:
    _write_prereg(
        project,
        body=(
            "We assess each process within its habitat unless the registered "
            "exclusion criterion applies."
        ),
    )

    assert _results(project) == []


def test_unfrozen_pre_registration_emits_nothing(project: Path) -> None:
    _write_prereg(project, body=_SCHEDULE, status="draft")

    assert _results(project) == []


@pytest.mark.usefixtures("prereg_schedule_registered")
def test_schedule_warning_surfaces_through_runner(project: Path) -> None:
    from science_tool.validate.runner import run

    _write_prereg(project, body=_SCHEDULE)

    rules = [result.rule for result in run(project, strict=False, verbose=False).results]

    assert "prereg.schedule-calibration-domain" in rules
