from __future__ import annotations

import science_tool.graph.sources as sources_mod


def test_load_loop_has_no_adapter_type_or_name_branching() -> None:
    src = sources_mod.__file__
    assert src is not None
    text = open(src, encoding="utf-8").read()
    # The loop must dispatch on declared policy, not adapter identity.
    assert "isinstance(adapter," not in text
    # `classify_owner_scope(adapter.name, ...)` is a value lookup and stays, but no
    # control-flow branch may compare adapter.name to a literal.
    assert "adapter.name ==" not in text
