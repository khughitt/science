"""Shared fixtures for source-aware promote tests (Tasks 7, 8, 10)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "t@x"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "t"],
        check=True, capture_output=True,
    )


def sourced_project(tmp_path: Path, ref: str) -> Path:
    """A copy of the proj-dataset fixture with r1 turned into a sourced resource."""
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    dp_path = proj / "data" / "fixture-ds" / "datapackage.json"
    dp = json.loads(dp_path.read_text())
    dp["resources"][0] = {
        "name": "r1",
        "path": "r1.txt",
        "format": "txt",
        "mediatype": "text/plain",
        "hash": "sha256:" + "a" * 64,
        "bytes": 12,
        "source": {"type": "local", "ref": ref},
    }
    dp_path.write_text(json.dumps(dp), encoding="utf-8")
    # r2 stays co-located; delete r1.txt so only the sourced one is off-repo.
    (proj / "data" / "fixture-ds" / "r1.txt").unlink()
    init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return proj


def init_commons(tmp_path: Path) -> Path:
    """A minimal initialized commons store with the empty layout dirs."""
    commons = tmp_path / "commons"
    commons.mkdir()
    init_repo(commons)
    (commons / "datasets").mkdir()
    (commons / ".migrations").mkdir()
    (commons / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return commons
