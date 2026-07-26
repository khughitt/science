from __future__ import annotations

import time
from pathlib import Path

import pytest

from science_tool.boundary.config import BoundaryRoot
from science_tool.boundary.walk import manifest_candidates


FILE_COUNT = 5000
BUDGET_SECONDS = 2.0


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
