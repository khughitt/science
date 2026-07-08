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


def test_exclude_paths_defaults_to_empty(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint is not None
    assert config.prose_lint.exclude_paths == []


def test_exclude_paths_explicit_list(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  exclude_paths:\n"
        "    - 'doc/plans/historical/**'\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint.exclude_paths == ["doc/plans/historical/**"]


def test_short_form_ids_deny_defaults_to_empty(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint is not None
    assert config.prose_lint.short_form_ids_deny == []


def test_short_form_ids_deny_explicit_list(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  short_form_ids_deny:\n"
        "    - 'D1'\n"
        "    - 'H3'\n"
        "    - 'T1'\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint.short_form_ids_deny == ["D1", "H3", "T1"]


def test_bare_author_year_deny_defaults_to_empty(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint is not None
    assert config.prose_lint.bare_author_year_deny == []


def test_bare_author_year_deny_explicit_list(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "prose_lint:\n"
        "  bare_author_year_deny:\n"
        "    - 'IMMULITE 2000'\n"
        "    - 'CDC 2011'\n"
    )
    config = load_project_config(tmp_path)
    assert config.prose_lint.bare_author_year_deny == ["IMMULITE 2000", "CDC 2011"]
