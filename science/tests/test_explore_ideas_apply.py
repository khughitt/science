from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest
import yaml
from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.cli import main
from science_tool.entities import EntityCommandError
from science_tool.explore_ideas import (
    ApplyResult,
    ApplyValidationError,
    ApplyWriteBackError,
    CandidateBlock,
    GapReportResult,
    apply_report,
    build_create_plan,
    check_report,
    derive_lens_views,
    inspect_gaps_report,
    parse_report,
    plan_report,
    resolve_report_path,
    write_back,
)
from science_tool.resolve_refs import build_ref_index

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


def test_parse_report_malformed_yaml_names_candidate_and_file_line() -> None:
    # fb-2026-07-17-005: an unquoted colon deep in a 28-block report failed the
    # whole file with only a block-relative line/column and no candidate_id, so
    # the offending block could not be located. The error must name the
    # candidate_id and the file-relative line.
    text = (
        "# Exploration report\n\n"
        "intro paragraph\n\n"
        "```yaml\n"
        "candidate_id: cand-gradient\n"
        "decision: keep\n"
        "note: Foundational gradient evidence: Hadza sleep 5.7-7\n"
        "```\n"
    )
    with pytest.raises(ApplyValidationError) as excinfo:
        parse_report(text)
    message = str(excinfo.value)
    assert "cand-gradient" in message
    assert "line 6" in message  # the block's candidate_id line, file-relative


def test_resolve_report_path_direct_file(tmp_path: Path) -> None:
    report = tmp_path / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, str(report)) == report


def test_resolve_report_path_relative_file_anchored_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "doc" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    assert resolve_report_path(tmp_path, "doc/explorations/explore-2026-07-04.md") == report


def test_resolve_report_path_by_id(tmp_path: Path) -> None:
    d = tmp_path / "doc" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, "explore-2026-07-04") == report


def test_resolve_report_path_no_reprepend(tmp_path: Path) -> None:
    d = tmp_path / "doc" / "explorations"
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


_REF_ROWS = [{"id": "question:0037-m6a-proliferation-axis", "title": "Proliferation axis"}]

