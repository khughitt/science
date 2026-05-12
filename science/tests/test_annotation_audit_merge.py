"""audit.py merge + ID-minting semantics."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.audit import (
    AuditFileReport,
    audit_file,
    merge_planned,
    mint_id,
)
from science_tool.annotation.lifecycle import mutate_status
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
)

NOW = datetime(2026, 5, 11, tzinfo=timezone.utc)


def _sel(exact: str) -> TextQuoteSelector:
    return TextQuoteSelector(exact=exact, prefix="", suffix="")


def _planned(
    *, source_name="lint:bare-author-year-v2026-05-11",
    exact="A claim sentence.",
    match_text="Brunton 2022",
    lifted_from=None,
) -> PlannedAnnotation:
    return PlannedAnnotation(
        target=SpecificResource(source="x.md", selector=_sel(exact)),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text=match_text,
        source_name=source_name,
        lifted_from=lifted_from,
    )


def test_merge_into_empty_sidecar() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    new_sc, written = merge_planned(sidecar, plans, actor="tester", now=NOW)
    assert len(written) == 1
    assert len(new_sc.annotations) == 1
    assert written[0].status is Status.OPEN
    assert written[0].creator == "tester"
    assert written[0].created == NOW
    assert written[0].content_hash is not None
    assert written[0].content_hash.startswith("sha256:")
    assert written[0].match_text == "Brunton 2022"


def test_clean_rerun_writes_zero_rows() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    sc1, _ = merge_planned(sidecar, plans, actor="tester", now=NOW)
    sc2, written = merge_planned(sc1, plans, actor="tester", now=NOW)
    assert written == []
    assert len(sc2.annotations) == 1


def test_status_mutated_row_preserved_across_rerun() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    sc1, written = merge_planned(sidecar, plans, actor="tester", now=NOW)
    acked = mutate_status(written[0], Status.ACK, actor="kh", now=NOW)
    sc_with_ack = Sidecar(
        annotations=(acked,) + sc1.annotations[1:],
    )
    sc2, new = merge_planned(sc_with_ack, plans, actor="tester", now=NOW)
    assert new == []
    assert sc2.annotations[0].status is Status.ACK


def test_superseded_predecessor_yields_dash_2_id() -> None:
    sidecar = Sidecar()
    plans = [_planned()]
    sc1, written = merge_planned(sidecar, plans, actor="tester", now=NOW)
    sup = mutate_status(written[0], Status.SUPERSEDED, actor="auto", now=NOW)
    sc_sup = Sidecar(annotations=(sup,))
    sc2, new = merge_planned(sc_sup, plans, actor="tester", now=NOW)
    assert len(new) == 1
    assert new[0].id.endswith("-2")
    assert len(sc2.annotations) == 2


def test_unrelated_collision_raises() -> None:
    """Force a collision by manually placing an unrelated row at base_id."""
    p = _planned()
    base_id = mint_id(Sidecar(), p, existing_by_id={})
    fake = Annotation(
        id=base_id,
        target=SpecificResource(
            source="other.md", selector=_sel("Different sentence."),
        ),
        bodies=(TextualBody(value="x"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="numeric-anchor",
        source="lint:numeric-anchor-v2026-05-11",
        status=Status.OPEN,
        creator="x",
        created=NOW,
        content_hash="sha256:00",
        match_text="42%",
    )
    sc = Sidecar(annotations=(fake,))
    with pytest.raises(IdCollisionError):
        merge_planned(sc, [p], actor="tester", now=NOW)


def test_planned_vs_planned_collision_within_call_raises() -> None:
    """Two planned rows with identical 4-tuple still dedupe; with same
    base_id but different 4-tuple should raise."""
    p1 = _planned(match_text="Brunton 2022")
    p2 = _planned(match_text="Brunton 2022")  # same 4-tuple → dedupes
    sc, written = merge_planned(Sidecar(), [p1, p2], actor="t", now=NOW)
    assert len(written) == 1


def test_mint_id_deterministic_on_4_tuple() -> None:
    p_a = _planned(match_text="Brunton 2022")
    p_b = _planned(match_text="Brunton 2022")
    assert mint_id(Sidecar(), p_a, existing_by_id={}) == mint_id(Sidecar(), p_b, existing_by_id={})


def test_single_source_invariant_enforced() -> None:
    p1 = _planned(source_name="lint:bare-author-year-v2026-05-11")
    p2 = _planned(source_name="lint:numeric-anchor-v2026-05-11")
    with pytest.raises(ValueError, match="single-source"):
        merge_planned(Sidecar(), [p1, p2], actor="t", now=NOW)


def test_content_hash_uses_target_exact_and_source_name() -> None:
    from science_tool.annotation.hash import content_hash
    p = _planned(exact="A claim sentence.")
    sc, written = merge_planned(Sidecar(), [p], actor="t", now=NOW)
    expected = content_hash("A claim sentence.", p.source_name)
    assert written[0].content_hash == expected


def test_audit_file_writes_sidecar_per_source(tmp_path: Path) -> None:
    """audit_file merges per source sequentially; both rows persisted."""
    md = tmp_path / "x.md"
    md.write_text("Sentence with [UNVERIFIED] inline.\n")
    sidecar = tmp_path / "x.anno.trig"
    from science_tool.annotation.sources import SOURCES
    report = audit_file(
        md, sidecar,
        sources=[SOURCES["marker-token"]],
        actor="tester",
        now=NOW,
    )
    assert isinstance(report, AuditFileReport)
    assert sidecar.exists()
    assert report.rows_written == 1
