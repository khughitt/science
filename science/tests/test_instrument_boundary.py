"""Instrument-result boundary guard (silent-instrument ruling).

Additive ratchet: a public helper in the instrument namespace must return
``InstrumentResult[...]`` or ``ValidationVerdict[...]``. It may not return a bare
``list``/``dict``/``int``, nor either ``tuple[list[T], bool]`` or
``tuple[list[T], str | None]`` precursor form.

The namespace is ``science_tool.instruments.INSTRUMENT_MODULES`` — imported, not
restated, so the guard and the migration query cannot drift.

Detection: a module-level ``def`` whose name does not start with ``_`` and whose
return annotation is a bare collection or the tuple precursor. Matched on the
ANNOTATION, structurally.

Known gap, stated rather than hidden: an un-annotated helper, or one annotated
``Any``, evades this guard. So does a helper that returns a bare collection from
a module outside INSTRUMENT_MODULES. This is a ratchet against the bare-collection
return that recurred across the tree, not a sandbox — the same class of limit the
output and durable-write guards document candidly.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from science_tool.instruments import INSTRUMENT_MODULES

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

# Instruments not yet migrated. DRAINED TO EMPTY by the migration; test_migration_is_complete
# locks it there. An entry the guard would still flag means the migration is incomplete --
# NOT a carve-out to add.
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()

# Pure/total helpers that live in the namespace but are NOT instruments. PERMANENT.
#
# The test, applied to every public body in INSTRUMENT_MODULES
# (docs/plans/2026-07-11-instrument-triage.md):
# does the helper do I/O, or resolve a user-supplied identifier? If NO -- it is a pure
# function of already-loaded arguments -- then an empty return is a fact about its INPUT,
# not a claim about the world, and a status surface would be ceremony without safety
# (the design's Non-goals).
#
# An entry here is a CLAIM that the function cannot be unwired. It is not a parking lot.
# If the claim is false, the entry is a bug -- not a carve-out. A deferred instrument goes
# in _DEFERRED_INSTRUMENTS, which blocks the closeout; it does NOT go here.
_NOT_INSTRUMENTS: frozenset[tuple[str, str]] = frozenset(
    {
        # Pure aggregation over rows the CALLER already fetched. Zero I/O. Always
        # returns all 6 facet keys (tasks is pre-seeded), so it is never even empty.
        # Its caller already holds the InstrumentResult from list_benchmarks.
        ("benchmark_catalog.py", "coverage_summary"),
        # Reads one key of a caller-supplied frontmatter dict. The dataset ref is
        # resolved LOUDLY upstream (cli.py:7245 exits 2 on a typo), so [] genuinely
        # means "this dataset records no consumers".
        ("datasets_catalog.py", "consumers_of"),
        # A RENDERER: its list is display *lines*, not findings. Always >= 6 lines.
        ("datasets_catalog.py", "format_show"),
        # Formats ONE candidate to a dict. Pure. Not a collection at all -- flagged
        # only because `dict` is in _BARE_COLLECTIONS, i.e. the detector being coarse.
        ("graph/attention.py", "format_attention_candidate"),
        # Pure sampler over a caller-supplied Sequence. No I/O. [] iff limit == 0 or
        # the input was empty -- a fact about the argument, not about the world.
        ("graph/attention.py", "reason_aware_sample_candidates"),
        ("graph/attention.py", "weighted_sample_without_replacement"),
        # Pure fold over a caller-supplied IdentityTable -> audit rows. Zero I/O; the only
        # caller is audit_project_sources internally. Empty rows == "no collisions in THIS
        # table", a fact about the argument, not the world. Surfaced only because migrate.py
        # joined the namespace.
        ("graph/migrate.py", "audit_identity_table"),
        # Pure fold over a caller-supplied error sequence -> audit rows. Zero I/O; the only
        # caller is audit_project_sources internally. Empty rows == "no conflicts in THIS
        # ledger", a fact about the argument. The unwiring risk lives at the CALL SITE, not
        # here, and test_identity_audit_entrypoints covers it end-to-end.
        ("graph/migrate.py", "audit_arbitration_errors"),
        # Takes NO ARGUMENTS. A projection over the module constant HEALTH_CHECKS.
        # It has no input that could be absent, and its return is never empty.
        ("graph/health.py", "list_health_checks"),
        # `return list(PREDICATE_REGISTRY)`. Same: a module constant, no input to lack.
        ("graph/store/validation.py", "query_predicates"),
    }
)

# Helpers that ARE instruments but are NOT migrated -- because the row-shaped type cannot
# express their shape or their payload.
#
# This set exists so that "deferred" can never be spelled "_NOT_INSTRUMENTS". That set's
# entries CLAIM a helper cannot be unwired; filing a known-broken instrument there would be
# a false statement in this guard's own vocabulary, and it would let test_migration_is_complete
# certify a completion it did not earn -- the exact bug this design exists to stop, committed
# by the mechanism built to prevent it. So an entry here is an ADMISSION OF INCOMPLETENESS,
# not an exoneration, and test_migration_is_complete asserts this set is EMPTY: a deferral
# BLOCKS the closeout until it is paid off or the design's completion criteria are explicitly
# amended. Silence is not an option the guard offers.
#
# It is empty today. The one candidate the plan anticipated -- benchmark_catalog.coverage_summary,
# a mapping the row-shaped type cannot carry -- turned out on reading to be PURE (it folds rows
# the caller already fetched), so it was never an instrument. See the triage doc.
_DEFERRED_INSTRUMENTS: frozenset[tuple[str, str]] = frozenset()

_BARE_COLLECTIONS = {"list", "dict", "int", "set"}


def _annotation_root(node: ast.expr) -> str | None:
    """Return the root name of an annotation: list[X] -> 'list', dict -> 'dict'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.value)
    return None


