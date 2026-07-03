from __future__ import annotations

import subprocess
import sys


def test_identity_authoring_imports_in_clean_process() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from science_tool.identity_authoring import build_identity_context; print('ok')"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
