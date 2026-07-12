"""The domain module must not import a CLI framework."""

from __future__ import annotations

import ast
from pathlib import Path

_PROMOTE = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "commons" / "promote.py"


def test_promote_does_not_import_click() -> None:
    tree = ast.parse(_PROMOTE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "click" for a in node.names), (
                "commons/promote.py imports click; the interactive prompt belongs in cli.py"
            )
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "click":
            raise AssertionError(
                "commons/promote.py imports click; the interactive prompt belongs in cli.py"
            )
