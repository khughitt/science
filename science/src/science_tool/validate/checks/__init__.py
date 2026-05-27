from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from science_tool.validate.result import Result

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


CheckFn = Callable[["ValidateContext"], Iterable[Result]]


@dataclass(frozen=True)
class CheckEntry:
    section: str
    order: int
    fn: CheckFn


CANONICAL_CHECKS: list[CheckEntry] = []


class Check:
    def __init__(self, section: str, order: int) -> None:
        self.section = section
        self.order = order

    def __call__(self, fn: CheckFn) -> CheckFn:
        CANONICAL_CHECKS.append(CheckEntry(section=self.section, order=self.order, fn=fn))
        CANONICAL_CHECKS.sort(key=lambda entry: entry.order)
        return fn


def clear_checks_for_tests() -> None:
    CANONICAL_CHECKS.clear()


def _load_canonical_checks() -> None:
    for module_name in (
        "tooling",
        "manifest",
        "directory_structure",
        "code_files",
        "research_scope",
        "document_structure",
        "hypotheses",
        "references",
        "papers",
        "unresolved_markers",
        "gap_analysis",
        "research_plan",
        "discussions",
        "prereg",
        "hypothesis_comparisons",
        "bias_audits",
        "notes",
        "graph",
        "tasks",
        "id_prefixes",
        "cross_references",
        "reference_collections",
        "identity_context",
        "dataset_taxonomy",
        "prose_lints",
        "annotations",
        "evidence_lines",
    ):
        importlib.import_module(f"{__name__}.{module_name}")


_load_canonical_checks()
