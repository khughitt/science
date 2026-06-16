# science/qa/src/science_qa/runner.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from science_qa.aspects import CHECK_REQUIRED, CheckSpec, Invocation
from science_qa.compile import CompileError, merge_configs, schema_to_config
from science_qa.config import QAConfig
from science_qa.context import Context, TableContext
from science_qa.coverage import (
    STATUS_BLOCKED, STATUS_EMPTY, STATUS_NA, STATUS_RAN, Coverage, CoverageEntry,
)
from science_qa.dispositions import reconcile_dispositions
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag
from science_qa.extensions import load_project_local
from science_qa.program import resolve_program
from science_qa.report import write_reports
from science_qa.selectors import resolve_columns


class RunnerError(Exception):
    """Raised on a static program/substrate incompatibility (fail early)."""


@dataclass
class RunResult:
    flags: list[Flag]
    structural_failed: bool
    coverage: Coverage
    rows_checked: int


def _read_table(table_path: Path) -> pd.DataFrame:
    if table_path.suffix == ".parquet":
        return pd.read_parquet(table_path)
    if table_path.suffix in {".csv", ".tsv"}:
        return pd.read_csv(table_path, sep="\t" if table_path.suffix == ".tsv" else ",")
    raise ValueError(f"unsupported table format: {table_path.suffix}")


def _invocations(spec: CheckSpec, config: QAConfig) -> list[Invocation]:
    if spec.kind == CHECK_REQUIRED:
        return [Invocation(requires=spec.requires)]
    return spec.expand(config) if spec.expand else []


def _missing_required(spec: CheckSpec, inv: Invocation, table: pd.DataFrame) -> list[str]:
    return [c for c in inv.requires if c not in table.columns]


def run_qa(config_path: Path, table_path: Path, report_dir: Path) -> RunResult:
    return _run_with_config(QAConfig.from_file(config_path), table_path, report_dir)


def run_qa_datapackage(datapackage_path: Path, resource_name: str, report_dir: Path,
                       runknobs_path: Path | None = None) -> RunResult:
    package = json.loads(Path(datapackage_path).read_text(encoding="utf-8"))
    resource = next((r for r in package.get("resources", []) if r.get("name") == resource_name), None)
    if resource is None:
        raise CompileError(f"resource {resource_name!r} not found in {datapackage_path}")
    pkg_dir = Path(datapackage_path).parent
    config = schema_to_config(resource, pkg_dir, package)
    if runknobs_path is not None:
        config = merge_configs(config, QAConfig.from_file(runknobs_path, require_program=False))
    if not config.program:
        config.program = "tabular"
    return _run_with_config(config, pkg_dir / resource["path"], report_dir)


def _evaluate(config: QAConfig, table_path: Path) -> RunResult:
    """Compile-independent core: resolve program, read table, run checks.

    Returns a RunResult (incl. rows_checked = len(table)). Writes nothing, reconciles
    nothing — so the package runner can call it per-resource and write ONE report."""
    program = resolve_program(config.program)
    built_in_ids = {spec.check_id for spec in program.checks}
    checks = [*program.checks, *load_project_local(config.project_local, reserved_check_ids=built_in_ids)]
    table = _read_table(table_path)

    # static program <-> substrate validation, before any context is built
    for spec in checks:
        if spec.accepts is not program.substrate:
            raise RunnerError(f"check {spec.check_id} accepts {spec.accepts.__name__}, "
                              f"program {program.name} binds {program.substrate.__name__}")

    flags: list[Flag] = []
    coverage = Coverage()

    for spec in checks:
        invs = _invocations(spec, config)
        if spec.expand is not None and not invs:
            coverage.unconfigured_families.append(spec.check_id)
            continue
        for inv in invs:
            entry = _run_invocation(spec, inv, table, config, flags)
            coverage.entries.append(entry)

    structural_failed = any(f.severity == SEVERITY_STRUCTURAL for f in flags)
    return RunResult(flags=flags, structural_failed=structural_failed,
                     coverage=coverage, rows_checked=len(table))


def _run_with_config(config: QAConfig, table_path: Path, report_dir: Path) -> RunResult:
    result = _evaluate(config, table_path)
    write_reports(result.flags, report_dir=report_dir,
                  rows_checked=result.rows_checked, coverage=result.coverage)
    distribution_ids = [f.flag_id for f in result.flags if f.severity == SEVERITY_DISTRIBUTION]
    reconcile_dispositions(report_dir, distribution_ids)
    return result


def _run_invocation(spec: CheckSpec, inv: Invocation, table: pd.DataFrame,
                    config: QAConfig, flags: list[Flag]) -> CoverageEntry:
    missing = _missing_required(spec, inv, table)
    if missing:
        if inv.optional:
            return CoverageEntry(spec.check_id, spec.aspect, STATUS_NA, [], 0)  # declared-optional input absent
        if spec.kind == CHECK_REQUIRED:
            # coverage-only: the absent column's structural flag is emitted by the owning
            # required_column check (program invariant), so we DON'T flag here -> no duplicates.
            return CoverageEntry(spec.check_id, spec.aspect, STATUS_BLOCKED, [], 0)
        # a configured family item names a column absent from the table -> fail early (exit 2), per B1
        raise RunnerError(f"{spec.check_id} references column(s) absent from table: {missing}")

    columns = _resolve(spec, inv, table, config)
    if (inv.columns is not None or spec.selector is not None) and not columns:
        return CoverageEntry(spec.check_id, spec.aspect, STATUS_EMPTY, [], 0)

    ctx: Context = TableContext(table=table, columns=columns)
    if not isinstance(ctx, spec.accepts):
        raise RunnerError(f"context {type(ctx).__name__} incompatible with {spec.check_id}")

    # merge this aspect's configured params under the invocation's explicit params
    params = dict(inv.params)
    for k, v in config.aspect_params.get(spec.aspect, {}).items():
        params.setdefault(k, v)
    produced = spec.fn(ctx, params)
    flags.extend(produced)
    return CoverageEntry(spec.check_id, spec.aspect, STATUS_RAN, columns, len(produced))


def _resolve(spec: CheckSpec, inv: Invocation, table: pd.DataFrame, config: QAConfig) -> list[str]:
    if inv.columns is not None:
        return [c for c in inv.columns if c in table.columns]
    if spec.selector is not None:
        return resolve_columns(spec.selector, table, column_sets=config.column_sets)
    # whole-table / fixed-column required checks have no column selection to record
    return []
