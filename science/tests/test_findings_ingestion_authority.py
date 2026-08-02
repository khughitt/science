from __future__ import annotations

import inspect
from pathlib import Path

import pytest

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


def test_the_cli_uses_the_shared_derivation():
    """One spelling, not two that can drift. The old private helpers are gone.

    `.callback`, not the command object: `@findings_group.command("ingest")` rebinds the name
    to a `click.core.Command`, and `inspect.getsource` on that raises
    `TypeError: module, class, method, function, traceback, frame, or code object was
    expected` -- measured. Click keeps the undecorated function on `.callback`.
    """
    assert not hasattr(findings_cli, "_load_ingestion_context")
    assert not hasattr(findings_cli, "_registry")
    assert "ingestion_authority" in inspect.getsource(findings_cli.ingest_command.callback)
