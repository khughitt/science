from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.audit.record import (
    AuditFindingRecord,
    Occurrence,
    RecordError,
    Review,
    Transition,
    occurrence_key,
    review_id,
)
from science_model.audit.evidence import LocationEvidence, TextEvidence
from science_model.audit.subjects import EntitySubject
from science_model.correspondence import Correspondence

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
FID = "a" * 64


def _occurrence(**overrides) -> Occurrence:
    producer = overrides.pop("producer_id", "dataset_anomalies")
    ingestion = overrides.pop("ingestion_ref", "run:2026-07-27-curation-sweep-a3f1")
    base = dict(
        idempotency_key=occurrence_key(
            producer_id=producer, ingestion_ref=ingestion, finding_id=FID
        ),
        producer_id=producer,
        ingestion_ref=ingestion,
        observed_at=NOW,
        severity="warn",
        message="drifted",
        qualifiers={"field": "year", "note": "non-identity"},
        evidence=(),
    )
    return Occurrence(**{**base, **overrides})


def _review(**overrides) -> Review:
    kind = overrides.pop("reviewer_kind", "human")
    ref = overrides.pop("reviewer_ref", "keith")
    lens = overrides.pop("lens", None)
    run = overrides.pop("run_ref", "run:x")
    base = dict(
        review_id=review_id(
            reviewer_kind=kind, reviewer_ref=ref, lens=lens, run_ref=run, finding_id=FID
        ),
        reviewer_kind=kind,
        reviewer_ref=ref,
        lens=lens,
        run_ref=run,
        at=NOW,
        outcome="confirms",
        note="checked",
    )
    return Review(**{**base, **overrides})


def _agent_review(**overrides) -> Review:
    fields = dict(
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="instrument:review-v1",
        model="test-model",
        correspondence=Correspondence(status="verified"),
    )
    fields.update(overrides)
    return _review(**fields)


def _record(**overrides) -> AuditFindingRecord:
    base = dict(
        finding_id=FID,
        fingerprint_version=1,
        rule_id="dataset.cached-field-drift",
        subject=EntitySubject(ref="dataset:gtex-v8"),
        identity_qualifiers={"field": "year"},
        occurrences=[_occurrence()],
        reviews=[],
        transitions=[
            Transition(
                from_status=None,
                to_status="proposed",
                actor="ingest",
                at=NOW,
                reason="detected",
            )
        ],
        status="proposed",
    )
    return AuditFindingRecord(**{**base, **overrides})


def test_genesis_transition_is_required():
    with pytest.raises(ValidationError):
        _record(transitions=[])


def test_first_transition_must_come_from_none():
    with pytest.raises(ValidationError):
        _record(
            transitions=[
                Transition(
                    from_status="proposed",
                    to_status="confirmed",
                    actor="k",
                    at=NOW,
                    reason="r",
                )
            ]
        )


def test_status_is_derived_and_must_agree_with_the_log():
    with pytest.raises(ValidationError):
        _record(status="confirmed")


def test_transition_outside_the_graph_is_rejected():
    with pytest.raises(ValidationError):
        Transition(
            from_status="proposed",
            to_status="promoted",
            actor="k",
            at=NOW,
            reason="r",
            task_ref="task:1",
        )


def test_promoted_task_present_iff_status_is_promoted():
    genesis = Transition(
        from_status=None,
        to_status="proposed",
        actor="ingest",
        at=NOW,
        reason="detected",
    )
    confirm = Transition(
        from_status="proposed",
        to_status="confirmed",
        actor="k",
        at=NOW,
        reason="r",
    )
    promote = Transition(
        from_status="confirmed",
        to_status="promoted",
        actor="k",
        at=NOW,
        reason="r",
        task_ref="task:0042",
    )
    ok = _record(
        transitions=[genesis, confirm, promote],
        status="promoted",
        promoted_task="task:0042",
    )
    assert ok.promoted_task == "task:0042"
    with pytest.raises(ValidationError):
        _record(transitions=[genesis, confirm, promote], status="promoted")
    with pytest.raises(ValidationError):
        _record(promoted_task="task:0042")


