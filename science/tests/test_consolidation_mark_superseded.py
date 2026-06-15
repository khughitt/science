"""Auto-derive `superseded` from supersedes chains (consolidation P1)."""

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
    (root / "science.yaml").write_text("name: chain-test\n", encoding="utf-8")


def _supersedes(target: str) -> dict:
    """A canonical supersedes relation entry, as authored in `relations:`."""
    return {"predicate": "sci:supersedes", "target": target}


def test_report_linear_chain_lists_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    # v3 <- v4 <- v5 : v5 supersedes v4, v4 supersedes v3. Survivor = v5.
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v5", {"id": "interpretation:i-v5", "type": "interpretation", "relations": [_supersedes("interpretation:i-v4")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["applied"] == []
    assert len(report["chains"]) == 1
    chain = report["chains"][0]
    assert chain["survivor"] == "interpretation:i-v5"
    assert chain["linear"] is True
    assert set(chain["members"]) == {"interpretation:i-v3", "interpretation:i-v4"}
    assert set(report["to_mark"]) == {"interpretation:i-v3", "interpretation:i-v4"}
    assert report["non_linear"] == []
    assert report["skipped_kinds"] == []


def test_amends_relation_does_not_mark_superseded(tmp_path: Path) -> None:
    _seed(tmp_path)
    # sci:amends is a revision, NOT a replacement — it must not mark the target.
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [{"predicate": "sci:amends", "target": "interpretation:i-v3"}]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["chains"] == []
    assert report["to_mark"] == []


def test_report_skips_already_superseded_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation", "status": "superseded"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["to_mark"] == []  # i-v3 is already superseded


def test_report_flags_non_linear_chain_and_skips_it(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Branched: both v4a and v4b supersede v3 (v3 has in-degree 2). Ambiguous.
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4a", {"id": "interpretation:i-v4a", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v4b", {"id": "interpretation:i-v4b", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["chains"] == []
    assert report["to_mark"] == []
    assert len(report["non_linear"]) == 1
    assert set(report["non_linear"][0]["nodes"]) == {
        "interpretation:i-v3",
        "interpretation:i-v4a",
        "interpretation:i-v4b",
    }


def test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed(tmp_path: Path) -> None:
    _seed(tmp_path)
    # workflow-run is supersedes-eligible but declares NO status vocabulary.
    # The member must be reported under skipped_kinds, never crash.
    _write(tmp_path, "workflow-runs", "wr-old", {"id": "workflow-run:wr-old", "type": "workflow-run"})
    _write(tmp_path, "workflow-runs", "wr-new", {"id": "workflow-run:wr-new", "type": "workflow-run", "relations": [_supersedes("workflow-run:wr-old")]})

    from science_tool.consolidation import mark_superseded

    report = mark_superseded(tmp_path, apply=False)
    assert report["to_mark"] == []
    assert {entry["id"] for entry in report["skipped_kinds"]} == {"workflow-run:wr-old"}
    assert report["skipped_kinds"][0]["kind"] == "workflow-run"
