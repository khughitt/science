from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from science_tool.entities import LOCAL_PART_WIDTH
from science_tool.entity_reservation import claim_number_in_dir, reserve_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


class _ExplodingHandle:
    """A context-manager handle whose write() raises, but which really created the file."""
    def __init__(self, real):
        self._real = real
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return self._real.__exit__(*exc)
    def write(self, _data):
        raise OSError("simulated disk-full during write")


def test_claim_self_cleans_partial_destination_on_write_failure(tmp_path, monkeypatch):
    root = _project(tmp_path)
    real_open = builtins.open

    def exploding_open(file, mode="r", *args, **kwargs):
        handle = real_open(file, mode, *args, **kwargs)
        if "x" in mode:  # the exclusive destination create — file now exists on disk
            return _ExplodingHandle(handle)
        return handle

    monkeypatch.setattr(builtins, "open", exploding_open)

    with pytest.raises(OSError):
        claim_number_in_dir(root, "plan", 1, "0001-a-thing", "# A Thing\n\nbody\n")

    plans_dir = root / "entities" / "plans"
    assert not (plans_dir / "0001-a-thing.md").exists(), "partial destination survived a failed write"
    assert not list(plans_dir.glob(".*.reserving")), "sentinel leaked"


def test_claim_removes_owned_destination_when_sentinel_cleanup_fails(
    tmp_path, monkeypatch
):
    root = _project(tmp_path)
    sentinel = root / "entities/plans/.0001.reserving"
    destination = root / "entities/plans/0001-a-thing.md"
    real_unlink = Path.unlink

    def failing_sentinel_unlink(path, *args, **kwargs):
        if path == sentinel:
            raise OSError("simulated sentinel cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", failing_sentinel_unlink)

    with pytest.raises(OSError, match="sentinel cleanup failure"):
        claim_number_in_dir(root, "plan", 1, "0001-a-thing", "# A Thing\n\nbody\n")

    assert not destination.exists(), "owned destination survived a failed claim"


def test_reserve_first_is_0001(tmp_path: Path) -> None:
    res = reserve_entity(tmp_path, "hypothesis", "first idea")
    assert res.entity_id == "hypothesis:0001-first-idea"
    assert (tmp_path / "entities" / "hypotheses" / "0001-first-idea.md").is_file()


def test_reserve_is_atomic_and_increments(tmp_path: Path) -> None:
    a = reserve_entity(tmp_path, "finding", "alpha")
    b = reserve_entity(tmp_path, "finding", "beta")
    assert a.entity_id == "finding:0001-alpha"
    assert b.entity_id == "finding:0002-beta"


def test_reserve_tolerates_legacy_letter_siblings(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True)
    (d / "h03-legacy.md").write_text("x", encoding="utf-8")
    res = reserve_entity(tmp_path, "hypothesis", "next")
    assert res.entity_id == "hypothesis:0004-next"


def test_reserve_is_atomic_across_concurrent_distinct_slugs(tmp_path: Path) -> None:
    # The regression that a slugged-filename lock misses: many reservers racing
    # with DIFFERENT slugs must still receive DISTINCT numbers (no two share NNNN).
    import threading

    n_workers = 12
    barrier = threading.Barrier(n_workers)
    results: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        barrier.wait()  # maximize interleaving around the os.open claim
        res = reserve_entity(tmp_path, "finding", f"topic-{i}")
        with lock:
            results.append(res.entity_id)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    numbers = sorted(int(rid.split(":")[1][:LOCAL_PART_WIDTH]) for rid in results)
    assert numbers == list(range(1, n_workers + 1)), f"duplicate/non-contiguous numbers: {numbers}"
    files = sorted(p.name for p in (tmp_path / "entities" / "findings").glob("*.md"))
    assert len(files) == n_workers
    assert len({name[:LOCAL_PART_WIDTH] for name in files}) == n_workers