def test_transition_to_promoted_requires_a_task_ref():
    genesis = Transition(
        from_status=None,
        to_status="proposed",
        actor="ingest",
        at=NOW,
        reason="detected",
    )
    with pytest.raises(ValidationError):
        Transition(
            from_status="confirmed",
            to_status="promoted",
            actor="k",
            at=NOW,
            reason="r",
        )
    with pytest.raises(ValidationError):
        Transition(
            from_status="proposed",
            to_status="confirmed",
            actor="k",
            at=NOW,
            reason="r",
            task_ref="task:1",
        )
    assert genesis.task_ref is None


def test_occurrence_carries_the_complete_qualifier_object():
    occ = _occurrence()
    assert set(occ.qualifiers) == {"field", "note"}


def test_occurrence_acceptance_key_is_optional():
    assert _occurrence().acceptance_key is None
    assert _occurrence(acceptance_key="b" * 32).acceptance_key == "b" * 32


def test_occurrence_key_is_stable_and_distinguishes_producers():
    a = occurrence_key(producer_id="p1", ingestion_ref="r1", finding_id=FID)
    assert a == occurrence_key(producer_id="p1", ingestion_ref="r1", finding_id=FID)
    assert a != occurrence_key(producer_id="p2", ingestion_ref="r1", finding_id=FID)


def test_occurrence_key_matches_the_independent_persisted_golden():
    # Oracle:
    # printf 'science.occurrence.v1\n%s\0%s\0%s' \
    #   'dataset_anomalies' 'run:résumé-β' \
    #   'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' | sha256sum
    assert occurrence_key(
        producer_id="dataset_anomalies",
        ingestion_ref="run:résumé-β",
        finding_id=FID,
    ) == "c89b7da3f53191cb6c108935d8fcd9d460e7401ab8498ef52aed09a2ebe8d2b4"


def test_review_id_includes_lens_so_two_lenses_do_not_collide():
    grounding = review_id(
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="grounding",
        run_ref="run:x",
        finding_id=FID,
    )
    coverage = review_id(
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="coverage",
        run_ref="run:x",
        finding_id=FID,
    )
    assert grounding != coverage
    assert grounding == review_id(
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="grounding",
        run_ref="run:x",
        finding_id=FID,
    )


def test_review_id_matches_the_independent_persisted_golden():
    # Oracle:
    # printf 'science.review.v1\n%s\0%s\0%s\0%s\0%s' \
    #   'agent' 'curation-sweep' 'grounding-β' 'run:résumé' \
    #   'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' | sha256sum
    assert review_id(
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="grounding-β",
        run_ref="run:résumé",
        finding_id=FID,
    ) == "dbe4266d101b03b1f75d9a64cf7c9856079ff19e892f1a669630081e85dc17db"


def test_a_nul_cannot_shift_the_boundary_between_occurrence_fields():
    """`\0` is the SEPARATOR, so it may not also be a value.

    Without this refusal the encoding is ambiguous: moving the NUL from the end of one
    component to the start of the next builds the identical byte string, so two
    different observations share one idempotency key -- the key that decides whether
    an arrival is a retry or a new occurrence. The digests are frozen against golden
    vectors, so the character is refused rather than the payload re-encoded.
    """
    with pytest.raises(RecordError, match="NUL"):
        occurrence_key(producer_id="a", ingestion_ref="b\0c", finding_id=FID)
    with pytest.raises(RecordError, match="NUL"):
        occurrence_key(producer_id="a\0b", ingestion_ref="c", finding_id=FID)


def test_a_nul_cannot_shift_the_boundary_between_review_fields():
    """The same ambiguity, in the five-component payload."""
    with pytest.raises(RecordError, match="NUL"):
        review_id(
            reviewer_kind="agent",
            reviewer_ref="r",
            lens="grounding\0run:x",
            run_ref="1",
            finding_id=FID,
        )
    with pytest.raises(RecordError, match="NUL"):
        review_id(
            reviewer_kind="agent",
            reviewer_ref="r",
            lens="grounding",
            run_ref="run:x\0" + "1",
            finding_id=FID,
        )


