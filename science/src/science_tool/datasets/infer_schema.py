"""science datasets infer-schema: a safe schema-authoring scaffold (Spec 3).

Infers a resource's observed shape (field names + coarse Frictionless types) from its
produced table. Emits a diff-vs-existing plus a human review report; with --write applies
ONLY the names+types patch under strict guards. It never infers build-fatal invariants
(constraints, keys, foreignKeys, qa) — those are recommended in the report, authored by a
human. See docs/user-guide/entities.md.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pandas as pd
import yaml
from pandas.api import types as pdt
from pydantic import ValidationError

from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues

_DESCRIPTOR_NAMES = ("datapackage.json", "datapackage.yaml", "datapackage.yml")
_FMT_BY_SUFFIX = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


class _RoundTripSafeLoader(yaml.SafeLoader):
    """SafeLoader with the implicit *timestamp* resolver removed, so an unquoted ISO-8601
    value (e.g. ``provenance.retrieved``) loads as a plain ``str`` and round-trips faithfully
    through load→dump instead of being coerced to ``datetime`` (which drops the ``T`` separator
    and changes the type). Other implicit scalars (int/float/bool/null) resolve normally —
    they round-trip without loss."""


_RoundTripSafeLoader.yaml_implicit_resolvers = {
    ch: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class InferSchemaError(Exception):
    """Any user-facing infer-schema failure (the CLI maps it to a clean error exit)."""


def load_descriptor(path: Path) -> tuple[dict, str]:
    """Load a datapackage descriptor mapping + its format ('json'|'yaml').

    `path` may be the descriptor file or a directory containing one. The descriptor is read
    as a plain mapping (json.load / yaml.safe_load), independent of the commons
    canonical-datapackage parser.
    """
    if path.is_dir():
        for name in _DESCRIPTOR_NAMES:
            candidate = path / name
            if candidate.exists():
                path = candidate
                break
        else:
            raise InferSchemaError(f"no datapackage descriptor found in {path}")
    fmt = _FMT_BY_SUFFIX.get(path.suffix)
    if fmt is None:
        raise InferSchemaError(
            f"unsupported descriptor extension {path.suffix!r} (want .json/.yaml/.yml)"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InferSchemaError(f"cannot read descriptor {path}: {exc}") from exc
    try:
        mapping = json.loads(text) if fmt == "json" else yaml.load(text, Loader=_RoundTripSafeLoader)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise InferSchemaError(f"malformed {fmt} descriptor {path}: {exc}") from exc
    if not isinstance(mapping, dict):
        raise InferSchemaError(f"descriptor {path} top level is not a mapping")
    return mapping, fmt


def _render_descriptor(mapping: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(mapping, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(mapping, sort_keys=True, default_flow_style=False, allow_unicode=True)


def dump_descriptor(mapping: dict, path: Path, fmt: str) -> None:
    """Atomically write the descriptor, canonically re-rendered in its own format.

    Canonical = sorted keys, deterministic output. Formatting/comments are not preserved.
    """
    text = _render_descriptor(mapping, fmt)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".infer-schema-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def resolve_resource(pkg: dict, resource: str) -> tuple[dict, int]:
    """Resolve `resource` against resources[]: by name first, then by path.

    Ambiguity (a name matching >1 resource, or a path-fallback matching >1 resource) is an
    error — never a silent pick. A name match is primary and short-circuits path matching.
    """
    resources = pkg.get("resources")
    if not isinstance(resources, list) or not resources:
        raise InferSchemaError("descriptor has no resources[] to resolve against")
    by_name = [(i, r) for i, r in enumerate(resources) if r.get("name") == resource]
    if len(by_name) > 1:
        raise InferSchemaError(f"resource name {resource!r} is ambiguous (matches {len(by_name)})")
    if len(by_name) == 1:
        i, r = by_name[0]
        return r, i
    by_path = [(i, r) for i, r in enumerate(resources) if r.get("path") == resource]
    if len(by_path) > 1:
        raise InferSchemaError(f"resource path {resource!r} is ambiguous (matches {len(by_path)})")
    if len(by_path) == 1:
        i, r = by_path[0]
        return r, i
    raise InferSchemaError(f"no resource named or pathed {resource!r} in descriptor")


@dataclass
class InferredField:
    name: str
    type: str
    mixed: bool = False


def coarse_type(series: pd.Series) -> str:
    """Map a pandas column to a coarse Frictionless type (used for CSV, which has no embedded
    schema). Conservative: anything not clearly int/float/bool/datetime — including all-null
    and mixed object columns — is 'string'."""
    if series.notna().sum() == 0:
        return "string"
    if pdt.is_bool_dtype(series):
        return "boolean"
    if pdt.is_integer_dtype(series):
        return "integer"
    if pdt.is_float_dtype(series):
        return "number"
    if pdt.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def coarse_type_from_arrow(arrow_type) -> str:
    """Map a pyarrow DataType to a coarse Frictionless type (authoritative for parquet)."""
    import pyarrow as pa

    if pa.types.is_boolean(arrow_type):
        return "boolean"
    if pa.types.is_integer(arrow_type):
        return "integer"
    if pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type):
        return "number"
    if pa.types.is_temporal(arrow_type):
        return "datetime"
    return "string"


def is_mixed_object(series: pd.Series) -> bool:
    """True when an object column holds >1 distinct python base type among non-null values."""
    if not pdt.is_object_dtype(series):
        return False
    kinds = {type(v) for v in series.dropna().tolist()}
    return len(kinds) > 1


def read_table_sample(table_path: Path, sample: int) -> pd.DataFrame:
    """Read up to `sample` rows of the table as a DataFrame (CSV/TSV/parquet).

    Used for report statistics and for CSV type inference. NOT the source of truth for
    parquet types — see observed_fields, which reads the Arrow schema instead.
    """
    suffix = table_path.suffix.lower()
    if not table_path.exists():
        raise InferSchemaError(f"table file not found: {table_path}")
    try:
        if suffix == ".parquet":
            import pyarrow.parquet as pq

            pf = pq.ParquetFile(str(table_path))
            batch = next(pf.iter_batches(batch_size=max(sample, 1)), None)
            return batch.to_pandas() if batch is not None else pd.DataFrame()
        if suffix in (".csv", ".tsv"):
            sep = "\t" if suffix == ".tsv" else ","
            return pd.read_csv(table_path, nrows=sample, sep=sep)
    except Exception as exc:  # malformed table is a user-facing failure, not a crash
        raise InferSchemaError(f"cannot read table {table_path}: {exc}") from exc
    raise InferSchemaError(f"unsupported table format {suffix!r} (want .parquet/.csv/.tsv)")


def infer_fields(df: pd.DataFrame) -> list[InferredField]:
    """Infer (name, coarse type, mixed-flag) from a DataFrame (the CSV path)."""
    fields: list[InferredField] = []
    for col in df.columns:
        series = cast(pd.Series, df[col])
        fields.append(InferredField(name=str(col), type=coarse_type(series), mixed=is_mixed_object(series)))
    return fields


def observed_fields(table_path: Path, sample: int) -> list[InferredField]:
    """Authoritative (name, type) per column. Parquet → Arrow schema metadata (no row scan;
    robust to empty/all-null/nullable columns). CSV/TSV → coarse inference over a sample."""
    if table_path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq

        if not table_path.exists():
            raise InferSchemaError(f"table file not found: {table_path}")
        schema = pq.ParquetFile(str(table_path)).schema_arrow
        return [
            InferredField(name=schema.field(i).name, type=coarse_type_from_arrow(schema.field(i).type))
            for i in range(len(schema))
        ]
    return infer_fields(read_table_sample(table_path, sample))


@dataclass
class DiffEntry:
    name: str
    action: str  # "add" | "change" | "same" | "remove"
    old_type: str | None
    new_type: str | None
    conflict: bool = False


def diff_schema(existing_fields: list[dict], inferred: list[InferredField]) -> list[DiffEntry]:
    """Diff inferred fields against an existing schema's fields. See §6.2 conflict rule."""
    existing = {f.get("name"): f for f in existing_fields}
    inferred_names = {i.name for i in inferred}
    entries: list[DiffEntry] = []
    for inf in inferred:
        if inf.name not in existing:
            entries.append(DiffEntry(inf.name, "add", None, inf.type))
            continue
        old = existing[inf.name].get("type")
        if old is None or old == "any":
            entries.append(DiffEntry(inf.name, "change", old, inf.type, conflict=False))
        elif old == inf.type:
            entries.append(DiffEntry(inf.name, "same", old, inf.type, conflict=False))
        else:
            entries.append(DiffEntry(inf.name, "change", old, inf.type, conflict=True))
    for name, fld in existing.items():
        if name not in inferred_names:
            entries.append(DiffEntry(str(name), "remove", fld.get("type"), None))
    return entries


