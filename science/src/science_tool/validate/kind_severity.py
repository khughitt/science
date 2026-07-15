"""Severity for KIND-level rules. One authority, consulted by every emitter that grades a kind.

A kind joins `_CERTIFIED_KINDS` at the END of its D5 slice -- never before. An uncertified
instrument may not fail anyone's build.

THIS SET CERTIFIES THE KIND, NOT EVERY RULE ABOUT IT. `hypothesis` here means: all 18 roots are
pinned, render, and validate. It does NOT mean the corpus carries verdict BASES -- >=11 of the 15
migrating verdicts do not, so `verdict.missing-basis` has its OWN ratchet, on its OWN axis, and
stays WARN. Two independent facts; do not let one certify the other. Rule-level ratchets do not
call this function.

Why a severity function and not a table on each check: three kind-level emitters
(`<kind>.status-vocabulary`, `<kind>.dangling-lineage`, `<kind>.unbacked-inverse`) all grade the
same axis -- is this KIND's instrument certified? Encoding that in three places is three chances to
strand one, which is exactly what happened before this module existed: two emitters carried a
hard-coded WARN and a comment promising ERROR "in Task 12", and Task 12 would have flipped one and
forgotten the others. One function, called by all three, is the only shape that cannot strand a promise.
"""

from __future__ import annotations

from science_tool.validate.result import Severity

_CERTIFIED_KINDS: frozenset[str] = frozenset({"hypothesis"})


def severity_for_kind(kind: str) -> Severity:
    """ERROR only for a kind whose instrument is certified; WARN for every other kind.

    The `_CERTIFIED_KINDS` set and the `hygiene` gate tier advance together, one kind at a time --
    a kind-scoped rule name (`hypothesis.dangling-lineage`) is added to the tier in the SAME slice
    that adds the kind here. Severity without a tier fails nobody's build; a tier entry without the
    matching certification would gate an uncertified kind. Neither moves alone.
    """
    return Severity.ERROR if kind in _CERTIFIED_KINDS else Severity.WARN
