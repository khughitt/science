"""Tests for `compile_workbench` (Task 5b).

`compile_workbench` is the only writer of proposition/evidence-line entities
from a workbench. It upserts a `PropositionEntity` per row (minting a
deterministic id for id-less rows and writing it back), lifts each inline
evidence stub to an `EvidenceLineEntity` (staging empirical-without-
dataset_usage as `belief_eligible=False`), and returns a `CompileResult`
exposing the compiled entities plus a NORMALIZED workbench where rows carry
their (minted) ids and stubs are replaced by evidence-line references.
"""

from __future__ import annotations

from pathlib import Path

from science_model.entities import EvidenceLineEntity
from science_model.frontmatter import parse_entity_file

from science_tool.dag.workbench import (
    CompileResult,
    EvidenceStub,
    WorkbenchFile,
    WorkbenchRow,
    compile_workbench,
)


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: compile-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# (i) id-less row -> deterministic minted proposition id + written entity file
# ---------------------------------------------------------------------------

def test_idless_row_mints_proposition_and_writes_file(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                claim_layer="causal_effect",
                identification_strength="observational",
                patch="patch-a",
            )
        ]
    )

    result = compile_workbench(wb, project_root=tmp_path)

    assert isinstance(result, CompileResult)
    assert len(result.propositions) == 1
    prop = result.propositions[0]
    assert prop.id is not None and prop.id.startswith("proposition:")

    # The normalized row carries the minted id written back.
    normalized_row = result.workbench.rows[0]
    assert normalized_row.id == prop.id

    # A PropositionEntity file exists under entities/propositions/ and parses.
    slug = prop.id.split(":", 1)[1]
    prop_path = tmp_path / "entities" / "propositions" / f"{slug}.md"
    assert prop_path.is_file()
    loaded = parse_entity_file(prop_path, "compile-test")
    assert loaded is not None
    assert loaded.id == prop.id
    assert loaded.kind == "proposition"

    # Authored axes mapped onto the entity.
    assert prop.subject == "gene:PHF19"
    assert prop.predicate == "affects"
    assert prop.object == "construct:proliferation"
    assert prop.polarity == "positive"
    assert prop.claim_layer == "causal_effect"
    assert prop.identification_strength == "observational"


def test_mint_is_deterministic(tmp_path: Path) -> None:
    """Same row compiled twice -> same minted id (idempotence precondition)."""
    _seed_project(tmp_path)

    def _row() -> WorkbenchRow:
        return WorkbenchRow(
            subject="gene:MYC",
            predicate="regulates",
            object="gene:CDK4",
            polarity="positive",
            patch="patch-a",
        )

    first = compile_workbench(WorkbenchFile(rows=[_row()]), project_root=tmp_path)
    second = compile_workbench(WorkbenchFile(rows=[_row()]), project_root=tmp_path)

    assert first.propositions[0].id == second.propositions[0].id
    assert first.workbench.rows[0].id == second.workbench.rows[0].id


def test_existing_id_is_preserved(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                id="proposition:my-explicit-id",
                subject="gene:A",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )
    result = compile_workbench(wb, project_root=tmp_path)
    assert result.propositions[0].id == "proposition:my-explicit-id"
    assert result.workbench.rows[0].id == "proposition:my-explicit-id"
    assert (tmp_path / "entities" / "propositions" / "my-explicit-id.md").is_file()


# ---------------------------------------------------------------------------
# (ii) inline evidence stub -> EvidenceLineEntity; normalized row holds a ref
# ---------------------------------------------------------------------------

def test_evidence_stub_lifts_to_entity_and_row_holds_reference(tmp_path: Path) -> None:
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

    result = compile_workbench(wb, project_root=tmp_path)

    assert len(result.evidence_lines) == 1
    ev = result.evidence_lines[0]
    assert isinstance(ev, EvidenceLineEntity)
    assert ev.stance == "supports"
    # target == the proposition id (edge-node IRI per Task 0).
    assert ev.target == result.propositions[0].id

    # The evidence-line entity file exists and parses.
    ev_slug = ev.id.split(":", 1)[1]
    ev_path = tmp_path / "entities" / "evidence-lines" / f"{ev_slug}.md"
    assert ev_path.is_file()
    loaded = parse_entity_file(ev_path, "compile-test")
    assert loaded is not None and loaded.id == ev.id
    assert isinstance(loaded, EvidenceLineEntity)
    assert loaded.stance == "supports"
    assert loaded.target == result.propositions[0].id

    # The normalized row at rest holds an evidence-line REFERENCE, not the stub.
    normalized_row = result.workbench.rows[0]
    assert ev.id in normalized_row.evidence
    # No inline EvidenceStub substance remains on the normalized row.
    assert all(not isinstance(item, EvidenceStub) for item in normalized_row.evidence)


# ---------------------------------------------------------------------------
# (iii) staging: empirical-without-dataset_usage -> belief_eligible=False
# ---------------------------------------------------------------------------

def test_empirical_without_dataset_usage_is_staged(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:A",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        stance="supports",
                        evidence_type="empirical_data_evidence",
                        # no dataset_usage -> staged
                    )
                ],
            )
        ]
    )
    result = compile_workbench(wb, project_root=tmp_path)
    assert result.evidence_lines[0].belief_eligible is False


def test_empirical_with_dataset_usage_is_belief_eligible(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:A",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        stance="supports",
                        evidence_type="empirical_data_evidence",
                        dataset_usage="dataset:gse100",
                    )
                ],
            )
        ]
    )
    result = compile_workbench(wb, project_root=tmp_path)
    assert result.evidence_lines[0].belief_eligible is True


def test_literature_evidence_is_belief_eligible(tmp_path: Path) -> None:
    """Non-empirical (literature) evidence is eligible even without dataset_usage."""
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:A",
                predicate="affects",
                object="construct:x",
                polarity="positive",
                patch="patch-a",
                evidence=[
                    EvidenceStub(stance="supports", evidence_type="literature_evidence"),
                ],
            )
        ]
    )
    result = compile_workbench(wb, project_root=tmp_path)
    assert result.evidence_lines[0].belief_eligible is True
