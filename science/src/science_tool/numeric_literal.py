"""Pure prose-numeric grammar and displayed-precision comparison (Part B)."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
import re

VERIFIED: Final = "verified"
MISMATCH: Final = "mismatch"
UNVERIFIABLE: Final = "unverifiable"

@dataclass(frozen=True)
class ParsedLiteral:
    value: Decimal
    quantum: Decimal
    unit: str | None

# Whole-token grammar. Optional sign, digits with optional thousands-commas OR
# plain digits, optional fraction, optional exponent, optional trailing ×/%.
_LITERAL_RE = re.compile(
    r"(?P<sign>[+-]?)"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<frac>\d+))?"
    r"(?:[eE](?P<exp>[+-]?\d+))?"
    r"(?P<unit>[×%]?)"
)

def parse_prose_literal(text: str) -> ParsedLiteral | None:
    m = _LITERAL_RE.fullmatch(text.strip())
    if m is None:
        return None
    int_part = m.group("int").replace(",", "")
    frac = m.group("frac") or ""
    exp = int(m.group("exp")) if m.group("exp") else 0
    unit_glyph = m.group("unit") or ""
    mantissa = Decimal(f"{m.group('sign')}{int_part}" + (f".{frac}" if frac else ""))
    value = mantissa * (Decimal(10) ** exp)
    quantum = Decimal(10) ** (exp - len(frac))
    unit = "%" if unit_glyph == "%" else None   # × is dropped
    return ParsedLiteral(value=value, quantum=quantum, unit=unit)

def compare_at_precision(parsed: ParsedLiteral, value: Decimal, tolerance: Decimal | None = None) -> str:
    if parsed.unit == "%":
        return UNVERIFIABLE            # scale normalization deferred; tolerance cannot bridge
    if tolerance is not None:
        return VERIFIED if abs(value - parsed.value) <= tolerance else MISMATCH
    half = parsed.quantum / 2
    lo, hi = parsed.value - half, parsed.value + half
    if value == lo or value == hi:
        return UNVERIFIABLE            # exact midpoint shared with adjacent display value
    return VERIFIED if lo < value < hi else MISMATCH
