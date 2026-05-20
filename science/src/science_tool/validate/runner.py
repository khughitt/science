from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from science_tool.validate.checks import CANONICAL_CHECKS
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

if TYPE_CHECKING:
    HookName = Literal["pre_validation", "extra_checks", "post_validation"]
else:
    HookName = str


HookFn = Callable[[ValidateContext], Iterable[Result]]
_HOOK_NAMES = ("pre_validation", "extra_checks", "post_validation")
_HOOKS: dict[str, list[HookFn]] = {name: [] for name in _HOOK_NAMES}


@dataclass(frozen=True)
class RunResult:
    results: list[Result]
    errors: int
    warnings: int
    infos: int


def hook(name: HookName) -> Callable[[HookFn], HookFn]:
    if name not in _HOOKS:
        raise ValueError(f"unknown validation hook: {name}")

    def register(fn: HookFn) -> HookFn:
        hooks = _HOOKS[name]
        if fn not in hooks:
            hooks.append(fn)
        return fn

    return register


def run(
    project_root: Path,
    *,
    strict: bool,
    verbose: bool,
    enable_python_sidecar: bool = False,
) -> RunResult:
    ctx = ValidateContext.from_project_root(project_root, strict=strict, verbose=verbose)
    results: list[Result] = []
    run_result: RunResult | None = None
    try:
        if enable_python_sidecar and os.environ.get("SCIENCE_VALIDATE_DISABLE_SIDECAR") != "1":
            _import_python_sidecars(ctx)
        results.extend(_dispatch_hooks("pre_validation", ctx))
        for entry in CANONICAL_CHECKS:
            results.extend(entry.fn(ctx))
        results.extend(_dispatch_hooks("extra_checks", ctx))
        run_result = _tally(results)
        return run_result
    finally:
        _dispatch_hooks("post_validation", ctx)


def _dispatch_hooks(name: str, ctx: ValidateContext) -> list[Result]:
    results: list[Result] = []
    for fn in _HOOKS[name]:
        results.extend(fn(ctx))
    return results


def _tally(results: list[Result]) -> RunResult:
    return RunResult(
        results=results,
        errors=sum(1 for result in results if result.severity is Severity.ERROR),
        warnings=sum(1 for result in results if result.severity is Severity.WARN),
        infos=sum(1 for result in results if result.severity is Severity.INFO),
    )


def _import_python_sidecars(ctx: ValidateContext) -> None:
    raise NotImplementedError("Python sidecar discovery is not implemented until Task 8")


def clear_hooks_for_tests() -> None:
    for hooks in _HOOKS.values():
        hooks.clear()
