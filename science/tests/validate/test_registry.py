from __future__ import annotations

from science_tool.validate import Check, Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def test_check_decorator_registers_callables_in_order() -> None:
    clear_checks_for_tests()

    @Check(section="second", order=20)
    def second(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "second", "second", None)]

    @Check(section="first", order=10)
    def first(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "first", "first", None)]

    assert first.__name__ == "first"
    assert [entry.section for entry in CANONICAL_CHECKS] == ["first", "second"]
    assert [entry.fn(None)[0].message for entry in CANONICAL_CHECKS] == ["first", "second"]  # type: ignore[arg-type]

    clear_checks_for_tests()
