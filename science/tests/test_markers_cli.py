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


def test_scan_json_includes_legacy_flag() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here.\n")
        result = runner.invoke(markers_group, ["scan", "--root", str(root), "--format", "json"])
        payload = json.loads(result.output)
        assert payload["counts"] == {"MISSING_CITATION": 1}
        hit = payload["hits"][0]
        assert hit["token"] == "MISSING_CITATION"
        assert hit["legacy"] is True


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


def test_migrate_dry_run_lists_files_with_legacy_tokens() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here\n")
        _write(root / "doc" / "b.md", "Already [MISSING_CITATION]\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root)])
        assert result.exit_code == 0
        assert "doc/a.md" in result.output
        assert "doc/b.md" not in result.output
        # File is unchanged in dry-run.
        assert "[NEEDS CITATION]" in (root / "doc" / "a.md").read_text()


def test_migrate_write_rewrites_legacy_to_canonical() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Old [NEEDS CITATION] here\nand again [NEEDS CITATION].\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root), "--write"])
        assert result.exit_code == 0
        new_text = (root / "doc" / "a.md").read_text()
        assert "[NEEDS CITATION]" not in new_text
        assert new_text.count("[MISSING_CITATION]") == 2


def test_migrate_preserves_backticked_legacy_tokens() -> None:
    """Documentation references to the legacy spelling must NOT be rewritten."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Bare [NEEDS CITATION] and `[NEEDS CITATION]` doc-ref.\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root), "--write"])
        text = (root / "doc" / "a.md").read_text()
        # Bare occurrence rewritten:
        assert "Bare [MISSING_CITATION]" in text
        # Backticked doc-reference preserved:
        assert "`[NEEDS CITATION]`" in text


def test_migrate_zero_legacy_tokens_is_noop() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "doc" / "a.md", "Modern [MISSING_CITATION] only.\n")
        result = runner.invoke(markers_group, ["migrate", "--root", str(root), "--write"])
        assert result.exit_code == 0
        assert "no legacy tokens" in result.output.lower()
