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
        "input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v1",
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
