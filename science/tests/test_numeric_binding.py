# science/tests/test_numeric_binding.py
from decimal import Decimal
import pytest
from science_tool.numeric_binding import validate_entry, ParsedEntry, BindingError, PointerLocator, ColumnLocator, OpaqueLocator

def test_pointer_ok():
    e = validate_entry("b1", {"artifact": "r.json", "locator": {"pointer": "/a/0"}}, ".json")
    assert isinstance(e, ParsedEntry) and isinstance(e.locator, PointerLocator) and e.artifact == "r.json"
def test_column_where_ok():
    e = validate_entry("b1", {"artifact": "x.feather", "locator": {"column": "c", "where": {"d": "D1"}}}, ".feather")
    assert isinstance(e, ParsedEntry) and isinstance(e.locator, ColumnLocator) and e.locator.where == {"d": "D1"}
def test_opaque_ok_any_ext():
    e = validate_entry("b1", {"artifact": "f.png", "locator": {"opaque": "read off panel"}}, ".png")
    assert isinstance(e, ParsedEntry) and isinstance(e.locator, OpaqueLocator)
def test_tolerance_positive_finite():
    e = validate_entry("b1", {"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": 5e-4}, ".json")
    assert isinstance(e, ParsedEntry) and e.tolerance == Decimal("0.0005")

@pytest.mark.parametrize("raw,ext", [
    ("not-a-mapping", ".json"),                                                        # entry not a map
    ({"artifact": "r.json", "locator": {"pointer": "/a", "column": "c"}}, ".json"),    # two shapes
    ({"artifact": "r.json", "locator": {}}, ".json"),                                  # no shape
    ({"artifact": "r.json", "locator": {"pointer": ""}}, ".json"),                     # empty pointer
    ({"artifact": "x.feather", "locator": {"column": ""}}, ".feather"),                # empty column
    ({"artifact": "f.png", "locator": {"opaque": ""}}, ".png"),                        # empty opaque
    ({"artifact": "x.feather", "locator": {"column": "c", "where": {}}}, ".feather"),  # empty where
    ({"artifact": "r.json", "locator": {"pointer": "/a", "junk": 1}}, ".json"),        # locator extra field
    ({"artifact": "r.json", "locator": {"column": "c"}}, ".json"),                     # ext mismatch
    ({"artifact": "", "locator": {"pointer": "/a"}}, ".json"),                         # empty artifact
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "bogus": 1}, ".json"),       # entry extra field
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": -1}, ".json"),  # negative tol
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": 0}, ".json"),   # zero tol
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": float("nan")}, ".json"),  # NaN tol
    ({"artifact": "r.json", "locator": {"pointer": "/a"}, "tolerance": float("inf")}, ".json"),  # inf tol
    ({"artifact": "f.png", "locator": {"opaque": "x"}, "tolerance": 1}, ".png"),       # tol w/ opaque
    ({"locator": {"pointer": "/a"}}, ".json"),                                          # missing artifact
])
def test_rejects(raw, ext):
    assert isinstance(validate_entry("b1", raw, ext), BindingError)

from science_tool.numeric_provenance import build_document_context
from science_tool.numeric_binding import parse_claim_bindings

FM = "numeric_claims:\n  b1:\n    artifact: x.feather\n    locator: {column: c}"   # 4 lines
def _doc(tmp_path, body, fm=FM):
    p = tmp_path / "e.md"; p.write_text(f"---\n{fm}\n---\n{body}\n"); return build_document_context(p)

def test_attaches_and_pins_span(tmp_path):
    doc = _doc(tmp_path, "The value was **7.94×**[^b1] here.")
    binds, errs = parse_claim_bindings(doc)
    assert errs == [] and len(binds) == 1
    assert binds[0].value_text == "7.94×" and binds[0].span[0] == 7   # body is line 7

def test_opaque_still_requires_numeric_pin(tmp_path):
    fm = "numeric_claims:\n  b1:\n    artifact: f.png\n    locator: {opaque: read off panel}"
    ok = parse_claim_bindings(_doc(tmp_path, "peak near **2.1×**[^b1].", fm))
    assert ok[1] == [] and ok[0][0].value_text == "2.1×"
    bad = parse_claim_bindings(_doc(tmp_path, "effect visible[^b1].", fm))    # non-numeric pin
    assert bad[0] == [] and bad[1]

def test_ratio_before_marker_is_error(tmp_path):
    binds, errs = parse_claim_bindings(_doc(tmp_path, "ratio 12/15[^b1] no."))
    assert binds == [] and any("single" in e.message.lower() or "not a" in e.message.lower() for e in errs)

def test_orphan_and_duplicate_are_errors(tmp_path):
    assert parse_claim_bindings(_doc(tmp_path, "no marker here."))[1]           # orphan
    assert parse_claim_bindings(_doc(tmp_path, "a 1.0[^b1] b 2.0[^b1]."))[1]    # duplicate

def test_bad_id_charset_and_non_map(tmp_path):
    fm_bad_id = "numeric_claims:\n  \"b 1\":\n    artifact: x.feather\n    locator: {column: c}"
    assert parse_claim_bindings(_doc(tmp_path, "v 1.0[^b1].", fm_bad_id))[1]    # id has space
    fm_list = "numeric_claims:\n  - a\n  - b"
    assert parse_claim_bindings(_doc(tmp_path, "text.", fm_list))[1]            # not a mapping

def test_real_footnote_untouched(tmp_path):
    doc = _doc(tmp_path, "cited 3.0[^b1]. Unrelated[^x] note.")
    binds, errs = parse_claim_bindings(doc)
    assert len(binds) == 1 and errs == []      # [^x] ignored (not in map)

def test_no_numeric_char_before_marker_errors_not_crashes(tmp_path):
    # The char immediately before the marker ("n") is outside the numeric-ish
    # charset, so the token-extraction regex finds no match at all. This must
    # surface as a BindingError, never an AttributeError from a None match.
    doc = _doc(tmp_path, "result shown[^b1].")
    binds, errs = parse_claim_bindings(doc)
    assert binds == [] and len(errs) == 1 and isinstance(errs[0], BindingError)
