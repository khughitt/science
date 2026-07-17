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