def test_the_models_refuse_the_nul_the_hashes_refuse():
    """A field the hash refuses must not be storable, or the check is unreachable.

    Rejecting only inside `occurrence_key`/`review_id` would leave a record able to
    carry a NUL in `producer_id` -- and `Occurrence` recomputes its own key, so the
    refusal would surface as a construction failure from inside a validator rather
    than as the field-level error it is.
    """
    # Built directly, not through `_occurrence`: that helper computes the key first,
    # so it would fail in `occurrence_key` and prove nothing about the field.
    for field in ("producer_id", "ingestion_ref"):
        kwargs = dict(
            idempotency_key="d" * 64,
            producer_id="p",
            ingestion_ref="r",
            observed_at=NOW,
            severity="warn",
            message="m",
            qualifiers={},
            evidence=(),
        )
        kwargs[field] = "a\0b"
        with pytest.raises(ValidationError, match="NUL"):
            Occurrence(**kwargs)
    for field in ("reviewer_ref", "lens", "run_ref"):
        kwargs = dict(
            review_id="c" * 64,
            reviewer_kind="agent",
            reviewer_ref="curation-sweep",
            lens="grounding",
            model="claude-opus-5",
            run_ref="run:x",
            at=NOW,
            outcome="confirms",
            note="checked",
        )
        kwargs[field] = "a\0b"
        with pytest.raises(ValidationError, match="NUL"):
            Review(**kwargs)


def test_agent_review_requires_lens_and_model():
    Review(
        review_id="c" * 64,
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="grounding",
        model="claude-opus-5",
        run_ref="run:x",
        at=NOW,
        outcome="confirms",
        note="checked",
        correspondence=Correspondence(status="verified"),
    )
    with pytest.raises(ValidationError):
        Review(
            review_id="c" * 64,
            reviewer_kind="agent",
            reviewer_ref="curation-sweep",
            model="claude-opus-5",
            run_ref="run:x",
            at=NOW,
            outcome="confirms",
            note="n",
        )
    with pytest.raises(ValidationError):
        Review(
            review_id="c" * 64,
            reviewer_kind="agent",
            reviewer_ref="curation-sweep",
            lens="grounding",
            run_ref="run:x",
            at=NOW,
            outcome="confirms",
            note="n",
        )


def test_human_review_needs_neither_lens_nor_model():
    Review(
        review_id="d" * 64,
        reviewer_kind="human",
        reviewer_ref="keith",
        run_ref="run:x",
        at=NOW,
        outcome="refutes",
        note="not real",
    )


def test_confirmation_count_is_derived_from_distinct_confirming_reviews():
    record = _record(
        reviews=[
            _review(reviewer_ref="keith", outcome="confirms"),
            _review(reviewer_ref="other", outcome="refutes"),
        ]
    )
    assert record.confirmation_count() == 1


def test_confirmation_count_excludes_an_unwired_agent_confirmation():
    review = _agent_review(
        evidence=(LocationEvidence(type="location", path="a.txt"),),
        correspondence=Correspondence(status="unwired", code="NO_EXPOSURE"),
    )
    assert _record(reviews=[review]).confirmation_count() == 0


def test_confirmation_count_excludes_a_vacuous_verified_agent_confirmation():
    assert _record(reviews=[_agent_review(evidence=())]).confirmation_count() == 0


def test_confirmation_count_excludes_a_mixed_evidence_agent_confirmation():
    review = _agent_review(
        evidence=(
            LocationEvidence(type="location", path="a.txt"),
            TextEvidence(type="text", text="prose is not a citation"),
        )
    )
    assert _record(reviews=[review]).confirmation_count() == 0


def test_idempotency_key_is_required_and_must_match_its_own_fields():
    with pytest.raises(ValidationError):
        Occurrence(
            producer_id="p",
            ingestion_ref="r",
            observed_at=NOW,
            severity="warn",
            message="m",
        )
    with pytest.raises(ValidationError):
        _record(occurrences=[_occurrence(idempotency_key="0" * 64)])


def test_duplicate_occurrence_keys_are_rejected():
    occ = _occurrence()
    with pytest.raises(ValidationError):
        _record(occurrences=[occ, occ])


def test_review_id_must_match_its_own_fields():
    with pytest.raises(ValidationError):
        _record(reviews=[_review().model_copy(update={"review_id": "0" * 64})])


def test_promoted_task_must_equal_the_promotion_transitions_task_ref():
    genesis = Transition(
        from_status=None,
        to_status="proposed",
        actor="ingest",
        at=NOW,
        reason="detected",
    )
    confirm = Transition(
        from_status="proposed",
        to_status="confirmed",
        actor="k",
        at=NOW,
        reason="r",
    )
    promote = Transition(
        from_status="confirmed",
        to_status="promoted",
        actor="k",
        at=NOW,
        reason="r",
        task_ref="task:0042",
    )
    with pytest.raises(ValidationError):
        _record(
            transitions=[genesis, confirm, promote],
            status="promoted",
            promoted_task="task:9999",
        )


