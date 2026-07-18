from science_tool.drift_sample.blind import blind_plan


def test_frontmatter_is_stripped_entirely():
    out = blind_plan("---\nkind: plan\nstatus: complete\nid: plan:1-x\n---\n\nbody text\n")
    assert "status" not in out
    assert "complete" not in out
    assert "body text" in out


def test_checked_boxes_are_normalized_to_unchecked():
    """62% of mm plans carry these; all-checked reads as `complete` to any reader."""
    out = blind_plan("---\nstatus: draft\n---\n\n- [x] did it\n- [X] also did it\n- [ ] not yet\n")
    assert "[x]" not in out and "[X]" not in out
    assert out.count("[ ]") == 3


def test_checkbox_text_survives_normalization():
    out = blind_plan("---\nstatus: draft\n---\n\n- [x] build `foo/bar.py`\n")
    assert "build `foo/bar.py`" in out


def test_progress_annotations_are_redacted():
    body = (
        "---\nstatus: draft\n---\n\n"
        "**Status:** SHIPPED -- merged to local main at `abc1234`.\n"
        "Design approved 2026-07-16.\n"
        "- [x] DONE: wire it up\n"
        "Everything works. ✅\n"
    )
    out = blind_plan(body)
    for leak in ("SHIPPED", "merged to local main", "approved", "DONE", "✅"):
        assert leak not in out, f"claim channel leaked: {leak}"


def test_ordinary_prose_is_not_redacted():
    """Over-redaction destroys the evidence the adjudicator needs."""
    out = blind_plan("---\nstatus: draft\n---\n\nAdd `src/foo.py` to complete the parser.\n")
    assert "`src/foo.py`" in out
    assert "parser" in out


def test_plan_without_frontmatter_is_returned_normalized():
    out = blind_plan("- [x] a thing\n")
    assert out.strip() == "- [ ] a thing"


def test_list_prefixed_status_banner_is_redacted():
    """`- **Status:** implemented` -- a banner behind a list marker (found in corpus)."""
    out = blind_plan("---\nstatus: draft\n---\n\n- **Status:** implemented (t700) all built\n")
    assert "implemented" not in out
    assert "built" not in out


def test_embedded_status_field_line_is_redacted():
    """Plans carry `status:` inside sub-entity/task YAML, not just top frontmatter."""
    out = blind_plan("---\nstatus: draft\n---\n\n- id: t1\n- status: done\n")
    assert "done" not in out
    out2 = blind_plan('---\nstatus: draft\n---\n\nsub:\n  status: "complete"\n')
    assert "complete" not in out2


def test_table_status_cell_is_redacted():
    """A verdict standing alone in a table cell is an authored claim: `| t466 | 0 | done |`."""
    out = blind_plan("---\nstatus: draft\n---\n\n| t466 | 0 | done |\n")
    assert "done" not in out
    adjacent = blind_plan("---\nstatus: draft\n---\n\n| a | done | complete |\n")
    assert "done" not in adjacent and "complete" not in adjacent


def test_deliverable_table_row_without_a_verdict_survives():
    """Over-redaction destroys evidence: a path/description table must pass through."""
    out = blind_plan("---\nstatus: draft\n---\n\n| `src/foo.py` | build the parser |\n")
    assert "`src/foo.py`" in out
    assert "parser" in out


def test_status_word_in_prose_without_colon_survives():
    """`status:` fields are redacted; the word `status` in prose is not."""
    out = blind_plan("---\nstatus: draft\n---\n\nThe review status of the parser is unclear.\n")
    assert "review status of the parser" in out
