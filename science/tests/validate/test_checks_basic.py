from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path, *, profile: str = "research", extra: str = "", layout_version: int = 1) -> None:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                f"profile: {profile}",
                f"layout_version: {layout_version}",
                "knowledge_profiles:",
                "  local: knowledge/local",
                extra,
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path, *, profile: str = "research", extra_manifest: str = "", layout_version: int = 1) -> ValidateContext:
    _write_manifest(root, profile=profile, extra=extra_manifest, layout_version=layout_version)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _messages(results: Iterable[Result]) -> list[str]:
    return [result.message for result in results]


def test_importing_checks_registers_first_canonical_checks_in_order() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.directory_structure as directory_structure
    import science_tool.validate.checks.document_structure as document_structure
    import science_tool.validate.checks.hypotheses as hypotheses
    import science_tool.validate.checks.manifest as manifest
    import science_tool.validate.checks.research_scope as research_scope
    import science_tool.validate.checks.tooling as tooling

    importlib.reload(tooling)
    importlib.reload(manifest)
    importlib.reload(directory_structure)
    importlib.reload(research_scope)
    importlib.reload(document_structure)
    importlib.reload(hypotheses)

    assert [(entry.section, entry.order) for entry in CANONICAL_CHECKS[:6]] == [
        ("tooling scaffold...", 0),
        ("project manifest...", 1),
        ("directory structure...", 2),
        ("research scope...", 3),
        ("document structure...", 4),
        ("hypotheses...", 5),
    ]


def test_tooling_warns_when_pyproject_and_env_are_missing(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)

    results = list(check_tooling(ctx))

    assert (Severity.WARN, "pyproject.toml missing") in [
        (result.severity, result.message.split(" — ")[0]) for result in results
    ]
    assert (
        Severity.WARN,
        ".env missing — SCIENCE_TOOL_PATH is unset (fix: create .env with `SCIENCE_TOOL_PATH=<absolute-path-to-science>`)",
    ) in [(result.severity, result.message) for result in results]


def test_tooling_reports_present_pyproject_science_reference_and_env(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname = 'science-demo'\n", encoding="utf-8")
    tmp_path.joinpath(".env").write_text("SCIENCE_TOOL_PATH=/tmp/science\n", encoding="utf-8")

    results = list(check_tooling(ctx))

    assert _messages(results) == [
        "pyproject.toml present",
        "  science reference present",
        ".env defines SCIENCE_TOOL_PATH",
    ]
    assert [result.severity for result in results] == [Severity.INFO, Severity.INFO, Severity.INFO]


def test_tooling_warns_when_pyproject_does_not_reference_science(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    results = list(check_tooling(ctx))

    assert (
        Severity.WARN,
        'pyproject.toml does not reference science (fix: `uv add --dev --editable "$SCIENCE_TOOL_PATH"`)',
    ) in [(result.severity, result.message) for result in results]


def test_tooling_warns_when_env_lacks_science_tool_path(tmp_path: Path) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)
    tmp_path.joinpath(".env").write_text("OTHER=value\nexport SCIENCE_TOOL_PATH=/tmp/science\n", encoding="utf-8")

    results = list(check_tooling(ctx))

    assert (
        Severity.WARN,
        ".env exists but does not define SCIENCE_TOOL_PATH (fix: add `SCIENCE_TOOL_PATH=<absolute-path>` to .env)",
    ) in [(result.severity, result.message) for result in results]


def test_tooling_warns_when_env_cannot_be_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.tooling import check_tooling

    ctx = _ctx(tmp_path)
    tmp_path.joinpath(".env").write_text("SCIENCE_TOOL_PATH=/tmp/science\n", encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs):
        if self.name == ".env":
            raise PermissionError("simulated denied .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    results = list(check_tooling(ctx))

    assert (
        Severity.WARN,
        ".env exists but could not be inspected; skipping secret file contents: simulated denied .env",
    ) in [(result.severity, result.message) for result in results]
    assert not any(result.rule == "validate.check-error" for result in results)


def test_manifest_reports_missing_required_fields_and_bad_knowledge_profiles(tmp_path: Path) -> None:
    from science_tool.validate.checks.manifest import check_manifest

    tmp_path.joinpath("science.yaml").write_text("name: demo\nknowledge_profiles: []\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)

    results = list(check_manifest(ctx))
    messages = _messages(results)

    assert "science.yaml exists" in messages
    assert "  name: present" in messages
    assert "science.yaml missing required field: created" in messages
    assert "science.yaml missing required knowledge_profiles section" in messages
    assert any(result.severity is Severity.ERROR for result in results)


def test_manifest_validates_knowledge_profile_shapes(tmp_path: Path) -> None:
    from science_tool.validate.checks.manifest import check_manifest

    ctx = _ctx(tmp_path, extra_manifest="  curated: curated-profile\nontologies: ontology")

    results = list(check_manifest(ctx))

    assert "science.yaml knowledge_profiles.curated must be a list" in _messages(results)


def test_manifest_reports_missing_or_empty_local_knowledge_profile(tmp_path: Path) -> None:
    from science_tool.validate.checks.manifest import check_manifest

    ctx = _ctx(tmp_path, extra_manifest="  local: ''")

    results = list(check_manifest(ctx))

    assert "science.yaml knowledge_profiles.local missing or empty" in _messages(results)


def test_manifest_reports_missing_local_knowledge_profile_key(tmp_path: Path) -> None:
    from science_tool.validate.checks.manifest import check_manifest

    tmp_path.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  curated: []",
            ]
        ),
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)

    results = list(check_manifest(ctx))

    assert "science.yaml knowledge_profiles.local missing or empty" in _messages(results)