_RELATED_FIXTURE = """# Explore report

```yaml
candidate_id: cand-sharper
title: Sharper m6A question
proposed_kind: question
novelty_bucket: sharpens-existing
related_existing:
  - m6a
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""


def test_build_plan_canonicalizes_related_existing() -> None:
    idx = build_ref_index(_REF_ROWS)
    data = _keep_question(related_existing=["m6a"])
    plan = build_create_plan("cand-q", data, "opus", ref_index=idx)
    assert plan.related == ["question:0037-m6a-proliferation-axis"]


def test_build_plan_related_existing_must_be_list() -> None:
    idx = build_ref_index(_REF_ROWS)
    data = _keep_question(related_existing="m6a")
    with pytest.raises(ApplyValidationError, match="related_existing must be a list"):
        build_create_plan("cand-q", data, "opus", ref_index=idx)


def test_build_plan_related_existing_entries_must_be_strings() -> None:
    idx = build_ref_index(_REF_ROWS)
    data = _keep_question(related_existing=[123])
    with pytest.raises(ApplyValidationError, match="non-empty strings"):
        build_create_plan("cand-q", data, "opus", ref_index=idx)


def test_build_plan_unresolved_related_existing_fails() -> None:
    idx = build_ref_index(_REF_ROWS)
    data = _keep_question(related_existing=["no-such-thing"])
    with pytest.raises(ApplyValidationError, match="unresolved related_existing"):
        build_create_plan("cand-q", data, "opus", ref_index=idx)


def test_build_plan_related_existing_without_index_fails() -> None:
    data = _keep_question(related_existing=["m6a"])
    with pytest.raises(ApplyValidationError, match="without a project index"):
        build_create_plan("cand-q", data, "opus")


def test_apply_writes_related_edges(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0037-m6a-proliferation-axis.md",
        {
            "id": "question:0037-m6a-proliferation-axis",
            "kind": "question",
            "title": "Proliferation axis",
            "status": "open",
            "created": "2026-07-01",
            "updated": "2026-07-01",
        },
        "Body.\n",
    )
    report = tmp_path / "doc" / "explorations" / "explore-2026-07-04.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_RELATED_FIXTURE, encoding="utf-8")

    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    created = next((tmp_path / "entities" / "questions").glob("0*-sharper*.md"))
    fm = _frontmatter(created)
    assert "question:0037-m6a-proliferation-axis" in fm["related"]


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


@pytest.mark.parametrize("kind", [None, "proverb"])
def test_build_plan_rejects_invalid_proposed_kind(kind: object) -> None:
    data = _keep_question(proposed_kind=kind)
    with pytest.raises(ApplyValidationError):
        build_create_plan("cand-q", data, "opus")


@pytest.mark.parametrize("kind", ["topic", "theme"])
def test_build_plan_accepts_topic_and_theme(kind: str) -> None:
    data = _keep_question(proposed_kind=kind, title=f"A {kind}")

    plan = build_create_plan(f"cand-{kind}", data, "opus")

    assert plan.kind == kind
    assert plan.title == f"A {kind}"
    assert plan.origins == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]


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
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""
    )
    plan = plan_report(blocks, "opus")
    assert [p.candidate_id for p in plan.to_create] == ["k1", "t1"]
    assert [p.kind for p in plan.to_create] == ["question", "topic"]
    assert plan.skipped_applied == ["a1"]
    assert plan.skipped_other == ["d1"]
    assert plan.manual == []


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
    verification: verified
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
    verification: verified
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
    d = root / "doc" / "explorations"
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


def test_apply_report_seeds_body_from_candidate_material(tmp_path: Path) -> None:
    # fb-2026-07-11-022 / -17-011: apply must not discard the researched prose
    # the block already carries. The created entity starts non-hollow.
    from science_tool.explore_ideas import _body_has_substantive_text

    seed_project(tmp_path)
    _write_fixture(tmp_path)

    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    q_path = next((tmp_path / "entities" / "questions").glob("*.md"))
    _, _, body = q_path.read_text(encoding="utf-8")[4:].partition("\n---")
    assert "Does reduced vagal tone sustain systemic inflammation?" in body
    assert "chronic feedback failure" in body  # the lens rationale survives
    assert _body_has_substantive_text(body) is True


def test_gaps_flags_unseeded_scaffold_but_not_seeded_body(tmp_path: Path) -> None:
    # A keep block with no question_or_claim / rationale has nothing to seed, so
    # its body stays the untouched template -- which mixes HTML comments with
    # placeholder bullets. `gaps` must flag it (fb-2026-07-17-011), while the
    # seeded sibling (with real prose) must NOT be flagged.
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-2026-07-04.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        "```yaml\n"
        "candidate_id: cand-bare\n"
        "proposed_kind: question\n"
        "title: A bare candidate\n"
        "decision: keep\n"
        "origin_plan:\n"
        "  origins:\n"
        "    - type: assistant\n"
        "      ref: explore-ideas-mechanism\n"
        "```\n\n"
        "```yaml\n"
        "candidate_id: cand-seeded\n"
        "proposed_kind: question\n"
        "title: A seeded candidate\n"
        "question_or_claim: Does X drive Y in this system?\n"
        "lens: mechanism\n"
        "rationale: A concrete mechanistic framing worth recording.\n"
        "decision: keep\n"
        "origin_plan:\n"
        "  origins:\n"
        "    - type: assistant\n"
        "      ref: explore-ideas-mechanism\n"
        "```\n",
        encoding="utf-8",
    )

    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    result = inspect_gaps_report(tmp_path, "explore-2026-07-04")

    by_candidate = {
        row["candidate_id"]: [gap["code"] for gap in cast(list[dict[str, object]], row["gaps"])]
        for row in cast(list[dict[str, object]], result.to_dict()["entities"])
    }
    assert "empty_body" in by_candidate["cand-bare"]
    assert "empty_body" not in by_candidate["cand-seeded"]


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
        "decision_notes": [],
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
        "folds": [],
        "failures": [],
    }


def test_plan_report_records_fold_candidates() -> None:
    # fb-2026-07-17-004: a sharpens-existing candidate gets an honest disposition
    # -- recorded as a fold worklist entry, writing no entity.
    blocks = parse_report(
        "```yaml\n"
        "candidate_id: cand-sharpen\n"
        "proposed_kind: question\n"
        "title: Sharper framing of X\n"
        "decision: fold\n"
        "related_existing:\n"
        "  - question:0032-existing\n"
        "```\n"
    )
    plan = plan_report(blocks, "test-model", ref_index=None)

    assert plan.to_create == []
    assert plan.skipped_other == []
    assert [f.candidate_id for f in plan.folds] == ["cand-sharpen"]
    assert plan.folds[0].targets == ["question:0032-existing"]
    assert plan.folds[0].title == "Sharper framing of X"


def test_plan_report_fold_requires_related_existing() -> None:
    blocks = parse_report(
        "```yaml\ncandidate_id: cand-x\ndecision: fold\ntitle: T\n```\n"
    )
    with pytest.raises(ApplyValidationError, match="fold block.*related_existing"):
        plan_report(blocks, "test-model", ref_index=None)


def test_apply_report_surfaces_folds_without_writing(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-2026-07-04.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        "```yaml\n"
        "candidate_id: cand-sharpen\n"
        "proposed_kind: question\n"
        "title: Sharper framing of X\n"
        "decision: fold\n"
        "related_existing:\n"
        "  - question:0032-existing\n"
        "```\n",
        encoding="utf-8",
    )

    result = apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    assert result.created == []
    assert [f.candidate_id for f in result.folds] == ["cand-sharpen"]
    assert result.folds[0].targets == ["question:0032-existing"]
    # The fold block is not written back to `applied`; it stays a fold worklist item.
    assert "decision: fold" in report.read_text(encoding="utf-8")
    assert list((tmp_path / "entities" / "questions").glob("*.md")) == []


def test_inspect_gaps_report_clean_applied_entity(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)
    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))

    # Fill bodies so the newly-created scaffolds are no longer gap-only.
    for path in (tmp_path / "entities").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\nSubstantive follow-up note.\n", encoding="utf-8")

    result = inspect_gaps_report(tmp_path, "explore-2026-07-04")

    payload = result.to_dict()
    entities = cast(list[dict[str, object]], payload["entities"])
    assert payload["report"] == str(report)
    assert payload["counts"] == {"entities": 2, "gaps": 0, "errors": 0, "warnings": 0}
    assert [row["candidate_id"] for row in entities] == [
        "cand-mechanism-vagal-cytokine-loop",
        "cand-methodology-retest-drift-threshold",
    ]
    assert all(row["gaps"] == [] for row in entities)


def test_body_has_substantive_text_ignores_multiline_comment_scaffold() -> None:
    # fb-2026-07-17-009 / -11-022: a rendered entity scaffold is all headings +
    # HTML comments, but the guidance comments are MULTI-LINE. The check must
    # treat the whole comment span as non-content, not just its first line.
    from science_tool.explore_ideas import _body_has_substantive_text

    scaffold = (
        "# Vagal tone as a cytokine feedback regulator\n\n"
        "## Summary\n\n"
        "<!-- What is being asked and why it is important. -->\n\n"
        "## Why It Matters\n\n"
        "<!-- Bulleted list. Cover at least:\n"
        "- the decision this question affects\n"
        "- the risk if the question is left unanswered\n"
        "-->\n\n"
        "## Current Evidence\n\n"
        "<!-- Bulleted list. Cover at least:\n"
        "- supporting evidence\n"
        "- conflicting evidence\n"
        "-->\n"
    )
    assert _body_has_substantive_text(scaffold) is False


def test_body_has_substantive_text_detects_prose_outside_comments() -> None:
    from science_tool.explore_ideas import _body_has_substantive_text

    body = (
        "# Title\n\n## Summary\n\n"
        "<!-- What is being asked and why it is important. -->\n\n"
        "Reduced vagal tone sustains systemic inflammation in post-acute syndromes.\n"
    )
    assert _body_has_substantive_text(body) is True


def _gap_codes(result: GapReportResult) -> list[str]:
    entities = cast(list[dict[str, object]], result.to_dict()["entities"])
    return [
        str(gap["code"])
        for row in entities
        for gap in cast(list[dict[str, object]], row["gaps"])
    ]


def test_inspect_gaps_report_reports_missing_applied_as(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-missing.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("```yaml\ncandidate_id: cand-x\ndecision: applied\n```\n", encoding="utf-8")

    result = inspect_gaps_report(tmp_path, str(report))

    assert _gap_codes(result) == ["missing_applied_as"]
    assert result.counts == {"entities": 1, "gaps": 1, "errors": 1, "warnings": 0}


def test_inspect_gaps_report_reports_missing_entity(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-stale.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "```yaml\ncandidate_id: cand-x\ndecision: applied\napplied_as: question:no-such\n```\n",
        encoding="utf-8",
    )

    result = inspect_gaps_report(tmp_path, str(report))

    assert _gap_codes(result) == ["missing_entity"]


def test_inspect_gaps_report_reports_entity_gaps(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)
    apply_report(tmp_path, "explore-2026-07-04", "test-model", date(2026, 7, 4))
    text = report.read_text(encoding="utf-8").replace("ref: cite:chen2022", "ref: null")
    text = text.replace("related_existing: []", "related_existing:\n  - question:existing", 1)
    report.write_text(text, encoding="utf-8")
    q_path = next((tmp_path / "entities" / "questions").glob("*.md"))
    fm = _frontmatter(q_path)
    fm.pop("source_refs", None)
    fm.pop("related", None)
    body = "# Vagal tone as a cytokine feedback regulator\n\n## Summary\n\n\n## Notes\n"
    q_path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n" + body, encoding="utf-8")

    result = inspect_gaps_report(tmp_path, "explore-2026-07-04")

    entities = cast(list[dict[str, object]], result.to_dict()["entities"])
    first_row_gaps = cast(list[dict[str, object]], entities[0]["gaps"])
    first_codes = [gap["code"] for gap in first_row_gaps]
    assert first_codes == ["empty_body", "unresolved_anchors", "missing_related"]


def test_check_report_validates_without_writing(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)
    before = report.read_text(encoding="utf-8")

    result = check_report(tmp_path, "explore-2026-07-04", "test-model")

    assert result.report == report
    assert [p.candidate_id for p in result.to_create] == [
        "cand-mechanism-vagal-cytokine-loop",
        "cand-methodology-retest-drift-threshold",
    ]
    assert result.skipped_other == ["cand-contrarian-null-effect"]
    assert result.skipped_applied == []
    assert result.manual == []
    assert report.read_text(encoding="utf-8") == before
    assert not list((tmp_path / "entities" / "questions").glob("*.md"))
    assert not list((tmp_path / "entities" / "hypotheses").glob("*.md"))


def test_check_report_to_dict_shape(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_fixture(tmp_path)

    payload = check_report(tmp_path, "explore-2026-07-04", "test-model").to_dict()

    assert payload == {
        "report": str(report),
        "decision_notes": [],
        "to_create": [
            {
                "candidate_id": "cand-mechanism-vagal-cytokine-loop",
                "kind": "question",
                "title": "Vagal tone as a cytokine feedback regulator",
                "slug": None,
            },
            {
                "candidate_id": "cand-methodology-retest-drift-threshold",
                "kind": "hypothesis",
                "title": "Retest interval drives apparent measurement drift",
                "slug": None,
            },
        ],
        "skipped_applied": [],
        "skipped_other": ["cand-contrarian-null-effect"],
        "manual": [],
        "folds": [],
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
    d = root / "doc" / "explorations"
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
title: Topic candidate
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""


def _write_keep_topic(root: Path) -> Path:
    d = root / "doc" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text(_KEEP_TOPIC, encoding="utf-8")
    return report


def test_apply_report_continues_past_create_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_apply_report_fatal_writeback_names_entity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert "created cand-mechanism-vagal-cytokine-loop ->" in result.output
        assert "created cand-methodology-retest-drift-threshold ->" in result.output
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


def test_cli_apply_reports_fold_worklist() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        report = root / "doc" / "explorations" / "explore-2026-07-04.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "```yaml\n"
            "candidate_id: cand-sharpen\n"
            "proposed_kind: question\n"
            "title: Sharper framing of X\n"
            "decision: fold\n"
            "related_existing:\n"
            "  - question:0032-existing\n"
            "```\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "test-model"],
        )
        assert result.exit_code == 0, result.output
        assert "1 to fold manually" in result.output
        assert "fold manually: cand-sharpen -> question:0032-existing" in result.output
        assert not list((root / "entities" / "questions").glob("*.md"))


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


def test_cli_apply_check_text_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        report = _write_fixture(root)
        before = report.read_text(encoding="utf-8")
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "test-model", "--check"],
        )
        assert result.exit_code == 0, result.output
        assert "2 would create" in result.output
        assert "would create cand-mechanism-vagal-cytokine-loop (question)" in result.output
        assert "1 deferred/dropped" in result.output
        assert report.read_text(encoding="utf-8") == before
        assert not list((root / "entities" / "questions").glob("*.md"))
        assert not list((root / "entities" / "hypotheses").glob("*.md"))


def test_cli_apply_check_json_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        result = runner.invoke(
            main,
            [
                "explore-ideas",
                "apply",
                "--from",
                "explore-2026-07-04",
                "--model-id",
                "m",
                "--check",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert [row["candidate_id"] for row in payload["to_create"]] == [
            "cand-mechanism-vagal-cytokine-loop",
            "cand-methodology-retest-drift-threshold",
        ]
        assert payload["skipped_other"] == ["cand-contrarian-null-effect"]


def test_cli_apply_missing_report_errors() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        seed_project(Path.cwd())
        result = runner.invoke(main, ["explore-ideas", "apply", "--from", "nope", "--model-id", "m"])
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
        result = runner.invoke(main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"])
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


def _monkeypatch_many_preexisting_audit_failures(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    """Fake a large, unrelated pre-existing audit-failure backlog for `explore-ideas apply`.

    Same shape as `test_dataset_add_cli.py` / `test_entities_cli.py`: `create_entity`'s
    `_validate_prospective_write` call lives in `science_tool.entities`, so patching its
    `audit_project_sources` name surfaces the same pre-existing warnings on every entity
    `apply_report` creates in this run -- reproducing the O(created x preexisting) explosion
    the projector must collapse.
    """
    from science_tool.instruments import ValidationVerdict

    rows = [
        {
            "check": "unresolved_reference",
            "status": "fail",
            "source": f"question:{i:04d}-existing",
            "field": "related",
            "target": f"hypothesis:{i:04d}-missing",
            "details": "pre-existing missing hypothesis",
        }
        for i in range(count)
    ]

    def fake_audit_project_sources(sources: object) -> ValidationVerdict[dict[str, str]]:
        return ValidationVerdict.from_has_failures(rows, True)

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)


def test_cli_apply_summarizes_many_preexisting_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _monkeypatch_many_preexisting_audit_failures(monkeypatch, 400)

        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"],
        )

        assert result.exit_code == 0, result.output
        assert "2 created" in result.output
        assert "pre-existing audit failure:" not in result.output
        # One summary note per created entity (2 entities in the fixture).
        assert result.output.count("400 pre-existing project audit warning") == 2


def test_cli_apply_json_summarizes_many_preexisting_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _monkeypatch_many_preexisting_audit_failures(monkeypatch, 400)

        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--format", "json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload["created"]) == 2
        for created in payload["created"]:
            assert created["warnings"] == []
            assert "400 pre-existing project audit warning" in created["preexisting_warnings_note"]


def test_cli_apply_show_preexisting_lists_them(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        _write_fixture(root)
        _monkeypatch_many_preexisting_audit_failures(monkeypatch, 5)

        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--show-preexisting"],
        )

        assert result.exit_code == 0, result.output
        # 5 pre-existing warnings x 2 created entities, listed in full.
        assert result.output.count("pre-existing audit failure:") == 10


def test_cli_explore_ideas_gaps_text() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        report = root / "doc" / "explorations" / "explore-gaps.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("```yaml\ncandidate_id: cand-x\ndecision: applied\n```\n", encoding="utf-8")

        result = runner.invoke(main, ["explore-ideas", "gaps", "--from", "explore-gaps"])

        assert result.exit_code == 0, result.output
        assert "applied entities inspected" in result.output
        assert "missing_applied_as" in result.output


def test_cli_explore_ideas_gaps_json() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        report = root / "doc" / "explorations" / "explore-gaps.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("```yaml\ncandidate_id: cand-x\ndecision: applied\n```\n", encoding="utf-8")

        result = runner.invoke(main, ["explore-ideas", "gaps", "--from", "explore-gaps", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["counts"] == {"entities": 1, "gaps": 1, "errors": 1, "warnings": 0}


def test_cli_apply_check_includes_topic_in_to_create() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir="/tmp"):
        root = Path.cwd()
        seed_project(root)
        report = _write_keep_topic(root)
        before = report.read_text(encoding="utf-8")
        result = runner.invoke(
            main,
            ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m", "--check"],
        )
        assert result.exit_code == 0, result.output
        assert "1 would create" in result.output
        assert "would create cand-topic (topic)" in result.output
        assert "apply manually (" not in result.output
        assert report.read_text(encoding="utf-8") == before
        assert not list((root / "entities" / "topics").glob("*.md"))


def test_apply_report_creates_topic_and_writes_back(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_keep_topic(tmp_path)

    result = apply_report(tmp_path, str(report), "test-model", date(2026, 7, 6))

    assert result.manual == []
    assert [(created.candidate_id, created.kind) for created in result.created] == [("cand-topic", "topic")]
    created_path = result.created[0].path
    fm = _frontmatter(created_path)
    assert fm["kind"] == "topic"
    assert fm["title"] == "Topic candidate"
    assert fm["origins"] == [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    assert fm["added_by"] == "explore-ideas:test-model:cand-topic"
    assert "decision: applied" in report.read_text(encoding="utf-8")
    assert f"applied_as: {result.created[0].entity_id}" in report.read_text(encoding="utf-8")


def test_apply_report_creates_theme_and_writes_back(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-theme.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        """\
# Theme report

