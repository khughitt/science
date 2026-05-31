from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from science_tool.commons.sequence_store import SequenceStoreError
from science_tool.commons.variant import VariantDefect, VariantMatch
from science_tool.validate.checks.variant_identity import (
    _evaluate_variant_rows,
    _row_expr,
    check_variant_identity,
    evaluate_variant_declaration,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.table/1.0+bio.identity_context/1.0"
_SEQCOL = "SQ.assembly"


def _ds(variant, **fm) -> dict:
    identity_context = {"molecular_ids": {"variant": variant}} if variant is not None else {}
    return {
        "type": "dataset",
        "id": "dataset:x",
        "schema_profile": _PROFILE,
        "_path": "data/x/datapackage.yaml",
        "identity_context": identity_context,
        **fm,
    }


def _locator() -> dict:
    return {"resource": "variants.csv", "format": "spdi", "column": "variant"}


def test_wellformed_vrs_declaration_passes_silently() -> None:
    ds = _ds({"namespace": "vrs", "locator": _locator()})
    assert list(evaluate_variant_declaration([ds])) == []


def test_wrong_namespace_errors() -> None:
    ds = _ds({"namespace": "dbsnp", "locator": _locator()})
    errors = [r for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "identity.variant-namespace-unsupported"


def test_missing_locator_errors() -> None:
    ds = _ds({"namespace": "vrs"})
    errors = [r for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "identity.variant-locator-malformed"


def test_vcf_locator_requires_columns_map() -> None:
    ds = _ds({"namespace": "vrs", "locator": {"resource": "variants.csv", "format": "vcf"}})
    errors = [r for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "identity.variant-locator-malformed"


def test_rsid_locator_requires_registry() -> None:
    ds = _ds({"namespace": "vrs", "locator": {"resource": "variants.csv", "format": "rsid", "column": "rsid"}})

    errors = [r for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]

    assert len(errors) == 1
    assert errors[0].rule == "identity.variant-locator-malformed"
    assert "rsid locator requires registry" in errors[0].message


def test_rsid_locator_accepts_optional_allele_columns() -> None:
    locator = {
        "resource": "variants.csv",
        "format": "rsid",
        "column": "rsid",
        "registry": "dataset:variant-labels-dbsnp-human",
        "allele_columns": {"ref": "REF", "alt": "ALT"},
    }
    ds = _ds({"namespace": "vrs", "locator": locator})

    assert list(evaluate_variant_declaration([ds])) == []


def test_row_layer_reports_unavailable_rsid_registry_before_row_minting(tmp_path: Path, monkeypatch) -> None:
    from science_tool.commons.errors import DataResourceNotFoundError

    project = _variant_project(
        tmp_path,
        "rsid\nrs123\n",
        locator_format="rsid",
        locator_column="rsid",
        locator_registry="dataset:variant-labels-dbsnp-human",
    )

    def fail_vrs_id(expr: str, *, fmt: str, assembly_seqcol: str):
        raise AssertionError(f"rsID locator unexpectedly used generic VRS minting: {expr} {fmt} {assembly_seqcol}")

    def fake_resolve(dataset_id: str, logical_path: str):
        raise DataResourceNotFoundError(dataset_id, logical_path, tried=[])

    monkeypatch.setattr("science_tool.commons.resolver.resolve", fake_resolve)
    monkeypatch.setattr("science_tool.commons.variant.vrs_id", fail_vrs_id)

    results = list(check_variant_identity(_ctx(project)))

    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.rule == "identity.variant-registry-unavailable"]
    assert len(infos) == 1


def test_row_layer_mints_rsid_locator(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
        allele_columns:
          ref: REF
          alt: ALT
"""
    project = _variant_project(
        tmp_path,
        "rsid,REF,ALT\nrs1,A,G\nrs2,C,T\n",
        locator=rsid_locator,
    )

    calls: list[tuple[str, str | None, str | None]] = []
    resolve_calls: list[tuple[str, str]] = []

    def fake_resolve(dataset_id: str, logical_path: str):
        resolve_calls.append((dataset_id, logical_path))
        return type("Resolved", (), {"path": sqlite_path})()

    def fake_vrs_id_from_rsid(
        rsid: str,
        *,
        assembly_seqcol: str,
        sqlite_path: Path,
        ref: str | None = None,
        alt: str | None = None,
    ) -> VariantMatch:
        calls.append((rsid, ref, alt))
        assert sqlite_path.name == "rsid_mappings.sqlite"
        return VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref")

    monkeypatch.setattr("science_tool.commons.resolver.resolve", fake_resolve)
    monkeypatch.setattr("science_tool.commons.variant.vrs_id_from_rsid", fake_vrs_id_from_rsid)

    results = list(check_variant_identity(_ctx(project)))

    assert [r.rule for r in results if r.rule == "identity.variant-rows-minted"] == ["identity.variant-rows-minted"]
    assert resolve_calls == [("dataset:variant-labels-dbsnp-human", "rsid_mappings.sqlite")]
    assert calls == [("rs1", "A", "G"), ("rs2", "C", "T")]


def test_row_layer_reports_bad_rsid_sqlite_as_registry_unavailable(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
"""
    project = _variant_project(
        tmp_path,
        "rsid\nrs1\n",
        locator=rsid_locator,
    )

    monkeypatch.setattr(
        "science_tool.commons.resolver.resolve",
        lambda dataset_id, logical_path: type("Resolved", (), {"path": sqlite_path})(),
    )

    def bad_vrs_id_from_rsid(*args, **kwargs):
        raise sqlite3.DatabaseError("bad sqlite")

    monkeypatch.setattr("science_tool.commons.variant.vrs_id_from_rsid", bad_vrs_id_from_rsid)

    results = list(check_variant_identity(_ctx(project)))

    infos = [r for r in results if r.rule == "identity.variant-registry-unavailable"]
    assert len(infos) == 1
    assert infos[0].severity is Severity.INFO
    assert "bad sqlite" in infos[0].message
    assert not [r for r in results if r.severity is Severity.ERROR]


def test_row_layer_reports_ambiguous_rsid(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
"""
    project = _variant_project(
        tmp_path,
        "rsid\nrs2\n",
        locator=rsid_locator,
    )

    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id_from_rsid",
        lambda *args, **kwargs: VariantDefect("rs2", "ambiguous-rsid", "2 candidate alleles for GRCH38"),
    )
    monkeypatch.setattr(
        "science_tool.commons.resolver.resolve",
        lambda dataset_id, logical_path: type("Resolved", (), {"path": sqlite_path})(),
    )

    results = list(check_variant_identity(_ctx(project)))

    errors = [r for r in results if r.rule == "identity.variant-rows-unresolved"]
    assert len(errors) == 1
    assert "ambiguous-rsid=1" in errors[0].message


def test_row_layer_reports_short_rsid_allele_row_as_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
        allele_columns:
          ref: REF
          alt: ALT
"""
    project = _variant_project(tmp_path, "rsid,REF,ALT\nrs1,A\n", locator=rsid_locator)
    monkeypatch.setattr(
        "science_tool.commons.resolver.resolve",
        lambda dataset_id, logical_path: type("Resolved", (), {"path": sqlite_path})(),
    )

    results = list(check_variant_identity(_ctx(project)))

    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert "missing value for column 'ALT'" in errors[0].message


def test_row_layer_reports_registry_unavailable_as_info(tmp_path: Path, monkeypatch) -> None:
    from science_tool.commons.errors import DataResourceNotFoundError

    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
"""
    project = _variant_project(tmp_path, "rsid\nrs1\n", locator=rsid_locator)

    def fake_resolve(dataset_id: str, logical_path: str):
        raise DataResourceNotFoundError(dataset_id, logical_path, tried=[])

    monkeypatch.setattr("science_tool.commons.resolver.resolve", fake_resolve)

    results = list(check_variant_identity(_ctx(project)))

    infos = [r for r in results if r.rule == "identity.variant-registry-unavailable"]
    assert len(infos) == 1
    assert infos[0].severity is Severity.INFO
    assert not [r for r in results if r.severity is Severity.ERROR]


def test_declared_unresolved_is_info_not_error() -> None:
    ds = _ds({"namespace": "vrs", "resolution_status": "declared_unresolved", "locator": _locator()})
    results = list(evaluate_variant_declaration([ds]))
    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.severity is Severity.INFO]
    assert len(infos) == 1
    assert infos[0].rule == "identity.variant-declared-unresolved"


def test_row_layer_reports_unresolved_defects_with_minted_count(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(tmp_path, "variant\nNC_000001.11:100:A:T\nNC_000001.11:101:G:C\n")
    calls: list[tuple[str, str, str]] = []

    def fake_vrs_id(expr: str, *, fmt: str, assembly_seqcol: str):
        calls.append((expr, fmt, assembly_seqcol))
        if len(calls) == 1:
            return VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref")
        return VariantDefect(query=expr, reason="ref-mismatch", detail="expected A")

    monkeypatch.setattr("science_tool.commons.variant.vrs_id", fake_vrs_id)

    results = list(check_variant_identity(_ctx(project)))
    errors = [r for r in results if r.rule == "identity.variant-rows-unresolved"]
    assert len(errors) == 1
    assert errors[0].severity is Severity.ERROR
    assert "minted=1" in errors[0].message
    assert "ref-mismatch=1" in errors[0].message
    assert calls == [
        ("NC_000001.11:100:A:T", "spdi", _SEQCOL),
        ("NC_000001.11:101:G:C", "spdi", _SEQCOL),
    ]


def test_row_layer_locator_resource_can_name_datapackage_resource(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(
        tmp_path,
        "variant\nNC_000001.11:100:A:T\n",
        locator_resource="variants",
        resource_name="variants",
        resource_path="data/variants.csv",
    )
    calls: list[str] = []

    def fake_vrs_id(expr: str, *, fmt: str, assembly_seqcol: str):
        calls.append(expr)
        return VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref")

    monkeypatch.setattr("science_tool.commons.variant.vrs_id", fake_vrs_id)

    results = list(check_variant_identity(_ctx(project)))

    assert not [r for r in results if r.rule == "identity.variant-resource-unavailable"]
    assert not [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert calls == ["NC_000001.11:100:A:T"]


def test_row_layer_reports_sequence_store_unavailable_as_info(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(tmp_path, "variant\nNC_000001.11:100:A:T\n")

    def fake_vrs_id(expr: str, *, fmt: str, assembly_seqcol: str):
        raise SequenceStoreError("store unavailable")

    monkeypatch.setattr("science_tool.commons.variant.vrs_id", fake_vrs_id)

    results = list(check_variant_identity(_ctx(project)))
    assert not [r for r in results if r.severity is Severity.ERROR]
    infos = [r for r in results if r.rule == "identity.variant-store-unavailable"]
    assert len(infos) == 1
    assert infos[0].severity is Severity.INFO


def test_unsafe_datapackage_path_reports_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(
        tmp_path,
        "variant\nNC_000001.11:100:A:T\n",
        datapackage_field="../outside/datapackage.yaml",
    )
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )

    results = list(check_variant_identity(_ctx(project)))
    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert errors[0].severity is Severity.ERROR
    assert "unsafe datapackage path" in errors[0].message


def test_missing_locator_column_reports_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(tmp_path, "other\nNC_000001.11:100:A:T\n")
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )

    results = list(check_variant_identity(_ctx(project)))
    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert errors[0].severity is Severity.ERROR
    assert "missing required column 'variant'" in errors[0].message


def test_ragged_csv_row_reports_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(tmp_path, "variant\nNC_000001.11:100:A:T,extra\n")
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )

    results = list(check_variant_identity(_ctx(project)))
    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert errors[0].severity is Severity.ERROR
    assert "ragged row 2" in errors[0].message


def test_invalid_utf8_variant_resource_reports_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project_bytes(tmp_path, b"variant\n\xff\n")
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )

    results = list(check_variant_identity(_ctx(project)))
    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert errors[0].severity is Severity.ERROR
    assert "cannot decode" in errors[0].message


def test_absent_locator_resource_reports_resource_unavailable(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(tmp_path, "variant\nNC_000001.11:100:A:T\n", locator_resource="missing.csv")
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )

    results = list(check_variant_identity(_ctx(project)))
    assert not [r for r in results if r.rule == "identity.variant-resource-invalid"]
    infos = [r for r in results if r.rule == "identity.variant-resource-unavailable"]
    assert len(infos) == 1
    assert infos[0].severity is Severity.INFO


def test_malformed_quoted_csv_reports_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    project = _variant_project(tmp_path, 'variant\n"NC_000001.11:100:A:T\n')
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )

    results = list(check_variant_identity(_ctx(project)))
    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert errors[0].severity is Severity.ERROR
    assert "malformed delimited text" in errors[0].message


def test_markdown_entity_without_datapackage_reports_resource_unavailable(tmp_path: Path, monkeypatch) -> None:
    tmp_path.joinpath("science.yaml").write_text("name: demo\n", encoding="utf-8")
    entity_path = tmp_path / "data" / "v" / "entity.md"
    entity_path.parent.mkdir(parents=True)
    entity_path.write_text("---\nid: dataset:v\ntype: dataset\ntitle: Variant markdown\n---\n", encoding="utf-8")
    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id",
        lambda expr, *, fmt, assembly_seqcol: VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref"),
    )
    ds = _ds(
        {"namespace": "vrs", "locator": _locator()},
        _path="data/v/entity.md",
        identity_context={
            "assembly": {"seqcol_digest": _SEQCOL},
            "molecular_ids": {"variant": {"namespace": "vrs", "locator": _locator()}},
        },
    )

    results = list(_evaluate_variant_rows(_ctx(tmp_path), [ds]))
    assert not [r for r in results if r.rule == "identity.variant-resource-invalid"]
    infos = [r for r in results if r.rule == "identity.variant-resource-unavailable"]
    assert len(infos) == 1
    assert infos[0].severity is Severity.INFO


def test_row_expr_builds_vcf_shorthand_from_column_mapping() -> None:
    locator = {"columns": {"chrom": "chrom", "pos": "pos", "ref": "ref", "alt": "alt"}}
    row: dict[str | None, str | list[str] | None] = {"chrom": "1", "pos": "101", "ref": "A", "alt": "T"}
    assert _row_expr(row, locator, "vcf") == "1-101-A-T"


def _ctx(project_root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(project_root, strict=False, verbose=False)


def _variant_project(
    tmp_path: Path,
    variants_csv: str,
    *,
    datapackage_field: str | None = None,
    locator: str | None = None,
    locator_format: str = "spdi",
    locator_column: str = "variant",
    locator_registry: str | None = None,
    locator_resource: str = "variants.csv",
    resource_name: str = "variants",
    resource_path: str = "variants.csv",
) -> Path:
    return _variant_project_bytes(
        tmp_path,
        variants_csv.encode("utf-8"),
        datapackage_field=datapackage_field,
        locator=locator,
        locator_format=locator_format,
        locator_column=locator_column,
        locator_registry=locator_registry,
        locator_resource=locator_resource,
        resource_name=resource_name,
        resource_path=resource_path,
    )


def _variant_project_bytes(
    tmp_path: Path,
    variants_bytes: bytes,
    *,
    datapackage_field: str | None = None,
    locator: str | None = None,
    locator_format: str = "spdi",
    locator_column: str = "variant",
    locator_registry: str | None = None,
    locator_resource: str = "variants.csv",
    resource_name: str = "variants",
    resource_path: str = "variants.csv",
) -> Path:
    tmp_path.joinpath("science.yaml").write_text("name: demo\n", encoding="utf-8")
    data_dir = tmp_path / "data" / "variants"
    data_dir.mkdir(parents=True)
    variants_path = data_dir / resource_path
    variants_path.parent.mkdir(parents=True, exist_ok=True)
    variants_path.write_bytes(variants_bytes)
    digest = hashlib.sha256(variants_bytes).hexdigest()
    datapackage_line = f"datapackage: {datapackage_field}\n" if datapackage_field is not None else ""
    registry_line = f"        registry: {locator_registry}\n" if locator_registry is not None else ""
    locator_yaml = (
        locator
        if locator is not None
        else f"""\
        resource: {locator_resource}
        format: {locator_format}
        column: {locator_column}
{registry_line}\
"""
    )
    data_dir.joinpath("datapackage.yaml").write_text(
        f"""\
profiles: [science-pkg-entity-1.0]
id: dataset:variants
type: dataset
title: Variants
schema_profile: {_PROFILE}
{datapackage_line}\
identity_context:
  assembly:
    seqcol_digest: {_SEQCOL}
  molecular_ids:
    variant:
      namespace: vrs
      locator:
{locator_yaml}\
resources:
  - name: {resource_name}
    path: {resource_path}
    hash: sha256:{digest}
    bytes: {len(variants_bytes)}
""",
        encoding="utf-8",
    )
    return tmp_path
