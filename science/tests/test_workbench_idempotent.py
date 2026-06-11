"""Tests for `serialize_canonical` (Task 5c): canonical YAML serialization and fixed-point.

``serialize_canonical`` must produce DETERMINISTIC, CANONICAL text from a
``CompileResult`` such that:

    serialize(compile(serialize(compile(W)))) == serialize(compile(W))

i.e. re-parsing the serialized text into a ``WorkbenchFile``, re-compiling,
and re-serializing yields bit-identical output.

Additional invariants:
- Rows sorted by proposition id (stable).
- Evidence items appear as id references (strings), never inline stub bodies.
- Id-less input rows are assigned a minted id in the canonical output.
- No None/empty optional fields emitted (lean output).
- No layout/cosmetic fields (node positions etc.) in the output.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.dag.workbench import (
    EvidenceStub,
    WorkbenchFile,
    WorkbenchRow,
    compile_workbench,
    serialize_canonical,
)


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: idempotent-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# (i)  Fixed-point: serialize → re-parse → compile → serialize yields same text
# ---------------------------------------------------------------------------


def test_serialize_canonical_is_fixed_point(tmp_path: Path) -> None:
    """Round-trip via re-parse + re-compile must produce bit-identical text."""
    _seed_project(tmp_path)

    # Build a workbench with (a) an id-less row and (b) an inline evidence stub.
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                # (a) id-less — will be minted by compile
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                claim_layer="causal_effect",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        # (b) inline stub — will be lifted to a ref
                        stance="supports",
                        source="paper:Smith2025",
                        evidence_type="literature_evidence",
                    )
                ],
            ),
            WorkbenchRow(
                # second row — different triple, also id-less
                subject="gene:MYC",
                predicate="regulates",
                object="gene:CDK4",
                polarity="positive",
                patch="patch-a",
            ),
        ]
    )

    # --- first compile + serialize ---
    r1 = compile_workbench(wb, project_root=tmp_path)
    t1 = serialize_canonical(r1)

    # --- re-parse + second compile + serialize ---
    wb2 = WorkbenchFile.model_validate(yaml.safe_load(t1))
    r2 = compile_workbench(wb2, project_root=tmp_path)
    t2 = serialize_canonical(r2)

    assert t1 == t2, (
        "serialize_canonical is not a fixed point.\n"
        f"--- first ---\n{t1}\n--- second ---\n{t2}"
    )


# ---------------------------------------------------------------------------
# (ii)  Id-less row gets a minted id in the canonical output
# ---------------------------------------------------------------------------


def test_idless_row_carries_id_in_canonical_text(tmp_path: Path) -> None:
    _seed_project(tmp_path)

    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )
    r = compile_workbench(wb, project_root=tmp_path)
    text = serialize_canonical(r)

    parsed = yaml.safe_load(text)
    row_dict = parsed["rows"][0]
    assert "id" in row_dict
    assert row_dict["id"].startswith("proposition:")


# ---------------------------------------------------------------------------
# (iii)  Inline stubs become references in canonical output
# ---------------------------------------------------------------------------


def test_inline_stub_becomes_reference_in_canonical_text(tmp_path: Path) -> None:
    _seed_project(tmp_path)

    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        stance="supports",
                        source="paper:Smith2025",
                        evidence_type="literature_evidence",
                    )
                ],
            )
        ]
    )
    r = compile_workbench(wb, project_root=tmp_path)
    text = serialize_canonical(r)

    parsed = yaml.safe_load(text)
    row_dict = parsed["rows"][0]
    evidence = row_dict.get("evidence", [])
    assert len(evidence) == 1
    # Must be a bare string reference, not a mapping (stub body).
    assert isinstance(evidence[0], str)
    assert evidence[0].startswith("evidence-line:")


# ---------------------------------------------------------------------------
# (iv)  Rows sorted deterministically by proposition id
# ---------------------------------------------------------------------------


def test_rows_sorted_by_proposition_id(tmp_path: Path) -> None:
    _seed_project(tmp_path)

    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:ZZZ",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
            ),
            WorkbenchRow(
                subject="gene:AAA",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
            ),
        ]
    )
    r = compile_workbench(wb, project_root=tmp_path)
    text = serialize_canonical(r)

    parsed = yaml.safe_load(text)
    ids = [row["id"] for row in parsed["rows"]]
    assert ids == sorted(ids), f"Rows not sorted by id: {ids}"


# ---------------------------------------------------------------------------
# (v)  None / empty optional fields are omitted (lean output)
# ---------------------------------------------------------------------------


def test_none_fields_omitted_from_canonical_text(tmp_path: Path) -> None:
    _seed_project(tmp_path)

    # Row with no claim_layer, no identification_strength, etc.
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:A",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )
    r = compile_workbench(wb, project_root=tmp_path)
    text = serialize_canonical(r)

    # None-valued fields must not appear in the text.
    assert "claim_layer:" not in text
    assert "identification_strength:" not in text
    assert "epistemic_role:" not in text
    assert "legacy_relation_label:" not in text


# ---------------------------------------------------------------------------
# (vi)  serialize_canonical is a pure function (no file writes)
# ---------------------------------------------------------------------------


def test_serialize_canonical_does_not_write_files(tmp_path: Path) -> None:
    """serialize_canonical must be pure — it must not create or modify any files."""
    _seed_project(tmp_path)

    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:A",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )
    r = compile_workbench(wb, project_root=tmp_path)

    # Snapshot filesystem state BEFORE calling serialize_canonical.
    before = {p for p in tmp_path.rglob("*") if p.is_file()}

    serialize_canonical(r)

    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after, f"serialize_canonical wrote files: {after - before}"


# ---------------------------------------------------------------------------
# (vii)  CompileResult with no rows yields valid, round-trippable YAML
# ---------------------------------------------------------------------------


def test_empty_workbench_round_trips(tmp_path: Path) -> None:
    _seed_project(tmp_path)

    wb = WorkbenchFile(rows=[])
    r = compile_workbench(wb, project_root=tmp_path)
    t1 = serialize_canonical(r)

    wb2 = WorkbenchFile.model_validate(yaml.safe_load(t1) or {})
    r2 = compile_workbench(wb2, project_root=tmp_path)
    t2 = serialize_canonical(r2)

    assert t1 == t2
