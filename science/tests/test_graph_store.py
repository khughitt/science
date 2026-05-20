from __future__ import annotations

from science_tool.graph.store import GRAPH_EXPORT_EDGE_METADATA_PREDICATES, SCI_NS


def test_sci_scope_is_registered_as_entity_metadata_predicate() -> None:
    """`sci:scope` is emitted by `_add_entity` as entity-level metadata
    (literal object), not an inter-entity edge. It must appear in the
    metadata-predicate allowlist so `store.py` does not misclassify it as
    a knowledge-graph edge."""
    assert SCI_NS.scope in GRAPH_EXPORT_EDGE_METADATA_PREDICATES
