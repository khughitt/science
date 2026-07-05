"""End-to-end test: B2 dataset-independence payoff.

Covers the five assertions stated in plan Task 5a:

  1. Same-dataset collapse  — two empirical evidence-lines backed by the same
     dataset (role=analyzed, overlap=full) collapse to ONE contributing unit
     after materialize + B2 + reduce_units.
  2. Distinct-dataset independence — two lines on *different* datasets stay
     in separate independence groups (both contribute; no collapse).
  3. Unregistered-ref WARN — a dataset_usage ref pointing at a dataset that is
     not registered in the project yields dataset-influence.ref-unresolved.
  4. Dependence-role + unknown overlap WARN — a dependence-role entry with
     overlap=unknown (or omitted) yields dataset-influence.overlap-unknown-candidate.
  5. Task source in provenance only — a line whose `source` is `task:<id>`
     appears as prov:wasDerivedFrom in provenance and never as a cito edge.
     (This mirrors test_evidence_line_task_source_lands_in_provenance_not_belief
     in test_evidence_line_materialize.py; included here so the e2e covers the
     full story end-to-end.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _manifest(root: Path) -> None:
    _write(root, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")


def _prop_md(pid: str) -> str:
    return (
        "---\n"
        f"id: proposition:{pid}\n"
        "kind: proposition\n"
        f'title: "Proposition {pid}"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "---\n"
    )


def _paper_md(pid: str, *, dataset_ref: str, overlap: str = "full") -> str:
    return (
        "---\n"
        f"id: paper:{pid}\n"
        "kind: paper\n"
        f"title: {pid}\n"
        "status: active\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-01'\n"
        "dataset_usage:\n"
        f"  - ref: {dataset_ref}\n"
        "    role: analyzed\n"
        f"    overlap: {overlap}\n"
        "---\n"
    )


def _evidence_line_md(eid: str, *, target: str, source: str) -> str:
    return (
        "---\n"
        f"id: evidence-line:{eid}\n"
        "kind: evidence-line\n"
        f"title: {eid}\n"
        "status: active\n"
        "stance: supports\n"
        f"target: proposition:{target}\n"
        f"source: {source}\n"
        "strength: moderate\n"
        "evidence_type: empirical_data_evidence\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-01'\n"
        "---\n"
    )


def _evidence_line_with_usage_md(eid: str, *, target: str, dataset_ref: str, overlap: str = "full") -> str:
    """Evidence-line with dataset_usage authored directly on the line (no paper intermediary)."""
    return (
        "---\n"
        f"id: evidence-line:{eid}\n"
        "kind: evidence-line\n"
        f"title: {eid}\n"
        "status: active\n"
        "stance: supports\n"
        f"target: proposition:{target}\n"
        "strength: moderate\n"
        "evidence_type: empirical_data_evidence\n"
        "dataset_usage:\n"
        f"  - ref: {dataset_ref}\n"
        "    role: analyzed\n"
        f"    overlap: {overlap}\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-01'\n"
        "---\n"
    )


def _dataset_dp(root: Path, slug: str) -> None:
    """Write a minimal external dataset datapackage."""
    dp = root / "data" / slug / "datapackage.yaml"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "kind: dataset\n"
        f"title: {slug}\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
        encoding="utf-8",
    )


def _materialize(root: Path) -> tuple:
    """Materialize the project and return (knowledge, provenance) named graphs."""
    from science_tool.graph.materialize import materialize_graph

    trig = materialize_graph(root)
    ds = Dataset()
    ds.parse(source=str(trig), format="trig")
    return (
        ds.graph(PROJECT_NS["graph/knowledge"]),
        ds.graph(PROJECT_NS["graph/provenance"]),
    )


# ---------------------------------------------------------------------------
# Point 1 — same-dataset collapse
# ---------------------------------------------------------------------------


def test_same_dataset_two_lines_collapse_to_one_unit(tmp_path: Path) -> None:
    """Two evidence-lines whose sources BOTH used dataset:mmrf (analyzed, full)
    support the same proposition → B2 emits one DatasetIndependenceCommitment,
    and reduce_units keeps exactly ONE of them (the other is collapsed).
    """
    _manifest(tmp_path)
    _dataset_dp(tmp_path, "mmrf")

    _write(tmp_path, "entities/propositions/p.md", _prop_md("p"))

    # Two papers, each analyzed dataset:mmrf at full overlap
    _write(tmp_path, "entities/papers/pa.md", _paper_md("pa", dataset_ref="dataset:mmrf"))
    _write(tmp_path, "entities/papers/pb.md", _paper_md("pb", dataset_ref="dataset:mmrf"))

    # Two evidence-lines citing those papers → they inherit the dataset usage via prov:wasDerivedFrom
    _write(tmp_path, "entities/evidence-lines/ea.md", _evidence_line_md("ea", target="p", source="paper:pa"))
    _write(tmp_path, "entities/evidence-lines/eb.md", _evidence_line_md("eb", target="p", source="paper:pb"))

    knowledge, provenance = _materialize(tmp_path)

    # --- B2 structural assertion: one DatasetIndependenceCommitment record ---
    commitments = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert len(commitments) == 1, f"Expected exactly 1 DatasetIndependenceCommitment; got {len(commitments)}"
    commitment = commitments[0]

    # Both lines are members of the shared-source group
    members = set(provenance.objects(commitment, SCI_NS.independenceMember))
    line_a = PROJECT_NS["evidence-line/ea"]
    line_b = PROJECT_NS["evidence-line/eb"]
    assert line_a in members, f"evidence-line:ea missing from commitment members {members}"
    assert line_b in members, f"evidence-line:eb missing from commitment members {members}"

    # The independence group carries the mmrf dataset slug
    groups = {str(o) for _, _, o in provenance.triples((commitment, SCI_NS.independenceGroup, None))}
    assert any("mmrf" in g for g in groups), f"Expected 'mmrf' in independence group; got {groups}"

    # --- reduce_units: both lines get shared-source metadata; they collapse to 1 kept unit ---
    from science_tool.graph.belief import collect_evidence_units, reduce_units

    target_uri = URIRef(PROJECT_NS["proposition/p"])
    units = collect_evidence_units(knowledge, provenance, [target_uri])
    assert len(units) == 2, f"Expected 2 raw units before reduction; got {len(units)}"

    # Both units must carry the same independence_group (the dataset-derived one)
    groups_on_units = {u.independence_group for u in units}
    # One group value (the shared dataset-derived group), not two different groups or None
    assert None not in groups_on_units, "Both units should carry a derived independence_group; found None"
    assert len(groups_on_units) == 1, f"Both units must share the same independence_group; got {groups_on_units}"

    reduced = reduce_units(units)
    # Exactly one unit kept; the other is collapsed (same group, same stance → only one winner)
    assert len(reduced.kept) == 1, (
        f"Expected 1 kept unit after collapse; got {len(reduced.kept)}. "
        f"kept={[u.line_uri for u in reduced.kept]}, collapsed={[u.line_uri for u in reduced.collapsed]}"
    )
    assert len(reduced.collapsed) == 1, f"Expected 1 collapsed unit; got {len(reduced.collapsed)}"
    assert reduced.flagged_ungrouped == [], "No units should be flagged as ungrouped"
    assert reduced.excluded_circular == [], "No units should be excluded as circular"


# ---------------------------------------------------------------------------
# Point 2 — distinct-dataset independence (no collapse)
# ---------------------------------------------------------------------------


def test_distinct_datasets_two_lines_stay_independent(tmp_path: Path) -> None:
    """Two evidence-lines backed by *different* datasets (mmrf vs gse19784)
    stay in distinct independence groups and both survive reduce_units.
    """
    _manifest(tmp_path)
    _dataset_dp(tmp_path, "mmrf")
    _dataset_dp(tmp_path, "gse19784")

    _write(tmp_path, "entities/propositions/p.md", _prop_md("p"))

    _write(tmp_path, "entities/papers/pa.md", _paper_md("pa", dataset_ref="dataset:mmrf"))
    _write(tmp_path, "entities/papers/pb.md", _paper_md("pb", dataset_ref="dataset:gse19784"))

    _write(tmp_path, "entities/evidence-lines/ea.md", _evidence_line_md("ea", target="p", source="paper:pa"))
    _write(tmp_path, "entities/evidence-lines/eb.md", _evidence_line_md("eb", target="p", source="paper:pb"))

    knowledge, provenance = _materialize(tmp_path)

    # No DatasetIndependenceCommitment (two different datasets → no shared-source group)
    commitments = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert commitments == [], f"Expected no commitment records for distinct datasets; got {len(commitments)}"

    # reduce_units keeps both lines as independent contributors
    from science_tool.graph.belief import collect_evidence_units, reduce_units

    target_uri = URIRef(PROJECT_NS["proposition/p"])
    units = collect_evidence_units(knowledge, provenance, [target_uri])
    assert len(units) == 2, f"Expected 2 raw units; got {len(units)}"

    reduced = reduce_units(units)
    assert len(reduced.kept) == 2, (
        f"Expected both units kept for distinct datasets; got {len(reduced.kept)} kept, "
        f"{len(reduced.collapsed)} collapsed"
    )
    assert reduced.collapsed == [], "No collapse expected for distinct-dataset lines"


# ---------------------------------------------------------------------------
# Point 3 — unregistered dataset ref WARNs
# ---------------------------------------------------------------------------


def test_unregistered_dataset_ref_warns_ref_unresolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An evidence-line (or paper) with a dataset_usage ref pointing at a dataset
    that is not registered in the project yields dataset-influence.ref-unresolved WARN.
    Uses evaluate_dataset_influence directly to avoid needing a commons registry.
    """
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence
    from science_tool.validate.result import Severity

    results = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "paper:Adams2025",
                    "kind": "paper",
                    "_path": "entities/papers/Adams2025.md",
                    "dataset_usage": [{"ref": "dataset:does-not-exist", "role": "analyzed", "overlap": "full"}],
                }
            ],
            dataset_ref_status={"dataset:does-not-exist": "missing"},
            row_usage_refs=[],
        )
    )

    rule_pairs = [(r.severity, r.rule) for r in results]
    assert (Severity.WARN, "dataset-influence.ref-unresolved") in rule_pairs, (
        f"Expected dataset-influence.ref-unresolved WARN; got {rule_pairs}"
    )