```yaml
candidate_id: cand-theme
proposed_kind: theme
title: Cross-cutting theme
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-contrast
```
""",
        encoding="utf-8",
    )

    result = apply_report(tmp_path, str(report), "test-model", date(2026, 7, 6))

    assert result.manual == []
    assert [(created.candidate_id, created.kind) for created in result.created] == [("cand-theme", "theme")]
    fm = _frontmatter(result.created[0].path)
    assert fm["kind"] == "theme"
    assert fm["title"] == "Cross-cutting theme"
    assert fm["theme_kind"] == "methodological"
    assert fm["theme_scope"] == "project"
    assert fm["origins"] == [{"type": "assistant", "ref": "explore-ideas-contrast"}]
    assert "decision: applied" in report.read_text(encoding="utf-8")


def test_cli_apply_translates_writeback_error_to_click_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args, **kwargs):
        raise ApplyWriteBackError("boom")

    monkeypatch.setattr("science_tool.explore_ideas_cli.apply_report", _boom)
    result = CliRunner().invoke(main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"])
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
    assert views == [{"lens": "mechanism", "rationale": "the framing", "origin_ref": "explore-ideas-mechanism"}]


def test_derive_lens_views_rejects_dangling_origin_ref() -> None:
    data = {"lens_views": [{"lens": "analogy", "rationale": "a", "origin_ref": "explore-ideas-analogy"}]}
    origins = [{"type": "assistant", "ref": "explore-ideas-mechanism"}]
    with pytest.raises(ApplyValidationError):
        derive_lens_views(data, origins, candidate_id="cand-x")


def test_apply_report_persists_multi_lens_origins_and_views(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-converged.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        """\
# Converged report

