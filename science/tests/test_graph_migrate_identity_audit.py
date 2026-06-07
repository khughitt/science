from pathlib import Path

import pytest
from science_model.entities import Entity, EntityType
from science_model.source_ref import SourceRef
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.graph.migrate import _audit_reference, audit_identity_table, audit_project_sources
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import load_project_sources


def _owner(cid, adapter, path, deprecated=False):
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope="proj",
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=path),
        deprecated=deprecated,
    )


def test_audit_identity_table_reports_collision_rows():
    table = IdentityTable(
        rows=[
            _owner("question:q1", "markdown", "entities/question/0007-q1.md"),
            _owner("question:q1", "aggregate", "knowledge/sources/local/entities.yaml", deprecated=True),
        ]
    )
    rows = audit_identity_table(table)
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "identity_collision"
    assert row["status"] == "fail"
    assert row["source"] == "question:q1"
    assert row["field"] == "owner_scope"
    assert row["target"] == "proj"
    assert "entities/question/0007-q1.md" in row["details"]
    assert "knowledge/sources/local/entities.yaml" in row["details"]


def test_audit_identity_table_clean_when_no_collisions():
    table = IdentityTable(rows=[_owner("hypothesis:h1", "markdown", "entities/hypothesis/0001-h1.md")])
    assert audit_identity_table(table) == []


def _seed(root: Path, name: str = "proj") -> None:
    (root / "science.yaml").write_text(
        f"name: {name}\nprofile: research\nprofiles: {{local: local}}\n", encoding="utf-8"
    )


def _md(root: Path, rel: str, cid: str, kind: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\ntype: "{kind}"\ntitle: "{cid}"\n---\n', encoding="utf-8")


def _agg(root: Path, cid: str, kind: str) -> None:
    # AggregateAdapter reads the `entities:` key of a mapping (aggregate.py:69).
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        f"entities:\n  - canonical_id: {cid}\n    kind: {kind}\n    title: {cid}\n"
        f"    profile: local\n    source_path: knowledge/sources/local/entities.yaml\n",
        encoding="utf-8",
    )


def test_strict_load_still_raises_on_stub_shadow(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/questions/q1.md", "question:q1", "question")
    _agg(tmp_path, "question:q1", "question")
    with pytest.raises(EntityIdentityCollisionError):
        load_project_sources(tmp_path, include_commons=False)


def test_nonstrict_load_then_audit_reports_identity_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/questions/q1.md", "question:q1", "question")
    _agg(tmp_path, "question:q1", "question")
    sources = load_project_sources(tmp_path, include_commons=False, strict_identity=False)
    rows, failed = audit_project_sources(sources)
    assert failed is True
    collision_rows = [r for r in rows if r["check"] == "identity_collision"]
    assert len(collision_rows) == 1
    assert collision_rows[0]["source"] == "question:q1"


def test_clean_project_audit_has_no_identity_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/hypotheses/h1.md", "hypothesis:h1", "hypothesis")
    sources = load_project_sources(tmp_path, include_commons=False)
    rows, _ = audit_project_sources(sources)
    assert [r for r in rows if r["check"] == "identity_collision"] == []


# ---------------------------------------------------------------------------
# _audit_reference: scope_ambiguous -> ambiguous_reference row emission
# ---------------------------------------------------------------------------


def _commons_owner(cid: str) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope="commons",
        adapter="commons-merged",
        source_ref=SourceRef(adapter_name="commons-merged", path="<commons>"),
    )


def _ref_entity(cid: str, kind: str, etype: EntityType, *, related: list[str] | None = None) -> Entity:
    k, slug = cid.split(":", 1)
    return Entity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        type=etype,
        title=cid,
        project="proj",
        ontology_terms=[],
        related=related or [],
        source_refs=[],
        content_preview="",
        file_path=f"entities/{k}/{slug}.md",
    )


def _two_scope_resolver() -> ReferenceResolver:
    # one entity (dedup keeps one) but the identity table records two owner scopes;
    # supplied DIRECTLY because no disk loader produces a two-scope table yet. This is
    # a purely direct unit test of _audit_reference.
    entities = [_ref_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(
        rows=[_owner("topic:bayesian", "markdown", "entities/topics/bayesian.md"), _commons_owner("topic:bayesian")]
    )
    return ReferenceResolver.from_entities(entities, identity_table=table)


def test_audit_reference_emits_ambiguous_reference_row() -> None:
    referer = _ref_entity("hypothesis:h1", "hypothesis", EntityType.HYPOTHESIS, related=["topic:bayesian"])
    rows = _audit_reference(
        referer,
        "related",
        "topic:bayesian",
        _two_scope_resolver(),
        ext_prefixes=frozenset(),
        allow_cross_kind_fallback=True,
        allow_tag=True,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "ambiguous_reference"
    assert row["status"] == "fail"
    assert row["source"] == "hypothesis:h1"
    assert row["field"] == "related"
    assert row["target"] == "topic:bayesian"
    assert "commons" in row["details"]
    assert "proj" in row["details"]  # both owning scopes are listed
    assert "commons:topic:bayesian" in row["details"]  # suggested scoped form


def test_audit_reference_scoped_form_is_not_flagged() -> None:
    referer = _ref_entity("hypothesis:h1", "hypothesis", EntityType.HYPOTHESIS, related=["commons:topic:bayesian"])
    rows = _audit_reference(
        referer,
        "related",
        "commons:topic:bayesian",
        _two_scope_resolver(),
        ext_prefixes=frozenset(),
        allow_cross_kind_fallback=True,
        allow_tag=True,
    )
    assert rows == []