# ---------------------------------------------------------------------------
# Point 4 — dependence-role + unknown overlap WARNs
# ---------------------------------------------------------------------------


def test_dependence_role_with_unknown_overlap_warns(tmp_path: Path) -> None:
    """An evidence-line's source paper has role=analyzed and overlap=unknown (omitted)
    → dataset-influence.overlap-unknown-candidate WARN fires.
    Uses evaluate_dataset_influence directly (the unit-level check).
    """
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence
    from science_tool.validate.result import Severity

    # overlap key omitted → defaults to "unknown" in the check
    results_omitted = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "paper:Adams2025",
                    "kind": "paper",
                    "_path": "entities/papers/Adams2025.md",
                    "dataset_usage": [{"ref": "dataset:mmrf", "role": "analyzed"}],
                }
            ],
            dataset_ref_status={"dataset:mmrf": "resolved"},
            row_usage_refs=[],
        )
    )
    rule_pairs_omitted = [(r.severity, r.rule) for r in results_omitted]
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") in rule_pairs_omitted, (
        f"Expected overlap-unknown-candidate WARN for omitted overlap; got {rule_pairs_omitted}"
    )

    # Explicit overlap=unknown also warns
    results_explicit = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "paper:Adams2025",
                    "kind": "paper",
                    "_path": "entities/papers/Adams2025.md",
                    "dataset_usage": [{"ref": "dataset:mmrf", "role": "analyzed", "overlap": "unknown"}],
                }
            ],
            dataset_ref_status={"dataset:mmrf": "resolved"},
            row_usage_refs=[],
        )
    )
    rule_pairs_explicit = [(r.severity, r.rule) for r in results_explicit]
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") in rule_pairs_explicit, (
        f"Expected overlap-unknown-candidate WARN for explicit overlap=unknown; got {rule_pairs_explicit}"
    )

    # overlap=full must NOT warn
    results_full = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "paper:Adams2025",
                    "kind": "paper",
                    "_path": "entities/papers/Adams2025.md",
                    "dataset_usage": [{"ref": "dataset:mmrf", "role": "analyzed", "overlap": "full"}],
                }
            ],
            dataset_ref_status={"dataset:mmrf": "resolved"},
            row_usage_refs=[],
        )
    )
    rule_pairs_full = [(r.severity, r.rule) for r in results_full]
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") not in rule_pairs_full, (
        f"overlap=full must NOT trigger overlap-unknown-candidate; got {rule_pairs_full}"
    )


