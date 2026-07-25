"""The import boundary — a module must load without help from whatever ran first.

`science_tool.entities` imports from `science_tool.graph`; `graph/__init__`
re-exports `materialize`, which reaches `commons.datapackage`; importing that
runs `commons/__init__`, which imports `commons.validator` — which imported
`entities` back, for `valid_statuses`. A cycle, closed.

Python does not raise on a cycle, it raises on a *name that is not bound yet*,
so the failure was invisible from the whole suite: something always imported
`graph` or `commons` before `entities` got there, completing the package and
leaving the cycle harmless. It surfaced only as `pytest tests/test_entities.py`
— a single module, run alone, whose first `science_tool` import was `entities`.
That is a real way to run tests, so the passing suite was not evidence.

The fix moved the profile-declared vocabulary down to `kind_descriptors`, which
imports `science_model` only, so `commons.validator` no longer reaches up
through `entities` to read it. These tests hold that floor: each import runs in
a **fresh interpreter**, because an in-process import proves nothing once the
suite has already populated `sys.modules`.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

#: Both ends of the repaired cycle plus the hubs that sit on it. Importing
#: `entities` first is the exact reproduction; the others fail the same way if a
#: future edge re-closes the loop from the other side.
CYCLE_SENSITIVE_MODULES = [
    "science_tool.entities",
    "science_tool.commons",
    "science_tool.commons.validator",
    "science_tool.graph",
    "science_tool.graph.materialize",
    "science_tool.kind_descriptors",
    "science_tool.cli",
]


@pytest.mark.parametrize("module", CYCLE_SENSITIVE_MODULES)
def test_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`import {module}` fails when it is the first science_tool module loaded:\n{result.stderr}"
    )


def test_kind_descriptors_does_not_import_science_tool() -> None:
    """The floor holds only while `kind_descriptors` stays a leaf.

    Any `science_tool` import here re-opens the path back up to `entities` and
    puts the cycle back, so this is checked structurally rather than left to the
    module docstring.
    """
    import ast
    import inspect

    from science_tool import kind_descriptors

    source = inspect.getsource(kind_descriptors)
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    offenders = [name for name in imported if name.split(".")[0] == "science_tool"]
    assert offenders == [], f"kind_descriptors must import science_model only, not {offenders}"


def test_commons_validator_reads_the_shared_vocabulary() -> None:
    """The cycle break must not have forked the vocabulary into a second copy.

    Reading a private table is deliberate: the point of the assertion is that
    these are the *same object*, which a public accessor would hide.
    """
    from science_tool.entities import _STATUS_VALUES
    from science_tool.kind_descriptors import DECLARED_STATUSES

    assert _STATUS_VALUES is DECLARED_STATUSES
