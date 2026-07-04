from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from science_tool.explore_ideas import (
    ApplyValidationError,
    ApplyWriteBackError,
    CandidateBlock,
    build_create_plan,
    parse_report,
    plan_report,
    resolve_report_path,
    write_back,
)

_REPORT = """\
---
type: meta
id: explore-2026-07-04
---

# Exploration report

Some human prose that is not a candidate.

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
decision: keep
```

```yaml
not_a_candidate: true
note: ignore me
```

```yaml
candidate_id: cand-b
proposed_kind: hypothesis
title: Second
decision: drop
```
"""


def test_parse_report_extracts_only_candidate_blocks() -> None:
    blocks = parse_report(_REPORT)
    assert [b.candidate_id for b in blocks] == ["cand-a", "cand-b"]
    assert isinstance(blocks[0], CandidateBlock)
    assert blocks[0].data["title"] == "First"


def test_parse_report_ignores_non_yaml_and_non_candidate() -> None:
    assert parse_report("no fenced blocks here") == []


def test_parse_report_malformed_yaml_raises_validation_error() -> None:
    text = "```yaml\ncandidate_id: [unterminated\n```\n"
    with pytest.raises(ApplyValidationError, match="invalid yaml"):
        parse_report(text)


def test_resolve_report_path_direct_file(tmp_path: Path) -> None:
    report = tmp_path / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, str(report)) == report


def test_resolve_report_path_relative_file_anchored_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    assert resolve_report_path(
        tmp_path, "entities/meta/explorations/explore-2026-07-04.md"
    ) == report


def test_resolve_report_path_by_id(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, "explore-2026-07-04") == report


def test_resolve_report_path_no_reprepend(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    (d / "explore-2026-07-04.md").write_text("x", encoding="utf-8")
    with pytest.raises(ApplyValidationError):
        resolve_report_path(tmp_path, "explore-explore-2026-07-04")


def test_resolve_report_path_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ApplyValidationError):
        resolve_report_path(tmp_path, "nope")


