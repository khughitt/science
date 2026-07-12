"""Structural guard: health checks live in health_checks/, one per module.

Phase 5 of the toolkit convergence work moved 16 inline check bodies out of
graph/health.py. This guard stops them growing back and — more importantly —
stops a check module importing from graph/health.py, which would reintroduce
the import cycle the package exists to break.

It also pins the checks inside the instrument-boundary guard's SCOPE. That guard
(`test_instrument_boundary.py`) only inspects modules named in
`science_tool.instruments.INSTRUMENT_MODULES`. A check that moved out of
`graph/health.py` without its new home entering that tuple would silently stop
being checked — and nothing would go red. Coverage may never narrow.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_GRAPH = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph"
_HEALTH = _GRAPH / "health.py"
_CHECKS_DIR = _GRAPH / "health_checks"

# Set from the measured post-migration size of health.py (450 lines), plus ~20%
# headroom, rounded to a clean number.
_HEALTH_LINE_BUDGET = 550

_NON_CHECK_MODULES = {"__init__.py", "base.py"}


def _check_modules() -> list[Path]:
    return sorted(p for p in _CHECKS_DIR.glob("*.py") if p.name not in _NON_CHECK_MODULES)


def _imports_health(tree: ast.Module) -> bool:
    """True if the module imports from science_tool.graph.health (the cycle).

    Covers every spelling that reaches the module:
      from science_tool.graph.health import X     (absolute, dotted)
      import science_tool.graph.health            (absolute, plain)
      from science_tool.graph import health       (absolute, module as alias)
      from ..health import X                      (relative)
      from .. import health                       (relative, module as alias)

    including function-local ones — `ast.walk` descends into function bodies, so
    a deferred import is caught the same as a module-level one. That matters:
    a module-level back-edge would blow up at import time anyway, but a
    function-local one is deferred and silently works, so the guard is its only
    backstop.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "science_tool.graph.health":
                return True
            imported = {alias.name for alias in node.names}
            # `from science_tool.graph import health` — the package is the module,
            # `health` is the name. Idiomatic here, and level 0, so it evades any
            # check gated on a relative import.
            if node.level == 0 and node.module == "science_tool.graph" and "health" in imported:
                return True
            if node.level > 0 and (node.module == "health" or "health" in imported):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == "science_tool.graph.health" for alias in node.names):
                return True
    return False


@pytest.mark.parametrize("module", _check_modules(), ids=lambda p: p.name)
def test_check_module_does_not_import_health(module: Path) -> None:
    """The import DAG is one-way: base <- checks <- __init__ <- health."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    assert not _imports_health(tree), (
        f"{module.name} imports from science_tool.graph.health, which imports the "
        f"check modules back. Import shared machinery from health_checks/base.py."
    )


@pytest.mark.parametrize("module", _check_modules(), ids=lambda p: p.name)
def test_check_module_defines_exactly_one_check(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    assigned = [
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and target.id == "CHECK"
    ]
    assert len(assigned) == 1, f"{module.name} must define exactly one CHECK, found {len(assigned)}"


def test_every_check_module_is_registered() -> None:
    from science_tool.graph.health_checks import HEALTH_CHECKS

    registered = {check.name for check in HEALTH_CHECKS}
    on_disk = {module.stem for module in _check_modules()}
    assert on_disk == registered, (
        f"health_checks/ modules and HEALTH_CHECKS disagree: "
        f"on disk only={sorted(on_disk - registered)}, registered only={sorted(registered - on_disk)}"
    )


def test_every_check_module_is_in_the_instrument_scope() -> None:
    """A check that leaves the instrument guard's scope stops being guarded silently.

    `test_instrument_boundary.py` only inspects modules listed in
    INSTRUMENT_MODULES. The 16 collectors return InstrumentResult and are exactly
    what that guard exists to check, so every check module must be in the tuple.
    Without this test, moving a collector to a module nobody added to the list
    would narrow coverage with a green suite.
    """
    from science_tool.instruments import INSTRUMENT_MODULES

    scoped = set(INSTRUMENT_MODULES)
    missing = [
        f"graph/health_checks/{module.name}"
        for module in _check_modules()
        if f"graph/health_checks/{module.name}" not in scoped
    ]
    assert not missing, (
        f"these health-check modules are outside INSTRUMENT_MODULES, so "
        f"test_instrument_boundary.py does not inspect them: {missing}. "
        f"Add them to science_tool/instruments.py::INSTRUMENT_MODULES."
    )


def test_health_stays_within_its_line_budget() -> None:
    lines = len(_HEALTH.read_text(encoding="utf-8").splitlines())
    assert lines <= _HEALTH_LINE_BUDGET, (
        f"health.py is {lines} lines (budget {_HEALTH_LINE_BUDGET}, set from a measured "
        f"post-migration count of 450 lines + ~20% headroom); a health check "
        f"belongs in its own module under graph/health_checks/"
    )
