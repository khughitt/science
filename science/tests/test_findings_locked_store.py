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


def test_lock_validation_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(fd: int) -> os.stat_result:
        raise OSError(errno.EIO, "fstat failed")

    monkeypatch.setattr(os, "fstat", boom)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(_project(tmp_path)):
            pass


def test_lock_validation_cleanup_failure_does_not_escape_storage_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_close = os.close
    armed = False

    def broken_fstat(fd: int) -> os.stat_result:
        nonlocal armed
        armed = True
        raise OSError(errno.EIO, "fstat failed")

    def flaky_close(fd: int) -> None:
        nonlocal armed
        real_close(fd)
        if armed:
            armed = False
            raise OSError(errno.EIO, "validation cleanup failed")

    monkeypatch.setattr(os, "fstat", broken_fstat)
    monkeypatch.setattr(os, "close", flaky_close)
    with pytest.raises(CaseStorageError, match="lock"):
        with locked_store(_project(tmp_path)):
            pass


def test_directory_close_failure_becomes_case_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_flock = fcntl.flock
    real_close = os.close
    lock_fd: int | None = None
    lock_closed = False

    def capture_lock(fd: int, operation: int) -> None:
        nonlocal lock_fd
        if operation == fcntl.LOCK_EX:
            lock_fd = fd
        real_flock(fd, operation)

    def flaky_close(fd: int) -> None:
        nonlocal lock_closed
        real_close(fd)
        if fd == lock_fd:
            lock_closed = True
        elif lock_closed:
            raise OSError(errno.EIO, "directory close failed")

    monkeypatch.setattr(fcntl, "flock", capture_lock)
    monkeypatch.setattr(os, "close", flaky_close)
    with pytest.raises(CaseStorageError, match="director"):
        with locked_store(_project(tmp_path)):
            pass


def test_body_exception_is_not_replaced_by_teardown_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_flock = fcntl.flock
    real_close = os.close
    lock_fd: int | None = None
    lock_closed = False
    failures: list[str] = []

    def flaky_flock(fd: int, operation: int) -> None:
        nonlocal lock_fd
        if operation == fcntl.LOCK_EX:
            lock_fd = fd
            real_flock(fd, operation)
        else:
            failures.append("release")
            raise OSError(errno.EIO, "release failed")

    def flaky_close(fd: int) -> None:
        nonlocal lock_closed
        real_close(fd)
        if fd == lock_fd:
            lock_closed = True
            failures.append("lock close")
            raise OSError(errno.EIO, "lock close failed")
        if lock_closed:
            failures.append("directory close")
            raise OSError(errno.EIO, "directory close failed")

    monkeypatch.setattr(fcntl, "flock", flaky_flock)
    monkeypatch.setattr(os, "close", flaky_close)
    sentinel = OSError(errno.EIO, "sentinel from the body")

    with pytest.raises(OSError) as caught:
        with locked_store(_project(tmp_path)):
            raise sentinel

    assert caught.value is sentinel
    assert failures == ["release", "lock close", "directory close"]


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
