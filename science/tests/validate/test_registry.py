from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from science_model.audit import FindingRule, FindingSection

from science_tool.validate import Check, Result, Severity, ValidateContext
from science_tool.validate.checks import (
    CANONICAL_CHECKS,
    CANONICAL_CHECK_MODULES,
    clear_checks_for_tests,
)
from science_tool.validate.findings import ValidationQualifiers
from science_tool.validate.observations import ValidationObservationBatch


_SECTION = FindingSection(id="registry-test", title="Registry test", section_order=1)
_RULE = FindingRule(
    id="registry-test.problem",
    severities={"warn"},
    subject_types={"project"},
    qualifier_schema=ValidationQualifiers,
    identity_qualifiers=("key",),
    title="Problem",
    section=_SECTION.id,
    display_order=1,
)


@pytest.fixture(autouse=True)
def _restore_canonical_checks() -> None:
    yield
    clear_checks_for_tests()
    for module_name in CANONICAL_CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))


def test_check_registers_the_exact_producer_projection() -> None:
    clear_checks_for_tests()

    @Check(
        section=_SECTION,
        order=10,
        producer_id="validate.registry-test",
        rules=(_RULE,),
    )
    def registered(ctx: ValidateContext) -> list[Result]:
        return [
            Result(
                Severity.WARN,
                None,
                None,
                "problem",
                _RULE,
                None,
                {"key": []},
            )
        ]

    entry = CANONICAL_CHECKS[0]
    assert registered.__name__ == "registered"
    assert entry.producer.producer_id == "validate.registry-test"
    assert entry.producer.source_module == "test_registry.py"
    assert entry.producer.rules == (_RULE,)
    batch = ValidationObservationBatch.from_observations(
        item.to_finding(Path.cwd())
        for item in entry.fn(None)  # type: ignore[arg-type]
    )
    assert entry.produce(batch) == batch.producer_result()
    clear_checks_for_tests()


def test_check_decorator_registers_callables_in_order() -> None:
    clear_checks_for_tests()

    second_section = FindingSection(id="second", title="second", section_order=2)
    first_section = FindingSection(id="first", title="first", section_order=1)

    @Check(
        section=second_section,
        order=20,
        producer_id="validate.second",
        rules=(),
    )
    def second(ctx: ValidateContext) -> list[Result]:
        return []

    @Check(
        section=first_section,
        order=10,
        producer_id="validate.first",
        rules=(),
    )
    def first(ctx: ValidateContext) -> list[Result]:
        return []

    assert first.__name__ == "first"
    assert [entry.section for entry in CANONICAL_CHECKS] == ["first", "second"]
    assert [entry.producer.producer_id for entry in CANONICAL_CHECKS] == [
        "validate.first",
        "validate.second",
    ]

    clear_checks_for_tests()
