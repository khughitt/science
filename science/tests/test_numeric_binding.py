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