# ---------------------------------------------------------------------------
# Point 5 — task source in provenance, not belief
# ---------------------------------------------------------------------------


def test_task_source_lands_in_provenance_not_belief(tmp_path: Path) -> None:
    """An evidence-line whose `source` is `task:<id>` must route exclusively into
    the provenance graph (prov:wasDerivedFrom), never as a cito edge in the
    knowledge graph.  The cito:supports edge must point at the proposition target.
    """
    _manifest(tmp_path)

    _write(
        tmp_path,
        "entities/tasks/t082.md",
        "---\n"
        "id: task:t082\n"
        "kind: task\n"
        'title: "Task T082"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "---\n",
    )

    _write(tmp_path, "entities/propositions/q.md", _prop_md("q"))

    _write(
        tmp_path,
        "entities/evidence-lines/el-task.md",
        "---\n"
        "id: evidence-line:el-task\n"
        "kind: evidence-line\n"
        'title: "EL task source"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "stance: supports\n"
        "target: proposition:q\n"
        "source: task:t082\n"
        "---\n",
    )

    knowledge, provenance = _materialize(tmp_path)

    line_uri = URIRef(PROJECT_NS["evidence-line/el-task"])
    task_uri = URIRef(PROJECT_NS["task/t082"])
    target_uri = URIRef(PROJECT_NS["proposition/q"])

    # prov:wasDerivedFrom must point at the task in provenance
    assert (line_uri, PROV.wasDerivedFrom, task_uri) in provenance, (
        "Expected prov:wasDerivedFrom edge from evidence-line:el-task to task:t082 in provenance graph"
    )

    # The task must NOT appear as the object of any cito edge
    assert (line_uri, CITO_NS.supports, task_uri) not in knowledge, (
        "task:t082 must not appear as object of cito:supports"
    )
    assert (line_uri, CITO_NS.disputes, task_uri) not in knowledge, (
        "task:t082 must not appear as object of cito:disputes"
    )

    # The cito:supports edge must point at the proposition target
    assert (line_uri, CITO_NS.supports, target_uri) in knowledge, (
        "Expected cito:supports edge from evidence-line:el-task to proposition:q in knowledge graph"
    )


