"""Port of validate.sh "Checking tooling scaffold..." block, lines 212-243."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.tooling_dependency import (
    CANONICAL_SCIENCE_SOURCE,
    ScienceSourceKind,
    inspect_science_dependency,
)
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


SECTION, RULES = declare_validation_rules(
    section_id="tooling",
    section_title="tooling",
    section_order=101,
    rule_ids=("tooling.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(severity: Severity, path: str | None, message: str) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=Path(path) if path is not None else None,
        line=None,
        message=message,
        rule=RULES["tooling.check"],
        task=None,
        qualifiers={"key": []},
    )


@Check(section=SECTION, order=0, producer_id="validate.tooling", rules=tuple(RULES.values()))
def check_tooling(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Validate static tooling scaffold files.

    The optional bash smoke test for `uv run science --help` is intentionally
    left for a later parity slice because this check must not spawn subprocesses.
    """

    pyproject_path = ctx.project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        yield _result(
            Severity.WARN,
            "pyproject.toml",
            "pyproject.toml missing — `uv run science ...` cannot resolve "
            f"(fix: see commands/create-project.md and configure `{CANONICAL_SCIENCE_SOURCE}`)",
        )
    else:
        yield _result(Severity.INFO, "pyproject.toml", "pyproject.toml present")
        try:
            dependency = inspect_science_dependency(ctx.project_root)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            yield _result(
                Severity.WARN,
                "pyproject.toml",
                f"pyproject.toml could not be parsed: {exc}",
            )
        else:
            if not dependency.dev_dependency_present:
                yield _result(
                    Severity.WARN,
                    "pyproject.toml",
                    "pyproject.toml does not list science under [dependency-groups].dev "
                    f"(fix: add the dependency and configure `{CANONICAL_SCIENCE_SOURCE}`)",
                )
            elif dependency.source_kind is ScienceSourceKind.MISSING:
                yield _result(
                    Severity.WARN,
                    "pyproject.toml",
                    f"science has no supported uv source (fix: `{CANONICAL_SCIENCE_SOURCE}`)",
                )
            elif dependency.source_kind is ScienceSourceKind.EXTERNAL_PATH:
                yield _result(
                    Severity.WARN,
                    "pyproject.toml",
                    "science uses an external path source that breaks in nested worktrees "
                    f"(fix: `{CANONICAL_SCIENCE_SOURCE}`)",
                )
            elif dependency.source_kind is ScienceSourceKind.GIT:
                yield _result(Severity.INFO, "pyproject.toml", "  science Git source is worktree-safe")
            else:
                yield _result(Severity.INFO, "pyproject.toml", "  science same-repository path source is worktree-safe")