def test_manifest_reports_invalid_top_level_ontologies_shape(tmp_path: Path) -> None:
    from science_tool.validate.checks.manifest import check_manifest

    ctx = _ctx(tmp_path, extra_manifest="ontologies: ontology")

    results = list(check_manifest(ctx))

    assert "science.yaml ontologies must be a list" in _messages(results)


def test_directory_structure_checks_research_required_dirs_and_files(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research")
    for dirname in ("specs", "doc", "knowledge", "tasks", "code", "papers", "data", "models"):
        tmp_path.joinpath(dirname).mkdir()
    tmp_path.joinpath("AGENTS.md").write_text(
        "BEGIN: load-bearing-constraints\nEND: load-bearing-constraints\n",
        encoding="utf-8",
    )

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "code/ exists" in messages
    assert "papers/ exists" in messages
    assert "Required directory missing: results/" in messages
    assert "Required file missing: CLAUDE.md" in messages
    assert "AGENTS.md exists" in messages


def test_directory_structure_reports_readme_as_project_document(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research")
    tmp_path.joinpath("README.md").write_text("# Demo\n", encoding="utf-8")

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "README.md exists" in messages
    assert "Required project README missing: README.md" not in messages


def test_directory_structure_uses_src_for_software_and_warns_about_code(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="software")
    for dirname in ("specs", "doc", "knowledge", "tasks", "src", "code"):
        tmp_path.joinpath(dirname).mkdir()
    tmp_path.joinpath("CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    tmp_path.joinpath("AGENTS.md").write_text(
        "BEGIN: load-bearing-constraints\nEND: load-bearing-constraints\n",
        encoding="utf-8",
    )

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "src/ exists" in messages
    assert "Software-profile project has top-level code/ — keep implementation in native roots such as src/" in messages
    assert "Required directory missing: code/" not in messages


def test_directory_structure_warns_about_agents_and_duplicate_docs_roots(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="software")
    for dirname in ("specs", "doc", "knowledge", "tasks", "src"):
        tmp_path.joinpath(dirname).mkdir()
    tmp_path.joinpath("docs").mkdir()
    tmp_path.joinpath("docs", "guide.md").write_text("guide\n", encoding="utf-8")
    tmp_path.joinpath("CLAUDE.md").write_text("@AGENTS.md\n@core/overview.md\n", encoding="utf-8")
    tmp_path.joinpath("AGENTS.md").write_text("@core/overview.md\n", encoding="utf-8")

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "CLAUDE.md should contain only @AGENTS.md" in messages
    assert "CLAUDE.md contains legacy @core/* include(s) — keep core files as pointers from AGENTS.md" in messages
    assert "AGENTS.md contains legacy @core/* include(s) — use the Pointers section instead" in messages
    assert (
        "AGENTS.md missing managed load-bearing-constraints markers — run /science:curate or refresh from templates/agents-md.md"
        in messages
    )
    assert "Duplicate document roots detected: doc/ and docs/" in messages


def test_research_scope_requires_research_question_for_research_profile(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_scope import check_research_scope

    ctx = _ctx(tmp_path, profile="research")
    tmp_path.joinpath("specs").mkdir()

    results = list(check_research_scope(ctx))

    assert [(result.severity, result.path, result.message) for result in results] == [
        (
            Severity.ERROR,
            Path("entities/research-question.md"),
            "research-question.md not found — every project needs a research question",
        )
    ]


def test_research_scope_skips_non_research_profile(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_scope import check_research_scope

    ctx = _ctx(tmp_path, profile="software")

    assert list(check_research_scope(ctx)) == []


def test_research_scope_defaults_missing_profile_to_research(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_scope import check_research_scope

    tmp_path.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)

    results = list(check_research_scope(ctx))

    assert (
        Severity.ERROR,
        "research-question.md not found — every project needs a research question",
    ) in [(result.severity, result.message) for result in results]


def test_document_structure_warns_for_missing_topic_and_paper_sections(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    topics_dir = tmp_path / "entities" / "topics"
    papers_dir = tmp_path / "entities" / "papers"
    topics_dir.mkdir(parents=True)
    papers_dir.mkdir(parents=True)
    topics_dir.joinpath("topic.md").write_text("## Summary\n\nBody\n", encoding="utf-8")
    papers_dir.joinpath("paper.md").write_text("## Methods\n\nBody\n", encoding="utf-8")

    results = list(check_document_structure(ctx))
    messages = _messages(results)

    assert "Checking entities/topics/topic.md..." in messages
    assert "entities/topics/topic.md missing section: ## Key Concepts" in messages
    assert "entities/topics/topic.md missing section: ## Current State of Knowledge" in messages
    assert "entities/topics/topic.md missing section: ## Relevance to This Project" in messages
    assert "entities/topics/topic.md missing section: ## Key References" in messages
    assert "Checking entities/papers/paper.md..." in messages
    assert "entities/papers/paper.md missing section: ## Key Contribution" in messages
    assert "entities/papers/paper.md missing section: ## Key Findings" in messages
    assert "entities/papers/paper.md missing section: ## Relevance" in messages


def test_document_structure_complete_docs_have_no_missing_section_warnings(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    topics_dir = tmp_path / "entities" / "topics"
    papers_dir = tmp_path / "entities" / "papers"
    topics_dir.mkdir(parents=True)
    papers_dir.mkdir(parents=True)
    topics_dir.joinpath("topic.md").write_text(
        "\n".join(
            [
                "## Summary",
                "## Key Concepts",
                "## Current State of Knowledge",
                "## Relevance to This Project",
                "## Key References",
            ]
        ),
        encoding="utf-8",
    )
    papers_dir.joinpath("paper.md").write_text(
        "\n".join(["## Key Contribution", "## Methods", "## Key Findings", "## Relevance"]),
        encoding="utf-8",
    )

    results = list(check_document_structure(ctx))

    assert [result.severity for result in results] == [Severity.INFO, Severity.INFO]


def test_document_structure_skips_literature_survey_paper_notes(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    papers_dir = tmp_path / "entities" / "papers"
    papers_dir.mkdir(parents=True)
    papers_dir.joinpath("survey.md").write_text(
        "---\nid: paper:survey\nkind: paper\ntitle: Survey\npaper_kind: literature-survey\n---\n"
        "## Scope\n\nBody\n## Synthesis\n\nBody\n",
        encoding="utf-8",
    )

    results = list(check_document_structure(ctx))
    messages = _messages(results)

    assert "Checking entities/papers/survey.md..." in messages
    assert not any("entities/papers/survey.md missing section" in message for message in messages)


def test_document_structure_requires_exact_h2_headings(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    topics_dir = tmp_path / "entities" / "topics"
    topics_dir.mkdir(parents=True)
    topics_dir.joinpath("topic.md").write_text(
        "\n".join(
            [
                "### Summary",
                "## Key Concepts",
                "## Current State of Knowledge",
                "## Relevance to This Project",
                "## Key References",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_document_structure(ctx))

    assert "entities/topics/topic.md missing section: ## Summary" in messages


def test_document_structure_rejects_indented_h2_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    topics_dir = tmp_path / "entities" / "topics"
    topics_dir.mkdir(parents=True)
    topics_dir.joinpath("topic.md").write_text(
        "\n".join(
            [
                "    ## Summary",
                "## Key Concepts",
                "## Current State of Knowledge",
                "## Relevance to This Project",
                "## Key References",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_document_structure(ctx))

    assert "entities/topics/topic.md missing section: ## Summary" in messages


def test_document_structure_rejects_fenced_h2_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    topics_dir = tmp_path / "entities" / "topics"
    topics_dir.mkdir(parents=True)
    topics_dir.joinpath("topic.md").write_text(
        "\n".join(
            [
                "```markdown",
                "## Summary",
                "```",
                "## Key Concepts",
                "## Current State of Knowledge",
                "## Relevance to This Project",
                "## Key References",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_document_structure(ctx))

    assert "entities/topics/topic.md missing section: ## Summary" in messages


def test_document_structure_rejects_tilde_fenced_h2_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.document_structure import check_document_structure

    ctx = _ctx(tmp_path)
    topics_dir = tmp_path / "entities" / "topics"
    topics_dir.mkdir(parents=True)
    topics_dir.joinpath("topic.md").write_text(
        "\n".join(
            [
                "~~~markdown",
                "## Summary",
                "~~~",
                "## Key Concepts",
                "## Current State of Knowledge",
                "## Relevance to This Project",
                "## Key References",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_document_structure(ctx))

    assert "entities/topics/topic.md missing section: ## Summary" in messages


def test_hypotheses_missing_falsifiability_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text("- **Status:** active\n", encoding="utf-8")

    results = list(check_hypotheses(ctx))

    assert (
        Severity.ERROR,
        "entities/hypotheses/h1.md missing ## Falsifiability section",
    ) in [(result.severity, result.message) for result in results]


def test_hypotheses_requires_exact_h2_falsifiability_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text("- **Status:** active\n### Falsifiability\nContent\n", encoding="utf-8")

    results = list(check_hypotheses(ctx))

    assert (
        Severity.ERROR,
        "entities/hypotheses/h1.md missing ## Falsifiability section",
    ) in [(result.severity, result.message) for result in results]


def test_hypotheses_rejects_indented_h2_falsifiability_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "- **Status:** active\n    ## Falsifiability\nContent\n", encoding="utf-8"
    )

    results = list(check_hypotheses(ctx))

    assert (
        Severity.ERROR,
        "entities/hypotheses/h1.md missing ## Falsifiability section",
    ) in [(result.severity, result.message) for result in results]


def test_hypotheses_rejects_fenced_h2_falsifiability_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "\n".join(["- **Status:** active", "```markdown", "## Falsifiability", "```", "Content"]),
        encoding="utf-8",
    )

    results = list(check_hypotheses(ctx))

    assert (
        Severity.ERROR,
        "entities/hypotheses/h1.md missing ## Falsifiability section",
    ) in [(result.severity, result.message) for result in results]


def test_hypotheses_rejects_indented_fenced_h2_falsifiability_heading(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "\n".join(["- **Status:** active", "   ```markdown", "## Falsifiability", "   ```", "Content"]),
        encoding="utf-8",
    )

    results = list(check_hypotheses(ctx))

    assert (
        Severity.ERROR,
        "entities/hypotheses/h1.md missing ## Falsifiability section",
    ) in [(result.severity, result.message) for result in results]


def test_hypotheses_empty_falsifiability_warns_but_content_passes(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "\n".join(["- **Status:** active", "## Falsifiability", "<!-- fill this in -->", "", "## Evidence"]),
        encoding="utf-8",
    )
    hypotheses_dir.joinpath("h2.md").write_text(
        "\n".join(["- **Status:** active", "## Falsifiability", "Could be falsified by x.", "## Evidence"]),
        encoding="utf-8",
    )

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/h1.md has empty Falsifiability section" in messages
    assert "entities/hypotheses/h2.md has empty Falsifiability section" not in messages


def test_hypotheses_subheading_and_multiline_comment_only_falsifiability_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "\n".join(
            [
                "- **Status:** active",
                "## Falsifiability",
                "### Criteria",
                "<!--",
                "template guidance",
                "-->",
                "## Evidence",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/h1.md has empty Falsifiability section" in messages


def test_hypotheses_status_can_be_frontmatter_or_inline(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text("## Falsifiability\nContent\n", encoding="utf-8")
    hypotheses_dir.joinpath("h2.md").write_text(
        "---\nstatus: active\n---\n## Falsifiability\nContent\n", encoding="utf-8"
    )
    hypotheses_dir.joinpath("h3.md").write_text(
        "- **Status:** candidate\n## Falsifiability\nContent\n", encoding="utf-8"
    )

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/h1.md missing Status field" in messages
    assert "entities/hypotheses/h2.md missing Status field" not in messages
    assert "entities/hypotheses/h3.md missing Status field" not in messages


def test_hypotheses_raw_top_level_status_line_satisfies_status(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text("status: active\n## Falsifiability\nContent\n", encoding="utf-8")

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/h1.md missing Status field" not in messages


def test_hypotheses_phase_validation(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "---\nstatus: active\nphase: proposed # template comment\n---\n## Falsifiability\nContent\n",
        encoding="utf-8",
    )
    hypotheses_dir.joinpath("h2.md").write_text(
        "---\nstatus: active\nphase: candidate\n---\n## Falsifiability\nContent\n",
        encoding="utf-8",
    )
    hypotheses_dir.joinpath("h3.md").write_text(
        "---\nstatus: active\nphase: 'active'\n---\n## Falsifiability\nContent\n",
        encoding="utf-8",
    )

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/h1.md has invalid phase 'proposed' (must be 'candidate' or 'active')" in messages
    assert "specs/hypotheses/h2.md has invalid phase 'candidate' (must be 'candidate' or 'active')" not in messages
    assert "specs/hypotheses/h3.md has invalid phase 'active' (must be 'candidate' or 'active')" not in messages


def test_hypotheses_warns_for_non_positive_review_horizon_under_entities(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hyp_dir = tmp_path / "entities" / "hypotheses"
    find_dir = tmp_path / "entities" / "findings"
    hyp_dir.mkdir(parents=True)
    find_dir.mkdir(parents=True)
    hyp_dir.joinpath("bad.md").write_text(
        "---\nreview_state:\n  review_horizon_days: 0\n---\nBody\n",
        encoding="utf-8",
    )
    find_dir.joinpath("bad.md").write_text(
        "---\nreview_state:\n  review_horizon_days: -2\n---\nBody\n",
        encoding="utf-8",
    )
    find_dir.joinpath("good.md").write_text(
        "---\nreview_state:\n  review_horizon_days: 1\n---\nBody\n",
        encoding="utf-8",
    )

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/bad.md: review_state.review_horizon_days must be positive (got 0)" in messages
    assert "entities/findings/bad.md: review_state.review_horizon_days must be positive (got -2)" in messages
    assert "entities/findings/good.md: review_state.review_horizon_days must be positive (got 1)" not in messages


def test_hypotheses_warns_for_quoted_numeric_review_horizon(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hyp_dir = tmp_path / "entities" / "hypotheses"
    hyp_dir.mkdir(parents=True)
    hyp_dir.joinpath("bad.md").write_text(
        '---\nreview_state:\n  review_horizon_days: "0"\n---\nBody\n',
        encoding="utf-8",
    )
    hyp_dir.joinpath("ignored.md").write_text(
        "---\nreview_state:\n  review_horizon_days: soon\n---\nBody\n",
        encoding="utf-8",
    )

    messages = _messages(check_hypotheses(ctx))

    assert "entities/hypotheses/bad.md: review_state.review_horizon_days must be positive (got 0)" in messages
    assert not any(
        message.startswith("entities/hypotheses/ignored.md: review_state.review_horizon_days") for message in messages
    )


def test_hypotheses_ignores_malformed_frontmatter_during_review_horizon_scan(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    # Under entities/findings (not entities/hypotheses) so only the review_horizon
    # scan inspects it — the structural hypotheses-dir check would flag a broken
    # hypothesis file regardless of horizon.
    find_dir = tmp_path / "entities" / "findings"
    find_dir.mkdir(parents=True)
    find_dir.joinpath("broken.md").write_text("---\nreview_state: [\n---\nBody\n", encoding="utf-8")

    results = list(check_hypotheses(ctx))

    assert results == []


def test_hypotheses_ignores_malformed_frontmatter_in_hypothesis_file(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypotheses import check_hypotheses

    ctx = _ctx(tmp_path)
    hypotheses_dir = tmp_path / "entities" / "hypotheses"
    hypotheses_dir.mkdir(parents=True)
    hypotheses_dir.joinpath("h1.md").write_text(
        "\n".join(["---", "status: [", "---", "- **Status:** active", "## Falsifiability", "Content"]),
        encoding="utf-8",
    )

    results = list(check_hypotheses(ctx))

    assert "Checking entities/hypotheses/h1.md..." in _messages(results)


def test_declared_code_root_not_flagged_as_legacy(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", extra_manifest="code_roots:\n  - code\n  - scripts")
    (tmp_path / "scripts").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert not any("Legacy top-level execution root detected: scripts" in m for m in messages)


def test_undeclared_scripts_still_flagged_as_legacy(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research")
    (tmp_path / "scripts").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert any("Legacy top-level execution root detected: scripts" in m for m in messages)


def test_missing_declared_code_root_is_error(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", extra_manifest="code_roots:\n  - code\n  - scripst")
    (tmp_path / "code").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert any("Declared code_roots directory missing: scripst/" in m for m in messages)


def test_multicomponent_declared_root_does_not_suppress_top_level_legacy(tmp_path: Path) -> None:
    from science_tool.validate.checks.directory_structure import check_directory_structure

    # A declared root of `src/scripts` must not suppress the legacy warning for an
    # unrelated top-level `scripts/` (the declared root is matched by full relative
    # path, not basename).
    ctx = _ctx(tmp_path, profile="research", extra_manifest="code_roots:\n  - src/scripts")
    (tmp_path / "src" / "scripts").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    messages = _messages(check_directory_structure(ctx))
    assert any("Legacy top-level execution root detected: scripts" in m for m in messages)


def test_context_rejects_absolute_code_root(tmp_path: Path) -> None:
    from science_tool.validate.context import ValidateContext, ValidateContextError

    _write_manifest(tmp_path, extra="code_roots:\n  - /etc")
    with pytest.raises(ValidateContextError, match="relative paths inside the project"):
        ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def test_context_rejects_non_list_code_roots(tmp_path: Path) -> None:
    from science_tool.validate.context import ValidateContext, ValidateContextError

    _write_manifest(tmp_path, extra="code_roots: code")
    with pytest.raises(ValidateContextError, match="must be a list of strings"):
        ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def test_layout_version_below_3_errors(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\ncreated: 2026-01-01\nlast_modified: 2026-01-01\nstatus: active\n"
        "summary: s\nprofile: research\nlayout_version: 2\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    from science_tool.validate.checks.manifest import check_manifest
    results = list(check_manifest(ctx))
    assert any(r.severity is Severity.ERROR and "layout_version" in r.message for r in results)


# ---------------------------------------------------------------------------
# Task 8: directory_structure version-gating tests
# ---------------------------------------------------------------------------

def test_directory_structure_v3_no_error_for_missing_specs(tmp_path: Path) -> None:
    """layout_version: 3 project with entities/ but no specs/ must NOT error on missing specs/."""
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", layout_version=3)
    for dirname in ("doc", "knowledge", "tasks", "code", "entities"):
        tmp_path.joinpath(dirname).mkdir()

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "Required directory missing: specs/" not in messages


def test_directory_structure_v3_errors_when_entities_missing(tmp_path: Path) -> None:
    """layout_version: 3 project with NO entities/ IS flagged as an error."""
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", layout_version=3)
    for dirname in ("doc", "knowledge", "tasks", "code"):
        tmp_path.joinpath(dirname).mkdir()
    # entities/ intentionally absent

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "Required directory missing: entities/" in messages


def test_directory_structure_requires_entities_even_when_manifest_is_v2(tmp_path: Path) -> None:
    """layout_version: 2 is invalid, but directory structure still enforces the current layout."""
    from science_tool.validate.checks.directory_structure import check_directory_structure

    ctx = _ctx(tmp_path, profile="research", layout_version=2)
    for dirname in ("doc", "knowledge", "tasks", "code"):
        tmp_path.joinpath(dirname).mkdir()
    # entities/ intentionally absent

    results = list(check_directory_structure(ctx))
    messages = _messages(results)

    assert "Required directory missing: entities/" in messages
    assert "Required directory missing: specs/" not in messages
