"""Cases are project-state, not knowledge, and not writable by an autonomous actor.

Both properties hold with NO change to `autonomy/policy.py` or to the graph writer;
these guards assert that, so a later edit cannot quietly break either.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from rdflib import Dataset
from science_model.audit import (
    AuditReport,
    EntitySubject,
    FindingRule,
    FindingSection,
    ReportedFinding,
)
from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import (
    ChangeSet,
    ChangeType,
    PathChange,
    entity_kind_for_path,
)
from science_tool.autonomy.path_gate import evaluate
from science_tool.findings.ingest import (
    IngestionContext,
    IngestionProvenance,
    ingest_report,
)
from science_tool.findings.producers import (
    FindingProducer,
    FindingRegistry,
    build_registry,
)
from science_tool.findings.storage import CASES_DIRNAME, load_cases
from science_tool.graph.attention import compute_attention_candidates
from science_tool.graph.io import (
    DEFAULT_REVISION_MANIFEST_EXCLUDES,
    build_input_manifest,
    read_revision_manifest,
)
from science_tool.graph.materialize import materialize_graph


def test_a_case_path_is_unclassified_and_therefore_denied():
    rel = f"{CASES_DIRNAME}/dataset-stale-review--{'a' * 64}.md"
    assert entity_kind_for_path(rel) is None


def test_the_path_gate_denies_an_actor_writing_a_case():
    rel = f"{CASES_DIRNAME}/dataset-stale-review--{'a' * 64}.md"
    change_set = ChangeSet(
        base_commit="a" * 40,
        head_commit="b" * 40,
        changes=(
            PathChange(
                path=rel,
                change_type=ChangeType.ADDED,
                entity_kind=None,
                fields=(),
            ),
        ),
    )
    verdict = evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL, report_path=None)
    assert not verdict.allowed
    assert any(d.path == rel for d in verdict.denials)


def test_cases_are_excluded_from_the_revision_manifest():
    assert f"{CASES_DIRNAME}/*.md" in DEFAULT_REVISION_MANIFEST_EXCLUDES


def test_a_case_directory_is_not_an_entity_home():
    # `cases` must not be in the directory->kind map, or a case would infer
    # `kind: finding` -- a live epistemic kind (design §5).
    from science_model.frontmatter import _DIR_TO_KIND

    assert "cases" not in _DIR_TO_KIND
    assert "audits" not in _DIR_TO_KIND


class _IsolationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str


def _seed_materializable_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: audit-case-isolation\nknowledge_profiles:\n  local: core\n",
        encoding="utf-8",
    )
    (root / "doc").mkdir()
    (root / "doc" / "notes.md").write_text("# Durable graph input\n", encoding="utf-8")
    hypothesis = root / "entities" / "hypotheses" / "h1.md"
    hypothesis.parent.mkdir(parents=True)
    hypothesis.write_text(
        "---\n"
        'id: "hypothesis:h1"\n'
        'kind: "hypothesis"\n'
        'title: "Isolation control"\n'
        'status: "active"\n'
        'created: "2026-04-01"\n'
        'updated: "2026-04-01"\n'
        'last_reviewed: "2026-05-01"\n'
        "---\n"
        "A canonical graph entity used as the finding subject.\n",
        encoding="utf-8",
    )


def _isolation_report() -> tuple[AuditReport, FindingRegistry]:
    section = FindingSection(id="isolation", title="Isolation", section_order=900)
    rule = FindingRule(
        id="isolation.audit-case",
        severities={"warn"},
        subject_types={"entity"},
        qualifier_schema=_IsolationQualifiers,
        identity_qualifiers=("field",),
        title="Audit case isolation",
        section=section.id,
        display_order=10,
    )
    producer = FindingProducer(
        producer_id="isolation_probe",
        namespace="health_checks",
        source_module="graph/health_checks/test.py",
        rules=(rule,),
        sections=(section,),
        metrics_schema=None,
        remediators=frozenset(),
    )
    finding = rule.build(
        subject=EntitySubject(ref="hypothesis:h1"),
        severity="warn",
        qualifiers={"field": "graph-boundary"},
        message="AUDIT-CASE-MUST-NOT-MATERIALIZE",
    )
    report = AuditReport(
        schema_version=2,
        fingerprint_version=1,
        ingestion_ref="isolation:ingest:1",
        generated_at="2026-07-27T12:00:00Z",
        findings=(
            ReportedFinding(
                producer_id=producer.producer_id,
                finding=finding,
            ),
        ),
        accepted=(),
        metrics={},
        unwired=(),
        totals={
            "findings_total": 1,
            "findings_by_severity": {"warn": 1},
            "accepted_total": 0,
            "unwired_total": 0,
        },
        meta={
            "producers_run": (producer.producer_id,),
            "total_duration_seconds": 0.01,
            "timings": (),
        },
    )
    return report, build_registry([producer], active_kinds=frozenset())


def _named_quads(dataset: Dataset) -> set[tuple[str, str, str, str]]:
    return {
        (str(subject), str(predicate), str(obj), str(graph.identifier))
        for graph in dataset.graphs()
        for subject, predicate, obj in graph
    }


def _load_graph(path: Path) -> Dataset:
    dataset = Dataset()
    dataset.parse(source=str(path), format="trig")
    return dataset


def test_ingested_case_stays_out_of_graph_attention_and_revision_inputs(
    tmp_path: Path,
) -> None:
    """Exercise the complete trusted-ingestion -> canonical-graph boundary.

    Comparing actual graph quads before and after ingestion closes all named graphs,
    including provenance. Comparing the stored revision manifest with a fresh input
    manifest proves ingestion does not merely avoid triples while still making the
    graph stale.
    """
    _seed_materializable_project(tmp_path)
    graph_path = materialize_graph(tmp_path, strict=False, include_commons=False)
    before_graph = _load_graph(graph_path)
    before_quads = _named_quads(before_graph)
    before_candidates = compute_attention_candidates(before_graph)
    before_manifest = build_input_manifest(graph_path)
    assert read_revision_manifest(before_graph) == before_manifest
    assert [row.entity_id for row in before_candidates.rows] == ["hypothesis:h1"]

    report, registry = _isolation_report()
    outcome = ingest_report(
        tmp_path,
        report,
        registry,
        provenance=IngestionProvenance(
            ingestion_ref=report.ingestion_ref,
            generated_at=report.generated_at,
            producer_ids=frozenset(report.meta.producers_run),
        ),
        context=IngestionContext(canonical_entity_ids=frozenset({"hypothesis:h1"})),
    )
    assert outcome.records_written == 1
    record = load_cases(tmp_path)[0]
    case_path = next((tmp_path / CASES_DIRNAME).glob("*.md")).relative_to(tmp_path)

    # The graph last built before ingestion remains current: case and lock leaves are
    # excluded from the revision inputs rather than merely ignored by one parser.
    after_manifest = build_input_manifest(graph_path)
    assert after_manifest == before_manifest
    assert read_revision_manifest(before_graph) == after_manifest

    rebuilt_path = materialize_graph(tmp_path, strict=False, include_commons=False)
    after_graph = _load_graph(rebuilt_path)
    after_quads = _named_quads(after_graph)
    assert after_quads == before_quads

    graph_text = "\n".join("\t".join(quad) for quad in sorted(after_quads))
    for forbidden in (
        record.finding_id,
        case_path.as_posix(),
        "isolation.audit-case",
        "AUDIT-CASE-MUST-NOT-MATERIALIZE",
    ):
        assert forbidden not in graph_text

    after_candidates = compute_attention_candidates(after_graph)
    assert after_candidates.status == "ok"
    assert [row.entity_id for row in after_candidates.rows] == ["hypothesis:h1"]
