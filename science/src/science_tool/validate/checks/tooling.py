"""Port of validate.sh "Checking tooling scaffold..." block, lines 212-243."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "tooling", None)


@Check(section="tooling scaffold...", order=0)
def check_tooling(ctx: ValidateContext) -> Iterator[Result]:
    """Validate static tooling scaffold files.

    The optional bash smoke test for `uv run science --help` is intentionally
    left for a later parity slice because this check must not spawn subprocesses.
    """

    pyproject_path = ctx.project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        yield _result(
            Severity.WARN,
            "pyproject.toml",
            'pyproject.toml missing — `uv run science ...` cannot resolve (fix: see commands/create-project.md, then `uv add --dev --editable "$SCIENCE_TOOL_PATH"`)',
        )
    else:
        yield _result(Severity.INFO, "pyproject.toml", "pyproject.toml present")
        if "science" not in ctx.read_text_cached(pyproject_path):
            yield _result(
                Severity.WARN,
                "pyproject.toml",
                'pyproject.toml does not reference science (fix: `uv add --dev --editable "$SCIENCE_TOOL_PATH"`)',
            )
        else:
            yield _result(Severity.INFO, "pyproject.toml", "  science reference present")

    env_path = ctx.project_root / ".env"
    if not env_path.is_file():
        yield _result(
            Severity.WARN,
            ".env",
            ".env missing — SCIENCE_TOOL_PATH is unset (fix: create .env with `SCIENCE_TOOL_PATH=<absolute-path-to-science>`)",
        )
        return

    try:
        env_lines = ctx.read_text_cached(env_path).splitlines()
    except OSError as exc:
        yield _result(
            Severity.INFO,
            ".env",
            f".env exists but could not be inspected; skipping secret file contents: {exc}",
        )
        return

    if not any(line.startswith("SCIENCE_TOOL_PATH=") for line in env_lines):
        yield _result(
            Severity.WARN,
            ".env",
            ".env exists but does not define SCIENCE_TOOL_PATH (fix: add `SCIENCE_TOOL_PATH=<absolute-path>` to .env)",
        )
    else:
        yield _result(Severity.INFO, ".env", ".env defines SCIENCE_TOOL_PATH")
