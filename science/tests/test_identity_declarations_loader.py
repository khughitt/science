from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.errors import EntityIdentityCollisionError
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


def _write_aggregate_stub(root: Path, cid: str, kind: str, title: str) -> None:
    # AggregateAdapter reads the `entities:` key of a MAPPING (aggregate.py:69),
    # not a top-level list.
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                f"  - canonical_id: {cid}",
                f"    kind: {kind}",
                f"    title: {title}",
                "    profile: local",
                "    source_path: knowledge/sources/local/entities.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )


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


def test_aggregate_entry_is_deprecated_owner_declaration(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write_aggregate_stub(tmp_path, "concept:1q-gain", "concept", "1q gain")
    sources = load_project_sources(tmp_path, include_commons=False)
    decls = {d.canonical_id: d for d in sources.identity_declarations}
    assert decls["concept:1q-gain"].deprecated is True
    assert decls["concept:1q-gain"].owner_scope == "proj"


def test_strict_identity_true_still_raises_on_duplicate(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write_md(tmp_path, "entities/questions/q1.md", "question:q1", "question", "Q1")
    _write_aggregate_stub(tmp_path, "question:q1", "question", "Q1")
    with pytest.raises(EntityIdentityCollisionError):
        load_project_sources(tmp_path, include_commons=False)  # strict_identity defaults True


def test_strict_identity_false_records_both_owner_declarations(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write_md(tmp_path, "entities/questions/q1.md", "question:q1", "question", "Q1")
    _write_aggregate_stub(tmp_path, "question:q1", "question", "Q1")
    sources = load_project_sources(tmp_path, include_commons=False, strict_identity=False)
    q1_owners = [
        d
        for d in sources.identity_declarations
        if d.canonical_id == "question:q1" and d.participation_mode is ParticipationMode.OWNER
    ]
    assert len(q1_owners) == 2
    adapters = {d.adapter for d in q1_owners}
    assert adapters == {"markdown", "aggregate"}
    # first entity still wins: exactly one question:q1 entity survives
    assert sum(1 for e in sources.entities if e.canonical_id == "question:q1") == 1
