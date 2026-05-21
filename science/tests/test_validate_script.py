from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _validate_script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "science_tool" / "project_artifacts" / "data" / "validate.sh"


def _write_uv_stub(bin_dir: Path, *, exit_code: int = 0) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    uv = bin_dir / "uv"
    uv.write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$UV_ARG_LOG"\nexit {exit_code}\n',
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return uv


def _run_validate_sh(
    project_root: Path,
    bin_dir: Path,
    arg_log: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["UV_ARG_LOG"] = str(arg_log)
    return subprocess.run(
        ["bash", str(_validate_script_path()), *args],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_sh_delegates_to_science_validate(tmp_path: Path) -> None:
    arg_log = tmp_path / "uv-args.txt"
    _write_uv_stub(tmp_path / "bin")

    result = _run_validate_sh(tmp_path, tmp_path / "bin", arg_log)

    assert result.returncode == 0
    assert arg_log.read_text(encoding="utf-8").splitlines() == ["run", "science", "validate"]


def test_validate_sh_forwards_cli_arguments_unchanged(tmp_path: Path) -> None:
    arg_log = tmp_path / "uv-args.txt"
    _write_uv_stub(tmp_path / "bin")

    result = _run_validate_sh(
        tmp_path,
        tmp_path / "bin",
        arg_log,
        "--format",
        "json",
        "--strict",
        "--project-root",
        ".",
    )

    assert result.returncode == 0
    assert arg_log.read_text(encoding="utf-8").splitlines() == [
        "run",
        "science",
        "validate",
        "--format",
        "json",
        "--strict",
        "--project-root",
        ".",
    ]


def test_validate_sh_propagates_science_validate_exit_code(tmp_path: Path) -> None:
    arg_log = tmp_path / "uv-args.txt"
    _write_uv_stub(tmp_path / "bin", exit_code=23)

    result = _run_validate_sh(tmp_path, tmp_path / "bin", arg_log)

    assert result.returncode == 23
    assert arg_log.read_text(encoding="utf-8").splitlines() == ["run", "science", "validate"]


def test_validate_sh_does_not_run_legacy_sidecar_itself(tmp_path: Path) -> None:
    arg_log = tmp_path / "uv-args.txt"
    marker = tmp_path / "sidecar-ran.txt"
    _write_uv_stub(tmp_path / "bin")
    (tmp_path / "validate.local.sh").write_text(
        f'printf "ran\\n" > "{marker}"\n',
        encoding="utf-8",
    )

    result = _run_validate_sh(tmp_path, tmp_path / "bin", arg_log)

    assert result.returncode == 0
    assert not marker.exists()
