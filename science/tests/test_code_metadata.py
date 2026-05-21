from science_tool.code.metadata import parse_code_metadata


def test_absent_when_no_block() -> None:
    result = parse_code_metadata("print('hi')\n")
    assert result.present is False
    assert result.fields is None
    assert result.valid is False


def test_parses_valid_block_with_yaml_types() -> None:
    text = (
        "# science:code\n"
        "# task_ids: [t491, t528]\n"
        "# decision_bearing: true\n"
        "# status: workflow-owned\n"
        "# science:end\n"
        "print(1)\n"
    )
    result = parse_code_metadata(text)
    assert result.valid is True
    assert result.fields == {
        "task_ids": ["t491", "t528"],
        "decision_bearing": True,
        "status": "workflow-owned",
    }


def test_empty_block_is_valid_empty_mapping() -> None:
    result = parse_code_metadata("# science:code\n# science:end\n")
    assert result.valid is True
    assert result.fields == {}


def test_unterminated_block_is_invalid_with_error() -> None:
    result = parse_code_metadata("# science:code\n# status: library\n")
    assert result.present is True
    assert result.fields is None
    assert "unterminated" in (result.error or "")


def test_non_mapping_block_is_invalid() -> None:
    text = "# science:code\n# - just\n# - a list\n# science:end\n"
    result = parse_code_metadata(text)
    assert result.present is True
    assert result.fields is None
    assert result.error is not None


def test_sentinel_substring_in_code_is_not_a_block() -> None:
    result = parse_code_metadata('msg = "science:code"\nx = 1\n')
    assert result.present is False


def test_end_marker_before_start_is_ignored() -> None:
    text = 'note = "science:end"\n# science:code\n# status: library\n# science:end\n'
    result = parse_code_metadata(text)
    assert result.valid is True
    assert result.fields == {"status": "library"}


def test_double_hash_comment_delimiters() -> None:
    result = parse_code_metadata("## science:code\n## status: library\n## science:end\n")
    assert result.valid is True
    assert result.fields == {"status": "library"}