```yaml
candidate_id: cand-converged
proposed_kind: question
title: Shared idea
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
      independent: true
    - type: assistant
      ref: explore-ideas-contrarian
      independent: true
lens_views:
  - lens: mechanism
    rationale: Mechanism-first framing.
    origin_ref: explore-ideas-mechanism
  - lens: contrarian
    rationale: Contrarian framing.
    origin_ref: explore-ideas-contrarian
```
""",
        encoding="utf-8",
    )

    result = apply_report(tmp_path, str(report), "test-model", date(2026, 7, 6))

    fm = _frontmatter(result.created[0].path)
    assert fm["origins"] == [
        {"type": "assistant", "ref": "explore-ideas-mechanism", "independent": True},
        {"type": "assistant", "ref": "explore-ideas-contrarian", "independent": True},
    ]
    assert fm["lens_views"] == [
        {
            "lens": "mechanism",
            "rationale": "Mechanism-first framing.",
            "origin_ref": "explore-ideas-mechanism",
        },
        {
            "lens": "contrarian",
            "rationale": "Contrarian framing.",
            "origin_ref": "explore-ideas-contrarian",
        },
    ]


def test_build_create_plan_carries_lens_views() -> None:
    data = {
        "proposed_kind": "question",
        "title": "Vagal tone as a cytokine regulator",
        "lens": "mechanism",
        "rationale": "framing",
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    plan = build_create_plan("cand-x", data, "model-1")
    assert plan.lens_views == [{"lens": "mechanism", "rationale": "framing", "origin_ref": "explore-ideas-mechanism"}]


def test_build_create_plan_rejects_duplicate_lens() -> None:
    data = {
        "proposed_kind": "question",
        "title": "Vagal tone as a cytokine regulator",
        "lens_views": [
            {"lens": "mechanism", "rationale": "a", "origin_ref": "explore-ideas-mechanism"},
            {"lens": "mechanism", "rationale": "b"},
        ],
        "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-mechanism"}]},
    }
    with pytest.raises(ApplyValidationError, match="duplicate lens_views"):
        build_create_plan("cand-x", data, "model-1")


def test_build_create_plan_rejects_duplicate_origin_ref() -> None:
    data = {
        "proposed_kind": "question",
        "title": "Vagal tone as a cytokine regulator",
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


# fb-2026-07-25: a 13-block report applied 2 entities then failed the remaining
# 11 on "Title is too long to derive a safe id slug". Two defects: the block
# schema had no way to name a slug, so the report carried no recovery path; and
# the check ran per-entity at write time, so the run stranded half-applied and
# had to be hand-unwound. The slug is now decided at plan time, from the title
# alone, for every keep block before the first write.

_LONG_TITLE = (
    "Collaboration scale at which the single-owner graph model breaks down "
    "under concurrent authorship"
)

_LONG_TITLE_REPORT = f"""\
---
kind: meta
id: explore-2026-07-25
---

