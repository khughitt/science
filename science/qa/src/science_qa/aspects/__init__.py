from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from science_qa.flags import Flag

CHECK_REQUIRED = "required"
CHECK_FAMILY = "family"

# Each check declares the Context subtype it consumes in `CheckSpec.accepts`, and
# the runner refuses to call it with anything else. A static annotation cannot tie
# `fn`'s first parameter to the sibling `accepts` field, so the context is Any here.
CheckFn = Callable[[Any, dict], list[Flag]]


@dataclass(frozen=True)
class Invocation:
    """One concrete instantiation of a check after config resolution."""
    params: dict = field(default_factory=dict)
    requires: tuple[str, ...] = ()        # input columns that must exist
    columns: list[str] | None = None      # explicit column selection; None -> use CheckSpec.selector
    optional: bool = False                # True -> absent required input is not-applicable, not an error


@dataclass(frozen=True)
class CheckSpec:
    aspect: str
    name: str
    kind: str                              # CHECK_REQUIRED | CHECK_FAMILY
    accepts: type                          # the Context subtype this check consumes
    fn: CheckFn
    selector: object | None = None         # selector spec for selector-driven required checks
    requires: tuple[str, ...] = ()         # required-check input columns (blocked if absent)
    expand: Callable[[object], list[Invocation]] | None = None  # families only

    @property
    def check_id(self) -> str:
        return f"{self.aspect}/{self.name}"