# ---------------------------------------------------------------------------
# Point 6 — UKB / UKB-PPP sub-cohort lineage commitment (end-to-end)
# ---------------------------------------------------------------------------


def _dataset_dp_with_parent(root: Path, slug: str, parent_slug: str) -> None:
    """Write an external dataset datapackage that declares a parent_dataset."""
    dp = root / "data" / slug / "datapackage.yaml"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "kind: dataset\n"
        f"title: {slug}\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "access:\n"
        "  level: controlled\n"
        "  verified: true\n"
        f"parent_dataset: dataset:{parent_slug}\n",
        encoding="utf-8",
    )


def test_ukb_ppp_sub_cohort_lineage_commitment_end_to_end(tmp_path: Path) -> None:
    """End-to-end UKB / UKB-PPP sub-cohort commitment.

    Project structure:
      - dataset:uk-biobank   (parent)
      - dataset:ukb-ppp      (child, parent_dataset: dataset:uk-biobank)
      - paper:pa             analyzed dataset:ukb-ppp, full overlap
      - paper:pb             analyzed dataset:uk-biobank, full overlap
      - proposition:p        the shared target
      - evidence-line:ea     source=paper:pa, supports proposition:p
      - evidence-line:eb     source=paper:pb, supports proposition:p

    Expected:
      - The knowledge graph carries sci:subCohortOf(ukb-ppp → uk-biobank)
        (materialised by Task 3).
      - B2 (Task 4) recognises the child-on-parent pair as a shared-source
        commitment and emits exactly ONE DatasetIndependenceCommitment.
      - Both evidence lines are independence members; sharedDataset covers
        both datasets in the lineage family.
      - reduce_units collapses to 1 kept unit.
    """
    _manifest(tmp_path)

    # Parent dataset: UK Biobank
    _dataset_dp(tmp_path, "uk-biobank")

    # Child dataset: UKB-PPP, declares parent_dataset
    _dataset_dp_with_parent(tmp_path, "ukb-ppp", "uk-biobank")

    # Proposition
    _write(tmp_path, "entities/propositions/p.md", _prop_md("p"))

    # Paper A analyzed ukb-ppp (the child sub-cohort)
    _write(tmp_path, "entities/papers/pa.md", _paper_md("pa", dataset_ref="dataset:ukb-ppp"))

    # Paper B analyzed uk-biobank (the parent)
    _write(tmp_path, "entities/papers/pb.md", _paper_md("pb", dataset_ref="dataset:uk-biobank"))

    # Evidence lines citing those papers
    _write(tmp_path, "entities/evidence-lines/ea.md", _evidence_line_md("ea", target="p", source="paper:pa"))
    _write(tmp_path, "entities/evidence-lines/eb.md", _evidence_line_md("eb", target="p", source="paper:pb"))

    knowledge, provenance = _materialize(tmp_path)

    # --- Task 3 sub-cohort edge must be present in knowledge graph ---
    ukb_ppp_uri = PROJECT_NS["dataset/ukb-ppp"]
    uk_biobank_uri = PROJECT_NS["dataset/uk-biobank"]
    assert (ukb_ppp_uri, SCI_NS.subCohortOf, uk_biobank_uri) in knowledge, (
        "Expected sci:subCohortOf(ukb-ppp, uk-biobank) in knowledge graph (Task 3 materialization)"
    )

    # --- Task 4 B2: exactly ONE DatasetIndependenceCommitment ---
    commitments = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert len(commitments) == 1, (
        f"Expected exactly 1 DatasetIndependenceCommitment for ukb-ppp/uk-biobank "
        f"child-on-parent pair; got {len(commitments)}"
    )
    commitment = commitments[0]

    # Both evidence lines are members
    members = set(provenance.objects(commitment, SCI_NS.independenceMember))
    line_a = PROJECT_NS["evidence-line/ea"]
    line_b = PROJECT_NS["evidence-line/eb"]
    assert line_a in members, f"evidence-line:ea missing from commitment members {members}"
    assert line_b in members, f"evidence-line:eb missing from commitment members {members}"

    # sharedDataset covers both members of the lineage family
    shared_datasets = set(provenance.objects(commitment, SCI_NS.sharedDataset))
    assert ukb_ppp_uri in shared_datasets, f"dataset:ukb-ppp missing from sharedDataset; got {shared_datasets}"
    assert uk_biobank_uri in shared_datasets, f"dataset:uk-biobank missing from sharedDataset; got {shared_datasets}"

    # independenceGroup is a deterministic key (slug for single-dataset, hash for multi)
    groups = {str(o) for _, _, o in provenance.triples((commitment, SCI_NS.independenceGroup, None))}
    assert len(groups) == 1, f"Expected exactly one independenceGroup on the commitment; got {groups}"
    assert groups.pop().startswith("dataset-derived:"), (
        f"Expected independence group to start with 'dataset-derived:'; got {groups}"
    )

    # --- reduce_units: collapse to exactly 1 kept unit ---
    from science_tool.graph.belief import collect_evidence_units, reduce_units

    target_uri = URIRef(PROJECT_NS["proposition/p"])
    units = collect_evidence_units(knowledge, provenance, [target_uri])
    assert len(units) == 2, f"Expected 2 raw units before reduction; got {len(units)}"

    groups_on_units = {u.independence_group for u in units}
    assert None not in groups_on_units, (
        "Both units should carry a derived independence_group from the sub-cohort "
        "commitment; found None — lineage B2 path may not be reaching the units"
    )
    assert len(groups_on_units) == 1, f"Both units must share the same independence_group; got {groups_on_units}"

    reduced = reduce_units(units)
    assert len(reduced.kept) == 1, (
        f"Expected 1 kept unit after ukb-ppp/uk-biobank sub-cohort collapse; "
        f"got {len(reduced.kept)}. "
        f"kept={[u.line_uri for u in reduced.kept]}, "
        f"collapsed={[u.line_uri for u in reduced.collapsed]}"
    )
    assert len(reduced.collapsed) == 1, f"Expected 1 collapsed unit; got {len(reduced.collapsed)}"
    assert reduced.flagged_ungrouped == [], "No units should be flagged as ungrouped"
    assert reduced.excluded_circular == [], "No units should be excluded as circular"