ENUM_MAX_DISTINCT = 20
HIGH_CARDINALITY_FRACTION = 0.9
STRING_SENTINELS = {"NA", "N/A", "null", "NULL", "NaN", "-", "?"}


@dataclass
class Recommendation:
    kind: str  # identifier|enum|required|unique|missing_sentinel|bound
    column: str
    message: str


@dataclass
class ReportWarning:
    column: str
    message: str


@dataclass
class ReviewReport:
    recommendations: list[Recommendation] = field(default_factory=list)
    warnings: list[ReportWarning] = field(default_factory=list)
    sample_rows: int = 0


def build_report(df: pd.DataFrame, inferred: list[InferredField]) -> ReviewReport:
    """Build the human-facing review report from a sample. Recommendations are candidate
    invariants the author may choose to add by hand; they are NEVER emitted into a schema."""
    rep = ReviewReport(sample_rows=int(len(df)))
    by_name = {i.name: i for i in inferred}
    for col in df.columns:
        s = cast(pd.Series, df[col])
        name = str(col)
        nonnull = s.dropna()
        n_nonnull = int(len(nonnull))
        n_null = int(len(s) - n_nonnull)
        distinct = int(nonnull.nunique())
        ftype = by_name[name].type if name in by_name else "string"

        if n_null == 0 and len(s) > 0:
            rep.recommendations.append(Recommendation(
                "required", name, f"no nulls in {len(s)} sampled rows — consider constraints.required"))
        is_unique = n_nonnull > 0 and distinct == n_nonnull
        if is_unique and n_null == 0 and ftype in ("string", "integer"):
            rep.recommendations.append(Recommendation(
                "identifier", name, "unique & non-null in sample — consider primaryKey"))
        elif is_unique:
            rep.recommendations.append(Recommendation(
                "unique", name, "all sampled values distinct — consider constraints.unique"))
        if (ftype in ("string", "integer", "boolean") and 2 <= distinct <= ENUM_MAX_DISTINCT
                and n_nonnull and not is_unique):
            rep.recommendations.append(Recommendation(
                "enum", name, f"low cardinality ({distinct} distinct) — consider constraints.enum"))
        if ftype in ("number", "integer", "datetime") and n_nonnull:
            rep.recommendations.append(Recommendation(
                "bound", name,
                f"observed range [{nonnull.min()!r}, {nonnull.max()!r}] in sample — "
                "possible minimum/maximum (sample-derived, NOT a constraint)"))

        # missing-sentinel: recurring out-of-band tokens
        sentinels = {str(v) for v in nonnull.unique()} & STRING_SENTINELS
        for tok in sorted(sentinels):
            if int((nonnull.astype(str) == tok).sum()) > 1:
                rep.recommendations.append(Recommendation(
                    "missing_sentinel", name,
                    f"recurring sentinel-like value {tok!r} — consider table missingValues"))

        # warnings
        if by_name.get(name) and by_name[name].mixed:
            rep.warnings.append(ReportWarning(name, "mixed python types in sample — typed as string"))
        if n_null:
            rep.warnings.append(ReportWarning(name, f"{n_null}/{len(s)} null in sample (nullable)"))
        if ftype == "string" and n_nonnull and distinct > HIGH_CARDINALITY_FRACTION * n_nonnull and not is_unique:
            rep.warnings.append(ReportWarning(name, "high-cardinality string (likely free text)"))
    return rep


