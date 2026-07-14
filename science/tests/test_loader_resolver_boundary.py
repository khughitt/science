"""Loader/resolver boundary guard — the LOADER must not build a REFERENCE RESOLVER.

This design has been introduced **twice** and reverted twice, because it looks obviously right:
`load_project_sources` has the whole corpus, the manual aliases and the identity declarations
sitting right there, so resolving lineage in a second pass is a two-line change.

It is wrong, and the reason is not about lineage at all:

    `ReferenceResolver.from_entities` -> `build_alias_map` RAISES `AliasCollisionError`
    when two entities claim one alias.

So constructing a resolver inside the loader makes a corpus with a duplicated alias **UNLOADABLE**
rather than **REPORTABLE** — for every caller of the loader, including the many that never look at a
hypothesis. `annotation/proposition_archive.py` exists precisely to report and unblock those
collisions and calls `load_project_sources` on a colliding corpus *on purpose*; the loader-side pass
breaks three of its tests.

**Loading and resolving are different jobs.** The loader reads and projects sources. Resolution is
analysis *over* an already-loaded corpus, and it belongs to the caller who wants an answer and can
handle the collision — which is what every other call site in the tree already does
(`materialize.py`, `migrate.py` (which catches `AliasCollisionError` explicitly),
`validate/checks/hypotheses.py`, `validate/checks/workflow_steps.py`, …).

WHY AN AST GUARD, and not just the behavioural test next door.
`test_the_LOADER_does_not_build_a_RESOLVER` (test_resolution_wiring.py) loads a colliding corpus and
asserts the loader does not raise. That pins the SYMPTOM, not the BOUNDARY: a loader that builds the
resolver, catches `AliasCollisionError`, and carries on would pass it — while silently reintroducing
the coupling *and* adding a swallowed exception. This guard pins the boundary itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SOURCES = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph" / "sources.py"

# The classmethod that constructs a resolver. Matched on the ATTRIBUTE NAME alone, deliberately:
# an import edge has many spellings (`from …reference_resolution import ReferenceResolver`,
# `import …reference_resolution as rr`, `ReferenceResolver as RR`, a function-local import, …) and a
# guard that matched the import would have a hole for every spelling it did not enumerate. Every
# spelling still has to end in a `.from_entities(...)` call to build one.
_CONSTRUCTOR = "from_entities"

_RESOLVER_MODULE = "science_tool.graph.reference_resolution"


def _tree() -> ast.Module:
    return ast.parse(_SOURCES.read_text(encoding="utf-8"), filename=str(_SOURCES))


def test_the_loader_module_never_CONSTRUCTS_a_resolver() -> None:
    calls = [
        node
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == _CONSTRUCTOR
    ]
    assert not calls, (
        f"graph/sources.py calls .{_CONSTRUCTOR}() at line(s) "
        f"{sorted(node.lineno for node in calls)}. The LOADER must not build a ReferenceResolver: "
        "from_entities raises AliasCollisionError on a duplicated alias, which would make a "
        "REPORTABLE fault an UNLOADABLE project for every caller of load_project_sources. "
        "Resolve in the CHECK (validate/checks/hypotheses.py), not in the loader."
    )


def test_the_loader_module_never_IMPORTS_the_resolver() -> None:
    # The import is the only way to reach the constructor, so forbidding it too closes the gap where
    # someone reaches the resolver through a name this guard's call-check does not recognise (a
    # module alias, a functools.partial, a getattr). Note a TOP-LEVEL import here is impossible
    # anyway -- `reference_resolution` imports `build_alias_map` FROM this module, so it would be a
    # cycle -- which means the only way in is a FUNCTION-LOCAL import. That is exactly the shape both
    # reverted attempts used, and exactly what this catches.
    offenders: list[int] = []
    for node in ast.walk(_tree()):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("reference_resolution"):
            offenders.append(node.lineno)
        elif isinstance(node, ast.Import):
            offenders.extend(
                node.lineno for alias in node.names if alias.name.endswith("reference_resolution")
            )
    assert not offenders, (
        f"graph/sources.py imports {_RESOLVER_MODULE} at line(s) {sorted(offenders)}. The loader "
        "must not reach the resolver at all -- see this module's docstring. (A function-local "
        "import is still an import: it is the shape both reverted attempts used.)"
    )


def test_the_GUARD_ITSELF_still_matches_a_real_construction() -> None:
    # ☠️ A guard that no longer recognises the thing it forbids is not a guard -- it is a green
    # light. If `from_entities` is ever renamed, the two tests above keep passing over a loader that
    # freely builds resolvers. So: assert the pattern this guard looks for STILL EXISTS in the real
    # code, at a site where it is legitimate.
    check = _SOURCES.parent.parent / "validate" / "checks" / "hypotheses.py"
    tree = ast.parse(check.read_text(encoding="utf-8"), filename=str(check))
    constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == _CONSTRUCTOR
    ]
    assert constructions, (
        f"validate/checks/hypotheses.py no longer calls .{_CONSTRUCTOR}(). Either the resolver "
        "construction moved (in which case the guard above is now pointed at nothing), or the "
        "constructor was renamed -- and this guard has been silently blind ever since."
    )
