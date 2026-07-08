# tests/test_dataset_prioritize.py
from __future__ import annotations

from pathlib import Path

from science_tool.dataset_prioritize import (
    frontmatter_reach,
    prioritize,
    readiness_for,
    readiness_weight,
    target_coverage,
)


def _ext(level: str, verified: bool, availability: str = "available") -> dict:
    return {
        "id": "dataset:x",
        "kind": "dataset",
        "title": "X",
        "status": "candidate",
        "origin": "external",
        "tier": "track",
        "access": {"level": level, "availability": availability, "verified": verified},
        "ontology_terms": [],
        "related": [],
    }


def test_readiness_for_reuses_canonical_states() -> None:
    assert readiness_for(_ext("public", False)).state == "public, unverified"
    assert readiness_for(_ext("controlled", True)).state == "available"
    assert readiness_for(_ext("public", False, availability="embargoed")).state == "embargoed"


def test_readiness_weight_ordering_and_flagged_default() -> None:
    # available > unverified-public > unverified-controlled > embargoed
    w_avail, f_avail = readiness_weight(_ext("controlled", True))
    w_pub, _ = readiness_weight(_ext("public", False))
    w_ctrl, _ = readiness_weight(_ext("controlled", False))
    w_emb, _ = readiness_weight(_ext("public", False, availability="embargoed"))
    assert w_avail == 1.0
    assert w_avail > w_pub > w_ctrl > w_emb
    assert f_avail == []
    # an unparseable / unknown-origin entity flags rather than silently bucketing
    w_unk, f_unk = readiness_weight({"id": "dataset:b", "kind": "dataset", "title": "B"})
    assert w_unk == 0.1
    assert "readiness-unresolved" in f_unk


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_frontmatter_reach_both_directions_excludes_source_refs(tmp_path: Path) -> None:
    # dataset A points outward to a question; question Q2 points back to dataset B.
    _write(
        tmp_path / "entities/datasets/a.md",
        '---\nid: "dataset:a"\nkind: "dataset"\ntitle: "A"\nrelated: ["question:q1", "topic:t1"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/b.md",
        '---\nid: "dataset:b"\nkind: "dataset"\ntitle: "B"\nsource_refs: ["question:qX"]\n---\n',
    )  # source_refs must NOT count
    _write(tmp_path / "entities/questions/q1.md", '---\nid: "question:q1"\nkind: "question"\ntitle: "Q1"\n---\n')
    _write(
        tmp_path / "entities/questions/q2.md",
        '---\nid: "question:q2"\nkind: "question"\ntitle: "Q2"\nrelated: ["dataset:b"]\n---\n',
    )

    reach = frontmatter_reach(tmp_path)
    assert reach["dataset:a"] == {"question:q1"}  # outgoing; topic ignored
    assert reach["dataset:b"] == {"question:q2"}  # incoming back-edge only
    assert "dataset:b" not in reach.get("dataset:b", set()) or "question:qX" not in reach["dataset:b"]


def test_frontmatter_reach_reads_question_datasets_field(tmp_path: Path) -> None:
    _write(tmp_path / "entities/datasets/d.md", '---\nid: "dataset:d"\nkind: "dataset"\ntitle: "D"\nrelated: []\n---\n')
    _write(
        tmp_path / "entities/questions/q.md",
        '---\nid: "question:q"\nkind: "question"\ntitle: "Q"\ndatasets: ["dataset:d"]\nrelated: []\n---\n',
    )

    reach = frontmatter_reach(tmp_path)

    assert reach["dataset:d"] == {"question:q"}


def test_frontmatter_reach_bridges_consumer_dataset_usage_to_related_qh(tmp_path: Path) -> None:
    _write(tmp_path / "entities/datasets/d.md", '---\nid: "dataset:d"\nkind: "dataset"\ntitle: "D"\nrelated: []\n---\n')
    _write(tmp_path / "entities/hypotheses/h.md", '---\nid: "hypothesis:h"\nkind: "hypothesis"\ntitle: "H"\n---\n')
    _write(
        tmp_path / "entities/papers/p.md",
        '---\nid: "paper:p"\nkind: "paper"\ntitle: "P"\n'
        'related: ["hypothesis:h"]\n'
        "dataset_usage:\n"
        '  - ref: "dataset:d"\n'
        '    role: "analyzed"\n'
        '    overlap: "full"\n---\n',
    )

    reach = frontmatter_reach(tmp_path)

    assert reach["dataset:d"] == {"hypothesis:h"}