@dataclass
class InferResult:
    fmt: str
    pkg: dict
    res_index: int
    descriptor_path: Path
    table_path: Path
    diff: list[DiffEntry]
    report: ReviewReport
    inferred: list[InferredField]


def infer_schema_result(dp_path: Path, resource: str, sample: int) -> InferResult:
    """Read-only pipeline: load descriptor, resolve resource, read table, infer, diff, report."""
    mapping, fmt = load_descriptor(dp_path)
    descriptor_path = dp_path if dp_path.is_file() else _resolved_descriptor_path(dp_path)
    res, idx = resolve_resource(mapping, resource)
    rel = res.get("path")
    if not rel:
        raise InferSchemaError(f"resource {resource!r} has no path")
    table_path = descriptor_path.parent / rel
    df = read_table_sample(table_path, sample)          # sample for the report stats
    inferred = observed_fields(table_path, sample)      # authoritative names+types (Arrow for parquet)
    existing_fields = (res.get("schema") or {}).get("fields") or []
    diff = diff_schema(existing_fields, inferred)
    report = build_report(df, inferred)
    return InferResult(fmt, mapping, idx, descriptor_path, table_path, diff, report, inferred)


def _resolved_descriptor_path(directory: Path) -> Path:
    for name in _DESCRIPTOR_NAMES:
        candidate = directory / name
        if candidate.exists():
            return candidate
    raise InferSchemaError(f"no datapackage descriptor found in {directory}")


