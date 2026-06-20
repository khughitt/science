# science/qa/tests/test_runner.py
import json
from pathlib import Path

import pandas as pd
import pytest

from science_qa.runner import run_qa


def _cfg(tmp_path, body="qa:\n  program: scrna-qc-table\n") -> Path:
    p = tmp_path / "qa.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _table(tmp_path, df) -> Path:
    p = tmp_path / "t.parquet"
    df.to_parquet(p)
    return p


def _good_scrna():
    return pd.DataFrame({
        "total_counts": [1000, 2000, 1500],
        "n_genes_by_counts": [500, 800, 600],
        "pct_counts_mt": [5.0, 8.0, 3.0],
    })


def test_clean_table_reports_coverage_no_structural_fail(tmp_path):
    res = run_qa(_cfg(tmp_path), _table(tmp_path, _good_scrna()), tmp_path)
    assert res.structural_failed is False
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    assert cov["executable_denominator"] >= 5
    # doublet is optional and absent -> not-applicable
    statuses = {e["check_id"]: e["status"] for e in cov["entries"]}
    assert statuses["scrna-qc-table/doublet_ceiling"] == "not-applicable"


def test_missing_required_column_blocks_and_structural_fails(tmp_path):
    df = _good_scrna().drop(columns=["pct_counts_mt"])
    res = run_qa(_cfg(tmp_path), _table(tmp_path, df), tmp_path)
    assert res.structural_failed is True
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    statuses = {e["check_id"]: e["status"] for e in cov["entries"]}
    assert statuses["scrna-qc-table/gates"] == "blocked"


def test_b1_parity_mito_gate_fires_with_same_severity(tmp_path):
    df = _good_scrna()
    df.loc[0, "pct_counts_mt"] = 30.0  # exceeds default max_mito_pct 20
    run_qa(_cfg(tmp_path), _table(tmp_path, df), tmp_path)
    flags = json.loads((tmp_path / "qa_report.json").read_text())["flags"]
    mito = [f for f in flags if f["flag_id"] == "scrna-qc-table/threshold/pct_counts_mt/max"]
    assert mito and mito[0]["severity"] == "distribution"


def test_b1_parity_rehomed_flag_ids(tmp_path):
    # scrna non_negative -> numeric-column/polarity ; all_zero_cell -> gene-expression-qc-table/degenerate_cell
    df = _good_scrna()
    df.loc[0, "total_counts"] = -1          # negative library size -> polarity (structural)
    df.loc[1, "total_counts"] = 0           # all-zero cell -> degenerate_cell (structural)
    df.loc[1, "n_genes_by_counts"] = 0
    cfg = _cfg(tmp_path, "qa:\n  program: scrna-qc-table\n  polarity: [total_counts]\n")
    res = run_qa(cfg, _table(tmp_path, df), tmp_path)
    ids = {f["flag_id"]: f["severity"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert ids.get("numeric-column/polarity/total_counts/-") == "structural"
    assert ids.get("gene-expression-qc-table/degenerate_cell/total_counts+n_genes_by_counts/-") == "structural"
    assert res.structural_failed is True


def test_unconfigured_family_recorded_not_errored(tmp_path):
    cov = json.loads(_run_and_read(tmp_path))["coverage"]
    assert "tabular/categoricals" in cov["unconfigured_families"]


def _run_and_read(tmp_path) -> str:
    run_qa(_cfg(tmp_path), _table(tmp_path, _good_scrna()), tmp_path)
    return (tmp_path / "qa_report.json").read_text()


def test_project_local_check_runs(tmp_path, monkeypatch):
    (tmp_path / "ext_runs.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "from science_qa.flags import Flag, SEVERITY_DISTRIBUTION\n"
        "def _fn(ctx, params):\n"
        "    return [Flag('project-local', 'marker', 'table', None, SEVERITY_DISTRIBUTION, '1', '0', 'ran')]\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, TableContext, _fn)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _cfg(tmp_path, "qa:\n  program: scrna-qc-table\n  project_local: ['ext_runs:marker']\n")
    run_qa(cfg, _table(tmp_path, _good_scrna()), tmp_path)
    ids = [f["flag_id"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]]
    assert "project-local/marker/table/-" in ids


def test_project_local_wrong_context_rejected(tmp_path, monkeypatch):
    from science_qa.runner import RunnerError
    (tmp_path / "ext_bad_ctx.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "class OtherContext: pass\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, OtherContext, lambda c, p: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _cfg(tmp_path, "qa:\n  program: scrna-qc-table\n  project_local: ['ext_bad_ctx:marker']\n")
    with pytest.raises(RunnerError):
        run_qa(cfg, _table(tmp_path, _good_scrna()), tmp_path)


def test_required_check_coverage_records_no_column_selection(tmp_path):
    # a fixed-column required check operates on specific columns, not a selection ->
    # its coverage entry records no resolved column selection (not the whole table)
    run_qa(_cfg(tmp_path), _table(tmp_path, _good_scrna()), tmp_path)
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    entry = next(e for e in cov["entries"] if e["check_id"] == "gene-expression-qc-table/library_size_positive")
    assert entry["columns"] == []


import json as _json


def _dp(tmp_path, resource: dict, df) -> Path:
    df.to_parquet(tmp_path / resource["path"])
    pkg = {"name": "p", "resources": [resource]}
    (tmp_path / "datapackage.json").write_text(_json.dumps(pkg))
    return tmp_path / "datapackage.json"


def test_datapackage_zero_config_runs_tabular_clean(tmp_path):
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "id", "type": "integer", "constraints": {"required": True, "unique": True}}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"id": [1, 2, 3]}))
    result = run_qa_datapackage(dp, "obs", tmp_path)
    assert result.structural_failed is False
    cov = json.loads((tmp_path / "qa_report.json").read_text())["coverage"]
    assert cov["executable_denominator"] >= 1