```yaml
candidate_id: cand-short
proposed_kind: question
title: A perfectly ordinary question title
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

```yaml
candidate_id: cand-long
proposed_kind: question
title: {_LONG_TITLE}
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-temporal
```
"""


def _write_report(root: Path, text: str, stem: str = "explore-2026-07-25") -> Path:
    directory = root / "doc" / "explorations"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / f"{stem}.md"
    report.write_text(text, encoding="utf-8")
    return report


def test_apply_rejects_untruncatable_title_before_writing_anything(tmp_path: Path) -> None:
    # The failing block is the SECOND one: a per-entity check would already have
    # written the first entity by the time it fired.
    seed_project(tmp_path)
    report = _write_report(tmp_path, _LONG_TITLE_REPORT)

    with pytest.raises(ApplyValidationError) as excinfo:
        apply_report(tmp_path, "explore-2026-07-25", "m", date(2026, 7, 25))

    message = str(excinfo.value)
    assert "cand-long" in message
    assert "concurrent-authorship" in message  # names the tail that would be lost
    assert "slug:" in message  # names the in-report recovery path
    # Nothing written, and the report is untouched -- no half-applied state to unwind.
    assert not list((tmp_path / "entities" / "questions").glob("*.md"))
    assert "decision: applied" not in report.read_text(encoding="utf-8")


def test_check_reports_untruncatable_title(tmp_path: Path) -> None:
    # --check runs the same planner, so the human sees the failure before apply.
    seed_project(tmp_path)
    _write_report(tmp_path, _LONG_TITLE_REPORT)

    with pytest.raises(ApplyValidationError, match="cand-long"):
        check_report(tmp_path, "explore-2026-07-25", "m")


def test_apply_honors_explicit_slug_in_candidate_block(tmp_path: Path) -> None:
    seed_project(tmp_path)
    report = _write_report(
        tmp_path,
        _LONG_TITLE_REPORT.replace(
            "      ref: explore-ideas-temporal\n",
            "      ref: explore-ideas-temporal\nslug: single-owner-graph-collaboration-scale\n",
        ),
    )

    result = apply_report(tmp_path, "explore-2026-07-25", "m", date(2026, 7, 25))

    assert result.failures == []
    long_block = next(c for c in result.created if c.candidate_id == "cand-long")
    assert long_block.entity_id.endswith("single-owner-graph-collaboration-scale")
    # The full title survives on the entity; only the id is shortened.
    assert _LONG_TITLE in long_block.path.read_text(encoding="utf-8")
    assert "applied_as: " + long_block.entity_id in report.read_text(encoding="utf-8")


def test_check_surfaces_planned_slug(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_report(
        tmp_path,
        _LONG_TITLE_REPORT.replace(
            "      ref: explore-ideas-temporal\n",
            "      ref: explore-ideas-temporal\nslug: single-owner-graph-collaboration-scale\n",
        ),
    )

    payload = cast(list[dict], check_report(tmp_path, "explore-2026-07-25", "m").to_dict()["to_create"])

    assert [row["slug"] for row in payload] == [None, "single-owner-graph-collaboration-scale"]


def test_apply_rejects_malformed_explicit_slug(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_report(
        tmp_path,
        _LONG_TITLE_REPORT.replace(
            "      ref: explore-ideas-temporal\n",
            "      ref: explore-ideas-temporal\nslug: Not A Valid Slug\n",
        ),
    )

    with pytest.raises(ApplyValidationError, match="Invalid slug"):
        apply_report(tmp_path, "explore-2026-07-25", "m", date(2026, 7, 25))

    assert not list((tmp_path / "entities" / "questions").glob("*.md"))


def test_apply_rejects_empty_explicit_slug(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_report(
        tmp_path,
        _LONG_TITLE_REPORT.replace(
            "      ref: explore-ideas-temporal\n",
            "      ref: explore-ideas-temporal\nslug: ''\n",
        ),
    )

    with pytest.raises(ApplyValidationError, match="non-empty string"):
        apply_report(tmp_path, "explore-2026-07-25", "m", date(2026, 7, 25))


def test_plan_report_collects_every_bad_title_in_one_pass(tmp_path: Path) -> None:
    # The point of planning up front: the human fixes all offending blocks in one
    # edit instead of discovering them one failed apply at a time.
    seed_project(tmp_path)
    text = _LONG_TITLE_REPORT.replace(
        "title: A perfectly ordinary question title",
        f"title: {_LONG_TITLE} in a second way",
    )
    _write_report(tmp_path, text)

    with pytest.raises(ApplyValidationError) as excinfo:
        check_report(tmp_path, "explore-2026-07-25", "m")

    message = str(excinfo.value)
    assert "cand-short" in message and "cand-long" in message


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
        result = runner.invoke(main, ["explore-ideas", "apply", "--from", "explore-2026-07-04", "--model-id", "m"])
        assert result.exit_code != 0
        assert "1 failed" in result.output or "FAILED" in result.output


def test_build_plan_rejects_unknown_verification_value() -> None:
    with pytest.raises(ApplyValidationError, match="verification"):
        build_create_plan(
            "cand-q",
            _keep_question(literature_anchors=[{"ref": "cite:a", "verification": "probably"}]),
            "opus",
        )


def test_build_plan_rejects_resolved_ref_marked_unverified() -> None:
    # The resolver sets `ref` and `verification: verified` together. A block
    # carrying a ref while claiming the identity is unconfirmed was hand-edited
    # into a state resolve-anchors cannot produce.
    with pytest.raises(ApplyValidationError, match="marked 'unverified'"):
        build_create_plan(
            "cand-q",
            _keep_question(literature_anchors=[{"ref": "cite:a", "verification": "unverified"}]),
            "opus",
        )


def test_build_plan_rejects_verified_claim_without_a_ref() -> None:
    # The symmetric half: nothing can be verified without having resolved to a
    # record, so `verified` with no ref launders an unchecked identifier.
    with pytest.raises(ApplyValidationError, match="carries no 'ref'"):
        build_create_plan(
            "cand-q",
            _keep_question(literature_anchors=[{"ref": None, "verification": "verified"}]),
            "opus",
        )


def test_build_plan_accepts_unverified_anchor_without_a_ref() -> None:
    # The common and correct case: a model-asserted identifier that resolved to
    # nothing, honestly marked. It contributes no source_ref.
    data = _keep_question(
        literature_anchors=[{"doi": "10.9999/nowhere", "ref": None, "verification": "unverified"}]
    )
    plan = build_create_plan("cand-q", data, "opus")
    assert plan.source_refs == []


def test_gaps_flags_anchors_carrying_no_verification_verdict(tmp_path: Path) -> None:
    # fb-2026-07-25-006: an unmarked anchor is indistinguishable on the page
    # from a confirmed one -- both merely lack a ref.
    from science_tool.explore_ideas import _unmarked_anchor_count

    assert _unmarked_anchor_count({"literature_anchors": [{"doi": "10.1/x"}]}) == 1
    assert _unmarked_anchor_count({"literature_anchors": [{"doi": "10.1/x", "verification": "unverified"}]}) == 0
    # An anchor with no identifier at all is not something resolve-anchors ever
    # reports on, so demanding a verdict for it would be unactionable noise.
    assert _unmarked_anchor_count({"literature_anchors": [{"note": "no identifier"}]}) == 0


def test_plan_report_collects_decision_notes(tmp_path: Path) -> None:
    # fb-2026-07-25-007: `decision: drop` is a bare token, so the reason a
    # candidate was rejected survived only in the conversation.
    seed_project(tmp_path)
    report = tmp_path / "doc" / "explorations" / "explore-2026-07-04.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        _FIXTURE.replace(
            "decision: drop",
            "decision: drop\ndecision_note: absorbed into the vagal-tone block; not independently individuated",
        ),
        encoding="utf-8",
    )

    result = check_report(tmp_path, "explore-2026-07-04", "test-model")

    assert result.decision_notes == [
        ("cand-contrarian-null-effect", "absorbed into the vagal-tone block; not independently individuated")
    ]
    assert result.to_dict()["decision_notes"] == [
        {
            "candidate_id": "cand-contrarian-null-effect",
            "note": "absorbed into the vagal-tone block; not independently individuated",
        }
    ]


def test_plan_report_rejects_empty_decision_note() -> None:
    from science_tool.explore_ideas import CandidateBlock, plan_report

    block = CandidateBlock(candidate_id="cand-x", data={**_keep_question(), "decision_note": "   "})
    with pytest.raises(ApplyValidationError, match="decision_note"):
        plan_report([block], "opus")


def test_decision_notes_are_capped_by_the_apply_projection() -> None:
    # Every growable list in the payload must be capped; a key added to the
    # payload but not to _GROWABLE_LIST_KEYS is silently unbounded.
    from science_tool.explore_ideas_projection import project_explore_ideas_apply

    payload = {"decision_notes": [{"candidate_id": f"c{i}", "note": "n"} for i in range(50)]}
    projected = project_explore_ideas_apply(payload, cap=40)
    assert len(projected["decision_notes"]) == 40
    assert projected["decision_notes_omitted"] == 10