def test_prioritize_sparse_no_graph_orders_by_accessibility_and_flags(tmp_path: Path) -> None:
    # available > unverified public; the unconnected one gets no-edge.
    # dataset:avail is controlled (gated) → include_gated=True keeps it visible so
    # the accessibility ordering can be asserted; the default-exclusion behavior is
    # covered separately by test_prioritize_excludes_gated_by_default.
    _write(
        tmp_path / "entities/datasets/avail.md",
        '---\nid: "dataset:avail"\nkind: "dataset"\ntitle: "Avail"\norigin: "external"\n'
        'related: ["question:q1"]\naccess: {level: "controlled", verified: true}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/unv.md",
        '---\nid: "dataset:unv"\nkind: "dataset"\ntitle: "Unv"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
    )
    _write(tmp_path / "entities/questions/q1.md", '---\nid: "question:q1"\nkind: "question"\ntitle: "Q1"\n---\n')

    rows = prioritize(tmp_path, include_gated=True)
    ids = [r["id"] for r in rows]
    assert ids[0] == "dataset:avail"  # verified + reach=1 ranks first
    unv = next(r for r in rows if r["id"] == "dataset:unv")
    assert "unverified" in unv["gap_flags"]
    assert "no-edge" in unv["gap_flags"]  # reach 0
    assert rows[0]["score"] > unv["score"]


def test_prioritize_excludes_gated_by_default(tmp_path: Path) -> None:
    # registration/controlled/commercial are gated; public/mixed and derived (no
    # access block → level "") are actionable and stay. Default hides the gated set.
    _write(
        tmp_path / "entities/datasets/pub.md",
        '---\nid: "dataset:pub"\nkind: "dataset"\ntitle: "Pub"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/mix.md",
        '---\nid: "dataset:mix"\nkind: "dataset"\ntitle: "Mix"\norigin: "external"\n'
        'access: {level: "mixed", verified: false}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/reg.md",
        '---\nid: "dataset:reg"\nkind: "dataset"\ntitle: "Reg"\norigin: "external"\n'
        'access: {level: "registration", verified: false}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/ctrl.md",
        '---\nid: "dataset:ctrl"\nkind: "dataset"\ntitle: "Ctrl"\norigin: "external"\n'
        'access: {level: "controlled", verified: true}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/com.md",
        '---\nid: "dataset:com"\nkind: "dataset"\ntitle: "Com"\norigin: "external"\n'
        'access: {level: "commercial", verified: true}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/der.md",
        '---\nid: "dataset:der"\nkind: "dataset"\ntitle: "Der"\norigin: "derived"\ndatapackage: "r/dp.yaml"\n---\n',
    )

    default_ids = {r["id"] for r in prioritize(tmp_path)}
    assert default_ids == {"dataset:pub", "dataset:mix", "dataset:der"}

    # opt-out restores the full set
    all_ids = {r["id"] for r in prioritize(tmp_path, include_gated=True)}
    assert all_ids == {
        "dataset:pub",
        "dataset:mix",
        "dataset:der",
        "dataset:reg",
        "dataset:ctrl",
        "dataset:com",
    }

    # an explicit level overrides the default exclusion for that level
    ctrl_ids = {r["id"] for r in prioritize(tmp_path, level="controlled")}
    assert ctrl_ids == {"dataset:ctrl"}


def test_prioritize_excludes_reference_and_pointer_by_default(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/datasets/dep.md",
        '---\nid: "dataset:dep"\nkind: "dataset"\ntitle: "Dep"\norigin: "external"\n'
        'dataset_class: "deposit"\naccess: {level: "public", verified: true}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/ref.md",
        '---\nid: "dataset:ref"\nkind: "dataset"\ntitle: "Ref"\norigin: "external"\n'
        'dataset_class: "reference"\naccess: {level: "public", verified: true, source_url: "https://example.org"}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/ptr.md",
        '---\nid: "dataset:ptr"\nkind: "dataset"\ntitle: "Ptr"\norigin: "external"\n'
        'dataset_class: "pointer"\naccess: {level: "public", verified: true, source_url: "https://example.org/p"}\n---\n',
    )

    assert {r["id"] for r in prioritize(tmp_path)} == {"dataset:dep"}
    assert {r["id"] for r in prioritize(tmp_path, include_reference=True)} == {"dataset:dep", "dataset:ref"}
    assert {r["id"] for r in prioritize(tmp_path, include_pointer=True)} == {"dataset:dep", "dataset:ptr"}
    assert {r["id"] for r in prioritize(tmp_path, runtime_state="reference-only")} == {"dataset:ref"}


