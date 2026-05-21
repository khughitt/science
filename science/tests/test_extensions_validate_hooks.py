"""Packaged validate.sh does not run legacy sidecars directly."""

import os
import subprocess
from importlib import resources
from pathlib import Path


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def test_validate_sh_leaves_sidecar_handling_to_cli(tmp_path: Path) -> None:
    marker = tmp_path / "sidecar-sourced.txt"
    arg_log = tmp_path / "uv-args.txt"
    (tmp_path / "validate.local.sh").write_text(
        f'printf "sourced\\n" > "{marker}"\n',
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$UV_ARG_LOG"\n',
        encoding="utf-8",
    )
    uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["UV_ARG_LOG"] = str(arg_log)
    result = subprocess.run(
        ["bash", str(_canonical_path())],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert not marker.exists()
    assert arg_log.read_text(encoding="utf-8").splitlines() == ["run", "science", "validate"]
