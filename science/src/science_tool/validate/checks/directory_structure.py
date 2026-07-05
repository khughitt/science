"""Port of validate.sh "Checking directory structure..." block, lines 310-421."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.paths import ProjectPaths, resolve_paths
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "directory_structure", None)


@Check(section="directory structure...", order=2)
def check_directory_structure(ctx: ValidateContext) -> Iterator[Result]:
    paths = resolve_paths(ctx.project_root)
    profile = paths.profile

    required_dirs = [
        ("entities", ctx.project_root / "entities"),
        ("doc", paths.doc_dir),
        ("knowledge", paths.knowledge_dir),
        ("tasks", paths.tasks_dir),
        (paths.code_dir.name, paths.code_dir),
    ]
    if profile == "research":
        required_dirs.extend(
            [
                ("papers", paths.papers_dir),
                ("data", paths.data_dir),
                ("models", paths.models_dir),
                ("results", ctx.project_root / "results"),
            ]
        )

    for name, path in required_dirs:
        if not path.is_dir():
            yield _result(Severity.ERROR, name, f"Required directory missing: {name}/")
        else:
            yield _result(Severity.INFO, name, f"{name}/ exists")

    for name in ("CLAUDE.md", "AGENTS.md"):
        if not (ctx.project_root / name).is_file():
            yield _result(Severity.ERROR, name, f"Required file missing: {name}")
        else:
            yield _result(Severity.INFO, name, f"{name} exists")

    yield from _check_claude(ctx)
    yield from _check_agents(ctx)
    yield from _check_overview(ctx)
    yield from _check_research_plan(ctx, profile)
    yield from _check_duplicate_docs(ctx)
    yield from _check_declared_roots_exist(ctx, paths)
    yield from _check_legacy_roots(ctx, profile, paths)


def _check_claude(ctx: ValidateContext) -> Iterator[Result]:
    claude_path = ctx.project_root / "CLAUDE.md"
    if not claude_path.is_file():
        return

    lines = ctx.read_text_cached(claude_path).splitlines()
    nonblank = [line.strip() for line in lines if line.strip()]
    if "\n".join(nonblank) != "@AGENTS.md":
        yield _result(Severity.WARN, "CLAUDE.md", "CLAUDE.md should contain only @AGENTS.md")
    if _has_legacy_core_include(lines):
        yield _result(
            Severity.WARN,
            "CLAUDE.md",
            "CLAUDE.md contains legacy @core/* include(s) — keep core files as pointers from AGENTS.md",
        )


def _check_agents(ctx: ValidateContext) -> Iterator[Result]:
    agents_path = ctx.project_root / "AGENTS.md"
    if not agents_path.is_file():
        return

    text = ctx.read_text_cached(agents_path)
    if _has_legacy_core_include(text.splitlines()):
        yield _result(
            Severity.WARN,
            "AGENTS.md",
            "AGENTS.md contains legacy @core/* include(s) — use the Pointers section instead",
        )
    if "BEGIN: load-bearing-constraints" not in text or "END: load-bearing-constraints" not in text:
        yield _result(
            Severity.WARN,
            "AGENTS.md",
            "AGENTS.md missing managed load-bearing-constraints markers — run /science:curate or refresh from templates/agents-md.md",
        )


def _check_overview(ctx: ValidateContext) -> Iterator[Result]:
    overview_path = ctx.project_root / "core" / "overview.md"
    if not overview_path.is_file():
        return

    text = ctx.read_text_cached(overview_path)
    line_count = len(text.splitlines())
    word_count = len(text.split())
    if line_count > 150 or word_count > 1200:
        yield _result(
            Severity.WARN,
            "core/overview.md",
            f"core/overview.md is {line_count} lines / {word_count} words; keep it under 150 lines / 1200 words and move evidence narratives into canonical docs",
        )


def _check_research_plan(ctx: ValidateContext, profile: str) -> Iterator[Result]:
    plan_path = ctx.project_root / "RESEARCH_PLAN.md"
    readme_path = ctx.project_root / "README.md"
    if profile == "research":
        if plan_path.is_file():
            yield _result(Severity.INFO, "RESEARCH_PLAN.md", "RESEARCH_PLAN.md exists")
        elif readme_path.is_file():
            yield _result(Severity.INFO, "README.md", "README.md exists; RESEARCH_PLAN.md not required")
        else:
            yield _result(
                Severity.WARN,
                "RESEARCH_PLAN.md",
                "RESEARCH_PLAN.md not found (allowed if high-level planning is in README.md)",
            )
    elif plan_path.is_file():
        yield _result(Severity.INFO, "RESEARCH_PLAN.md", "RESEARCH_PLAN.md exists")


def _check_duplicate_docs(ctx: ValidateContext) -> Iterator[Result]:
    docs_path = ctx.project_root / "docs"
    doc_path = ctx.project_root / "doc"
    if not docs_path.is_dir() or not doc_path.is_dir():
        return

    has_duplicate_content = any(
        path.is_file() and not _is_allowed_superpowers_doc(path.relative_to(docs_path)) for path in docs_path.rglob("*")
    )
    if has_duplicate_content:
        yield _result(
            Severity.WARN,
            "docs",
            "Duplicate document roots detected: doc/ and docs/",
        )


def _check_declared_roots_exist(ctx: ValidateContext, paths: ProjectPaths) -> Iterator[Result]:
    for label, roots in (("code_roots", paths.code_roots), ("app_roots", paths.app_roots)):
        for root in roots:
            if root == paths.code_dir:
                continue
            if not root.is_dir():
                rel = root.relative_to(ctx.project_root).as_posix()
                yield _result(Severity.ERROR, rel, f"Declared {label} directory missing: {rel}/")


def _check_legacy_roots(ctx: ValidateContext, profile: str, paths: ProjectPaths) -> Iterator[Result]:
    code_dir_name = paths.code_dir.name
    if profile == "research":
        declared_roots = {p.relative_to(ctx.project_root).as_posix() for p in (*paths.code_roots, *paths.app_roots)}
        for dirname in ("scripts", "notebooks", "workflow"):
            if dirname in declared_roots:
                continue
            if (ctx.project_root / dirname).is_dir():
                yield _result(
                    Severity.WARN,
                    dirname,
                    f"Legacy top-level execution root detected: {dirname}/ — consolidate under {code_dir_name}/",
                )
        pipelines_path = ctx.project_root / code_dir_name / "pipelines"
        if pipelines_path.is_dir():
            yield _result(
                Severity.WARN,
                f"{code_dir_name}/pipelines",
                f"Legacy workflow directory detected: {code_dir_name}/pipelines/ — use {code_dir_name}/workflows/",
            )

    if profile == "software" and (ctx.project_root / "code").is_dir():
        yield _result(
            Severity.WARN,
            "code",
            "Software-profile project has top-level code/ — keep implementation in native roots such as src/",
        )

    for dirname in ("prompts", "templates"):
        if (ctx.project_root / dirname).is_dir():
            yield _result(
                Severity.WARN,
                dirname,
                f"Legacy top-level AI artifact root detected: {dirname}/ — use .ai/ overrides only when needed",
            )


def _has_legacy_core_include(lines: list[str]) -> bool:
    return any(line.strip().startswith("@core/") for line in lines if line.strip())


def _is_allowed_superpowers_doc(path: Path) -> bool:
    return len(path.parts) >= 2 and path.parts[0] == "superpowers"
