from pathlib import Path

from click.testing import CliRunner

from science_tool import cli
from science_tool.graph import belief_snapshot


def test_belief_snapshot_writes_jsonl(tmp_path: Path, monkeypatch):
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n", encoding="utf-8")
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "graph.trig").write_text("", encoding="utf-8")

    canned = [{
        "as_of": "2026-05-24", "claim": "prop:p1", "belief_state": "fragile",
        "contested": False, "diagnostic_dispute_count": 0, "scalar_enabled": False,
        "massed_support_score": None, "massed_dispute_score": None,
        "massed_support_band": None, "massed_dispute_band": None,
        "net_band": None, "net_robust": None,
        "input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v3",
        "policy_id": "core-default", "policy_version": "1",
    }]
    monkeypatch.setattr(belief_snapshot, "make_snapshots", lambda *a, **k: canned)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["belief", "snapshot", "--path", str(tmp_path / "knowledge" / "graph.trig"),
         "--as-of", "2026-05-24"],
    )
    assert result.exit_code == 0, result.output
    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    assert out.is_file()
    assert "prop:p1" in out.read_text(encoding="utf-8")
    assert "1 new rows" in result.output


def test_belief_profile_emits_json_query_rows(tmp_path: Path, monkeypatch):
    from science_tool.graph import belief_profile

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text("", encoding="utf-8")

    canned = [
        {
            "entity": "proposition:pa",
            "kind": "proposition",
            "label": "Panel membership claim",
            "belief_state": "fragile",
            "contested": False,
            "epistemic_labels": ["fragile", "single_source"],
            "evidence": {
                "support_count": 1,
                "dispute_count": 0,
                "diagnostic_count": 0,
                "source_count": 1,
                "evidence_types": ["expert_judgment"],
                "has_empirical_data": False,
            },
            "caps": {
                "authored_capped": False,
                "qa_dataset_capped": False,
                "capped_by_refutation": False,
            },
            "freshness_state": None,
            "belief_scalar": None,
        }
    ]
    calls = []

    def fake_make_profiles(path, *, include_all=False, kinds=(), labels=()):
        calls.append((path, include_all, kinds, labels))
        return canned

    monkeypatch.setattr(belief_profile, "make_profiles", fake_make_profiles)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "belief",
            "profile",
            "--path",
            str(graph_path),
            "--format",
            "json",
            "--all",
            "--kind",
            "proposition",
            "--label",
            "fragile",
            "--label",
            "single_source",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(graph_path, True, ("proposition",), ("fragile", "single_source"))]

    import json

    payload = json.loads(result.output)
    assert payload["format"] == "json"
    assert payload["rows"] == canned
    assert payload["meta"] == {
        "count": 1,
        "include_all": True,
        "kinds": ["proposition"],
        "labels": ["fragile", "single_source"],
    }
