from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project
from science_tool.cli import main
from science_tool.entities import EntityCommandError
from science_tool.explore_ideas import (
    ApplyResult,
    ApplyValidationError,
    ApplyWriteBackError,
    CandidateBlock,
    apply_report,
    build_create_plan,
    derive_lens_views,
    parse_report,
    plan_report,
    resolve_report_path,
    write_back,
)

_REPORT = """\
---
kind: meta
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


def test_parse_report_accepts_crlf_fenced_yaml_blocks() -> None:
    blocks = parse_report("```yaml\r\ncandidate_id: cand-a\r\ndecision: drop\r\n```\r\n")
    assert len(blocks) == 1
    assert blocks[0].candidate_id == "cand-a"
    assert blocks[0].data["decision"] == "drop"


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


def test_write_back_same_candidate_is_idempotent() -> None:
    once = write_back(_WB_REPORT, "cand-a", "question-0007", "2026-07-04")
    twice = write_back(once, "cand-a", "question-0007", "2026-07-04")
    assert twice.count("applied_as: question-0007") == 1
    assert twice.count("applied_at: 2026-07-04") == 1
    assert twice.count("decision: applied") == 1


_WB_REPORT_WITHOUT_DECISION = """\
# Report

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
```
"""


def test_write_back_missing_decision_line_raises() -> None:
    with pytest.raises(ApplyWriteBackError):
        write_back(_WB_REPORT_WITHOUT_DECISION, "cand-a", "question-0007", "2026-07-04")


_WB_REPORT_WITH_NESTED_DECISION = """\
# Report

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
metadata:
  decision: keep
decision: keep
```
"""


def test_write_back_only_updates_top_level_decision() -> None:
    out = write_back(_WB_REPORT_WITH_NESTED_DECISION, "cand-a", "question-0007", "2026-07-04")
    assert "metadata:\n  decision: keep\n" in out
    assert "decision: applied\n" in out
    assert "applied_as: question-0007\n" in out
    assert "applied_at: 2026-07-04\n" in out


_WB_REPORT_INDENTED_BLOCK = """\
# Report

  Before the block.

  ```yaml
  candidate_id: cand-a
  proposed_kind: question
  title: First
  decision: keep
  ```

  After the block.
"""


def test_write_back_preserves_indented_block_prefix() -> None:
    out = write_back(_WB_REPORT_INDENTED_BLOCK, "cand-a", "question-0007", "2026-07-04")
    assert "  decision: applied\n" in out
    assert "  applied_as: question-0007\n" in out
    assert "  applied_at: 2026-07-04\n" in out
    assert "  Before the block.\n\n  ```yaml\n" in out
    assert "\n  After the block.\n" in out


_WB_REPORT_CRLF = (
    "# Report\r\n"
    "\r\n"
    "```yaml\r\n"
    "candidate_id: cand-a\r\n"
    "proposed_kind: question\r\n"
    "title: First\r\n"
    "decision: keep\r\n"
    "```\r\n"
)


def test_write_back_preserves_crlf_newlines() -> None:
    out = write_back(_WB_REPORT_CRLF, "cand-a", "question-0007", "2026-07-04")
    assert "\r\n" in out
    assert "\n" not in out.replace("\r\n", "")
    assert "decision: applied\r\n" in out
    assert "applied_as: question-0007\r\n" in out
    assert "applied_at: 2026-07-04\r\n" in out


_WB_REPORT_NO_TRAILING_NEWLINE = """\
# Report

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
decision: keep
```"""


def test_write_back_preserves_absence_of_trailing_newline() -> None:
    out = write_back(_WB_REPORT_NO_TRAILING_NEWLINE, "cand-a", "question-0007", "2026-07-04")
    assert not out.endswith("\n")
    assert out.endswith("```")


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


