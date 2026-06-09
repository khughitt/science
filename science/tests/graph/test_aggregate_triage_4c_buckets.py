# tests/graph/test_aggregate_triage_4c_buckets.py
from __future__ import annotations

from science_tool.graph.aggregate_triage import AggregateBucket, _bucket


def _b(kind, *, has_pei=False, self_sourced=True, source_path=None, has_real_owner=False):
    bucket, _evidence = _bucket(kind, source_path, has_real_owner, self_sourced, has_pei)
    return bucket


def test_curie_bearing_row_is_curie_external_ref() -> None:
    assert _b("protein", has_pei=True) is AggregateBucket.CURIE_EXTERNAL_REF
    assert _b("disease", has_pei=True) is AggregateBucket.CURIE_EXTERNAL_REF


def test_no_curie_biomedical_row_is_residual_ambiguous() -> None:
    assert _b("disease", has_pei=False) is AggregateBucket.AMBIGUOUS
    assert _b("drug", has_pei=False) is AggregateBucket.AMBIGUOUS


def test_bare_question_is_deferred() -> None:
    assert _b("question", has_pei=False) is AggregateBucket.QUESTION_DEFERRED


def test_bare_method_and_topic_are_coined() -> None:
    assert _b("method", has_pei=False) is AggregateBucket.COINED
    assert _b("topic", has_pei=False) is AggregateBucket.COINED


def test_shadow_still_wins_over_curie() -> None:
    # An id with a real owner is SHADOW regardless of a curie on the stub.
    assert _b("protein", has_pei=True, has_real_owner=True) is AggregateBucket.SHADOW


def test_existing_coinable_concept_still_coined() -> None:
    assert _b("concept", has_pei=False) is AggregateBucket.COINED
