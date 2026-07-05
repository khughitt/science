from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.document_structure import check_document_structure
from science_tool.validate.context import ValidateContext


def test_topics_checked_under_entities(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "topics"
    d.mkdir(parents=True)
    (d / "0001-t.md").write_text(
        '---\nid: "topic:0001-t"\nkind: topic\nstatus: active\n---\n# Topic\n',
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_document_structure(ctx))
    # Emits an INFO "Checking <path>..." per visited document.
    assert any("entities/topics/0001-t.md" in str(r.path) for r in results)