def _keep_question(**over):
    data = {
        "candidate_id": "cand-q",
        "proposed_kind": "question",
        "title": "A question",
        "decision": "keep",
        "literature_anchors": [],
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    data.update(over)
    return data


def test_build_plan_reasoned_only() -> None:
    plan = build_create_plan("cand-q", _keep_question(), "opus")
    assert plan.kind == "question"
    assert plan.title == "A question"
    assert plan.origins == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    assert plan.source_refs == []
    assert plan.added_by == "explore-ideas:opus:cand-q"


def test_build_plan_supporting_anchor_becomes_source_ref() -> None:
    data = _keep_question(
        literature_anchors=[{"ref": "cite:chen2022", "note": "supports the framing"}],
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == ["cite:chen2022"]
    assert plan.origins == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]


def test_build_plan_predates_anchor_is_not_a_source_ref() -> None:
    data = _keep_question(
        literature_anchors=[{"ref": "cite:okafor2015", "note": "predates: convergent"}],
        origin_plan={
            "origins": [
                {"type": "assistant", "ref": "explore-ideas-methodology"},
                {"type": "literature", "ref": "cite:okafor2015", "independent": True},
            ]
        },
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == []
    assert any(o.get("independent") for o in plan.origins)


def test_build_plan_dedupes_source_refs_in_order() -> None:
    data = _keep_question(
        literature_anchors=[
            {"ref": "cite:a", "note": "x"},
            {"ref": "cite:b", "note": "y"},
            {"ref": "cite:a", "note": "again"},
            {"ref": None, "note": "unresolved"},
        ],
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == ["cite:a", "cite:b"]


def test_build_plan_normalizes_yaml_date_object() -> None:
    data = _keep_question(
        origin_plan={
            "origins": [
                {"type": "assistant", "ref": "explore-ideas-methodology"},
                {
                    "type": "literature",
                    "ref": "cite:okafor2015",
                    "independent": True,
                    "date": date(2015, 3, 12),
                },
            ]
        },
    )
    plan = build_create_plan("cand-q", data, "opus")
    lit = [o for o in plan.origins if o["type"] == "literature"][0]
    assert lit["date"] == "2015-03-12"
    assert "note" not in lit


def test_build_plan_canonical_origin_dump_excludes_defaults() -> None:
    data = _keep_question(
        origin_plan={
            "origins": [
                {"type": "assistant", "ref": "explore-ideas-methodology", "note": None},
                {
                    "type": "literature",
                    "ref": "cite:okafor2015",
                    "independent": True,
                    "note": None,
                    "date": date(2015, 3, 12),
                },
            ]
        },
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.origins[0] == {"type": "assistant", "ref": "explore-ideas-methodology"}
    assert plan.origins[1] == {
        "type": "literature",
        "ref": "cite:okafor2015",
        "independent": True,
        "date": "2015-03-12",
    }


def test_build_plan_rejects_missing_title() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(title=""), "opus")


def test_build_plan_rejects_missing_origins() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(origin_plan={"origins": []}), "opus")


def test_build_plan_rejects_bad_origin() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan(
            "cand-q",
            _keep_question(origin_plan={"origins": [{"type": "literature"}]}),
            "opus",
        )


def test_build_plan_rejects_non_string_ref() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": 123}]), "opus")


def test_build_plan_rejects_non_string_note() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": "cite:a", "note": 5}]), "opus")


def test_build_plan_rejects_non_string_note_on_unresolved_anchor() -> None:
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": None, "note": 5}]), "opus")


@pytest.mark.parametrize("kind", [None, "topic"])
def test_build_plan_rejects_invalid_proposed_kind(kind: object) -> None:
    data = _keep_question(proposed_kind=kind)
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", data, "opus")


def test_build_plan_missing_note_routes_as_support() -> None:
    plan = build_create_plan("cand-q", _keep_question(literature_anchors=[{"ref": "cite:a"}]), "opus")
    assert plan.source_refs == ["cite:a"]


def test_plan_report_partitions_by_decision_and_kind() -> None:
    blocks = parse_report(
        """\
```yaml
candidate_id: k1
proposed_kind: question
title: One
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
```yaml
candidate_id: a1
proposed_kind: question
title: Two
decision: applied
```
```yaml
candidate_id: d1
proposed_kind: question
title: Three
decision: defer
```
```yaml
candidate_id: t1
proposed_kind: topic
title: Four
decision: keep
```
"""
    )
    plan = plan_report(blocks, "opus")
    assert [p.candidate_id for p in plan.to_create] == ["k1"]
    assert plan.skipped_applied == ["a1"]
    assert plan.skipped_other == ["d1"]
    assert plan.manual == [("t1", "topic")]


def test_plan_report_rejects_duplicate_ids() -> None:
    blocks = parse_report(
        "```yaml\ncandidate_id: dup\ndecision: drop\n```\n```yaml\ncandidate_id: dup\ndecision: drop\n```\n"
    )
    with pytest.raises(ApplyValidationError, match="duplicate"):
        plan_report(blocks, "opus")


def test_plan_report_rejects_unknown_decision() -> None:
    blocks = parse_report("```yaml\ncandidate_id: x\nproposed_kind: question\ndecision: maybe\n```\n")
    with pytest.raises(ApplyValidationError, match="decision"):
        plan_report(blocks, "opus")


def test_plan_report_rejects_unknown_kind() -> None:
    blocks = parse_report("```yaml\ncandidate_id: x\nproposed_kind: proverb\ndecision: keep\n```\n")
    with pytest.raises(ApplyValidationError, match="proposed_kind"):
        plan_report(blocks, "opus")


_WB_REPORT = """\
# Report

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
rationale: >
  A folded scalar that must be preserved
  exactly across two lines.
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-b
proposed_kind: hypothesis
title: Second
decision: keep
```
"""


def test_write_back_flips_decision_and_inserts_fields() -> None:
    out = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    assert "decision: applied\n" in out
    assert "applied_as: question-0007\n" in out
    assert "applied_at: 2026-07-04\n" in out
    # cand-b block untouched
    assert out.count("decision: keep") == 1


def test_write_back_preserves_everything_else() -> None:
    out = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    # The folded rationale and surrounding prose survive byte-for-byte.
    assert "  A folded scalar that must be preserved\n  exactly across two lines.\n" in out
    assert out.startswith("# Report\n")


_WB_REPORT_WITH_COMMENT = """\
# Report

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
decision: keep  # human note
```
"""


def test_write_back_preserves_decision_trailing_comment() -> None:
    out = write_back(_WB_REPORT_WITH_COMMENT, "cand-a", "question-0007", "2026-07-04")
    assert "decision: applied  # human note\n" in out
    assert "applied_as: question-0007\n" in out
    assert "applied_at: 2026-07-04\n" in out


def test_write_back_targets_correct_block_by_id() -> None:
    out = write_back(_WB_REPORT, "cand-b", "hypothesis-0003", "2026-07-04")
    # Only cand-b changed; cand-a still keep.
    a_block = out.split("candidate_id: cand-a")[1].split("```")[0]
    assert "decision: keep" in a_block
    b_block = out.split("candidate_id: cand-b")[1].split("```")[0]
    assert "decision: applied" in b_block
    assert "applied_as: hypothesis-0003" in b_block


def test_write_back_is_composable_across_two_candidates() -> None:
    once = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    twice = write_back(once, "cand-b", "hypothesis-0003", "2026-07-04")
    assert twice.count("decision: applied") == 2
    assert "applied_as: question-0007" in twice
    assert "applied_as: hypothesis-0003" in twice


def test_write_back_missing_candidate_raises() -> None:
    with pytest.raises(ApplyWriteBackError):
        write_back(_WB_REPORT, "cand-zzz", "x", "2026-07-04")
