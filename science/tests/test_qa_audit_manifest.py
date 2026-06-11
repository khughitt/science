import json
from pathlib import Path

import yaml

from science_tool.qa_audit.manifest import load_qa_artifacts


def _manifest(run_dir: Path, resources):
    (run_dir / "datapackage.yaml").write_text(yaml.safe_dump({"name": "run", "resources": resources}))


def _report(path: Path, distribution_ids):
    path.write_text(json.dumps({
        "flags": [{"flag_id": fid, "severity": "distribution"} for fid in distribution_ids]
    }))


def _dispositions(path: Path, entries):
    path.write_text(yaml.safe_dump({"dispositions": entries}))


def test_single_substrate_pairs_report_and_dispositions(tmp_path):
    _report(tmp_path / "qa_report.json", ["scrna/threshold/pct_counts_mt/max"])
    _dispositions(tmp_path / "qa_dispositions.yaml",
                  [{"flag_id": "scrna/threshold/pct_counts_mt/max", "disposition": "addressed", "change": "x"}])
    _manifest(tmp_path, [
        {"name": "qa_report", "path": "qa_report.json"},
        {"name": "qa_dispositions", "path": "qa_dispositions.yaml"},
    ])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is True
    assert flags[0].disposition == "addressed" and flags[0].change == "x"


def test_multi_substrate_aggregates(tmp_path):
    _report(tmp_path / "a.json", ["generic/range/glucose/max"])
    _report(tmp_path / "b.json", ["scrna/threshold/pct_counts_mt/max"])
    _dispositions(tmp_path / "a.yaml", [{"flag_id": "generic/range/glucose/max", "disposition": "open"}])
    _dispositions(tmp_path / "b.yaml", [{"flag_id": "scrna/threshold/pct_counts_mt/max", "disposition": "open"}])
    _manifest(tmp_path, [
        {"name": "qa_report:cells", "path": "a.json"},
        {"name": "qa_dispositions:cells", "path": "a.yaml"},
        {"name": "qa_report:bulk", "path": "b.json"},
        {"name": "qa_dispositions:bulk", "path": "b.yaml"},
    ])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is True
    assert len(flags) == 2


def test_no_qa_resources_returns_false(tmp_path):
    _manifest(tmp_path, [{"name": "data", "path": "data.parquet"}])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is False and flags == []


def test_open_flag_without_disposition_entry_defaults_open(tmp_path):
    _report(tmp_path / "qa_report.json", ["generic/range/glucose/max"])
    _manifest(tmp_path, [{"name": "qa_report", "path": "qa_report.json"}])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is True
    assert flags[0].disposition == "open"
