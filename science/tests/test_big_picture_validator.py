from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.validator import (
    REFERENCE_PATTERN,
    _collect_project_ids,
    validate_rollup_file,
    validate_synthesis_file,
)

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    f = tmp_path / name
    f.write_text(body)
    return f


def test_flags_nonexistent_interpretation_id(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

The investigation began with interpretation:i99-does-not-exist.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE).rows
    assert any(i.kind == "nonexistent_reference" and "i99-does-not-exist" in i.message for i in issues)


def test_passes_when_all_references_exist(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

The investigation built on interpretation:i01-h1-q03.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE).rows
    assert not any(i.kind == "nonexistent_reference" for i in issues)


def test_rollup_orphan_count_mismatch(tmp_path: Path) -> None:
    rollup = _write(
        tmp_path,
        "synthesis.md",
        """---
kind: "synthesis-rollup"
orphan_question_count: 99
synthesized_from: []
---
""",
    )
    issues = validate_rollup_file(rollup, project_root=FIXTURE).rows
    # FIXTURE has one research orphan: q05-orphan (declared no aspects -> inherits
    # research). q06-software-pipeline-concern is software-only and does not count.
    assert any(i.kind == "orphan_count_mismatch" and "expected 1" in i.message for i in issues)


def test_rollup_orphan_count_matches(tmp_path: Path) -> None:
    rollup = _write(
        tmp_path,
        "synthesis.md",
        """---
kind: "synthesis-rollup"
orphan_question_count: 1
synthesized_from: []
---
""",
    )
    issues = validate_rollup_file(rollup, project_root=FIXTURE).rows
    assert not any(i.kind == "orphan_count_mismatch" for i in issues)


def test_thin_coverage_flagged_when_arc_is_long(tmp_path: Path) -> None:
    body = "word " * 400  # A long Arc section.
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        f"""---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "thin"
---

## State

Empty.

## Arc

{body}
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE).rows
    assert any(i.kind == "thin_coverage_marker_mismatch" for i in issues)


def test_thin_coverage_passes_when_arc_is_short(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "thin"
---

## Arc

Arc reconstruction is limited because no prior_interpretations chains exist.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE).rows
    assert not any(i.kind == "thin_coverage_marker_mismatch" for i in issues)


def test_collect_project_ids_harvests_aggregated_task_headings(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        """# Task queue

## [t082] PHF19 residualization
type: research
related: [question:q01]

## [t091] Cross-dataset replication
related: [question:q02]
""",
    )
    (tmp_path / "tasks" / "done").mkdir()
    (tmp_path / "tasks" / "done" / "2026-04.md").write_text(
        """## [t055] Longitudinal virtual FISH

Some notes.

## [t113] Shared covariate structure

More notes.
""",
    )
    ids = _collect_project_ids(tmp_path)
    assert {"task:t082", "task:t091", "task:t055", "task:t113"}.issubset(ids)


def test_aggregated_tasks_unblock_reference_validation(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t082] PHF19 residualization\n\nBody.\n",
    )
    synth = _write(
        tmp_path,
        "h1.md",
        """---
id: "synthesis:h1"
hypothesis: "hypothesis:h1"
provenance_coverage: "high"
---

## Arc

PHF19 residualization in task:t082 showed 93.8% coefficient retention.
""",
    )
    issues = validate_synthesis_file(synth, project_root=tmp_path).rows
    assert not any(i.kind == "nonexistent_reference" and "t082" in i.message for i in issues)


def test_orphan_count_excludes_software_only_questions() -> None:
    # Using the extended minimal_project fixture which now has q06 tagged
    # aspects: [software-development]. That question has no hypothesis
    # match, but should NOT count as a research orphan.
    from science_tool.big_picture.resolver import resolve_questions
    from science_tool.big_picture.validator import list_research_orphans

    resolved = resolve_questions(FIXTURE)
    q06 = resolved.get("question:q06-software-pipeline-concern")
    assert q06 is not None
    assert q06.primary_hypothesis is None

    result = list_research_orphans(resolved, project_root=FIXTURE)
    # FIXTURE's research orphans: q05-orphan (declared no aspects -> inherits
    # research). q06 should NOT count here.
    assert len(result.rows) == 1
    assert "question:q06-software-pipeline-concern" not in result.rows


def test_orphan_rows_and_count_cannot_drift() -> None:
    """The count IS the list. There is no second definition to drift from.

    A rollup once reported 40 orphans beside a hand-derived list of 31
    (fb-2026-07-11-014). That is only possible when two functions define the
    same predicate.
    """
    from science_tool.big_picture.resolver import resolve_questions
    from science_tool.big_picture.validator import list_research_orphans

    resolved = resolve_questions(FIXTURE)
    result = list_research_orphans(resolved, project_root=FIXTURE)

    assert result.status in {"ok", "empty"}
    assert result.rows == sorted(result.rows)
    assert all(resolved[qid].primary_hypothesis is None for qid in result.rows)


def test_count_research_orphans_is_gone() -> None:
    """The scalar counter is prohibited, not wrapped (fb-2026-07-11-014)."""
    import science_tool.big_picture.validator as validator

    assert not hasattr(validator, "count_research_orphans")


def test_synthesis_validation_is_unwired_when_no_project_ids(tmp_path: Path) -> None:
    """No entities/ and no tasks/ means the reference check has no corpus.

    Without this, known_ids is empty and EVERY reference in the file is reported as
    nonexistent -- a full sheet of false positives from a check that never ran.
    """
    synth = _write(
        tmp_path,
        "h1.md",
        '---\nid: "synthesis:h1"\n---\n\n## Arc\n\nWork in task:t082 and question:q01.\n',
    )
    result = validate_synthesis_file(synth, project_root=tmp_path)

    assert result.status == "unwired"
    assert result.code == "no_project_ids"
    # The whole point: it must NOT invent findings it did not earn.
    assert result.rows == []


def test_rollup_validation_is_unwired_when_frontmatter_unreadable(tmp_path: Path) -> None:
    """`read_frontmatter(path) or {}` rendered an unparseable rollup as clean."""
    rollup = tmp_path / "synthesis.md"
    rollup.write_text("no frontmatter here at all\n", encoding="utf-8")

    result = validate_rollup_file(rollup, project_root=tmp_path)

    assert result.status == "unwired"
    assert result.code == "frontmatter_unreadable"


def test_rollup_with_no_orphan_claim_is_empty_not_unwired(tmp_path: Path) -> None:
    """A parseable rollup that claims no count HAS been checked -- there was simply
    nothing to contradict. That is `empty`, not `unwired`."""
    rollup = _write(tmp_path, "synthesis.md", '---\nid: "synthesis:rollup"\n---\n\nBody.\n')

    result = validate_rollup_file(rollup, project_root=tmp_path)

    assert result.status == "empty"
    assert result.code == "no_orphan_claim"


def test_reference_pattern_matches_topic_refs() -> None:
    text = "See topic:ribosome-biogenesis for more."
    matches = [m.group(0) for m in REFERENCE_PATTERN.finditer(text)]
    assert "topic:ribosome-biogenesis" in matches


def test_collect_project_ids_includes_topic_entities() -> None:
    ids = _collect_project_ids(FIXTURE)
    assert "topic:t01-covered" in ids
    assert "topic:t04-paper-covered" in ids
