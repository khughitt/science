"""Phase 3c: core/decisions.md section parser."""

from __future__ import annotations

from science_tool.graph.decision_log import parse_decision_log

MM30_STYLE = """\
<!-- header comment -->

# Decisions

## D1. Z-score normalization before meta-analysis (2026-03-31)

**Date**: 2026-03-31
**Status**: active
**Decision**: z-score first.

**Why**: scale differences.

---

## D5. Layered rationale (2026-05-01)

- **Date:** 2026-05-01
- **Status:** active

Body line.

---

A horizontal rule inside the body:

---

Amendment (2026-05-02): later note.

---
"""

META_STYLE = """\
# Decisions

## D-001: Scaffold the meta-project

- **Date:** 2026-04-23
- **Status:** active

Why text.
"""


def test_parses_canonical_ids_from_both_heading_styles():
    idx = parse_decision_log(MM30_STYLE)
    assert set(idx.sections) == {"decision:D1", "decision:D5"}
    idx2 = parse_decision_log(META_STYLE)
    assert set(idx2.sections) == {"decision:D-001"}


def test_title_excludes_leading_id_token():
    idx = parse_decision_log(MM30_STYLE)
    assert idx.sections["decision:D1"].title == "Z-score normalization before meta-analysis (2026-03-31)"
    idx2 = parse_decision_log(META_STYLE)
    assert idx2.sections["decision:D-001"].title == "Scaffold the meta-project"


def test_extracts_date_and_status_from_both_label_forms():
    idx = parse_decision_log(MM30_STYLE)
    assert idx.sections["decision:D1"].date == "2026-03-31"  # **Date**: form
    assert idx.sections["decision:D1"].status == "active"
    assert idx.sections["decision:D5"].date == "2026-05-01"  # - **Date:** form
    assert idx.sections["decision:D5"].status == "active"


def test_body_preserves_internal_horizontal_rule_and_is_not_truncated():
    idx = parse_decision_log(MM30_STYLE)
    body = idx.sections["decision:D5"].body
    assert "Body line." in body
    assert "A horizontal rule inside the body:" in body
    assert "Amendment (2026-05-02): later note." in body
    # The metadata label lines stay verbatim in the body too.
    assert "**Date:**" in body


def test_missing_date_and_status_are_none():
    idx = parse_decision_log("## D9. No metadata here\n\nJust prose.\n")
    sec = idx.sections["decision:D9"]
    assert sec.date is None
    assert sec.status is None
    assert sec.local_id == "D9"


def test_status_superseded_by_normalizes_query_copy_but_preserves_body():
    idx = parse_decision_log("## D-001: Old choice\n\n- **Status:** superseded by D-002\n\nBody.\n")
    sec = idx.sections["decision:D-001"]
    assert sec.status == "superseded"
    assert "superseded by D-002" in sec.body
