from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Literal, cast

from science_tool.validate.checks import CANONICAL_CHECKS, CheckEntry
from science_tool.validate.context import ValidateContext, ValidateContextError
from science_tool.validate.gates import gated_findings, resolve_gate_tier
from science_tool.validate.result import Result, Severity

if TYPE_CHECKING:
    HookName = Literal["pre_validation", "extra_checks", "post_validation"]
    ValidationProfile = Literal["full", "commit"]
else:
    HookName = str
    ValidationProfile = str


HookFn = Callable[[ValidateContext], Iterable[Result]]
_HOOK_NAMES = ("pre_validation", "extra_checks", "post_validation")
_HOOKS: dict[str, list[HookFn]] = {name: [] for name in _HOOK_NAMES}
_MISSING_MODULE = object()
_LEGACY_SIDECAR_REMOVED_RULE = "validate.sidecar.legacy_removed"
_LEGACY_SIDECAR_PORTING_GUIDE = "docs/migration/2026-05-19-validate-local-sh-porting-guide.md"
VALIDATE_PROFILES = ("full", "commit")
_COMMIT_EXCLUDED_SECTIONS = {"knowledge graph..."}
_COMMIT_EXCLUDED_FUNCTIONS = {"check_belief_authoring"}


@dataclass(frozen=True)
class RunResult:
    results: list[Result]
    errors: int
    warnings: int
    infos: int
    gate_tier: str = "report"
    gated: tuple[Result, ...] = ()
    sections: tuple[str, ...] = ()
    skipped_sections: tuple[str, ...] = ()
    profile: ValidationProfile = "full"


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
    fail_on: str | None = None,
    profile: ValidationProfile = "full",
    enable_python_sidecar: bool = True,
) -> RunResult:
    checks = _checks_for_profile(profile)
    skipped_checks = _skipped_checks_for_profile(profile)
    ctx = ValidateContext.from_project_root(project_root, strict=strict, verbose=verbose)
    results: list[Result] = []
    run_result: RunResult | None = None
    sidecar_enabled = enable_python_sidecar and os.environ.get("SCIENCE_VALIDATE_DISABLE_SIDECAR") != "1"
    python_sidecar_path = ctx.project_root / "validate_local.py"
    legacy_sidecar_path = ctx.project_root / "validate.local.sh"
    python_sidecar_exists = sidecar_enabled and python_sidecar_path.is_file()
    legacy_sidecar_exists = sidecar_enabled and legacy_sidecar_path.exists()
    should_cleanup_python_sidecar_hooks = sidecar_enabled
    python_sidecar_state: _PythonSidecarState | None = None
    python_sidecar_imported = False
    try:
        if sidecar_enabled:
            _clear_hooks()
        if sidecar_enabled and legacy_sidecar_exists:
            results.append(_legacy_sidecar_removed_result())
        if sidecar_enabled and python_sidecar_exists:
            python_sidecar_state = _install_python_sidecar(ctx)
            python_sidecar_imported = True
        if sidecar_enabled:
            results.extend(_dispatch_hooks("pre_validation", ctx))
        for entry in checks:
            try:
                results.extend(entry.fn(ctx))
            except Exception as exc:  # noqa: BLE001 - one check must not abort the whole run
                # A single check (e.g. one that loads project sources and hits a
                # malformed entity) must not abort the entire validate run. Surface
                # the failure as an ERROR finding and continue with the other checks.
                results.append(
                    Result(
                        Severity.ERROR,
                        None,
                        None,
                        f"check {entry.fn.__name__!r} (section {entry.section!r}) could not run: "
                        f"{type(exc).__name__}: {exc}",
                        "validate.check-error",
                        None,
                    )
                )
        if sidecar_enabled:
            results.extend(_dispatch_hooks("extra_checks", ctx))
        run_result = _tally(results, checks, skipped_checks, profile)
        try:
            tier = resolve_gate_tier(fail_on, ctx.manifest)
        except ValueError as exc:
            raise ValidateContextError(str(exc)) from exc
        run_result = replace(run_result, gate_tier=tier, gated=tuple(gated_findings(results, tier)))
        return run_result
    finally:
        try:
            if python_sidecar_imported:
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


def _checks_for_profile(profile: ValidationProfile) -> list[CheckEntry]:
    if profile == "full":
        return list(CANONICAL_CHECKS)
    if profile == "commit":
        return [entry for entry in CANONICAL_CHECKS if not _commit_profile_excludes(entry)]
    raise ValueError(f"unknown validation profile: {profile}")


def _skipped_checks_for_profile(profile: ValidationProfile) -> list[CheckEntry]:
    if profile == "full":
        return []
    if profile == "commit":
        return [entry for entry in CANONICAL_CHECKS if _commit_profile_excludes(entry)]
    raise ValueError(f"unknown validation profile: {profile}")


def _commit_profile_excludes(entry: CheckEntry) -> bool:
    return entry.section in _COMMIT_EXCLUDED_SECTIONS or entry.fn.__name__ in _COMMIT_EXCLUDED_FUNCTIONS


def _tally(
    results: list[Result],
    checks: list[CheckEntry],
    skipped_checks: list[CheckEntry],
    profile: ValidationProfile,
) -> RunResult:
    return RunResult(
        results=results,
        errors=sum(1 for result in results if result.severity is Severity.ERROR),
        warnings=sum(1 for result in results if result.severity is Severity.WARN),
        infos=sum(1 for result in results if result.severity is Severity.INFO),
        sections=tuple(dict.fromkeys(entry.section for entry in checks)),
        skipped_sections=tuple(dict.fromkeys(entry.section for entry in skipped_checks)),
        profile=profile,
    )


def _legacy_sidecar_removed_result() -> Result:
    message = f"validate.local.sh is no longer supported; migrate it using {_LEGACY_SIDECAR_PORTING_GUIDE}"
    return Result(Severity.ERROR, None, None, message, _LEGACY_SIDECAR_REMOVED_RULE, None)


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
