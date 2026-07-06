from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest

from science_tool.validate import Check, Result, Severity, ValidateContext, hook
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import _HOOKS, RunResult, clear_hooks_for_tests, run


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


def test_hook_decorator_registers_without_disabled_sidecar_dispatch(tmp_path: Path) -> None:
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

    assert fired == []
    assert result.results == []


def test_disabled_sidecar_run_skips_registered_hooks(tmp_path: Path) -> None:
    fired: list[str] = []

    @hook("pre_validation")
    def pre(ctx: ValidateContext) -> list[Result]:
        fired.append("pre")
        return [Result(Severity.ERROR, None, None, "pre should not run", "pre", None)]

    @hook("extra_checks")
    def extra(ctx: ValidateContext) -> list[Result]:
        fired.append("extra")
        return [Result(Severity.ERROR, None, None, "extra should not run", "extra", None)]

    @hook("post_validation")
    def post(ctx: ValidateContext) -> list[Result]:
        fired.append("post")
        raise RuntimeError("post should not run")

    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

    assert fired == []
    assert result.results == []


def test_disabled_sidecar_run_dispatches_canonical_checks_and_tallies(tmp_path: Path) -> None:
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

    assert fired == ["check"]
    assert result.errors == 1
    assert result.warnings == 1
    assert result.infos == 1
    assert [item.message for item in result.results] == ["bad", "warn", "info"]


def test_disabled_sidecar_run_skips_extra_checks_that_would_raise(tmp_path: Path) -> None:
    fired: list[str] = []

    @hook("extra_checks")
    def extra(ctx: ValidateContext) -> list[Result]:
        fired.append("extra")
        raise RuntimeError("boom")

    @hook("post_validation")
    def post(ctx: ValidateContext, result: object | None = None) -> list[Result]:
        fired.append("post")
        return []

    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

    assert fired == []
    assert result.results == []


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


def test_disabled_sidecar_run_isolates_canonical_check_that_raises(tmp_path: Path) -> None:
    fired: list[str] = []

    @Check(section="canonical", order=10)
    def canonical(ctx: ValidateContext) -> list[Result]:
        fired.append("check")
        raise RuntimeError("canonical boom")

    @hook("post_validation")
    def post(ctx: ValidateContext) -> list[Result]:
        fired.append("post")
        return []

    # A raising canonical check is now isolated into an ERROR finding rather than
    # aborting the whole run, so run() returns normally.
    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

    assert fired == ["check"]
    crash = [r for r in result.results if r.rule == "validate.check-error"]
    assert len(crash) == 1
    assert "canonical" in crash[0].message
    assert crash[0].severity is Severity.ERROR


def test_run_isolates_a_crashing_canonical_check(tmp_path: Path) -> None:
    @Check(section="early", order=5)
    def boom(ctx: ValidateContext) -> list[Result]:
        raise ValueError("schema validation failed for dataset:x")

    @Check(section="late", order=99)
    def later(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "later ran", "later.ok", None)]

    result = run(_project(tmp_path), strict=False, verbose=False, enable_python_sidecar=False)

    # the crash did NOT abort the run: the later check still ran
    assert any(r.rule == "later.ok" for r in result.results)
    # the crash was reported as a single ERROR finding, not raised
    crash = [r for r in result.results if r.rule == "validate.check-error"]
    assert len(crash) == 1
    assert "boom" in crash[0].message
    assert crash[0].severity is Severity.ERROR


# ---------------------------------------------------------------------------
# End-to-end: a malformed member_of datapackage must not abort the whole run.
# ---------------------------------------------------------------------------

_MALFORMED_MEMBER_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)

# A member_of derivation that is MISSING its required member_key. The entity
# fields (id/type/title) stay valid so DatapackageAdapter.discover accepts the
# package; only the derivation is malformed.
_MALFORMED_MEMBER_DP = """\
profiles: [science-pkg-entity-1.0]
id: dataset:member-malformed
kind: dataset
title: Member Malformed
status: active
origin: derived
tier: use-now
parent_dataset: dataset:some-parent
derivation:
  kind: member_of
  parent_dataset: dataset:some-parent
"""

_DATASET_INFLUENCE_MANIFEST = "name: demo\nknowledge_profiles:\n  local: local\n"


