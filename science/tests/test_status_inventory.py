"""Certify the hypothesis lifecycle/verdict mapping (D5 Task 3). The instrument writes nothing.

The mapping INVERTS what every earlier revision of the design assumed: `phase` is the lifecycle
and `status` was only ever the verdict. `proposed`/`under-investigation` are not states — they say
"the evidence has not spoken", which is exactly what an ABSENT verdict already says.

60 of 147 real files carry `status: proposed` AND `phase: active` at once. Under the old reading
(`proposed → draft`, `active → active`) those two rules contradict each other on the largest cohort,
and 88 files would have been mis-migrated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.status_inventory import Adjudicated, inventory


def _hyp(root: Path, name: str, *, status: str | None, phase: str | None) -> None:
    directory = root / "entities" / "hypotheses"
    directory.mkdir(parents=True, exist_ok=True)
    lines = ["---", f'id: "hypothesis:{name}"', 'kind: "hypothesis"', 'title: "T"']
    if status is not None:
        lines.append(f'status: "{status}"')
    if phase is not None:
        lines.append(f'phase: "{phase}"')
    lines += ["---", "", "body"]
    (directory / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def test_phase_is_the_lifecycle_status_is_the_verdict(tmp_path: Path) -> None:
    # The 60-file cohort: both template defaults. `phase` owns the lifecycle, and `proposed`
    # means "the evidence has not spoken" -- which is ABSENCE, not `draft`.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")

    row = inventory(tmp_path).rows[0]

    assert (row.target_status, row.target_verdict, row.ambiguity) == ("active", None, None)


def test_absent_phase_defaults_to_active(tmp_path: Path) -> None:
    # 28 files. The template ships `phase: "active"`, so absence means the author never
    # touched it -- not that the hypothesis has no lifecycle.
    _hyp(tmp_path, "0002-b", status="proposed", phase=None)

    assert inventory(tmp_path).rows[0].target_status == "active"


def test_candidate_becomes_draft(tmp_path: Path) -> None:
    _hyp(tmp_path, "0003-c", status="proposed", phase="candidate")

    row = inventory(tmp_path).rows[0]

    assert (row.target_status, row.target_verdict) == ("draft", None)


def test_candidate_keeps_its_verdict(tmp_path: Path) -> None:
    # The axes are ORTHOGONAL: a candidate frame can already carry a verdict.
    _hyp(tmp_path, "0004-d", status="weakened", phase="candidate")

    row = inventory(tmp_path).rows[0]

    assert (row.target_status, row.target_verdict) == ("draft", "weakened")


@pytest.mark.parametrize("verdict", ["supported", "weakened", "partially-supported", "refuted"])
def test_every_verdict_word_survives_the_move(tmp_path: Path, verdict: str) -> None:
    _hyp(tmp_path, "0005-e", status=verdict, phase="active")

    row = inventory(tmp_path).rows[0]

    assert (row.target_status, row.target_verdict) == ("active", verdict)


def test_a_lifecycle_word_in_status_is_accepted_when_phase_agrees(tmp_path: Path) -> None:
    # 3 files author `status: active`. It carries no verdict, and `phase` says the same thing.
    _hyp(tmp_path, "0006-f", status="active", phase="active")

    row = inventory(tmp_path).rows[0]

    assert (row.target_status, row.target_verdict, row.ambiguity) == ("active", None, None)


def test_terminal_status_is_refused_not_guessed(tmp_path: Path) -> None:
    # natural-systems/0009 -- the file whose corruption opened this whole arc. A terminal word in
    # the collapsed field destroyed the lifecycle, the verdict AND the closure reason at once.
    _hyp(tmp_path, "0009-g", status="retired", phase="candidate")

    inv = inventory(tmp_path)

    assert inv.deterministic == []
    assert len(inv.ambiguous) == 1
    assert inv.ambiguous[0].target_status is None  # never guessed
    assert inv.ambiguous[0].target_verdict is None


def test_a_missing_status_is_refused(tmp_path: Path) -> None:
    _hyp(tmp_path, "0010-h", status=None, phase="active")

    inv = inventory(tmp_path)

    assert len(inv.ambiguous) == 1
    assert inv.ambiguous[0].target_status is None


def test_an_unknown_phase_is_refused(tmp_path: Path) -> None:
    _hyp(tmp_path, "0011-i", status="proposed", phase="speculative")

    inv = inventory(tmp_path)

    assert len(inv.ambiguous) == 1
    assert "speculative" in (inv.ambiguous[0].ambiguity or "")


def test_an_adjudication_lets_a_refused_file_through(tmp_path: Path) -> None:
    # THE escape from the refusal loop. Without an artifact, `_classify` re-reads the same terminal
    # status forever and 0009 can NEVER migrate, no matter what an author does to the file -- the
    # author's edit is indistinguishable from the corruption. Rev 1 shipped exactly that loop.
    _hyp(tmp_path, "0009-g", status="retired", phase="candidate")
    adjudication = {
        "hypothesis:0009-g": Adjudicated(
            status="retired", verdict="weakened", closure_basis="confirmatory null, z=-0.889"
        )
    }

    inv = inventory(tmp_path, adjudication=adjudication)

    assert inv.ambiguous == []
    row = inv.deterministic[0]
    assert (row.target_status, row.target_verdict) == ("retired", "weakened")
    assert row.target_closure_basis == "confirmatory null, z=-0.889"


def test_adjudication_for_an_unknown_id_is_an_error(tmp_path: Path) -> None:
    # Fail early. A typo'd id must not silently adjudicate nothing and leave the file refused.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")

    with pytest.raises(KeyError):
        inventory(tmp_path, adjudication={"hypothesis:9999-nope": Adjudicated(status="retired")})


def test_the_checked_in_canary_fixture_is_discharged_by_its_adjudication() -> None:
    """The toolkit's own missing-status fixture gets NO inference shortcut (ruled 2026-07-12).

    It is refused exactly as a real project's file would be, and escapes only via an explicit
    artifact. A classifier that special-cased test data would be an instrument certified against a
    corpus it cannot see.
    """
    from science_tool.status_inventory import load_adjudication

    root = Path(__file__).parent / "fixtures" / "commons_mm30_canary" / "project"

    assert inventory(root).ambiguous, "the canary must be REFUSED without an adjudication"

    inv = inventory(root, adjudication=load_adjudication(root / "hypothesis-adjudication.yaml"))

    assert inv.ambiguous == []
    row = inv.deterministic[0]
    assert (row.target_status, row.target_verdict) == ("draft", None)


def test_only_hypotheses_are_inventoried(tmp_path: Path) -> None:
    directory = tmp_path / "entities" / "questions"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "q.md").write_text(
        '---\nid: "question:0001-q"\nkind: "question"\ntitle: "T"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )

    assert inventory(tmp_path).rows == []
