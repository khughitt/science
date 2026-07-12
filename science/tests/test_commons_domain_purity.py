"""Structural guard: the promote pipeline stays decomposed.

Phase 6 split commons/promote.py into a shared type vocabulary plus three
single-purpose layers. Two invariants keep it split:

  1. No module under commons/ except cli.py imports click. An interactive prompt
     in a domain module is what made promote.py import a CLI framework.
  2. The extracted layers never import back from commons/promote. That back-edge
     is the cycle the decomposition exists to prevent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_COMMONS = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "commons"
_PROMOTE = _COMMONS / "promote.py"

# cli.py is the ONLY module under commons/ allowed to import click.
_CLICK_ALLOWED = {"cli.py"}

# The layers extracted out of promote.py. Each may import promote_types; none may
# import promote.
_EXTRACTED_LAYERS = ("promote_types.py", "git.py", "promote_render.py", "promote_dataset.py")

# 2,193 measured (Step 1) + ~20% headroom, rounded up to a clean hundred.
_PROMOTE_LINE_BUDGET = 2700


def _commons_modules() -> list[Path]:
    return sorted(p for p in _COMMONS.glob("*.py") if p.name != "__init__.py")


def _imports_click(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "click" for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").split(".")[0] == "click":
                return True
    return False


def _imported_commons_modules(tree: ast.Module) -> set[str]:
    """Every commons submodule this module imports, by any spelling.

    An import edge has five spellings, and a guard that checks only the obvious one
    is a guard with a hole:

        from science_tool.commons.promote import plan_promote   # absolute module
        import science_tool.commons.promote                     # absolute, plain
        from science_tool.commons import promote                # package, module-as-alias
        from .promote import plan_promote                       # relative module
        from . import promote                                   # relative, module-as-alias

    All five are resolved to the bare submodule name ("promote"). `ast.walk` descends
    into function bodies, so a deferred import counts the same as a module-level one.
    """
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {alias.name for alias in node.names}
            if node.level == 0:
                if module.startswith("science_tool.commons."):
                    modules.add(module.removeprefix("science_tool.commons.").split(".")[0])
                elif module == "science_tool.commons":
                    modules |= names
            elif module:
                # `from ..commons.promote import x` -> module "commons.promote"
                modules.add(module.split(".")[-1])
            else:
                # `from . import promote`
                modules |= names
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("science_tool.commons."):
                    modules.add(alias.name.removeprefix("science_tool.commons.").split(".")[0])
    return modules


@pytest.mark.parametrize(
    "module", _commons_modules(), ids=lambda p: p.name
)
def test_only_the_cli_imports_click(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    if module.name in _CLICK_ALLOWED:
        return
    assert not _imports_click(tree), (
        f"commons/{module.name} imports click. Only commons/cli.py may depend on a CLI "
        f"framework -- an interactive prompt does not belong in a domain module."
    )


@pytest.mark.parametrize("name", _EXTRACTED_LAYERS)
def test_extracted_layer_does_not_import_promote(name: str) -> None:
    """The import DAG is one-way: promote_types <- {git, render, dataset} <- promote."""
    tree = ast.parse((_COMMONS / name).read_text(encoding="utf-8"))
    assert "promote" not in _imported_commons_modules(tree), (
        f"commons/{name} imports from commons.promote, which imports it back. "
        f"Shared vocabulary belongs in commons/promote_types.py."
    )


def test_promote_types_is_the_bottom_of_the_dag() -> None:
    """promote_types imports none of the layers that import it."""
    tree = ast.parse((_COMMONS / "promote_types.py").read_text(encoding="utf-8"))
    forbidden = {"git", "promote_render", "promote_dataset", "promote", "cli"}
    offenders = sorted(_imported_commons_modules(tree) & forbidden)
    assert not offenders, (
        f"promote_types imports commons.{', commons.'.join(offenders)}, which import "
        f"promote_types back. promote_types is the bottom of the DAG and must stay a leaf."
    )


def test_promote_stays_within_its_line_budget() -> None:
    lines = len(_PROMOTE.read_text(encoding="utf-8").splitlines())
    assert lines <= _PROMOTE_LINE_BUDGET, (
        f"promote.py is {lines} lines (budget {_PROMOTE_LINE_BUDGET}). A renderer belongs in "
        f"promote_render.py, a git call in git.py, a dataset rule in promote_dataset.py, and a "
        f"shared type in promote_types.py."
    )
