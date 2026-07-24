"""Dataset-profile reference boundary guard.

`BASE_DATASET_SCHEMA_PROFILE` is the FIXED generation-2 dataset profile. It is correct only
for commons dataset callers, whose `dataset` mixin stays `dataset/2.0` across generations.
Every PROJECT dataset writer must instead default through `project_dataset_schema_profile`,
which honors the project's `entity_schema_version` pin.

This scans EVERY reference to the constant, not just `from ... import` edges: a from-import
plus its `Name` uses, an aliased module attribute
(`import ... as ia; ia.BASE_DATASET_SCHEMA_PROFILE`), and a star import from the defining
module. Detecting only `ImportFrom` would miss the attribute-access and star-import spellings.
Deny-by-default: the whole `science_tool` tree is scanned and only the commons package is
allowlisted, so a future project-side writer that reaches for the raw gen-2 constant fails
here and is forced through the resolver.

The defining module is scanned too. Only the constant's top-level assignment target is
exempt; any load of the constant there remains forbidden.

Known limit, stated rather than hidden: matching the bare name as an attribute would also flag
an unrelated symbol that happened to share the exact name `BASE_DATASET_SCHEMA_PROFILE`. No such
collision exists in this tree, and the name is specific enough that one is implausible.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_CONSTANT = "BASE_DATASET_SCHEMA_PROFILE"
_DEFINING_MODULE = _SCIENCE_SRC / "identity_authoring.py"

# Only commons callers may reference the fixed gen-2 constant (gen-2 is correct for commons).
_ALLOWED_DIR = _SCIENCE_SRC / "commons"


def _references_constant(path: Path) -> bool:
    """True if the module contains a forbidden constant binding or access."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defining_assignment_target = None
    if path == _DEFINING_MODULE:
        defining_assignment_target = next(
            (
                target
                for statement in tree.body
                if isinstance(statement, ast.Assign)
                for target in statement.targets
                if isinstance(target, ast.Name) and target.id == _CONSTANT
            ),
            None,
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == _CONSTANT:
                    return True
                if alias.name == "*" and module.endswith("identity_authoring"):
                    return True
        elif isinstance(node, ast.Name) and node.id == _CONSTANT:
            if node is defining_assignment_target:
                continue
            return True
        elif isinstance(node, ast.Attribute) and node.attr == _CONSTANT:
            return True
    return False


def test_defining_module_assignment_target_is_allowed():
    assert not _references_constant(_DEFINING_MODULE)


def test_defining_module_constant_load_is_forbidden(tmp_path: Path, monkeypatch):
    defining_module = tmp_path / "identity_authoring.py"
    defining_module.write_text(
        f'{_CONSTANT} = "fixed-default"\nresolved = {_CONSTANT}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "_DEFINING_MODULE", defining_module)

    assert _references_constant(defining_module)


def test_base_dataset_schema_profile_reference_is_commons_only():
    offenders = []
    for path in _SCIENCE_SRC.rglob("*.py"):
        if _ALLOWED_DIR in path.parents:
            continue
        if _references_constant(path):
            offenders.append(str(path.relative_to(_SCIENCE_SRC)))
    assert offenders == [], (
        f"{_CONSTANT} is the fixed gen-2 dataset profile; these non-commons modules reference it "
        f"instead of defaulting through project_dataset_schema_profile: {offenders}"
    )
