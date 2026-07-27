"""End-to-end acceptance on a sanitized MM30-shaped tree.

Shape derived from MM30 as of 2026-07-26: an external-dataset root whose
descriptors are tracked beside ignored bulk parquet and an ignored raw/ subtree,
a flat gitignored PDF store, and tracked source that an unanchored pattern had
been hiding. No MM30 content, only its layout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.boundary.cli import boundary_group
from science_tool.validate.checks.boundary import check_boundary
from science_tool.validate.context import ValidateContext

DECL = {
    "roots": [
        {
            "path": "data/external",
            "class": "manifest",
            "tracked": ["datapackage.json", "*.qa_verdict.json"],
        },
        {"path": "data/raw", "class": "payload"},
        {"path": "pdfs", "class": "payload"},
    ]
}


def _mm30(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "MM", "id": "mm", "boundary": DECL}))

    def w(rel: str, body: str = "x") -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    w("data/external/opentargets/25.03/datapackage.json", "{}")
    w("data/external/opentargets/25.03/opentargets.qa_verdict.json", "{}")
    w("data/external/opentargets/25.03/mm-associations.parquet")
    w("data/external/opentargets/25.03/raw/target/part-0.parquet")
    w("data/raw/GSE1234_series_matrix.txt", "x" * 200_000)
    w("pdfs/2024_Author_Title.pdf")
    w("tests/migration/archive/test_pilot.py", "def test_x(): pass\n")
    w("entities/hypotheses/h0001.md", "# h\n")
    w(".gitignore", ".venv/\narchive\n")
    return tmp_path


def _rules(root: Path) -> list[str]:
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return [r.rule for r in check_boundary(ctx)]


def test_acceptance_sync_then_clean(tmp_path: Path):
    repo = _mm30(tmp_path)
    runner = CliRunner()

    assert runner.invoke(boundary_group, ["sync", "--project-root", str(repo)]).exit_code == 0
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    staged = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split()

    # Descriptors tracked; payload not.
    assert "data/external/opentargets/25.03/datapackage.json" in staged
    assert "data/external/opentargets/25.03/opentargets.qa_verdict.json" in staged
    assert "data/external/opentargets/25.03/mm-associations.parquet" not in staged
    assert "data/external/opentargets/25.03/raw/target/part-0.parquet" not in staged
    assert "data/raw/GSE1234_series_matrix.txt" not in staged
    assert "pdfs/2024_Author_Title.pdf" not in staged

    # The unanchored bare `archive` rule STILL hides this file: `sync` manages
    # declared roots and deliberately does not rewrite unmanaged rules. Verified
    # against real git -- an earlier draft asserted the opposite.
    assert "tests/migration/archive/test_pilot.py" not in staged

    rules = _rules(repo)
    assert "boundary.tracked-ignored" not in rules  # ignored AND untracked, so no contradiction
    assert "boundary.generated-drift" not in rules
    assert "boundary.unreachable-tracked" not in rules
    assert "boundary.unanchored-pattern" in rules  # the bare `archive` is reported


def test_acceptance_anchoring_the_warned_rule_is_the_remedy(tmp_path: Path):
    """Following the WARN's advice makes the hidden source reachable again.

    This is the check earning its keep: nothing else in the toolchain reports
    that a tracked-looking test file is invisible to git, ripgrep, and ruff.
    """
    repo = _mm30(tmp_path)
    result = CliRunner().invoke(boundary_group, ["sync", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    text = (repo / ".gitignore").read_text().replace("archive\n", "/archive/\n", 1)
    (repo / ".gitignore").write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    staged = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split()
    assert "tests/migration/archive/test_pilot.py" in staged
    assert "boundary.unanchored-pattern" not in _rules(repo)


def test_acceptance_verify_current_tree_is_transactional(tmp_path: Path):
    repo = _mm30(tmp_path)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    before = (repo / ".gitignore").read_text()
    result = CliRunner().invoke(
        boundary_group,
        ["sync", "--verify-current-tree", "--project-root", str(repo)],
    )
    assert result.exit_code == 1, result.output
    assert "ignore decision(s) would change" in result.output
    assert "data/external/opentargets/25.03/mm-associations.parquet" in result.output
    assert "data/raw/GSE1234_series_matrix.txt" in result.output
    assert "pdfs/2024_Author_Title.pdf" in result.output
    assert (repo / ".gitignore").read_text() == before


def test_acceptance_init_proposes_the_same_shape(tmp_path: Path):
    repo = _mm30(tmp_path)
    (repo / "science.yaml").write_text(yaml.safe_dump({"name": "MM", "id": "mm"}))
    output = CliRunner().invoke(boundary_group, ["init", "--project-root", str(repo)]).output
    assert yaml.safe_load(output) == {
        "boundary": {
            "roots": [
                {
                    "path": "data/external",
                    "class": "manifest",
                    "tracked": ["datapackage.json"],
                },
                {"path": "data/raw", "class": "payload"},
                {"path": "pdfs", "class": "payload"},
            ]
        }
    }
