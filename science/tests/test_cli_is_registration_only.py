"""Structural guard: science_tool/cli.py stays registration-only.

Convergence Phase 4 extracted every inline Click group/command body out of
cli.py into <domain>_cli.py modules, each registered back via
``main.add_command(...)``. This guard fails if cli.py ever regrows an inline
command/group body — the failure mode the phase existed to close out.
"""
from __future__ import annotations

import ast
from pathlib import Path

_CLI = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "cli.py"
_ROOT_GROUP = "main"  # the one allowed group/command definition (the Click root)


def _is_group_or_command_decorator(dec: ast.expr) -> bool:
    """True for @X.group(...)/@X.command(...) and @click.group(...)/@click.command(...),
    for ANY owner X — decorator-owner-blind on purpose. A guard keyed on `main.*`
    alone would let a future inline subcommand on an *imported* group slip through.
    """
    target = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(target, ast.Attribute) and target.attr in {"group", "command"}


def _command_defs(tree: ast.Module) -> list[str]:
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_is_group_or_command_decorator(d) for d in node.decorator_list)
    ]


def test_cli_defines_only_the_root_group():
    tree = ast.parse(_CLI.read_text(encoding="utf-8"))
    offenders = [name for name in _command_defs(tree) if name != _ROOT_GROUP]
    assert not offenders, (
        "cli.py must be registration-only: the only command/group definition allowed "
        f"is the root '{_ROOT_GROUP}'. Every other group/command lives in a "
        "<domain>_cli.py module registered here via main.add_command(...). "
        f"Inline definitions found: {offenders}"
    )


def test_cli_within_line_budget():
    """cli.py must stay a thin, registration-only entrypoint.

    Real post-migration count at authoring time (Convergence Phase 4, Task 12):
    236 lines (``wc -l src/science_tool/cli.py``). Budget set to 300 — a small
    margin for a handful of future ``main.add_command(...)`` lines, not enough
    room for a re-inlined command/group body (which historically ran to
    hundreds of lines per group). If this trips, extract the offending logic
    into a <domain>_cli.py module rather than raising the budget.
    """
    lines = _CLI.read_text(encoding="utf-8").count("\n") + 1
    assert lines <= 300, f"cli.py is {lines} lines; extract inline logic (budget 300)"
