"""CLI tests for `science markers`."""
import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from science_tool.markers_cli import markers_group


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_scan_emits_json_with_per_token_counts() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "[UNVERIFIED] [UNVERIFIED] [SPECULATION]\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["counts"] == {"UNVERIFIED": 2, "SPECULATION": 1}
        assert len(payload["hits"]) == 3


def test_scan_json_does_not_include_legacy_field() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Missing [MISSING_CITATION] here.\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        payload = json.loads(result.output)
        assert payload["counts"] == {"MISSING_CITATION": 1}
        hit = payload["hits"][0]
        assert hit["token"] == "MISSING_CITATION"
        assert "legacy" not in hit


def test_scan_text_format_lists_per_token_counts() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "[UNVERIFIED]\n[SPECULATION]\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root)])
        assert "UNVERIFIED" in result.output
        assert "SPECULATION" in result.output


def test_scan_strict_promotes_info_severity() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "[SPECULATION]\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json", "--strict"])
        payload = json.loads(result.output)
        assert payload["hits"][0]["severity"] == "warn"


def test_scan_zero_hits_emits_empty_payload() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "no markers here\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        payload = json.loads(result.output)
        assert payload["counts"] == {}
        assert payload["hits"] == []


def test_migrate_command_is_removed() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root)])
        assert result.exit_code != 0
        assert "No such command" in result.output
        assert "[NEEDS CITATION]" in (root / "doc" / "a.md").read_text()