def test_datapackage_bounds_violation_is_structural(tmp_path):
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "p", "type": "number", "constraints": {"minimum": 0}}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"p": [-1.0, 0.5, 2.0]}))
    result = run_qa_datapackage(dp, "obs", tmp_path)
    assert result.structural_failed is True
    ids = {f["flag_id"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert "numeric-column/bounds/p/minimum" in ids


def test_datapackage_with_runknobs_overlay(tmp_path):
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "v", "type": "number"}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"v": [-1.0, 1.0]}))
    (tmp_path / "qa.yaml").write_text("qa:\n  polarity: [v]\n")  # no program: -> tabular default
    run_qa_datapackage(dp, "obs", tmp_path, runknobs_path=tmp_path / "qa.yaml")
    ids = {f["flag_id"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert "numeric-column/polarity/v/-" in ids  # polarity came from the run-knob yaml


def test_datapackage_unknown_resource_errors(tmp_path):
    from science_qa.compile import CompileError
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet", "schema": {"fields": [{"name": "id"}]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"id": [1]}))
    with pytest.raises(CompileError, match="resource"):
        run_qa_datapackage(dp, "missing", tmp_path)


def test_datapackage_numeric_missing_sentinel_fires_structural(tmp_path):
    # end-to-end: a schema-declared numeric missingValue ("-999") must actually flag a
    # surviving -999 in a numeric column — i.e. the compiler's string sentinel is coerced
    # so numeric-column/missing_sentinel (numeric-only) matches it.
    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "v", "type": "number"}], "missingValues": ["-999"]}}
    dp = _dp(tmp_path, res, pd.DataFrame({"v": [1.0, -999.0, 2.0]}))
    result = run_qa_datapackage(dp, "obs", tmp_path)
    assert result.structural_failed is True
    ids = {f["flag_id"] for f in json.loads((tmp_path / "qa_report.json").read_text())["flags"]}
    assert "numeric-column/missing_sentinel/v/-" in ids


def test_run_qa_datapackage_exposes_rows_checked(tmp_path):
    import json as _json

    from science_qa.runner import run_qa_datapackage
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "id", "type": "integer"}]}}
    pd.DataFrame({"id": [1, 2, 3, 4]}).to_parquet(tmp_path / "obs.parquet")
    (tmp_path / "datapackage.json").write_text(_json.dumps({"name": "p", "resources": [res]}))
    result = run_qa_datapackage(tmp_path / "datapackage.json", "obs", tmp_path)
    assert result.rows_checked == 4


def test_run_qa_datapackage_reads_yaml(tmp_path):
    from science_qa.runner import run_qa_datapackage
    pd.DataFrame({"id": [1, 2, 3]}).to_parquet(tmp_path / "obs.parquet")
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: obs\n    path: obs.parquet\n    schema:\n      fields:\n"
        "        - name: id\n          type: integer\n          constraints: {required: true}\n")
    result = run_qa_datapackage(tmp_path / "datapackage.yaml", "obs", tmp_path)
    assert result.structural_failed is False and result.rows_checked == 3


def _yaml_pkg(tmp_path, body: str) -> Path:
    (tmp_path / "datapackage.yaml").write_text(body)
    return tmp_path / "datapackage.yaml"


def test_package_clean_multi_resource_ok(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"v": [0.1, 0.2]}).to_parquet(tmp_path / "b.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n"
        "  - name: b\n    path: b.parquet\n    schema: {fields: [{name: v, type: number}]}\n")
    result = run_qa_package(dp)
    assert result.package_structural_failed is False
    assert {o.name: o.status for o in result.outcomes} == {"a": "ok", "b": "ok"}


