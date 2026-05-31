"""Variant-identity checks (C4a-D6, §variant identity, order 33).

Two-layer C4a variant identity validation:

- declaration layer: validate identity_context.molecular_ids.variant with the
  shared tier declaration rules exposed by identity_context.tier_declaration_defect
- row layer: mint/check row-level VRS IDs from declared small-allele resources

This check intentionally does not use the crosswalk evaluator: VRS identity is
minted from row content plus the declared assembly, not resolved through a
registry member-key crosswalk.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.checks.identity_context import tier_declaration_defect
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SUPPORTED = frozenset({"vrs"})
_FORMATS = frozenset({"spdi", "hgvs", "vcf", "rsid"})
_ROW_MINTING_FORMATS = frozenset({"spdi", "hgvs", "vcf", "rsid"})


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _variant_decl(fm: dict[str, Any]) -> Any:
    idc = fm.get("identity_context") or {}
    mids = idc.get("molecular_ids") if isinstance(idc, dict) else None
    return mids.get("variant") if isinstance(mids, dict) else None


def _locator_defect(locator: Any) -> str | None:
    if not isinstance(locator, dict):
        return "locator must be an object"
    resource = locator.get("resource")
    if not isinstance(resource, str) or not resource.strip():
        return "missing or blank resource"
    fmt = locator.get("format")
    if not isinstance(fmt, str) or fmt.lower() not in _FORMATS:
        return f"format must be one of {sorted(_FORMATS)}"
    if fmt.lower() == "vcf":
        columns = locator.get("columns")
        if not isinstance(columns, dict):
            return "vcf locator requires columns map"
        for key in ("chrom", "pos", "ref", "alt"):
            value = columns.get(key)
            if not isinstance(value, str) or not value.strip():
                return f"vcf locator columns.{key} must be a nonblank string"
        return None
    if fmt.lower() == "rsid":
        registry = locator.get("registry")
        if not isinstance(registry, str) or not registry.startswith("dataset:"):
            return "rsid locator requires registry dataset:<slug>"
        column = locator.get("column")
        if not isinstance(column, str) or not column.strip():
            return "rsid locator requires a nonblank column"
        allele_columns = locator.get("allele_columns")
        if allele_columns is not None:
            if not isinstance(allele_columns, dict):
                return "rsid locator allele_columns must be an object"
            for key in ("ref", "alt"):
                value = allele_columns.get(key)
                if not isinstance(value, str) or not value.strip():
                    return f"rsid locator allele_columns.{key} must be a nonblank string"
        return None
    column = locator.get("column")
    if not isinstance(column, str) or not column.strip():
        return f"{fmt.lower()} locator requires a nonblank column"
    return None


def evaluate_variant_declaration(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        decl = _variant_decl(fm)
        if decl is None:
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        loc = "identity_context.molecular_ids.variant"
        if not isinstance(decl, dict):
            yield _result(Severity.ERROR, path, f"{ident}: {loc} must be an object", "identity.variant-malformed")
            continue
        defect = tier_declaration_defect(decl)
        if defect is not None:
            yield _result(Severity.ERROR, path, f"{ident}: malformed {loc} -- {defect}", "identity.variant-malformed")
            continue
        namespace = str(decl["namespace"])
        if namespace not in _SUPPORTED:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: variant namespace {namespace!r} is not supported (expected one of {sorted(_SUPPORTED)})",
                "identity.variant-namespace-unsupported",
            )
            continue
        if decl.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: variant identity declared_unresolved (honoured, RCM-D2)",
                "identity.variant-declared-unresolved",
            )
            continue
        locator_defect = _locator_defect(decl.get("locator"))
        if locator_defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed {loc}.locator -- {locator_defect}",
                "identity.variant-locator-malformed",
            )


@Check(section="variant identity", order=33)
def check_variant_identity(ctx: ValidateContext) -> Iterator[Result]:
    datasets = dataset_frontmatters(ctx)
    yield from evaluate_variant_declaration(datasets)
    yield from _evaluate_variant_rows(ctx, datasets)


def _evaluate_variant_rows(ctx: ValidateContext, datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    import csv
    import sqlite3

    from science_tool.commons.datapackage import read_datapackage, stream_sha256_and_bytes, validate_logical_path
    from science_tool.commons.errors import CommonsDatapackageError, CommonsError
    from science_tool.commons.resolver import resolve
    from science_tool.commons.rsid import SQLITE_RESOURCE
    from science_tool.commons.sequence_store import SequenceStoreError
    from science_tool.commons.variant import (
        VariantDefect,
        VariantMatch,
        VariantStoreUnavailable,
        vrs_id,
        vrs_id_from_rsid,
    )

    def datapackage_path(fm: dict[str, Any]) -> Path | None:
        source = fm.get("_path")
        if not isinstance(source, str) or not source:
            raise ValueError("dataset frontmatter is missing _path")
        try:
            source_path = Path(validate_logical_path(source))
        except CommonsError as exc:
            raise ValueError(f"unsafe dataset path {source!r}: {exc}") from exc
        base_dir = source_path.parent
        declared = fm.get("datapackage")
        if declared is None:
            if source_path.suffix not in (".yaml", ".yml"):
                return None
            logical = source_path
        elif isinstance(declared, str) and declared.strip():
            try:
                declared_path = Path(validate_logical_path(declared))
            except CommonsError as exc:
                raise ValueError(f"unsafe datapackage path {declared!r}: {exc}") from exc
            if len(declared_path.parts) > 1:
                logical = declared_path
                expected_parent = ctx.project_root
            else:
                logical = base_dir / declared_path
                expected_parent = ctx.project_root / base_dir
        else:
            raise ValueError("dataset datapackage field must be a nonblank string")
        resolved = (ctx.project_root / logical).resolve()
        root = (expected_parent if declared is not None else ctx.project_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"unsafe datapackage path {declared or source!r}") from exc
        return resolved

    def locate_resource(fm: dict[str, Any], logical_path: str) -> Path | None:
        dp_path = datapackage_path(fm)
        if dp_path is None:
            return None
        if not dp_path.is_file():
            return None
        descriptor = read_datapackage(dp_path)
        try:
            resource = descriptor.resource(logical_path)
        except CommonsDatapackageError as error:
            if error.reason.startswith("no resource with logical path"):
                return None
            raise
        file_path = dp_path.parent / resource.path
        if not file_path.is_file():
            return None
        actual_hash, actual_bytes = stream_sha256_and_bytes(file_path)
        if actual_hash != resource.hash:
            raise CommonsError(f"{file_path}: hash mismatch, expected {resource.hash}, got {actual_hash}")
        if resource.bytes is not None and actual_bytes != resource.bytes:
            raise CommonsError(f"{file_path}: byte count mismatch, expected {resource.bytes}, got {actual_bytes}")
        return file_path

    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        decl = _variant_decl(fm)
        if not _row_layer_decl_is_usable(decl):
            continue
        assert isinstance(decl, dict)
        locator = decl["locator"]
        assert isinstance(locator, dict)
        path = fm.get("_path")
        ident = fm.get("id", "?")
        idc = fm.get("identity_context") or {}
        assembly = idc.get("assembly") if isinstance(idc, dict) else None
        seqcol = assembly.get("seqcol_digest") if isinstance(assembly, dict) else None
        if not isinstance(seqcol, str) or not seqcol.strip():
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: variant row minting requires identity_context.assembly.seqcol_digest",
                "identity.variant-no-assembly",
            )
            continue

        fmt = str(locator["format"]).lower()
        rsid_sqlite_path: Path | None = None
        if fmt == "rsid":
            try:
                rsid_sqlite_path = resolve(str(locator["registry"]), SQLITE_RESOURCE).path
            except CommonsError as error:
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: variant rsID registry unavailable; row VRS IDs cannot be minted: {error}",
                    "identity.variant-registry-unavailable",
                )
                continue

        try:
            resource_path = locate_resource(fm, str(locator["resource"]))
        except (CommonsError, ValueError, OSError) as error:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: variant resource {locator['resource']!r} is invalid: {error}",
                "identity.variant-resource-invalid",
            )
            continue
        if resource_path is None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: variant resource {locator['resource']!r} unavailable; row VRS IDs cannot be minted",
                "identity.variant-resource-unavailable",
            )
            continue

        minted = 0
        defects: Counter[str] = Counter()
        delimiter = "\t" if resource_path.suffix == ".tsv" else ","
        invalid_resource: str | None = None
        try:
            with resource_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle, delimiter=delimiter, strict=True)
                missing = _missing_required_columns(reader.fieldnames, locator, fmt)
                if missing:
                    invalid_resource = f"missing required column {missing[0]!r}"
                for row_number, row in enumerate(reader, start=2):
                    if invalid_resource is not None:
                        break
                    if None in row:
                        invalid_resource = f"ragged row {row_number}: extra values with no header"
                        break
                    try:
                        expr = _row_expr(row, locator, fmt)
                        if fmt == "rsid":
                            if rsid_sqlite_path is None:
                                raise TypeError("rsID SQLite path was not resolved")
                            ref_filter, alt_filter = _rsid_allele_filter(row, locator)
                            # sqlite_path is pre-resolved once per dataset, so registry is
                            # intentionally omitted here: resolve_rsid only consults registry
                            # as a fallback when sqlite_path is None.
                            result = vrs_id_from_rsid(
                                expr,
                                assembly_seqcol=seqcol,
                                sqlite_path=rsid_sqlite_path,
                                ref=ref_filter,
                                alt=alt_filter,
                            )
                        else:
                            result = vrs_id(expr, fmt=fmt, assembly_seqcol=seqcol)
                    except ValueError as error:
                        invalid_resource = f"row {row_number}: {error}"
                        break
                    if isinstance(result, VariantMatch):
                        minted += 1
                    elif isinstance(result, VariantDefect):
                        defects[result.reason] += 1
                    else:
                        helper = "vrs_id_from_rsid" if fmt == "rsid" else "vrs_id"
                        raise TypeError(f"{helper} returned unsupported result {type(result).__name__}")
        except sqlite3.Error as error:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: variant rsID registry unavailable; row VRS IDs cannot be minted: {error}",
                "identity.variant-registry-unavailable",
            )
            continue
        except (SequenceStoreError, VariantStoreUnavailable) as error:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: variant store unavailable; row VRS IDs cannot be minted: {error}",
                "identity.variant-store-unavailable",
            )
            continue
        except UnicodeDecodeError as error:
            invalid_resource = f"cannot decode as UTF-8: {error}"
        except csv.Error as error:
            invalid_resource = f"malformed delimited text: {error}"
        if invalid_resource is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: variant resource {locator['resource']!r} is invalid: {invalid_resource}",
                "identity.variant-resource-invalid",
            )
            continue

        if defects:
            counts = ", ".join(f"{reason}={count}" for reason, count in sorted(defects.items()))
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: variant rows unresolved: minted={minted}; defects: {counts}",
                "identity.variant-rows-unresolved",
            )
        else:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: variant rows minted: minted={minted}",
                "identity.variant-rows-minted",
            )


def _row_layer_decl_is_usable(decl: Any) -> bool:
    if not isinstance(decl, dict):
        return False
    if tier_declaration_defect(decl) is not None:
        return False
    if decl["namespace"] not in _SUPPORTED:
        return False
    if decl.get("resolution_status") == "declared_unresolved":
        return False
    locator = decl.get("locator")
    if _locator_defect(locator) is not None:
        return False
    assert isinstance(locator, dict)
    return str(locator["format"]).lower() in _ROW_MINTING_FORMATS


def _missing_required_columns(fieldnames: Sequence[str] | None, locator: dict[str, Any], fmt: str) -> list[str]:
    present = set(fieldnames or [])
    return [column for column in _required_columns(locator, fmt) if column not in present]


def _required_columns(locator: dict[str, Any], fmt: str) -> list[str]:
    if fmt == "vcf":
        columns = locator["columns"]
        return [str(columns[key]) for key in ("chrom", "pos", "ref", "alt")]
    if fmt == "rsid":
        required = [str(locator["column"])]
        allele_columns = locator.get("allele_columns")
        if isinstance(allele_columns, dict):
            required.extend([str(allele_columns["ref"]), str(allele_columns["alt"])])
        return required
    return [str(locator["column"])]


def _row_expr(row: dict[str | None, str | list[str] | None], locator: dict[str, Any], fmt: str) -> str:
    if fmt == "vcf":
        columns = locator["columns"]
        return "-".join(_required_value(row, str(columns[key])) for key in ("chrom", "pos", "ref", "alt"))
    return _required_value(row, str(locator["column"]))


def _rsid_allele_filter(
    row: dict[str | None, str | list[str] | None],
    locator: dict[str, Any],
) -> tuple[str | None, str | None]:
    allele_columns = locator.get("allele_columns")
    if not isinstance(allele_columns, dict):
        return None, None
    return (
        _required_value(row, str(allele_columns["ref"])),
        _required_value(row, str(allele_columns["alt"])),
    )


def _required_value(row: dict[str | None, str | list[str] | None], column: str) -> str:
    value = row.get(column)
    if value is None:
        raise ValueError(f"missing value for column {column!r}")
    if not isinstance(value, str):
        raise ValueError(f"non-scalar value for column {column!r}")
    return value
