from __future__ import annotations

import ast
from pathlib import Path

import pytest

from science_tool.autonomy.policy import (
    CREATION_ALLOWLIST,
    DEFAULT_DENY_REASON,
    FIELD_ALLOWLIST,
    denial_reason,
    is_creation_allowed,
    is_field_allowed,
)

POLICY_SOURCE = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "autonomy" / "policy.py"


def test_an_unregistered_field_is_denied_with_no_registration():
    """Design §4 default-deny: a field nobody has heard of needs no action to be denied."""
    assert is_field_allowed("paper", "zzz_field_invented_tomorrow") is False


def test_an_unregistered_kind_is_denied_entirely():
    assert is_field_allowed("hypothesis", "title") is False
    assert is_field_allowed("evidence-line", "strength") is False


def test_belief_bearing_fields_are_denied_on_every_allowlisted_kind():
    for kind in FIELD_ALLOWLIST:
        for field in ("confidence", "evidence_refs", "claim_layer", "aliases", "kind", "id", "related"):
            assert is_field_allowed(kind, field) is False, f"{kind}.{field} must be denied"


def test_creation_is_denied_for_every_kind():
    """S1 grants no creation surface; the table exists so Plan D has a place to argue."""
    assert dict(CREATION_ALLOWLIST) == {}
    assert is_creation_allowed("paper", "title") is False


def test_named_denial_reasons_cover_the_design_table():
    assert "payload boundary" in denial_reason("data/raw/counts.tsv")
    assert "durable writer" in denial_reason("knowledge/graph.trig")
    assert "schema-version pin" in denial_reason("science.yaml")
    assert "guard integrity" in denial_reason("core/decisions.md")
    assert "supervisor-owned" in denial_reason("runs/2026-07-25-sweep-a3f1.md")
    assert "toolchain" in denial_reason("uv.lock")


def test_an_unnamed_path_still_gets_the_default_deny_reason():
    assert denial_reason("some/path/nobody/enumerated.txt") == DEFAULT_DENY_REASON


def test_allowlists_cannot_be_mutated_at_runtime():
    """Layer 3 is one-way (design §5): nothing may write the allowlist."""
    with pytest.raises(TypeError):
        FIELD_ALLOWLIST["paper"] = frozenset({"confidence"})  # type: ignore[index]


def test_policy_module_reads_no_project_state():
    """Design §4: the gate is NOT project-overridable. An override is a hole that will be
    widened under pressure by the very agents it constrains. This is the guard."""
    # An ALLOWLIST, not a blacklist. A blacklist cannot express "reads no project
    # state": any unlisted module (`science_tool.project_config`, `configparser`,
    # `importlib.resources`, ...) walks straight through it. These four are everything
    # policy.py legitimately needs, plus the pure filename constant imported directly
    # from its single authority. Anything else is a design change that must be argued
    # for here first.
    permitted_imports = {
        "__future__",
        "collections.abc",
        "science_model.frontmatter",
        "types",
    }
    tree = ast.parse(POLICY_SOURCE.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert imported <= permitted_imports, (
        f"policy.py imports {sorted(imported - permitted_imports)}. The gate is not "
        "project-overridable: it must read no project state. Widening this allowlist is "
        "a design change, not a fix."
    )
    frontmatter_imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "science_model.frontmatter"
        for alias in node.names
    ]
    assert frontmatter_imports == ["PROJECT_CONFIG_FILENAME"], (
        "policy.py may import only the pure PROJECT_CONFIG_FILENAME authority from "
        "science_model.frontmatter; path helpers would make project-state access possible."
    )
