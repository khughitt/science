"""Tooling-scaffold health check: pyproject and environment scaffold for science tooling."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.graph.health_checks.base import HealthCheck
from science_tool.instruments import InstrumentResult


class ToolingScaffoldFinding(TypedDict):
    code: str  # pyproject_missing | science_tool_dep_missing | env_missing | env_path_missing
    detail: str  # human-readable description
    fix: str  # suggested remediation command


def collect_tooling_scaffold_findings(project_root: Path) -> InstrumentResult[ToolingScaffoldFinding]:
    """Check the project has the canonical science invocation scaffold.

    A compliant project has:
      - root `pyproject.toml` (so `uv run` resolves a project context)
      - `science` listed under `[dependency-groups].dev`
      - `.env` containing `SCIENCE_TOOL_PATH=...`

    Without these, the documented `uv run science <cmd>` shorthand cannot
    work; users fall back to verbose `uv run --project ...` or `uv run --with ...`
    forms. See `commands/create-project.md` (pyproject.toml section).

    This check has NO unwired state. The ABSENCE of those files IS its finding — a
    bare directory yields two findings, not silence — so an empty return is
    unambiguous: the scaffold is present and compliant.
    """
    findings: list[ToolingScaffoldFinding] = []

    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        findings.append(
            {
                "code": "pyproject_missing",
                "detail": "No root pyproject.toml — `uv run science ...` cannot resolve.",
                "fix": 'Create pyproject.toml per commands/create-project.md, then `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.',
            }
        )
    else:
        has_dep = False
        try:
            text = pyproject_path.read_text(encoding="utf-8")
            try:
                import tomllib  # py3.11+
            except ModuleNotFoundError:  # pragma: no cover
                import tomli as tomllib  # type: ignore[import-not-found]
            data = tomllib.loads(text)
            dev_group = data.get("dependency-groups", {}).get("dev", [])
            for entry in dev_group:
                # entries can be strings ("science") or tables; we only need name match
                if isinstance(entry, str) and entry.split("[")[0].split(">=")[0].split("==")[0].strip() == "science":
                    has_dep = True
                    break
        except Exception as exc:
            findings.append(
                {
                    "code": "pyproject_unreadable",
                    "detail": f"pyproject.toml could not be parsed: {exc}",
                    "fix": "Repair pyproject.toml — see commands/create-project.md for canonical shape.",
                }
            )
            has_dep = True  # don't double-report; parsing already failed

        if not has_dep:
            findings.append(
                {
                    "code": "science_tool_dep_missing",
                    "detail": "pyproject.toml does not list `science` under [dependency-groups].dev.",
                    "fix": 'Run `uv add --dev --editable "$SCIENCE_TOOL_PATH"` from the project root.',
                }
            )

    env_path = project_root / ".env"
    if not env_path.exists():
        findings.append(
            {
                "code": "env_missing",
                "detail": "No .env file — SCIENCE_TOOL_PATH is unset for validate.sh and other tooling.",
                "fix": "Create .env with `SCIENCE_TOOL_PATH=<absolute-path-to-science>` (see create-project.md).",
            }
        )
    else:
        try:
            env_text = env_path.read_text(encoding="utf-8")
        except OSError:
            env_text = None
        if env_text is not None and not any(line.strip().startswith("SCIENCE_TOOL_PATH=") for line in env_text.splitlines()):
            findings.append(
                {
                    "code": "env_path_missing",
                    "detail": ".env exists but does not define SCIENCE_TOOL_PATH.",
                    "fix": "Add `SCIENCE_TOOL_PATH=<absolute-path-to-science>` to .env.",
                }
            )

    return InstrumentResult.from_rows(findings)


CHECK = HealthCheck(
    name="tooling_scaffold",
    description="Check pyproject and environment scaffold for science tooling.",
    requires_sources=False,
    run=lambda context: collect_tooling_scaffold_findings(context.project_root),
    empty=lambda _root: [],
)