def test_target_coverage_reports_runtime_states_and_gap_reasons(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/questions/q-run.md",
        '---\nid: "question:q-run"\nkind: "question"\ntitle: "Runnable"\n'
        'required_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n---\n',
    )
    _write(
        tmp_path / "entities/questions/q-ref.md",
        '---\nid: "question:q-ref"\nkind: "question"\ntitle: "Reference"\n'
        'required_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n---\n',
    )
    _write(
        tmp_path / "entities/questions/q-gated.md",
        '---\nid: "question:q-gated"\nkind: "question"\ntitle: "Gated"\n'
        'required_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n---\n',
    )
    _write(
        tmp_path / "entities/questions/q-unverified.md",
        '---\nid: "question:q-unverified"\nkind: "question"\ntitle: "Unverified"\n'
        'required_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n---\n',
    )
    _write(
        tmp_path / "entities/questions/q-gap.md",
        '---\nid: "question:q-gap"\nkind: "question"\ntitle: "Gap"\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/run.md",
        '---\nid: "dataset:run"\nkind: "dataset"\ntitle: "Run"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/run/datapackage.json"\n'
        'related: ["question:q-run"]\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "public", verified: true}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/ref.md",
        '---\nid: "dataset:ref"\nkind: "dataset"\ntitle: "Ref"\norigin: "external"\n'
        'dataset_class: "reference"\nrelated: ["question:q-ref"]\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "public", verified: true, source_url: "https://example.org"}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/gated.md",
        '---\nid: "dataset:gated"\nkind: "dataset"\ntitle: "Gated"\norigin: "external"\n'
        'dataset_class: "deposit"\nrelated: ["question:q-gated"]\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "controlled", verified: false}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/unv.md",
        '---\nid: "dataset:unv"\nkind: "dataset"\ntitle: "Unv"\norigin: "external"\n'
        'dataset_class: "deposit"\nrelated: ["question:q-unverified"]\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "public", verified: false}\n---\n',
    )

    rows = prioritize(tmp_path, include_gated=True, include_reference=True, include_pointer=True)
    by_target = {r["target"]: r for r in target_coverage(rows, tmp_path)}

    assert by_target["question:q-run"]["coverage_state"] == "covered-runnable"
    assert by_target["question:q-run"]["gap_reason"] == "none"
    assert by_target["question:q-ref"]["coverage_state"] == "covered-reference"
    assert by_target["question:q-ref"]["gap_reason"] == "only-reference"
    assert by_target["question:q-gated"]["coverage_state"] == "blocked-access"
    assert by_target["question:q-gated"]["gap_reason"] == "only-gated"
    assert by_target["question:q-unverified"]["coverage_state"] == "unverified"
    assert by_target["question:q-unverified"]["gap_reason"] == "only-unverified"
    assert by_target["question:q-gap"]["coverage_state"] == "no-candidate"
    assert by_target["question:q-gap"]["gap_reason"] == "no-candidate"


def test_target_coverage_rejects_runtime_dataset_with_wrong_capability(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/questions/q-atac.md",
        '---\nid: "question:q-atac"\nkind: "question"\ntitle: "Chromatin accessibility"\n'
        'required_capabilities: [{assay: "chromatin-accessibility", modality: "scATAC"}]\n'
        'datasets: ["dataset:scrna"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/scrna.md",
        '---\nid: "dataset:scrna"\nkind: "dataset"\ntitle: "scRNA"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/scrna/datapackage.json"\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "scRNA"}]\n'
        'access: {level: "public", verified: true}\n---\n',
    )

    rows = prioritize(tmp_path)
    coverage = target_coverage(rows, tmp_path)[0]

    assert coverage["datasets"] == ["dataset:scrna"]
    assert coverage["compatible_datasets"] == []
    assert coverage["coverage_state"] == "capability-mismatch"
    assert coverage["gap_reason"] == "capability-mismatch"
    assert coverage["counts"]["runnable"] == 0
    assert coverage["incompatible_datasets"][0]["dataset"] == "dataset:scrna"


