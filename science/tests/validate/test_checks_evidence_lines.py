"""Tests for evidence-line structural QA checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, Literal, RDF, URIRef
from rdflib.namespace import PROV

from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import PROJECT_NS, _graph_uri
from science_tool.validate import Severity, ValidateContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_manifest(root: Path) -> None:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Rule: evidence.unstanced — sub-case (a): missing stance or target on a line
# ---------------------------------------------------------------------------

def test_unstanced_clean_line_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert results == []


def test_unstanced_missing_stance_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == p
    assert "stance" in r.message


def test_unstanced_missing_target_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == p
    assert "target" in r.message


def test_unstanced_empty_target_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: ''\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == p


# ---------------------------------------------------------------------------
# Rule: evidence.unstanced — sub-case (b): uncounted proposition source_ref
# ---------------------------------------------------------------------------

def test_unstanced_counted_source_ref_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write(
        tmp_path,
        "doc/propositions/p1.md",
        "---\nid: proposition:p1\nsource_refs:\n  - paper:x\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert results == []


def test_unstanced_uncounted_source_ref_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    prop = _write(
        tmp_path,
        "doc/propositions/p1.md",
        "---\nid: proposition:p1\nsource_refs:\n  - paper:x\n  - paper:y\n---\n",
    )
    # Only paper:x has a matching evidence-line; paper:y is uncounted.
    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == prop
    assert "paper:y" in r.message


def test_unstanced_cite_prefix_source_ref_is_skipped(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write(
        tmp_path,
        "doc/propositions/p1.md",
        "---\nid: proposition:p1\nsource_refs:\n  - cite:jones2020\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    # cite: refs are skipped — no warning
    assert results == []


# ---------------------------------------------------------------------------
# Rule: independence.ungrouped-collapse
# ---------------------------------------------------------------------------

def test_ungrouped_collapse_shared_source_without_group_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: shared-source\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "independence.ungrouped-collapse"
    assert r.path == p


def test_ungrouped_collapse_circular_without_group_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: circular\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "independence.ungrouped-collapse"
    assert r.path == p


def test_ungrouped_collapse_shared_source_with_group_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: shared-source\nindependence_group: grp-a\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert results == []


def test_ungrouped_collapse_independent_is_always_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Rule: independence.suspect-circular
# ---------------------------------------------------------------------------

def test_suspect_circular_two_independent_sharing_dataset_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nshared_dataset: gse100\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:y\nindependence: independent\nshared_dataset: gse100\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "independence.suspect-circular"
    assert "shared_dataset" in r.message
    assert "gse100" in r.message


def test_suspect_circular_two_independent_sharing_group_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nindependence_group: grp-a\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:y\nindependence: independent\nindependence_group: grp-a\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert len(results) == 1
    assert results[0].rule == "independence.suspect-circular"


def test_suspect_circular_single_line_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nshared_dataset: ds:alpha\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert results == []


def test_suspect_circular_genuinely_independent_lines_emit_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:y\nindependence: independent\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert results == []


def test_suspect_circular_different_targets_do_not_trigger(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    # Same shared_dataset but DIFFERENT targets — should not trigger.
    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nshared_dataset: gse100\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p2\nsource: paper:y\nindependence: independent\nshared_dataset: gse100\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Rule: evidence.strength-implausible
# ---------------------------------------------------------------------------

def test_strength_implausible_strong_background_constraint_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_strength_implausible

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nstrength: strong\nevidence_role: background_constraint\n---\n",
    )

    results = list(check_evidence_strength_implausible(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.strength-implausible"
    assert r.path == p


def test_strength_implausible_strong_direct_test_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_strength_implausible

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nstrength: strong\nevidence_role: direct_test\n---\n",
    )

    results = list(check_evidence_strength_implausible(_ctx(tmp_path)))

    assert results == []


def test_strength_implausible_moderate_background_constraint_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_strength_implausible

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nstrength: moderate\nevidence_role: background_constraint\n---\n",
    )

    results = list(check_evidence_strength_implausible(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Rule: evidence.unscored-line
# ---------------------------------------------------------------------------

def test_unscored_line_warns_for_unrecognized_type(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: made_up\nevidence_role: direct_test\nstrength: strong\n---\n")
    results = list(check_evidence_unscored_line(_ctx(tmp_path)))
    assert len(results) == 1 and results[0].severity is Severity.WARN


def test_unscored_line_clean_for_fully_specified(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: empirical_data\nevidence_role: direct_test\nstrength: strong\n---\n")
    assert list(check_evidence_unscored_line(_ctx(tmp_path))) == []


def test_unscored_line_skips_diagnostic_roles(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    # model_criticism is recognized-but-non-massed: outside EVIDENCE_ROLE_RANK, never flagged.
    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: disputes\ntarget: proposition:p1\nevidence_role: model_criticism\n---\n")
    assert list(check_evidence_unscored_line(_ctx(tmp_path))) == []


def _ctx_with_b2_graph(tmp_path: Path, *, record_type: URIRef, authored: dict[str, str] | None = None) -> ValidateContext:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    graph_path = root / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    if authored:
        for key, value in authored.items():
            predicate = {
                "independence": SCI_NS.evidenceIndependence,
                "independence_group": SCI_NS.independenceGroup,
                "shared_dataset": SCI_NS.sharedDataset,
            }[key]
            provenance.add((line_a, predicate, Literal(value)))
    record = PROJECT_NS["dataset-independence/r1"]
    provenance.add((record, RDF.type, record_type))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceMember, line_a))
    provenance.add((record, SCI_NS.independenceMember, line_b))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceReason, Literal("unknown-overlap")))
    provenance.add((record, SCI_NS.sharedDataset, PROJECT_NS["dataset/gtex-v8"]))
    for suffix, line in (("a", line_a), ("b", line_b)):
        usage = PROJECT_NS[f"dataset-usage/{suffix}"]
        provenance.add((line, SCI_NS.hasDatasetUsage, usage))
        provenance.add((usage, RDF.type, SCI_NS.DatasetUsage))
        provenance.add((usage, SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]))
        provenance.add((usage, SCI_NS.usageRole, Literal("analyzed")))
        provenance.add((usage, SCI_NS.usageOverlap, Literal("full")))
        provenance.add((usage, SCI_NS.usageSource, Literal("authored")))
    ds.serialize(graph_path, format="trig")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_suspect_circular_warns_for_untagged_lines_with_derived_candidate(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    ctx = _ctx_with_b2_graph(tmp_path, record_type=SCI_NS.DatasetIndependenceCandidate)

    results = list(check_independence_suspect_circular(ctx))

    assert [(result.severity, result.rule) for result in results] == [
        (Severity.WARN, "independence.suspect-circular")
    ]


def test_committed_dataset_dependence_errors_when_line_authored_independent(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    ctx = _ctx_with_b2_graph(
        tmp_path,
        record_type=SCI_NS.DatasetIndependenceCommitment,
        authored={"independence": "independent"},
    )

    results = list(check_independence_suspect_circular(ctx))

    assert [(result.severity, result.rule) for result in results] == [
        (Severity.ERROR, "independence.dataset-derived-contradiction")
    ]


def test_authored_shared_dataset_refuted_only_when_line_has_direct_b2_usage(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    ctx = _ctx_with_b2_graph(
        tmp_path,
        record_type=SCI_NS.DatasetIndependenceCandidate,
        authored={
            "independence": "shared-source",
            "independence_group": "manual-gtex",
            "shared_dataset": str(PROJECT_NS["dataset/other"]),
        },
    )

    results = list(check_independence_suspect_circular(ctx))

    assert any(result.rule == "independence.shared-dataset-refuted" for result in results)


# ---------------------------------------------------------------------------
# Rule: evidence.reference-basis-no-identification-strength (A2/A-D4)
# ---------------------------------------------------------------------------

def _write_reference_basis_graph(
    root: Path,
    *,
    has_identification_strength: bool = False,
    source_class: str = "reference",
) -> None:
    """Build a minimal graph with one evidence line derived from a dataset."""
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))

    dataset_uri = URIRef("https://example.org/dataset/ds1")
    line_uri = URIRef("https://example.org/el/el1")
    prop_uri = URIRef("https://example.org/prop/p1")

    # Dataset with source_class in knowledge.
    k.add((dataset_uri, RDF.type, SCI_NS.Dataset))
    k.add((dataset_uri, SCI_NS.sourceClass, Literal(source_class)))

    # Evidence line typed in knowledge; supports the proposition.
    k.add((line_uri, RDF.type, SCI_NS.EvidenceLine))
    k.add((line_uri, CITO_NS.supports, prop_uri))

    # Provenance: line derived from dataset.
    p.add((line_uri, PROV.wasDerivedFrom, dataset_uri))

    # Optionally set identification_strength on the line (also in provenance).
    if has_identification_strength:
        p.add((line_uri, SCI_NS.identificationStrength, Literal("structural")))

    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def test_reference_basis_without_identification_strength_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import (
        check_reference_basis_no_identification_strength,
    )

    _write_reference_basis_graph(tmp_path, has_identification_strength=False)
    results = list(check_reference_basis_no_identification_strength(_ctx(tmp_path)))
    rules = [(r.severity, r.rule) for r in results]
    assert (Severity.WARN, "evidence.reference-basis-no-identification-strength") in rules


def test_reference_basis_with_identification_strength_is_silent(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import (
        check_reference_basis_no_identification_strength,
    )

    _write_reference_basis_graph(tmp_path, has_identification_strength=True)
    results = list(check_reference_basis_no_identification_strength(_ctx(tmp_path)))
    rules = [r.rule for r in results]
    assert "evidence.reference-basis-no-identification-strength" not in rules


def test_non_reference_source_does_not_nudge(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import (
        check_reference_basis_no_identification_strength,
    )

    _write_reference_basis_graph(
        tmp_path, has_identification_strength=False, source_class="observational"
    )
    results = list(check_reference_basis_no_identification_strength(_ctx(tmp_path)))
    rules = [r.rule for r in results]
    assert "evidence.reference-basis-no-identification-strength" not in rules


def test_reference_basis_no_graph_is_silent(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import (
        check_reference_basis_no_identification_strength,
    )

    # No knowledge/graph.trig present → tolerant early-return, zero results, no crash.
    results = list(check_reference_basis_no_identification_strength(_ctx(tmp_path)))
    rules = [r.rule for r in results]
    assert "evidence.reference-basis-no-identification-strength" not in rules
