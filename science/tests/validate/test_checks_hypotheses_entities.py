from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.hypotheses import check_hypotheses
from science_tool.validate.context import ValidateContext


def test_hypotheses_checked_under_entities_with_numeric_names(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        '---\nid: "hypothesis:0001-x"\nkind: hypothesis\nstatus: proposed\n---\n'
        "## Falsifiability\n\nIt is falsifiable.\n",
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_hypotheses(ctx))
    # The check emits an INFO "Checking <path>..." result for every file it visits.
    assert any("entities/hypotheses/0001-x.md" in str(r.path) for r in results)
