from __future__ import annotations

from collections.abc import Iterable
import importlib
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path, *, profile: str = "research", extra: str = "") -> None:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                f"profile: {profile}",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
                extra,
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path, *, profile: str = "research", extra_manifest: str = "") -> ValidateContext:
    _write_manifest(root, profile=profile, extra=extra_manifest)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _messages(results: Iterable[Result]) -> list[str]:
    return [result.message for result in results]


def test_importing_checks_registers_first_canonical_checks_in_order() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.directory_structure as directory_structure
    import science_tool.validate.checks.manifest as manifest
    import science_tool.validate.checks.tooling as tooling

    importlib.reload(tooling)
    importlib.reload(manifest)
    importlib.reload(directory_structure)

    assert [(entry.section, entry.order) for entry in CANONICAL_CHECKS[:3]] == [
        ("tooling scaffold...", 0),
        ("project manifest...", 1),
        ("directory structure...", 2),
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
