# science/tests/test_numeric_literal.py
from decimal import Decimal
import pytest
from science_tool.numeric_literal import parse_prose_literal, compare_at_precision

@pytest.mark.parametrize("text,value,quantum,unit", [
    ("8",       Decimal("8"),    Decimal("1"),     None),
    ("7.94",    Decimal("7.94"), Decimal("0.01"),  None),
    ("-7.94×",  Decimal("-7.94"),Decimal("0.01"),  None),   # × dropped
    ("0.001",   Decimal("0.001"),Decimal("0.001"), None),
    ("1,234",   Decimal("1234"), Decimal("1"),     None),
    ("7.94e3",  Decimal("7940"), Decimal("10"),    None),
    ("58%",     Decimal("58"),   Decimal("1"),     "%"),
])
def test_accepts_single_scalar(text, value, quantum, unit):
    p = parse_prose_literal(text)
    assert p is not None
    assert p.value == value and p.quantum == quantum and p.unit == unit

@pytest.mark.parametrize("text", ["12/15", "3–5", "3-5", "7.94 7.95", "abc", "", "1.2.3"])
def test_rejects_non_scalar(text):
    assert parse_prose_literal(text) is None

def _c(text, artifact, tol=None):
    return compare_at_precision(parse_prose_literal(text), Decimal(str(artifact)), tol)

def test_open_interval_and_boundary():
    assert _c("7.94", "7.94312") == "verified"
    assert _c("8", "7.9449") == "verified"
    assert _c("7.94", "7.951") == "mismatch"
    assert _c("7.94", "7.945") == "unverifiable"      # exact boundary (midpoint)
    assert _c("7.94e3", "7943.1") == "verified"

def test_percent_is_unverifiable():
    assert _c("58%", "0.58") == "unverifiable"
    assert _c("58%", "58", Decimal("0.5")) == "unverifiable"   # tolerance can't rescue %

def test_tolerance_is_closed():
    assert _c("0.001", "0.0015", Decimal("0.0005")) == "verified"   # boundary included
    assert _c("0.001", "0.0016", Decimal("0.0005")) == "mismatch"
