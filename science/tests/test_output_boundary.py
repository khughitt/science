"""Output-emitter boundary guard (convergence Phase 3).

Additive ratchet: a *new* hand-rolled JSON emitter must not appear outside the
canonical module (science_tool/output.py) and the named allowlist below.

Detection: a function violates the boundary if its body contains BOTH an
emission call (click.echo / bare print / console.print / sys.stdout.write) AND a
call to any attribute named ``dumps`` (json.dumps, _json.dumps, yaml.dumps — any
alias; matched by attribute name so it is binding-blind). Function-scoped, so a
``dumps`` that writes a file or builds a hash in a function with no emission call
passes, and a function with only stderr echoes and no ``dumps`` passes. Nested
defs/lambdas bind to their own nearest enclosing function.

Known gap, stated rather than hidden: a helper that returns a JSON *string*
echoed by a different function evades this (cross-function). So would a fence
built via ``str.format``. This is a ratchet against the bare ``echo(dumps(...))``
form that recurred across the tree, not a sandbox — the same class of limit the
durable-write and frontmatter guards document candidly.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_CANONICAL = _SCIENCE_SRC / "output.py"


def _is_emission_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # bare print(...)
    if isinstance(func, ast.Name) and func.id == "print":
        return True
    if isinstance(func, ast.Attribute):
        # click.echo(...), console.print(...), <anything>.print(...)
        if func.attr in {"echo", "print"}:
            return True
        # sys.stdout.write(...)  /  <stream>.write(...) on stdout
        if func.attr == "write" and isinstance(func.value, ast.Attribute) and func.value.attr == "stdout":
            return True
    return False


def _is_dumps_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "dumps"


def _nearest_function_bodies(tree: ast.Module) -> list[ast.AST]:
    """Every FunctionDef/AsyncFunctionDef node in the module."""
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _direct_children_calls(func: ast.AST) -> list[ast.AST]:
    """Calls bound to THIS function, not descending into nested def/lambda."""
    calls: list[ast.AST] = []

    class _Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is func:
                self.generic_visit(node)  # descend into the target itself

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is func:
                self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return  # lambdas bind to themselves

        def visit_Call(self, node: ast.Call) -> None:
            calls.append(node)
            self.generic_visit(node)

    _Visitor().visit(func)
    return calls


def _function_is_emitter(func: ast.AST) -> bool:
    calls = _direct_children_calls(func)
    return any(_is_emission_call(c) for c in calls) and any(_is_dumps_call(c) for c in calls)


def _emitter_functions() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    repo_root = Path(__file__).resolve().parents[1]
    for path in _SCIENCE_SRC.rglob("*.py"):
        if path == _CANONICAL:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = str(path.relative_to(repo_root))
        for func in _nearest_function_bodies(tree):
            if _function_is_emitter(func):
                found.append((rel, func.name))
    return found


# (rel_path, function_name) -> reason. Functions that legitimately keep a stderr
# echo beside a file/hash dumps, or a byte-form the canonical emitter cannot
# reproduce. Fill from the Step-2 detector run against the migrated tree.
_ALLOWED_EMITTERS: dict[tuple[str, str], str] = {
    ("src/science_tool/datasets_identity.py", "_stamp_datapackage"): (
        "stderr-only warning echoes; dumps serializes a datapackage descriptor to disk (atomic file write)"
    ),
    # NOTE: keyed by bare function name, so this exempts ANY benchmark_cli.py closure
    # named `_render` that pairs an emission with a `dumps`. Today only these two
    # qualify (of the `_render` closures in benchmark_cli.py, only these contain a
    # dumps at all — moved here from cli.py by Phase 4's `benchmark` group
    # extraction). If a future extraction adds more `_render` closures, re-audit —
    # a future real emitter named `_render` would silently inherit this entry.
    ("src/science_tool/benchmark_cli.py", "_render"): (
        "render_text closures for `benchmark-opportunities` and `benchmark-gaps`: dumps only stringifies a "
        "scalar/list value for a Rich table cell (compact JSON display of a composite value), not a payload "
        "emission; the actual output line is Console(...).print(table) / a stderr-adjacent click.echo fallback"
    ),
    ("src/science_tool/annotation/cli.py", "resynthesis_draft_context_cmd"): (
        "nl=False: byte output intentionally omits trailing newline; emit() always appends one via click.echo, "
        "so this stays hand-rolled to preserve the exact byte contract"
    ),
}


def test_no_new_output_emitters() -> None:
    offenders = [pair for pair in _emitter_functions() if pair not in _ALLOWED_EMITTERS]
    assert not offenders, (
        "New hand-rolled JSON emitter(s) found outside science_tool/output.py and "
        "the named allowlist. Route output through science_tool.output.emit(...); "
        "if a stderr echo legitimately shares a function with a file/hash dumps, "
        f"add an _ALLOWED_EMITTERS entry with a reason. Offenders: {sorted(offenders)}"
    )


def test_allowlist_has_no_stale_entries() -> None:
    live = set(_emitter_functions())
    stale = [pair for pair in _ALLOWED_EMITTERS if pair not in live]
    assert not stale, (
        "Allowlisted entries no longer detected as emitters (migrated or removed?). "
        f"Delete these stale entries: {sorted(stale)}"
    )