# ---------------------------------------------------------------------------
# Point 6 (original) — line-authored dataset_usage collapse (B2 headline mechanism)
# ---------------------------------------------------------------------------


def test_line_authored_dataset_usage_same_dataset_collapse(tmp_path: Path) -> None:
    """Two evidence-lines with dataset_usage authored DIRECTLY on the lines
    (no paper intermediary) both targeting the same dataset (analyzed, full)
    must collapse identically to the paper-mediated case.

    This exercises B1 (usage_records_for_entity materialises the line's own
    dataset_usage with source='authored') and B2 (_ancestor_path returns
    'direct' when consumer == line).

    Assertions mirror test_same_dataset_two_lines_collapse_to_one_unit:
      - exactly 1 DatasetIndependenceCommitment
      - both lines are members of it
      - independence_group contains the dataset slug
      - reduce_units yields len(kept)==1, len(collapsed)==1
    """
    _manifest(tmp_path)
    _dataset_dp(tmp_path, "mmrf")

    _write(tmp_path, "entities/propositions/p.md", _prop_md("p"))

    # Two evidence-lines that each carry dataset_usage directly — no paper
    _write(
        tmp_path,
        "entities/evidence-lines/la.md",
        _evidence_line_with_usage_md("la", target="p", dataset_ref="dataset:mmrf"),
    )
    _write(
        tmp_path,
        "entities/evidence-lines/lb.md",
        _evidence_line_with_usage_md("lb", target="p", dataset_ref="dataset:mmrf"),
    )

    knowledge, provenance = _materialize(tmp_path)

    # --- B2: one DatasetIndependenceCommitment ---
    commitments = list(provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment))
    assert len(commitments) == 1, (
        f"Expected exactly 1 DatasetIndependenceCommitment for line-authored usage; got {len(commitments)}"
    )
    commitment = commitments[0]

    line_a = PROJECT_NS["evidence-line/la"]
    line_b = PROJECT_NS["evidence-line/lb"]
    members = set(provenance.objects(commitment, SCI_NS.independenceMember))
    assert line_a in members, f"evidence-line:la missing from commitment members {members}"
    assert line_b in members, f"evidence-line:lb missing from commitment members {members}"

    groups = {str(o) for _, _, o in provenance.triples((commitment, SCI_NS.independenceGroup, None))}
    assert any("mmrf" in g for g in groups), f"Expected 'mmrf' in independence group; got {groups}"

    # --- reduce_units: collapse to 1 kept ---
    from science_tool.graph.belief import collect_evidence_units, reduce_units

    target_uri = URIRef(PROJECT_NS["proposition/p"])
    units = collect_evidence_units(knowledge, provenance, [target_uri])
    assert len(units) == 2, f"Expected 2 raw units before reduction; got {len(units)}"

    groups_on_units = {u.independence_group for u in units}
    assert None not in groups_on_units, (
        "Both units should carry a derived independence_group; found None — "
        "line-authored dataset_usage may not be reaching _ancestor_path"
    )
    assert len(groups_on_units) == 1, f"Both units must share the same independence_group; got {groups_on_units}"

    reduced = reduce_units(units)
    assert len(reduced.kept) == 1, (
        f"Expected 1 kept unit after collapse of line-authored usage; got {len(reduced.kept)}. "
        f"kept={[u.line_uri for u in reduced.kept]}, collapsed={[u.line_uri for u in reduced.collapsed]}"
    )
    assert len(reduced.collapsed) == 1, f"Expected 1 collapsed unit; got {len(reduced.collapsed)}"
    assert reduced.flagged_ungrouped == [], "No units should be flagged as ungrouped"
    assert reduced.excluded_circular == [], "No units should be excluded as circular"