def test_target_coverage_accepts_multicapability_dataset(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/questions/q-atac.md",
        '---\nid: "question:q-atac"\nkind: "question"\ntitle: "Chromatin accessibility"\n'
        'required_capabilities: [{assay: "chromatin-accessibility", modality: "scATAC"}]\n'
        'datasets: ["dataset:multiome"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/multiome.md",
        '---\nid: "dataset:multiome"\nkind: "dataset"\ntitle: "Multiome"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/multiome/datapackage.json"\n'
        'provided_capabilities:\n'
        '  - {assay: "gene-expression", modality: "scRNA"}\n'
        '  - {assay: "chromatin-accessibility", modality: "scATAC"}\n'
        'access: {level: "public", verified: true}\n---\n',
    )

    rows = prioritize(tmp_path)
    coverage = target_coverage(rows, tmp_path)[0]

    assert coverage["compatible_datasets"] == ["dataset:multiome"]
    assert coverage["incompatible_datasets"] == []
    assert coverage["coverage_state"] == "covered-runnable"
    assert coverage["gap_reason"] == "none"
    assert coverage["counts"]["runnable"] == 1


def test_target_coverage_reports_missing_capability_metadata(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/questions/q-unassessed.md",
        '---\nid: "question:q-unassessed"\nkind: "question"\ntitle: "Unassessed"\n'
        'datasets: ["dataset:run"]\n---\n',
    )
    _write(
        tmp_path / "entities/questions/q-required.md",
        '---\nid: "question:q-required"\nkind: "question"\ntitle: "Required"\n'
        'required_capabilities: [{assay: "proteomics", modality: "mass-spec"}]\n'
        'datasets: ["dataset:unknown"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/run.md",
        '---\nid: "dataset:run"\nkind: "dataset"\ntitle: "Run"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/run/datapackage.json"\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "public", verified: true}\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/unknown.md",
        '---\nid: "dataset:unknown"\nkind: "dataset"\ntitle: "Unknown"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/unknown/datapackage.json"\n'
        'access: {level: "public", verified: true}\n---\n',
    )

    rows = prioritize(tmp_path)
    by_target = {row["target"]: row for row in target_coverage(rows, tmp_path)}

    assert by_target["question:q-unassessed"]["coverage_state"] == "missing-required-capabilities"
    assert by_target["question:q-unassessed"]["gap_reason"] == "missing-required-capabilities"
    assert by_target["question:q-required"]["coverage_state"] == "missing-provided-capabilities"
    assert by_target["question:q-required"]["gap_reason"] == "missing-provided-capabilities"


def test_target_coverage_reports_out_of_molecular_scope(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities/questions/q-method.md",
        '---\nid: "question:q-method"\nkind: "question"\ntitle: "Meta method"\n'
        'capability_scope: "methodological"\n'
        'datasets: ["dataset:run"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/run.md",
        '---\nid: "dataset:run"\nkind: "dataset"\ntitle: "Run"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/run/datapackage.json"\n'
        'provided_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'access: {level: "public", verified: true}\n---\n',
    )

    rows = prioritize(tmp_path)
    coverage = target_coverage(rows, tmp_path)[0]

    assert coverage["coverage_state"] == "out-of-molecular-scope"
    assert coverage["gap_reason"] == "methodological"


def test_scoped_dataset_does_not_gap_classify_a_molecular_target(tmp_path: Path) -> None:
    # A clinical (scoped) dataset cross-linked to a molecular question must not
    # drag the target into a capability gap — it is outside the molecular gate.
    _write(
        tmp_path / "entities/questions/q-mol.md",
        '---\nid: "question:q-mol"\nkind: "question"\ntitle: "Molecular"\n'
        'required_capabilities: [{assay: "gene-expression", modality: "bulk-rna"}]\n'
        'datasets: ["dataset:clin"]\n---\n',
    )
    _write(
        tmp_path / "entities/datasets/clin.md",
        '---\nid: "dataset:clin"\nkind: "dataset"\ntitle: "Clinical"\norigin: "external"\n'
        'dataset_class: "deposit"\ndatapackage: "data/clin/datapackage.json"\n'
        'capability_scope: "clinical-outcome"\n'
        'access: {level: "public", verified: true}\n---\n',
    )

    rows = prioritize(tmp_path)
    coverage = target_coverage(rows, tmp_path)[0]

    assert coverage["incompatible_datasets"] == []
    assert coverage["coverage_state"] == "no-candidate"
    assert coverage["gap_reason"] == "no-candidate"
