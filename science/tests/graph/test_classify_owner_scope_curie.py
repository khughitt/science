# tests/graph/test_classify_owner_scope_curie.py
from __future__ import annotations

from science_tool.graph.identity_table import classify_owner_scope


def test_curie_ref_is_nondeprecated_authority_scope() -> None:
    assert classify_owner_scope("curie-ref", project_name="demo") == ("curie-ref", False)
