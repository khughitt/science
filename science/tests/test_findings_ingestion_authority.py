from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.findings import cli as findings_cli
from science_tool.findings.ingest import IngestionContext, ingestion_authority


def test_it_returns_a_registry_and_a_context_over_the_project(ungraphed_project: Path):
    registry, context = ingestion_authority(ungraphed_project)

    assert isinstance(context, IngestionContext)
    assert "proposition:p1" in context.canonical_entity_ids
    assert registry.rule("managed-artifact.missing") is not None


def test_it_loads_sources_without_relaxing_identity(
    ungraphed_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Spec 1 §8: ingestion keeps `strict_identity=True`, so an identity conflict refuses the
    write. Health passes `strict_identity=False` on purpose, to carry conflicts into its audit
    gate -- reusing the health loader here would silently ingest what should be refused.

    Asserted on the CALL, not on the source text: a source-text assertion cannot tell a
    docstring from an argument, so a correct implementation that merely EXPLAINS the rule in a
    comment would fail it.
    """
    import science_tool.findings.ingest as ingest_module
    from science_tool.graph import sources as sources_module

    seen: dict[str, object] = {}
    real = sources_module.load_project_sources

    def _record(project_root, **kwargs):
        seen.update(kwargs)
        return real(project_root, **kwargs)

    monkeypatch.setattr(sources_module, "load_project_sources", _record)
    ingest_module.ingestion_authority(ungraphed_project)

    assert seen.get("strict_identity", True) is True, (
        "the strict default must stand: a relaxed identity check ingests a conflict that "
        "Spec 1 refuses"
    )


def test_the_cli_uses_the_shared_derivation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """One spelling, not two that can drift. The old private helpers are gone.

    ASSERTED ON THE CALL, NOT ON THE SOURCE TEXT -- the same discipline the test above states,
    which this one used to violate. `"ingestion_authority" in inspect.getsource(...)` is
    satisfied by a COMMENT mentioning the name, by a dead import, or by a second private
    derivation sitting beside a docstring that cites the shared one; none of those is the
    command calling it. Monkeypatching the module attribute and requiring it to be invoked
    over the project root is a claim about behaviour, and it fails the moment the command
    grows a private path again.
    """
    assert not hasattr(findings_cli, "_load_ingestion_context")
    assert not hasattr(findings_cli, "_registry")

    calls: list[Path] = []

    def _record(project_root: Path):
        calls.append(project_root)
        return ingestion_authority(project_root)

    monkeypatch.setattr(findings_cli, "ingestion_authority", _record)

    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "fingerprint_version": 1,
                "ingestion_ref": "ing:1",
                "generated_at": "2026-07-27T12:00:00+00:00",
                "findings": [],
                "accepted": [],
                "metrics": {},
                "unwired": [],
                "totals": {
                    "findings_total": 0,
                    "findings_by_severity": {},
                    "accepted_total": 0,
                    "unwired_total": 0,
                },
                "meta": {
                    "producers_run": ["dataset_anomalies"],
                    "total_duration_seconds": 0.0,
                    "timings": [],
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        findings_cli.findings_group,
        [
            "ingest", str(report),
            "--project-root", str(tmp_path),
            "--attest-ingestion-ref", "ing:1",
            "--attest-generated-at", "2026-07-27T12:00:00+00:00",
            "--attest-producer-id", "dataset_anomalies",
        ],
    )

    assert calls == [tmp_path], result.output
