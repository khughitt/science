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


def test_group_qualifies_task_family_only_suppressed(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Same value "alpha" reached by DIFFERENT bases is basis-namespaced internally so
    # the two groups never collide. Post-tuning gating: `group` is a PRIMARY basis so
    # h1/h2 are reported; `task-family` alone is corroborating-only, so the h3/h4
    # task-family cluster is SUPPRESSED (task:alpha is not a resolvable entity, so no
    # shared-anchor / related-overlap co-signal rescues it).
    _write(tmp_path, "hypotheses", "0001-aa", {"id": "hypothesis:0001-aa", "type": "hypothesis", "group": "alpha"})
    _write(tmp_path, "hypotheses", "0002-bb", {"id": "hypothesis:0002-bb", "type": "hypothesis", "group": "alpha"})
    _write(tmp_path, "hypotheses", "0003-cc", {"id": "hypothesis:0003-cc", "type": "hypothesis", "related": ["task:alpha"]})
    _write(tmp_path, "hypotheses", "0004-dd", {"id": "hypothesis:0004-dd", "type": "hypothesis", "related": ["task:alpha"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = [c for c in report.semantic_clusters if c.signal == "structural-family"]
    assert len(family) == 1
    assert family[0].members == ["hypothesis:0001-aa", "hypothesis:0002-bb"]
    assert "group 'alpha'" in family[0].evidence


def test_task_family_only_cluster_is_suppressed(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Two distinct-stem interpretations sharing only task:t99 (a non-entity prefix
    # ref) have no primary basis and no co-signal -> nothing reported.
    _write(tmp_path, "interpretations", "0001-alpha", {"id": "interpretation:0001-alpha", "type": "interpretation", "related": ["task:t99"]})
    _write(tmp_path, "interpretations", "0002-beta", {"id": "interpretation:0002-beta", "type": "interpretation", "related": ["task:t99"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert report.semantic_clusters == []


def test_single_shared_anchor_only_is_suppressed(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Two distinct-stem interpretations each referencing the SAME single anchor plus
    # their own distinct resolvable refs: one shared anchor, Jaccard below threshold,
    # distinct id-stems -> shared-anchor is corroborating-only, nothing qualifies.
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for c in ("p", "q", "r", "s"):
        _write(tmp_path, "concepts", f"c-{c}", {"id": f"concept:c-{c}", "type": "concept"})
    _write(tmp_path, "interpretations", "0001-alpha", {"id": "interpretation:0001-alpha", "type": "interpretation",
        "related": ["hypothesis:0005-anchor", "concept:c-p", "concept:c-q"]})
    _write(tmp_path, "interpretations", "0002-beta", {"id": "interpretation:0002-beta", "type": "interpretation",
        "related": ["hypothesis:0005-anchor", "concept:c-r", "concept:c-s"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert report.semantic_clusters == []


def test_two_shared_anchors_qualify_standalone(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Same two interpretations share TWO common anchors but also carry distinct extra
    # refs, so related Jaccard (2/6 = 0.33) stays below threshold and related-overlap
    # does NOT fire. The two single-anchor shared-anchor clusters have identical
    # member-sets and merge; >=2 distinct anchors makes shared-anchor self-qualifying
    # WITHOUT any primary basis -- isolating the anchor-count gate.
    _write(tmp_path, "hypotheses", "0005-a1", {"id": "hypothesis:0005-a1", "type": "hypothesis"})
    _write(tmp_path, "hypotheses", "0006-a2", {"id": "hypothesis:0006-a2", "type": "hypothesis"})
    for c in ("p", "q", "r", "s"):
        _write(tmp_path, "concepts", f"c-{c}", {"id": f"concept:c-{c}", "type": "concept"})
    _write(tmp_path, "interpretations", "0001-alpha", {"id": "interpretation:0001-alpha", "type": "interpretation",
        "related": ["hypothesis:0005-a1", "hypothesis:0006-a2", "concept:c-p", "concept:c-q"]})
    _write(tmp_path, "interpretations", "0002-beta", {"id": "interpretation:0002-beta", "type": "interpretation",
        "related": ["hypothesis:0005-a1", "hypothesis:0006-a2", "concept:c-r", "concept:c-s"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    members = ["interpretation:0001-alpha", "interpretation:0002-beta"]
    matching = [c for c in report.semantic_clusters if c.members == members]
    assert len(matching) == 1
    assert matching[0].signal == "shared-anchor"
    assert "hypothesis:0005-a1" in matching[0].evidence
    assert "hypothesis:0006-a2" in matching[0].evidence


def test_oversized_cluster_suppressed_and_counted(tmp_path: Path) -> None:
    _seed(tmp_path)
    # An id-stem family larger than max_cluster_size is suppressed but counted (no
    # silent caps): with 4 members and max_cluster_size=3, it drops and is tallied.
    for n in range(1, 5):
        _write(tmp_path, "interpretations", f"000{n}-foo-v{n}", {"id": f"interpretation:000{n}-foo-v{n}", "type": "interpretation"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path, max_cluster_size=3)
    assert report.semantic_clusters == []
    assert report.counts["suppressed_oversized"] == 1
    # Raising the ceiling re-admits it.
    report2 = detect_consolidation_candidates(tmp_path, max_cluster_size=4)
    assert len(report2.semantic_clusters) == 1
    assert report2.counts["suppressed_oversized"] == 0


def test_id_stem_clusters_sort_first(tmp_path: Path) -> None:
    _seed(tmp_path)
    # An id-stem family and a related-overlap cluster. "related-overlap" sorts before
    # "structural-family" alphabetically, but id-stem clusters must surface FIRST.
    _write(tmp_path, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "type": "interpretation"})
    for a in ("a", "b", "c"):
        _write(tmp_path, "concepts", f"anchor-{a}", {"id": f"concept:anchor-{a}", "type": "concept"})
    # Distinct-stem pair sharing 3 concept anchors -> related-overlap (Jaccard 1.0),
    # but >=2 anchors so it also stands as shared-anchor; either way it is non-id-stem.
    _write(tmp_path, "questions", "0001-zeta", {"id": "question:0001-zeta", "type": "question",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})
    _write(tmp_path, "questions", "0002-omega", {"id": "question:0002-omega", "type": "question",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert len(report.semantic_clusters) == 2
    assert "id-stem" in report.semantic_clusters[0].evidence


def test_default_related_jaccard_is_point_seven(tmp_path: Path) -> None:
    _seed(tmp_path)
    for a in ("a", "b", "c", "d", "e"):
        _write(tmp_path, "concepts", f"anchor-{a}", {"id": f"concept:anchor-{a}", "type": "concept"})
    # x={a,b,c}, y={a,b,c,d,e} -> Jaccard 3/5 = 0.6 < 0.7 default : no related-overlap.
    # Distinct stems, three shared anchors so shared-anchor self-qualifies instead —
    # confirming the threshold change without losing the pair entirely.
    _write(tmp_path, "interpretations", "0001-alpha", {"id": "interpretation:0001-alpha", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})
    _write(tmp_path, "interpretations", "0002-beta", {"id": "interpretation:0002-beta", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c", "concept:anchor-d", "concept:anchor-e"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if "related-overlap" in c.signal] == []


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
    # All three share the same related set {hypothesis:0005-anchor}, so related-overlap
    # (Jaccard=1.0) also fires and merges with shared-anchor into a combined signal.
    members = ["interpretation:int-a", "interpretation:int-b", "interpretation:int-c"]
    anchors = [c for c in report.semantic_clusters if c.members == members]
    assert len(anchors) == 1
    assert "shared-anchor" in anchors[0].signal
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


def test_related_overlap_clusters_above_threshold(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Anchors a..d exist as entities so refs resolve.
    for a in ("a", "b", "c", "d"):
        _write(tmp_path, "concepts", f"anchor-{a}", {"id": f"concept:anchor-{a}", "type": "concept"})
    # x and y share 3/4 related -> Jaccard 0.75 >= 0.5 : cluster.
    # They also share anchors a/b/c, so shared-anchor fires too; signals merge.
    _write(tmp_path, "interpretations", "x", {"id": "interpretation:x", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})
    _write(tmp_path, "interpretations", "y", {"id": "interpretation:y", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c", "concept:anchor-d"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    members = ["interpretation:x", "interpretation:y"]
    overlap = [c for c in report.semantic_clusters if c.members == members]
    assert len(overlap) == 1
    assert "related-overlap" in overlap[0].signal
    assert "Jaccard" in overlap[0].evidence


def test_related_overlap_below_threshold_no_cluster(tmp_path: Path) -> None:
    _seed(tmp_path)
    for a in ("a", "b", "c"):
        _write(tmp_path, "concepts", f"anchor-{a}", {"id": f"concept:anchor-{a}", "type": "concept"})
    # x={a}, y={a,b,c} -> Jaccard 1/3 = 0.33 < 0.5 : no cluster.
    _write(tmp_path, "interpretations", "x", {"id": "interpretation:x", "type": "interpretation", "related": ["concept:anchor-a"]})
    _write(tmp_path, "interpretations", "y", {"id": "interpretation:y", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "related-overlap"] == []


def test_related_overlap_ignores_non_entity_refs(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Both share only a non-entity tag string -> not counted -> no cluster.
    _write(tmp_path, "interpretations", "x", {"id": "interpretation:x", "type": "interpretation", "related": ["just-a-tag", ""]})
    _write(tmp_path, "interpretations", "y", {"id": "interpretation:y", "type": "interpretation", "related": ["just-a-tag"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "related-overlap"] == []


def test_duplicate_member_sets_merge_evidence(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Same two entities fire BOTH id-stem (shared stem 'foo') AND shared-anchor
    # (both ref hypothesis:0005) -> one merged cluster, both evidences, joined signal.
    # Each carries DISTINCT extra resolvable refs so related-overlap stays below
    # threshold (Jaccard 1/5 = 0.2 < 0.5) and does NOT also fire — keeping the
    # merged signal exactly "shared-anchor+structural-family".
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for c in ("p", "q", "r", "s"):
        _write(tmp_path, "concepts", f"c-{c}", {"id": f"concept:c-{c}", "type": "concept"})
    _write(tmp_path, "interpretations", "0001-foo-v1",
        {"id": "interpretation:0001-foo-v1", "type": "interpretation",
         "related": ["hypothesis:0005-anchor", "concept:c-p", "concept:c-q"]})
    _write(tmp_path, "interpretations", "0002-foo-v2",
        {"id": "interpretation:0002-foo-v2", "type": "interpretation",
         "related": ["hypothesis:0005-anchor", "concept:c-r", "concept:c-s"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    members = ["interpretation:0001-foo-v1", "interpretation:0002-foo-v2"]
    matching = [c for c in report.semantic_clusters if c.members == members]
    assert len(matching) == 1  # merged, not duplicated
    assert matching[0].signal == "shared-anchor+structural-family"
    assert "id-stem 'foo'" in matching[0].evidence
    assert "hypothesis:0005-anchor" in matching[0].evidence


def test_semantic_excludes_non_default_visible_entities(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Three share stem 'foo', but one is superseded -> excluded from semantic
    # clustering, leaving only 2 visible members. (It still appears in lineage if
    # part of a chain; here it is not.)
    _write(tmp_path, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0003-foo-v3", {"id": "interpretation:0003-foo-v3", "type": "interpretation", "status": "superseded"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = [c for c in report.semantic_clusters if c.signal == "structural-family"]
    assert len(family) == 1
    assert family[0].members == ["interpretation:0001-foo-v1", "interpretation:0002-foo-v2"]


def test_report_is_deterministic(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for n in ("a", "b", "c"):
        _write(tmp_path, "interpretations", f"0001-fam-{n}",
            {"id": f"interpretation:0001-fam-{n}", "type": "interpretation", "related": ["hypothesis:0005-anchor"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    first = detect_consolidation_candidates(tmp_path).model_dump(mode="json")
    second = detect_consolidation_candidates(tmp_path).model_dump(mode="json")
    assert first == second
