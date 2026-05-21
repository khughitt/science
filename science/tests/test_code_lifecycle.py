from science_tool.code.lifecycle import CODE_FILE_STATUSES


def test_lifecycle_vocabulary_is_exact() -> None:
    assert CODE_FILE_STATUSES == frozenset(
        {"exploratory", "workflow-owned", "library", "retired"}
    )


def test_vocabulary_is_immutable() -> None:
    assert isinstance(CODE_FILE_STATUSES, frozenset)


def test_orphan_gating_exempt_statuses() -> None:
    from science_tool.code.lifecycle import ORPHAN_GATING_EXEMPT_STATUSES

    assert ORPHAN_GATING_EXEMPT_STATUSES == frozenset({"exploratory", "retired"})
