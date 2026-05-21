from science_tool.code.lifecycle import CODE_FILE_STATUSES


def test_lifecycle_vocabulary_is_exact() -> None:
    assert CODE_FILE_STATUSES == frozenset(
        {"exploratory", "workflow-owned", "library", "retired"}
    )


def test_vocabulary_is_immutable() -> None:
    assert isinstance(CODE_FILE_STATUSES, frozenset)
