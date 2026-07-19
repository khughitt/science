# science/tests/test_numeric_literal.py
from decimal import Decimal
import pytest
from science_tool.numeric_literal import parse_prose_literal

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
