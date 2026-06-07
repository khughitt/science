from science_model.source_ref import SourceRef
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.graph.migrate import audit_identity_table


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