def _build_malformed_member_project(tmp_path: Path) -> Path:
    tmp_path.joinpath("science.yaml").write_text(_MALFORMED_MEMBER_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    dp_dir = tmp_path / "data" / "member-malformed"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(_MALFORMED_MEMBER_DP, encoding="utf-8")
    return tmp_path


def _write_dataset_influence_project(
    root: Path, *, local_dataset: bool = False, usage_ref: str = "dataset:gtex-v8"
) -> Path:
    root.joinpath("science.yaml").write_text(_DATASET_INFLUENCE_MANIFEST, encoding="utf-8")
    (root / "entities" / "papers").mkdir(parents=True)
    (root / "entities" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\nkind: paper\ntitle: Adams\ndataset_usage:\n"
        f"  - ref: {usage_ref}\n    role: analyzed\n    overlap: full\n---\n",
        encoding="utf-8",
    )
    if local_dataset:
        dp_dir = root / "data" / "gtex"
        dp_dir.mkdir(parents=True)
        (dp_dir / "datapackage.yaml").write_text(
            "profiles: [science-pkg-entity-1.0]\nid: dataset:gtex-v8\nkind: dataset\ntitle: GTEx\n"
            "aliases: [dataset:gtex]\n"
            "origin: external\ntier: use-now\ndatapackage: datapackage.yaml\naccess: {level: public, verified: true}\n",
            encoding="utf-8",
        )
    return root


def _initialized_commons(root: Path) -> Path:
    commons = root / "commons"
    for dirname in (".git", "datasets", "papers", "topics", "themes"):
        (commons / dirname).mkdir(parents=True)
    return commons


def _dataset_influence_rules(result: RunResult) -> list[tuple[Severity, str]]:
    return [
        (item.severity, item.rule)
        for item in result.results
        if isinstance(item.rule, str) and item.rule.startswith("dataset-influence.")
    ]


def _register_real_canonical_checks() -> None:
    """Re-register the real canonical checks after the autouse fixture cleared them.

    ``_load_canonical_checks`` only ``import_module``s the check submodules, which
    is a no-op once they are already cached in ``sys.modules`` — so the ``@Check``
    decorators never re-run and ``CANONICAL_CHECKS`` stays empty. Force a reload of
    each already-imported submodule so the decorators fire again.
    """
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
        "project_readme",
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
        "variant_identity",
        "genesets",
        "reference_graphs",
        "dataset_influence",
        "prose_lints",
        "annotations",
        "evidence_lines",
    ):
        full = f"science_tool.validate.checks.{module_name}"
        module = sys.modules.get(full)
        if module is not None:
            importlib.reload(module)
        else:
            importlib.import_module(full)


def test_full_run_reports_malformed_member_without_crashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    _register_real_canonical_checks()  # register the real checks (autouse fixture cleared them)
    project = _build_malformed_member_project(tmp_path)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=False)  # must NOT raise

    # the malformed member is reported by reference_collections (it no longer crashes the run)
    assert any(r.rule == "reference-collection.malformed-member" for r in result.results)
    # and nothing propagated an exception — we got a RunResult with the error counted
    assert result.errors >= 1


def test_canonical_loader_registers_dataset_influence_after_genesets() -> None:
    import science_tool.validate.checks as checks

    clear_checks_for_tests()
    for module_name in ("genesets", "dataset_influence"):
        sys.modules.pop(f"science_tool.validate.checks.{module_name}", None)

    checks._load_canonical_checks()

    ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in checks.CANONICAL_CHECKS]
    genesets_index = next(index for index, entry in enumerate(ordered) if entry[0] == "gene-set collections")
    influence_index = next(index for index, entry in enumerate(ordered) if entry[0] == "dataset influence")
    assert influence_index > genesets_index


def test_canonical_loader_registers_reference_graphs_between_genesets_and_dataset_influence() -> None:
    import science_tool.validate.checks as checks

    clear_checks_for_tests()
    for module_name in ("genesets", "reference_graphs", "dataset_influence"):
        sys.modules.pop(f"science_tool.validate.checks.{module_name}", None)

    checks._load_canonical_checks()

    ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in checks.CANONICAL_CHECKS]
    genesets_index = next(index for index, entry in enumerate(ordered) if entry[0] == "gene-set collections")
    reference_graphs_index = next(
        index for index, entry in enumerate(ordered) if entry[0] == "reference graph collections"
    )
    influence_index = next(index for index, entry in enumerate(ordered) if entry[0] == "dataset influence")
    assert genesets_index < reference_graphs_index < influence_index
    assert ordered[genesets_index][1] == 34
    assert ordered[reference_graphs_index][1] == 35
    assert ordered[influence_index][1] == 36


def test_runner_dataset_influence_resolves_local_dataset_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _register_real_canonical_checks()
    project = _write_dataset_influence_project(tmp_path, local_dataset=True)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=False)

    assert _dataset_influence_rules(result) == []


def test_runner_dataset_influence_resolves_local_dataset_alias_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _register_real_canonical_checks()
    project = _write_dataset_influence_project(tmp_path, local_dataset=True, usage_ref="dataset:gtex")

    result = run(project, strict=False, verbose=False, enable_python_sidecar=False)

    assert _dataset_influence_rules(result) == []


@pytest.mark.parametrize("commons_mode", ["missing", "empty"])
def test_runner_dataset_influence_unbuilt_commons_ref_infos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commons_mode: str
) -> None:
    commons = tmp_path / "commons"
    if commons_mode == "empty":
        commons.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    _register_real_canonical_checks()
    project = _write_dataset_influence_project(tmp_path)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=False)

    assert _dataset_influence_rules(result) == [(Severity.INFO, "dataset-influence.ref-unresolved-unavailable")]


def test_runner_dataset_influence_initialized_commons_missing_ref_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_initialized_commons(tmp_path)))
    _register_real_canonical_checks()
    project = _write_dataset_influence_project(tmp_path)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=False)

    assert _dataset_influence_rules(result) == [(Severity.WARN, "dataset-influence.ref-unresolved")]
