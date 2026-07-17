"""The absence predicate, shared by every layer that must not confuse absence with falsehood.

A leaf on purpose. Both `commons.overlay` (borrower composition) and `graph.identity_arbitration`
(contribution arbitration) must read absence the SAME way -- the graph layer already imports the
commons layer, so the one predicate they share cannot live in either.
"""

from __future__ import annotations


def is_unset(value: object) -> bool:
    """True when `value` is ABSENT, as a shape -- never as truthiness.

    `False`, `0`, and `0.0` are values an author wrote and an owner defends. Reading absence off
    truthiness (`if not value:`) silently reclassifies them as missing and lets a borrower
    overwrite an authored `False`, which is exactly the defect the superseded helper carried.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False
