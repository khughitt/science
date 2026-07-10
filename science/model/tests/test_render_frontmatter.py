from datetime import date, datetime

from science_model.frontmatter import (
    render_frontmatter,
    render_frontmatter_block,
    split_frontmatter,
)


def test_block_basic_shape():
    block = render_frontmatter_block({"id": "q:demo", "kind": "question"})
    assert block == 'id: q:demo\nkind: question\n'


def test_full_document_fences_and_body():
    doc = render_frontmatter({"id": "x"}, "hello body\n")
    assert doc == "---\nid: x\n---\nhello body\n"


def test_force_quotes_version_and_dates():
    block = render_frontmatter_block(
        {"version": "1.0.0", "created": "2026-07-10", "updated": "2026-07-10", "pin_version": "2.1"}
    )
    assert 'version: "1.0.0"' in block
    assert 'created: "2026-07-10"' in block
    assert 'updated: "2026-07-10"' in block
    assert 'pin_version: "2.1"' in block


def test_coerces_date_and_datetime_objects():
    block = render_frontmatter_block(
        {"created": date(2026, 7, 10), "updated": datetime(2026, 7, 10, 8, 30)}
    )
    assert 'created: "2026-07-10"' in block
    assert 'updated: "2026-07-10"' in block


def test_null_and_empty_force_quoted_values_left_unquoted():
    block = render_frontmatter_block({"version": None})
    # None dumps as `null`; the force-quoter leaves null/empty untouched
    assert "version: null" in block


def test_long_scalar_not_wrapped():
    long_value = "x" * 500
    block = render_frontmatter_block({"note": long_value})
    assert long_value in block  # width=10_000 prevents pyyaml wrapping


def test_allow_unicode_true():
    block = render_frontmatter_block({"title": "café"})
    assert "café" in block  # not \uXXXX-escaped


def test_idempotent_fixed_point():
    # Writer idempotence: render -> split -> render must be a fixed point.
    fields = {"id": "q:demo", "kind": "question", "created": "2026-07-10", "version": "1.0.0"}
    body = "Some body text.\n"
    t1 = render_frontmatter(fields, body)
    f2, b2 = split_frontmatter(t1)
    t2 = render_frontmatter(f2, b2)
    assert t1 == t2