def test_the_record_is_frozen():
    record = _record()
    with pytest.raises(ValidationError):
        record.status = "confirmed"


def test_appending_goes_through_validation():
    record = _record()
    grown = record.with_occurrence(_occurrence(ingestion_ref="ing:2"))
    assert len(grown.occurrences) == 2
    # A bad append is refused rather than silently stored, which model_copy would allow.
    with pytest.raises(ValidationError):
        record.with_occurrence(_occurrence(idempotency_key="0" * 64))


@pytest.mark.parametrize(
    "append",
    [
        lambda record: record.with_occurrence(
            _occurrence(ingestion_ref="ing:2").model_copy(
                update={"severity": "fatal"}
            )
        ),
        lambda record: record.with_review(
            _review().model_copy(update={"outcome": "invented"})
        ),
        lambda record: record.with_transition(
            Transition(
                from_status="proposed",
                to_status="confirmed",
                actor="k",
                at=NOW,
                reason="checked",
            ).model_copy(update={"actor": 123})
        ),
    ],
    ids=["occurrence", "review", "transition"],
)
def test_append_methods_revalidate_forged_nested_instances(append):
    with pytest.raises(ValidationError):
        append(_record())


def test_transition_append_normalizes_a_forged_naive_instant():
    transition = Transition(
        from_status="proposed",
        to_status="confirmed",
        actor="k",
        at=NOW,
        reason="checked",
    ).model_copy(update={"at": datetime(2026, 7, 27, 12, 0)})

    grown = _record().with_transition(transition)

    assert grown.transitions[-1].at.tzinfo is UTC


def test_current_severity_uses_each_producers_most_recent_ingestion():
    from datetime import timedelta

    later = NOW + timedelta(hours=1)
    record = _record(
        occurrences=[
            _occurrence(ingestion_ref="ing:1", severity="error"),
            _occurrence(ingestion_ref="ing:2", severity="warn", observed_at=later),
        ]
    )
    # The newer look from the same producer supersedes the older one.
    assert record.current_severity() == "warn"


def test_current_severity_takes_the_max_across_producers():
    record = _record(
        occurrences=[
            _occurrence(producer_id="a", severity="warn"),
            _occurrence(producer_id="b", severity="error"),
        ]
    )
    assert record.current_severity() == "error"


def test_identity_qualifiers_cannot_be_mutated_in_place():
    # `finding_id` is a digest OVER this mapping. If the mapping can change, the
    # digest silently stops describing the case it names.
    #
    # The two exception types are not a typo: `mappingproxy` refuses SUBSCRIPT
    # mutation with `TypeError` and simply does not HAVE the mutating dict methods,
    # so `.clear()` is an `AttributeError`. Both are asserted because both are ways
    # a caller reaches for.
    record = _record()
    with pytest.raises(TypeError):
        record.identity_qualifiers["field"] = "month"  # type: ignore[index]
    with pytest.raises(AttributeError):
        record.identity_qualifiers.clear()  # type: ignore[attr-defined]


def test_occurrence_qualifiers_cannot_be_mutated_in_place():
    occurrence = _record().occurrences[0]
    with pytest.raises(TypeError):
        occurrence.qualifiers["field"] = "month"  # type: ignore[index]


def test_occurrence_nested_qualifier_arrays_are_copied_and_immutable():
    source = {"metadata": {"tags": [["stable"]]}}
    occurrence = _occurrence(qualifiers=source)

    source["metadata"]["tags"][0].append("caller-added")

    with pytest.raises(TypeError):
        occurrence.qualifiers["metadata"]["tags"][0][0] = "mutated"
    assert occurrence.model_dump(mode="json")["qualifiers"] == {
        "metadata": {"tags": [["stable"]]}
    }


def test_record_nested_identity_qualifier_arrays_are_copied_and_immutable():
    source = {"tags": [["stable"]]}
    record = _record(
        identity_qualifiers=source,
        occurrences=[_occurrence(qualifiers={"tags": [["stable"]]})],
    )

    source["tags"][0].append("caller-added")

    with pytest.raises(TypeError):
        record.identity_qualifiers["tags"][0][0] = "mutated"
    assert record.model_dump(mode="json")["identity_qualifiers"] == {
        "tags": [["stable"]]
    }


