"""Durable-writer boundary guard (kernel closure, Phase 1).

Static AST ratchet: the ONLY production modules permitted to call the durable
graph-write primitives (`save_graph_dataset` / `_save_dataset`) are the compiler
write phase (`graph/materialize.py`) and the module that defines the primitive
(`graph/store/dataset.py`). Every other call site is a direct writer that bypasses
the source-declaration -> `science graph build` boundary.

Direct writers that are KNOWN and intentionally deferred to a later kernel-closure
phase are enumerated in `EXPECTED_DEFERRED_WRITERS`, each tagged with its retirement
phase. The guard fails if:
  * a writer site appears that is NOT in the ledger (a new boundary violation), or
  * a ledger entry no longer exists in code (a stale ledger after a retirement).

This guard was authored RED: the Tier 1 sites (orphaned inquiry / data-package
mutators) were deliberately absent from the ledger, so the guard reported them as
unexpected until Phase 1 Task 5 deleted them. With Tier 1 gone, `actual` now
equals the ledger exactly and the guard is GREEN.

Scope / limitation: the match is name-based on the call site — a bare
`_save_dataset(...)` / `save_graph_dataset(...)` call resolved to its enclosing
function. It is a ratchet against *accidental* regrowth of a direct writer, not a
runtime sandbox: an aliased re-import (`from .dataset import _save_dataset as p`)
or an indirect call through a variable would evade the static check. Closing those
holes would require import-alias resolution; the source-declaration boundary is
enforced for real at build time by the compiler, and this test guards against the
common case of a new module simply calling the primitive by name.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "science_tool"
_WRITE_FUNCS = {"save_graph_dataset", "_save_dataset"}

# Modules that legitimately own durable graph writes.
_ALLOWLIST_MODULES = {
    "graph/materialize.py",  # compiler write phase — sole graph.trig owner
    "graph/store/dataset.py",  # defines/wraps the save primitive
}

# Direct writers that are KNOWN and intentionally deferred to a later
# kernel-closure phase. Every entry carries a retirement phase. Tier 1 sites are
# deliberately ABSENT — their presence in code is what makes this guard RED until
# Phase 1 Task 5 deletes them.
EXPECTED_DEFERRED_WRITERS = {
    # Tier 2 — live `graph add *` mutators; retire in Phase 3 via _retired_mutator.
    "graph/store/mutations.py:add_concept",
    "graph/store/mutations.py:add_article",
    "graph/store/mutations.py:add_proposition",
    "graph/store/mutations.py:add_observation",
    "graph/store/mutations.py:add_evidence_edge",
    "graph/store/mutations.py:add_finding",
    "graph/store/mutations.py:add_interpretation",
    "graph/store/mutations.py:add_discussion",
    "graph/store/mutations.py:add_falsification",
    "graph/store/mutations.py:add_mechanism",
    "graph/store/mutations.py:add_story",
    "graph/store/mutations.py:add_paper_entity",
    "graph/store/mutations.py:add_hypothesis",
    "graph/store/mutations.py:add_question",
    "graph/store/mutations.py:add_edge",
    # Tier 3 — classify/retire in a later phase.
    "graph/store/snapshot.py:import_snapshot",
    "graph/store/snapshot.py:stamp_revision",
}


def _enclosing_writer_sites() -> set[str]:
    sites: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC).as_posix()
        if rel in _ALLOWLIST_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node  # type: ignore[attr-defined]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            else:
                name = None
            if name not in _WRITE_FUNCS:
                continue
            enclosing: ast.AST | None = node
            while enclosing is not None and not isinstance(
                enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                enclosing = getattr(enclosing, "parent", None)
            func_name = (
                enclosing.name
                if isinstance(enclosing, (ast.FunctionDef, ast.AsyncFunctionDef))
                else "<module>"
            )
            sites.add(f"{rel}:{func_name}")
    return sites


def test_no_durable_graph_writer_outside_allowlist() -> None:
    actual = _enclosing_writer_sites()
    unexpected = actual - EXPECTED_DEFERRED_WRITERS
    stale = EXPECTED_DEFERRED_WRITERS - actual
    assert not unexpected, (
        "new direct graph writer(s) outside allowlist/ledger — route through "
        f"`science graph build` or add to EXPECTED_DEFERRED_WRITERS: {sorted(unexpected)}"
    )
    assert not stale, (
        "ledger lists writer(s) that no longer exist — prune "
        f"EXPECTED_DEFERRED_WRITERS: {sorted(stale)}"
    )
