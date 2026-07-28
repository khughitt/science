from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from science_model.audit import EntitySubject, PathSubject

from science_tool.findings.catalog import build_registry_for_entity_registry
from science_tool.findings.ingest import (
    IngestionContext,
    IngestionProvenance,
    ingest_report,
)
from science_tool.graph.health import build_health_report
from science_tool.graph.health_checks import (
    entity_identity,
    identity_policy,
    invalid_entity_aspects,
)
from science_tool.graph.health_checks.base import HealthContext
from science_tool.graph.sources import ProjectSources, load_project_sources
from science_tool.instruments import InstrumentResult


def _context(root: Path, *canonical_ids: str) -> HealthContext:
    entities = [SimpleNamespace(canonical_id=canonical_id) for canonical_id in canonical_ids]
    return HealthContext(
        project_root=root,
        sources=cast(ProjectSources, SimpleNamespace(entities=entities)),
    )


def test_entity_identity_selects_path_when_candidate_ref_is_not_in_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        entity_identity,
        "_collect_entity_identity",
        lambda _context: [
            {
                "code": "invalid-canonical-id",
                "severity": "warning",
                "message": "invalid",
                "path": "entities/questions/bad.md",
                "canonical_id": "question:missing",
            }
        ],
    )

    result = entity_identity.CHECK.run(_context(tmp_path))

    assert result.instrument.rows[0].subject == PathSubject(path="entities/questions/bad.md")


def test_identity_policy_selects_path_when_candidate_ref_is_not_in_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        identity_policy,
        "collect_identity_policy_findings",
        lambda *_args, **_kwargs: InstrumentResult.from_rows(
            [
                {
                    "check": "missing_taxon",
                    "entity_id": "question:missing",
                    "source_file": "entities/questions/bad.md",
                    "message": "missing taxon",
                }
            ]
        ),
    )

    result = identity_policy.CHECK.run(_context(tmp_path))

    assert result.instrument.rows[0].subject == PathSubject(path="entities/questions/bad.md")


def test_invalid_aspects_selects_path_when_candidate_ref_is_not_in_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        invalid_entity_aspects,
        "collect_invalid_entity_aspects",
        lambda _root: InstrumentResult.from_rows(
            [
                {
                    "entity_id": "question:missing",
                    "source_file": "entities/questions/bad.md",
                    "message": "unknown aspect",
                }
            ]
        ),
    )

    result = invalid_entity_aspects.CHECK.run(_context(tmp_path))

    assert result.instrument.rows[0].subject == PathSubject(path="entities/questions/bad.md")


def test_subject_selection_uses_entity_only_for_exact_source_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        invalid_entity_aspects,
        "collect_invalid_entity_aspects",
        lambda _root: InstrumentResult.from_rows(
            [
                {
                    "entity_id": "question:present",
                    "source_file": "entities/questions/present.md",
                    "message": "unknown aspect",
                }
            ]
        ),
    )

    result = invalid_entity_aspects.CHECK.run(_context(tmp_path, "question:present"))

    assert result.instrument.rows[0].subject == EntitySubject(ref="question:present")


def test_missing_reverse_dataset_reference_uses_research_package_subject_and_ingests(
    tmp_path: Path,
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    package = tmp_path / "research" / "packages" / "lens" / "section" / "research-package.md"
    package.parent.mkdir(parents=True)
    package.write_text(
        '---\nid: "research-package:rp1"\nkind: "research-package"\ntitle: "RP1"\ndisplays: ["dataset:missing"]\n---\n',
        encoding="utf-8",
    )
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:reverse-reference",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"dataset_anomalies"},
    )
    finding = report.findings[0].finding
    assert finding.subject == EntitySubject(ref="research-package:rp1")
    assert finding.qualifiers == {"counterpart": "dataset:missing"}

    sources = load_project_sources(tmp_path)
    outcome = ingest_report(
        tmp_path,
        report,
        build_registry_for_entity_registry(sources.registry),
        provenance=IngestionProvenance(
            ingestion_ref=report.ingestion_ref,
            generated_at=report.generated_at,
            producer_ids=frozenset(report.meta.producers_run),
        ),
        context=IngestionContext(canonical_entity_ids=frozenset(entity.canonical_id for entity in sources.entities)),
    )

    assert outcome.records_written == 1
