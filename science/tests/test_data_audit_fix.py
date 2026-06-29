# science/tests/test_data_audit_fix.py
"""Conservative fixer for `science data audit --fix`."""
import subprocess
from pathlib import Path

from science_tool.data_audit import Quadrant, audit_project
from science_tool.data_audit_fix import apply_fixes


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _staged(root: Path) -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout
    return {ln for ln in out.splitlines() if ln}


def test_untracked_stranded_record_moves_and_stages(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    moved = [o for o in outcomes if o.violation.quadrant is Quadrant.STRANDED_RECORD]
    assert moved and moved[0].performed and moved[0].action == "move"
    assert not (tmp_path / "data/processed/exp1/RESULTS.md").exists()
    assert (tmp_path / "results/exp1/RESULTS.md").read_text() == "# r\n"
    assert "results/exp1/RESULTS.md" in _staged(tmp_path)


def test_fix_does_not_commit(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    apply_fixes(tmp_path, audit_project(tmp_path))
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path,
                         capture_output=True, text=True)
    assert log.stdout.strip() == ""  # nothing committed


def test_tracked_stranded_record_uses_git_mv(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    subprocess.run(["git", "add", "-f", "data/processed/exp1/RESULTS.md"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    apply_fixes(tmp_path, audit_project(tmp_path))
    assert (tmp_path / "results/exp1/RESULTS.md").exists()
    assert "results/exp1/RESULTS.md" in _staged(tmp_path)


def test_collision_different_content_flags(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"NEW\n")
    _write(tmp_path, "results/exp1/RESULTS.md", b"EXISTING\n")
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.quadrant is Quadrant.STRANDED_RECORD][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "data/processed/exp1/RESULTS.md").exists()  # not moved


def test_leaked_payload_never_moved(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "entities/x/big.feather", b"\x00" * 8)
    subprocess.run(["git", "add", "-f", "entities/x/big.feather"], cwd=tmp_path, check=True)
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.quadrant is Quadrant.LEAKED_PAYLOAD][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "entities/x/big.feather").exists()
