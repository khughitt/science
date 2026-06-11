import json

from science_qa.flags import Flag
from science_qa.report import write_reports


def _flags():
    return [
        Flag("generic", "unique_key", "SUBJECT_ID", None, "structural", "2", "0", "2 dup"),
        Flag("generic", "range", "glucose", "max", "distribution", "1", "500", "above max"),
    ]


def test_writes_json_and_md(tmp_path):
    write_reports(_flags(), report_dir=tmp_path, rows_checked=3)
    assert (tmp_path / "qa_report.json").exists()
    assert (tmp_path / "qa_report.md").exists()


def test_json_lists_flags_sorted_by_id(tmp_path):
    write_reports(_flags(), report_dir=tmp_path, rows_checked=3)
    payload = json.loads((tmp_path / "qa_report.json").read_text())
    ids = [f["flag_id"] for f in payload["flags"]]
    assert ids == ["generic/range/glucose/max", "generic/unique_key/SUBJECT_ID/-"]
    assert payload["structural_count"] == 1
    assert payload["distribution_count"] == 1


def test_output_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    write_reports(_flags(), report_dir=a, rows_checked=3)
    write_reports(list(reversed(_flags())), report_dir=b, rows_checked=3)
    assert (a / "qa_report.json").read_bytes() == (b / "qa_report.json").read_bytes()
    assert (a / "qa_report.md").read_bytes() == (b / "qa_report.md").read_bytes()
