from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset
from rdflib.namespace import RDF

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.graph.store import PROJECT_NS, SCI_NS

rdflib = pytest.importorskip("rdflib")


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(
    root: Path,
    slug: str,
    title: str | None = None,
    *,
    status: str = "active",
    extra_frontmatter: str = "",
    kind: str = "proposition",
) -> Path:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        f"kind: {kind}\n"
        f"title: {title or slug}\n"
        f"status: {status}\n"
        f"{extra_frontmatter}"
        "---\n\n"
        "Claim.\n",
        encoding="utf-8",
    )
    return path


def _build_knowledge_graph(root: Path):
    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(root, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(out_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def _entity_uri(ref: str):
    kind, slug = ref.split(":", 1)
    return PROJECT_NS[f"{kind}/{slug}"]


def test_live_superseded_without_lineage_is_graph_neutral(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="superseded")
    _proposition(tmp_path, "new")

    knowledge = _build_knowledge_graph(tmp_path)

    assert list(knowledge.triples((None, SCI_NS.supersededBy, None))) == []


def test_live_superseded_by_emits_superseded_by_edge(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "old",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:new\n",
    )
    _proposition(tmp_path, "new")

    knowledge = _build_knowledge_graph(tmp_path)

    assert (
        _entity_uri("proposition:old"),
        SCI_NS.supersededBy,
        _entity_uri("proposition:new"),
    ) in knowledge


def test_live_resynthesized_into_emits_one_superseded_by_edge_per_target(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:positive\n"
            "  - proposition:negative\n"
        ),
    )
    _proposition(tmp_path, "positive")
    _proposition(tmp_path, "negative")

    knowledge = _build_knowledge_graph(tmp_path)

    assert set(knowledge.objects(_entity_uri("proposition:broad"), SCI_NS.supersededBy)) == {
        _entity_uri("proposition:negative"),
        _entity_uri("proposition:positive"),
    }


def test_live_lineage_can_target_active_archived_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "old",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:archived-successor\n",
    )
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:archived-successor",
            kind="proposition",
            title="Archived successor",
            original_path="entities/propositions/archived-successor.md",
            archived_at="T1",
        ),
    )

    knowledge = _build_knowledge_graph(tmp_path)

    archived_successor = _entity_uri("proposition:archived-successor")
    assert (
        _entity_uri("proposition:old"),
        SCI_NS.supersededBy,
        archived_successor,
    ) in knowledge
    assert (archived_successor, RDF.type, SCI_NS.ArchivedEntity) in knowledge


@pytest.mark.parametrize(
    ("extra_frontmatter", "match"),
    [
        ("superseded_by: proposition:new\n", "status"),
        (
            "superseded_by: proposition:new\n"
            "resynthesized_into:\n"
            "  - proposition:other\n",
            "both superseded_by and resynthesized_into",
        ),
    ],
)
def test_live_lineage_rejects_invalid_owner_state(
    tmp_path: Path,
    extra_frontmatter: str,
    match: str,
) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="active", extra_frontmatter=extra_frontmatter)
    _proposition(tmp_path, "new")
    _proposition(tmp_path, "other")

    with pytest.raises(ValueError, match=match):
        _build_knowledge_graph(tmp_path)


@pytest.mark.parametrize(
    ("extra_frontmatter", "match"),
    [
        ("superseded_by: proposition:missing\n", "unknown live lineage target"),
        (
            "resynthesized_into:\n"
            "  - proposition:new\n"
            "  - proposition:new\n",
            "duplicate",
        ),
        ("superseded_by: proposition:old\n", "cannot supersede itself"),
        ("superseded_by:\n", "malformed superseded_by"),
        ("resynthesized_into: proposition:new\n", "malformed resynthesized_into"),
    ],
)
def test_live_lineage_rejects_invalid_targets(
    tmp_path: Path,
    extra_frontmatter: str,
    match: str,
) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="superseded", extra_frontmatter=extra_frontmatter)
    _proposition(tmp_path, "new")

    with pytest.raises(ValueError, match=match):
        _build_knowledge_graph(tmp_path)


def test_live_lineage_rejects_raw_owner_not_loaded_as_live_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(
        tmp_path,
        "old",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:new\n",
        kind="not-a-real-kind",
    )
    _proposition(tmp_path, "new")

    with pytest.raises(ValueError, match="not a loaded live entity"):
        _build_knowledge_graph(tmp_path)