def _is_str_or_none(node: ast.expr) -> bool:
    """Match ``str | None`` (and ``Optional[str]``)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        sides = {ast.unparse(node.left), ast.unparse(node.right)}
        return sides == {"str", "None"}
    if isinstance(node, ast.Subscript) and _annotation_root(node) == "Optional":
        return ast.unparse(node.slice) == "str"
    return False


def _is_tuple_precursor(node: ast.expr) -> bool:
    """Match ``tuple[list[T], bool]`` and ``tuple[list[T], str | None]``.

    The former carries the has_failures verdict; the latter is the reason
    precursor. Both are pre-convergence shapes: the verdict now belongs in
    ``ValidationVerdict`` and the reason in ``InstrumentResult``. (Reversed from
    the earlier exclusion of the bool channel — the sibling type carries it now.)
    """
    if not isinstance(node, ast.Subscript):
        return False
    if _annotation_root(node) != "tuple":
        return False
    inner = node.slice
    if not isinstance(inner, ast.Tuple) or len(inner.elts) != 2:
        return False
    if _annotation_root(inner.elts[0]) != "list":
        return False
    second = inner.elts[1]
    return _is_str_or_none(second) or _annotation_root(second) == "bool"


@pytest.mark.parametrize(
    "annotation",
    [
        "tuple[list[dict[str, str]], bool]",
        "tuple[list[str], str | None]",
        "tuple[list[int], Optional[str]]",
    ],
)
def test_detector_flags_both_precursor_families(annotation: str) -> None:
    node = ast.parse(f"def f() -> {annotation}: ...").body[0]
    assert _is_tuple_precursor(node.returns) is True


def test_detector_ignores_verdict_and_instrument_returns() -> None:
    for annotation in (
        "ValidationVerdict[dict[str, str]]",
        "InstrumentResult[dict[str, str]]",
        "tuple[Graph, Graph]",
    ):
        node = ast.parse(f"def f() -> {annotation}: ...").body[0]
        assert _is_tuple_precursor(node.returns) is False


def test_new_modules_in_namespace() -> None:
    assert "graph/materialize.py" in INSTRUMENT_MODULES
    assert "graph/migrate.py" in INSTRUMENT_MODULES


def _violations(module_rel: str) -> list[str]:
    path = _SCIENCE_SRC / module_rel
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[str] = []
    for node in tree.body:  # module-level defs only
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        if node.returns is None:
            continue
        if _is_tuple_precursor(node.returns) or _annotation_root(node.returns) in _BARE_COLLECTIONS:
            bad.append(node.name)
    return bad


def _known(module_rel: str, fn: str) -> bool:
    return (module_rel, fn) in _ALLOWLIST | _NOT_INSTRUMENTS | _DEFERRED_INSTRUMENTS


def test_instrument_namespace_returns_canonical_result() -> None:
    offenders: list[str] = []
    for module_rel in INSTRUMENT_MODULES:
        for fn in _violations(module_rel):
            if not _known(module_rel, fn):
                offenders.append(f'        ("{module_rel}", "{fn}"),')
    assert not offenders, (
        "These namespace helpers return a bare collection. Each is EITHER an\n"
        "instrument (-> migrate it to InstrumentResult or ValidationVerdict, or park it "
        "in _ALLOWLIST)\n"
        "OR a pure/total helper that cannot be unwired (-> _NOT_INSTRUMENTS, with a\n"
        "justification). An empty list cannot say whether an instrument ran:\n"
        + "\n".join(sorted(offenders))
    )


def test_allowlist_has_no_stale_entries() -> None:
    """A listed helper that no longer violates must be REMOVED from its set.

    This is what forces the ratchet to drain instead of rotting.
    """
    stale = [
        f"{module_rel}::{fn}"
        for (module_rel, fn) in _ALLOWLIST | _NOT_INSTRUMENTS | _DEFERRED_INSTRUMENTS
        if fn not in _violations(module_rel)
    ]
    assert not stale, (
        "These helpers are listed but no longer violate the boundary. "
        "Delete them:\n  " + "\n  ".join(sorted(stale))
    )


def test_sets_are_disjoint() -> None:
    """A helper is an instrument, or it is not. It cannot be filed as both.

    _NOT_INSTRUMENTS asserts "cannot be unwired". _DEFERRED_INSTRUMENTS asserts
    "can be unwired, and still is". An entry in both is a contradiction on its face.
    """
    for a, b, names in (
        (_ALLOWLIST, _NOT_INSTRUMENTS, "_ALLOWLIST/_NOT_INSTRUMENTS"),
        (_ALLOWLIST, _DEFERRED_INSTRUMENTS, "_ALLOWLIST/_DEFERRED_INSTRUMENTS"),
        (_NOT_INSTRUMENTS, _DEFERRED_INSTRUMENTS, "_NOT_INSTRUMENTS/_DEFERRED_INSTRUMENTS"),
    ):
        assert not (a & b), f"{names} overlap: {sorted(a & b)}"


def test_migration_is_complete() -> None:
    """The migration is complete. A new entry in EITHER set is a regression.

    Per the convergence design: an allowlist entry the guard would still flag means the
    migration is incomplete -- NOT a carve-out to add.

    _DEFERRED_INSTRUMENTS is asserted empty for the same reason, and it is the more
    important of the two: a deferred entry is a KNOWN instrument that still lies to its
    callers. Draining _ALLOWLIST while _DEFERRED_INSTRUMENTS quietly held one would let
    this guard certify a completion it did not earn -- which is precisely the failure the
    whole design exists to stop, committed by the mechanism built to prevent it.
    """
    assert _ALLOWLIST == frozenset(), (
        "The instrument-result migration is finished. Do not re-open the allowlist; "
        "migrate the helper instead."
    )
    assert _DEFERRED_INSTRUMENTS == frozenset(), (
        "A known instrument is still unmigrated. This test is the intended blocker: either "
        "migrate it, or amend the design's completion criteria to bless the carve-out "
        "explicitly. Moving it to _NOT_INSTRUMENTS is NOT the fix -- that set means 'cannot "
        "be unwired', which would be a false claim about this helper."
    )
