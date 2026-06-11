import yaml

from science_qa.dispositions import VALID_DISPOSITIONS, reconcile_dispositions


def _write(path, entries):
    path.write_text(yaml.safe_dump({"dispositions": entries}, sort_keys=True))


def test_scaffolds_open_stub_when_absent(tmp_path):
    stats = reconcile_dispositions(tmp_path, ["generic/range/glucose/max"])
    data = yaml.safe_load((tmp_path / "qa_dispositions.yaml").read_text())
    entry = data["dispositions"][0]
    assert entry["flag_id"] == "generic/range/glucose/max"
    assert entry["disposition"] == "open"
    assert stats.added == 1 and stats.resolved == 0 and stats.unchanged == 0


def test_preserves_filled_entries_and_marks_resolved(tmp_path):
    path = tmp_path / "qa_dispositions.yaml"
    _write(path, [
        {"flag_id": "a/b/c/-", "disposition": "addressed", "note": "fixed", "change": "min_genes=200"},
        {"flag_id": "stale/x/y/-", "disposition": "accepted-real", "note": "ok"},
    ])
    stats = reconcile_dispositions(tmp_path, ["a/b/c/-", "new/d/e/-"])
    data = {e["flag_id"]: e for e in yaml.safe_load(path.read_text())["dispositions"]}
    assert data["a/b/c/-"]["disposition"] == "addressed"     # preserved
    assert data["a/b/c/-"]["change"] == "min_genes=200"      # preserved
    assert data["new/d/e/-"]["disposition"] == "open"        # added
    assert data["stale/x/y/-"]["disposition"] == "resolved"  # vanished
    assert (stats.added, stats.resolved, stats.unchanged) == (1, 1, 1)


def test_never_overwrites_on_repeat(tmp_path):
    reconcile_dispositions(tmp_path, ["a/b/c/-"])
    path = tmp_path / "qa_dispositions.yaml"
    data = yaml.safe_load(path.read_text())
    data["dispositions"][0]["disposition"] = "investigating"
    path.write_text(yaml.safe_dump(data, sort_keys=True))
    reconcile_dispositions(tmp_path, ["a/b/c/-"])
    again = yaml.safe_load(path.read_text())
    assert again["dispositions"][0]["disposition"] == "investigating"


def test_valid_dispositions_set():
    assert VALID_DISPOSITIONS == {"open", "investigating", "addressed", "accepted-real", "wont-fix", "resolved"}
