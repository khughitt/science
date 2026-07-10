"""Project-config path boundary guard (convergence Phase 1).

Static ratchet: the ``"science.yaml"`` filename is defined in exactly one
place, ``science_model/frontmatter.py``'s ``PROJECT_CONFIG_FILENAME``. Every
other module must reach the path via that constant or ``project_config_path``.
This guards against the filename regrowing across the tree.

This is a literal-string scan: no exception can be dodged by aliasing the path
into a variable, because every builder must name the file *somewhere*. The literal
is permitted in exactly ONE module — `science_model/frontmatter.py`, which defines
`PROJECT_CONFIG_FILENAME`. `data_root.py` and `project_config.py` are deliberately
NOT exempt (they consume the constant like everyone else), so "one place" is
literally true rather than "three places we trust."

Scope of the ratchet: it matches only an exact ``ast.Constant`` whose value is
``"science.yaml"``. That is necessary-but-not-sufficient. It deliberately does
NOT flag the filename *embedded* in a larger string (e.g. the shell heredoc in
`validate/checks/cross_references.py`) — which is why an AST scan is used rather
than a raw-text regex that would false-positive on it. The trade-off is that a
future author could still evade the guard by *constructing* the name at runtime
(`"science" + ".yaml"`, an f-string, `.format()`, `%`-templating, a bytes
literal). None exist today. Reviewers of new filename-handling code must still
check for those forms by eye; this guard catches the one form that actually
recurred (the bare literal), not every conceivable one.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_MODEL_SRC = Path(__file__).resolve().parents[1] / "model" / "src" / "science_model"

# The single module permitted to name the manifest file: where the constant lives.
_ALLOWED = {
    _MODEL_SRC / "frontmatter.py",
}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in (_SCIENCE_SRC, _MODEL_SRC):
        files.extend(p for p in root.rglob("*.py"))
    return files


def _literal_offenders() -> list[str]:
    offenders: list[str] = []
    for path in _source_files():
        if path in _ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "science.yaml":
                offenders.append(f"{path.name}:{node.lineno}")
    return offenders


def test_science_yaml_literal_is_centralized() -> None:
    offenders = _literal_offenders()
    assert not offenders, (
        'the "science.yaml" literal is permitted only in '
        "science_model/frontmatter.py (where PROJECT_CONFIG_FILENAME is "
        "defined); every other module must use PROJECT_CONFIG_FILENAME or "
        "call project_config_path(root). Offenders: "
        f"{sorted(offenders)}"
    )
