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
            source = py.read_text(encoding="utf-8")
            if "science_tool.graph.store" not in source:
                continue
            try:
                tree = ast.parse(source, filename=str(py))
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


STORE_DIR = SCIENCE_ROOT / "src" / "science_tool" / "graph" / "store"

# Canonical dependency order: a submodule may import only siblings EARLIER in this list.
CANONICAL_ORDER = [
    "constants", "types", "graphutil", "identity", "notebooks", "dataset",
    "evidence_signals", "mutations", "export", "inquiry", "snapshot",
    "validation", "queries", "summary", "dot",
]


def _sibling_imports(tree: ast.AST) -> set[str]:
    sibs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level >= 1 and mod in CANONICAL_ORDER:          # from .sibling import x
                sibs.add(mod)
            if node.level >= 1 and mod == "":                        # from . import sibling
                for alias in node.names:
                    if alias.name in CANONICAL_ORDER:
                        sibs.add(alias.name)
            if mod.startswith("science_tool.graph.store."):          # from ...store.sibling import x
                sibs.add(mod.split(".")[-1])
            if mod == "science_tool.graph.store":                    # from ...store import sibling
                for alias in node.names:
                    if alias.name in CANONICAL_ORDER:
                        sibs.add(alias.name)
        if isinstance(node, ast.Import):                             # import ...store.sibling
            for alias in node.names:
                if alias.name.startswith("science_tool.graph.store."):
                    sibs.add(alias.name.split(".")[-1])
    return sibs


def _imports_materialize(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("science_tool.graph.materialize"):
            return True
        if isinstance(node, ast.Import):
            if any(a.name.startswith("science_tool.graph.materialize") for a in node.names):
                return True
    return False


def test_copy_viz_notebook_import_root_is_src(tmp_path, monkeypatch):
    import science_tool
    from science_tool.graph.store import notebooks

    # _uv_lock shells out to `uv lock`; stub it. viz.py (under test) is written before it runs.
    monkeypatch.setattr(notebooks, "_uv_lock", lambda directory: None)

    expected_root = Path(science_tool.__file__).resolve().parent.parent  # .../science/src
    buggy_root = expected_root / "science_tool"                          # what parents[2] would wrongly yield

    notebooks_dir = tmp_path / "notebooks"
    notebooks._copy_viz_notebook(notebooks_dir)
    content = (notebooks_dir / "viz.py").read_text(encoding="utf-8")

    assert "__SCIENCE_TOOL_IMPORT_ROOT__" not in content
    assert buggy_root.as_posix() not in content, "import root must be src/, not src/science_tool"
    assert expected_root.as_posix() in content


def test_no_upward_or_materialize_imports():
    for index, module_name in enumerate(CANONICAL_ORDER):
        path = STORE_DIR / f"{module_name}.py"
        if not path.exists():
            continue  # not yet extracted
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert not _imports_materialize(tree), f"{module_name}.py must not import graph.materialize"
        for sib in _sibling_imports(tree):
            assert CANONICAL_ORDER.index(sib) < index, (
                f"{module_name}.py imports later sibling '{sib}' — upward dependency edge"
            )