_FIXTURE = """\
---
kind: meta
id: explore-2026-07-04
title: Exploration report - 2026-07-04
created: 2026-07-04
---

# Exploration report - 2026-07-04

```yaml
candidate_id: cand-mechanism-vagal-cytokine-loop
proposed_kind: question
title: Vagal tone as a cytokine feedback regulator
question_or_claim: Does reduced vagal tone sustain systemic inflammation?
lens: mechanism
rationale: >
  Established in acute sepsis, under-explored as chronic feedback failure.
literature_anchors:
  - doi: 10.1000/chen2022-vagal
    title: Vagal afferents and cytokine feedback
    first_author: Chen
    year: 2022
    note: supports the feedback-loop framing
    ref: cite:chen2022
novelty_bucket: novel
related_existing: []
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-methodology-retest-drift-threshold
proposed_kind: hypothesis
title: Retest interval drives apparent measurement drift
question_or_claim: A fixed retest interval below the assay autocorrelation timescale manifests as spurious drift.
lens: methodology
rationale: >
  Reasoned independently before locating prior work making the same point.
literature_anchors:
  - doi: 10.1000/okafor2015-retest
    title: Autocorrelation timescales and apparent drift
    first_author: Okafor
    year: 2015
    date: 2015-03-12
    note: "predates: independently reasoned convergence"
    ref: cite:okafor2015
novelty_bucket: novel
related_existing: []
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-methodology
    - type: literature
      ref: cite:okafor2015
      independent: true
      date: 2015-03-12
```

```yaml
candidate_id: cand-contrarian-null-effect
proposed_kind: question
title: Is the effect fully explained by selection bias?
lens: contrarian
rationale: >
  Included to exercise the drop path.
literature_anchors: []
novelty_bucket: out-of-scope
related_existing: []
decision: drop
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-contrarian
```
"""


def _write_fixture(root: Path) -> Path:
    d = root / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text(_FIXTURE, encoding="utf-8")
    return report


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), text[:40]
    fm, _, _ = text[4:].partition("\n---")
    return yaml.safe_load(fm)


