from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from science_qa.checks import run_distribution_checks, run_structural_checks
from science_qa.config import QAConfig
from science_qa.dispositions import reconcile_dispositions
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag
from science_qa.packs import resolve_pack
from science_qa.report import write_reports


@dataclass
class RunResult:
    flags: list[Flag]
    structural_failed: bool


def _read_table(table_path: Path) -> pd.DataFrame:
    if table_path.suffix == ".parquet":
        return pd.read_parquet(table_path)
    if table_path.suffix in {".csv", ".tsv"}:
        sep = "\t" if table_path.suffix == ".tsv" else ","
        return pd.read_csv(table_path, sep=sep)
    raise ValueError(f"unsupported table format: {table_path.suffix}")


def run_qa(config_path: Path, table_path: Path, report_dir: Path) -> RunResult:
    config = QAConfig.from_file(config_path)
    table = _read_table(table_path)

    flags: list[Flag] = []
    flags += run_structural_checks(table, config, base_dir=config_path.parent)
    flags += run_distribution_checks(table, config)
    for pack_name in config.packs:
        flags += resolve_pack(pack_name)(table, config.pack_params.get(pack_name, {}))

    write_reports(flags, report_dir=report_dir, rows_checked=len(table))
    distribution_ids = [f.flag_id for f in flags if f.severity == SEVERITY_DISTRIBUTION]
    reconcile_dispositions(report_dir, distribution_ids)

    structural_failed = any(f.severity == SEVERITY_STRUCTURAL for f in flags)
    return RunResult(flags=flags, structural_failed=structural_failed)
