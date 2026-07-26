from __future__ import annotations

import time
from pathlib import Path

import pytest

from science_tool.boundary.config import BoundaryRoot
from science_tool.boundary.walk import manifest_candidates


FILE_COUNT = 5000
BUDGET_SECONDS = 2.0
CONFLICT_BUDGET_SECONDS = 5.0


@pytest.fixture
def big_tree(tmp_path: Path) -> Path:
    for shard in range(50):
        d = tmp_path / "data/external/ds" / f"{shard:03d}"
        d.mkdir(parents=True)
        (d / "datapackage.json").write_text("{}")
        for n in range(FILE_COUNT // 50 - 1):
            (d / f"part-{n:05d}.parquet").write_text("x")
    return tmp_path


def test_walk_stays_within_budget(big_tree: Path):
    root = BoundaryRoot.model_validate(
        {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}
    )
    start = time.perf_counter()
    found = manifest_candidates(big_tree, root)
    elapsed = time.perf_counter() - start
    assert len(found) == 50
    assert elapsed < BUDGET_SECONDS, f"walk took {elapsed:.2f}s over {FILE_COUNT} files"


def test_conflict_detection_stays_within_budget(big_tree: Path):
    """Feed every extant path under the declared root; never sample an ERROR check."""
    import subprocess

    from science_tool.boundary.gitio import matching_unmanaged_rules
    from science_tool.validate.checks.boundary import _conflict_subjects

    subprocess.run(["git", "init", "-q", str(big_tree)], check=True)
    (big_tree / ".gitignore").write_text("*.parquet\n")
    subprocess.run(
        ["git", "-C", str(big_tree), "add", "-f", ".gitignore"], check=True
    )

    start = time.perf_counter()
    subjects = _conflict_subjects(big_tree, "data/external")
    hits = matching_unmanaged_rules(big_tree, subjects)
    elapsed = time.perf_counter() - start

    assert len(subjects) >= FILE_COUNT, "every extant path must be fed in, not a sample"
    assert hits, "the wildcard rule must be detected"
    assert elapsed < CONFLICT_BUDGET_SECONDS, (
        f"conflict pass took {elapsed:.2f}s over {FILE_COUNT} files"
    )


def test_conflict_detection_worst_case_peeling_stays_within_budget(big_tree: Path):
    """Pin all 40 matching lines, not merely a nonempty first peeling round."""
    import subprocess

    from science_tool.boundary.gitio import matching_unmanaged_rules
    from science_tool.validate.checks.boundary import _conflict_subjects

    subprocess.run(["git", "init", "-q", str(big_tree)], check=True)
    rules = "\n".join(
        f"*.parquet\n!/data/external/ds/{shard:03d}/**" for shard in range(20)
    )
    (big_tree / ".gitignore").write_text(rules + "\n")
    subprocess.run(
        ["git", "-C", str(big_tree), "add", "-f", ".gitignore"], check=True
    )

    start = time.perf_counter()
    hits = matching_unmanaged_rules(
        big_tree, _conflict_subjects(big_tree, "data/external")
    )
    elapsed = time.perf_counter() - start

    recovered = {
        (r.source, r.line) for rule_list in hits.values() for r in rule_list
    }
    assert recovered == {(".gitignore", n) for n in range(1, 41)}, (
        f"expected all 40 unmanaged rule lines, recovered {len(recovered)}"
    )
    assert elapsed < CONFLICT_BUDGET_SECONDS, (
        f"peeling took {elapsed:.2f}s over 40 rules"
    )