def test_apply_report_creates_kept_entities(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_fixture(tmp_path)

    result = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    assert isinstance(result, ApplyResult)
    assert len(result.created) == 2
    assert sorted(c.kind for c in result.created) == ["hypothesis", "question"]
    assert result.skipped_other == ["cand-contrarian-null-effect"]
    assert result.failures == []

    q_files = list((tmp_path / "entities" / "questions").glob("*.md"))
    h_files = list((tmp_path / "entities" / "hypotheses").glob("*.md"))
    assert len(q_files) == 1
    assert len(h_files) == 1


def test_apply_report_routes_origins_and_source_refs(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_fixture(tmp_path)

    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    q_fm = _frontmatter(next((tmp_path / "entities" / "questions").glob("*.md")))
    assert q_fm["source_refs"] == ["cite:chen2022"]
    assert all(o.get("ref") != "cite:chen2022" for o in q_fm.get("origins") or [])
    assert q_fm["added_by"] == "explore-ideas:test-model:cand-mechanism-vagal-cytokine-loop"

    h_fm = _frontmatter(next((tmp_path / "entities" / "hypotheses").glob("*.md")))
    lit = [o for o in h_fm["origins"] if o["type"] == "literature"]
    assert len(lit) == 1
    assert lit[0]["ref"] == "cite:okafor2015"
    assert lit[0]["independent"] is True
    assert str(lit[0]["date"]) == "2015-03-12"
    assert "cite:okafor2015" not in (h_fm.get("source_refs") or [])


def test_apply_report_writes_back_and_is_idempotent(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)

    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    text = report.read_text(encoding="utf-8")
    assert text.count("decision: applied") == 2
    assert "applied_at: 2026-07-04" in text
    assert text.count("decision: drop") == 1

    result2 = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    assert result2.created == []
    assert sorted(result2.skipped_applied) == [
        "cand-mechanism-vagal-cytokine-loop",
        "cand-methodology-retest-drift-threshold",
    ]
    assert len(list((tmp_path / "entities" / "questions").glob("*.md"))) == 1
    assert len(list((tmp_path / "entities" / "hypotheses").glob("*.md"))) == 1


def test_apply_report_to_dict_shape(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)

    result = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    payload = result.to_dict()

    assert payload == {
        "report": str(report),
        "created": [
            {
                "candidate_id": c.candidate_id,
                "entity_id": c.entity_id,
                "kind": c.kind,
                "path": str(c.path),
                "warnings": list(c.warnings),
            }
            for c in result.created
        ],
        "skipped_applied": [],
        "skipped_other": ["cand-contrarian-null-effect"],
        "manual": [],
        "failures": [],
    }


_TWO_KEEP = """\
---
kind: meta
id: explore-2026-07-04
---

```yaml
candidate_id: cand-good
proposed_kind: question
title: A well-formed question
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-bad
proposed_kind: question
title: Another question
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""


def _write_two_keep(root: Path) -> Path:
    d = root / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text(_TWO_KEEP, encoding="utf-8")
    return report


_KEEP_TOPIC = """\
---
kind: meta
id: explore-2026-07-04
---

```yaml
candidate_id: cand-topic
proposed_kind: topic
title: Manual routing candidate
decision: keep
```
"""


def _write_keep_topic(root: Path) -> Path:
    d = root / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text(_KEEP_TOPIC, encoding="utf-8")
    return report


def test_apply_report_continues_past_create_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    report = _write_two_keep(tmp_path)

    created_ids: list[str] = []
    real_apply_report = apply_report

    import science_tool.explore_ideas as mod

    real_create_entity = mod.create_entity

    def _patched_create_entity(*args, **kwargs):
        title = kwargs["title"]
        if title == "Another question":
            raise EntityCommandError("simulated create failure")
        result = real_create_entity(*args, **kwargs)
        created_ids.append(result.entity_id)
        return result

    monkeypatch.setattr(mod, "create_entity", _patched_create_entity)

    result = real_apply_report(tmp_path, "explore-2026-07-04", "m", date(2026, 7, 4))

    assert [c.candidate_id for c in result.created] == ["cand-good"]
    assert result.failures == [("cand-bad", "simulated create failure")]
    assert len(created_ids) == 1
    text = report.read_text(encoding="utf-8")
    good = text.split("candidate_id: cand-good")[1].split("```")[0]
    bad = text.split("candidate_id: cand-bad")[1].split("```")[0]
    assert "decision: applied" in good
    assert "decision: keep" in bad
    assert len(list((tmp_path / "entities" / "questions").glob("*.md"))) == 1


def test_apply_report_fatal_writeback_names_entity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    _write_fixture(tmp_path)

    import science_tool.explore_ideas as mod

    def _boom(*args, **kwargs):
        raise ApplyWriteBackError("simulated write-back failure")

    monkeypatch.setattr(mod, "write_back", _boom)

    with pytest.raises(ApplyWriteBackError) as excinfo:
        apply_report(tmp_path, "explore-2026-07-04", "m", date(2026, 7, 4))

    message = str(excinfo.value)
    assert "retry" in message.lower()
    assert "applied_as" in message
    assert list((tmp_path / "entities" / "questions").glob("*.md"))


def test_cli_apply_requires_from() -> None:
    result = CliRunner().invoke(main, ["explore-ideas", "apply", "--model-id", "m"])
    assert result.exit_code != 0
    assert "from" in result.output.lower()


def test_cli_apply_requires_model_id() -> None:
    result = CliRunner().invoke(main, ["explore-ideas", "apply", "--from", "explore-2026-07-04"])
    assert result.exit_code != 0
    assert "model-id" in result.output.lower()


def test_cli_apply_round_trip_text() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "test-model"],
        )
        assert result.exit_code == 0, result.output
        assert "2 created" in result.output
        assert (
            "created cand-mechanism-vagal-cytokine-loop ->" in result.output
        )
        assert (
            "created cand-methodology-retest-drift-threshold ->" in result.output
        )
        assert "skipped drop/defer: cand-contrarian-null-effect" in result.output
        assert len(list((root / "entities" / "questions").glob("*.md"))) == 1
        assert len(list((root / "entities" / "hypotheses").glob("*.md"))) == 1

        result2 = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "test-model"],
        )
        assert result2.exit_code == 0, result2.output
        assert "2 already applied" in result2.output
        assert "already applied: cand-mechanism-vagal-cytokine-loop" in result2.output
        assert "already applied: cand-methodology-retest-drift-threshold" in result2.output
        assert "skipped drop/defer: cand-contrarian-null-effect" in result2.output


def test_cli_apply_json_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload["created"]) == 2
        assert payload["skipped_other"] == ["cand-contrarian-null-effect"]


def test_cli_apply_missing_report_errors() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        seed_project(Path.cwd())
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "nope", "--model-id", "m"]
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


def _patch_create_with_warning(monkeypatch: pytest.MonkeyPatch, warning: str) -> None:
    import science_tool.explore_ideas as mod
    from science_tool.entities import EntityWriteResult

    real = mod.create_entity

    def _warned(*args, **kwargs):
        res = real(*args, **kwargs)
        return EntityWriteResult(entity_id=res.entity_id, path=res.path, warnings=[warning])

    monkeypatch.setattr(mod, "create_entity", _warned)


def test_cli_apply_emits_warnings_in_text(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _patch_create_with_warning(monkeypatch, "heads up: derived id truncated")
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"]
        )
        assert result.exit_code == 0, result.output
        assert "heads up: derived id truncated" in result.output


def test_cli_apply_json_stays_valid_with_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _patch_create_with_warning(monkeypatch, "w!")
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["created"][0]["warnings"] == ["w!"]


def test_cli_apply_emits_manual_detail_in_text() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_keep_topic(root)
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"]
        )
        assert result.exit_code == 0, result.output
        assert "1 to apply manually" in result.output
        assert "apply manually (topic): cand-topic" in result.output


def test_cli_apply_translates_writeback_error_to_click_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args, **kwargs):
        raise ApplyWriteBackError("boom")

    monkeypatch.setattr("science_tool.cli.apply_report", _boom)
    result = CliRunner().invoke(
        main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"]
    )
    assert result.exit_code != 0
    assert "boom" in result.output


def test_derive_lens_views_from_explicit_block() -> None:
    data = {
        "lens_views": [
            {"lens": "mechanism", "rationale": "m", "origin_ref": "explore-ideas-mechanism"},
            {"lens": "analogy", "rationale": "a", "origin_ref": "explore-ideas-analogy"},
        ],
    }
    origins = [
        {"type": "assistant", "ref": "explore-ideas-mechanism"},
        {"type": "assistant", "ref": "explore-ideas-analogy", "independent": True},
    ]
    views = derive_lens_views(data, origins)
    assert [v["lens"] for v in views] == ["mechanism", "analogy"]
    assert views[1]["origin_ref"] == "explore-ideas-analogy"


def test_derive_lens_views_synthesizes_from_legacy_single_lens() -> None:
    data = {"lens": "mechanism", "rationale": "the framing"}
    origins = [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    views = derive_lens_views(data, origins)
    assert views == [
        {"lens": "mechanism", "rationale": "the framing", "origin_ref": "explore-ideas-mechanism"}
    ]


def test_derive_lens_views_rejects_dangling_origin_ref() -> None:
    data = {"lens_views": [{"lens": "analogy", "rationale": "a", "origin_ref": "explore-ideas-analogy"}]}
    origins = [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    with pytest.raises(ApplyValidationError):
        derive_lens_views(data, origins, candidate_id="cand-x")


def test_build_create_plan_carries_lens_views() -> None:
    data = {
        "proposed_kind": "question",
        "title": "T",
        "lens": "mechanism",
        "rationale": "framing",
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    plan = build_create_plan("cand-x", data, "model-1")
    assert plan.lens_views == [
        {"lens": "mechanism", "rationale": "framing", "origin_ref": "explore-ideas-mechanism"}
    ]


def test_build_create_plan_rejects_duplicate_lens() -> None:
    data = {
        "proposed_kind": "question",
        "title": "T",
        "lens_views": [
            {"lens": "mechanism", "rationale": "a", "origin_ref": "explore-ideas-mechanism"},
            {"lens": "mechanism", "rationale": "b"},
        ],
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-x", data, "model-1")


def test_build_create_plan_rejects_duplicate_origin_ref() -> None:
    data = {
        "proposed_kind": "question",
        "title": "T",
        "lens": "mechanism",
        "rationale": "framing",
        "origin_plan": {
            "origins": [
                {"type": "assistant", "ref": "explore-ideas-mechanism"},
                {"type": "assistant", "ref": "explore-ideas-mechanism", "independent": True},
            ]
        },
    }
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-x", data, "model-1")


def test_cli_apply_nonzero_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_two_keep(root)

        import science_tool.explore_ideas as mod

        real_create_entity = mod.create_entity

        def _patched_create_entity(*args, **kwargs):
            if kwargs["title"] == "Another question":
                raise EntityCommandError("simulated create failure")
            return real_create_entity(*args, **kwargs)

        monkeypatch.setattr(mod, "create_entity", _patched_create_entity)
        result = runner.invoke(
            main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"]
        )
        assert result.exit_code != 0
        assert "1 failed" in result.output or "FAILED" in result.output
