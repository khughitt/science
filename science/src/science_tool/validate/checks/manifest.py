"""Port of validate.sh "Checking project manifest..." block, lines 246-306."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_REQUIRED_FIELDS = ("name", "created", "last_modified", "status", "summary", "profile", "layout_version")


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, Path("science.yaml"), None, message, "manifest", None)


@Check(section="project manifest...", order=1)
def check_manifest(ctx: ValidateContext) -> Iterator[Result]:
    yield _result(Severity.INFO, "science.yaml exists")

    for field in _REQUIRED_FIELDS:
        if field not in ctx.manifest:
            yield _result(Severity.ERROR, f"science.yaml missing required field: {field}")
        else:
            yield _result(Severity.INFO, f"  {field}: present")

    layout_version = ctx.manifest.get("layout_version")
    if isinstance(layout_version, int) and layout_version < 3:
        yield _result(
            Severity.ERROR,
            "science.yaml: layout_version must be 3",
        )

    profiles = ctx.manifest.get("knowledge_profiles")
    if not isinstance(profiles, dict):
        yield _result(Severity.ERROR, "science.yaml missing required knowledge_profiles section")
        return

    local_profile = profiles.get("local")
    if not isinstance(local_profile, str) or local_profile == "":
        yield _result(Severity.ERROR, "science.yaml knowledge_profiles.local missing or empty")
        return

    curated: Any = profiles.get("curated")
    if curated is not None and not isinstance(curated, list):
        yield _result(Severity.ERROR, "science.yaml knowledge_profiles.curated must be a list")
        return

    ontologies: Any = ctx.manifest.get("ontologies")
    if ontologies is not None and not isinstance(ontologies, list):
        yield _result(Severity.ERROR, "science.yaml ontologies must be a list")
        return

    yield _result(Severity.INFO, "knowledge_profiles configured")
