from __future__ import annotations

from collections.abc import Generator
import importlib
from pathlib import Path
import sys
from types import ModuleType

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

    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

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

    result = run(_project(tmp_path), strict=True, verbose=True, enable_python_sidecar=False)

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
        run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

    assert fired == ["extra", "post"]


def test_python_sidecar_imports_project_validate_local_when_enabled(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("helper.py").write_text('MESSAGE = "sidecar warning"\n', encoding="utf-8")
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from helper import MESSAGE",
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, MESSAGE, "local.extra", None)]',
                "",
                '@hook("post_validation")',
                "def post(ctx):",
                '    ctx.project_root.joinpath("post-ran.txt").write_text("yes", encoding="utf-8")',
                "    return []",
            ]
        ),
        encoding="utf-8",
    )
    sys_path_before = list(sys.path)

    disabled_result = run(project, strict=False, verbose=False, enable_python_sidecar=False)
    enabled_result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in disabled_result.results] == []
    assert [item.message for item in enabled_result.results] == ["sidecar warning"]
    assert enabled_result.warnings == 1
    assert project.joinpath("post-ran.txt").read_text(encoding="utf-8") == "yes"
    assert sys.path == sys_path_before
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_imports_project_validate_local_by_default(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "default sidecar warning", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False)

    assert [item.message for item in result.results] == ["default sidecar warning"]
    assert result.warnings == 1
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_clears_hooks_when_post_validation_raises(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import hook",
                "",
                '@hook("post_validation")',
                "def post(ctx):",
                '    raise RuntimeError("sidecar post boom")',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="sidecar post boom"):
        run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_import_failure_does_not_run_partial_post_hooks(tmp_path: Path) -> None:
    project = _project(tmp_path)
    post_marker = project / "post-ran.txt"
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import hook",
                "",
                '@hook("post_validation")',
                "def post(ctx):",
                '    ctx.project_root.joinpath("post-ran.txt").write_text("yes", encoding="utf-8")',
                '    raise RuntimeError("post boom")',
                "",
                'raise RuntimeError("import boom")',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="import boom"):
        run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert all(not hooks for hooks in _HOOKS.values())
    assert not post_marker.exists()


