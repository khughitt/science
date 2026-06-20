from dataclasses import dataclass as _dc
from dataclasses import field as _f

import pytest
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import (
    IdentityCollision,
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
    build_identity_table,
    classify_owner_scope,
)


def _decl(cid, mode=ParticipationMode.OWNER, scope="proj", adapter="markdown", path="p", deprecated=False):
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=mode,
        owner_scope=scope,
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=path),
        deprecated=deprecated,
    )


def test_modes_and_row_defaults():
    assert ParticipationMode.OWNER.value == "owner"
    assert ParticipationMode.BORROWER.value == "borrower"
    assert ParticipationMode.EXTERNAL_REFERENCE.value == "external-reference"
    row = _decl("hypothesis:h1")
    assert row.deprecated is False
    assert row.owner_scope == "proj"


def test_owners_keyed_by_scope_and_id_no_collision_when_clean():
    table = IdentityTable(rows=[_decl("hypothesis:h1"), _decl("task:t1", adapter="task")])
    assert set(table.owners()) == {("proj", "hypothesis:h1"), ("proj", "task:t1")}
    assert table.collisions() == []


def test_collision_when_two_owners_share_key_stub_shadow():
    table = IdentityTable(
        rows=[
            _decl("question:q1", adapter="markdown", path="entities/question/0007-q1.md"),
            _decl("question:q1", adapter="aggregate", path="knowledge/sources/local/entities.yaml", deprecated=True),
        ]
    )
    cols = table.collisions()
    assert len(cols) == 1
    assert cols[0].owner_scope == "proj"
    assert cols[0].canonical_id == "question:q1"
    assert len(cols[0].rows) == 2
    assert any(r.deprecated for r in cols[0].rows)  # the stub is flagged


def test_no_collision_across_scopes_or_for_borrower():
    table = IdentityTable(
        rows=[
            _decl("topic:bayesian", scope="commons", adapter="commons-merged"),
            _decl("topic:bayesian", mode=ParticipationMode.BORROWER, scope="commons", adapter="overlay"),
            _decl("topic:bayesian", scope="proj"),  # different scope key
        ]
    )
    # commons owner + commons borrower + proj owner => no key has >1 OWNER row
    assert table.collisions() == []


_COMMONS = "commons"


def test_classify_owner_scope():
    # aggregate AND datapackage are transitional deprecated owners (design §B4/§C3):
    # in the target state datapackages are attachments, not owners, so any datapackage
    # currently emitting an entity is an orphan/transitional owner to be migrated.
    assert classify_owner_scope("aggregate", project_name="proj") == ("proj", True)
    assert classify_owner_scope("datapackage", project_name="proj") == ("proj", True)
    # commons-merged is owned by the commons scope, not deprecated
    assert classify_owner_scope("commons-merged", project_name="proj") == (_COMMONS, False)
    # everything else (markdown/task/workflow-run/code-file/legacy-*) is a plain owner
    for adapter in ("markdown", "task", "workflow-run", "code-file", "legacy-model", "legacy-parameter"):
        assert classify_owner_scope(adapter, project_name="proj") == ("proj", False)


def test_classify_owner_scope_rejects_empty_adapter():
    with pytest.raises(ValueError):
        classify_owner_scope("", project_name="proj")


@_dc
class _Sources:
    identity_declarations: list = _f(default_factory=list)


def test_build_identity_table_wraps_declarations_and_finds_collisions():
    src = _Sources(
        identity_declarations=[
            _decl("question:q1", adapter="markdown", path="entities/question/0007-q1.md"),
            _decl("question:q1", adapter="aggregate", path="knowledge/sources/local/entities.yaml", deprecated=True),
            _decl("hypothesis:h1"),
        ]
    )
    table = build_identity_table(src)
    assert len(table.rows) == 3
    cols = table.collisions()
    assert [c.canonical_id for c in cols] == ["question:q1"]


def test_owner_scopes_by_id_groups_scopes_per_canonical_id() -> None:
    def owner(cid: str, scope: str) -> IdentityDeclaration:
        return IdentityDeclaration(
            canonical_id=cid,
            participation_mode=ParticipationMode.OWNER,
            owner_scope=scope,
            adapter="markdown",
            source_ref=None,
        )

    table = IdentityTable(
        rows=[
            owner("topic:bayesian", "proj"),
            owner("topic:bayesian", "commons"),  # same id, two scopes
            owner("hypothesis:h1", "proj"),
            IdentityDeclaration(  # a borrower row must NOT count as an owning scope
                canonical_id="topic:bayesian",
                participation_mode=ParticipationMode.BORROWER,
                owner_scope="commons",
                adapter="overlay",
                source_ref=None,
            ),
        ]
    )
    index = table.owner_scopes_by_id()
    assert index["topic:bayesian"] == frozenset({"proj", "commons"})
    assert index["hypothesis:h1"] == frozenset({"proj"})


def _collision(*deprecations: bool) -> IdentityCollision:
    rows = tuple(
        IdentityDeclaration(
            canonical_id="dataset:x",
            participation_mode=ParticipationMode.OWNER,
            owner_scope="proj",
            adapter="markdown",
            source_ref=SourceRef(adapter_name="markdown", path=f"p{i}.md"),
            deprecated=dep,
        )
        for i, dep in enumerate(deprecations)
    )
    return IdentityCollision(owner_scope="proj", canonical_id="dataset:x", rows=rows)


def test_is_genuine_two_real_owners() -> None:
    assert _collision(False, False).is_genuine is True


def test_is_genuine_transitional_shadow_is_not_genuine() -> None:
    # one real markdown owner + one deprecated aggregate/datapackage stub -> carried, not a hard error
    assert _collision(False, True).is_genuine is False


def test_is_genuine_two_deprecated_owners_is_not_genuine() -> None:
    assert _collision(True, True).is_genuine is False