def proposed_schema(inferred: list[InferredField]) -> dict:
    """The machine-safe patch: names + types ONLY."""
    return {"schema": {"fields": [{"name": i.name, "type": i.type} for i in inferred]}}


def render_diff_rows(diff: list[DiffEntry]) -> list[dict]:
    rows: list[dict] = []
    glyph = {"add": "+", "change": "~", "same": "=", "remove": "-"}
    for d in diff:
        if d.action == "change":
            detail = f"{d.old_type or '(none)'} -> {d.new_type}" + (" CONFLICT" if d.conflict else "")
        elif d.action == "add":
            detail = f"type={d.new_type}"
        elif d.action == "remove":
            detail = "in schema, not in file"
        else:
            detail = f"type={d.new_type}"
        rows.append({"action": d.action, "glyph": glyph[d.action], "field": d.name, "details": detail})
    return rows


def render_report_rows(report: ReviewReport) -> list[dict]:
    rows = [{"kind": r.kind, "column": r.column, "note": r.message,
             "label": "recommendation — not emitted as invariant"}
            for r in report.recommendations]
    rows += [{"kind": "warning", "column": w.column, "note": w.message, "label": "warning"}
             for w in report.warnings]
    return rows


def report_to_yaml(report: ReviewReport) -> str:
    obj = {
        "disclaimer": "recommendations are candidate invariants only — NOT emitted as invariant",
        "sample_rows": report.sample_rows,
        "recommendations": [{"kind": r.kind, "column": r.column, "message": r.message}
                            for r in report.recommendations],
        "warnings": [{"column": w.column, "message": w.message} for w in report.warnings],
    }
    return yaml.safe_dump(obj, sort_keys=False, default_flow_style=False, allow_unicode=True)


def result_to_json(result: InferResult) -> str:
    obj = {
        "patch": proposed_schema(result.inferred),
        "diff": [{"name": d.name, "action": d.action, "old_type": d.old_type,
                  "new_type": d.new_type, "conflict": d.conflict} for d in result.diff],
        "report": {
            "sample_rows": result.report.sample_rows,
            "recommendations": [{"kind": r.kind, "column": r.column, "message": r.message}
                                for r in result.report.recommendations],
            "warnings": [{"column": w.column, "message": w.message} for w in result.report.warnings],
        },
    }
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write_patch(result: InferResult) -> None:
    """Apply ONLY the names+types patch, under the §6 guards, then atomically write.

    Refuses (and writes nothing) on a type-disagreement conflict or a descriptor that would
    parse invalid as a whole package. Authored field- and table-level metadata is preserved.
    """
    conflicts = [d.name for d in result.diff if d.conflict]
    if conflicts:
        raise InferSchemaError(
            f"type conflict on field(s) {conflicts} — authored type differs from inferred; "
            "resolve by hand (the tool never overwrites an authored type)")

    pkg = copy.deepcopy(result.pkg)
    res = pkg["resources"][result.res_index]
    schema = res.setdefault("schema", {})
    fields = schema.setdefault("fields", [])
    by_name = {f.get("name"): f for f in fields}
    for d in result.diff:
        if d.action == "add":
            fields.append({"name": d.name, "type": d.new_type})
        elif d.action == "change":  # conflicts already excluded → safe type fill
            by_name[d.name]["type"] = d.new_type
        # "same"/"remove": untouched (remove is reported, never auto-applied)

    # Whole-package post-validation (cross-resource FK resolution needs every descriptor).
    descriptors: list[ResourceDescriptor] = []
    for r in pkg["resources"]:
        try:
            descriptors.append(ResourceDescriptor.model_validate(r))
        except ValidationError as exc:
            raise InferSchemaError(f"resulting descriptor is invalid: {exc.errors()[0]}") from exc
    issues = package_consistency_issues(descriptors)
    if issues:
        raise InferSchemaError("resulting package is inconsistent: " + "; ".join(issues))

    written = {f.get("name") for f in fields}
    missing = {i.name for i in result.inferred} - written
    if missing:
        raise InferSchemaError(f"internal: inferred columns missing after patch: {sorted(missing)}")

    dump_descriptor(pkg, result.descriptor_path, result.fmt)
