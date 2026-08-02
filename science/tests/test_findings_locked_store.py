from __future__ import annotations

import errno
import fcntl
import os
from pathlib import Path

import pytest

from science_tool.findings.storage import CaseStorageError, locked_store


def _project(tmp_path: Path) -> Path:
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    return tmp_path


def test_locked_store_yields_a_store(tmp_path: Path) -> None:
    with locked_store(_project(tmp_path)) as store:
        assert store.names() == []


def test_flock_acquisition_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(fd: int, operation: int) -> None:
        raise OSError(errno.ENOLCK, "no locks available")

    monkeypatch.setattr(fcntl, "flock", boom)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(_project(tmp_path)):
            pass


def test_flock_release_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = fcntl.flock
    calls: list[int] = []

    def flaky(fd: int, operation: int) -> None:
        calls.append(operation)
        if operation == fcntl.LOCK_UN:
            raise OSError(errno.EIO, "release failed")
        real(fd, operation)

    monkeypatch.setattr(fcntl, "flock", flaky)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(_project(tmp_path)):
            pass
    assert fcntl.LOCK_UN in calls


def test_close_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = os.close
    state = {"armed": False}

    def flaky(fd: int) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OSError(errno.EIO, "close failed")
        real(fd)

    monkeypatch.setattr(os, "close", flaky)
    project = _project(tmp_path)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(project):
            state["armed"] = True


def test_body_exception_is_not_relabelled(tmp_path: Path) -> None:
    """`locked_store` adds NO catch spanning its body.

    An OSError that is neither FileNotFoundError nor PathSafetyError is not
    intercepted by `case_store`'s pre-existing clauses either, so it must arrive
    at the caller as itself.
    """
    sentinel = OSError(errno.EIO, "sentinel from the body")
    with pytest.raises(OSError) as caught:
        with locked_store(_project(tmp_path)):
            raise sentinel
    assert caught.value is sentinel
