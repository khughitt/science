"""Packaged validate.sh delegates hook behavior to the validate CLI."""

import os
import subprocess
from importlib import resources
from pathlib import Path


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def _fake_uv(tmp_path: Path, *, exit_code: int = 0) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$UV_ARG_LOG"\nexit {exit_code}\n',
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return bin_dir


def _run_canonical(project: Path, bin_dir: Path, arg_log: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["UV_ARG_LOG"] = str(arg_log)
    return subprocess.run(
        ["bash", str(_canonical_path()), *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_canonical_delegates_to_validate_cli_with_original_args(tmp_path: Path) -> None:
    arg_log = tmp_path / "uv-args.txt"
    bin_dir = _fake_uv(tmp_path)

    result = _run_canonical(tmp_path, bin_dir, arg_log, "--strict", "--verbose")

    assert result.returncode == 0
    assert arg_log.read_text(encoding="utf-8").splitlines() == [
        "run",
        "science",
        "validate",
        "--strict",
        "--verbose",
    ]


def test_canonical_propagates_validate_cli_exit_code(tmp_path: Path) -> None:
    arg_log = tmp_path / "uv-args.txt"
    bin_dir = _fake_uv(tmp_path, exit_code=37)

    result = _run_canonical(tmp_path, bin_dir, arg_log)

    assert result.returncode == 37
    assert arg_log.read_text(encoding="utf-8").splitlines() == ["run", "science", "validate"]


def test_canonical_no_longer_embeds_bash_hook_dispatch() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert "dispatch_hook" not in text
    assert "register_validation_hook" not in text
    assert 'source "validate.local.sh"' not in text
