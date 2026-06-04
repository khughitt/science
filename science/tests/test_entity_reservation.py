from __future__ import annotations

from pathlib import Path

from science_tool.entities import LOCAL_PART_WIDTH
from science_tool.entity_reservation import reserve_entity


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
