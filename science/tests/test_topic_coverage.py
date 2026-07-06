from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.topic_coverage import MalformedTopicError, compute_topic_coverage

FIX = Path(__file__).parent / "fixtures" / "topic_coverage"


def _by_id(cov):
    return {r.id: r for r in cov.topics}


def test_counts_and_ratio() -> None:
    cov = compute_topic_coverage(FIX)
    # template-stub, promoted-stub, substantive, partial  (_index.md skipped)
    assert cov.n_topics == 4
    assert cov.n_substantive == 2  # substantive + partial
    assert cov.stub_ratio == 0.5
    assert cov.stub_dominated is False  # strictly > 0.5


def test_both_stub_shapes_detected() -> None:
    rows = _by_id(compute_topic_coverage(FIX))
    assert rows["topic:template-stub"].substantive is False
    assert rows["topic:promoted-stub"].substantive is False


def test_partial_curation_counts_substantive() -> None:
    rows = _by_id(compute_topic_coverage(FIX))
    assert rows["topic:partial"].substantive is True


def test_rows_sorted_by_id_and_have_paths() -> None:
    cov = compute_topic_coverage(FIX)
    ids = [r.id for r in cov.topics]
    assert ids == sorted(ids)
    for r in cov.topics:
        assert r.path.startswith("entities/topics/")


def test_zero_topics_branch(tmp_path: Path) -> None:
    (tmp_path / "entities" / "topics").mkdir(parents=True)
    cov = compute_topic_coverage(tmp_path)
    assert cov.n_topics == 0
    assert cov.stub_ratio is None
    assert cov.stub_dominated is False
    assert cov.note == "no topics"
    assert cov.to_dict()["stub_ratio"] is None


def test_malformed_frontmatter_raises(tmp_path: Path) -> None:
    # Own tmp dir — a malformed file in the shared FIX tree would break every test.
    topics = tmp_path / "entities" / "topics"
    topics.mkdir(parents=True)
    (topics / "broken.md").write_text("---\ntitle: [unterminated\n---\n\n# X\n", encoding="utf-8")
    with pytest.raises(MalformedTopicError):
        compute_topic_coverage(tmp_path)


def test_cli_json_shape() -> None:
    res = CliRunner().invoke(
        main, ["project", "topic-coverage", "--project-root", str(FIX), "--format", "json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["n_topics"] == 4
    assert payload["n_substantive"] == 2
    assert {t["id"] for t in payload["topics"]} >= {"topic:promoted-stub", "topic:partial"}
    assert all({"id", "title", "path", "substantive"} <= set(t) for t in payload["topics"])


def test_cli_text_default() -> None:
    res = CliRunner().invoke(main, ["project", "topic-coverage", "--project-root", str(FIX)])
    assert res.exit_code == 0, res.output
    assert "topics" in res.output.lower()
