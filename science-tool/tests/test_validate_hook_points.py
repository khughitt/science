"""Hook dispatch points exist in the canonical and fire in the documented order."""

import os
import subprocess
import textwrap
from importlib import resources
from pathlib import Path


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def test_canonical_dispatches_pre_validation_once() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert text.count('dispatch_hook "pre_validation"') == 1, (
        "expected exactly one pre_validation dispatch site in the canonical"
    )


def test_canonical_dispatches_extra_checks_once() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert text.count('dispatch_hook "extra_checks"') == 1, (
        "expected exactly one extra_checks dispatch site in the canonical"
    )


def test_canonical_traps_post_validation_on_exit() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert "trap 'dispatch_hook post_validation' EXIT" in text, "expected EXIT trap dispatching post_validation"


def test_pre_validation_fires_before_section_1() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    pre_pos = text.find('dispatch_hook "pre_validation"')
    sec1_pos = text.find("# ─── 1. Project manifest")
    assert pre_pos > 0 and sec1_pos > 0, "missing markers"
    assert pre_pos < sec1_pos, "pre_validation must dispatch before section 1"


def test_extra_checks_fires_before_summary() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    extra_pos = text.find('dispatch_hook "extra_checks"')
    summary_pos = text.find("# ─── Summary")
    assert extra_pos > 0 and summary_pos > 0, "missing markers"
    assert extra_pos < summary_pos, "extra_checks must dispatch before the summary"


def test_post_validation_trap_set_after_sidecar_source() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    sidecar_pos = text.find('source "validate.local.sh"')
    trap_pos = text.find("trap 'dispatch_hook post_validation' EXIT")
    assert sidecar_pos > 0 and trap_pos > 0, "missing markers"
    assert trap_pos > sidecar_pos, "EXIT trap must be set AFTER sidecar source so registered hooks are visible"


def _scaffold_minimal_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        textwrap.dedent(
            """\
            name: hooktest
            created: "2026-04-27"
            last_modified: "2026-04-27"
            status: "active"
            summary: "hooktest"
            profile: software
            layout_version: 2
            knowledge_profiles:
              local: local
            """
        ),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("# Hooktest\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    for d in ("doc", "specs", "tasks", "knowledge", "src"):
        (root / d).mkdir()
    (root / "tasks" / "active.md").write_text("<!-- tasks -->\n", encoding="utf-8")


def _run_canonical(project: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    canonical = _canonical_path()
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(canonical)],
        cwd=project,
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_three_hook_points_fire_in_order(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    _scaffold_minimal_project(project)
    log = project / "hook-log.txt"

    (project / "validate.local.sh").write_text(
        textwrap.dedent(
            f"""\
            on_pre()  {{ echo pre  >> "{log}"; }}
            on_extra(){{ echo extra >> "{log}"; }}
            on_post() {{ echo post >> "{log}"; }}
            register_validation_hook pre_validation on_pre
            register_validation_hook extra_checks   on_extra
            register_validation_hook post_validation on_post
            """
        ),
        encoding="utf-8",
    )

    result = _run_canonical(project)
    assert log.exists(), f"no hook log written; canonical output:\n{result.stdout}\n{result.stderr}"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines == ["pre", "extra", "post"], f"unexpected hook firing order: {lines}"


def test_post_validation_fires_when_extra_checks_fails(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    _scaffold_minimal_project(project)
    log = project / "hook-log.txt"

    (project / "validate.local.sh").write_text(
        textwrap.dedent(
            f"""\
            on_extra(){{ echo extra >> "{log}"; exit 99; }}
            on_post() {{ echo post  >> "{log}"; }}
            register_validation_hook extra_checks    on_extra
            register_validation_hook post_validation on_post
            """
        ),
        encoding="utf-8",
    )

    result = _run_canonical(project)
    assert result.returncode == 99, f"expected exit 99 from extra_checks; got {result.returncode}"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines == ["extra", "post"], f"post_validation must still fire on failure; got: {lines}"


def test_multiple_hooks_per_point_dispatch_in_registration_order(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    _scaffold_minimal_project(project)
    log = project / "hook-log.txt"

    (project / "validate.local.sh").write_text(
        textwrap.dedent(
            f"""\
            a(){{ echo a >> "{log}"; }}
            b(){{ echo b >> "{log}"; }}
            c(){{ echo c >> "{log}"; }}
            register_validation_hook pre_validation a
            register_validation_hook pre_validation b
            register_validation_hook pre_validation c
            """
        ),
        encoding="utf-8",
    )

    _run_canonical(project)
    assert log.read_text(encoding="utf-8").splitlines() == ["a", "b", "c"]