def test_a_record_round_trips_through_a_plain_dict_dump():
    # The frozen mappings serialize as ordinary dicts, so re-validation -- which is
    # how `with_occurrence` appends -- works on the dumped form.
    record = _record()
    assert AuditFindingRecord.model_validate(record.model_dump(mode="json")) == record


def test_an_unimplemented_fingerprint_version_is_refused():
    # A stored v2 record's finding_id is a digest under rules this toolkit cannot
    # reproduce, so every derived check would be comparing against a scheme it does
    # not have. `int` would have accepted it and then silently mis-validated.
    with pytest.raises(ValidationError):
        _record(fingerprint_version=2)


def test_acceptance_key_must_have_the_same_shape_the_report_requires():
    with pytest.raises(ValidationError):
        _record(occurrences=[_occurrence(acceptance_key="not-a-key")])
    with pytest.raises(ValidationError):
        _record(occurrences=[_occurrence(acceptance_key="B" * 32)])  # uppercase
    _record(occurrences=[_occurrence(acceptance_key="b" * 32)])


def test_an_occurrence_must_agree_with_the_records_identity():
    # The record says this case is about `field: year`; the occurrence reports
    # `field: month`. That is a different finding filed under this one's digest.
    with pytest.raises(ValidationError, match="different findings"):
        _record(occurrences=[_occurrence(qualifiers={"field": "month"})])


def test_an_occurrence_may_not_omit_an_identity_qualifier():
    with pytest.raises(ValidationError, match="omits identity qualifier"):
        _record(occurrences=[_occurrence(qualifiers={"note": "no field at all"})])


def test_identity_agreement_compares_normalized_values():
    # U+00E9 and "e" + U+0301 are the same string after NFC, and the fingerprint
    # hashes the NFC form. Comparing raw would split one finding into two.
    record = _record(
        identity_qualifiers={"field": "année"},
        occurrences=[_occurrence(qualifiers={"field": "année"})],
    )
    assert record.status == "proposed"


def test_stored_identity_qualifier_copies_use_one_nfc_spelling():
    record = _record(
        identity_qualifiers={"field": "anne\u0301e"},
        occurrences=[_occurrence(qualifiers={"field": "anne\u0301e"})],
    )

    dumped = record.model_dump(mode="json")
    assert dumped["identity_qualifiers"] == {"field": "année"}
    assert dumped["occurrences"][0]["qualifiers"]["field"] == "année"


def test_occurrence_content_includes_observed_at():
    from datetime import timedelta

    from science_model.audit.record import canonical_occurrence_content

    first = _occurrence()
    later = _occurrence(observed_at=NOW + timedelta(seconds=1))
    # Same producer, same ingestion ref -- so the SAME idempotency key -- but a
    # different moment. If the content signature ignored `observed_at`, ingestion
    # would treat the second as an identical retry of the first.
    assert first.idempotency_key == later.idempotency_key
    assert canonical_occurrence_content(first) != canonical_occurrence_content(later)


def test_occurrence_content_distinguishes_absent_from_explicit_null_qualifiers():
    from science_model.audit.record import canonical_occurrence_content

    absent = _occurrence(qualifiers={"field": "year"})
    explicit_null = _occurrence(qualifiers={"field": "year", "note": None})

    assert absent.idempotency_key == explicit_null.idempotency_key
    assert canonical_occurrence_content(absent) != canonical_occurrence_content(
        explicit_null
    )
    assert '"note":null' in canonical_occurrence_content(explicit_null)


def test_current_severity_survives_a_mix_of_naive_and_aware_timestamps():
    # `current_severity()` compares `observed_at` with `>`, and Python raises
    # TypeError on a naive/aware pair. Frontmatter and JSON both round-trip through
    # parsers that may or may not attach a timezone, so the model cannot assume one
    # was attached -- it normalizes at validation instead.
    record = _record(
        occurrences=[
            _occurrence(ingestion_ref="r1", severity="error"),
            _occurrence(
                ingestion_ref="r2",
                severity="warn",
                observed_at=datetime(2026, 7, 27, 13, 0),  # NAIVE, and later
            ),
        ]
    )
    assert all(o.observed_at.tzinfo is not None for o in record.occurrences)
    assert record.current_severity() == "warn"


