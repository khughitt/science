"""Port of validate.sh "Checking project manifest..." block, lines 246-306."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.data_root import PROJECT_CONFIG_FILENAME
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_REQUIRED_FIELDS = ("name", "created", "last_modified", "status", "summary", "profile", "layout_version")


SECTION, RULES = declare_validation_rules(
    section_id="manifest",
    section_title="manifest",
    section_order=102,
    rule_ids=("manifest.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(severity: Severity, message: str, *, key: list[str]) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=Path(PROJECT_CONFIG_FILENAME),
        line=None,
        message=message,
        rule=RULES["manifest.check"],
        task=None,
        qualifiers={"key": key},
    )


@Check(section=SECTION, order=1, producer_id="validate.manifest", rules=tuple(RULES.values()))
def check_manifest(ctx: ValidateContext) -> Iterator[CheckObservation]:
    yield _result(Severity.INFO, "science.yaml exists", key=["exists"])

    for field in _REQUIRED_FIELDS:
        if field not in ctx.manifest:
            yield _result(
                Severity.ERROR,
                f"science.yaml missing required field: {field}",
                key=["required-field", field],
            )
        else:
            yield _result(Severity.INFO, f"  {field}: present", key=["field-present", field])

    layout_version = ctx.manifest.get("layout_version")
    if isinstance(layout_version, int) and layout_version < 3:
        yield _result(
            Severity.ERROR,
            "science.yaml: layout_version must be 3",
            key=["layout-version"],
        )

    profiles = ctx.manifest.get("knowledge_profiles")
    if not isinstance(profiles, dict):
        yield _result(
            Severity.ERROR,
            "science.yaml missing required knowledge_profiles section",
            key=["knowledge-profiles"],
        )
        return

    local_profile = profiles.get("local")
    if not isinstance(local_profile, str) or local_profile == "":
        yield _result(
            Severity.ERROR,
            "science.yaml knowledge_profiles.local missing or empty",
            key=["knowledge-profiles", "local"],
        )
        return

    curated: Any = profiles.get("curated")
    if curated is not None and not isinstance(curated, list):
        yield _result(
            Severity.ERROR,
            "science.yaml knowledge_profiles.curated must be a list",
            key=["knowledge-profiles", "curated"],
        )
        return

    ontologies: Any = ctx.manifest.get("ontologies")
    if ontologies is not None and not isinstance(ontologies, list):
        yield _result(
            Severity.ERROR,
            "science.yaml ontologies must be a list",
            key=["ontologies"],
        )
        return

    yield _result(
        Severity.INFO,
        "knowledge_profiles configured",
        key=["knowledge-profiles-configured"],
    )
