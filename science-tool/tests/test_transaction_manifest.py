"""ManifestSnapshot: take/restore for declared paths, no Git required."""

from pathlib import Path

from science_tool.project_artifacts.migrations.transaction import ManifestSnapshot


def test_take_restore_round_trip_outside_git(tmp_path: Path) -> None:
    target_a = tmp_path / "a.txt"
    target_b = tmp_path / "sub" / "b.txt"
    target_a.write_text("orig-a", encoding="utf-8")
    target_b.parent.mkdir()
    target_b.write_text("orig-b", encoding="utf-8")

    snap = ManifestSnapshot(tmp_path, touched_paths=[Path("a.txt"), Path("sub/b.txt")])
    snap.take()

    target_a.write_text("modified-a", encoding="utf-8")
    target_b.write_text("modified-b", encoding="utf-8")

    snap.restore()

    assert target_a.read_text(encoding="utf-8") == "orig-a"
    assert target_b.read_text(encoding="utf-8") == "orig-b"


def test_restore_recreates_deleted_file(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("orig", encoding="utf-8")
    snap = ManifestSnapshot(tmp_path, touched_paths=[Path("a.txt")])
    snap.take()
    target.unlink()
    snap.restore()
    assert target.read_text(encoding="utf-8") == "orig"


def test_restore_only_touches_declared_paths(tmp_path: Path) -> None:
    declared = tmp_path / "a.txt"
    other = tmp_path / "b.txt"
    declared.write_text("a-orig", encoding="utf-8")
    other.write_text("b-orig", encoding="utf-8")
    snap = ManifestSnapshot(tmp_path, touched_paths=[Path("a.txt")])
    snap.take()
    declared.write_text("a-mod", encoding="utf-8")
    other.write_text("b-mod", encoding="utf-8")
    snap.restore()
    assert declared.read_text(encoding="utf-8") == "a-orig"
    assert other.read_text(encoding="utf-8") == "b-mod"  # not restored


def test_discard_is_noop(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    snap = ManifestSnapshot(tmp_path, touched_paths=[Path("a.txt")])
    snap.take()
    target.write_text("y", encoding="utf-8")
    snap.discard(commit_message="ignored")
    assert target.read_text(encoding="utf-8") == "y"  # discard does not restore


def test_restore_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("orig", encoding="utf-8")
    snap = ManifestSnapshot(tmp_path, touched_paths=[Path("a.txt")])
    snap.take()
    target.write_text("mod", encoding="utf-8")
    snap.restore()
    assert target.read_text(encoding="utf-8") == "orig"
    # Second restore must not raise; covers update.update_artifact's
    # outer-except path that runs after run_migration already restored.
    snap.restore()
    assert target.read_text(encoding="utf-8") == "orig"
