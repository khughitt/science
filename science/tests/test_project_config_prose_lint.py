from science_tool.project_config import (
    DEFAULT_ANCHOR_PATTERNS,
    load_project_config,
)


def test_default_anchor_patterns_when_block_absent(tmp_path):
    (tmp_path / "science.yaml").write_text("name: demo\n")
    config = load_project_config(tmp_path)
    assert config.prose_lint is None
    # Caller resolves defaults via DEFAULT_ANCHOR_PATTERNS.
    assert "task:" in DEFAULT_ANCHOR_PATTERNS


def test_explicit_anchor_patterns(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  anchor_patterns:\n"
        "    - 'task:'\n"
        "    - 'doc/'\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint is not None
    assert config.prose_lint.anchor_patterns == ["task:", "doc/"]


def test_enabled_checks(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  enabled_checks:\n"
        "    - bare-author-year\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint.enabled_checks == ["bare-author-year"]
