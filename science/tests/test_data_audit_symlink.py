# science/tests/test_data_audit_symlink.py
"""--fix must not move records out of a symlink-hydrated data dir."""
import subprocess
from pathlib import Path

from science_tool.data_audit import Quadrant, audit_project
from science_tool.data_audit_fix import apply_fixes


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def test_record_under_symlinked_data_dir_is_flagged(tmp_path: Path):
    _init_repo(tmp_path)
    # External shared source root (outside the project) holds the real file.
    external = tmp_path.parent / "external_source"
    (external / "processed" / "exp1").mkdir(parents=True, exist_ok=True)
    (external / "processed" / "exp1" / "RESULTS.md").write_text("# r\n")
    # data/processed is a symlink into the external source (data_worktree hydration).
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "processed").symlink_to(external / "processed")

    violations = audit_project(tmp_path)
    stranded = [v for v in violations if v.quadrant is Quadrant.STRANDED_RECORD]
    # Reported: the record under the symlinked data dir IS surfaced.
    assert any(v.path == "data/processed/exp1/RESULTS.md" for v in stranded)
    # Fixed: but --fix FLAGs it (never moves through the symlink).
    outcomes = apply_fixes(tmp_path, violations)
    moved = [o for o in outcomes
             if o.violation.path == "data/processed/exp1/RESULTS.md"][0]
    assert moved.performed is False and moved.action == "flag"
    assert "symlink" in (moved.reason or "")
    # The real external file is untouched; no results/ copy was created.
    assert (external / "processed" / "exp1" / "RESULTS.md").exists()
    assert not (tmp_path / "results" / "exp1" / "RESULTS.md").exists()
