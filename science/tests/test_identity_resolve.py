from __future__ import annotations

import socket

from science_tool.commons.assembly import ASSEMBLY_REGISTRY_ID, AssemblyEntry
from science_tool.commons.errors import CommonsError
from science_tool.commons.gene_crosswalk import GENE_CROSSWALK_ID
from science_tool.commons.identity_resolve import resolve_assembly_label, resolve_identity, resolve_namespace


_HG38_DIGEST = "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp"


def test_resolve_assembly_label_with_fixture_registry(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_resolve_assembly(label_or_digest: str, *, registry_id: str, commons_root=None, data_root=None):
        calls.append((label_or_digest, registry_id))
        return AssemblyEntry(seqcol_digest=_HG38_DIGEST, label="hg38", accession="GCF_000001405.40")

    monkeypatch.setattr("science_tool.commons.assembly.resolve_assembly", fake_resolve_assembly)

    assert resolve_assembly_label("hg38", ASSEMBLY_REGISTRY_ID) == _HG38_DIGEST
    assert calls == [("hg38", ASSEMBLY_REGISTRY_ID)]


def test_missing_assembly_registry_degrades_to_declared_unresolved(monkeypatch) -> None:
    def missing_registry(label_or_digest: str, *, registry_id: str, commons_root=None, data_root=None):
        raise CommonsError("registry unavailable")

    monkeypatch.setattr("science_tool.commons.assembly.resolve_assembly", missing_registry)
    ctx = {"taxon": 9606, "assembly": {"label": "hg38", "registry": ASSEMBLY_REGISTRY_ID}}

    resolved = resolve_identity(ctx)

    assert resolved.identity_context["assembly"] == {
        "label": "hg38",
        "registry": ASSEMBLY_REGISTRY_ID,
        "resolution_status": "declared_unresolved",
    }
    assert [(m.level, m.path) for m in resolved.messages] == [("warning", "identity_context.assembly")]
    assert "registry unavailable" in resolved.messages[0].message


def test_resolve_identity_idempotent_for_resolved_context(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("already-resolved assembly should not be re-resolved")

    monkeypatch.setattr("science_tool.commons.assembly.resolve_assembly", fail_if_called)
    ctx = {
        "taxon": 9606,
        "assembly": {
            "seqcol_digest": _HG38_DIGEST,
            "registry": ASSEMBLY_REGISTRY_ID,
            "resolution_status": "resolved",
        },
        "molecular_ids": {
            "gene": {
                "namespace": "hgnc_id",
                "registry": GENE_CROSSWALK_ID,
                "resolution_status": "resolved",
            }
        },
    }

    resolved = resolve_identity(ctx, registries={GENE_CROSSWALK_ID: True})

    assert resolved.identity_context == ctx
    assert resolved.identity_context is not ctx


def test_resolve_identity_never_uses_network(monkeypatch) -> None:
    def fake_socket(*args, **kwargs):
        raise AssertionError("identity resolver must not open network sockets")

    def fake_resolve_assembly(label_or_digest: str, *, registry_id: str, commons_root=None, data_root=None):
        return AssemblyEntry(seqcol_digest=_HG38_DIGEST, label="hg38", accession="GCF_000001405.40")

    monkeypatch.setattr(socket, "socket", fake_socket)
    monkeypatch.setattr("science_tool.commons.assembly.resolve_assembly", fake_resolve_assembly)

    resolved = resolve_identity(
        {"taxon": 9606, "assembly": {"label": "hg38", "registry": ASSEMBLY_REGISTRY_ID}},
        registries={GENE_CROSSWALK_ID: True},
    )

    assert resolved.identity_context["assembly"]["seqcol_digest"] == _HG38_DIGEST
    assert resolved.identity_context["assembly"]["resolution_status"] == "resolved"


def test_resolve_namespace_supported_gene_namespace() -> None:
    resolution = resolve_namespace("hgnc_id", GENE_CROSSWALK_ID, registries={GENE_CROSSWALK_ID: True})

    assert resolution.resolution_status == "resolved"
    assert resolution.messages == ()


def test_resolve_namespace_missing_registry_degrades() -> None:
    resolution = resolve_namespace("hgnc_id", GENE_CROSSWALK_ID, registries={})

    assert resolution.resolution_status == "declared_unresolved"
    assert [(m.level, m.path) for m in resolution.messages] == [("warning", "identity_context.molecular_ids")]
    assert "unavailable" in resolution.messages[0].message


def test_resolve_namespace_unsupported_namespace_reports_error() -> None:
    resolution = resolve_namespace("refseq", GENE_CROSSWALK_ID, registries={GENE_CROSSWALK_ID: True})

    assert resolution.resolution_status == "declared_unresolved"
    assert [(m.level, m.path) for m in resolution.messages] == [("error", "identity_context.molecular_ids")]
    assert "unsupported namespace" in resolution.messages[0].message
