from __future__ import annotations

from pathlib import Path

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.sources import load_project_sources


def _seed(root: Path, name: str = "proj") -> None:
    (root / "science.yaml").write_text(
        f"name: {name}\nprofile: research\nprofiles: {{local: local}}\n",
        encoding="utf-8",
    )


def _write_md(root: Path, rel: str, cid: str, kind: str, title: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\nkind: "{kind}"\ntitle: "{title}"\n---\n', encoding="utf-8")


def test_normal_load_populates_owner_declarations(tmp_path: Path) -> None:
    _seed(tmp_path, name="proj")
    _write_md(tmp_path, "entities/hypotheses/h1.md", "hypothesis:h1", "hypothesis", "H1")
    sources = load_project_sources(tmp_path, include_commons=False)
    decls = {d.canonical_id: d for d in sources.identity_declarations}
    assert "hypothesis:h1" in decls
    assert decls["hypothesis:h1"].participation_mode is ParticipationMode.OWNER
    assert decls["hypothesis:h1"].owner_scope == "proj"
    assert decls["hypothesis:h1"].deprecated is False
    assert decls["hypothesis:h1"].adapter == "markdown"