def test_package_structural_violation_fails_package(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "a.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n          constraints: {minimum: 0}\n")
    result = run_qa_package(dp)
    assert result.package_structural_failed is True
    assert result.outcomes[0].status == "fail"


def test_package_absent_data_is_blocked_not_fatal(tmp_path):
    from science_qa.runner import run_qa_package
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: missing.parquet\n    schema: {fields: [{name: id, type: integer}]}\n")
    result = run_qa_package(dp)
    assert result.package_structural_failed is False
    assert result.outcomes[0].status == "blocked" and result.outcomes[0].reason == "data file absent"


def test_package_non_tabular_is_not_applicable(tmp_path):
    from science_qa.runner import run_qa_package
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: v\n    path: v.qa_verdict.json\n")
    result = run_qa_package(dp)
    assert result.outcomes[0].status == "not-applicable" and result.outcomes[0].reason == "non-tabular"


def test_package_schemaless_tabular_is_skipped(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"x": [1]}).to_parquet(tmp_path / "a.parquet")
    dp = _yaml_pkg(tmp_path, "name: p\nresources:\n  - name: a\n    path: a.parquet\n")
    result = run_qa_package(dp)
    assert result.outcomes[0].status == "skipped" and result.outcomes[0].reason == "no schema"


def test_package_resource_selection_and_unknown(tmp_path):
    from science_qa.compile import CompileError
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"v": [1.0]}).to_parquet(tmp_path / "b.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n"
        "  - name: b\n    path: b.parquet\n    schema: {fields: [{name: v, type: number}]}\n")
    result = run_qa_package(dp, resources=["a"])
    assert [o.name for o in result.outcomes] == ["a"]
    with pytest.raises(CompileError, match="not found"):
        run_qa_package(dp, resources=["ghost"])


def test_package_report_dir_none_writes_nothing(tmp_path):
    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    dp = _yaml_pkg(tmp_path,
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n")
    run_qa_package(dp)  # report_dir=None
    assert not (tmp_path / "qa_report.json").exists()
    assert not (tmp_path / "a").exists()


def test_package_report_writes_subdirs_and_rollup(tmp_path):
    import json as _json

    from science_qa.runner import run_qa_package
    pd.DataFrame({"id": [1, 2]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "b.parquet")
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema: {fields: [{name: id, type: integer}]}\n"
        "  - name: b\n    path: b.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n          constraints: {minimum: 0}\n")
    out = tmp_path / "out"
    run_qa_package(tmp_path / "datapackage.yaml", report_dir=out)
    # per-resource subdir reports exist
    assert (out / "a" / "qa_report.json").exists()
    assert (out / "b" / "qa_report.json").exists()
    # package rollup
    rollup = _json.loads((out / "qa_report.json").read_text())
    assert rollup["package"] == "p" and rollup["package_structural_failed"] is True
    sections = {s["resource"]: s for s in rollup["resources"]}
    assert sections["b"]["status"] == "fail" and sections["b"]["flags"]
    assert sections["a"]["status"] == "ok" and sections["a"]["flags"] == []


def test_package_same_flag_id_two_resources_does_not_merge(tmp_path):
    # collision regression: identical flag_id in two resources -> separate subdir ledgers
    import json as _json

    from science_qa.runner import run_qa_package
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "a.parquet")
    pd.DataFrame({"p": [-2.0, 1.0]}).to_parquet(tmp_path / "b.parquet")
    field = ("        - name: p\n          type: number\n"
             "          constraints: {minimum: 0}\n")
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        f"  - name: a\n    path: a.parquet\n    schema:\n      fields:\n{field}"
        f"  - name: b\n    path: b.parquet\n    schema:\n      fields:\n{field}")
    out = tmp_path / "out"
    run_qa_package(tmp_path / "datapackage.yaml", report_dir=out)
    a_ids = {f["flag_id"] for f in _json.loads((out / "a" / "qa_report.json").read_text())["flags"]}
    b_ids = {f["flag_id"] for f in _json.loads((out / "b" / "qa_report.json").read_text())["flags"]}
    # same flag_id present in BOTH, each in its own resource-scoped report (not merged)
    assert "numeric-column/bounds/p/minimum" in a_ids
    assert "numeric-column/bounds/p/minimum" in b_ids
    # each resource gets its OWN disposition ledger (proves no shared/merged ledger)
    assert (out / "a" / "qa_dispositions.yaml").exists()
    assert (out / "b" / "qa_dispositions.yaml").exists()
