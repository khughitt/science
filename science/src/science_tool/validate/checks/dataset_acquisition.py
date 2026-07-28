"""Dataset acquisition check: an acquired dataset must carry a data pointer.

Acquisition lifecycle lives on `status` (candidate = not yet acquired); the data
pointer is `datapackage` OR `local_path` (the single-file escape hatch). Reads raw
frontmatter like dataset_taxonomy, re-enforcing the rule with a friendly message.
See docs/user-guide/entities.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


SECTION, RULES = declare_validation_rules(
    section_id="dataset-acquisition",
    section_title="dataset acquisition",
    section_order=130,
    rule_ids=("dataset.acquired-without-pointer",),
    severities=frozenset({"error", "warn", "info"}),
)


def evaluate_dataset_acquisition(datasets: Iterable[dict[str, Any]]) -> Iterator[CheckObservation]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`)."""
    for fm in datasets:
        if fm.get("kind") != "dataset":
            continue
        if fm.get("status") == "candidate":
            continue  # not-yet-acquired: pointer optional
        if fm.get("datapackage") or fm.get("local_path"):
            continue  # acquired and pointed
        ident = fm.get("id", "?")
        path = fm.get("_path")
        yield validation_observation(
            severity=Severity.ERROR,
            path=Path(path) if path else None,
            line=None,
            message=f"{ident}: acquired dataset (status={fm.get('status')!r}) has no datapackage or local_path; set status: candidate if not yet acquired, or add a datapackage/local_path pointer",
            rule=RULES["dataset.acquired-without-pointer"],
            task=None,
            qualifiers={"key": []},
        )


@Check(section=SECTION, order=32, producer_id="validate.dataset-acquisition", rules=tuple(RULES.values()))
def check_dataset_acquisition(ctx: ValidateContext) -> Iterator[CheckObservation]:
    yield from evaluate_dataset_acquisition(dataset_frontmatters(ctx))
