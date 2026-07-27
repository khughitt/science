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
def big_tree(tmp_path: Path) -> tuple[Path, frozenset[str]]:
    fixture_paths: set[str] = set()
    for shard in range(50):
        shard_rel = f"data/external/ds/{shard:03d}"
        d = tmp_path / shard_rel
        d.mkdir(parents=True)
        (d / "datapackage.json").write_text("{}")
        fixture_paths.add(f"{shard_rel}/datapackage.json")
        for n in range(FILE_COUNT // 50 - 1):
            (d / f"part-{n:05d}.parquet").write_text("x")
            fixture_paths.add(f"{shard_rel}/part-{n:05d}.parquet")
    assert len(fixture_paths) == FILE_COUNT
    return tmp_path, frozenset(fixture_paths)


def test_walk_stays_within_budget(big_tree: tuple[Path, frozenset[str]]):
    project_root, _fixture_paths = big_tree
    root = BoundaryRoot.model_validate({"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]})
    start = time.perf_counter()
    found = manifest_candidates(project_root, root)
    elapsed = time.perf_counter() - start
    assert len(found) == 50
    assert elapsed < BUDGET_SECONDS, f"walk took {elapsed:.2f}s over {FILE_COUNT} files"


def test_conflict_detection_stays_within_budget(big_tree: tuple[Path, frozenset[str]]):
    """Feed every extant path under the declared root; never sample an ERROR check."""
    import subprocess

    from science_tool.boundary.gitio import matching_unmanaged_rules
    from science_tool.validate.checks.boundary import _conflict_subjects

    project_root, fixture_paths = big_tree
    subprocess.run(["git", "init", "-q", str(project_root)], check=True)
    (project_root / ".gitignore").write_text("*.parquet\n")
    subprocess.run(["git", "-C", str(project_root), "add", "-f", ".gitignore"], check=True)

    start = time.perf_counter()
    subjects = _conflict_subjects(project_root, "data/external")
    hits = matching_unmanaged_rules(project_root, subjects)
    elapsed = time.perf_counter() - start

    subject_paths = set(subjects)
    assert fixture_paths <= subject_paths, (
        f"conflict subjects omitted {len(fixture_paths - subject_paths)} fixture paths"
    )
    assert len(subjects) >= FILE_COUNT, "every extant path must be fed in, not a sample"
    assert hits, "the wildcard rule must be detected"
    assert elapsed < CONFLICT_BUDGET_SECONDS, f"conflict pass took {elapsed:.2f}s over {FILE_COUNT} files"


def test_conflict_detection_worst_case_peeling_stays_within_budget(big_tree: tuple[Path, frozenset[str]]):
    """Pin all 40 matching lines, not merely a nonempty first peeling round."""
    import subprocess

    from science_tool.boundary.gitio import matching_unmanaged_rules
    from science_tool.validate.checks.boundary import _conflict_subjects

    project_root, _fixture_paths = big_tree
    subprocess.run(["git", "init", "-q", str(project_root)], check=True)
    rules = "\n".join(f"*.parquet\n!/data/external/ds/{shard:03d}/**" for shard in range(20))
    (project_root / ".gitignore").write_text(rules + "\n")
    subprocess.run(["git", "-C", str(project_root), "add", "-f", ".gitignore"], check=True)

    start = time.perf_counter()
    hits = matching_unmanaged_rules(
        project_root,
        _conflict_subjects(project_root, "data/external"),
    )
    elapsed = time.perf_counter() - start

    recovered = {(r.source, r.line) for rule_list in hits.values() for r in rule_list}
    assert recovered == {(".gitignore", n) for n in range(1, 41)}, (
        f"expected all 40 unmanaged rule lines, recovered {len(recovered)}"
    )
    assert elapsed < CONFLICT_BUDGET_SECONDS, f"peeling took {elapsed:.2f}s over 40 rules"
