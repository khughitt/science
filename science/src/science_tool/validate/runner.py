from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Literal, cast

from science_tool.validate._legacy.runner import run_legacy_sidecar
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
_MISSING_MODULE = object()
_LEGACY_SIDECAR_DEPRECATION_RULE = "validate.sidecar.legacy_deprecated"


@dataclass(frozen=True)
class RunResult:
    results: list[Result]
    errors: int
    warnings: int
    infos: int


@dataclass(frozen=True)
class _PythonSidecarState:
    original_sys_path: list[str]
    original_sys_modules: set[str]
    previous_module: object
    project_root: Path

    def restore(self) -> None:
        sys.path[:] = self.original_sys_path
        for module_name, module in list(sys.modules.items()):
            if module_name not in self.original_sys_modules and _module_is_from_project(
                module,
                self.project_root,
            ):
                sys.modules.pop(module_name, None)
        if self.previous_module is _MISSING_MODULE:
            sys.modules.pop("validate_local", None)
        else:
            sys.modules["validate_local"] = cast(ModuleType, self.previous_module)


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
    enable_python_sidecar: bool = True,
) -> RunResult:
    ctx = ValidateContext.from_project_root(project_root, strict=strict, verbose=verbose)
    results: list[Result] = []
    run_result: RunResult | None = None
    sidecar_enabled = enable_python_sidecar and os.environ.get("SCIENCE_VALIDATE_DISABLE_SIDECAR") != "1"
    python_sidecar_path = ctx.project_root / "validate_local.py"
    legacy_sidecar_path = ctx.project_root / "validate.local.sh"
    python_sidecar_exists = python_sidecar_path.is_file()
    legacy_sidecar_exists = legacy_sidecar_path.is_file()
    legacy_sidecar_selected = sidecar_enabled and legacy_sidecar_exists and not python_sidecar_exists
    should_cleanup_python_sidecar_hooks = sidecar_enabled
    python_sidecar_state: _PythonSidecarState | None = None
    python_sidecar_imported = False
    try:
        if sidecar_enabled:
            _clear_hooks()
        if sidecar_enabled and legacy_sidecar_exists:
            results.append(_legacy_sidecar_deprecation_result(python_sidecar_exists))
        if sidecar_enabled and python_sidecar_exists:
            python_sidecar_state = _install_python_sidecar(ctx)
            python_sidecar_imported = True
        if legacy_sidecar_selected:
            # Legacy bash sidecars run once per phase in separate subprocesses.
            # Their failures become Results so Python canonical checks continue.
            legacy_results, _log_lines = run_legacy_sidecar(
                ctx.project_root,
                phase="pre_validation",
                count_post_validation=False,
            )
            results.extend(legacy_results)
        results.extend(_dispatch_hooks("pre_validation", ctx))
        for entry in CANONICAL_CHECKS:
            results.extend(entry.fn(ctx))
        results.extend(_dispatch_hooks("extra_checks", ctx))
        if legacy_sidecar_selected:
            legacy_results, _log_lines = run_legacy_sidecar(
                ctx.project_root,
                phase="extra_checks",
            )
            results.extend(legacy_results)
        run_result = _tally(results)
        return run_result
    finally:
        try:
            if not sidecar_enabled or python_sidecar_imported:
                _dispatch_hooks("post_validation", ctx)
        finally:
            if python_sidecar_state is not None:
                python_sidecar_state.restore()
            if should_cleanup_python_sidecar_hooks:
                _clear_hooks()


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


def _legacy_sidecar_deprecation_result(python_sidecar_exists: bool) -> Result:
    if python_sidecar_exists:
        message = "validate.local.sh is deprecated and ignored because validate_local.py takes precedence"
    else:
        message = "validate.local.sh is deprecated; migrate validation hooks to validate_local.py"
    return Result(Severity.WARN, None, None, message, _LEGACY_SIDECAR_DEPRECATION_RULE, None)


def _install_python_sidecar(ctx: ValidateContext) -> _PythonSidecarState:
    sidecar_path = ctx.project_root / "validate_local.py"
    module_name = "validate_local"
    spec = importlib.util.spec_from_file_location(module_name, sidecar_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not import validation sidecar: {sidecar_path}")

    module = importlib.util.module_from_spec(spec)
    state = _PythonSidecarState(
        original_sys_path=list(sys.path),
        original_sys_modules=set(sys.modules),
        previous_module=sys.modules.get(module_name, _MISSING_MODULE),
        project_root=ctx.project_root,
    )
    try:
        sys.path.insert(0, str(sidecar_path.parent))
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except BaseException:
        state.restore()
        raise
    return state


def _module_is_from_project(module: ModuleType, project_root: Path) -> bool:
    resolved_project_root = project_root.resolve()
    module_file = getattr(module, "__file__", None)
    if module_file is not None and _path_is_from_project(module_file, resolved_project_root):
        return True

    module_path = getattr(module, "__path__", None)
    if not isinstance(module_path, Iterable):
        return False
    return any(
        _path_is_from_project(path_entry, resolved_project_root)
        for path_entry in module_path
        if isinstance(path_entry, str | os.PathLike)
    )


def _path_is_from_project(path: str | os.PathLike[str], resolved_project_root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(resolved_project_root)
    except (OSError, ValueError):
        return False
    return True


def _clear_hooks() -> None:
    for hooks in _HOOKS.values():
        hooks.clear()


def clear_hooks_for_tests() -> None:
    _clear_hooks()
