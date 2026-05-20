from __future__ import annotations

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
