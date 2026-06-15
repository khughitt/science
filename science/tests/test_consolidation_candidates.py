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


def test_id_stem_clusters_within_a_kind(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0003-foo-v3", {"id": "interpretation:0003-foo-v3", "type": "interpretation"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = [c for c in report.semantic_clusters if c.signal == "structural-family"]
    assert len(family) == 1
    assert family[0].members == [
        "interpretation:0001-foo-v1",
        "interpretation:0002-foo-v2",
        "interpretation:0003-foo-v3",
    ]
    assert "id-stem 'foo'" in family[0].evidence


def test_id_stem_does_not_cross_kinds(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "questions", "0001-foo", {"id": "question:0001-foo", "type": "question"})
    _write(tmp_path, "hypotheses", "0002-foo", {"id": "hypothesis:0002-foo", "type": "hypothesis"})
    _write(tmp_path, "interpretations", "0003-foo", {"id": "interpretation:0003-foo", "type": "interpretation"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "structural-family"] == []


def test_group_and_task_family_are_basis_namespaced(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Same value "alpha" reached by DIFFERENT bases must NOT merge into one cluster:
    #   - h1/h2 share group: alpha
    #   - h3/h4 share task:alpha in related
    # id-stems are distinct, so the only structural keys are (group, alpha) and
    # (task-family, task:alpha) -> two separate clusters.
    _write(tmp_path, "hypotheses", "0001-aa", {"id": "hypothesis:0001-aa", "type": "hypothesis", "group": "alpha"})
    _write(tmp_path, "hypotheses", "0002-bb", {"id": "hypothesis:0002-bb", "type": "hypothesis", "group": "alpha"})
    _write(tmp_path, "hypotheses", "0003-cc", {"id": "hypothesis:0003-cc", "type": "hypothesis", "related": ["task:alpha"]})
    _write(tmp_path, "hypotheses", "0004-dd", {"id": "hypothesis:0004-dd", "type": "hypothesis", "related": ["task:alpha"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = sorted((c for c in report.semantic_clusters if c.signal == "structural-family"), key=lambda c: c.members)
    assert len(family) == 2
    assert family[0].members == ["hypothesis:0001-aa", "hypothesis:0002-bb"]
    assert "group 'alpha'" in family[0].evidence
    assert family[1].members == ["hypothesis:0003-cc", "hypothesis:0004-dd"]
    assert "task-family 'task:alpha'" in family[1].evidence


def test_shared_anchor_clusters_same_kind(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for n in ("a", "b", "c"):
        _write(
            tmp_path, "interpretations", f"int-{n}",
            {"id": f"interpretation:int-{n}", "type": "interpretation", "related": ["hypothesis:0005-anchor"]},
        )

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    anchors = [c for c in report.semantic_clusters if c.signal == "shared-anchor"]
    assert len(anchors) == 1
    assert anchors[0].members == ["interpretation:int-a", "interpretation:int-b", "interpretation:int-c"]
    assert "hypothesis:0005-anchor" in anchors[0].evidence


def test_shared_anchor_ignores_unresolved_refs(tmp_path: Path) -> None:
    _seed(tmp_path)
    # The shared ref is a non-entity tag string, not a known kind:slug id -> no cluster.
    for n in ("a", "b", "c"):
        _write(
            tmp_path, "interpretations", f"int-{n}",
            {"id": f"interpretation:int-{n}", "type": "interpretation", "related": ["topic-tag-not-an-entity"]},
        )

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "shared-anchor"] == []
