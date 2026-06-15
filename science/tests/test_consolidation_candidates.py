"""Tests for the read-only consolidation-candidate detector (P2)."""

from __future__ import annotations

from pathlib import Path

import yaml


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: cand-test\n", encoding="utf-8")


def _supersedes(target: str) -> dict:
    return {"predicate": "sci:supersedes", "target": target}


def test_lineage_linear_reports_survivor_and_archivable(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v5", {"id": "interpretation:i-v5", "type": "interpretation", "relations": [_supersedes("interpretation:i-v4")]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert len(report.superseded_lineage.linear) == 1
    chain = report.superseded_lineage.linear[0]
    assert chain.survivor == "interpretation:i-v5"
    assert chain.archivable == ["interpretation:i-v3", "interpretation:i-v4"]
    assert chain.members == ["interpretation:i-v3", "interpretation:i-v4", "interpretation:i-v5"]
    assert report.counts["linear"] == 1


def test_lineage_non_linear_reported(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-a", {"id": "interpretation:i-a", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-b", {"id": "interpretation:i-b", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert report.superseded_lineage.linear == []
    assert len(report.superseded_lineage.non_linear) == 1
    assert report.superseded_lineage.non_linear[0].nodes == ["interpretation:i-a", "interpretation:i-b", "interpretation:i-v3"]


def test_lineage_reports_kind_lacking_superseded_vocab(tmp_path: Path) -> None:
    # workflow-run is supersedes-eligible but declares NO status vocabulary;
    # mark_superseded(apply) skips it, but the read-only detector still reports it.
    _seed(tmp_path)
    _write(tmp_path, "workflow-runs", "wr-old", {"id": "workflow-run:wr-old", "type": "workflow-run"})
    _write(tmp_path, "workflow-runs", "wr-new", {"id": "workflow-run:wr-new", "type": "workflow-run", "relations": [_supersedes("workflow-run:wr-old")]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert len(report.superseded_lineage.linear) == 1
    assert report.superseded_lineage.linear[0].archivable == ["workflow-run:wr-old"]