def test_python_sidecar_mode_clears_existing_hooks_before_import(tmp_path: Path) -> None:
    project = _project(tmp_path)

    @hook("extra_checks")
    def existing(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, None, None, "existing hook", "existing", None)]

    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "sidecar hook", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == ["sidecar hook"]
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_can_import_itself_without_double_execution(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                'counter_path = Path(__file__).with_name("sidecar-counter.txt")',
                'count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0',
                'counter_path.write_text(str(count + 1), encoding="utf-8")',
                "",
                "import validate_local",
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "sidecar hook", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert project.joinpath("sidecar-counter.txt").read_text(encoding="utf-8") == "1"
    assert [item.message for item in result.results] == ["sidecar hook"]
    assert "validate_local" not in sys.modules
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_hook_can_lazily_import_validate_local_once(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                'counter_path = Path(__file__).with_name("sidecar-counter.txt")',
                'count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0',
                'counter_path.write_text(str(count + 1), encoding="utf-8")',
                'MESSAGE = "lazy sidecar import"',
                "",
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                "    import validate_local",
                "    return [Result(Severity.WARN, None, None, validate_local.MESSAGE, 'local.extra', None)]",
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert project.joinpath("sidecar-counter.txt").read_text(encoding="utf-8") == "1"
    assert [item.message for item in result.results] == ["lazy sidecar import"]
    assert "validate_local" not in sys.modules
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_hook_can_lazily_import_project_local_helper(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("helper.py").write_text('MESSAGE = "lazy helper import"\n', encoding="utf-8")
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                "    from helper import MESSAGE",
                "    return [Result(Severity.WARN, None, None, MESSAGE, 'local.extra', None)]",
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == ["lazy helper import"]
    assert "helper" not in sys.modules
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_removes_project_namespace_package_imported_by_lazy_hook(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    project.joinpath("localpkg").mkdir()
    project.joinpath("localpkg", "helper.py").write_text(
        'MESSAGE = "lazy namespace helper import"\n',
        encoding="utf-8",
    )
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                "    from localpkg.helper import MESSAGE",
                "    return [Result(Severity.WARN, None, None, MESSAGE, 'local.extra', None)]",
            ]
        ),
        encoding="utf-8",
    )
    module_names = ("localpkg", "localpkg.helper")
    missing_module = object()
    original_modules = {module_name: sys.modules.get(module_name, missing_module) for module_name in module_names}

    try:
        result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

        assert [item.message for item in result.results] == ["lazy namespace helper import"]
        assert "localpkg" not in sys.modules
        assert "localpkg.helper" not in sys.modules
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("localpkg.helper")
        assert all(not hooks for hooks in _HOOKS.values())
    finally:
        for module_name, original_module in original_modules.items():
            if original_module is missing_module:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original_module  # type: ignore[assignment]


def test_python_sidecar_keeps_preexisting_unrelated_namespace_package(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _project(project)
    outside_namespace_path = tmp_path / "outside" / "outsidepkg"
    outside_namespace_path.mkdir(parents=True)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "sidecar hook", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )
    missing_module = object()
    original_module: object = sys.modules.get("outsidepkg", missing_module)
    outside_module = ModuleType("outsidepkg")
    outside_module.__path__ = [str(outside_namespace_path)]  # type: ignore[attr-defined]
    sys.modules["outsidepkg"] = outside_module

    try:
        result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

        assert [item.message for item in result.results] == ["sidecar hook"]
        assert sys.modules["outsidepkg"] is outside_module
        assert all(not hooks for hooks in _HOOKS.values())
    finally:
        if original_module is missing_module:
            sys.modules.pop("outsidepkg", None)
        else:
            sys.modules["outsidepkg"] = original_module  # type: ignore[assignment]


def test_python_sidecar_restores_existing_sys_path_and_validate_local_module(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("post_validation")',
                "def post(ctx):",
                "    import validate_local",
                "    ctx.project_root.joinpath('post-message.txt').write_text(",
                "        validate_local.MESSAGE, encoding='utf-8'",
                "    )",
                "    return []",
                "",
                'MESSAGE = "sidecar post import"',
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                "    return [Result(Severity.WARN, None, None, MESSAGE, 'local.extra', None)]",
            ]
        ),
        encoding="utf-8",
    )
    previous_module = ModuleType("validate_local")
    previous_module.MESSAGE = "preexisting"  # type: ignore[attr-defined]
    missing_module = object()
    original_module: object = sys.modules.get("validate_local", missing_module)
    original_sys_path = list(sys.path)
    sys.modules["validate_local"] = previous_module
    try:
        result = run(project, strict=False, verbose=False, enable_python_sidecar=True)
        assert [item.message for item in result.results] == ["sidecar post import"]
        assert project.joinpath("post-message.txt").read_text(encoding="utf-8") == "sidecar post import"
        assert sys.path == original_sys_path
        assert str(project) not in sys.path
        assert sys.modules["validate_local"] is previous_module
        assert all(not hooks for hooks in _HOOKS.values())
    finally:
        if original_module is missing_module:
            sys.modules.pop("validate_local", None)
        else:
            sys.modules["validate_local"] = original_module  # type: ignore[assignment]
        sys.path[:] = original_sys_path


def test_python_sidecar_mode_without_validate_local_does_not_error(tmp_path: Path) -> None:
    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=True)

    assert result.results == []
    assert all(not hooks for hooks in _HOOKS.values())


def test_python_sidecar_mode_without_validate_local_clears_existing_hooks(tmp_path: Path) -> None:
    fired: list[str] = []

    @hook("extra_checks")
    def existing(ctx: ValidateContext) -> list[Result]:
        fired.append("existing")
        return [Result(Severity.WARN, None, None, "existing hook", "existing", None)]

    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=True)

    assert fired == []
    assert result.results == []
    assert all(not hooks for hooks in _HOOKS.values())


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
        run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

    assert fired == ["check", "post"]
