from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from science_tool.validate import Check, Result, Severity, ValidateContext, hook
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import _HOOKS, clear_hooks_for_tests, run


@pytest.fixture(autouse=True)
def clean_registries() -> Generator[None]:
    clear_checks_for_tests()
    clear_hooks_for_tests()
    yield
    clear_hooks_for_tests()
    clear_checks_for_tests()


def _project(root: Path) -> Path:
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    return root


def test_hook_decorator_registers_and_dispatches_in_order(tmp_path: Path) -> None:
    fired: list[str] = []

    @hook("extra_checks")
    def first(ctx: ValidateContext) -> list[Result]:
        fired.append("first")
        return []

    hook("extra_checks")(first)

    @hook("extra_checks")
    def second(ctx: ValidateContext) -> list[Result]:
        fired.append("second")
        return []

    assert _HOOKS["extra_checks"] == [first, second]

    result = run(_project(tmp_path), strict=False, verbose=False)

    assert fired == ["first", "second"]
    assert result.results == []


def test_run_pipeline_dispatches_hooks_checks_and_tallies(tmp_path: Path) -> None:
    fired: list[str] = []

    @hook("pre_validation")
    def pre(ctx: ValidateContext) -> list[Result]:
        fired.append("pre")
        return [Result(Severity.INFO, None, None, "pre", "pre", None)]

    @Check(section="canonical", order=10)
    def canonical(ctx: ValidateContext) -> list[Result]:
        fired.append("check")
        return [
            Result(Severity.ERROR, Path("science.yaml"), 1, "bad", "canonical", None),
            Result(Severity.WARN, None, None, "warn", None, None),
            Result(Severity.INFO, None, None, "info", None, None),
        ]

    @hook("extra_checks")
    def extra(ctx: ValidateContext) -> list[Result]:
        fired.append("extra")
        return [Result(Severity.WARN, None, None, "extra", "extra", None)]

    @hook("post_validation")
    def post(ctx: ValidateContext, result: object | None = None) -> list[Result]:
        fired.append("post")
        return []

    result = run(_project(tmp_path), strict=True, verbose=True)

    assert fired == ["pre", "check", "extra", "post"]
    assert result.errors == 1
    assert result.warnings == 2
    assert result.infos == 2
    assert [item.message for item in result.results] == ["pre", "bad", "warn", "info", "extra"]


def test_post_validation_runs_when_extra_checks_raises(tmp_path: Path) -> None:
    fired: list[str] = []

    @hook("extra_checks")
    def extra(ctx: ValidateContext) -> list[Result]:
        fired.append("extra")
        raise RuntimeError("boom")

    @hook("post_validation")
    def post(ctx: ValidateContext, result: object | None = None) -> list[Result]:
        fired.append("post")
        return []

    with pytest.raises(RuntimeError, match="boom"):
        run(_project(tmp_path), strict=False, verbose=False)

    assert fired == ["extra", "post"]


def test_python_sidecar_mode_fails_until_discovery_is_implemented(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match="Python sidecar discovery is not implemented until Task 8"):
        run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=True)


def test_post_validation_runs_when_canonical_check_raises(tmp_path: Path) -> None:
    fired: list[str] = []

    @Check(section="canonical", order=10)
    def canonical(ctx: ValidateContext) -> list[Result]:
        fired.append("check")
        raise RuntimeError("canonical boom")

    @hook("post_validation")
    def post(ctx: ValidateContext) -> list[Result]:
        fired.append("post")
        return []

    with pytest.raises(RuntimeError, match="canonical boom"):
        run(_project(tmp_path), strict=False, verbose=False)

    assert fired == ["check", "post"]
