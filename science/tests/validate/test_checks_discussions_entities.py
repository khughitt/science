from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.discussions import check_discussions
from science_tool.validate.context import ValidateContext


def test_discussions_checked_under_entities(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "discussions"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        '---\nid: "discussion:0001-x"\ntype: discussion\nstatus: active\n---\nbody\n',
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_discussions(ctx))
    # Emits an INFO "Checking <path>..." per visited discussion.
    assert any("entities/discussions/0001-x.md" in str(r.path) for r in results)