def test_a_tzinfo_without_an_offset_is_read_as_naive_utc(monkeypatch):
    import time
    from datetime import tzinfo

    class OffsetlessTimezone(tzinfo):
        def utcoffset(self, value):
            return None

    try:
        with monkeypatch.context() as environment:
            environment.setenv("TZ", "EST5")
            time.tzset()
            occurrence = _occurrence(
                observed_at=datetime(
                    2026,
                    7,
                    27,
                    12,
                    0,
                    tzinfo=OffsetlessTimezone(),
                )
            )
    finally:
        time.tzset()

    assert occurrence.observed_at == NOW
    assert occurrence.observed_at.tzinfo is UTC


def test_every_stored_moment_is_normalized_to_aware_utc():
    from datetime import timedelta, timezone

    record = _record(
        occurrences=[_occurrence(observed_at=datetime(2026, 7, 27, 12, 0))],
        transitions=[
            Transition(
                from_status=None,
                to_status="proposed",
                actor="ingest",
                at=datetime(
                    2026,
                    7,
                    27,
                    13,
                    0,
                    tzinfo=timezone(timedelta(hours=1)),
                ),
                reason="detected",
            )
        ],
    )
    assert record.occurrences[0].observed_at == NOW
    assert record.transitions[0].at == NOW


def test_occurrence_content_normalizes_the_instant_spelling():
    from datetime import timedelta, timezone

    from science_model.audit.record import canonical_occurrence_content

    # 13:00+01:00 is the same instant as 12:00Z. One instant, one signature.
    shifted = _occurrence(
        observed_at=datetime(
            2026,
            7,
            27,
            13,
            0,
            tzinfo=timezone(timedelta(hours=1)),
        )
    )
    assert canonical_occurrence_content(_occurrence()) == canonical_occurrence_content(
        shifted
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor", ""),
        ("actor", " "),
        ("actor", " keith"),
        ("reason", ""),
        ("reason", "\t"),
        ("reason", " checked"),
    ],
)
def test_transition_provenance_is_nonblank_and_not_silently_trimmed(field, value):
    kwargs = dict(
        from_status=None,
        to_status="proposed",
        actor="keith",
        at=NOW,
        reason="checked",
    )
    kwargs[field] = value
    with pytest.raises(ValidationError, match=field):
        Transition(**kwargs)


@pytest.mark.parametrize("task_ref", ["", " ", " task:t001", "task:t001 "])
def test_optional_transition_task_ref_is_nonblank_and_not_silently_trimmed(task_ref):
    with pytest.raises(ValidationError, match="task_ref"):
        Transition(
            from_status="confirmed",
            to_status="promoted",
            actor="keith",
            at=NOW,
            reason="confirmed defect",
            task_ref=task_ref,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reviewer_ref", ""),
        ("reviewer_ref", " "),
        ("reviewer_ref", " keith"),
        ("run_ref", ""),
        ("run_ref", "\t"),
        ("run_ref", " run:x"),
        ("note", ""),
        ("note", " "),
        ("note", " checked"),
        ("lens", ""),
        ("lens", " "),
        ("lens", " grounding"),
        ("model", ""),
        ("model", " "),
        ("model", " opus"),
    ],
)
def test_review_provenance_is_nonblank_and_not_silently_trimmed(field, value):
    kwargs = dict(
        review_id="c" * 64,
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="grounding",
        model="claude-opus-5",
        run_ref="run:x",
        at=NOW,
        outcome="confirms",
        note="checked",
    )
    kwargs[field] = value
    with pytest.raises(ValidationError, match=field):
        Review(**kwargs)


def test_authored_provenance_accepts_exact_nonblank_values():
    transition = Transition(
        from_status="confirmed",
        to_status="promoted",
        actor="keith",
        at=NOW,
        reason="confirmed defect",
        task_ref="task:t001",
    )
    review = Review(
        review_id="c" * 64,
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens="grounding",
        model="claude-opus-5",
        run_ref="run:x",
        at=NOW,
        outcome="confirms",
        note="checked",
        correspondence=Correspondence(status="verified"),
    )
    assert transition.actor == "keith"
    assert review.note == "checked"
