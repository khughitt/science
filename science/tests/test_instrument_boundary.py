"""Instrument-result boundary guard (silent-instrument ruling).

Additive ratchet: a public helper in the instrument namespace must return
``InstrumentResult[...]``. It may not return a bare ``list``/``dict``/``int``,
nor the ``tuple[list[T], str | None]`` precursor form that two catalog helpers
grew independently before this type existed.

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

from science_tool.instruments import INSTRUMENT_MODULES

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

# Instruments not yet migrated. DRAINED TO EMPTY by the migration; test_migration_is_complete
# locks it there. An entry the guard would still flag means the migration is incomplete --
# NOT a carve-out to add.
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("benchmark_catalog.py", "benchmark_sources"),
        ("benchmark_catalog.py", "list_benchmarks"),
        ("big_picture/validator.py", "count_research_orphans"),
        ("big_picture/validator.py", "validate_rollup_file"),
        ("big_picture/validator.py", "validate_synthesis_file"),
        ("datasets_catalog.py", "list_datasets"),
        ("datasets_catalog.py", "reconcile_dataset_links"),
        ("graph/attention.py", "compute_attention_candidates"),
        ("graph/attention.py", "query_attention_ranked"),
        ("graph/attention.py", "query_attention_sample"),
        ("graph/health.py", "check_dataset_anomalies"),
        ("graph/health.py", "collect_agent_context_findings"),
        ("graph/health.py", "collect_identity_policy_findings"),
        ("graph/health.py", "collect_invalid_entity_aspects"),
        ("graph/health.py", "collect_legacy_task_type"),
        ("graph/health.py", "collect_lingering_tags"),
        ("graph/health.py", "collect_tooling_scaffold_findings"),
        ("graph/health.py", "collect_unregistered_ref_kinds"),
        ("graph/health.py", "collect_unresolved_refs"),
        ("graph/health.py", "collect_validation_findings"),
        ("graph/store/inquiry.py", "list_inquiries"),
        ("graph/store/inquiry.py", "list_inquiries_dataset"),
        ("graph/store/inquiry.py", "validate_inquiry"),
        ("graph/store/inquiry.py", "validate_inquiry_dataset"),
        ("graph/store/queries.py", "query_claims"),
        ("graph/store/queries.py", "query_evidence"),
        ("graph/store/queries.py", "query_neighborhood"),
        ("graph/store/summary.py", "query_coverage"),
        ("graph/store/summary.py", "query_dashboard_summary"),
        ("graph/store/summary.py", "query_gaps"),
        ("graph/store/summary.py", "query_inquiry_summary"),
        ("graph/store/summary.py", "query_neighborhood_summary"),
        ("graph/store/summary.py", "query_project_summary"),
        ("graph/store/summary.py", "query_question_summary"),
        ("graph/store/summary.py", "query_uncertainty"),
        ("graph/store/validation.py", "diff_graph_inputs"),
        ("graph/store/validation.py", "diff_graph_inputs_dataset"),
    }
)

# Pure/total helpers that live in the namespace but are NOT instruments. PERMANENT.
#
# The test, applied by reading all 46 bodies (docs/plans/2026-07-11-instrument-triage.md):
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
    """Match ``tuple[list[T], str | None]`` — the ad-hoc REASON channel, precisely.

    Deliberately NOT ``tuple[list[T], ...]``. The validator family returns
    ``tuple[list[...], bool]``, where the bool is ``has_failures`` — an independent
    pass/fail channel, not a reason string (validation.py computes it as
    ``any(row["status"] == "fail" ...)``, so it is NOT ``bool(rows)``). Sweeping
    those in would force them through a type whose ``status`` cannot carry them:
    for a validator, ``ok`` means "found rows", i.e. found PROBLEMS — orthogonal to
    pass/fail, not a synonym for it.
    """
    if not isinstance(node, ast.Subscript):
        return False
    if _annotation_root(node) != "tuple":
        return False
    inner = node.slice
    if not isinstance(inner, ast.Tuple) or len(inner.elts) != 2:
        return False
    return _annotation_root(inner.elts[0]) == "list" and _is_str_or_none(inner.elts[1])


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


def test_instrument_namespace_returns_instrument_result() -> None:
    offenders: list[str] = []
    for module_rel in INSTRUMENT_MODULES:
        for fn in _violations(module_rel):
            if not _known(module_rel, fn):
                offenders.append(f'        ("{module_rel}", "{fn}"),')
    assert not offenders, (
        "These namespace helpers return a bare collection. Each is EITHER an\n"
        "instrument (-> migrate it to InstrumentResult, or park it in _ALLOWLIST)\n"
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
