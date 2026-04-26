"""Hook contract: register_validation_hook + dispatch in canonical."""

import shutil
import subprocess
from pathlib import Path


def _copy_fixture_to(tmp: Path) -> Path:
    src = Path(__file__).parent / "_fixtures" / "validate_hooks_canonical.sh"
    dst = tmp / "validate.sh"
    shutil.copy(src, dst)
    dst.chmod(0o755)
    return dst


def test_no_sidecar_runs_canonical_only(tmp_path: Path) -> None:
    canonical = _copy_fixture_to(tmp_path)
    result = subprocess.run([str(canonical)], cwd=tmp_path, capture_output=True, text=True, check=True)
    out = result.stdout.strip().splitlines()
    assert out == ["BEGIN", "MIDDLE", "END"]


def test_sidecar_hook_runs_at_named_point(tmp_path: Path) -> None:
    _copy_fixture_to(tmp_path)
    (tmp_path / "validate.local.sh").write_text(
        "my_hook() { echo 'INTERPOSED'; }\nregister_validation_hook before_pre_registration_check my_hook\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(tmp_path / "validate.sh")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip().splitlines()
    assert out == ["BEGIN", "INTERPOSED", "MIDDLE", "END"]


def test_multiple_hooks_dispatch_in_registration_order(tmp_path: Path) -> None:
    _copy_fixture_to(tmp_path)
    (tmp_path / "validate.local.sh").write_text(
        "h1() { echo 'A'; }\nh2() { echo 'B'; }\n"
        "register_validation_hook final_summary h1\n"
        "register_validation_hook final_summary h2\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(tmp_path / "validate.sh")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip().splitlines()
    assert out == ["BEGIN", "MIDDLE", "END", "A", "B"]
