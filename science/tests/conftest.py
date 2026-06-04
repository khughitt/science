from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Keep pytest's tmp_path off the per-user /tmp tmpfs quota. The validate parity
# gates stage real downstream projects into tmp_path; on Linux, systemd applies a
# per-UID usrquota to the /tmp tmpfs, and tools such as Claude Code point TMPDIR
# there, so multi-run/concurrent test temp can exhaust it and silently break any
# process that writes to /tmp. Route the test temp root to disk-backed storage.
# Override SCIENCE_TEST_TMPDIR to relocate it (for example, on CI).
_PYTEST_TMP_ROOT = Path(
    os.environ.get("SCIENCE_TEST_TMPDIR", Path.home() / ".cache" / "science-pytest-tmp")
)
_PYTEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_PYTEST_TMP_ROOT)
# tempfile caches the temp dir on first use; set it explicitly so the redirect
# wins even if something already called tempfile.gettempdir() during startup.
tempfile.tempdir = str(_PYTEST_TMP_ROOT)

# Make `_fixtures.*` importable as a top-level package: tests/ has no
# __init__.py (cross-project pytest collection treats it as a rootdir),
# so we add the tests directory to sys.path here.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@pytest.fixture(autouse=True)
def isolate_science_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / ".science-config"))
