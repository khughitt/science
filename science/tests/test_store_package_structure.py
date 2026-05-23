"""Structural guard tests for the graph.store package decomposition."""
from __future__ import annotations

import ast
from pathlib import Path

import science_tool.graph.store as store

# science/tests/test_store_package_structure.py -> parents[1] == science/
SCIENCE_ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = [SCIENCE_ROOT / "src", SCIENCE_ROOT / "tests"]


def _names_imported_from_store() -> set[str]:
    names: set[str] = set()
    for root in SEARCH_ROOTS:
        for py in root.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "science_tool.graph.store":
                    for alias in node.names:
                        if alias.name != "*":
                            names.add(alias.name)
    return names


def test_store_reexports_every_imported_name():
    imported = _names_imported_from_store()
    assert imported, "expected to find imports from science_tool.graph.store"
    missing = sorted(name for name in imported if not hasattr(store, name))
    assert not missing, f"store/__init__.py must re-export these names: {missing}"
