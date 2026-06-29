import hashlib
import os
from pathlib import Path

import pytest

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_package.payload import PayloadError, payload_inventory


def _write(root: Path, rel: str, content: bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_payload_inventory_hashes_and_sorts(tmp_path: Path):
    _write(tmp_path, "data/processed/b.parquet", b"\x01\x02\x03")
    _write(tmp_path, "data/raw/a.bin", b"\x00")
    inv = payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set={"data/raw/a.bin"})
    assert inv == [
        {
            "path": "data/processed/b.parquet",
            "sha256": hashlib.sha256(b"\x01\x02\x03").hexdigest(),
            "bytes": 3,
            "git_tracked": False,
        },
        {
            "path": "data/raw/a.bin",
            "sha256": hashlib.sha256(b"\x00").hexdigest(),
            "bytes": 1,
            "git_tracked": True,
        },
    ]


def test_payload_inventory_follows_symlink_to_content(tmp_path: Path):
    target = tmp_path / "outside.bin"
    target.write_bytes(b"hydrated")
    (tmp_path / "data" / "processed").mkdir(parents=True)
    os.symlink(target, tmp_path / "data" / "processed" / "link.bin")
    inv = payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())
    assert inv[0]["sha256"] == hashlib.sha256(b"hydrated").hexdigest()
    assert inv[0]["bytes"] == len(b"hydrated")


def test_payload_inventory_raises_payload_error_on_cycle(tmp_path: Path):
    d = tmp_path / "data" / "processed"
    d.mkdir(parents=True)
    os.symlink(d, d / "loop")
    with pytest.raises(PayloadError):
        payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())


def test_payload_inventory_raises_payload_error_on_non_regular(tmp_path: Path):
    d = tmp_path / "data" / "processed"
    d.mkdir(parents=True)
    os.mkfifo(d / "fifo")
    with pytest.raises(PayloadError):
        payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())
